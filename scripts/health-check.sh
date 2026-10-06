#!/usr/bin/env bash
set -euo pipefail
URL="${1:-http://localhost:8081/health}"
for i in {1..10}; do
  if curl -fs "$URL" >/dev/null; then
    echo "Healthy: $URL"; exit 0
  fi
  echo "Attempt $i failed, retrying..."; sleep 3
done
echo "Unhealthy: $URL"; exit 1