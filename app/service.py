import copy
import math
import random
import uuid
from collections import Counter
from sqlalchemy import select
from .db import Session
from .models import Document, Dataset, Question, Config, Run, Item
from .schemas import Case, RunInput
from .providers import PROMPT_VERSION, GENERATION_PROMPT, JUDGE_PROMPT
from .rag import digest, fixed_spans, chunk_identifier
from .settings import settings

TAGS = ['分块问题', '召回失败', '排序问题', '生成幻觉', '提示词问题', '知识库缺失']


def uid(prefix):
    return prefix + '-' + uuid.uuid4().hex[:16]


def validate_case(case, documents):
    payload = Case.model_validate(case).model_dump()
    for evidence in payload['evidence']:
        doc = documents.get(evidence['doc_id'])
        if not doc:
            raise ValueError('标准证据引用了不存在的文档：' + evidence['doc_id'])
        text = doc.content
        if evidence['quote'] not in text:
            raise ValueError('标准证据原文不在指定文档中：' + evidence['doc_id'])
        if evidence['start'] is None:
            evidence['start'] = text.index(evidence['quote'])
            evidence['end'] = evidence['start'] + len(evidence['quote'])
        if evidence['end'] is None or text[evidence['start']:evidence['end']] != evidence['quote']:
            raise ValueError('标准证据坐标与原文不一致')
    unique = {}
    for e in payload['evidence']:
        unique[(e['doc_id'],e['start'],e['end'])] = e
    payload['evidence'] = list(unique.values())
    expected_docs = list(dict.fromkeys(e['doc_id'] for e in payload['evidence']))
    if payload['gold_doc'] and set(payload['gold_doc']) != set(expected_docs):
        raise ValueError('gold_doc与evidence文档不一致')
    payload['gold_doc'] = expected_docs
    # 必填gold_chunk_id保存固定500/80基线的实际块ID；跨策略评测使用稳定证据坐标。
    baseline_ids = []
    for e in payload['evidence']:
        doc = documents[e['doc_id']]
        for start, end in fixed_spans(doc.content, 500, 80):
            if min(end, e['end']) > max(start, e['start']):
                baseline_ids.append(chunk_identifier({'id':doc.id,'content_hash':doc.content_hash},start,end,
                    {'chunk_strategy':'fixed','chunk_size':500,'chunk_overlap':80}))
    payload['gold_chunk_id'] = list(dict.fromkeys(baseline_ids))
    return payload


