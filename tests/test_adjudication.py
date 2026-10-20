from copy import deepcopy
from app.db import Session
from app.models import Item, Run, Adjudication
from app.schemas import RunInput
from app.service import create_run
from app.worker import execute_run, claim_run
import pytest


@pytest.mark.asyncio
async def test_adjudication_changes_only_effective_view_and_preserves_agreement(client, seeded):
    run_id = create_run(RunInput(dataset_id='dataset-demo', config_ids=['config-c01']))
    assert claim_run('test-adjudication') == run_id
    await execute_run(run_id, 'test-adjudication')
    with Session() as db:
        from sqlalchemy import select
        item = db.scalar(select(Item).where(Item.run_id == run_id, Item.case_id == 'DEMO-001'))
        item.human_review = {'accuracy': 5, 'completeness': 5, 'refused': False, 'reviewer': 'fixture'}
        before = deepcopy({'judgement': item.judgement, 'metrics': item.metrics, 'generation': item.generation, 'human': item.human_review})
        item_id = item.id
        db.add(Adjudication(item_id=item_id, payload={'reviewer_kind': 'ai', 'reviewer': 'AI test fixture', 'scores': {
            'accuracy': 1, 'completeness': 1, 'refused': True, 'unsupported': False, 'factually_incorrect': False, 'reason': 'test refusal'}}))
        db.commit()
    raw = client.get(f'/api/runs/{run_id}/metrics').json()['data']
    corrected = client.get(f'/api/runs/{run_id}/metrics?adjudicated=true').json()['data']
    assert raw['rows'][0]['task_success'] > corrected['rows'][0]['task_success']
    assert raw['rows'][0]['classification_agreement'] == corrected['rows'][0]['classification_agreement']
    assert corrected['adjudication_count'] == 1 and corrected['metrics_basis'] == 'ai_adjudicated'
    detail = client.get(f'/api/items/{item_id}').json()['data']
    assert detail['adjudication']['reviewer_kind'] == 'ai'
    assert detail['human_review'] == before['human']
    assert detail['judgement'] == before['judgement'] and detail['metrics'] == before['metrics']
    assert detail['generation'] == before['generation']
    revised = client.get(f'/api/runs/{run_id}/items?adjudicated=true&bad_only=true').json()['data']
    assert any(i['id'] == item_id and i['adjudicated'] for i in revised['rows'])
    text = client.get(f'/api/runs/{run_id}/export?format=markdown&adjudicated=true').text
    assert 'AI复核裁决' in text
