"""
Tests for session synchronization and ReentrantCrossThreadLock context ownership.
"""
from app.db.session import ReentrantCrossThreadLock, _lock_token_cv


def test_lock_release_preserves_context_ownership():
    """
    Regression test: acquiring locks A and B, releasing B, verifying A can still
    be reacquired non-blockingly, and cleaning up both locks.
    """
    lock_a = ReentrantCrossThreadLock()
    lock_b = ReentrantCrossThreadLock()

    # Acquire locks A and B in the same context
    assert lock_a.acquire(blocking=False) is True
    assert lock_b.acquire(blocking=False) is True

    # Release lock B
    lock_b.release()
    assert not lock_b.is_locked()

    # Verify A can still be reacquired non-blockingly
    assert lock_a.acquire(blocking=False) is True
    assert lock_a._count == 2

    # Clean up both locks
    lock_a.release()
    lock_a.release()
    assert not lock_a.is_locked()
    assert _lock_token_cv.get() is None


def test_independent_contexts_cannot_both_acquire():
    """
    Regression test: two independent contexts on one thread cannot both acquire the lock.
    """
    import contextvars

    lock = ReentrantCrossThreadLock()
    ctx1 = contextvars.Context()
    ctx2 = contextvars.Context()

    # Context 1 acquires the lock
    assert ctx1.run(lock.acquire, False) is True

    # Legitimate reentry within Context 1 succeeds
    assert ctx1.run(lock.acquire, False) is True
    ctx1.run(lock.release)

    # Independent Context 2 on the same thread cannot acquire non-blockingly while Context 1 holds it
    assert ctx2.run(lock.acquire, False) is False

    # Cleanup Context 1
    ctx1.run(lock.release)
    assert not lock.is_locked()

    # Now Context 2 can acquire
    assert ctx2.run(lock.acquire, False) is True
    ctx2.run(lock.release)
    assert not lock.is_locked()
