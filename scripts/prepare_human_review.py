"""全量完成后，导出固定抽样20题×7配置的盲评底稿及单独Judge对照表。"""
import csv,json,sys
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
run_id=sys.argv[1] if len(sys.argv)>1 else json.loads((ROOT/'runtime/real_campaign.json').read_text(encoding='utf-8'))['full_run']
folder=ROOT/'reports/raw'/run_id
folder.mkdir(parents=True,exist_ok=True)
with httpx.Client(base_url='http://127.0.0.1:8010',trust_env=False,timeout=30) as client:
    def get(path):
        response=client.get(path);response.raise_for_status();return response.json()['data']
    run=get('/api/runs/'+run_id)
    if run['state']!='completed':raise SystemExit('全量尚未全部完成，先续跑；不导出不完整的正式评分底稿。')
    items=get('/api/runs/'+run_id+'/items?sampled_only=true&page_size=200')['rows']
    assert len(items)==len(run['human_sample'])*len(run['configs'])
    details=[get('/api/items/'+i['id']) for i in items]
    columns=['item_id','case_id','config_id','type','question','gold_answer','gold_evidence','answer',
             'accuracy','completeness','refused','unsupported','factually_incorrect','reviewer','note']
    with (folder/'人工独立评分底稿.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for d in details:
            writer.writerow({'item_id':d['id'],'case_id':d['case']['id'],'config_id':d['config_id'],'type':d['case']['type'],
                'question':d['case']['question'],'gold_answer':d['case']['gold_answer'],
                'gold_evidence':json.dumps(d['case']['evidence'],ensure_ascii=False),'answer':d['generation']['answer']})
    (folder/'Judge对照表_评分后查看.json').write_text(json.dumps([{'item_id':d['id'],'case_id':d['case']['id'],
        'config_id':d['config_id'],'scores':d['judgement']['scores']} for d in details],ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'说明.md').write_text(f'# 人工评分底稿\n\n运行{run_id}；固定种子{run["sample_seed"]}；{len(run["human_sample"])}题×{len(run["configs"])}配置，共{len(items)}条。\n\n请先独立阅读答案与标准来源评分，不先查看Judge对照表。准确性/完整性1–5分，布尔字段true/false，事实错误无法判断可填null；reviewer填写实际本人。底稿所有人工评分栏为空，导出行为不代表评分完成。\n\n可通过平台逐题人工核验提交评分，接口PUT /api/items/{item_id}/human-review；接口保存真实时间。\n',encoding='utf-8')
print('Human review worksheet prepared:',len(items),'answers; human scores remain empty')
