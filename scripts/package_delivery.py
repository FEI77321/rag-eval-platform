"""Create timestamped source and complete-results delivery archives."""
from datetime import datetime
import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime('%Y-%m-%d-%H%M%S')
PARENT = ROOT.parent
SOURCE_ZIP = PARENT / f'rag-eval-platform-final-{STAMP}.zip'
RESULTS_DIR = PARENT / f'rag-eval-results-final-{STAMP}'
RESULTS_ZIP = PARENT / f'rag-eval-results-final-{STAMP}.zip'

EXCLUDED_DIRS = {
    '.git', '.pytest_cache', '__pycache__', 'node_modules', 'dist',
    'runtime', 'venv', '.venv', 'reports/raw',
}
EXCLUDED_FILES = {'.env', 'platform.db', 'platform.db-shm', 'platform.db-wal'}


def source_files():
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        parts = relative.parts
        if any(part in EXCLUDED_DIRS for part in parts):
            continue
        if relative.as_posix().startswith('reports/raw/'):
            continue
        if path.name in EXCLUDED_FILES or path.suffix in {'.pyc', '.pyo'}:
            continue
        yield path


with zipfile.ZipFile(SOURCE_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in source_files():
        archive.write(path, Path(ROOT.name) / path.relative_to(ROOT))

with zipfile.ZipFile(SOURCE_ZIP) as archive:
    names = archive.namelist()
    assert archive.testzip() is None
    assert not any(name.endswith('/.env') or '/runtime/' in name or '/node_modules/' in name for name in names)
    assert any(name.endswith('docs/BadCase分析报告.md') for name in names)
    assert any(name.endswith('data/eval_set.json') for name in names)
print(f'Source archive verified: {SOURCE_ZIP.name} ({SOURCE_ZIP.stat().st_size} bytes)')

RESULTS_DIR.mkdir()
source_db = ROOT / 'runtime/platform.db'
if not source_db.exists():
    raise FileNotFoundError(f'Complete results database not found: {source_db}')
db_copy = RESULTS_DIR / 'platform.db'
with sqlite3.connect(source_db) as source, sqlite3.connect(db_copy) as destination:
    source.backup(destination)
with sqlite3.connect(db_copy) as connection:
    assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

state = json.loads((ROOT / 'runtime/real_campaign.json').read_text(encoding='utf-8'))
review_folder = ROOT / 'reports/raw' / state['full_run']
if review_folder.exists():
    shutil.copytree(review_folder, RESULTS_DIR / '人工独立评分')
for report_name in ('运行汇总.json', '指标汇总.csv', 'BadCase分析报告.md', 'BadCase样本.json', 'Judge一致性报告.md',
                    'Judge复核裁决.json', 'Judge复核裁决报告.md', '配置对比报告.md', '配置对比图.svg'):
    report = ROOT / 'reports' / state['full_run'] / report_name
    if report.exists():
        shutil.copy2(report, RESULTS_DIR / report.name)
revised = ROOT / 'reports' / state['full_run'] / '复核裁决版'
if revised.exists():
    shutil.copytree(revised, RESULTS_DIR / '复核裁决版')
for name in ('干净环境安装验证.json', '干净环境部署验证.json', '部署验收记录.json'):
    record = ROOT / 'docs' / name
    if record.exists():
        shutil.copy2(record, RESULTS_DIR / name)
(RESULTS_DIR / '说明.md').write_text(
    '# 本机完整结果备份\n\n'
    'platform.db由SQLite backup API复制并通过PRAGMA integrity_check；包含原始召回、生成、Judge、'
    '人工评分和模型调用账本。源码与结果分开打包；源码包不含运行数据库、密钥或依赖目录。\n\n'
    '恢复时先停止API与Worker，备份现有数据库，再将platform.db放入项目runtime/platform.db。\n',
    encoding='utf-8',
)
with zipfile.ZipFile(RESULTS_ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in RESULTS_DIR.rglob('*'):
        if path.is_file():
            archive.write(path, Path(RESULTS_DIR.name) / path.relative_to(RESULTS_DIR))
with zipfile.ZipFile(RESULTS_ZIP) as archive:
    assert archive.testzip() is None
print(f'Results archive verified: {RESULTS_ZIP.name} ({RESULTS_ZIP.stat().st_size} bytes)')
