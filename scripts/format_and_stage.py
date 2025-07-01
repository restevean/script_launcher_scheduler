# scripts/format_and_stage.py
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    print(f'Running: {" ".join(cmd)}')
    return subprocess.call(cmd)


files = [f for f in sys.argv[1:] if Path(f).suffix == '.py']
if not files:
    print('No hay archivos Python que formatear.')
    sys.exit(0)

# ret = run(["poetry", "run", "ruff", "check", "--fix", "--line-length", "120"] + files)
# run(["poetry", "run", "ruff", "format", "--line-length", "120"] + files)
# run(["git", "add"] + files)

# Ejecutar Ruff con autocorrección y formateo
run(['poetry', 'run', 'ruff', 'check', '--fix', '--line-length', '120'] + files)
run(['poetry', 'run', 'ruff', 'format', '--line-length', '120'] + files)
run(['git', 'add'] + files)

sys.exit(0)
