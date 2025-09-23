#!/usr/bin/env bash
# Watch PSI (Pressure Stall Information) for cpu/io/memory for N seconds
set -euo pipefail
sec=${1:-10}
for t in cpu io memory; do
  f="/proc/pressure/$t"; echo "=== $t ==="; if [[ -f $f ]]; then
    ( for i in $(seq 1 "$sec"); do date +%T; cat "$f"; sleep 1; done )
  else
    echo "not available"
  fi
done

