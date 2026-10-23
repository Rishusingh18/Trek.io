#!/bin/sh
set -e

# Tested database restore script adhering to NFR-09 (Disaster Recovery & Tested Restore)
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-learning_recommender}"

if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_backup_dump_file>"
    echo "Example: $0 /backups/backup_learning_recommender_20261023_000000.dump"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file '$BACKUP_FILE' not found."
    exit 1
fi

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Commencing restore drill for $POSTGRES_DB from $BACKUP_FILE..."
export PGPASSWORD="$POSTGRES_PASSWORD"

# Terminate active client connections to target DB to allow clean restore
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "postgres" -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();" || true

# Perform restore with clean flag
pg_restore -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges "$BACKUP_FILE"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Database restore completed successfully."
