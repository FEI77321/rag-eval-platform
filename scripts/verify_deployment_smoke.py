"""Exercise an isolated running deployment using 10 demo cases and 2 configs."""
import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8011')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with httpx.Client(base_url=args.base, trust_env=False, timeout=30) as client:
        def api(method, path, **kwargs):
            r = client.request(method, '/api'+path, **kwargs)
            r.raise_for_status()
            return r.json()['data']
        health = api('GET', '/health')
        assert health['database'] == 'sqlite' and health['mode'] == 'demo'
        assert not health['generation_ready'] and not health['embedding_ready']
        assert client.get('/').status_code == 200
        candidates = api('GET', '/datasets/dataset-demo/questions')
        cases = [{key: value for key, value in candidates[i].items() if key != 'row_id'} for i in [0,1,2,3,40,41,42,70,71,90]]
        dataset = api('POST', '/datasets', json={'name':'干净环境10题验证', 'description':'隔离demo；不调用云端API'})['id']
        api('POST', f'/datasets/{dataset}/import', json={'format':'json', 'text':json.dumps(cases,ensure_ascii=False)})
        quality = api('GET', f'/datasets/{dataset}/quality')
        assert quality['total'] == 10
        run_id = api('POST', '/runs', json={'name':'干净环境20条部署验证', 'dataset_id':dataset,
            'config_ids':['config-c01','config-c02'], 'mode':'demo', 'concurrency':2})['id']
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            run = api('GET', '/runs/'+run_id)
            if run['state'] in ('completed','failed'):
                break
            time.sleep(0.4)
        assert run['state'] == 'completed' and run['counts'].get('succeeded') == 20, run
        metrics = api('GET', f'/runs/{run_id}/metrics?adjudicated=true')
        assert len(metrics['rows']) == 2 and all(row['total']==10 for row in metrics['rows'])
        items = api('GET', f'/runs/{run_id}/items')['rows']
        detail = api('GET', '/items/'+items[0]['id'])
        assert detail['generation']['answer'] and detail['judgement'] and detail['attempts']==1
        assert api('GET', f'/runs/{run_id}/calls') == []
        assert client.get(f'/api/runs/{run_id}/export?format=csv').status_code == 200
        record = {'base':args.base, 'environment':'same-machine fresh venv + npm ci + empty SQLite',
            'run_id':run_id, 'dataset_id':dataset, 'cases':10, 'configurations':2, 'completed':20,
            'succeeded':20, 'no_cloud_credentials':True, 'paid_api_calls':0, 'source_page_http':200,
            'detail_verified':True, 'csv_export_verified':True, 'metrics':metrics['rows']}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({key:record[key] for key in ('run_id','completed','succeeded','paid_api_calls')},ensure_ascii=False))


if __name__ == '__main__':
    main()
