"""
Python backup helper script for NFR-09.
Can be invoked locally or within containers to generate a pg_dump archive.
"""
import os
import sys
import datetime
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


def run_backup(
    output_dir: str = "backups",
    retention_days: int = 7,
    db_url: str = None
) -> Path:
    """
    NFR-09: Generates a compressed pg_dump archive of the database.
    """
    db_url = db_url or settings.DATABASE_URL
    parsed = urlparse(db_url)

    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    user = parsed.username or "postgres"
    password = parsed.password or "postgres"
    dbname = parsed.path.lstrip("/") or "learning_recommender"

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = out_path / f"backup_{dbname}_{timestamp}.dump"

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    cmd = [
        "pg_dump",
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", dbname,
        "-Fc",
        "-Z", "9",
        "-f", str(backup_file),
    ]

    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Running pg_dump for {dbname} -> {backup_file}")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"pg_dump failed with exit code {res.returncode}: {res.stderr}")

    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] Backup successfully created at {backup_file}")

    # Retention prune
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
    for p in out_path.glob(f"backup_{dbname}_*.dump"):
        if datetime.datetime.fromtimestamp(p.stat().st_mtime, tz=datetime.timezone.utc) < cutoff:
            print(f"Pruning expired backup: {p.name}")
            p.unlink(missing_ok=True)

    return backup_file


if __name__ == "__main__":
    out = os.environ.get("BACKUP_DIR", "backups")
    days = int(os.environ.get("RETENTION_DAYS", "7"))
    try:
        run_backup(output_dir=out, retention_days=days)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
