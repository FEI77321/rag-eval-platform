import math
from collections import defaultdict
import numpy as np


def evidence_retrieval(case, chunks, threshold=0.8):
    evidence = case['evidence']
    if case['type'] == 'refusal' or not evidence:
        return {k: None for k in ['recall', 'hit', 'all_evidence', 'mrr', 'hit1']}
    matches, first = set(), None
    for rank, chunk in enumerate(chunks, 1):
        relevant = False
        for index, item in enumerate(evidence):
            if chunk['doc_id'] != item['doc_id']:
                continue
            if item.get('start') is not None and item.get('end') is not None:
                overlap = max(0, min(chunk['end'], item['end']) - max(chunk['start'], item['start']))
                covered = overlap / max(1, item['end'] - item['start']) >= threshold
            else:
                covered = item['quote'] in chunk['text']
            if covered:
                matches.add(index)
                relevant = True
        if relevant and first is None:
            first = rank
    return {'recall': len(matches) / len(evidence), 'hit': float(bool(matches)),
            'all_evidence': float(len(matches) == len(evidence)), 'mrr': 1 / first if first else 0,
            'hit1': float(first == 1)}


def calculate(case, generation, judgement, prices):
    metrics = evidence_retrieval(case, generation['chunks'], generation['evidence_coverage'])
    scores = judgement['scores']
    correct = scores['accuracy'] >= 4 and scores['completeness'] >= 4
    refusal = case['type'] == 'refusal'
    success = correct and (scores['refused'] if refusal else not scores['refused'])
    hallucination = False if not scores['unsupported'] else scores['factually_incorrect']
    metrics.update({'correct': float(success) if not refusal else None,
                    'refusal_correct': float(success) if refusal else None,
                    'task_success': float(success), 'hallucination': float(hallucination) if hallucination is not None else None,
                    'unsupported': float(scores['unsupported']), 'type': case['type'],
                    **generation['timings'], 'judge_ms': judgement['judge_ms']})
    generation_usage, judge_usage = generation['usage'], judgement['usage']
    metrics['generation_tokens'] = sum(generation_usage.values()) if all(v is not None for v in generation_usage.values()) else None
    metrics['judge_tokens'] = sum(judge_usage.values()) if all(v is not None for v in judge_usage.values()) else None
    cost = 0.0
    known = True
    for role, usage in [('generation', generation_usage), ('judge', judge_usage)]:
        for direction in ['input', 'output']:
            price = prices.get(f'{role}_{direction}_price')
            count = usage.get(f'{direction}_tokens')
            if price is None or count is None:
                known = False
            else:
                cost += price * count / 1_000_000
    metrics['dialogue_cost'] = cost if known else None
    return metrics


def mean(values):
    available = [v for v in values if v is not None]
    return sum(available) / len(available) if available else None


def aggregate(items):
    groups = defaultdict(list)
    for item in items:
        groups[item.config_id].append(item)
    result = []
    keys = ['recall', 'hit', 'all_evidence', 'mrr', 'hit1', 'correct', 'refusal_correct',
            'task_success', 'hallucination', 'unsupported', 'qa_ms', 'judge_ms',
            'generation_tokens', 'judge_tokens', 'dialogue_cost']
    for config_id, rows in groups.items():
        successful = [r for r in rows if r.state == 'succeeded' and r.metrics]
        latencies = [r.metrics['qa_ms'] for r in successful]
        output = {'config_id': config_id, 'total': len(rows), 'succeeded': len(successful),
                  'failed': sum(r.state == 'failed' for r in rows),
                  'success_coverage': len(successful) / len(rows) if rows else 0,
                  'p95_ms': float(np.percentile(latencies, 95)) if latencies else None}
        for key in keys:
            output[key] = mean([r.metrics.get(key) for r in successful])
            output[key + '_n'] = sum(r.metrics.get(key) is not None for r in successful)
        output['agreement_n'] = sum(r.human_review is not None for r in successful)
        paired = [r for r in successful if r.human_review]
        output['score_agreement'] = mean([float(r.human_review['accuracy'] == r.judgement['scores']['accuracy'] and
            r.human_review['completeness'] == r.judgement['scores']['completeness']) for r in paired])
        output['classification_agreement'] = mean([float(
            (r.human_review['accuracy'] >= 4 and r.human_review['completeness'] >= 4 and
             (r.human_review['refused'] if r.metrics['type'] == 'refusal' else not r.human_review['refused'])) == bool(r.metrics['task_success'])) for r in paired])
        output['per_type'] = {kind: {'n': len([r for r in successful if r.metrics['type'] == kind]),
            'success': mean([r.metrics['task_success'] for r in successful if r.metrics['type'] == kind])}
            for kind in ['fact', 'reasoning', 'multihop', 'refusal']}
        result.append(output)
    return result


def suggest_tags(case, metrics, generation, scores):
    tags = []
    if metrics['task_success']:
        return tags
    if case['type'] == 'refusal':
        tags.extend(['知识库缺失', '提示词问题'])
    elif metrics['hit'] == 0:
        tags.append('召回失败')
        candidate_metrics = evidence_retrieval(case, generation['candidates'], generation['evidence_coverage'])
        if candidate_metrics['hit']:
            tags.append('排序问题')
    elif metrics['mrr'] is not None and metrics['mrr'] < 1:
        tags.append('排序问题')
    if scores['unsupported'] and scores['factually_incorrect'] is True:
        tags.append('生成幻觉')
    if case['type'] != 'refusal' and metrics['all_evidence'] != 1:
        for evidence in case['evidence']:
            if evidence.get('start') is None or evidence.get('end') is None:
                continue
            intervals = sorted((max(c['start'],evidence['start']), min(c['end'],evidence['end']))
                for c in generation['candidates'] if c['doc_id']==evidence['doc_id']
                and min(c['end'],evidence['end'])>max(c['start'],evidence['start']))
            if len(intervals)<2:
                continue
            merged=[]
            for start,end in intervals:
                if merged and start<=merged[-1][1]:
                    merged[-1][1]=max(merged[-1][1],end)
                else:
                    merged.append([start,end])
            length=evidence['end']-evidence['start']
            target=generation['evidence_coverage']
            if sum(b-a for a,b in merged)/length>=target and max(b-a for a,b in intervals)/length<target:
                tags.append('分块问题')
                break
    if not tags:
        tags.append('提示词问题')
    return list(dict.fromkeys(tags))
