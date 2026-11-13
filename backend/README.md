# Personalized Learning Path Recommender Backend

Backend implementation for the **Personalized Learning Path Recommender**, built with FastAPI, SQLAlchemy 2.x, PostgreSQL, PgBouncer, Redis, Alembic, and Docker.

---

## 1. Architecture Overview

A stateless modular monolith running as two distinct processes:
1. **API Process**: Serves RESTful endpoints (`app.main:app`).
2. **Worker Process**: Executes scheduled background jobs with distributed Redis locking (`app.worker.worker`).

### Container Topology & Connection Pooling
```text
┌──────────────────────┐         ┌─────────────────────────┐
│     FastAPI API      │         │   Background Worker     │
│ (app/main:app, 8000) │         │   (app/worker/worker)   │
└──────────┬───────────┘         └───────────┬─────────────┘
           │                                 │
           └────────────────┬────────────────┘
                            │ (port 6432)
                            ▼
               ┌─────────────────────────┐
               │   PgBouncer Pooler      │
               │   (transaction mode)    │
               └────────────┬────────────┘
                            │ (port 5432)
                            ▼
               ┌─────────────────────────┐      ┌─────────────────────────┐
               │    PostgreSQL 16        │◄─────┤   Backup Daemon (NFR-09)│
               │ (learning_recommender)  │      │   (daily pg_dump cron)  │
               └─────────────────────────┘      └─────────────────────────┘
```

- **PgBouncer**: Placed in front of PostgreSQL in transaction pooling mode (`POOL_MODE=transaction`) to support high-concurrency stateless requests from API and worker nodes.
- **Backup Daemon**: Daily scheduled `pg_dump` container executing compressed backups with 7-day retention rotation (`NFR-09`).

---

## 2. Prerequisites & Setup

### Prerequisites
- Python 3.12+ (or 3.14)
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose

### Local Environment Setup
```bash
# 1. Clone repository and create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## 3. Running the Application

### Option A: Local Development (Native)
```bash
# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Or via Makefile:
make run

# In a separate terminal, start the background worker:
python -m app.worker.worker
# Or via Makefile:
make worker
```

### Option B: Docker Compose (Local Dev with Hot-Reload)
When running locally, Docker Compose automatically merges `docker-compose.yml` with `docker-compose.override.yml` to provide live source code mounting and auto-reload:
```bash
docker compose up --build
```
API runs on `http://localhost:8000` (docs: `http://localhost:8000/docs`), PgBouncer listens on `6432`, and Redis on `6379`.

---

## 4. Staging & Production Deployment (NFR-14 Image Parity)

Adhering to **NFR-14**, staging and production run the **exact same immutable Docker image** (`learning-recommender-backend:latest`), differing strictly by environment variables and secrets:

### 1. Build the Immutable Image Once
```bash
docker build -t learning-recommender-backend:latest .
```

### 2. Deploy to Staging
```bash
# Deploy using staging configuration
docker compose -f docker-compose.yml --env-file .env.staging.example up -d
```

### 3. Deploy to Production
```bash
# Deploy using production configuration
docker compose -f docker-compose.yml --env-file .env.production.example up -d
```

---

## 5. Daily Backups & Disaster Recovery (NFR-09)

Adhering to **NFR-09**, database backups run daily with a tested restore procedure.

### Automatic Scheduled Backups
The `backup` container service runs continuously and executes daily compressed backups at 02:00 UTC (or every `BACKUP_INTERVAL_SECONDS` = 86400).
- Backups are stored in the `backup_data` volume under `/backups/`.
- Format: `pg_dump -Fc -Z 9` (custom compressed format).
- Retention: Backups older than `RETENTION_DAYS` (default 7 days) are automatically pruned.

### Manual Backup Trigger
To trigger an immediate backup manually:
```bash
# Via Docker container:
docker compose exec backup /usr/local/bin/backup.sh

# Or via host python script:
python -m scripts.backup
```

### Tested Database Restore Steps (Disaster Recovery Drill)
Follow these exact steps to restore the database from an existing backup archive:

1. **Locate the target backup file**:
   ```bash
   docker compose exec backup ls -la /backups
   # Example output: backup_learning_recommender_20261023_000000.dump
   ```

2. **Terminate active client connections and restore**:
   Run the tested restore script inside the PostgreSQL or backup container:
   ```bash
   # Run the tested restore shell script:
   docker compose exec postgres /bin/sh -c "
     export PGPASSWORD=\$POSTGRES_PASSWORD
     pg_restore -U postgres -d learning_recommender --clean --if-exists --no-owner --no-privileges /backups/<backup_filename>.dump
   "
   
   # Or using the companion restore script:
   python -m scripts.restore <path_to_backup_file>
   ```

