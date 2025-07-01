import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from main import DB_PATH, LOG_DIR, app, get_all_tasks, init_db, update_task_field

client = TestClient(app)


def setup_module(module):
    """Preparar entorno aislado para los tests"""
    os.makedirs('data', exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    init_db()


def teardown_module(module):
    """Limpiar tras los tests"""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(LOG_DIR):
        shutil.rmtree(LOG_DIR)


def test_create_and_get_task():
    # Crear una tarea usando la API
    start_time = (datetime.now() + timedelta(minutes=1)).isoformat(timespec='minutes')
    response = client.post(
        '/api/tasks',
        data={
            'name': 'Test task',
            'script_path': 'scripts/fake.py',
            'interval_days': 0,
            'interval_hours': 0,
            'interval_minutes': 1,
            'weekdays': json.dumps(['Monday', 'Tuesday']),
            'start_datetime': start_time,
        },
    )
    assert response.status_code == 200
    task_id = response.json()['id']

    # Obtener tareas y comprobar que se ha creado correctamente
    response = client.get('/api/tasks')
    assert response.status_code == 200
    tasks = response.json()
    assert any(t['id'] == task_id for t in tasks)


def test_update_task_field_and_run_now():
    task = get_all_tasks()[0]
    task_id = task['id']

    # Modificar campo "active"
    update_task_field(task_id, 'active', 0)
    updated = get_all_tasks()[0]
    assert updated['active'] == 0

    # Ejecutar tarea manualmente
    response = client.post(f'/api/tasks/{task_id}/run')
    assert response.status_code == 200 or response.status_code == 404


def test_stop_and_resume_task():
    task = get_all_tasks()[0]
    task_id = task['id']

    # Intentar detenerla
    response = client.post(f'/api/tasks/{task_id}/stop')
    assert response.status_code in [200, 400]

    # Reanudar
    response = client.post(f'/api/tasks/{task_id}/resume')
    assert response.status_code == 200


def test_logs_creation_and_listing():
    # Escribir un log de prueba
    log_file = os.path.join(LOG_DIR, datetime.now().strftime('%Y-%m-%d') + '.log')
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write('[test log line]\n')

    # Comprobar que aparece en /api/logs
    response = client.get('/api/logs')
    assert response.status_code == 200
    files = response.json()
    assert any(f.endswith('.log') for f in files)

    # Leer contenido de log
    log_name = files[0]
    response = client.get(f'/api/logs/{log_name}')
    assert response.status_code == 200
    assert '[test log line]' in response.json()['log']
