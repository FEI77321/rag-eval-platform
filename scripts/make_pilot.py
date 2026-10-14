"""从真实已人工审核题目创建4/3/2/1的十题试跑集，绝不代替人工审核。"""
import sys
import json
import httpx


def main():
    source=sys.argv[1] if len(sys.argv)>1 else 'dataset-real-draft'
    with httpx.Client(base_url='http://127.0.0.1:8010',trust_env=False,timeout=30) as client:
        response=client.get(f'/api/datasets/{source}/questions',params={'status':'reviewed'})
        response.raise_for_status()
        cases=response.json()['data']
        selected=[]
        for kind,n in [('fact',4),('reasoning',3),('multihop',2),('refusal',1)]:
            group=[c for c in cases if c['type']==kind]
            if len(group)<n:
                raise SystemExit(f'已人工审核的{kind}题至少需要{n}道；当前{len(group)}道。请在界面补齐审核，不自动标记。')
            for case in group[:n]:
                case.pop('row_id')
                selected.append(case)
        response=client.post('/api/datasets',json={'name':'10题 · 已审核云端试跑','description':f'从{source}复制真实已审核的4/3/2/1题，保留审核人和时间'})
        response.raise_for_status()
        dataset_id=response.json()['data']['id']
        response=client.post(f'/api/datasets/{dataset_id}/import',json={'format':'json','text':json.dumps(selected,ensure_ascii=False)})
        response.raise_for_status()
        print(dataset_id)
        print(f'试跑：python -m app.cli run --dataset {dataset_id} --configs config-c01,config-c06 --mode cloud')


if __name__=='__main__':
    main()
