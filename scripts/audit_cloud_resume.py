"""只读核验全量完成与续跑调用次数。"""
import json,sys
from collections import Counter
from pathlib import Path
from sqlalchemy import select
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.db import Session
from app.models import Run,Item,ApiCall
run_id=json.loads((ROOT/'runtime/real_campaign.json').read_text(encoding='utf-8'))['full_run']
with Session() as db:
    run=db.get(Run,run_id)
    items=db.scalars(select(Item).where(Item.run_id==run_id)).all()
    calls=db.scalars(select(ApiCall).where(ApiCall.run_id==run_id)).all()
    generations=Counter(c.item_id for c in calls if c.role=='generation' and c.status=='succeeded')
    assert len(items)==700 and all(i.state=='succeeded' for i in items)
    assert len(generations)==700 and max(generations.values())==1
    assert {i.judgement['model'] for i in items}=={run.snapshot['judge_model']}
    data={'run_id':run_id,'state':run.state,'total':len(items),'states':dict(Counter(i.state for i in items)),
          'generation_models':dict(Counter(i.generation['model'] for i in items)),
          'judge_models':dict(Counter(i.judgement['model'] for i in items)),
          'successful_generation_call_count':sum(generations.values()),
          'max_successful_generation_calls_per_item':max(generations.values()),
          'calls_by_role_status':dict(Counter(c.role+'/'+c.status for c in calls)),
          'http402_attempts':sum(c.payload.get('error_code')==402 for c in calls),
          'attempt_distribution':dict(Counter(i.attempts for i in items)),
          'judge_request_versions':dict(Counter(i.judgement.get('request_version','judge-json-v1') for i in items)),
          'final_saved_validation_feedback_count':sum(len(i.judgement.get('validation_attempts',[])) for i in items),
          'human_scores':sum(bool(i.human_review) for i in items),'human_reviewed':run.snapshot['human_reviewed_count'],
          'scope':'每项成功生成API调用仅1次；失败402、格式校验与Judge补跑另列。API成功状态表示HTTP成功，不等于Judge结构校验成功；最终结果均通过结构与引用校验。'}
(ROOT/'docs/真实续跑与调用核验.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(data,ensure_ascii=False))
