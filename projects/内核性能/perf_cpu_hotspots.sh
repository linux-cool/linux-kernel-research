#!/usr/bin/env bash
# System-wide CPU hotspots quick look
set -euo pipefail
sec=${1:-3}
if ! command -v perf >/dev/null 2>&1; then
  echo "perf not installed." >&2
  exit 2
fi
sudo perf stat -a -- sleep "$sec"
sudo perf record -a -g -- sleep "$sec"
sudo perf report --stdio | head -n 60

