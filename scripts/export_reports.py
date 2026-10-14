"""从已保存结果重新分析，无模型调用；导出汇总、逐配置CSV、案例与一致率。"""
import csv
import json
import sys
from pathlib import Path
from collections import Counter
import httpx

ROOT=Path(__file__).resolve().parents[1]


def export(run_id, base='http://127.0.0.1:8010'):
    folder=ROOT/'reports'/run_id
    folder.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url=base,trust_env=False,timeout=30) as client:
        def get(path):
            response=client.get(path)
            response.raise_for_status()
            return response.json()['data']
        run=get('/api/runs/'+run_id)
        metrics=get('/api/runs/'+run_id+'/metrics')
        for fmt,filename in [('csv','指标汇总.csv'),('markdown','配置对比报告.md'),('human','人工评分记录.json')]:
            response=client.get(f'/api/runs/{run_id}/export',params={'format':fmt})
            response.raise_for_status()
            (folder/filename).write_bytes(response.content)
        for row in metrics['rows']:
            simple={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
            with (folder/(row['config_id']+'.csv')).open('w',encoding='utf-8-sig',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=list(simple))
                writer.writeheader();writer.writerow(simple)
        (folder/'运行汇总.json').write_text(json.dumps({'run':run,'metrics':metrics},ensure_ascii=False,indent=2),encoding='utf-8')
        bad=get('/api/runs/'+run_id+'/bad-cases')
        candidate=get(f'/api/runs/{run_id}/items?bad_only=true&page_size=200')['rows']
        selected=[]
        tag_counts=Counter()
        for row in candidate:
            wanted=[t for t in row['tags'] if tag_counts[t]<2]
            if wanted:
                selected.append(get('/api/items/'+row['id']))
                tag_counts.update(wanted)
        suggestions={'分块问题':'调整块大小或重叠，检查标准证据是否跨块；保持证据坐标。',
                     '召回失败':'对照向量分数与BM25命中，尝试混合检索、阈值或Top-K。',
                     '排序问题':'检查候选池与最终上下文，单变量测试Rerank。',
                     '生成幻觉':'核验标准证据、收紧来源约束；不足时拒答，再做回归。',
                     '提示词问题':'根据具体失败调整Prompt约束，并固化新版本。',
                     '知识库缺失':'补充可溯源材料；若业务不可回答，应设计正确拒答。'}
        text=f'# Bad Case分析报告\n\n运行：{run_id}；模式：{run["mode"]}。自动建议标签须人工确认。\n\n'
        text+='## 标签分布\n\n'+json.dumps(bad['tag_counts'],ensure_ascii=False)+'\n\n'
        for tag,suggestion in suggestions.items():
            text+=f'## {tag}\n\n改进建议：{suggestion}\n\n'
            examples=[d for d in selected if tag in d['tags']][:2]
            if not examples:
                text+='此次运行未观察到已归入本类的案例；正式验收案例待人工确认，未补造结果。\n\n'
            for d in examples:
                text+=f"- `{d['case']['id']}` / `{d['config_id']}`：{d['case']['question']}；任务成功：{d['metrics']['task_success']}；Judge理由：{d['judgement']['scores']['reason']}\n"
        (folder/'BadCase分析报告.md').write_text(text,encoding='utf-8')
        (folder/'BadCase样本.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
        text=f'# Judge一致性报告\n\n运行：{run_id}；随机种子：{run["sample_seed"]}；抽样题数：{len(run["human_sample"])}。\n\n'
        for row in metrics['rows']:
            text+=f"- {row['name']}：已配对评分{row['agreement_n']}条；分数完全一致率{row['score_agreement']}；二分类一致率{row['classification_agreement']}。\n"
        text+='\n尚无人工评分时一致率为N/A（JSON为null），不是0或100%。不一致案例需人工写明证据、规则与最终判断。\n'
        (folder/'Judge一致性报告.md').write_text(text,encoding='utf-8')
    print(folder)


if __name__=='__main__':
    if len(sys.argv)<2:
        raise SystemExit('用法：python scripts/export_reports.py RUN_ID')
    export(sys.argv[1])
