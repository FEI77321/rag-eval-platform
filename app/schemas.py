from typing import Literal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Evidence(StrictModel):
    doc_id: str
    quote: str = Field(min_length=4)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=1)


class Case(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=3)
    type: Literal['fact', 'reasoning', 'multihop', 'refusal']
    gold_answer: str = Field(min_length=1)
    gold_doc: list[str] = Field(default_factory=list)
    gold_chunk_id: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    difficulty: Literal['easy', 'medium', 'hard'] = 'medium'
    status: Literal['draft', 'reviewed', 'demo'] = 'draft'
    annotator: str | None = None
    reviewed_at: str | None = None
    annotation_note: str = ''

    @model_validator(mode='after')
    def valid_evidence(self):
        if self.type == 'refusal' and (self.evidence or self.gold_doc or self.gold_chunk_id):
            raise ValueError('拒答题标准来源必须为空')
        if self.type != 'refusal' and not self.evidence:
            raise ValueError('回答题必须标注稳定标准证据')
        if self.status == 'reviewed' and (not self.annotator or not self.reviewed_at):
            raise ValueError('人工审核题必须记录审核人和审核时间')
        if self.status == 'reviewed':
            try:
                stamp = datetime.fromisoformat(self.reviewed_at.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('审核时间必须为带时区的ISO 8601时间') from None
            if stamp.tzinfo is None:
                raise ValueError('审核时间必须包含时区')
        return self


class Parameters(StrictModel):
    chunk_strategy: Literal['fixed', 'recursive', 'semantic'] = 'fixed'
    chunk_size: int = Field(default=500, ge=100, le=5000)
    chunk_overlap: int = Field(default=80, ge=0)
    semantic_threshold: float = Field(default=0.55, ge=-1, le=1)
    retrieval: Literal['vector', 'hybrid'] = 'vector'
    top_k: int = Field(default=3, ge=1, le=30)
    candidate_k: int = Field(default=15, ge=1, le=100)
    similarity_threshold: float = Field(default=0, ge=-1, le=1)
    rerank: bool = False
    rerank_top_n: int = Field(default=5, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1)
    model: str = 'deepseek-flash'
    thinking: bool = False
    input_price: float | None = Field(default=None, ge=0)
    output_price: float | None = Field(default=None, ge=0)
    temperature: float = Field(default=0, ge=0, le=2)
    max_tokens: int = Field(default=700, ge=32, le=8192)
    evidence_coverage: float = Field(default=0.8, gt=0, le=1)

    @model_validator(mode='after')
    def limits(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError('chunk_overlap必须小于chunk_size')
        if self.candidate_k < self.top_k:
            raise ValueError('candidate_k不能小于top_k')
        if self.rerank and not self.top_k <= self.rerank_top_n <= self.candidate_k:
            raise ValueError('开启重排时 top_k ≤ rerank_top_n ≤ candidate_k')
        return self


class JudgeOutput(StrictModel):
    accuracy: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    refused: bool
    unsupported: bool
    factually_incorrect: bool | None
    reason: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class HumanReview(StrictModel):
    accuracy: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    refused: bool = False
    unsupported: bool = False
    factually_incorrect: bool | None = None
    reviewer: str = Field(min_length=1)
    note: str = ''


class RunInput(StrictModel):
    name: str = Field(default='配置对比实验', min_length=1)
    dataset_id: str
    config_ids: list[str] = Field(min_length=1)
    mode: Literal['demo', 'cloud'] = 'demo'
    concurrency: int = Field(default=3, ge=1, le=20)
    sample_seed: int = 42
