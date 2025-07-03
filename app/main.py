import json
import os

# import shutil
# import signal
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from time import sleep

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

# from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DB_PATH = 'data/tasks.db'
LOG_DIR = 'logs'
os.makedirs('data', exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))


# In-memory store of running tasks: {task_id: Popen}
running_tasks = {}
task_threads = {}

# ---------- BBDD ----------


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                script_path TEXT NOT NULL,
                interval_days INTEGER,
                interval_hours INTEGER,
                interval_minutes INTEGER,
                weekdays TEXT,
                start_datetime TEXT,
                last_started TEXT,
                last_stopped TEXT,
                active INTEGER DEFAULT 1
            );
        """)
        conn.commit()


def get_all_tasks():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT * FROM tasks')
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_task(task_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))


def update_task_field(task_id, field, value):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f'UPDATE tasks SET {field} = ? WHERE id = ?', (value, task_id))
        conn.commit()


# ---------- LOG ----------


def get_log_filename():
    return os.path.join(LOG_DIR, f'{datetime.now().strftime("%Y-%m-%d")}.log')


def write_log(task_id, message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] [Tarea {task_id}] {message}\n'
    with open(get_log_filename(), 'a', encoding='utf-8') as f:
        f.write(line)


# ---------- EJECUCIÓN ----------


def run_script(task):
    task_id = task['id']
    script_path = task['script_path']
    if not os.path.exists(script_path):
        write_log(task_id, f"ERROR: Script '{script_path}' no encontrado.")
        return

    write_log(task_id, 'Iniciando ejecución.')
    update_task_field(task_id, 'last_started', datetime.now().isoformat())

    process = subprocess.Popen(['python', script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    running_tasks[task_id] = process

    for line in process.stdout:
        write_log(task_id, line.strip())

    process.wait()
    write_log(task_id, f'Finalizado con código {process.returncode}.')
    update_task_field(task_id, 'last_stopped', datetime.now().isoformat())
    running_tasks.pop(task_id, None)


def scheduler_loop(task):
    task_id = task['id']
    while True:
        task = get_task(task_id)
        if not task or not task['active']:
            break

        start_dt = datetime.fromisoformat(task['start_datetime'])
        interval = timedelta(
            days=task['interval_days'] or 0, hours=task['interval_hours'] or 0, minutes=task['interval_minutes'] or 0
        )
        weekdays = json.loads(task['weekdays'])

        now = datetime.now()
        should_run = (
            now >= start_dt
            and now.strftime('%A') in weekdays
            and (not task['last_started'] or datetime.fromisoformat(task['last_started']) + interval <= now)
        )

        if should_run and task_id not in running_tasks:
            thread = Thread(target=run_script, args=(task,))
            thread.start()

        sleep(30)  # Check every 30 seconds


# ---------- RUTAS ----------


@app.get('/', response_class=HTMLResponse)
def serve_index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.get('/api/tasks')
def api_get_tasks():
    return get_all_tasks()


@app.post('/api/tasks')
def api_create_task(
    name: str = Form(...),
    script_path: str = Form(...),
    interval_days: int = Form(0),
    interval_hours: int = Form(0),
    interval_minutes: int = Form(0),
    weekdays: str = Form(...),  # JSON list
    start_datetime: str = Form(...),
):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (
                name, script_path,
                interval_days, interval_hours, interval_minutes,
                weekdays, start_datetime, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
            (name, script_path, interval_days, interval_hours, interval_minutes, weekdays, start_datetime),
        )
        conn.commit()
        task_id = cursor.lastrowid

    task = get_task(task_id)
    thread = Thread(target=scheduler_loop, args=(task,))
    thread.start()
    task_threads[task_id] = thread
    return {'status': 'ok', 'id': task_id}


@app.post('/api/tasks/{task_id}/run')
def api_run_now(task_id: int):
    task = get_task(task_id)
    if task:
        Thread(target=run_script, args=(task,)).start()
        return {'status': 'ok'}
    return JSONResponse({'error': 'Tarea no encontrada'}, status_code=404)


@app.post('/api/tasks/{task_id}/stop')
def api_stop_task(task_id: int):
    proc = running_tasks.get(task_id)
    if proc:
        proc.terminate()
        write_log(task_id, 'Tarea detenida manualmente.')
        return {'status': 'ok'}
    return JSONResponse({'error': 'No se está ejecutando'}, status_code=400)


@app.post('/api/tasks/{task_id}/resume')
def api_resume_task(task_id: int):
    task = get_task(task_id)
    if task:
        update_task_field(task_id, 'active', 1)
        if task_id not in task_threads:
            thread = Thread(target=scheduler_loop, args=(task,))
            thread.start()
            task_threads[task_id] = thread
        return {'status': 'ok'}
    return JSONResponse({'error': 'Tarea no encontrada'}, status_code=404)


@app.get('/api/logs')
def api_list_logs():
    return sorted(os.listdir(LOG_DIR))


@app.get('/api/logs/{log_file}')
def api_read_log(log_file: str):
    path = os.path.join(LOG_DIR, log_file)
    if not os.path.exists(path):
        return JSONResponse({'error': 'Archivo no encontrado'}, status_code=404)
    with open(path, encoding='utf-8') as f:
        return {'log': f.read()}


# ---------- BOOT ----------

if __name__ == '__main__':
    import uvicorn

    init_db()

    for task in get_all_tasks():
        if task['active']:
            thread = Thread(target=scheduler_loop, args=(task,))
            thread.start()
            task_threads[task['id']] = thread

    uvicorn.run(app, host='0.0.0.0', port=8000)
