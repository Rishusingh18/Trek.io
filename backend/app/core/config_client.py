"""
Dynamic Configuration Client adhering to NFR-13, FR-807, and the Redis Rule:
1. Check Redis cache first.
2. On miss/failure, fetch from PostgreSQL 'configs' table.
3. Cache in Redis with mandatory TTL.
4. Fall back to defaults in app/core/config.py if unset in DB.
"""
from typing import Any, Dict, Optional
import json
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.logging import logger
from app.db.models.config import Config


class ConfigClient:
    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        cache_key = f"config:{key}"
        # 1. Check Redis cache
        try:
            client = get_redis_client()
            cached = client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss/error for config '{key}': {e}")

        # 2. Fallback to PostgreSQL
        try:
            from sqlalchemy import select
            row = self.db.execute(select(Config).where(Config.key == key)).scalar_one_or_none()
            if row and row.value is not None:
                val = row.value
                # 3. Store back in Redis with 24h TTL
                try:
                    client = get_redis_client()
                    client.setex(cache_key, 86400, json.dumps(val))
                except Exception as e:
                    logger.warning(f"Failed to cache config '{key}' into Redis: {e}")
                return val
        except Exception as e:
            logger.warning(f"Database lookup failed for config '{key}': {e}")

        # 4. Fallback to default
        return default
