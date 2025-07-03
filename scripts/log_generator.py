#!/usr/bin/env python3
import random
import time
from datetime import datetime

MESSAGES = [
    'Inicializando módulo principal',
    'Conectando a la base de datos',
    'Proceso de ejecución iniciado',
    'Lectura de parámetros completada',
    'Ejecutando tarea programada',
    'Tarea finalizada con éxito',
    'Recibiendo señal de parada',
    'Guardando registros en disco',
    'Reanudando ejecución tras pausa',
    'Finalizando proceso con código 0',
]


def main():
    try:
        while True:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg = random.choice(MESSAGES)
            print(f'[{now}] {msg}')
            time.sleep(1 + random.random() * 2)  # espera entre 1 y 3 segundos
    except KeyboardInterrupt:
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Proceso de log detenido por el usuario.')


if __name__ == '__main__':
    main()
