from sqlalchemy import String, Text, Integer, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, utcnow

LargeText = Text().with_variant(LONGTEXT(), 'mysql')


class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(2048), default='')
    content: Mapped[str] = mapped_column(LargeText)
    content_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20), default='real')
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)


class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)


class Question(Base):
    __tablename__ = 'questions'
    __table_args__ = (UniqueConstraint('dataset_id', 'case_id'),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'))
    case_id: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)


class Config(Base):
    __tablename__ = 'configs'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    parameters: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)


class Run(Base):
    __tablename__ = 'runs'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    dataset_id: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    mode: Mapped[str] = mapped_column(String(12))
    concurrency: Mapped[int] = mapped_column(Integer, default=3)
    snapshot: Mapped[dict] = mapped_column(JSON)
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    heartbeat: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)


class Item(Base):
    __tablename__ = 'run_items'
    __table_args__ = (UniqueConstraint('run_id', 'config_id', 'case_id'),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    config_id: Mapped[str] = mapped_column(String(64), index=True)
    case_id: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    generation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judgement: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(Text, default='')
    human_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[object] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class IndexCache(Base):
    __tablename__ = 'index_cache'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)


class ApiCall(Base):
    __tablename__ = 'api_calls'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)
