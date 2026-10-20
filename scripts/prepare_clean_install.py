"""Copy source without secrets/state and install/test into a new Windows environment."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    target = args.target.resolve()
    if target.exists() or target.is_relative_to(ROOT):
        raise ValueError('Target must be new and outside the project source')
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('.git', '.env', 'runtime', '.venv', 'venv', 'node_modules', 'dist', '__pycache__', '.pytest_cache', 'raw', '*.pyc', '*.log'))
    shutil.copy2(target/'.env.example', target/'.env')
    log_dir = ROOT/'runtime/clean-install'
    log_dir.mkdir(parents=True, exist_ok=True)
    records = []
    def run(name, command, cwd=target):
        print(name, flush=True)
        start = time.time()
        with (log_dir/(name+'.log')).open('w', encoding='utf-8') as log:
            completed = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'PYTHONUTF8': '1'})
        records.append({'name': name, 'command': command, 'returncode': completed.returncode, 'seconds': round(time.time()-start, 2)})
        if completed.returncode:
            raise RuntimeError(f'{name} failed, inspect {log_dir/(name+".log")}')
    run('create_venv', [sys.executable, '-m', 'venv', str(target/'.venv')])
    python = str(target/'.venv/Scripts/python.exe')
    requirements = 'requirements-lock.txt' if (target/'requirements-lock.txt').exists() else 'requirements.txt'
    run('pip_install', [python, '-m', 'pip', 'install', '-r', requirements, '--disable-pip-version-check'])
    run('pip_check', [python, '-m', 'pip', 'check'])
    run('backend_tests', [python, '-m', 'pytest', '-q'])
    run('npm_ci', ['cmd.exe', '/d', '/c', 'npm.cmd', 'ci'], target/'frontend')
    run('frontend_tests', ['cmd.exe', '/d', '/c', 'npm.cmd', 'test'], target/'frontend')
    run('frontend_build', ['cmd.exe', '/d', '/c', 'npm.cmd', 'run', 'build'], target/'frontend')
    record = {'kind': 'same_machine_clean_isolated_install', 'target': str(target), 'fresh_venv': True,
              'fresh_node_modules': True, 'new_database': True, 'credentials_copied': False, 'steps': records}
    (ROOT/'docs/干净环境安装验证.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Clean install and tests completed: '+str(target), flush=True)


if __name__ == '__main__':
    main()
