#!/usr/bin/env bash
# Quickstart for ftrace via tracefs: function_graph sample + sched events.
set -euo pipefail
TRACING=/sys/kernel/tracing
sudo mount -t tracefs nodev "$TRACING" 2>/dev/null || true
cd "$TRACING"
# Clean
echo 0 | sudo tee tracing_on >/dev/null
: | sudo tee trace >/dev/null
# function_graph 1s
echo function_graph | sudo tee current_tracer >/dev/null
(echo 1 | sudo tee tracing_on >/dev/null; sleep 1; echo 0 | sudo tee tracing_on >/dev/null)
sudo tail -n 30 trace || true
# sched events minimal sample
for e in sched_switch sched_wakeup; do echo 1 | sudo tee events/sched/$e/enable >/dev/null; done
( taskset -c 0 sh -c 'yes >/dev/null' & ); P=$!; sleep 1; kill $P 2>/dev/null || true
sudo tail -n 40 trace || true
# Cleanup: disable sched events
for e in sched_switch sched_wakeup; do echo 0 | sudo tee events/sched/$e/enable >/dev/null; done

