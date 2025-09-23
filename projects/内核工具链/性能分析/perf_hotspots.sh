#!/usr/bin/env bash
# Perf hotspots quick look. Usage: bash perf_hotspots.sh [seconds]
set -euo pipefail
sec=${1:-3}
if ! command -v perf >/dev/null 2>&1; then
  echo "perf not installed; consider using vmstat/tracefs as alternatives." >&2
  exit 2
fi
sudo perf stat -a -- sleep "$sec" | sed -n '1,80p'
sudo perf record -a -g -- sleep "$sec"
sudo perf report --stdio | head -n 60

