from app.db import Session
from app.models import Document


def test_quality_and_cloud_gate(client,seeded):
    quality=client.get('/api/datasets/dataset-demo/quality').json()['data']
    assert quality['total']==100
    assert quality['types']=={'fact':40,'reasoning':30,'multihop':20,'refusal':10}
    assert quality['statuses']=={'demo':100}
    response=client.post('/api/runs',json={'dataset_id':'dataset-demo','config_ids':['config-c01'],'mode':'cloud'})
    assert response.status_code==400
    assert '人工审核' in response.json()['message']


def test_question_source_validation_and_atomic_import(client,seeded):
    case=client.get('/api/datasets/dataset-demo/questions').json()['data'][0]
    case.pop('row_id')
    case['id']='new-case'
    case['evidence'][0]['quote']='this quote does not exist'
    assert client.post('/api/datasets/dataset-demo/questions',json=case).status_code==400
    import json
    response=client.post('/api/datasets/dataset-demo/import',json={'format':'json','text':json.dumps([case])})
    assert response.status_code==400
    assert len(client.get('/api/datasets/dataset-demo/questions').json()['data'])==100


def test_configuration_versions_and_snapshot_isolation(client,seeded):
    config=client.get('/api/configs').json()['data'][0]
    response=client.post('/api/configs/'+config['id']+'/clone',json={'name':'clone','parameters':{**config['parameters'],'top_k':5}})
    assert response.status_code==200
    assert response.json()['data']['id']!=config['id']
    response=client.post('/api/runs',json={'dataset_id':'dataset-demo','config_ids':['config-c01']})
    run_id=response.json()['data']['id']
    case=client.get('/api/datasets/dataset-demo/questions').json()['data'][0]
    row_id=case.pop('row_id')
    case['question']='This question has been changed'
    assert client.put('/api/questions/'+row_id,json=case).status_code==200
    from app.models import Run
    with Session() as db:
        assert db.get(Run,run_id).snapshot['cases'][0]['question']!='This question has been changed'


def test_missing_and_invalid_records_have_unified_errors(client):
    assert client.get('/api/items/does-not-exist').status_code==404
    result=client.post('/api/configs',json={'name':'invalid','parameters':{'top_k':0}})
    assert result.status_code==422 and result.json()['code']==422
