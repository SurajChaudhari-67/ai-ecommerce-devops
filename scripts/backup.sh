#!/usr/bin/env bash
# backup.sh - archive project sources (state files and secrets are excluded)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP="${KEEP:-5}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/nexvion-backup-$STAMP.tar.gz"

mkdir -p "$BACKUP_DIR"
cd "$ROOT"
tar czf "$FILE" \
  --exclude='*.tfstate*' --exclude='*.tfvars' --exclude='.terraform' \
  --exclude='backups' --exclude='.git' \
  application docker helm kubernetes terraform ansible monitoring logging jenkins scripts ai

echo "Backup created: $FILE ($(du -h "$FILE" | cut -f1))"

# keep only the newest $KEEP backups
ls -1t "$BACKUP_DIR"/nexvion-backup-*.tar.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "Backups kept: $(ls -1 "$BACKUP_DIR"/nexvion-backup-*.tar.gz | wc -l)"
