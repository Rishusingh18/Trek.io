"""
Tests for Environment & Image Parity adhering to NFR-14.
Requirement NFR-14:
"The system shall run in containers on any Linux host (Portability).
Staging and production use the same images, differing only in environment
variables and secrets."
"""
from pathlib import Path
import yaml


def test_nfr14_docker_compose_image_parity_and_pgbouncer():
    """
    NFR-14: Verifies that docker-compose.yml uses parameterized images and
    connects services through the PgBouncer connection pooler.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    compose_file = Path("docker-compose.yml") if Path("docker-compose.yml").exists() else backend_dir / "docker-compose.yml"
    assert compose_file.exists(), "docker-compose.yml must exist"

    with open(compose_file, "r") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})

    # 1. Verify PgBouncer service is present
    assert "pgbouncer" in services, "PgBouncer service must be present in docker-compose"
    pgbouncer = services["pgbouncer"]
    assert pgbouncer.get("environment", {}).get("POOL_MODE") == "${PGBOUNCER_POOL_MODE:-transaction}"

    # 2. Verify API and Worker use the exact same image specification
    api_service = services.get("api", {})
    worker_service = services.get("worker", {})

    assert api_service.get("image") == worker_service.get("image")
    assert "${BACKEND_IMAGE:-learning-recommender-backend:latest}" in api_service.get("image", "")

    # 3. Verify services connect via pgbouncer port 6432
    api_env = api_service.get("environment", [])
    worker_env = worker_service.get("environment", [])

    api_db_env = next((e for e in api_env if "DATABASE_URL" in e), "")
    worker_db_env = next((e for e in worker_env if "DATABASE_URL" in e), "")

    assert "@pgbouncer:6432/" in api_db_env, "API must route queries through PgBouncer"
    assert "@pgbouncer:6432/" in worker_db_env, "Worker must route queries through PgBouncer"

    # 4. Verify Backup service is defined for NFR-09
    assert "backup" in services, "Backup service must be defined in docker-compose"


def test_nfr14_environment_example_parity():
    """
    NFR-14: Verifies that staging and production environment templates are provided,
    differing only in environment-specific configurations and credentials.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    staging_env = Path(".env.staging.example") if Path(".env.staging.example").exists() else backend_dir / ".env.staging.example"
    prod_env = Path(".env.production.example") if Path(".env.production.example").exists() else backend_dir / ".env.production.example"

    assert staging_env.exists(), ".env.staging.example must exist"
    assert prod_env.exists(), ".env.production.example must exist"

    staging_text = staging_env.read_text()
    prod_text = prod_env.read_text()

    assert "ENVIRONMENT=staging" in staging_text
    assert "ENVIRONMENT=production" in prod_text

    # Both must configure PgBouncer
    assert "PGBOUNCER_PORT=6432" in staging_text
    assert "PGBOUNCER_PORT=6432" in prod_text
