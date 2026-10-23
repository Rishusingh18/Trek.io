"""
Custom ASGI Middlewares:
1. Request ID & Latency Logging Middleware (NFR-01, NFR-12).
2. Rate Limiting Middleware (Global & Stricter on /auth/login) (NFR-06).
"""
import time
import uuid
from typing import Dict, Tuple, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.core.logging import request_id_ctx, logger


class RequestIDAndLatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Resolve or generate Request ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(req_id)

        start_time = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            status_code = getattr(response, "status_code", 500) if response else 500

            # Log request metrics with latency
            logger.info(
                f"Handled {request.method} {request.url.path} with status {status_code} in {latency_ms:.2f}ms"
            )
            request_id_ctx.reset(token)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding window rate limiter.
    - Global limit: 120 req / minute per IP.
    - Stricter login limit: 5 req / minute per IP on /auth/login (NFR-06).
    """
    requests_history: Dict[str, List[float]] = {}

    def __init__(
        self,
        app,
        global_limit: int = 120,
        login_limit: int = 5,
        window_seconds: int = 60
    ):
        super().__init__(app)
        self.global_limit = global_limit
        self.login_limit = login_limit
        self.window_seconds = window_seconds

    @classmethod
    def reset(cls) -> None:
        """Reset rate limiter state across all instances."""
        cls.requests_history.clear()

    def _is_rate_limited(self, key: str, limit: int) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        timestamps = self.requests_history.get(key, [])
        # Retain only timestamps within the current window
        valid_timestamps = [ts for ts in timestamps if ts > cutoff]
        
        if len(valid_timestamps) >= limit:
            self.requests_history[key] = valid_timestamps
            return True
        
        valid_timestamps.append(now)
        self.requests_history[key] = valid_timestamps
        return False

    def clear_history(self) -> None:
        """Reset rate limiter history (useful for test isolation)."""
        self.requests_history.clear()

    async def dispatch(self, request: Request, call_next) -> Response:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"
        path = request.url.path
        req_id = request_id_ctx.get() or request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Strict rate limit for login endpoint (NFR-06)
        if path.endswith("/auth/login") and request.method == "POST":
            login_key = f"login:{client_ip}"
            if self._is_rate_limited(login_key, self.login_limit):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many login attempts. Please wait before trying again.",
                            "request_id": req_id,
                            "details": {"retry_after_seconds": self.window_seconds}
                        }
                    },
                    headers={"X-Request-ID": req_id}
                )

        # Global rate limit
        global_key = f"global:{client_ip}"
        if self._is_rate_limited(global_key, self.global_limit):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Global rate limit exceeded. Please throttle your requests.",
                        "request_id": req_id,
                        "details": {"retry_after_seconds": self.window_seconds}
                    }
                },
                headers={"X-Request-ID": req_id}
            )

        return await call_next(request)