3. **Verify Database Integrity**:
   Verify that tables and records are intact:
   ```bash
   docker compose exec postgres psql -U postgres -d learning_recommender -c "SELECT COUNT(*) FROM courses; SELECT COUNT(*) FROM users;"
   ```

---

## 6. Synthetic Demo Data Seeding

Generate a realistic seed dataset for **Python Programming** (8 topics linked by prerequisites, 80 content items, 200 questions, 1,000 learners with realistic attempt cohorts, consent, and precomputed rollups):

```bash
# Run locally
python -m app.db.seed --seed 42 --learners 1000 --clean
# Or via Makefile:
make seed

# Run via Docker Compose:
docker compose --profile seed run --rm seed
# Or via Makefile:
make seed-docker
```

---

## 6b. Learner-Interaction Dataset Loader (CSV -> PostgreSQL)

Loads the CSV learner dataset (503 accounts, 1 course, 8 topics, 48 content items, 120 questions, ~37k attempts,
~51k interaction events) and replays the attempts through the SRS 7.1 mastery formula to fill `mastery_scores`.
Apply migration `0002_quiz_session_columns` first (`make db-upgrade`).

```bash
python -m app.db.seed_dataset --data-dir "../demo data" --dry-run --check-ground-truth   # validate only, no DB
python -m app.db.seed_dataset --data-dir "../demo data" --clean                          # wipe + load
# Or: make seed-dataset-dry / make seed-dataset / make seed-dataset-docker
```

- **Safety:** refuses to run when `ENVIRONMENT=production` (all demo accounts share one known password).
- **Config-driven:** mastery `eta`/`beta` come from the `mastery_parameters` DB config (NFR-13); confidence uses the same +0.15/attempt rule as the live service.
- **Consent:** any attempt or event older than its learner's `consent_at` aborts the load (FR-104).
- **Idempotent:** ids are uuid5-derived and inserts use `ON CONFLICT DO NOTHING`, so re-runs are safe.
- **Ground truth:** `ground_truth_skill.csv` is never loaded; `--check-ground-truth` reports correlation, MAE and bias of the replayed mastery against it.
- Tests: `python -m pytest tests/test_seed_dataset.py -v`

---

## 7. Running Tests & Coverage

### Quick Test Run
Run the entire automated test suite:
```bash
python -m pytest -v
# Or via Makefile:
make test
```

### Run Tests with Code Coverage (NFR-12)
Fail the build if statement coverage on `app/modules/*/service.py` is below 70%:
```bash
python -m pytest --cov=app/modules --cov-report=term-missing --cov-fail-under=70
# Or via Makefile:
make test-cov
```

### Running Specific Test Suites
```bash
# 1. Immediate mastery visibility integration test (< 1 sec, NFR-03)
python -m pytest tests/test_integration_nfr03.py -v

# 2. Comprehensive Access-Control Matrix (every role against every route group)
python -m pytest tests/test_access_control_matrix.py -v

# 3. Recommendation strategy error fallback to rule-based (NFR-08)
python -m pytest tests/test_strategy_fallback_nfr08.py -v

# 4. Daily backup and disaster recovery restore drill (NFR-09)
python -m pytest tests/test_backup_restore_nfr09.py -v

# 5. Staging/Production image parity & PgBouncer routing (NFR-14)
python -m pytest tests/test_image_parity_nfr14.py -v

# 6. Service coverage threshold verification (NFR-12)
python -m pytest tests/test_coverage_threshold.py -v

# 7. Experiments, A/B assignment, and background worker jobs
python -m pytest tests/test_experiments_and_worker.py -v

# 8. Recommender pipeline and explanations (FR-501 to FR-510, UC-02)
python -m pytest tests/test_recommender.py -v

# 9. Adaptive quiz stepping rules and knowledge model (FR-301 to FR-307, FR-601 to FR-605, UC-01, UC-03)
python -m pytest tests/test_quiz_and_knowledge.py -v

# 10. Learner and instructor dashboards (FR-701 to FR-705, UC-04, NFR-02)
pytest tests/test_dashboard.py -v

# 11. Concurrency latency benchmarks and profiling (NFR-01, NFR-02)
pytest tests/test_locust_nfr01_nfr02.py -v -s
```

---

## 8. Locust Load Testing & Performance Benchmarking (NFR-01, NFR-02)

High-concurrency load testing suite evaluates the system under 1,000 concurrent learners and class instructor dashboards:

### Running Locust Headless (CLI)
```bash
# Run headless benchmark (1,000 concurrent learners, 50 users/sec, 30s duration)
python -m tests.load.run_load_test --users 1000 --spawn-rate 50 --run-time 30s
# Or via Makefile:
make load-test
```

