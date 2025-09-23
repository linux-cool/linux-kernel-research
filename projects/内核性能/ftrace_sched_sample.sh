#!/usr/bin/env bash
# Minimal sched trace sample
set -euo pipefail
TR=/sys/kernel/tracing
sudo mount -t tracefs nodev "$TR" 2>/dev/null || true
cd "$TR"
echo 0 | sudo tee tracing_on >/dev/null
: | sudo tee trace >/dev/null
for e in sched_switch sched_wakeup sched_migrate_task; do echo 1 | sudo tee events/sched/$e/enable >/dev/null; done
( taskset -c 0 sh -c 'yes >/dev/null' & ); P=$!; sleep 1; kill $P 2>/dev/null || true
sudo tail -n 80 trace | sed -n '1,80p'
for e in sched_switch sched_wakeup sched_migrate_task; do echo 0 | sudo tee events/sched/$e/enable >/dev/null; done

