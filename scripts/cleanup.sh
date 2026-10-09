#!/usr/bin/env bash
# cleanup.sh - remove old backups, old logs and unused docker data
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DAYS="${DAYS:-7}"

echo "== Removing backups older than $DAYS days =="
find "$ROOT/backups" -name 'nexvion-backup-*.tar.gz' -mtime +"$DAYS" -print -delete 2>/dev/null

echo "== Removing logs older than $DAYS days =="
find "$ROOT/logs" -type f -mtime +"$DAYS" -print -delete 2>/dev/null

if command -v docker >/dev/null 2>&1; then
  echo "== Docker cleanup =="
  docker image prune -f
  docker container prune -f
fi
echo "Cleanup done."