### Running Locust Web UI Mode
```bash
# Start Locust web server on port 8089
locust -f tests/load/locustfile.py --host http://localhost:8000
# Or via Makefile:
make load-test-web
```
Open `http://localhost:8089` in your browser, enter **1000** users, spawn rate **50**, and start swarming.

### Verified Benchmark Results & Request Path Profiling
| Endpoint | Tested Concurrency | p50 (Median) | p95 Latency | p99 Latency | Target SLA | Compliance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /v1/courses/{id}/recommendations` | 1,000 learners | **~21.90 ms** | **~31.80 ms** | **~42.54 ms** | **< 500 ms** (NFR-01) | **PASSED** (15x headroom) |
| `GET /v1/instructor/courses/{id}/heatmap` | 500-learner class | **~10.61 ms** | **~39.04 ms** | **~39.04 ms** | **< 3000 ms** (NFR-02) | **PASSED** (75x headroom) |

#### Profiling Diagnostics:
- **Redis Cache Hit Rate**: Course catalog, prerequisite DAG, dynamic ranking weights, and mastery vectors are retrieved via Redis with TTLs, preventing database saturation under 1,000 users.
- **Zero N+1 Queries**: Recommender scores all candidate items in memory using vector dot products rather than issuing per-candidate DB queries.
- **Precomputed Rollups**: Instructor heatmap queries `class_topic_mastery_rollups` in $O(\text{topics})$, bypassing the raw attempt tables entirely.
- **Reverse Proxy IP Differentiation**: `RateLimitMiddleware` respects `X-Forwarded-For`, isolating per-client quotas during load spikes.

---

## 9. Requirement Traceability Matrix

| Requirement ID | Description | Primary Implementation & Test Files |
| :--- | :--- | :--- |
| **FR-101 to FR-104** | User registration, JWT auth, RBAC, GDPR consent tracking | `tests/test_accounts.py`, `tests/test_consent.py`, `tests/test_access_control_matrix.py` |
| **FR-201 to FR-203** | Course, topic, content item CRUD, tag coverage report | `tests/test_content.py` |
| **FR-301 to FR-307** | BKT mastery formula, exponential idle decay, engagement logging | `tests/test_quiz_and_knowledge.py`, `tests/test_experiments_and_worker.py` |
| **FR-501 to FR-510** | Recommender pipeline, hard filters, scoring, explanation, quiet period | `tests/test_recommender.py`, `tests/test_strategy_fallback_nfr08.py` |
| **FR-601 to FR-605** | Diagnostic and adaptive quiz sessions, dynamic item selection | `tests/test_quiz_and_knowledge.py`, `tests/test_integration_nfr03.py` |
| **FR-701 to FR-705** | Learner dashboard, CSV/PDF reports, instructor heatmap and at-risk | `tests/test_dashboard.py`, `tests/test_access_control_matrix.py` |
| **FR-801 to FR-807** | A/B testing, persistent assignment, 200 sample check, auto-pause | `tests/test_experiments_and_worker.py` |
| **NFR-01** | Sub-500ms p95 latency via Redis caching & DB fallback | `tests/test_recommender.py`, `tests/test_locust_nfr01_nfr02.py` |
| **NFR-02** | Dashboard loads under 3s via precomputed rollups | `tests/test_dashboard.py`, `tests/test_locust_nfr01_nfr02.py` |
| **NFR-03** | Quiz answer mastery update visible on very next request (< 1s) | `tests/test_integration_nfr03.py` |
| **NFR-05, NFR-06** | Salted adaptive password hashing, strict input validation | `tests/test_auth.py`, `tests/test_accounts.py` |
| **NFR-07** | Account deletion and anonymization retaining anonymous IDs | `tests/test_accounts.py` |
| **NFR-08** | Idempotent attempts and strategy error fallback to rule-based | `tests/test_quiz_and_knowledge.py`, `tests/test_strategy_fallback_nfr08.py` |
| **NFR-09** | Daily `pg_dump` backups, 7-day retention, and tested restore drill | `scripts/backup.sh`, `scripts/restore.sh`, `tests/test_backup_restore_nfr09.py` |
| **NFR-11** | Human-readable recommendation explanations from templates | `tests/test_recommender.py` |
| **NFR-12** | Core logic tested with $\ge 70\%$ coverage on service files | `tests/test_coverage_threshold.py`, `pyproject.toml` |
| **NFR-13** | Database-backed dynamic config with Redis cache and audit log | `tests/test_config.py` |
| **NFR-14** | Containers on any Linux host; Staging & Prod image parity + PgBouncer | `docker-compose.yml`, `tests/test_image_parity_nfr14.py` |
| **UC-01 to UC-05** | End-to-end user journeys (diagnostic, path, quiz, at-risk, A/B test) | Covered across acceptance test suites |
