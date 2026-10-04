import os
import tempfile
from pathlib import Path
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='assessment-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(os.environ['DATA_DIR'])/'test.db')
os.environ['LLM_MODE'] = 'mock'
os.environ['RETRIEVAL_MODE'] = 'local'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import store

@pytest.fixture(autouse=True)
def reset_database():
    store.Base.metadata.drop_all(store.engine)
    store.init_db()
    yield

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def headers():
    return {'X-Service-Token':'local-demo-internal-token','X-Tenant-ID':'demo-hospital','X-Actor-ID':'test-reviewer','X-Role':'reviewer'}
