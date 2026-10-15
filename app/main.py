import csv
import io
import json
import math
from collections import Counter
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
import yaml
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from .db import Session, init_db, utcnow, engine
from .models import Document, Dataset, Question, Config, Run, Item, ApiCall
from .schemas import Case, Parameters, RunInput, HumanReview
from .service import uid, validate_case, create_run, dataset_quality, TAGS
from .rag import digest, fixed_spans
from .metrics import aggregate
from .settings import settings, ROOT


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title='RAG Lab · 质量评测与调优平台', version='0.1.0', lifespan=lifespan)


def ok(data):
    return {'code': 0, 'message': 'ok', 'data': data}


@app.exception_handler(ValueError)
async def invalid(_, exc):
    return JSONResponse(status_code=400, content={'code': 400, 'message': str(exc), 'data': None})


@app.exception_handler(HTTPException)
async def http_error(_, exc):
    return JSONResponse(status_code=exc.status_code, content={'code': exc.status_code, 'message': str(exc.detail), 'data': None})


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc):
    messages = ['.'.join(map(str, e['loc'])) + ': ' + e['msg'] for e in exc.errors()]
    return JSONResponse(status_code=422, content={'code': 422, 'message': '; '.join(messages), 'data': None})


@app.exception_handler(IntegrityError)
async def conflict(_, exc):
    return JSONResponse(status_code=409, content={'code': 409, 'message': '数据已存在或仍被引用', 'data': None})


def required(db, model, row_id):
    row = db.get(model, row_id)
    if not row:
        raise HTTPException(404, '记录不存在')
    return row


class DatasetInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ''


