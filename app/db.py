from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.engine import URL
from .settings import settings


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


Path('runtime').mkdir(exist_ok=True)
database_target = URL.create('mysql+pymysql', username=settings.mysql_user, password=settings.mysql_password,
    host=settings.mysql_host, port=settings.mysql_port, database=settings.mysql_database,
    query={'charset':'utf8mb4'}) if settings.mysql_host else settings.database_url
sqlite_mode = not settings.mysql_host and settings.database_url.startswith('sqlite')
engine = create_engine(database_target, pool_pre_ping=True,
    connect_args={'check_same_thread': False, 'timeout': 30} if sqlite_mode else {})
if sqlite_mode:
    @event.listens_for(engine, 'connect')
    def sqlite_setup(conn, _):
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')

Session = sessionmaker(engine, expire_on_commit=False)


def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
