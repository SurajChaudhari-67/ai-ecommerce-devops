#!/usr/bin/env bash
# setup.sh - check required tools and prepare working directories
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Tool check =="
missing=0
for tool in git docker kubectl az helm terraform; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  [OK]      $tool"
  else
    echo "  [MISSING] $tool"
    missing=1
  fi
done

echo "== System check =="
echo "  OS      : $(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '\"')"
echo "  Disk    : $(df -h "$ROOT" | awk 'NR==2 {print $4 " free"}')"
echo "  Memory  : $(free -m | awk '/Mem:/ {print $7 " MB available"}')"

echo "== Directories =="
mkdir -p "$ROOT/backups" "$ROOT/logs"
echo "  created: backups/ logs/"

if [ "$missing" -eq 1 ]; then
  echo "Some tools are missing. Install them before running the pipeline."
  exit 1
fi
echo "Setup check passed."
