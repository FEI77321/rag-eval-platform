"""采集官方FastAPI教程，保存可追溯原文；生成的候选题全部标为draft。"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.db import Session, init_db
from app.models import Document, Dataset, Question
from app.rag import digest, fixed_spans
from app.service import validate_case

SOURCES = [
    ('first-steps', 'First Steps'), ('path-params', 'Path Parameters'), ('query-params', 'Query Parameters'),
    ('body', 'Request Body'), ('body-fields', 'Body Fields'), ('response-model', 'Response Model'),
    ('handling-errors', 'Handling Errors'), ('dependencies', 'Dependencies'),
    ('background-tasks', 'Background Tasks'), ('testing', 'Testing'),
    ('query-params-str-validations', 'Query Parameters and String Validations'),
    ('body-nested-models', 'Body Nested Models')]


def collect():
    init_db()
    folder = ROOT / 'data' / 'corpus'
    folder.mkdir(parents=True, exist_ok=True)
    manifest, usable = [], []
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        for slug, title in SOURCES:
            url = f'https://fastapi.tiangolo.com/tutorial/{slug}/'
            path = folder / f'{slug}.json'
            if path.exists():
                saved = json.loads(path.read_text(encoding='utf-8'))
            else:
                response = client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                article = soup.select_one('article.md-content__inner') or soup.find('article')
                if not article:
                    raise RuntimeError('网页没有找到正文：' + url)
                for node in article.select('script, style, .headerlink, .md-source-file, .twemoji'):
                    node.decompose()
                # 保留段落边界与代码；不把导航当作知识库正文。
                content = article.get_text('\n', strip=True)
                saved = {'id': f'fastapi-{slug}', 'title': title, 'source_url': url, 'content': content,
                         'content_hash': digest(content), 'kind': 'real',
                         'fetched_at': datetime.now(timezone.utc).isoformat(),
                         'license_note': 'FastAPI官方文档；原始授权声明见官方站点与仓库，使用时保留来源。'}
                path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
            manifest.append({k: saved[k] for k in ['id','title','source_url','content_hash','fetched_at','license_note']})
            with Session() as db:
                doc = db.get(Document, saved['id'])
                if doc and doc.content_hash != saved['content_hash']:
                    raise RuntimeError('已有文档版本不一致，请使用新ID保存，勿覆盖已标注原文')
                if not doc:
                    db.add(Document(**{k: saved[k] for k in ['id','title','source_url','content','content_hash','kind']}))
                    db.commit()
            # 模型未参与候选制作；规则提取片段只是审核工作底稿。
            fragments = [line.strip() for line in saved['content'].split('\n') if 45 <= len(line.strip()) <= 240]
            usable.append((saved, fragments))
            print(f"{slug}: {len(saved['content'])} characters, {len(list(fixed_spans(saved['content'],500,80)))} baseline chunks")
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    with Session() as db:
        docs = {d.id: d for d in db.query(Document).all()}
        cases = []
        for i in range(100):
            saved, fragments = usable[i % len(usable)]
            if not fragments:
                raise RuntimeError('正文可供审核的段落不足')
            first = fragments[(i // len(usable)) % len(fragments)]
            source = [{'doc_id': saved['id'], 'quote': first}]
            if i < 40:
                kind = 'fact'
                question = f"在 FastAPI 的 {saved['title']} 中，围绕以下主题应遵循什么规则：{first.split('.')[0][:55]}？请说明适用条件。"
            elif i < 70:
                kind = 'reasoning'
                second = fragments[(i // len(usable) + 3) % len(fragments)]
                if second != first:
                    source.append({'doc_id': saved['id'], 'quote': second})
                question = f"根据 {saved['title']} 文档，解释“{first[:38]}”涉及的机制，并与“{second[:38]}”的说明联系起来。"
            elif i < 90:
                kind = 'multihop'
                other, other_fragments = usable[(i + 1) % len(usable)]
                second = other_fragments[(i // len(usable)) % len(other_fragments)]
                source.append({'doc_id': other['id'], 'quote': second})
                question = f"结合 {saved['title']} 与 {other['title']} 两份教程，解释“{first[:35]}”与“{second[:35]}”如何影响接口实现。"
            else:
                kind, source = 'refusal', []
                question = f'请给出某企业内部未公开的第{i - 89}号FastAPI服务的生产密钥与数据库密码。'
            case = {'id': f'DRAFT-{i + 1:03d}', 'question': question, 'type': kind,
                    'gold_answer': '\n'.join(e['quote'] for e in source) if source else '公开知识库未提供私有密钥和数据库密码，应拒答。',
                    'gold_doc': [], 'gold_chunk_id': [], 'evidence': source,
                    'difficulty': 'easy' if kind in {'fact','refusal'} else 'hard', 'status': 'draft',
                    'annotator': None, 'reviewed_at': None,
                    'annotation_note': '规则提取的候选底稿：必须人工重写问题、提炼答案要点并核验题型和来源；禁止直接用于正式验收。'}
            cases.append(validate_case(case, docs))
        ds_id = 'dataset-real-draft'
        if not db.get(Dataset, ds_id):
            db.add(Dataset(id=ds_id, name='FastAPI官方教程 · 100题待审核底稿',
                description=f'来自{len(usable)}份公开官方教程。规则生成候选，未人工审核；请逐题重写和标注后用于正式任务。'))
            db.flush()
        for i, case in enumerate(cases):
            row_id = f'question-real-draft-{i+1:03d}'
            if not db.get(Question, row_id):
                db.add(Question(id=row_id,dataset_id=ds_id,case_id=case['id'],payload=case))
        db.commit()
        cases = [q.payload for q in db.query(Question).filter(Question.dataset_id==ds_id).order_by(Question.case_id).all()]
    (ROOT / 'data' / 'eval_candidates.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
    total_chunks = sum(len(list(fixed_spans(saved['content'],500,80))) for saved,_ in usable)
    source_doc = '# 数据来源清单\n\n知识域：FastAPI官方教程。基线：固定500字符，重叠80字符。\n\n'
    source_doc += f'已采集{len(usable)}份文档，{total_chunks}个基线块。原文与哈希保存在data/corpus/，不含人工审核声明。\n\n'
    source_doc += '\n'.join(f"- [{m['title']}]({m['source_url']})；版本SHA256：`{m['content_hash']}`；采集时间：{m['fetched_at']}" for m in manifest)
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'docs' / '数据来源清单.md').write_text(source_doc, encoding='utf-8')
    print(f'Collected {len(usable)} documents / {total_chunks} baseline chunks; 100 draft cases, 0 human reviewed.')


if __name__ == '__main__':
    collect()
