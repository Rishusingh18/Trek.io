"""
Worker process (Architecture doc & SRS section 5.3, FR-305, FR-307, FR-804 to FR-806).
Runs scheduled jobs using distributed Redis locks to ensure single execution per job type:
- Mastery decay for idle topics (FR-305)
- Rollup computation for dashboard and metrics (NFR-02, FR-702, FR-804)
- Experiment metrics and guardrails auto-pause (FR-805, FR-806)
- Partition retention aggregation (SRS 5.3)
- Embedding refresh stub (FR-507)
"""
import time
import sys
from app.core.logging import logger, setup_logging
from app.db.session import SessionLocal
from app.worker.locks import WorkerLock
from app.worker.jobs import (
    run_mastery_decay_job,
    run_rollup_job,
    run_experiment_metrics_job,
    run_guardrails_check,
    run_retention_job,
    run_embedding_refresh_job,
)


def execute_job(job_name: str, job_func, ttl_seconds: int = 120) -> None:
    """Execute a worker job wrapped in a distributed Redis lock."""
    lock = WorkerLock(job_name=job_name, ttl_seconds=ttl_seconds)
    if not lock.acquire():
        logger.info(f"Job '{job_name}' currently claimed by another worker. Skipping this cycle.")
        return

    try:
        db = SessionLocal()
        try:
            job_func(db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error executing job '{job_name}': {e}", exc_info=True)
    finally:
        lock.release()


def run_worker_cycle() -> None:
    """Run one complete cycle of scheduled background jobs."""
    execute_job("decay", run_mastery_decay_job)
    execute_job("rollups", run_rollup_job)
    execute_job("experiment_metrics", run_experiment_metrics_job)
    execute_job("guardrails", run_guardrails_check)
    execute_job("retention", run_retention_job)
    execute_job("embedding_refresh", run_embedding_refresh_job)


def main() -> None:
    setup_logging()
    logger.info("Personalized Learning Path Recommender Worker started.")
    try:
        while True:
            run_worker_cycle()
            time.sleep(60)  # Periodic execution interval
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
