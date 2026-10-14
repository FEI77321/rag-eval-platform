import os
import tempfile
from pathlib import Path
import pytest

# 所有测试使用独立临时数据库，绝不清空用户演示/正式结果。
test_dir = Path(tempfile.mkdtemp(prefix='rag-lab-tests-'))
os.environ['DATABASE_URL'] = 'sqlite:///' + (test_dir / 'tests.db').as_posix()
os.environ['PROVIDER_MODE'] = 'demo'


@pytest.fixture(autouse=True)
def clean_test_database():
    from app.db import Base, engine, init_db
    init_db()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded():
    from app.seed import seed
    seed()
