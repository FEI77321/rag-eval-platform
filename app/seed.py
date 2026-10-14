"""可重复加载演示：全部为合成语料、demo标注，无伪造人工审核。"""
import json
from pathlib import Path
from .db import Session, init_db
from .models import Document, Dataset, Question, Config
from .schemas import Parameters
from .service import validate_case
from .rag import digest
from .settings import ROOT


def seed():
    init_db()
    with Session() as db:
        docs = []
        for index in range(12):
            doc_id = f'demo-office-{index + 1:02d}'
            name = f'服务处{index + 1:02d}'
            paragraphs = []
            for service in range(24):
                paragraphs.append(f'{name}办理事项{service + 1:02d}：申请材料需包含身份证明与事项编号。'
                    f'事项{service + 1:02d}的办理时限为{(index + service) % 9 + 2}个工作日，费用为{(index * 7 + service * 3) % 100}元。'
                    f'受理地点是{index + 1}号楼{service + 101}室，负责人为专员{index + 1:02d}-{service + 1:02d}。'
                    f'收到回执后应在{service % 5 + 2}日内核对材料；材料缺失先补交，不保证提前办结。')
            content = '\n\n'.join(paragraphs)
            doc = db.get(Document, doc_id)
            if not doc:
                doc = Document(id=doc_id, title=f'{name}办事手册（合成演示）', source_url='',
                               content=content, content_hash=digest(content), kind='demo')
                db.add(doc)
            docs.append(doc)
        db.flush()
        ds_id = 'dataset-demo'
        if not db.get(Dataset, ds_id):
            db.add(Dataset(id=ds_id, name='100题 · 本地模拟演示', description='合成办事语料；用于功能验证，禁止当作正式评测交付。'))
            db.flush()
        docs_by_id = {d.id: d for d in docs}
        cases = []
        def evidence(doc, service):
            return {'doc_id': doc.id, 'quote': doc.content.split('\n\n')[service]}
        for i in range(100):
            doc, service = docs[i % 12], i % 24
            if i < 40:
                kind = 'fact'
                question = f'服务处{i % 12 + 1:02d}的事项{service + 1:02d}需要多久办理、费用是多少？'
                sources = [evidence(doc, service)]
            elif i < 70:
                kind = 'reasoning'
                other = (service + 1) % 24
                question = f'比较服务处{i % 12 + 1:02d}事项{service + 1:02d}与事项{other + 1:02d}的办理时间和费用，分别说明。'
                sources = [evidence(doc, service), evidence(doc, other)]
            elif i < 90:
                kind = 'multihop'
                other_doc = docs[(i + 1) % 12]
                question = f'先到服务处{i % 12 + 1:02d}办理事项{service + 1:02d}，再到服务处{(i + 1) % 12 + 1:02d}办理事项{service + 1:02d}，两处负责人和地点是什么？'
                sources = [evidence(doc, service), evidence(other_doc, service)]
            else:
                kind = 'refusal'
                question = f'星际科研基地第{i - 89}号太空航班的发射日期和登舰密码是什么？'
                sources = []
            case = {'id': f'DEMO-{i + 1:03d}', 'question': question, 'type': kind,
                    'gold_answer': '\n'.join(e['quote'] for e in sources) if sources else '知识库无此信息，应拒答。',
                    'gold_doc': [], 'gold_chunk_id': [], 'evidence': sources,
                    'difficulty': 'easy' if kind in {'fact', 'refusal'} else 'hard', 'status': 'demo',
                    'annotator': None, 'reviewed_at': None, 'annotation_note': '程序生成合成演示题，未经人工正式审核'}
            payload = validate_case(case, docs_by_id)
            cases.append(payload)
            row_id = f'question-demo-{i + 1:03d}'
            if not db.get(Question, row_id):
                db.add(Question(id=row_id, dataset_id=ds_id, case_id=payload['id'], payload=payload))
        configurations = [
            ('C01 固定分块 · 向量 K3', {}),
            ('C02 向量 K1', {'top_k': 1}),
            ('C03 向量 K5', {'top_k': 5}),
            ('C04 递归分块', {'chunk_strategy': 'recursive'}),
            ('C05 语义分块', {'chunk_strategy': 'semantic'}),
            ('C06 混合检索', {'retrieval': 'hybrid'}),
            ('C07 混合 + 重排', {'retrieval': 'hybrid', 'rerank': True}),
            ('C08 相似度阈值0.25', {'similarity_threshold': 0.25}),
            ('C09 DeepSeek Pro', {'model': 'deepseek-v4-pro'})]
        folder = ROOT / 'data' / 'configs'
        folder.mkdir(parents=True, exist_ok=True)
        import yaml
        for i, (name, values) in enumerate(configurations, 1):
            config_id = f'config-c{i:02d}'
            params = Parameters(**values).model_dump()
            if not db.get(Config, config_id):
                db.add(Config(id=config_id, name=name, parameters=params))
            (folder / f'C{i:02d}.yaml').write_text(yaml.safe_dump({'id': config_id, 'name': name, 'parameters': params}, allow_unicode=True, sort_keys=False), encoding='utf-8')
        asset = ROOT / 'data' / 'demo_eval_set.json'
        asset.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
        db.commit()
        print('演示初始化完成：12份合成文档，100道demo题，9套配置；不代表正式验收。')


if __name__ == '__main__':
    seed()
