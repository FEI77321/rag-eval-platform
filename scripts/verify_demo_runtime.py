"""对正在运行的API/Worker做真实暂停与续跑验证，始终使用demo不消耗额度。"""
import json
import time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]


def verify():
    with httpx.Client(base_url='http://127.0.0.1:8010',trust_env=False,timeout=30) as client:
        def request(method,path,body=None):
            response=client.request(method,path,json=body)
            response.raise_for_status()
            return response.json()['data']
        previous=request('GET','/api/runs')[0]['id']
        run_id=request('POST','/api/runs',{'name':'暂停与续跑实测 · 本地模拟','dataset_id':'dataset-demo',
            'config_ids':[f'config-c{i:02d}' for i in range(1,10)],'mode':'demo','concurrency':1})['id']
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            status=request('GET','/api/runs/'+run_id)
            if status['counts'].get('succeeded',0)>0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('Worker未及时启动任务')
        request('POST',f'/api/runs/{run_id}/pause')
        while time.monotonic()<deadline:
            status=request('GET','/api/runs/'+run_id)
            if status['state']=='paused':
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('任务没有进入暂停状态')
        first=request('GET',f'/api/runs/{run_id}/items?page_size=200')['rows']
        protected={r['id']:request('GET','/api/items/'+r['id']) for r in first if r['state']=='succeeded'}
        assert protected, '必须在实际成功项之后验证暂停'
        before_count=status['counts']['succeeded']
        request('POST',f'/api/runs/{run_id}/resume')
        while time.monotonic()<deadline:
            status=request('GET','/api/runs/'+run_id)
            if status['state'] in ['completed','failed']:
                break
            time.sleep(0.5)
        assert status['state']=='completed' and status['counts']['succeeded']==900
        for item_id,old in protected.items():
            current=request('GET','/api/items/'+item_id)
            assert current['attempts']==old['attempts']==1
            assert current['generation']==old['generation']
        comparison=request('GET',f'/api/compare?left={previous}&right={run_id}')
        assert comparison['comparable'] and len(comparison['rows'])==9
        result={'mode':'demo','run_id':run_id,'previous_run':previous,'paused_after_successes':before_count,
                'preserved_items_checked':len(protected),'completed':900,'successful':900,
                'history_comparable':True,'no_paid_api_calls':not request('GET',f'/api/runs/{run_id}/calls')}
        (ROOT/'docs'/'运行续跑验证.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    verify()
