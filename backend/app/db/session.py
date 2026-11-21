"""
SQLAlchemy database session and engine management.
Supports PostgreSQL and local SQLite with seamless relative path resolution.
"""
from typing import Generator
import os
import threading
import uuid
from contextvars import ContextVar
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.core.logging import logger

_lock_token_cv: ContextVar[str | None] = ContextVar("lock_token", default=None)
_held_locks_cv: ContextVar[frozenset] = ContextVar("held_locks", default=frozenset())


def _current_actor():
    try:
        import asyncio
        task = asyncio.current_task()
        if task is not None:
            return (threading.get_ident(), id(task))
    except Exception:
        pass
    return (threading.get_ident(), None)


class ReentrantCrossThreadLock:
    """
    A reentrant lock that supports cross-thread and cross-worker release
    across asynchronous and threadpool worker lifecycles.
    Tracks context ownership via ContextVar (falling back to actor identity),
    allowing safe reentrant acquisition while permitting cleanup and release
    from different worker threads without owner-thread release errors, while
    preventing concurrent copied-context workers from bypassing checkout serialization.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._owner_id = None
        self._owner_actor = None
        self._count = 0

    def acquire(self, blocking=True):
        token = _lock_token_cv.get()
        actor = _current_actor()

        with self._cond:
            if self._count > 0:
                is_same_actor = (self._owner_actor == actor)
                is_same_owner = (token is not None and self._owner_id == token)
                if is_same_actor and is_same_owner:
                    self._count += 1
                    return True

            if not blocking:
                if self._count > 0:
                    return False
            else:
                while self._count > 0:
                    self._cond.wait()

            new_token = token or f"ctx-{uuid.uuid4().hex}"
            _lock_token_cv.set(new_token)
            try:
                held = _held_locks_cv.get()
                _held_locks_cv.set(held | {id(self)})
            except Exception:
                pass

            self._owner_id = new_token
            self._owner_actor = actor
            self._count = 1
            return True

    def release(self):
        with self._cond:
            if self._count == 0:
                raise RuntimeError("cannot release un-acquired lock")
            self._count -= 1
            if self._count == 0:
                self._owner_id = None
                self._owner_actor = None
                try:
                    held = _held_locks_cv.get()
                    new_held = held - {id(self)}
                    _held_locks_cv.set(new_held)
                    if not new_held:
                        _lock_token_cv.set(None)
                except Exception:
                    pass
                self._cond.notify()

    def is_locked(self) -> bool:
        with self._cond:
            return self._count > 0

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


from sqlalchemy.pool import StaticPool


class SynchronizedStaticPool(StaticPool):
    """StaticPool with serialized connection checkout to protect SQLite in-memory transactions."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mutex = ReentrantCrossThreadLock()

    def _do_get(self):
        self._mutex.acquire()
        try:
            return super()._do_get()
        except Exception:
            self._mutex.release()
            raise

    def _do_return_conn(self, record):
        super()._do_return_conn(record)
        while self._mutex.is_locked():
            self._mutex.release()

def _create_engine():
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        path_part = ""
        if db_url.startswith("sqlite:///"):
            path_part = db_url[len("sqlite:///"):]
        elif db_url.startswith("sqlite://"):
            path_part = db_url[len("sqlite://"):]

        is_memory = (not path_part or path_part == ":memory:")
        if not is_memory:
            if not os.path.isabs(path_part):
                abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", path_part))
                db_url = f"sqlite:///{abs_path}"

        engine_kwargs = {"connect_args": {"check_same_thread": False}}
        if is_memory:
            engine_kwargs["poolclass"] = SynchronizedStaticPool
        return create_engine(
            db_url,
            **engine_kwargs
        )
    
    # Fallback if PostgreSQL is configured
    try:
        eng = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"connect_timeout": 1},
        )
        with eng.connect() as probe_conn:
            probe_conn.execute(text("SELECT 1"))
        return eng
    except Exception as e:
        is_local_dev = settings.ENVIRONMENT in ("development", "local", "test")
        if not is_local_dev:
            logger.error(f"PostgreSQL connection failed in {settings.ENVIRONMENT} deployment: {e}")
            raise
        logger.warning(f"PostgreSQL init failed ({e}). Falling back to local SQLite in {settings.ENVIRONMENT} mode.")
        sqlite_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "trek.db"))
        return create_engine(
            f"sqlite:///{sqlite_path}",
            connect_args={"check_same_thread": False},
        )

engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


_db_lock = ReentrantCrossThreadLock()


def get_db() -> Generator[Session, None, None]:
    with _db_lock:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def check_db_health() -> bool:
    try:
        with _db_lock:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False
