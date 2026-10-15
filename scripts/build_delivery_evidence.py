"""离线校验及汇总：不调用模型，不填写人工审核，不导出全部问答大文件。"""
import argparse,csv,json,re,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import httpx,yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.rag import digest,fixed_spans
from app.db import Session
from app.models import Config


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def main(run_id=None):
    docs=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT/'data/corpus_v2').glob('*.json')) if p.name!='manifest.json']
    cases=json.loads((ROOT/'data/eval_set_ai_verified.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'data/real_evaluation_manifest.json').read_text(encoding='utf-8'))
    by_id={d['id']:d for d in docs}
    assert len(docs)==23 and len(cases)==100
    assert all(digest(d['content'])==d['content_hash'] for d in docs)
    checked=[];leaks=[]
    for case in cases:
        assert case['annotator'] is None and case['reviewed_at'] is None
        assert case['status']=='ai_reviewed'
        for e in case['evidence']:
            assert by_id[e['doc_id']]['content'][e['start']:e['end']]==e['quote']
        assert case['type']=='refusal' or case['gold_chunk_id']
        checked.append({'case_id':case['id'],'type':case['type'],'evidence_count':len(case['evidence']),
                        'coordinates_valid':True,'human_reviewed':False})
        for d in docs:
            if re.sub(r'\s+','',case['question']).casefold() in re.sub(r'\s+','',d['content']).casefold():
                leaks.append({'case_id':case['id'],'doc_id':d['id']})
    audit={'checked_at':datetime.now(timezone.utc).isoformat(),'dataset_id':manifest['dataset_id'],
           'documents':len(docs),'baseline_chunks':sum(len(list(fixed_spans(d['content'],500,80))) for d in docs),
           'cases':len(cases),'types':dict(Counter(c['type'] for c in cases)),
           'exact_question_copy_matches':leaks,'human_reviewed':0,'human_scores':0,
           'scope':'机器检查来源哈希、证据坐标、字段与问题全文复制；不证明人工审核或答案语义正确。',
           'cases_checked':checked}
    write(ROOT/'docs/AI题集核验记录.json',audit)
    with (ROOT/'docs/人工标注复核底稿.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['id','type','question','gold_answer','gold_doc','gold_chunk_id','human_annotator','reviewed_at','review_note'])
        writer.writeheader()
        for c in cases:writer.writerow({**{k:json.dumps(c[k],ensure_ascii=False) if isinstance(c[k],list) else c[k] for k in ['id','type','question','gold_answer','gold_doc','gold_chunk_id']},'human_annotator':'','reviewed_at':'','review_note':''})
    with Session() as db:
        for cid in manifest['config_ids']:
            config=db.get(Config,cid)
            (ROOT/'data/configs'/f'{cid}.yaml').write_text(yaml.safe_dump({'id':cid,'name':config.name,'parameters':config.parameters},allow_unicode=True,sort_keys=False),encoding='utf-8')
    source_text='# 数据来源清单 · v2\n\n23份FastAPI官方教程，固定500字符、重叠80，共714块。以下为正文规范化快照；旧v1保留用于历史结果复现，v2运行通过document_ids隔离。\n\n'
    for d in docs:source_text+=f"- [{d['title']}]({d['source_url']})；SHA256：`{d['content_hash']}`；采集时间：{d['fetched_at']}。\n"
    (ROOT/'docs/数据来源清单.md').write_text(source_text,encoding='utf-8')
    state=json.loads((ROOT/'runtime/real_campaign.json').read_text(encoding='utf-8'))
    run_id=run_id or state.get('full_run') or state['pilot_run']
    with httpx.Client(base_url='http://127.0.0.1:8010',trust_env=False,timeout=30) as client:
        def get(path):
            r=client.get(path);r.raise_for_status();return r.json()['data']
        run=get('/api/runs/'+run_id);metrics=get('/api/runs/'+run_id+'/metrics')
        items=get('/api/runs/'+run_id+'/items?page_size=200')['rows']
        examples=[get('/api/items/'+i['id']) for i in [r for r in items if r['state']=='succeeded'][:20]]
        folder=ROOT/'reports'/run_id
        write(folder/'运行汇总.json',{'run':run,'metrics':metrics})
        write(folder/'真实问答样本.json',examples)
        source={'provider':'本机RAG Lab API / SQLite持久结果','label':run['name'],
                'tables':['runs','run_items','api_calls'],'files':['runtime/platform.db'],
                'evidenceFlow':[{'title':'真实调用保存','detail':'DeepSeek生成与独立Judge；百炼Embedding；每题逐阶段保存。'},
                                {'title':'汇总重算','detail':f'GET /api/runs/{run_id}/metrics，无新增模型调用。'},
                                {'title':'范围','detail':'失败项不计质量均值；成功覆盖率单列。AI题集0人工审核，不作正式最优配置结论。'}],
                'metricDefinitions':[{'label':'证据Recall@K','definition':'成功的非拒答题中，每题召回证据段覆盖数/标准证据段数的平均；单段覆盖≥80%。'},
                                     {'label':'答案正确率','definition':'成功非拒答题中，独立Judge准确性≥4、完整性≥4且非拒答的比例。'},
                                     {'label':'对话参考成本 USD','definition':'成功生成及Judge真实输入/输出Token×公开峰时缓存未命中单价，不是人民币账户账单；不含Embedding/Rerank和失败尝试。'}]}
        clean_rows=[{k:v for k,v in row.items() if not isinstance(v,(dict,list))} for row in metrics['rows']]
        snapshot={'surface':'report','title':'RAG云端预评测 · 结果与改进依据','generatedAt':datetime.now(timezone.utc).isoformat(),
                  'status':'observed-ai-preliminary','buildStatus':'creating','filters':[],
                  'run':run,'metrics':metrics,'audit':audit,
                  'report':{'asOf':'2026-10-15'},
                  'queries':{'config_results':{'rows':clean_rows,'source':source,'methods':[{'language':'Python',
                    'code':f'python scripts/build_delivery_evidence.py --run {run_id}\n# GET /api/runs/{run_id}/metrics recomputes app.metrics.aggregate over persisted run_items.\n# Chart aliases recallRate=recall and correctRate=correct preserve the raw 0-1 values.'}]},
                             'sample_answers':{'rows':[{'case_id':e['case']['id'],'config_id':e['config_id'],'question':e['case']['question'],
                                                         'answer':e['generation']['answer'],'reason':e['judgement']['scores']['reason']} for e in examples],
                                               'source':{**source,'label':'前20条成功问答样本','evidenceFlow':source['evidenceFlow']+[{'title':'样本边界','detail':'按接口排序取前20条成功结果，仅用于故障观察，不能代替固定种子的人工抽样。'}]}}}}
        write(ROOT/'runtime/report_snapshot.json',snapshot)
    print(json.dumps({'run':run_id,'state':run['state'],'done':run['done'],'total':run['total'],
                      'audit':{k:v for k,v in audit.items() if k!='cases_checked'},'snapshot':'runtime/report_snapshot.json'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run');args=parser.parse_args();main(args.run)
