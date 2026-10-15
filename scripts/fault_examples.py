"""受控故障定位样例，模拟评分且无云调用，绝不混入正常评测。"""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.metrics import calculate,suggest_tags
cases=json.loads((ROOT/'data/eval_set_ai_verified.json').read_text(encoding='utf-8'))
output=[]
plans=[('分块问题','将完整标准证据切成两个各覆盖50%的候选块','扩大块或增加重叠，避免证据被切断'),
       ('召回失败','从候选与最终上下文移除标准证据','检查分词/跨语言向量，比较混合检索与Top-K'),
       ('排序问题','标准证据留在候选池，但最终上下文只保留不相关块','扩大候选池，采用真实重排并做单变量回归'),
       ('生成幻觉','提供完整证据，但模拟答案添加经人工设定为错误的主张','收紧来源引用，抽检事实错误；检查生成与评分'),
       ('提示词问题','证据完整但模拟输出拒答，制造过严约束','允许依规则分析假设条件，并对拒答边界回归'),
       ('知识库缺失','范围外拒答题被模拟模型强行回答','明确知识库范围；不足时拒答，另行补充真实资料')]
for tag,trigger,fix in plans:
    for n in range(2):
        case=cases[90+n] if tag=='知识库缺失' else cases[n]
        e=case['evidence'][0] if case['evidence'] else None
        full={'id':'fixture-gold','doc_id':e['doc_id'],'start':e['start'],'end':e['end'],'text':e['quote']} if e else None
        chunks=[full] if full else [];candidates=list(chunks)
        if tag=='分块问题':
            mid=(e['start']+e['end'])//2
            candidates=[{**full,'id':'fixture-a','end':mid},{**full,'id':'fixture-b','start':mid}];chunks=candidates
        elif tag=='召回失败':chunks=[];candidates=[]
        elif tag=='排序问题':chunks=[]
        generation={'chunks':chunks,'candidates':candidates,'evidence_coverage':0.8,'timings':{'qa_ms':0},
                    'usage':{'input_tokens':None,'output_tokens':None}}
        scores={'accuracy':1,'completeness':1,'refused':tag=='提示词问题','unsupported':tag=='生成幻觉',
                'factually_incorrect':True if tag=='生成幻觉' else None}
        judgement={'scores':scores,'judge_ms':0,'usage':{'input_tokens':None,'output_tokens':None}}
        metrics=calculate(case,generation,judgement,{})
        suggested=suggest_tags(case,metrics,generation,scores)
        assert tag in suggested
        output.append({'id':f'FAULT-{len(output)+1:02d}','origin':'controlled_fault_injection','judge':'fixture-not-cloud',
                       'case_id':case['id'],'question':case['question'],'target_tag':tag,'trigger':trigger,
                       'suggested_tags':suggested,'observed_metrics':metrics,'suggestion':fix})
(ROOT/'docs/受控故障定位样例.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
text='# 受控故障定位样例（不计入正常质量统计）\n\n以下12例来自明确构造的故障条件和模拟Judge字段，只验证标签定位逻辑，不代表真实模型失败，也不能自动补足课程“每类真实Bad Case两例”的要求。\n\n'
for row in output:text+=f"- {row['id']} / {row['target_tag']} / {row['case_id']}：{row['trigger']}；实际建议标签{row['suggested_tags']}；改进：{row['suggestion']}。\n"
(ROOT/'docs/受控故障定位说明.md').write_text(text,encoding='utf-8')
print('12 controlled examples verified; excluded from cloud metrics')
