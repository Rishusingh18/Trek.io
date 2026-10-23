"""
Pytest fixtures and configuration.
Uses in-memory SQLite database with StaticPool for fast, isolated test execution.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db

# Create an in-memory SQLite database
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class FakeRedis:
    def __init__(self):
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self._data:
            return None
        self._data[key] = str(value) if not isinstance(value, (str, bytes)) else value
        return True

    def setex(self, key, time, value):
        self._data[key] = str(value) if not isinstance(value, (str, bytes)) else value
        return True

    def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                count += 1
        return count

    def ping(self):
        return True


@pytest.fixture(autouse=True)
def mock_redis_for_tests(monkeypatch):
    """Ensure tests run lightning fast in-memory without waiting on Redis socket timeouts."""
    fake = FakeRedis()
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: fake)
    monkeypatch.setattr("app.core.redis._redis_client", fake)
    yield fake



@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all database tables for test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a transactional database session for a test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session):
    """TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
