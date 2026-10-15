"""源码与完整结果分别打包；源码含Git历史，不含密钥、依赖或数据库。"""
import json,sqlite3,subprocess,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
target=ROOT.parent/'rag-eval-platform.zip'
files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name in files:
        path=ROOT/name
        if name and path.is_file():archive.write(path,Path(ROOT.name)/name)
    for path in (ROOT/'.git').rglob('*'):
        if path.is_file() and path.name not in ['index.lock','COMMIT_EDITMSG']:
            archive.write(path,Path(ROOT.name)/path.relative_to(ROOT))
with zipfile.ZipFile(target) as archive:
    assert not any(n.endswith('/.env') or '/runtime/' in n or '/node_modules/' in n for n in archive.namelist())
    assert archive.testzip() is None
print('Source package verified:',target.name,target.stat().st_size,'bytes')
data_target=ROOT.parent/'rag-eval-results'
data_target.mkdir(exist_ok=True)
source_db=ROOT/'runtime/platform.db'
if source_db.exists():
    with sqlite3.connect(source_db) as source,sqlite3.connect(data_target/'platform.db') as dest:
        source.backup(dest)
    with sqlite3.connect(data_target/'platform.db') as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    state=json.loads((ROOT/'runtime/real_campaign.json').read_text(encoding='utf-8'))
    review_folder=ROOT/'reports/raw'/state['full_run']
    if review_folder.exists():
        shutil.copytree(review_folder,data_target/'人工独立评分',dirs_exist_ok=True)
    (data_target/'说明.md').write_text('# 本机完整结果备份\n\nplatform.db通过SQLite备份API一致性复制，含原始召回、生成、Judge、调用账本及历史demo。不是只复制WAL主文件。无.env与API密钥。\n\n恢复时先停止本项目服务，备份现有数据库，再把本文件放入项目runtime/platform.db；不要在服务写入时直接替换。源码包与本结果库分开，结果库不进Git。\n',encoding='utf-8')
    print('SQLite backup integrity: ok')
    with zipfile.ZipFile(ROOT.parent/'rag-eval-results.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in data_target.rglob('*'):
            if path.is_file():archive.write(path,Path(data_target.name)/path.relative_to(data_target))
    print('Results package prepared separately from source')
