#!/bin/bash
#
# test_parallel_runs.sh - acceptance test for per-run directories.
#
# Launches TWO quickstart runs concurrently from THIS checkout and asserts
# they do not interfere: distinct run dirs, both complete with summary.txt,
# both pass the quickstart smoke baseline, check_sim.sh addresses each one
# while both are live, and nothing new appears at the checkout root.
#
# Wall time: two 6h-sim quickstarts side by side, 30-90 min depending on
# box load. Runs are nice'd. Logs: /tmp/monerosim_partest_<pid>_{a,b}.log
#
# Usage: ./scripts/test_parallel_runs.sh [CONFIG]   (default test_configs/quickstart.yaml)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source scripts/log_lib.sh
source scripts/run_dir_lib.sh

CONFIG="${1:-test_configs/quickstart.yaml}"
STAMP=$(date +%H%M%S)
NAME_A="par_a_$STAMP"
NAME_B="par_b_$STAMP"
LOG_A="/tmp/monerosim_partest_$$_a.log"
LOG_B="/tmp/monerosim_partest_$$_b.log"
fail() { log_err "$*"; exit 1; }

root_before=$(ls -A "$ROOT" | sort)

log_step "Build once (both runs use --no-build)"
cargo build --release --quiet

log_step "Launch two runs concurrently from $ROOT"
nice ./run_sim.sh --config "$CONFIG" --name "$NAME_A" --no-build --no-monitor > "$LOG_A" 2>&1 &
PID_A=$!
sleep 1
nice ./run_sim.sh --config "$CONFIG" --name "$NAME_B" --no-build --no-monitor > "$LOG_B" 2>&1 &
PID_B=$!
log_info "run_sim.sh pids: $PID_A $PID_B"

# "|| true": under pipefail, `ls` matching nothing makes the pipeline's exit
# status non-zero even though `tail -1` (last in the pipe) succeeds; without
# this, `RUN_A=$(find_run ...)` trips `set -e` and kills the script silently
# (no fail() message) on the very first loop check, before run_sim.sh has
# created the run dir.
find_run() { ls -d "$ROOT"/archived_runs/*_"$1" 2>/dev/null | tail -1 || true; }

log_step "Wait for both runs to have a populated shadow.data/hosts (max 20 min)"
deadline=$((SECONDS + 1200))
RUN_A=""; RUN_B=""
while (( SECONDS < deadline )); do
    RUN_A=$(find_run "$NAME_A"); RUN_B=$(find_run "$NAME_B")
    if [[ -n "$RUN_A" && -n "$RUN_B" && -d "$RUN_A/shadow.data/hosts" && -d "$RUN_B/shadow.data/hosts" ]]; then
        break
    fi
    kill -0 "$PID_A" 2>/dev/null || fail "run A died early; see $LOG_A"
    kill -0 "$PID_B" 2>/dev/null || fail "run B died early; see $LOG_B"
    sleep 10
done
[[ -d "$RUN_A/shadow.data/hosts" && -d "$RUN_B/shadow.data/hosts" ]] || fail "hosts dirs did not appear in time"
[[ "$RUN_A" != "$RUN_B" ]] || fail "both runs resolved to the same directory: $RUN_A"
log_ok "run A: $RUN_A"
log_ok "run B: $RUN_B"

log_step "check_sim.sh addresses each live run"
for R in "$RUN_A" "$RUN_B"; do
    [[ "$(run_dir_state "$R")" == "live" ]] || fail "$R is not live while its run_sim.sh runs"
    out=$(./scripts/check_sim.sh "$R" 2>&1) || fail "check_sim.sh failed for $R: $out"
    grep -q "run: $R (live)" <<< "$out" || fail "check_sim.sh did not announce $R as live"
done
log_ok "check_sim.sh OK on both live runs"

log_step "Wait for completion"
status=0
wait "$PID_A" || { log_err "run A exited non-zero (see $LOG_A)"; status=1; }
wait "$PID_B" || { log_err "run B exited non-zero (see $LOG_B)"; status=1; }
(( status == 0 )) || exit 1

log_step "Assertions"
for R in "$RUN_A" "$RUN_B"; do
    [[ -f "$R/summary.txt" ]] || fail "$R has no summary.txt"
    [[ "$(run_dir_state "$R")" == "complete" ]] || fail "$R is not complete"
    grep -q 'Exit code:      0' "$R/summary.txt" || fail "$R: Shadow exit code not 0"
    (( $(ls "$R/shadow.data/hosts" | wc -l) > 0 )) || fail "$R: empty shadow.data/hosts"
    [[ -f "$R/shadow_output/run_env.sh" ]] || fail "$R: no run_env.sh"
    grep -q "MONEROSIM_RUN_DIR=\"$(readlink -f "$R")\"" "$R/shadow_output/run_env.sh" || fail "$R: run_env.sh names another run"
    # $R's name is par_{a,b}_<stamp>, not <ts>_<scenario>, so
    # smoke_assertions.py's name-derived default baseline lookup would miss;
    # point it at the baseline for the config we actually ran instead.
    python3 scripts/smoke_assertions.py --run-dir "$R" --baseline "tests/baselines/$(basename "$CONFIG" .yaml)_metrics.json" || fail "$R: smoke assertions failed"
    log_ok "$R: complete, exit 0, smoke assertions pass"
done
root_after=$(ls -A "$ROOT" | sort)
if [[ "$root_before" != "$root_after" ]]; then
    diff <(echo "$root_before") <(echo "$root_after") || true
    fail "checkout root changed during the runs"
fi
log_ok "checkout root unchanged"
rm -f "$LOG_A" "$LOG_B"
log_ok "PARALLEL RUNS OK: $RUN_A and $RUN_B"
