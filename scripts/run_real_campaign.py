"""可续接的真实云预评测：10题两配置通过后，运行100题七配置。"""
import json,time,sys
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.db import Session
from app.models import Dataset,Question,Run
from app.providers import PROMPT_VERSION

STATE=ROOT/'runtime'/'real_campaign.json'


def main():
    manifest=json.loads((ROOT/'data'/'real_evaluation_manifest.json').read_text(encoding='utf-8'))
    state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    with Session() as db:
        cases=[q.payload for q in db.query(Question).filter(Question.dataset_id==manifest['dataset_id']).order_by(Question.case_id).all()]
        selected=[]
        for kind,n in [('fact',4),('reasoning',3),('multihop',2),('refusal',1)]:
            selected.extend([c for c in cases if c['type']==kind][:n])
        pilot_id='dataset-ai-pilot-v2'
        if not db.get(Dataset,pilot_id):
            db.add(Dataset(id=pilot_id,name='10题真实云试跑 · AI题集',description='AI辅助核验，未人工审核；4/3/2/1'));db.flush()
            for case in selected:
                db.add(Question(id='pilot-v2-'+case['id'],dataset_id=pilot_id,case_id=case['id'],payload=case))
            db.commit()
    with httpx.Client(base_url='http://127.0.0.1:8010',trust_env=False,timeout=30) as client:
        def request(method,path,body=None):
            r=client.request(method,path,json=body);r.raise_for_status();return r.json()['data']
        def save():STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        def start(name,dataset,configs):
            return request('POST','/api/runs',{'name':name,'dataset_id':dataset,'config_ids':configs,
                'mode':'cloud','allow_ai_reviewed':True,'document_ids':manifest['document_ids'],
                'concurrency':6,'sample_seed':42})['id']
        def wait(run_id):
            existing=request('GET','/api/runs/'+run_id)
            if existing['state'] in ['failed','paused']:
                request('POST','/api/runs/'+run_id+'/resume')
            last=None
            validation_resumes=0
            while True:
                run=request('GET','/api/runs/'+run_id)
                progress=(run['state'],run['done'],run['counts'].get('failed',0))
                if progress!=last:
                    print(json.dumps({'run':run_id,'state':run['state'],'succeeded':run['counts'].get('succeeded',0),
                        'total':run['total'],'failed':run['counts'].get('failed',0)},ensure_ascii=False),flush=True)
                    last=progress
                if run['state']=='completed':return run
                if run['state']=='failed' and validation_resumes<2:
                    with Session() as db:
                        from app.models import Item
                        failed=db.query(Item).filter(Item.run_id==run_id,Item.state=='failed').all()
                        repairable=failed and all(i.generation and i.error=='Judge引用了不存在的检索证据' for i in failed)
                    if repairable:
                        validation_resumes+=1
                        request('POST','/api/runs/'+run_id+'/resume')
                        continue
                if run['state'] in ['failed','paused']:
                    raise RuntimeError('任务停止，请检查逐题错误后续跑：'+run_id)
                time.sleep(10)
        if not state.get('pilot_run'):
            state['pilot_run']=start('10题×2配置 · 真实云预评测',pilot_id,manifest['config_ids'][:1]+[manifest['config_ids'][4]])
            save()
        wait(state['pilot_run'])
        with Session() as db:
            frozen_version=db.get(Run,state['pilot_run']).snapshot.get('prompt_version')
        if frozen_version!=PROMPT_VERSION:
            state.setdefault('previous_pilots',[]).append(state['pilot_run'])
            state['pilot_run']=start('10题×2配置 · Prompt v2回归',pilot_id,manifest['config_ids'][:1]+[manifest['config_ids'][4]])
            state['prompt_version']=PROMPT_VERSION
            save()
            wait(state['pilot_run'])
        metrics=request('GET',f"/api/runs/{state['pilot_run']}/metrics")
        state['pilot_metrics']=metrics;save()
        costs=[r['dialogue_cost'] for r in metrics['rows'] if r['dialogue_cost'] is not None]
        estimate=sum(costs)/len(costs)*700 if costs else None
        state['full_dialogue_reference_estimate_usd']=estimate;save()
        print('Pilot successful; 700-answer dialogue reference estimate USD:',estimate,flush=True)
        if estimate is not None and estimate>5:
            raise RuntimeError('小样本推算费用超出本次保守自动跑批上限5美元，已停止扩量')
        if not state.get('full_run'):
            state['full_run']=start('100题×7配置 · 真实云AI预评测',manifest['dataset_id'],manifest['config_ids'])
            save()
        wait(state['full_run'])
        state['full_metrics']=request('GET',f"/api/runs/{state['full_run']}/metrics");save()
        print('Cloud campaign completed:',state['full_run'],flush=True)


if __name__=='__main__':main()
