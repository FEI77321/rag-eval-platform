import hashlib
import json
import math
import re
import time
from collections import Counter
import numpy as np
from .db import Session
from .models import IndexCache
from .providers import tokens
from .settings import settings


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def chunk_identifier(doc, start, end, parameters):
    version = digest({'hash': doc['content_hash'], 'strategy': parameters['chunk_strategy'],
                      'size': parameters['chunk_size'], 'overlap': parameters['chunk_overlap'],
                      'semantic_threshold': parameters.get('semantic_threshold') if parameters['chunk_strategy'] == 'semantic' else None})[:10]
    return f"{doc['id']}:{version}:{start}-{end}"


def fixed_spans(text, size, overlap):
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        yield start, end
        if end == len(text):
            break
        start = end - overlap


def recursive_spans(text, size, overlap):
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            lower = start + max(1, size // 2)
            choices = [text.rfind(sep, lower, end) + len(sep) for sep in ['\n\n', '\n', '。', '. ']]
            choices = [v for v in choices if lower < v <= end]
            if choices:
                end = max(choices)
        yield start, end
        if end == len(text):
            break
        start = max(start + 1, end - overlap)


async def semantic_spans(text, parameters, gateway):
    # 单元先按句/段切分，再用嵌入余弦距离控制边界；原文坐标始终保留。
    units = [(m.start(), m.end()) for m in re.finditer(r'[^\n。.!?！？]+[\n。.!?！？]*', text)]
    if not units:
        return list(fixed_spans(text, parameters['chunk_size'], parameters['chunk_overlap']))
    vectors = np.asarray(await gateway.embed([text[a:b] for a, b in units]))
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)
    spans, start = [], units[0][0]
    for i in range(1, len(units)):
        boundary = float(vectors[i - 1] @ vectors[i]) < parameters['semantic_threshold']
        too_long = units[i][1] - start > parameters['chunk_size']
        if boundary or too_long:
            end = units[i - 1][1]
            for a, b in fixed_spans(text[start:end], parameters['chunk_size'], parameters['chunk_overlap']):
                spans.append((start + a, start + b))
            start = max(units[i][0] - parameters['chunk_overlap'], units[i - 1][0])
    for a, b in fixed_spans(text[start:units[-1][1]], parameters['chunk_size'], parameters['chunk_overlap']):
        spans.append((start + a, start + b))
    return list(dict.fromkeys(spans))


class RagIndex:
    def __init__(self, chunks, vectors):
        self.chunks = chunks
        matrix = np.asarray(vectors, dtype=float)
        self.vectors = matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
        self.term_counts = [Counter(tokens(c['text'])) for c in chunks]
        self.lengths = [sum(c.values()) for c in self.term_counts]
        self.avg_length = sum(self.lengths) / max(1, len(self.lengths))
        self.df = Counter(t for c in self.term_counts for t in c)

    @classmethod
    async def build(cls, documents, parameters, gateway):
        key = digest({'docs': [(d['id'], d['content_hash']) for d in documents],
                      'chunk': {k: parameters[k] for k in ['chunk_strategy', 'chunk_size', 'chunk_overlap', 'semantic_threshold']},
                      'mode': gateway.mode, 'embedding_model': settings.embedding_model,
                      'embedding_url': settings.embedding_base_url, 'implementation': 2})
        with Session() as db:
            cached = db.get(IndexCache, key)
            if cached:
                return cls(**cached.payload)
        chunks = []
        for doc in documents:
            text = doc['content']
            strategy = parameters['chunk_strategy']
            if strategy == 'semantic':
                spans = await semantic_spans(text, parameters, gateway)
            else:
                fn = fixed_spans if strategy == 'fixed' else recursive_spans
                spans = list(fn(text, parameters['chunk_size'], parameters['chunk_overlap']))
            for start, end in spans:
                chunks.append({'id': chunk_identifier(doc, start, end, parameters), 'doc_id': doc['id'],
                               'start': start, 'end': end, 'text': text[start:end], 'source_url': doc['source_url']})
        if not chunks:
            raise ValueError('知识库没有可索引文本')
        vectors = await gateway.embed([c['text'] for c in chunks])
        with Session() as db:
            if not db.get(IndexCache, key):
                db.add(IndexCache(id=key, payload={'chunks': chunks, 'vectors': vectors}))
                db.commit()
        return cls(chunks, vectors)

    def bm25(self, question):
        n = len(self.chunks)
        scores = []
        for counts, length in zip(self.term_counts, self.lengths):
            score = 0.0
            for term in set(tokens(question)):
                freq = counts[term]
                if freq:
                    idf = math.log(1 + (n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                    score += idf * freq * 2.5 / (freq + 1.5 * (0.25 + 0.75 * length / max(1, self.avg_length)))
            scores.append(score)
        return scores

    async def retrieve(self, question, parameters, gateway):
        start = time.perf_counter()
        query = np.asarray((await gateway.embed([question]))[0])
        query /= max(np.linalg.norm(query), 1e-12)
        scores = self.vectors @ query
        vector_order = sorted((i for i in range(len(scores)) if scores[i] >= parameters['similarity_threshold']),
                              key=lambda i: float(scores[i]), reverse=True)[:parameters['candidate_k']]
        fused = {}
        if parameters['retrieval'] == 'hybrid':
            lexical = self.bm25(question)
            bm_order = sorted((i for i in range(len(lexical)) if lexical[i] > 0),
                              key=lambda i: lexical[i], reverse=True)[:parameters['candidate_k']]
            for order in [vector_order, bm_order]:
                for rank, index in enumerate(order, 1):
                    fused[index] = fused.get(index, 0) + 1 / (parameters['rrf_k'] + rank)
            order = sorted(fused, key=fused.get, reverse=True)[:parameters['candidate_k']]
        else:
            order = vector_order
        candidates = [{**self.chunks[i], 'vector_score': float(scores[i]), 'fusion_score': fused.get(i)} for i in order]
        retrieval_ms = (time.perf_counter() - start) * 1000
        rerank_start = time.perf_counter()
        ranked = await gateway.rerank(question, candidates, parameters['rerank_top_n']) if parameters['rerank'] else candidates
        rerank_ms = (time.perf_counter() - rerank_start) * 1000 if parameters['rerank'] else 0
        return ranked[:parameters['top_k']], candidates, {'retrieval_ms': retrieval_ms, 'rerank_ms': rerank_ms}
