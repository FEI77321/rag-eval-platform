"""Record five AI adjudications without modifying human or Judge history."""
import hashlib
import json
from pathlib import Path
from sqlalchemy import select
from app.db import Session, init_db, utcnow
from app.models import Run, Item, Adjudication
from app.adjudication import reviewed_aggregate

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = 'run-54107b88329d40c8'
PAIRS = [('AI-057', 'cloud-v2-01'), ('AI-057', 'cloud-v2-06'),
         ('AI-067', 'cloud-v2-01'), ('AI-067', 'cloud-v2-05'), ('AI-078', 'cloud-v2-04')]


def main():
    init_db()
    records = []
    with Session() as db:
        run = db.get(Run, RUN_ID)
        if run is None:
            raise ValueError('Expected cloud run is missing')
        cases = {c['id']: c for c in run.snapshot['cases']}
        for case_id, config_id in PAIRS:
            item = db.scalar(select(Item).where(Item.run_id == RUN_ID, Item.case_id == case_id, Item.config_id == config_id))
            if item is None or item.state != 'succeeded':
                raise ValueError(f'Result missing: {case_id}/{config_id}')
            answer = item.generation['answer'].strip()
            if answer != '知识库依据不足，无法回答。' or cases[case_id]['type'] == 'refusal':
                raise ValueError(f'Expected answer changed: {case_id}/{config_id}; review required')
            digest = hashlib.sha256(json.dumps({'answer': answer, 'case': cases[case_id], 'judge': item.judgement}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            existing = db.get(Adjudication, item.id)
            if existing:
                if existing.payload['source_hash'] != digest:
                    raise ValueError('Frozen evidence changed; refusing to overwrite adjudication')
                payload = existing.payload
            else:
                payload = {'run_id': RUN_ID, 'case_id': case_id, 'config_id': config_id,
                    'reviewer': 'Codex（AI复核裁决）', 'reviewer_kind': 'ai', 'method': 'ai_evidence_adjudication',
                    'reviewed_at': utcnow().isoformat() + 'Z', 'source_hash': digest,
                    'question': cases[case_id]['question'], 'gold_answer': cases[case_id]['gold_answer'],
                    'evidence': cases[case_id]['evidence'], 'answer': answer,
                    'original_judge': item.judgement['scores'], 'original_human_review': item.human_review,
                    'original_metrics': item.metrics,
                    'scores': {'accuracy': 1, 'completeness': 1, 'refused': True, 'unsupported': False,
                               'factually_incorrect': False,
                               'reason': '原始回答仅为“知识库依据不足，无法回答。”，没有给出标准答案所要求的事实或推理。题目有可追溯官方证据，因此属于错误拒答，准确性与完整性均为1分。Judge理由声称回答了具体内容，与保存的原答不匹配。'},
                    'decision': 'incorrect_refusal', 'task_success': False,
                    'scope': '独立AI裁决层；不改写原始Judge、人工评分或任务快照。'}
                db.add(Adjudication(item_id=item.id, payload=payload))
            records.append({'item_id': item.id, **payload})
        db.commit()
        original, _ = reviewed_aggregate(db, run, False)
        revised, _ = reviewed_aggregate(db, run, True)
    payload = {'run_id': RUN_ID, 'reviewer_kind': 'ai', 'count': len(records), 'records': records,
               'original_metrics': original, 'adjudicated_metrics': revised,
               'human_agreement_note': '一致率仍是原人工评分对原Judge；AI裁决不作为新增真人评分。'}
    destinations = [ROOT/'docs/Judge复核裁决.json', ROOT/'reports'/RUN_ID/'Judge复核裁决.json']
    for path in destinations:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'adjudications': len(records), 'before_successes': sum(round(r['task_success']*r['succeeded']) for r in original),
                      'after_successes': sum(round(r['task_success']*r['succeeded']) for r in revised)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
