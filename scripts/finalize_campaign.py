"""仅在全量全部成功后生成最终预评测材料；没有新的模型调用。"""
import json,sys,shutil
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.export_reports import export
from scripts.build_delivery_evidence import main as evidence
run_id=sys.argv[1] if len(sys.argv)>1 else json.loads((ROOT/'runtime/real_campaign.json').read_text(encoding='utf-8'))['full_run']
with httpx.Client(base_url='http://127.0.0.1:8010',trust_env=False,timeout=30) as client:
    r=client.get('/api/runs/'+run_id);r.raise_for_status();run=r.json()['data']
    if run['state']!='completed' or run['counts'].get('succeeded')!=run['total']:
        raise SystemExit('任务尚未全部成功；不生成声称全量完成的交付报告。')
    response=client.get('/api/runs/'+run_id+'/metrics');response.raise_for_status();metrics=response.json()['data']
export(run_id);evidence(run_id)
folder=ROOT/'reports'/run_id
for name in ['配置对比报告.md','BadCase分析报告.md','Judge一致性报告.md']:
    shutil.copyfile(folder/name,ROOT/'docs'/name)
rows={r['config_id']:r for r in metrics['rows']}
pairs=[('Top-K 1','01','02'),('Top-K 5','01','03'),('递归分块','01','04'),('混合检索','01','05'),('阈值0.4','01','06'),('混合加重排','05','07')]
text='\n## 控制变量观察\n\n同一100题、23份来源、Prompt v2和模型服务；所有配置均100/100成功。以下为处理配置减基线配置。百分点变化为观察值，不代表独立测试的稳定增益。\n\n|变量|配对|Recall变化(pp)|答案正确率变化(pp)|问答延迟变化(ms)|\n|---|---|---|---|---|\n'
deltas=[]
for label,base,treat in pairs:
    a,b=rows['cloud-v2-'+base],rows['cloud-v2-'+treat]
    delta=(b['correct']-a['correct'])*100
    deltas.append((abs(delta),label,delta))
    text+=f"|{label}|R{base}→R{treat}|{(b['recall']-a['recall'])*100:+.2f}|{delta:+.2f}|{b['qa_ms']-a['qa_ms']:+.1f}|\n"
_,label,delta=max(deltas)
text+=f'\n本轮受控配对中，答案正确率绝对变化最大的因素为{label}（{delta:+.2f}个百分点）。这个结论只描述当前题集/语料/服务快照；题集由AI策划且未人工审核，不能作为无偏的生产泛化效果。\n'
text+='\n延迟含API限流等待、按配置顺序执行，时段和共享RPM队列存在混杂；成本为USD公开参考，不含Embedding/Rerank、失败尝试与人民币实际扣费。人工评分0条，一致率N/A。\n'
with (ROOT/'docs/配置对比报告.md').open('a',encoding='utf-8') as f:f.write(text)
manifest={'run_id':run_id,'state':'completed','succeeded':run['total'],'total':run['total'],
          'evaluation_level':'ai_preliminary','human_reviewed':0,'human_scores':0,
          'source_api':f'/api/runs/{run_id}/metrics','sample_seed':run['sample_seed'],
          'sample_cases':run['human_sample'],'config_ids':list(rows)}
(ROOT/'docs/真实云运行完成记录.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('Complete cloud preliminary evaluation exported:',run['total'],'answers; human review remains outstanding')
