"""把已重算的本机结果快照同步到同一报告，保留报告身份。"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
target=ROOT.parent/'rag-eval-report'/'src'/'data.json'
if not target.exists():raise SystemExit('请先通过Data报告工具准备rag-eval-report')
old=json.loads(target.read_text(encoding='utf-8'))
fresh=json.loads((ROOT/'runtime/report_snapshot.json').read_text(encoding='utf-8'))
fresh['id']=old['id']
fresh['buildStatus']='complete'
target.write_text(json.dumps(fresh,ensure_ascii=False,indent=2),encoding='utf-8')
print('Report snapshot updated; identity preserved')
