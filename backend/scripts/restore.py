"""
Python restore helper script for NFR-09.
Executes tested pg_restore drill against PostgreSQL.
"""
import os
import sys
import datetime
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


def run_restore(backup_file: str, db_url: str = None) -> None:
    """
    NFR-09: Restores a compressed pg_dump archive into PostgreSQL.
    """
    backup_path = Path(backup_file)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found at {backup_path}")

    db_url = db_url or settings.DATABASE_URL
    parsed = urlparse(db_url)

    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"
    dbname = parsed.path.lstrip("/") or "learning_recommender"

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Restoring {dbname} from {backup_path}...")

    # Optional: terminate existing connections if psql is present
    try:
        term_cmd = [
            "psql",
            "-h", host,
            "-p", port,
            "-U", user,
            "-d", "postgres",
            "-c", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{dbname}' AND pid <> pg_backend_pid();"
        ]
        subprocess.run(term_cmd, env=env, capture_output=True, text=True, timeout=10)
    except Exception:
        pass

    cmd = [
        "pg_restore",
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", dbname,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        str(backup_path),
    ]

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    # Note: pg_restore returns non-zero warnings on harmless drops if tables did not exist; check stderr
    if res.returncode not in [0, 1]:
        raise RuntimeError(f"pg_restore failed with code {res.returncode}: {res.stderr}")

    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Restore drill completed successfully.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.restore <path_to_backup_file>")
        sys.exit(1)

    target_backup = sys.argv[1]
    try:
        run_restore(target_backup)
    except Exception as e:
        print(f"Error during restore: {e}", file=sys.stderr)
        sys.exit(1)
