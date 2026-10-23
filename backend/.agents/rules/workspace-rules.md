# Personalized Learning Path Recommender - Workspace Rules

You are helping build the backend of a Personalized Learning Path Recommender.
Read everything in docs/ (PRD, SRS, Architecture) before doing anything.

## Tech Stack
- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Docker

## Architecture Rules
- One stateless modular monolith, run as two processes: API and worker.
- Folder layout:
  - `app/main.py`
  - `app/core/`
  - `app/modules/<name>/` with `router.py`, `service.py`, `repository.py`, `schemas.py`
  - `app/worker/`
  - `app/db/`
- Modules: `accounts`, `content`, `knowledge`, `quiz`, `recommender`, `experiments`.
- Modules call each other ONLY through `service.py`. Only `repository.py` touches the module's own tables. No module writes another module's tables.
- Routers are thin: validate input, call one service function, shape the response.
- Follow the requirement IDs (`FR-xxx`, `NFR-xxx`) from the SRS and mention them in code comments and test names.
- Redis rule: every key has an expiry, and every read falls back to PostgreSQL on a miss. Redis must hold nothing that cannot be rebuilt from PostgreSQL.
- Configuration (weights, thresholds, learning rate, decay, strategy flags) lives in the database, is cached in Redis, and is never hardcoded.
- Always propose a plan first and wait for my approval before writing code.
- Always write tests and tell me how to run them.
