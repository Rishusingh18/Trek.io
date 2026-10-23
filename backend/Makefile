.PHONY: run worker seed seed-docker test lint clean

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	python -m app.worker.worker

seed:
	python -m app.db.seed --seed 42 --learners 1000 --clean

seed-docker:
	docker compose --profile seed run --rm seed

test:
	pytest -v

test-cov:
	pytest --cov=app/modules --cov-report=term-missing --cov-fail-under=70

load-test:
	python -m tests.load.run_load_test --users 1000 --spawn-rate 50 --run-time 30s

load-test-web:
	locust -f tests/load/locustfile.py --host http://localhost:8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
