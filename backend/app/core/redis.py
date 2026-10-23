"""
Redis client wrapper adhering to the Redis Rule:
Every key must have an expiry, and every read falls back to PostgreSQL on a miss.
Redis must hold nothing that cannot be rebuilt from PostgreSQL.
"""
from typing import Optional, Any, Callable
import json
import redis
from app.core.config import settings
from app.core.logging import logger

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    return _redis_client


def check_redis_health() -> bool:
    try:
        client = get_redis_client()
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
    Attempt to read from Redis.
    On miss, exception, or unavailability, run fallback_fn to read from PostgreSQL,
    and then populate Redis with the mandatory TTL.
    """
    try:
        client = get_redis_client()
        cached = client.get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read error for key {key}, falling back to DB: {e}")

    # Fallback to PostgreSQL
    data = fallback_fn()
    if data is not None:
        try:
            client = get_redis_client()
            client.set(key, json.dumps(data), ex=ttl_seconds)
        except Exception as e:
            logger.warning(f"Failed to cache key {key} in Redis: {e}")

    return data
