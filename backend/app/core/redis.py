"""
Redis client wrapper adhering to the Redis Rule:
Every key must have an expiry, and every read falls back to PostgreSQL/DB on a miss.
Redis must hold nothing that cannot be rebuilt from PostgreSQL.
Includes lightweight in-memory fallback when standalone Redis server is unavailable.
"""
from typing import Optional, Any, Callable
import json
import time
import socket
import threading
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import redis
from app.core.config import settings
from app.core.logging import logger

_redis_client: Optional[Any] = None


class InMemoryRedis:
    """Thread-safe in-memory cache fallback implementing basic Redis string semantics."""
    def __init__(self):
        self._data = {}
        self._expiries = {}
        self._lock = threading.RLock()

    def _purge_expired(self):
        """Purge expired keys synchronously so memory is reclaimed independently."""
        now = time.time()
        expired_keys = [k for k, exp in self._expiries.items() if now > exp]
        for k in expired_keys:
            self._data.pop(k, None)
            self._expiries.pop(k, None)

    def get(self, key: str):
        with self._lock:
            self._purge_expired()
            if key in self._expiries and time.time() > self._expiries[key]:
                self._data.pop(key, None)
                self._expiries.pop(key, None)
                return None
            return self._data.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False):
        with self._lock:
            self._purge_expired()
            if key in self._expiries and time.time() > self._expiries[key]:
                self._data.pop(key, None)
                self._expiries.pop(key, None)

            # Atomic existence check and set when nx is requested
            if nx and key in self._data:
                return None
            self._data[key] = str(value) if not isinstance(value, (str, bytes)) else value
            if ex is not None:
                self._expiries[key] = time.time() + ex
            else:
                self._expiries.pop(key, None)
            return True

    def setex(self, key: str, time_s: int, value: Any):
        return self.set(key, value, ex=time_s)

    def delete(self, *keys):
        with self._lock:
            count = 0
            for k in keys:
                if k in self._data:
                    del self._data[k]
                    self._expiries.pop(k, None)
                    count += 1
            return count

    def ping(self) -> bool:
        return True


def _sanitize_redis_url(url_str: str) -> str:
    """Sanitize redis URL to omit credentials in userinfo and query string when logging."""
    try:
        parsed = urlparse(url_str)
        netloc = parsed.hostname or "127.0.0.1"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"

        # Filter sensitive credential parameters from query string while preserving safe diagnostic parameters
        sensitive_keys = {"password", "secret", "token", "auth", "key", "access_token"}
        safe_query = []
        if parsed.query:
            for k, v in parse_qsl(parsed.query, keep_blank_values=True):
                if k.lower() in sensitive_keys:
                    safe_query.append((k, "******"))
                else:
                    safe_query.append((k, v))
        query_str = urlencode(safe_query) if safe_query else ""

        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, query_str, parsed.fragment))
    except Exception:
        return "redis://[sanitized-host]"


def _sanitize_error_str(err: Exception, raw_url: str) -> str:
    """Ensure error message does not expose Redis credentials."""
    msg = str(err)
    try:
        parsed = urlparse(raw_url)
        if parsed.password and parsed.password in msg:
            msg = msg.replace(parsed.password, "******")
    except Exception:
        pass
    return msg


def get_redis_client() -> Any:
    global _redis_client
    if _redis_client is None:
        try:
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                retry_on_timeout=False,
            )
            client.ping()
            _redis_client = client
            return _redis_client
        except Exception as e:
            safe_url = _sanitize_redis_url(settings.REDIS_URL)
            safe_err = _sanitize_error_str(e, settings.REDIS_URL)
            logger.warning(f"Failed to connect to Redis at {safe_url}: {safe_err}")
            _redis_client = InMemoryRedis()
    return _redis_client


def check_redis_health() -> bool:
    try:
        client = get_redis_client()
        # When InMemoryRedis fallback is active, report Redis as unavailable
        if isinstance(client, InMemoryRedis):
            return False
        return bool(client.ping())
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


def get_with_fallback(
    key: str,
    fallback_fn: Callable[[], Any],
    ttl_seconds: int = 3600
) -> Any:
    """
    Attempt to read from Redis/cache.
    On miss, exception, or unavailability, run fallback_fn to read from DB,
    and then populate Redis/cache with the mandatory TTL.
    """
    try:
        client = get_redis_client()
        cached = client.get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Cache read error for key {key}, falling back to DB: {e}")

    # Fallback to DB
    data = fallback_fn()
    if data is not None:
        try:
            client = get_redis_client()
            client.set(key, json.dumps(data), ex=ttl_seconds)
        except Exception as e:
            logger.warning(f"Failed to cache key {key}: {e}")

    return data
