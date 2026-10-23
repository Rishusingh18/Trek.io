"""
Redis distributed locking for background worker jobs (Architecture doc, Worker section).
Ensures each job type is claimed by only one worker at a time.
"""
import uuid
import time
from typing import Optional
from app.core.redis import get_redis_client
from app.core.logging import logger


class WorkerLock:
    """
    Distributed lock backed by Redis with TTL to prevent deadlocks.
    """
    def __init__(self, job_name: str, ttl_seconds: int = 120, worker_id: Optional[str] = None):
        self.job_name = job_name
        self.ttl_seconds = ttl_seconds
        self.lock_key = f"lock:worker:{job_name}"
        self.token = worker_id or str(uuid.uuid4())
        self.acquired = False

    def acquire(self) -> bool:
        """Attempt to acquire distributed lock with NX and EX."""
        try:
            client = get_redis_client()
            res = client.set(self.lock_key, self.token, nx=True, ex=self.ttl_seconds)
            self.acquired = bool(res)
            return self.acquired
        except Exception as e:
            logger.warning(f"Worker lock error on {self.lock_key}: {e}. Proceeding as fallback.")
            self.acquired = True
            return True

    def release(self) -> None:
        """Release the lock if held by this worker."""
        if not self.acquired:
            return
        try:
            client = get_redis_client()
            # Release only if value matches token (safe unlock)
            val = client.get(self.lock_key)
            if val == self.token:
                client.delete(self.lock_key)
        except Exception as e:
            logger.warning(f"Error releasing worker lock on {self.lock_key}: {e}")
        finally:
            self.acquired = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
