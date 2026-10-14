"""独立持久化Worker：python -m app.worker；单Worker负责全局API限额。"""
import asyncio
import logging
import time
from datetime import timedelta
from sqlalchemy import select, update, or_, and_
from .db import Session, init_db, utcnow
from .models import Run, Item
from .providers import Gateway, CALL_CONTEXT
from .rag import RagIndex
from .metrics import calculate, suggest_tags
from .service import uid
from .settings import settings

log = logging.getLogger(__name__)
LEASE_SECONDS = 30


class LeaseLost(Exception):
    """旧Worker复活时，禁止覆盖新拥有者的结果。"""


def persist_item(db, run_id, item_id, owner, **values):
    owns_run = select(Run.id).where(Run.id == run_id, Run.owner == owner).exists()
    changed = db.execute(update(Item).where(Item.id == item_id, Item.state == 'running', owns_run)
                         .values(**values)).rowcount
    if not changed:
        raise LeaseLost()
    db.commit()


def claim_run(owner):
    with Session() as db:
        stale = utcnow() - timedelta(seconds=LEASE_SECONDS)
        candidates = db.scalars(select(Run).where(or_(Run.state == 'queued',
            and_(Run.state.in_(['running', 'pausing']), Run.heartbeat < stale))).order_by(Run.created_at)).all()
        for run in candidates:
            if run.state == 'pausing':
                changed = db.execute(update(Run).where(Run.id == run.id, Run.state == 'pausing', Run.heartbeat < stale)
                    .values(state='paused', owner=None, heartbeat=None)).rowcount
                if changed:
                    db.execute(update(Item).where(Item.run_id == run.id, Item.state == 'running').values(state='pending'))
                    db.commit()
                continue
            changed = db.execute(update(Run).where(Run.id == run.id, or_(Run.state == 'queued',
                and_(Run.state == 'running', Run.heartbeat < stale))).values(state='running', owner=owner, heartbeat=utcnow())).rowcount
            if changed:
                db.execute(update(Item).where(Item.run_id == run.id, Item.state == 'running').values(state='pending'))
                db.commit()
                return run.id
            db.rollback()
    return None


async def heartbeat(run_id, owner):
    while True:
        with Session() as db:
            changed = db.execute(update(Run).where(Run.id == run_id, Run.owner == owner)
                                 .values(heartbeat=utcnow())).rowcount
            db.commit()
            if not changed:
                return
        await asyncio.sleep(2)


def allowed(run_id, owner):
    with Session() as db:
        run = db.get(Run, run_id)
        return run is not None and run.state == 'running' and run.owner == owner