class DocumentInput(BaseModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    source_url: str = ''
    content: str = Field(min_length=20)
    kind: str = 'real'


class ConfigInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parameters: Parameters


class ImportInput(BaseModel):
    format: str = 'json'
    text: str


class TagInput(BaseModel):
    tags: list[str]
    note: str = ''


@app.get('/api/health')
def health():
    return ok({'status': 'ok', 'mode': settings.provider_mode,
        'database': engine.dialect.name,
        'generation_ready': bool(settings.generation_api_key), 'embedding_ready': bool(settings.embedding_api_key),
        'rerank_ready': bool(settings.rerank_url and settings.rerank_api_key),
        'model': settings.generation_model, 'judge_model': settings.judge_model,
        'currency': settings.currency, 'tags': TAGS})


@app.get('/api/documents')
def documents():
    with Session() as db:
        docs = db.scalars(select(Document).order_by(Document.created_at)).all()
        return ok([{'id': d.id, 'title': d.title, 'source_url': d.source_url, 'kind': d.kind,
                    'characters': len(d.content), 'content_hash': d.content_hash,
                    'baseline_chunks': len(list(fixed_spans(d.content, 500, 80)))} for d in docs])


@app.get('/api/documents/{doc_id}')
def get_document(doc_id: str):
    with Session() as db:
        d = required(db, Document, doc_id)
        return ok({'id': d.id, 'title': d.title, 'source_url': d.source_url, 'content': d.content,
                   'kind': d.kind, 'content_hash': d.content_hash})


@app.post('/api/documents')
def add_document(data: DocumentInput):
    if data.kind not in {'real', 'demo'}:
        raise ValueError('kind必须是real或demo')
    if data.kind == 'real' and not data.source_url.startswith(('https://', 'http://')):
        raise ValueError('真实文档须提供可追溯的HTTP来源链接')
    with Session() as db:
        doc_id = data.id or uid('doc')
        if db.get(Document, doc_id):
            raise HTTPException(409, '文档ID已存在，更新原文须创建新版本ID')
        db.add(Document(id=doc_id, title=data.title, source_url=data.source_url,
                        content=data.content, content_hash=digest(data.content), kind=data.kind))
        db.commit()
        return ok({'id': doc_id})


@app.get('/api/datasets')
def datasets():
    with Session() as db:
        output = []
        for ds in db.scalars(select(Dataset).order_by(Dataset.created_at)).all():
            rows = db.scalars(select(Question).where(Question.dataset_id == ds.id)).all()
            output.append({'id': ds.id, 'name': ds.name, 'description': ds.description,
                           'total': len(rows), 'reviewed': sum(q.payload['status'] == 'reviewed' for q in rows),
                           'types': dict(Counter(q.payload['type'] for q in rows))})
        return ok(output)


@app.post('/api/datasets')
def add_dataset(data: DatasetInput):
    with Session() as db:
        row = Dataset(id=uid('dataset'), **data.model_dump())
        db.add(row)
        db.commit()
        return ok({'id': row.id})


@app.put('/api/datasets/{dataset_id}')
def edit_dataset(dataset_id: str, data: DatasetInput):
    with Session() as db:
        row = required(db, Dataset, dataset_id)
        row.name, row.description = data.name, data.description
        db.commit()
        return ok({'id': dataset_id})


@app.delete('/api/datasets/{dataset_id}')
def delete_dataset(dataset_id: str):
    with Session() as db:
        row = required(db, Dataset, dataset_id)
        db.execute(delete(Question).where(Question.dataset_id == dataset_id))
        db.delete(row)
        db.commit()
        return ok({'deleted': True})


@app.get('/api/datasets/{dataset_id}/questions')
def questions(dataset_id: str, type: str | None = None, status: str | None = None):
    with Session() as db:
        required(db, Dataset, dataset_id)
        rows = db.scalars(select(Question).where(Question.dataset_id == dataset_id).order_by(Question.case_id)).all()
        return ok([{'row_id': q.id, **q.payload} for q in rows
                   if (not type or q.payload['type'] == type) and (not status or q.payload['status'] == status)])


@app.post('/api/datasets/{dataset_id}/questions')
def add_question(dataset_id: str, data: Case):
    with Session() as db:
        required(db, Dataset, dataset_id)
        payload = validate_case(data.model_dump(), {d.id: d for d in db.scalars(select(Document)).all()})
        row = Question(id=uid('question'), dataset_id=dataset_id, case_id=data.id, payload=payload)
        db.add(row)
        db.commit()
        return ok({'row_id': row.id})


@app.put('/api/questions/{row_id}')
def edit_question(row_id: str, data: Case):
    with Session() as db:
        row = required(db, Question, row_id)
        row.payload = validate_case(data.model_dump(), {d.id: d for d in db.scalars(select(Document)).all()})
        row.case_id = data.id
        db.commit()
        return ok({'row_id': row.id})


@app.delete('/api/questions/{row_id}')
def delete_question(row_id: str):
    with Session() as db:
        db.delete(required(db, Question, row_id))
        db.commit()
        return ok({'deleted': True})


@app.post('/api/datasets/{dataset_id}/import')
def import_questions(dataset_id: str, data: ImportInput):
    if data.format == 'json':
        payload = json.loads(data.text)
        rows = payload.get('questions', []) if isinstance(payload, dict) else payload
    elif data.format == 'csv':
        rows = list(csv.DictReader(io.StringIO(data.text)))
        for row in rows:
            for field in ['gold_doc', 'gold_chunk_id', 'evidence']:
                row[field] = json.loads(row.get(field) or '[]')
            for field in ['annotator', 'reviewed_at']:
                row[field] = row.get(field) or None
    else:
        raise ValueError('导入格式仅支持json或csv')
    if not isinstance(rows, list) or not rows:
        raise ValueError('导入内容必须是非空题目数组')
    with Session() as db:
        required(db, Dataset, dataset_id)
        docs = {d.id: d for d in db.scalars(select(Document)).all()}
        validated = [validate_case(row, docs) for row in rows]
        if len({row['id'] for row in validated}) != len(validated):
            raise ValueError('导入文件存在重复题目ID')
        existing = {q.case_id for q in db.scalars(select(Question).where(Question.dataset_id == dataset_id)).all()}
        if any(row['id'] in existing for row in validated):
            raise ValueError('导入题目ID已存在；请编辑原题或使用新ID')
        for payload in validated:
            db.add(Question(id=uid('question'), dataset_id=dataset_id, case_id=payload['id'], payload=payload))
        db.commit()
        return ok({'imported': len(validated)})


@app.get('/api/datasets/{dataset_id}/quality')
def quality(dataset_id: str):
    return ok(dataset_quality(dataset_id))


@app.get('/api/datasets/{dataset_id}/export')
def export_dataset(dataset_id: str):
    with Session() as db:
        required(db, Dataset, dataset_id)
        rows = db.scalars(select(Question).where(Question.dataset_id == dataset_id).order_by(Question.case_id)).all()
        return Response(json.dumps([q.payload for q in rows], ensure_ascii=False, indent=2), media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename=eval_set.json'})


@app.get('/api/configs')
def configs():
    with Session() as db:
        return ok([{'id': c.id, 'name': c.name, 'parameters': c.parameters} for c in db.scalars(select(Config).order_by(Config.created_at)).all()])


@app.post('/api/configs')
def add_config(data: ConfigInput):
    with Session() as db:
        row = Config(id=uid('config'), name=data.name, parameters=data.parameters.model_dump())
        db.add(row)
        db.commit()
        return ok({'id': row.id})


@app.post('/api/configs/{config_id}/clone')
def clone_config(config_id: str, data: ConfigInput):
    with Session() as db:
        required(db, Config, config_id)
    return add_config(data)


@app.get('/api/configs/{config_id}/export')
def export_config(config_id: str, format: str = 'yaml'):
    with Session() as db:
        row = required(db, Config, config_id)
        data = {'id': row.id, 'name': row.name, 'parameters': row.parameters}
        if format not in {'yaml', 'json'}:
            raise ValueError('仅支持yaml/json')
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False) if format == 'yaml' else json.dumps(data, ensure_ascii=False, indent=2)
        return Response(text, media_type='text/plain', headers={'Content-Disposition': f'attachment; filename={config_id}.{format}'})


def run_summary(db, run):
    items = db.execute(select(Item.state, Item.config_id, Item.metrics).where(Item.run_id == run.id)).all()
    counts = Counter(i.state for i in items)
    done = counts['succeeded'] + counts['failed']
    latencies = [i.metrics['qa_ms'] + i.metrics['judge_ms'] for i in items if i.metrics]
    eta = ((sum(latencies) / len(latencies)) / 1000 * (len(items) - done) / run.concurrency) if latencies else None
    current = list(dict.fromkeys(i.config_id for i in items if i.state == 'running'))
    return {'id': run.id, 'name': run.name, 'state': run.state, 'mode': run.mode,
            'evaluation_level': run.snapshot.get('evaluation_level','demo' if run.mode=='demo' else 'human_reviewed'),
            'dataset_id': run.dataset_id, 'dataset_name': run.snapshot['dataset_name'],
            'total': len(items), 'done': done, 'counts': dict(counts), 'eta_seconds': eta,
            'current_configs': current, 'created_at': run.created_at.isoformat() + 'Z',
            'error': run.error, 'heartbeat': run.heartbeat.isoformat() + 'Z' if run.heartbeat else None,
            'configs': run.snapshot['configs'], 'dataset_hash': run.snapshot['dataset_hash'],
            'human_sample': run.snapshot['human_sample'], 'sample_seed': run.snapshot['sample_seed']}


@app.get('/api/runs')
def runs():
    with Session() as db:
        return ok([run_summary(db, run) for run in db.scalars(select(Run).order_by(Run.created_at.desc())).all()])


@app.post('/api/runs')
def new_run(data: RunInput):
    return ok({'id': create_run(data)})


@app.get('/api/runs/{run_id}')
def get_run(run_id: str):
    with Session() as db:
        return ok(run_summary(db, required(db, Run, run_id)))


@app.post('/api/runs/{run_id}/pause')
def pause(run_id: str):
    with Session() as db:
        run = required(db, Run, run_id)
        if run.state not in {'queued', 'running'}:
            raise ValueError('只有排队/运行任务可以暂停')
        run.state = 'pausing' if run.owner else 'paused'
        db.commit()
        return ok({'state': run.state})


@app.post('/api/runs/{run_id}/resume')
def resume(run_id: str):
    with Session() as db:
        run = required(db, Run, run_id)
        if run.state not in {'paused', 'failed'}:
            raise ValueError('只有已暂停/失败任务可以续跑；暂停中请等待在途项结束')
        db.execute(update(Item).where(Item.run_id == run.id, Item.state.in_(['failed', 'running'])).values(state='pending', error=None))
        run.state, run.owner, run.heartbeat, run.error = 'queued', None, None, None
        db.commit()
        return ok({'state': run.state})


@app.get('/api/runs/{run_id}/metrics')
def run_metrics(run_id: str):
    with Session() as db:
        run = required(db, Run, run_id)
        summaries = aggregate(db.scalars(select(Item).where(Item.run_id == run_id)).all())
        configs_by_id = {c['id']: c for c in run.snapshot['configs']}
        for row in summaries:
            row['name'] = configs_by_id[row['config_id']]['name']
            row['parameters'] = configs_by_id[row['config_id']]['parameters']
        calls = db.scalars(select(ApiCall).where(ApiCall.run_id==run_id)).all()
        return ok({'mode': run.mode, 'evaluation_level':run.snapshot.get('evaluation_level'), 'rows': summaries, 'currency': run.snapshot['prices']['currency'],
                   'cost_reference_note':run.snapshot.get('cost_reference_note','配置单价×API实际用量的参考估算，不是账户账单；不含Embedding/Rerank及失败尝试。'),
                   'api_calls':dict(Counter(c.role for c in calls)), 'failed_api_attempts':sum(c.status=='failed' for c in calls)})


@app.get('/api/runs/{run_id}/items')
def run_items(run_id: str, config_id: str | None = None, type: str | None = None,
              bad_only: bool = False, sampled_only: bool = False, tag: str | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    with Session() as db:
        run = required(db, Run, run_id)
        cases = {c['id']: c for c in run.snapshot['cases']}
        items = db.scalars(select(Item).where(Item.run_id == run_id).order_by(Item.case_id, Item.config_id)).all()
        filtered = [i for i in items if (not config_id or i.config_id == config_id)
                    and (not type or cases[i.case_id]['type'] == type)
                    and (not bad_only or i.state == 'failed' or i.metrics and not i.metrics['task_success'])
                    and (not sampled_only or i.case_id in run.snapshot['human_sample'])
                    and (not tag or tag in i.tags)]
        rows = [{'id': i.id, 'config_id': i.config_id, 'case_id': i.case_id, 'question': cases[i.case_id]['question'],
                 'type': cases[i.case_id]['type'], 'state': i.state, 'metrics': i.metrics, 'tags': i.tags,
                 'note': i.note, 'reviewed': bool(i.human_review), 'sampled': i.case_id in run.snapshot['human_sample'],
                 'error': i.error} for i in filtered[(page - 1) * page_size:page * page_size]]
        return ok({'rows': rows, 'total': len(filtered), 'page': page, 'page_size': page_size})


@app.get('/api/items/{item_id}')
def detail(item_id: str):
    with Session() as db:
        item = required(db, Item, item_id)
        run = required(db, Run, item.run_id)
        case = next(c for c in run.snapshot['cases'] if c['id'] == item.case_id)
        return ok({'id': item.id, 'case': case, 'config_id': item.config_id, 'state': item.state,
                   'generation': item.generation, 'judgement': item.judgement, 'metrics': item.metrics,
                   'tags': item.tags, 'note': item.note, 'human_review': item.human_review,
                   'attempts': item.attempts, 'error': item.error, 'mode': run.mode})


@app.put('/api/items/{item_id}/tags')
def edit_tags(item_id: str, data: TagInput):
    if any(tag not in TAGS for tag in data.tags):
        raise ValueError('标签不在六类标准标签中')
    with Session() as db:
        row = required(db, Item, item_id)
        row.tags, row.note = list(dict.fromkeys(data.tags)), data.note
        db.commit()
        return ok({'saved': True})


@app.put('/api/items/{item_id}/human-review')
def human_review(item_id: str, data: HumanReview):
    with Session() as db:
        row = required(db, Item, item_id)
        if row.state != 'succeeded':
            raise ValueError('只有完成的结果可以人工评分')
        row.human_review = {**data.model_dump(), 'reviewed_at': utcnow().isoformat() + 'Z'}
        db.commit()
        return ok({'saved': True})


@app.get('/api/runs/{run_id}/bad-cases')
def bad_cases(run_id: str):
    with Session() as db:
        run = required(db, Run, run_id)
        rows = db.scalars(select(Item).where(Item.run_id == run_id)).all()
        failed = [i for i in rows if i.state == 'failed' or i.metrics and not i.metrics['task_success']]
        tags = Counter(t for i in failed for t in i.tags)
        cases = {c['id']: c for c in run.snapshot['cases']}
        frequencies = Counter(i.case_id for i in failed)
        return ok({'total': len(failed), 'tag_counts': {tag: tags[tag] for tag in TAGS},
                   'typical': [{'case_id': case_id, 'question': cases[case_id]['question'], 'frequency': n}
                               for case_id, n in frequencies.most_common(15)],
                   'untagged': sum(not i.tags for i in failed)})


@app.get('/api/compare')
def compare(left: str, right: str):
    with Session() as db:
        a, b = required(db, Run, left), required(db, Run, right)
        comparable = all(a.snapshot[k] == b.snapshot[k] for k in ['dataset_hash', 'corpus_hash', 'prompt_version', 'judge_model',
            'generation_prompt','judge_prompt','embedding_model','embedding_base_url','judge_base_url']) and a.mode == b.mode
        am = {r['config_id']: r for r in aggregate(db.scalars(select(Item).where(Item.run_id == left)).all())}
        bm = {r['config_id']: r for r in aggregate(db.scalars(select(Item).where(Item.run_id == right)).all())}
        keys = ['recall', 'mrr', 'correct', 'refusal_correct', 'task_success', 'qa_ms']
        rows = []
        for cid in am.keys() & bm.keys():
            ac = next(c['parameters'] for c in a.snapshot['configs'] if c['id']==cid)
            bc = next(c['parameters'] for c in b.snapshot['configs'] if c['id']==cid)
            if ac != bc:
                comparable = False
            rows.append({'config_id': cid, 'left': {k: am[cid][k] for k in keys},
                         'right': {k: bm[cid][k] for k in keys},
                         'delta': {k: bm[cid][k] - am[cid][k] if bm[cid][k] is not None and am[cid][k] is not None else None for k in keys}})
        return ok({'comparable': comparable, 'message': '版本一致，可对照' if comparable else '题集/语料/评分规则/模式不同，不能直接归因于配置回归', 'rows': rows})


@app.get('/api/runs/{run_id}/calls')
def call_records(run_id: str):
    with Session() as db:
        required(db,Run,run_id)
        records=db.scalars(select(ApiCall).where(ApiCall.run_id==run_id).order_by(ApiCall.created_at)).all()
        return ok([{'id':c.id,'item_id':c.item_id,'role':c.role,'model':c.model,'status':c.status,
                    'created_at':c.created_at.isoformat()+'Z',**c.payload} for c in records])


@app.get('/api/runs/{run_id}/export')
def export_run(run_id: str, format: str = 'csv'):
    with Session() as db:
        run = required(db, Run, run_id)
        items = db.scalars(select(Item).where(Item.run_id == run_id)).all()
        summaries = aggregate(items)
        names = {c['id']: c['name'] for c in run.snapshot['configs']}
        if format == 'csv':
            columns = ['config_id', 'name', 'total', 'succeeded', 'success_coverage', 'recall', 'mrr', 'hit1',
                       'correct', 'refusal_correct', 'hallucination', 'hallucination_n', 'qa_ms', 'p95_ms',
                       'generation_tokens', 'judge_tokens', 'dialogue_cost', 'currency', 'cost_reference_note', 'score_agreement', 'agreement_n']
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows({**row, 'name': names[row['config_id']], 'currency':run.snapshot['prices']['currency'],
                              'cost_reference_note':run.snapshot.get('cost_reference_note','参考估算，不是账户账单。')} for row in summaries)
            text = '\ufeff' + buffer.getvalue()
            media = 'text/csv; charset=utf-8'
        elif format == 'markdown':
            text = f"# 配置对比报告：{run.name}\n\n运行ID：{run.id}；模式：{run.mode}；状态：{run.state}。\n"
            if run.snapshot.get('evaluation_level')=='ai_preliminary':
                text += '\n> 真实云端AI辅助预评测：题集由AI编写核验，尚未完成人工审核；不满足作业人工标注验收要求。\n'
            text += '\n> 模拟数据仅验证工程流程，不证明真实模型效果。\n' if run.mode == 'demo' else '\n'
            text += '\n|配置|成功/总数|Recall|MRR|正确率|拒答率|平均ms|P95ms|\n|---|---|---|---|---|---|---|---|\n'
            fmt = lambda x: 'N/A' if x is None else f'{x:.4f}'
            for row in summaries:
                text += f"|{names[row['config_id']]}|{row['succeeded']}/{row['total']}|" + '|'.join(fmt(row[k]) for k in ['recall', 'mrr', 'correct', 'refusal_correct', 'qa_ms', 'p95_ms']) + '|\n'
            complete = run.state == 'completed' and all(r['success_coverage'] == 1 for r in summaries)
            eligible = [r for r in summaries if r['task_success'] is not None] if complete else []
            if eligible:
                best = max(eligible, key=lambda r: (r['task_success'], r['mrr'] or 0, -(r['qa_ms'] or 0)))
                text += f"\n## 候选推荐\n\n按全题任务成功率优先、MRR其次、延迟最后排序：{names[best['config_id']]}。"
                text += '此为模拟流程推荐，正式推荐须由云端评测、人工核验、成本约束支持。\n' if run.mode == 'demo' else '此为自动候选，需结合人工核验、幻觉率与成本约束审核后作为最终推荐。\n'
            else:
                text += '\n## 推荐状态\n\n对照尚未全部成功完成，成功样本覆盖不同，暂不选择最优配置；需补齐失败项后做配对比较。\n'
            text += '\n## Bad Case标签分布\n\n' + json.dumps(dict(Counter(t for i in items if i.metrics and not i.metrics['task_success'] for t in i.tags)), ensure_ascii=False)
            text += '\n\n## 实验边界\n\n正确率阈值为准确性≥4、完整性≥4；拒答题检索指标N/A；失败项不进入质量均值，成功覆盖率另列。延迟不含Judge和建索引。对话成本不包含Embedding/Rerank。\n'
            text += '\n费用币种：'+run.snapshot['prices']['currency']+'；'+run.snapshot.get('cost_reference_note','配置单价×API用量的参考估算，不是账户账单。')+'\n'
            media = 'text/markdown; charset=utf-8'
        elif format == 'human':
            rows = [{'case_id': i.case_id, 'config_id': i.config_id, 'human_review': i.human_review,
                     'judge': i.judgement['scores'] if i.judgement else None,
                     'sampled': i.case_id in run.snapshot['human_sample']} for i in items if i.human_review or i.case_id in run.snapshot['human_sample']]
            text, media = json.dumps(rows, ensure_ascii=False, indent=2), 'application/json'
        else:
            raise ValueError('格式支持csv、markdown、human')
        ext = {'csv': 'csv', 'markdown': 'md', 'human': 'json'}[format]
        return Response(text, media_type=media, headers={'Content-Disposition': f'attachment; filename={run_id}.{ext}'})


dist = ROOT / 'frontend' / 'dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
