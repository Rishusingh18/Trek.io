"""
Health check tests (SRS requirement verification).
"""
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_health_endpoint_healthy(client: TestClient):
    """Verify GET /health returns 200 and healthy when DB and Redis are up."""
    with patch("app.main.check_db_health", return_value=True), \
         patch("app.main.check_redis_health", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "up"
        assert data["redis"] == "up"
        assert "version" in data


def test_health_endpoint_degraded_when_db_down(client: TestClient):
    """Verify GET /health returns 503 and degraded when DB is unreachable."""
    with patch("app.main.check_db_health", return_value=False), \
         patch("app.main.check_redis_health", return_value=True):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "down"
        assert data["redis"] == "up"


def test_health_endpoint_degraded_when_redis_down(client: TestClient):
    """Verify GET /health returns 503 and degraded when Redis is unreachable."""
    with patch("app.main.check_db_health", return_value=True), \
         patch("app.main.check_redis_health", return_value=False):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "up"
        assert data["redis"] == "down"
