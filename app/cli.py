import argparse
import json
import time
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser(description='RAG Lab HTTP命令行客户端')
    parser.add_argument('--base', default='http://127.0.0.1:8010')
    sub = parser.add_subparsers(dest='command', required=True)
    start = sub.add_parser('run')
    start.add_argument('--dataset', default='dataset-demo')
    start.add_argument('--configs', default='config-c01,config-c02,config-c03,config-c04,config-c06,config-c07')
    start.add_argument('--mode', choices=['demo','cloud'], default='demo')
    start.add_argument('--concurrency',type=int,default=3)
    start.add_argument('--name',default='CLI配置对比实验')
    for action in ['pause','resume','status','wait','export']:
        cmd = sub.add_parser(action)
        cmd.add_argument('run_id')
        if action == 'export':
            cmd.add_argument('--format',choices=['csv','markdown','human'],default='csv')
            cmd.add_argument('--out',required=True)
    args = parser.parse_args()
    with httpx.Client(base_url=args.base, timeout=30, trust_env=False) as client:
        if args.command == 'run':
            response = client.post('/api/runs', json={'name':args.name,'dataset_id':args.dataset,
                'config_ids':args.configs.split(','),'mode':args.mode,'concurrency':args.concurrency})
        elif args.command in ['pause','resume']:
            response = client.post(f'/api/runs/{args.run_id}/{args.command}')
        elif args.command == 'wait':
            while True:
                response = client.get(f'/api/runs/{args.run_id}')
                response.raise_for_status()
                data = response.json()['data']
                print(f"{data['state']} {data['counts'].get('succeeded',0)}/{data['total']} successful")
                if data['state'] in ['completed','failed','paused']:
                    break
                time.sleep(2)
        elif args.command == 'export':
            response = client.get(f'/api/runs/{args.run_id}/export',params={'format':args.format})
            response.raise_for_status()
            Path(args.out).parent.mkdir(parents=True,exist_ok=True)
            Path(args.out).write_bytes(response.content)
            print(args.out)
            return
        else:
            response = client.get(f'/api/runs/{args.run_id}')
        if not response.is_success:
            raise SystemExit(response.text)
        print(json.dumps(response.json(),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