def create_run(data: RunInput):
    if len(set(data.config_ids)) != len(data.config_ids):
        raise ValueError('配置ID不能重复')
    with Session() as db:
        dataset = db.get(Dataset, data.dataset_id)
        if not dataset:
            raise ValueError('评测集不存在')
        questions = db.scalars(select(Question).where(Question.dataset_id == data.dataset_id)).all()
        if not questions:
            raise ValueError('评测集没有题目')
        documents = db.scalars(select(Document)).all()
        if not documents:
            raise ValueError('知识库没有文档')
        if data.mode == 'cloud':
            if any(q.payload['status'] != 'reviewed' for q in questions):
                raise ValueError('正式云评测只接受逐题人工审核的reviewed题集')
            referenced = {e['doc_id'] for q in questions for e in q.payload['evidence']}
            if any(d.kind != 'real' for d in documents if d.id in referenced):
                raise ValueError('正式题目引用了模拟语料，请改用真实来源')
            documents = [d for d in documents if d.kind == 'real']
            if not settings.generation_api_key or not settings.embedding_api_key:
                raise ValueError('请在本地.env配置生成和Embedding Key，然后重启API和Worker')
        else:
            referenced = {e['doc_id'] for q in questions for e in q.payload['evidence']}
            # 演示题集隔离到演示语料；真实草稿的离线调试使用真实文档。
            kinds = {d.kind for d in documents if d.id in referenced}
            if kinds == {'demo'}:
                documents = [d for d in documents if d.kind == 'demo']
        configs = []
        for config_id in data.config_ids:
            config = db.get(Config, config_id)
            if not config:
                raise ValueError('配置不存在：' + config_id)
            if data.mode == 'cloud' and config.parameters['rerank'] and not settings.rerank_url:
                raise ValueError('所选配置启用了Rerank，请配置RERANK_URL或选择关闭重排的配置')
            configs.append({'id': config.id, 'name': config.name, 'parameters': config.parameters})
        cases = [copy.deepcopy(q.payload) for q in sorted(questions, key=lambda q: q.case_id)]
        by_id = {d.id: d for d in documents}
        cases = [validate_case(case, by_id) for case in cases]
        docs = [{'id': d.id, 'title': d.title, 'source_url': d.source_url,
                 'content': d.content, 'content_hash': d.content_hash, 'kind': d.kind} for d in documents]
        prices = {name: getattr(settings, name) for name in ['generation_input_price', 'generation_output_price',
            'judge_input_price', 'judge_output_price', 'currency']}
        rng = random.Random(data.sample_seed)
        # 按题型分层随机抽样，整体严格ceil(20%题数)，至少每类一题（样本容量允许时）。
        sample_n = math.ceil(len(cases) * 0.2)
        groups = {kind: [c['id'] for c in cases if c['type'] == kind] for kind in ['fact', 'reasoning', 'multihop', 'refusal']}
        sampled = []
        nonempty = [ids for ids in groups.values() if ids]
        if sample_n >= len(nonempty):
            sampled = [rng.choice(ids) for ids in nonempty]
        rest = [c['id'] for c in cases if c['id'] not in sampled]
        sampled.extend(rng.sample(rest, sample_n - len(sampled)))
        snapshot = {'dataset_name': dataset.name, 'cases': cases, 'documents': docs, 'configs': configs,
                    'dataset_hash': digest(cases), 'corpus_hash': digest(docs), 'prices': prices,
                    'sample_seed': data.sample_seed, 'human_sample': sampled,
                    'prompt_version': PROMPT_VERSION, 'generation_prompt': GENERATION_PROMPT, 'judge_prompt': JUDGE_PROMPT,
                    'judge_model': settings.judge_model, 'embedding_model': settings.embedding_model,
                    'generation_default_model': settings.generation_model,
                    'generation_base_url': settings.generation_base_url, 'judge_base_url': settings.judge_base_url,
                    'embedding_base_url': settings.embedding_base_url, 'rerank_model': settings.rerank_model,
                    'rerank_url': settings.rerank_url, 'accuracy_threshold': 4, 'completeness_threshold': 4}
        run = Run(id=uid('run'), name=data.name, dataset_id=dataset.id, mode=data.mode,
                  concurrency=data.concurrency, snapshot=snapshot)
        db.add(run)
        db.flush()
        for config in configs:
            for case in cases:
                db.add(Item(id=uid('item'), run_id=run.id, config_id=config['id'], case_id=case['id']))
        db.commit()
        return run.id


def dataset_quality(dataset_id):
    with Session() as db:
        dataset = db.get(Dataset, dataset_id)
        if not dataset:
            raise ValueError('评测集不存在')
        rows = db.scalars(select(Question).where(Question.dataset_id == dataset_id)).all()
        docs = db.scalars(select(Document)).all()
        leaked = []
        for row in rows:
            question = ''.join(row.payload['question'].split()).casefold()
            for doc in docs:
                if question in ''.join(doc.content.split()).casefold():
                    leaked.append({'case_id': row.case_id, 'doc_id': doc.id})
        return {'total': len(rows), 'types': dict(Counter(q.payload['type'] for q in rows)),
                'statuses': dict(Counter(q.payload['status'] for q in rows)),
                'average_question_length': sum(len(q.payload['question']) for q in rows) / len(rows) if rows else 0,
                'sources': dict(Counter(e['doc_id'] for q in rows for e in q.payload['evidence'])),
                'leakage_matches': leaked, 'leakage_method': '去除空白、casefold后完整题目字符串包含检查；不是语义泄漏证明'}
