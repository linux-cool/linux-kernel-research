#!/usr/bin/env bash
# Compare context switch and runqueue when pinning 2 loops to 1 CPU vs 2 CPUs.
set -euo pipefail
sample_vmstat() { vmstat 1 3 | tail -n 1; }
# Case A: both on CPU0
( taskset -c 0 sh -c 'yes >/dev/null' & ); A1=$!
( taskset -c 0 sh -c 'yes >/dev/null' & ); A2=$!
echo "Case A (1 CPU, 2 procs):"; sample_vmstat
kill $A1 $A2 2>/dev/null || true; sleep 1
# Case B: one on CPU0, one on CPU1 (if available)
( taskset -c 0 sh -c 'yes >/dev/null' & ); B1=$!
( taskset -c 1 sh -c 'yes >/dev/null' & ); B2=$!
echo "Case B (2 CPUs, 1 proc each):"; sample_vmstat
kill $B1 $B2 2>/dev/null || true

