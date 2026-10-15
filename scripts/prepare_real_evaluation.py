"""采集/复用官方文档正文快照。不会调用模型或生成题目。"""
import asyncio
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.db import init_db,Session
from app.models import Document
from app.rag import digest,fixed_spans

SLUGS=['first-steps','path-params','query-params','body','body-fields','response-model',
       'handling-errors','dependencies','background-tasks','testing','query-params-str-validations',
       'body-nested-models','body-multiple-params','path-params-numeric-validations','extra-data-types',
       'header-params','cookie-params','query-param-models','response-status-code','request-forms',
       'request-files','debugging','sql-databases']
FOLDER=ROOT/'data'/'corpus_v2'


def clean_html(html):
    soup=BeautifulSoup(html,'html.parser')
    article=soup.select_one('article.md-content__inner') or soup.find('article')
    if not article:
        raise ValueError('没有找到正文')
    for node in article.select('script,style,.headerlink,.md-source-file'):
        node.decompose()
    blocks=[]
    for node in article.select('h1,h2,h3,h4,p,pre,li,table'):
        if node.find_parent(['pre','li','table']) is not None:
            continue
        text=node.get_text('',strip=False) if node.name=='pre' else node.get_text(' ',strip=True)
        text=text.strip()
        if text:
            blocks.append(text)
    return '\n\n'.join(blocks)


async def collect():
    FOLDER.mkdir(parents=True,exist_ok=True)
    docs=[]
    async with httpx.AsyncClient(timeout=45,follow_redirects=True) as client:
        for slug in SLUGS:
            path=FOLDER/(slug+'.json')
            if path.exists():
                doc=json.loads(path.read_text(encoding='utf-8'))
            else:
                url='https://fastapi.tiangolo.com/tutorial/'+slug+'/'
                reply=await client.get(url);reply.raise_for_status()
                text=clean_html(reply.text)
                doc={'id':'official-v2-'+slug,'title':slug.replace('-',' ').title(),
                     'source_url':url,'content':text,'content_hash':digest(text),'kind':'real',
                     'fetched_at':datetime.now(timezone.utc).isoformat(),
                     'normalization':'HTML正文块；段内保留空格，代码保留原始换行；v2'}
                path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
            docs.append(doc)
            with Session() as db:
                if not db.get(Document,doc['id']):
                    db.add(Document(**{k:doc[k] for k in ['id','title','source_url','content','content_hash','kind']}));db.commit()
            print('source',slug,len(doc['content']),flush=True)
    chunks=sum(len(list(fixed_spans(d['content'],500,80))) for d in docs)
    (FOLDER/'manifest.json').write_text(json.dumps([{k:d[k] for k in ['id','title','source_url','content_hash','fetched_at']} for d in docs],ensure_ascii=False,indent=2),encoding='utf-8')
    assert chunks>=300,f'基线块不足：{chunks}'
    print('corpus:',len(docs),'documents',chunks,'baseline chunks',flush=True)
    return docs


if __name__=='__main__':
    init_db()
    asyncio.run(collect())
