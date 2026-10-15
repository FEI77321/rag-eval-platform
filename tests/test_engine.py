import asyncio
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.db import Session, utcnow
from app.models import Dataset, Question, Run, Item
from app.schemas import RunInput
from app.service import create_run
from app.worker import claim_run, execute_run, persist_item, LeaseLost
from app.providers import Gateway


def small_dataset():
    from app.seed import seed
    seed()
    with Session() as db:
        db.add(Dataset(id='small',name='Small',description=''))
        db.flush()
        source = db.scalars(select(Question).where(Question.dataset_id=='dataset-demo')).first()
        for i in range(4):
            payload = {**source.payload,'id':f'q{i}'}
            db.add(Question(id=f'small-{i}',dataset_id='small',case_id=f'q{i}',payload=payload))
        db.commit()


@pytest.mark.asyncio
async def test_pause_resume_preserves_successful_generation():
    small_dataset()
    run_id = create_run(RunInput(dataset_id='small',config_ids=['config-c01'],concurrency=1))
    assert claim_run('worker-test') == run_id
    class PauseAfterFirst(Gateway):
        def __init__(self):
            super().__init__('demo')
            self.generated = 0
        async def generate(self,*args):
            self.generated += 1
            return await super().generate(*args)
        async def judge(self,*args):
            result = await super().judge(*args)
            if self.generated == 1:
                with Session() as db:
                    db.get(Run,run_id).state='pausing'
                    db.commit()
            return result
    gateway = PauseAfterFirst()
    await execute_run(run_id,'worker-test',gateway)
    with Session() as db:
        assert db.get(Run,run_id).state == 'paused'
        complete = db.scalars(select(Item).where(Item.run_id==run_id,Item.state=='succeeded')).all()
        assert len(complete) == 1
        original_answer = complete[0].generation
        original_id = complete[0].id
        db.get(Run,run_id).state='queued'
        db.commit()
    assert claim_run('worker-test') == run_id
    await execute_run(run_id,'worker-test')
    with Session() as db:
        assert db.get(Run,run_id).state == 'completed'
        assert db.get(Item,original_id).generation == original_answer
        assert db.get(Item,original_id).attempts == 1
        assert len(db.scalars(select(Item).where(Item.run_id==run_id,Item.state=='succeeded')).all()) == 4


@pytest.mark.asyncio
async def test_judge_failure_resumes_without_regeneration(client):
    small_dataset()
    run_id = create_run(RunInput(dataset_id='small',config_ids=['config-c01'],concurrency=2))
    claim_run('worker-test')
    class FailingJudge(Gateway):
        async def judge(self,*args):
            raise ValueError('Controlled judge failure')
    await execute_run(run_id,'worker-test',FailingJudge('demo'))
    with Session() as db:
        items = db.scalars(select(Item).where(Item.run_id==run_id)).all()
        before = {i.id:i.generation for i in items}
        assert all(i.generation and i.state=='failed' for i in items)
    assert client.post(f'/api/runs/{run_id}/resume').status_code == 200
    claim_run('worker-test')
    class NoRegeneration(Gateway):
        async def generate(self,*args):
            raise AssertionError('Successful generation must not be rerun')
    await execute_run(run_id,'worker-test',NoRegeneration('demo'))
    with Session() as db:
        assert db.get(Run,run_id).state=='completed'
        assert all(i.generation==before[i.id] for i in db.scalars(select(Item).where(Item.run_id==run_id)).all())


def test_stale_lease_recovery_and_exclusive_run_claim():
    small_dataset()
    run_id = create_run(RunInput(dataset_id='small',config_ids=['config-c01']))
    assert claim_run('first') == run_id
    assert claim_run('second') is None
    with Session() as db:
        db.get(Run,run_id).heartbeat = utcnow()-timedelta(seconds=40)
        item=db.scalars(select(Item).where(Item.run_id==run_id)).first()
        item.state='running'
        db.commit()
    assert claim_run('second') == run_id
    with Session() as db:
        assert db.get(Run,run_id).owner=='second'
        assert db.scalars(select(Item).where(Item.run_id==run_id)).first().state=='pending'


def test_old_worker_cannot_overwrite_after_takeover():
    small_dataset()
    run_id=create_run(RunInput(dataset_id='small',config_ids=['config-c01']))
    claim_run('old')
    with Session() as db:
        run=db.get(Run,run_id)
        run.owner='new'
        item=db.scalars(select(Item).where(Item.run_id==run_id)).first()
        item.state='running'
        db.commit()
        with pytest.raises(LeaseLost):
            persist_item(db,run_id,item.id,'old',generation={'answer':'stale'})
        db.rollback()
        assert db.get(Item,item.id).generation is None


@pytest.mark.asyncio
async def test_transient_rate_limit_is_retried(monkeypatch):
    import httpx
    gateway=Gateway('cloud')
    calls=0
    async def action():
        nonlocal calls
        calls+=1
        if calls==1:
            request=httpx.Request('POST','https://example.invalid')
            response=httpx.Response(429,headers={'Retry-After':'0'},request=request)
            raise httpx.HTTPStatusError('limited',request=request,response=response)
        return 'success'
    assert await gateway.call(action)=='success'
    assert calls==2 and gateway.retries==1


@pytest.mark.asyncio
async def test_quota_failure_pauses_queue_and_keeps_saved_generation():
    from app.providers import QuotaExhausted
    small_dataset()
    run_id=create_run(RunInput(dataset_id='small',config_ids=['config-c01'],concurrency=1))
    claim_run('quota-test')
    class NoBalanceJudge(Gateway):
        async def judge(self,*args):
            raise QuotaExhausted('云API返回HTTP 402；账户余额不足，请充值后断点续跑')
    await execute_run(run_id,'quota-test',NoBalanceJudge('demo'))
    with Session() as db:
        assert db.get(Run,run_id).state=='paused'
        items=db.scalars(select(Item).where(Item.run_id==run_id)).all()
        failed=[i for i in items if i.state=='failed']
        assert len(failed)==1 and failed[0].generation
        assert sum(i.state=='pending' for i in items)==3
