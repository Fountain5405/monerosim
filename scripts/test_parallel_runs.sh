#!/bin/bash
#
# test_parallel_runs.sh - acceptance test for per-run directories.
#
# Launches N runs of one config concurrently from THIS checkout and asserts
# they do not interfere: distinct run dirs, every run complete with
# summary.txt and Shadow exit 0, check_sim.sh addresses each one while all
# are live, the archived chain snapshots are byte-identical across runs
# (same seed, so any divergence means the runs touched each other's state),
# the smoke baseline passes when one exists for the config, and nothing new
# appears at the checkout root.
#
# Wall time: N 6h-sim quickstarts side by side take 20-45 min; a 100-agent
# config takes hours. Runs are nice'd. Logs: /tmp/monerosim_partest_<pid>_<i>.log
#
# Usage: ./scripts/test_parallel_runs.sh [CONFIG] [N]
#   CONFIG  default test_configs/quickstart.yaml
#   N       number of concurrent runs, default 2
#        ./scripts/test_parallel_runs.sh --check CONFIG RUN_DIR...
#   Re-run the post-completion assertions on finished run dirs (no launch,
#   no root-change check).
#
# Chain identity: same config + same seed gives byte-identical archived chain
# snapshots ONLY when the config does not enable Shadow's native preemption
# (general.native_preemption). Preemption fires on real CPU time, so under
# load it reorders transaction timing between otherwise identical runs; the
# block schedule (miner pacing from the seeded RNG) still matches. With
# preemption on, differing snapshots are reported as a warning and equal
# block counts are asserted instead.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source scripts/log_lib.sh
source scripts/run_dir_lib.sh

