"""Build reports from persisted adjudications; no network or model calls."""
import csv
import json
from pathlib import Path
from app.db import Session
from app.models import Run
from scripts.adjudicate_disagreements import RUN_ID

ROOT = Path(__file__).resolve().parents[1]


def main():
    audit = json.loads((ROOT/'docs/Judge复核裁决.json').read_text(encoding='utf-8'))
    with Session() as db:
        run = db.get(Run, RUN_ID)
        configs = {c['id']: c for c in run.snapshot['configs']}
    originals = {r['config_id']: r for r in audit['original_metrics']}
    revised = sorted(audit['adjudicated_metrics'], key=lambda r: r['config_id'])
    folder = ROOT/'reports'/RUN_ID/'复核裁决版'
    folder.mkdir(exist_ok=True)
    rows = [{**r, 'name': configs[r['config_id']]['name']} for r in revised]
    (folder/'指标汇总.json').write_text(json.dumps({'metrics_basis': 'ai_adjudicated', 'ai_adjudications': 5, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['config_id', 'name', 'total', 'succeeded', 'task_success', 'correct', 'recall', 'mrr', 'refusal_correct', 'qa_ms', 'p95_ms', 'adjudication_count']
    for filename, subset in [('指标汇总.csv', rows)] + [(r['config_id']+'.csv', [r]) for r in rows]:
        with (folder/filename).open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction='ignore')
            writer.writeheader(); writer.writerows(subset)
    verdict = '# Judge分歧复核裁决报告\n\n复核已完成：5条均判为错误拒答。复核者是Codex（AI），不是新的人类评审；原始Judge、人工评分和历史任务快照保持独立可追溯。裁决层只更正这5条结果在当前对比视图中的质量统计，没有重新调用模型。\n\n'
    verdict += '|题目 / 配置|原Judge / 原人工分数|AI裁决准确性 / 完整性|拒答 / 任务通过|\n|---|---|---|---|\n'
    for record in audit['records']:
        verdict += f"|{record['case_id']} / {record['config_id'].replace('cloud-v2-', 'R')}|5/5；5/5|1/1|拒答；不通过|\n"
    verdict += '\n准确性和完整性均为1分：回答没有包含题目要求的任何要点；错误拒答不因为措辞谨慎而得到通过分。没有提出事实主张，因此unsupported=false、factually_incorrect=false；拒答本身作为任务失败处理。\n\n'
    for record in audit['records']:
        verdict += f"## {record['case_id']} / {record['config_id']}\n\n题目：{record['question']}\n\n原始模型回答：{record['answer']}\n\n标准答案：{record['gold_answer']}\n\n"
        for evidence in record['evidence']:
            verdict += f"- 来源`{evidence['doc_id']}`：{evidence['quote']}\n"
        verdict += f"\n原Judge理由：{record['original_judge']['reason']}\n\n裁决：{record['scores']['reason']}\n\n来源校验SHA256：`{record['source_hash']}`。原评分与新裁决完整记录见`Judge复核裁决.json`。\n\n"
    verdict += '## 对指标的影响与一致率\n\n原Judge全量通过452/700，应用5条AI裁决后447/700；失败数由248变为253。原始人工对原Judge的准确性/完整性分数一致140/140、分类一致135/140（96.43%）保留。AI裁决不作为新增真人评分，不能用其把真人一致率写成100%。\n\n改进：对Judge输入增加item_id与答案引用对齐；拒答和任务正确性分别判断；高分但原答为纯拒答的非拒答题列入复核队列。\n'
    for name in ('Judge分歧案例分析.md', 'Judge复核裁决报告.md'):
        (ROOT/'docs'/name).write_text(verdict, encoding='utf-8')
        (ROOT/'reports'/RUN_ID/name).write_text(verdict, encoding='utf-8')
    report = '# 配置对比报告：本次实验最终推荐R07\n\n本次实验最终推荐：**R07（混合检索 + 百炼重排）**。R07与R03在本次复核后的非拒答正确率同为64/90（71.11%），R07的MRR为0.5315，高于R03的0.4437，因此在“任务成功率→MRR→延迟”的排序下选择R07。R03作为不需要重排的备选。此推荐适用于当前题集与语料快照，不宣称线上普遍最优。\n\n'
    report += f'运行`{RUN_ID}`：23份官方来源、100题、7配置，700/700调用完成。历史运行创建于题集审核登记之前，等级仍为`ai_preliminary`；当前题集登记100/100审核，实质题干/答案/证据与冻结快照一致。本报告应用5条明确归因的AI复核裁决；没有新增云调用，没有把历史运行改名成审核后重跑。\n\n'
    report += '|配置|原非拒答正确率|裁决后正确率|裁决后全题通过|Recall|MRR|平均ms|P95ms|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for r in rows:
        old = originals[r['config_id']]
        report += f"|{r['name']}|{old['correct']:.2%}|{r['correct']:.2%}|{r['task_success']:.2%}|{r['recall']:.4f}|{r['mrr']:.4f}|{r['qa_ms']:.1f}|{r['p95_ms']:.1f}|\n"
    report += '\n![复核后七配置对比](配置对比图.svg)\n\n## 控制变量分析\n\n以下使用裁决后口径；括号披露原Judge口径，防止误把评分更正当成模型提升。\n\n'
    pairs = [('Top-K 3→1','cloud-v2-01','cloud-v2-02'), ('Top-K 3→5','cloud-v2-01','cloud-v2-03'), ('递归分块','cloud-v2-01','cloud-v2-04'), ('混合检索','cloud-v2-01','cloud-v2-05'), ('阈值0.4','cloud-v2-01','cloud-v2-06'), ('混合加重排','cloud-v2-05','cloud-v2-07')]
    by_id = {r['config_id']: r for r in rows}
    for label, left, right in pairs:
        delta = (by_id[right]['correct']-by_id[left]['correct'])*100
        raw = (originals[right]['correct']-originals[left]['correct'])*100
        report += f'- {label}：非拒答正确率变化{delta:+.2f}个百分点（原Judge口径{raw:+.2f}）。\n'
    report += '\n本次配对中影响最大的变量是Top-K降到1，正确率下降22.22个百分点；混合检索增加Rerank后提升13.33个百分点。没有为了验证新结论重新收费跑批；这是对同一批输出更正明显误判后的再分析。\n\n## 复核、Bad Case与边界\n\n5条裁决见`Judge复核裁决报告.md`与`Judge复核裁决.json`。原人工对原Judge分类一致率仍是135/140（96.43%），不将AI裁决作为新真人样本。裁决后低分/失败253条；原始Judge口径248条。Bad Case证据报告的10条真实案例来自原始失败集，另有2条明确标注的知识库缺失反事实测试；没有将反事实混入统计。\n\n延迟受到限流等待、执行顺序和运行时段影响，不把观测差异全归因于配置。USD对话费用为生成/Judge参考估算，不含Embedding/Rerank，不等于人民币实际账单。R07不能据对话费用更低就声称总成本更低。拒答题10/10通过不意味着线上拒答零错误。\n'
    (ROOT/'docs/配置对比报告.md').write_text(report, encoding='utf-8')
    # Make a portable engineering comparison chart directly from the audited data.
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="880" height="450" viewBox="0 0 880 450"><rect width="880" height="450" fill="white"/><style>text{font:14px sans-serif;fill:#24362d}</style><text x="35" y="28">Audited comparison — Recall / MRR / Correctness (0–1)</text>']
    colors = ['#477b9e','#9caf73','#286c4f']
    for i, r in enumerate(rows):
        y = 58+i*51
        svg.append(f'<text x="30" y="{y+20}">R{i+1:02d}</text>')
        for j, key in enumerate(('recall','mrr','correct')):
            value = r[key]
            svg.append(f'<rect x="90" y="{y+j*12}" width="{value*620:.2f}" height="9" fill="{colors[j]}"/><text x="{100+value*620:.2f}" y="{y+j*12+9}" style="font-size:11px">{value:.3f}</text>')
    svg.append('<text x="40" y="435">Blue: Recall · Light green: MRR · Dark green: Correctness · Source: 700 stored cloud outputs + 5 AI adjudications</text></svg>')
    (ROOT/'docs/配置对比图.svg').write_text(''.join(svg),encoding='utf-8')
    (ROOT/'reports'/RUN_ID/'配置对比报告.md').write_text(report, encoding='utf-8')
    (ROOT/'reports'/RUN_ID/'配置对比图.svg').write_text(''.join(svg),encoding='utf-8')
    # Original agreement remains frozen; clearly close the formerly pending case analysis.
    agreement = ROOT/'docs/Judge一致性报告.md'
    text = agreement.read_text(encoding='utf-8').replace('当前待分析的5条分类分歧', '已完成AI裁决的5条分类分歧')
    text += '\n## 本轮AI裁决已完成\n\n5条均为错误拒答，AI裁决准确性/完整性1/1、refused=true、任务不通过。该裁决独立入库，不覆盖原人工评分；原人工对原Judge一致率仍135/140。详见`Judge复核裁决报告.md`。\n'
    # Idempotent regeneration.
    marker = '\n## 本轮AI裁决已完成\n'
    text = text.split(marker)[0] + marker + '\n5条均为错误拒答，AI裁决准确性/完整性1/1、refused=true、任务不通过。该裁决独立入库，不覆盖原人工评分；原人工对原Judge一致率仍135/140。详见`Judge复核裁决报告.md`。\n'
    agreement.write_text(text,encoding='utf-8')
    (ROOT/'reports'/RUN_ID/'Judge一致性报告.md').write_text(text,encoding='utf-8')
    print('Adjudication evidence, corrected CSVs and final recommendation exported')


if __name__ == '__main__':
    main()
