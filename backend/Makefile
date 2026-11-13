.PHONY: run worker seed seed-docker seed-dataset seed-dataset-dry seed-dataset-check seed-dataset-docker db-current db-upgrade db-revision db-downgrade db-upgrade-docker test lint clean
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	python -m app.worker.worker

# Use module invocation so migrations do not rely on the alembic script being on PATH.
db-current:
	python -m alembic current

db-upgrade:
	python -m alembic upgrade head

db-revision:
	python -m alembic revision --autogenerate -m "$(message)"

db-downgrade:
	python -m alembic downgrade -1

db-upgrade-docker:
	docker compose run --rm api python -m alembic upgrade head

seed:
	python -m app.db.seed --seed 42 --learners 1000 --clean

seed-docker:
	docker compose --profile seed run --rm seed

seed-dataset-check:
	python -m app.db.seed_dataset --data-dir "../demo data" --dry-run --check-ground-truth

seed-dataset-dry:
	python -m app.db.seed_dataset --data-dir "../demo data" --dry-run

seed-dataset:
	python -m app.db.seed_dataset --data-dir "../demo data" --clean

seed-dataset-docker:
	docker compose --profile seed run --rm --build seed-dataset

test:
	python -m pytest -v

test-cov:
	python -m pytest --cov=app/modules --cov-report=term-missing --cov-fail-under=70

load-test:
	python -m tests.load.run_load_test --users 1000 --spawn-rate 50 --run-time 30s

load-test-web:
	locust -f tests/load/locustfile.py --host http://localhost:8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