CHECK_ONLY=0
if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=1; shift
    CONFIG="${1:?--check needs CONFIG}"; shift
    (( $# >= 1 )) || { echo "--check needs at least one RUN_DIR" >&2; exit 2; }
    RUNS=("$@"); N=${#RUNS[@]}
else
    CONFIG="${1:-test_configs/quickstart.yaml}"
    N="${2:-2}"
    [[ "$N" =~ ^[0-9]+$ && "$N" -ge 1 ]] || { echo "N must be a positive integer" >&2; exit 2; }
fi
STAMP=$(date +%H%M%S)
NAMES=(); LOGS=(); PIDS=(); (( CHECK_ONLY )) || RUNS=()
for ((i = 1; i <= N; i++)); do
    NAMES+=("par${i}_$STAMP")
    LOGS+=("/tmp/monerosim_partest_$$_$i.log")
done
fail() {
    log_err "$*"
    local p
    for p in "${PIDS[@]}"; do kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null; done
    exit 1
}

marker=""
if (( CHECK_ONLY == 0 )); then
mkdir -p "$ROOT/.superpowers"
marker="$ROOT/.superpowers/partest_marker_$$"
touch "$marker"
cleanup_marker() { rm -f "$marker"; }
trap cleanup_marker EXIT

log_step "Build once (all runs use --no-build)"
cargo build --release --quiet

log_step "Launch $N runs of $CONFIG concurrently from $ROOT"
for ((i = 0; i < N; i++)); do
    nice ./run_sim.sh --config "$CONFIG" --name "${NAMES[$i]}" --no-build --no-monitor > "${LOGS[$i]}" 2>&1 </dev/null &
    PIDS+=("$!")
    sleep 1
done
log_info "run_sim.sh pids: ${PIDS[*]}"

# "|| true": under pipefail, `ls` matching nothing makes the pipeline's exit
# status non-zero even though `tail -1` (last in the pipe) succeeds; without
# this, `$(find_run ...)` trips `set -e` and kills the script silently before
# run_sim.sh has created the run dir.
find_run() { ls -d "$ROOT"/archived_runs/*_"$1" 2>/dev/null | tail -1 || true; }

log_step "Wait for every run to have a populated shadow.data/hosts (max 30 min)"
deadline=$((SECONDS + 1800))
while (( SECONDS < deadline )); do
    RUNS=(); ready=0
    for ((i = 0; i < N; i++)); do
        r=$(find_run "${NAMES[$i]}")
        RUNS+=("$r")
        [[ -n "$r" && -d "$r/shadow.data/hosts" ]] && ready=$((ready + 1))
        kill -0 "${PIDS[$i]}" 2>/dev/null || fail "run ${NAMES[$i]} died early; see ${LOGS[$i]}"
    done
    (( ready == N )) && break
    sleep 10
done
(( ${#RUNS[@]} == N )) || fail "run dirs did not all appear in time"
for ((i = 0; i < N; i++)); do
    [[ -n "${RUNS[$i]}" && -d "${RUNS[$i]}/shadow.data/hosts" ]] || fail "hosts dir for ${NAMES[$i]} did not appear in time"
done
(( $(printf '%s\n' "${RUNS[@]}" | sort -u | wc -l) == N )) || fail "run directories are not distinct: ${RUNS[*]}"
for r in "${RUNS[@]}"; do log_ok "run: $r"; done

log_step "check_sim.sh addresses each live run"
for R in "${RUNS[@]}"; do
    [[ "$(run_dir_state "$R")" == "live" ]] || fail "$R is not live while its run_sim.sh runs"
    out=$(./scripts/check_sim.sh "$R" 2>&1) || fail "check_sim.sh failed for $R: $out"
    grep -q "run: $R (live)" <<< "$out" || fail "check_sim.sh did not announce $R as live"
done
log_ok "check_sim.sh OK on all $N live runs"

log_step "Wait for completion"
status=0
for ((i = 0; i < N; i++)); do
    wait "${PIDS[$i]}" || { log_err "run ${NAMES[$i]} exited non-zero (see ${LOGS[$i]})"; status=1; }
done
(( status == 0 )) || exit 1
fi  # CHECK_ONLY

log_step "Assertions"
# Concurrent runs share the cores, so wall time is judged against the
# *_parallel baseline (relaxed wall-time ceiling, identical correctness
# metrics); fall back to the solo baseline; skip with a warning if neither
# exists for this config.
base="tests/baselines/$(basename "$CONFIG" .yaml)"
baseline="${base}_parallel_metrics.json"
[[ -f "$baseline" ]] || baseline="${base}_metrics.json"
[[ -f "$baseline" ]] || { log_warn "no smoke baseline for $(basename "$CONFIG"); skipping smoke assertions"; baseline=""; }
for R in "${RUNS[@]}"; do
    [[ -f "$R/summary.txt" ]] || fail "$R has no summary.txt"
    [[ "$(run_dir_state "$R")" == "complete" ]] || fail "$R is not complete"
    grep -q 'Exit code:      0' "$R/summary.txt" || fail "$R: Shadow exit code not 0"
    (( $(ls "$R/shadow.data/hosts" | wc -l) > 0 )) || fail "$R: empty shadow.data/hosts"
    [[ -f "$R/shadow_output/run_env.sh" ]] || fail "$R: no run_env.sh"
    grep -q "MONEROSIM_RUN_DIR=\"$(readlink -f "$R")\"" "$R/shadow_output/run_env.sh" || fail "$R: run_env.sh names another run"
    if [[ -n "$baseline" ]]; then
        python3 scripts/smoke_assertions.py --run-dir "$R" --baseline "$baseline" || fail "$R: smoke assertions failed (baseline $baseline)"
    fi
    log_ok "$R: complete, exit 0${baseline:+, smoke assertions pass}"
done

# Same config + same seed => the same block schedule in every run (miner
# pacing comes from the seeded RNG), and byte-identical archived chain
# snapshots unless native preemption is on (see header).
if (( N > 1 )); then
    blocks() { grep -m1 'Blocks mined:' "$1/summary.txt" | awk '{print $3}'; }
    ref_blocks=$(blocks "${RUNS[0]}")
    for R in "${RUNS[@]:1}"; do
        [[ "$(blocks "$R")" == "$ref_blocks" ]] || fail "$R: $(blocks "$R") blocks mined vs $ref_blocks in ${RUNS[0]} (block schedule diverged)"
    done
    log_ok "all $N runs mined $ref_blocks blocks"
    chain_sig() { (cd "$1/blockchain" 2>/dev/null && find . -name data.mdb | sort | xargs -r md5sum) || true; }
    ref=$(chain_sig "${RUNS[0]}")
    preempt=$(grep -E '^\s*native_preemption:\s*true' "$CONFIG" | wc -l)
    if [[ -z "$ref" ]]; then
        log_warn "no archived blockchain snapshot in ${RUNS[0]}; skipping chain-identity check"
    else
        for R in "${RUNS[@]:1}"; do
            if [[ "$(chain_sig "$R")" != "$ref" ]]; then
                if (( preempt > 0 )); then
                    log_warn "$R: archived chain snapshot differs from ${RUNS[0]} (expected with native_preemption: true under load; tx counts: $(grep -m1 'Created:' "${RUNS[0]}/summary.txt" | awk '{print $2}') vs $(grep -m1 'Created:' "$R/summary.txt" | awk '{print $2}'))"
                else
                    fail "$R: archived chain snapshot differs from ${RUNS[0]} (runs interfered or are non-deterministic)"
                fi
            fi
        done
        (( preempt > 0 )) || log_ok "archived chain snapshots identical across all $N runs"
    fi
fi

# Excludes cover both the directory itself and its contents: creating or
# removing an entry inside a directory (a new run dir under archived_runs/,
# a lock file git takes and releases, ...) bumps that directory's OWN mtime
# even though its contents are separately excluded, so the bare directory
# path must be excluded too or it false-flags as "changed".
if (( CHECK_ONLY == 0 )); then
changed=$(find "$ROOT" -newer "$marker" \
    -not -path "$ROOT/archived_runs" -not -path "$ROOT/archived_runs/*" \
    -not -path "$ROOT/target" -not -path "$ROOT/target/*" \
    -not -path "$ROOT/.superpowers" -not -path "$ROOT/.superpowers/*" \
    -not -path "$ROOT/.git" -not -path "$ROOT/.git/*" \
    -not -path "$ROOT/.pytest_cache" -not -path "$ROOT/.pytest_cache/*")
if [[ -n "$changed" ]]; then
    echo "$changed"
    fail "checkout root changed during the runs"
fi
log_ok "checkout root unchanged"
rm -f "${LOGS[@]}"
fi
log_ok "PARALLEL RUNS OK ($N runs): ${RUNS[*]}"
