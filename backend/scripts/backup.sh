#!/bin/sh
set -e

# Daily pg_dump backup script adhering to NFR-09 (Reliability & Disaster Recovery)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-learning_recommender}"

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/backup_${POSTGRES_DB}_${TIMESTAMP}.dump"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting database backup for $POSTGRES_DB at $POSTGRES_HOST:$POSTGRES_PORT..."

export PGPASSWORD="$POSTGRES_PASSWORD"

pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -Z 9 -f "$BACKUP_FILE"

FILESIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Backup successfully created: $BACKUP_FILE ($FILESIZE)"

# Prune older backups
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "backup_${POSTGRES_DB}_*.dump" -type f -mtime +$RETENTION_DAYS -delete
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Backup rotation complete."