async def execute_run(run_id, owner, gateway=None):
    with Session() as db:
        run = db.get(Run, run_id)
        snapshot, mode, concurrency = run.snapshot, run.mode, run.concurrency
    # 防止暂停后修改.env导致同一任务用不同模型/端点继续。
    fields = ['judge_model', 'embedding_model', 'generation_base_url', 'judge_base_url',
              'embedding_base_url', 'rerank_model', 'rerank_url']
    if mode == 'cloud' and any(snapshot[k] != getattr(settings, k) for k in fields):
        with Session() as db:
            run = db.get(Run, run_id)
            run.state, run.error, run.owner = 'failed', '云服务模型或端点与任务快照不同；请恢复原配置或新建任务', None
            db.commit()
        return
    own_gateway = gateway is None
    gateway = gateway or Gateway(mode)
    context_token = CALL_CONTEXT.set((run_id, None))
    beat = asyncio.create_task(heartbeat(run_id, owner))
    try:
        indices = {}
        for config in snapshot['configs']:
            if not allowed(run_id, owner):
                break
            indices[config['id']] = await RagIndex.build(snapshot['documents'], config['parameters'], gateway)
        cases = {c['id']: c for c in snapshot['cases']}
        configs = {c['id']: c for c in snapshot['configs']}
        with Session() as db:
            ids = db.scalars(select(Item.id).where(Item.run_id == run_id, Item.state == 'pending')).all()
        queue = asyncio.Queue()
        for item_id in ids:
            queue.put_nowait(item_id)

        async def consume():
            while not queue.empty() and allowed(run_id, owner):
                try:
                    item_id = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                with Session() as db:
                    owns_run = select(Run.id).where(Run.id == run_id, Run.owner == owner, Run.state == 'running').exists()
                    changed = db.execute(update(Item).where(Item.id == item_id, Item.state == 'pending', owns_run)
                        .values(state='running', attempts=Item.attempts + 1, error=None)).rowcount
                    db.commit()
                    if not changed:
                        continue
                    item = db.get(Item, item_id)
                    case, config = cases[item.case_id], configs[item.config_id]
                    generation, judgement = item.generation, item.judgement
                item_token = CALL_CONTEXT.set((run_id, item_id))
                try:
                    if not generation:
                        started = time.perf_counter()
                        chunks, candidates, timings = await indices[config['id']].retrieve(case['question'], config['parameters'], gateway)
                        before = time.perf_counter()
                        generation = await gateway.generate(case['question'], chunks, config['parameters'])
                        timings['generation_ms'] = (time.perf_counter() - before) * 1000
                        timings['qa_ms'] = (time.perf_counter() - started) * 1000
                        generation.update({'chunks': chunks, 'candidates': candidates, 'timings': timings,
                            'evidence_coverage': config['parameters']['evidence_coverage']})
                        with Session() as db:
                            persist_item(db, run_id, item_id, owner, generation=generation)
                    if not judgement:
                        before = time.perf_counter()
                        judgement = await gateway.judge(case, generation)
                        judgement['judge_ms'] = (time.perf_counter() - before) * 1000
                        with Session() as db:
                            persist_item(db, run_id, item_id, owner, judgement=judgement)
                    prices = dict(snapshot['prices'])
                    for direction in ['input', 'output']:
                        configured = config['parameters'].get(direction + '_price')
                        if configured is not None:
                            prices[f'generation_{direction}_price'] = configured
                        elif config['parameters']['model'] != snapshot.get('generation_default_model'):
                            prices[f'generation_{direction}_price'] = None
                    metrics = calculate(case, generation, judgement, prices)
                    with Session() as db:
                        persist_item(db, run_id, item_id, owner, metrics=metrics,
                            tags=suggest_tags(case, metrics, generation, judgement['scores']), state='succeeded', error=None)
                except LeaseLost:
                    log.warning('lease lost; discard stale item result=%s', item_id)
                except asyncio.CancelledError:
                    with Session() as db:
                        try:
                            persist_item(db, run_id, item_id, owner, state='pending')
                        except LeaseLost:
                            pass
                    raise
                except Exception as exc:
                    with Session() as db:
                        # 不保留第三方SDK的原始请求对象和可能含凭据的异常信息。
                        error = str(exc)[:500] if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
                        try:
                            persist_item(db, run_id, item_id, owner, state='failed', error=error)
                        except LeaseLost:
                            pass
                    log.warning('item=%s failed=%s', item_id, type(exc).__name__)
                finally:
                    CALL_CONTEXT.reset(item_token)
                    queue.task_done()
        await asyncio.gather(*(consume() for _ in range(concurrency)))
        with Session() as db:
            run = db.get(Run, run_id)
            if run.owner == owner:
                states = db.scalars(select(Item.state).where(Item.run_id == run_id)).all()
                if run.state == 'pausing':
                    run.state = 'paused'
                elif any(s == 'pending' for s in states):
                    run.state = 'queued'
                else:
                    run.state = 'failed' if any(s == 'failed' for s in states) else 'completed'
                run.owner, run.heartbeat = None, None
                db.commit()
    except Exception as exc:
        with Session() as db:
            run = db.get(Run, run_id)
            if run.owner == owner:
                run.state, run.owner = 'failed', None
                run.error = str(exc)[:500] if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
                db.commit()
        log.exception('run preparation failed: %s', run_id)
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
        if own_gateway:
            await gateway.close()
        CALL_CONTEXT.reset(context_token)


async def serve():
    init_db()
    owner = uid('worker')
    log.info('Worker ready: %s', owner)
    gateways = {mode: Gateway(mode) for mode in ['demo', 'cloud']}
    try:
        while True:
            run_id = claim_run(owner)
            if run_id:
                with Session() as db:
                    mode = db.get(Run, run_id).mode
                log.info('claimed run=%s', run_id)
                await execute_run(run_id, owner, gateways[mode])
            else:
                await asyncio.sleep(1)
    finally:
        for gateway in gateways.values():
            await gateway.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
