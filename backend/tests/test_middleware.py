"""
Middleware tests: Request ID, Latency Logging, and Rate Limiting (NFR-01, NFR-06, NFR-12).
"""
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_middleware_request_id_returned_in_header(client: TestClient):
    """Verify middleware assigns or forwards X-Request-ID header on all responses."""
    with patch("app.main.check_db_health", return_value=True), \
         patch("app.main.check_redis_health", return_value=True):
        # Generated if not provided
        res1 = client.get("/health")
        assert "X-Request-ID" in res1.headers
        generated_id = res1.headers["X-Request-ID"]
        assert len(generated_id) > 0

        # Forwarded if provided by client
        custom_id = str(uuid.uuid4())
        res2 = client.get("/health", headers={"X-Request-ID": custom_id})
        assert res2.headers["X-Request-ID"] == custom_id


def test_middleware_stricter_rate_limit_on_login(client: TestClient):
    """Verify NFR-06: Stricter rate limit on login (5 req/min) returns 429 on breach."""
    from app.core.middleware import RateLimitMiddleware
    RateLimitMiddleware.reset()

    login_payload = {"email": "ratelimit@test.com", "password": "wrongpassword"}

    # First 5 login attempts are allowed through to handler (returning 401 for bad creds)
    for _ in range(5):
        res = client.post("/v1/auth/login", json=login_payload)
        assert res.status_code != 429

    # 6th attempt breaches the limit -> 429 Too Many Requests
    breached_res = client.post("/v1/auth/login", json=login_payload)
    assert breached_res.status_code == 429
    err = breached_res.json()["error"]
    assert err["code"] == "RATE_LIMIT_EXCEEDED"
    assert "retry_after_seconds" in err["details"]
    assert "X-Request-ID" in breached_res.headers


def test_middleware_latency_logging(client: TestClient):
    """Verify NFR-01, NFR-12: Latency is measured and logged for requests."""
    with patch("app.main.check_db_health", return_value=True), \
         patch("app.main.check_redis_health", return_value=True), \
         patch("app.core.middleware.logger.info") as mock_log:
        client.get("/health")
        assert mock_log.called
        log_message = mock_log.call_args[0][0]
        assert "Handled GET /health" in log_message
        assert "ms" in log_message
