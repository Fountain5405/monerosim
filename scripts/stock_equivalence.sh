#!/bin/bash
#
# stock_equivalence.sh - is an unflagged monerod-sim the same daemon as stock
# monerod?
#
# monerod-sim is stock monerod plus the patches in patches/series. Every patch
# is gated by a --sim-* style flag and is meant to be inert without it. This
# test checks that, end to end: it runs a scenario twice with the same seed,
# once as committed (every daemon is stock `monerod`) and once with every
# `daemon: monerod` rewritten to `monerod-sim` and nothing else changed, and
# passes only when
#   - both runs pass the scenario's smoke assertions
#     (tests/baselines/<scenario>_metrics.json), and
#   - every daemon node's chain is identical in the two runs over the heights
#     both reached (scripts/compare_chains.py, block ids from the daemon logs).
#
# Run it after changing patches/series or any patch (after ./setup.sh
# --sim-binary). Two quickstarts take about 35 min on an idle box.
#
# Usage:
#   ./scripts/stock_equivalence.sh                # quickstart
#   ./scripts/stock_equivalence.sh <scenario>     # test_configs/<scenario>.yaml
#                                                 # + tests/baselines/<scenario>_metrics.json
#
# The scenario must be one stock monerod can run: legacy mining (no
# general.mining.mode: native), no --sim-* / --fakechain-* / --peerlist-dump
# options, and only `daemon: monerod` daemons.
#
# Each run appends a row to tests/baselines/stock_equivalence_history.csv
# (commit, monerod-sim sha256, its patch count, verdict, first divergence).
#
# Exit codes:
#   0  PASS: both runs pass the assertions and every chain is identical.
#   1  FAIL: a chain diverged or a smoke assertion failed.
#   2  compare_chains.py could not compare (a node missing, no blocks).
#   4  Scenario missing, or one stock monerod cannot run.
#   5  run_sim.sh exited 0 but never reported its run directory.
#   *  Any other non-zero from run_sim.sh is propagated.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT" || exit 1
# shellcheck disable=SC1091
source "$SCRIPT_DIR/colors.sh"

SCENARIO="${1:-quickstart}"
CONFIG_PATH="test_configs/${SCENARIO}.yaml"
BASELINE_PATH="tests/baselines/${SCENARIO}_metrics.json"
HISTORY="tests/baselines/stock_equivalence_history.csv"
BIN_DIR="$HOME/.monerosim/bin"

# --- Preflight ---------------------------------------------------------------
for f in "$CONFIG_PATH" "$BASELINE_PATH"; do
    if [[ ! -f "$f" ]]; then
        echo -e "${RED}Stock equivalence: missing $f${NC}" >&2
        exit 4
    fi
done
refuse() { echo -e "${RED}Stock equivalence: stock monerod cannot run $CONFIG_PATH: $1${NC}" >&2; exit 4; }
grep -Eq '^\s*mode:\s*native\b' "$CONFIG_PATH" && refuse "general.mining.mode is native (needs --sim-hash-interval-ms)"
grep -Eq '^\s*(--)?(sim-[a-z0-9-]+|fakechain-hard-forks|peerlist-dump-file)\s*:' "$CONFIG_PATH" \
    && refuse "it sets a patched-daemon option ($(grep -Eo '(sim-[a-z0-9-]+|fakechain-hard-forks|peerlist-dump-file)' "$CONFIG_PATH" | sort -u | tr '\n' ' '))"
grep -Eq '^\s*daemon:\s*monerod\s*$' "$CONFIG_PATH" || refuse "no 'daemon: monerod' agent"
grep -Eq '^\s*daemon:\s*monerod[^ ]' "$CONFIG_PATH" && refuse "a daemon is not stock monerod ($(grep -Eo 'daemon:\s*monerod[^ ]+' "$CONFIG_PATH" | sort -u | tr '\n' ' '))"

# The two configs: a copy, and the copy with every daemon rewritten.
WORK=$(mktemp -d "${TMPDIR:-/tmp}/stock_equivalence.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
STOCK_CFG="$WORK/${SCENARIO}_stock.yaml"
SIM_CFG="$WORK/${SCENARIO}_sim.yaml"
cp "$CONFIG_PATH" "$STOCK_CFG"
sed -E 's/^(\s*daemon:\s*)monerod\s*$/\1monerod-sim/' "$CONFIG_PATH" > "$SIM_CFG"
N_REWRITTEN=$(grep -Ec '^\s*daemon:\s*monerod-sim\s*$' "$SIM_CFG")

echo -e "${BOLD}${BLUE}=== Stock equivalence: ${SCENARIO} ===${NC}"
echo "Config:    $CONFIG_PATH ($N_REWRITTEN daemons rewritten to monerod-sim in the second run)"
echo "Baseline:  $BASELINE_PATH"
echo "Binary:    $BIN_DIR/monerod-sim"
echo

# --- The two runs -----------------------------------------------------------
# run_one <label> <config>: sets RUN_DIR_<label>; exits on a run_sim.sh failure.
run_one() {
    local label=$1 cfg=$2 dir_file rc=0 dir
    dir_file=$(mktemp "$WORK/run_dir.XXXXXX")
    echo -e "${BOLD}Run $label: ./run_sim.sh --config $cfg${NC}"
    ./run_sim.sh --config "$cfg" --run-dir-file "$dir_file" || rc=$?
    dir=""
    [[ -s "$dir_file" ]] && dir=$(head -n 1 "$dir_file")
    if (( rc != 0 )); then
        echo -e "${RED}Stock equivalence FAIL: run_sim.sh ($label) exited $rc${NC}" >&2
        [[ -n "$dir" ]] && echo "  run dir: $dir" >&2
        exit "$rc"
    fi
    if [[ -z "$dir" || ! -d "$dir" ]]; then
        echo -e "${RED}Stock equivalence FAIL: run_sim.sh ($label) did not report its run directory${NC}" >&2
        exit 5
    fi
    printf -v "RUN_DIR_$label" '%s' "$dir"
    echo -e "${BOLD}Run $label archive: $dir${NC}"
    echo
}

START_TS=$(date +%s)
run_one stock "$STOCK_CFG"
run_one sim "$SIM_CFG"
WALL_S=$(( $(date +%s) - START_TS ))

# --- Smoke assertions on both ------------------------------------------------
echo -e "${BOLD}${BLUE}=== Smoke assertions ===${NC}"
ASSERT_FAIL=""
for label in stock sim; do
    dir_var="RUN_DIR_$label"
    echo -e "${BOLD}$label:${NC}"
    rc=0
    python3 "$SCRIPT_DIR/smoke_assertions.py" --run-dir "${!dir_var}" --baseline "$BASELINE_PATH" || rc=$?
    (( rc != 0 )) && ASSERT_FAIL+="$label(exit $rc) "
done
echo

# --- Chains ------------------------------------------------------------------
echo -e "${BOLD}${BLUE}=== Chains: every daemon node, stock vs monerod-sim ===${NC}"
N_NODES=$(find "$RUN_DIR_stock/daemon_logs" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
echo "$N_NODES daemon nodes in the stock run"
CHAIN_JSON="$WORK/chains.json"
CHAIN_RC=0
python3 "$SCRIPT_DIR/compare_chains.py" "$RUN_DIR_stock" "$RUN_DIR_sim" --json "$CHAIN_JSON" || CHAIN_RC=$?
echo

# --- Verdict + history -------------------------------------------------------
FIRST_DIV=""
if [[ -f "$CHAIN_JSON" ]]; then
    FIRST_DIV=$(python3 - "$CHAIN_JSON" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
hits = [f"{n['node']}@{n['first_divergence']}" for n in d["nodes"] if n["first_divergence"] is not None]
errs = [f"{n['node']}:error" for n in d["nodes"] if n["error"]]
print(" ".join(hits + errs))
PY
    )
fi
if (( CHAIN_RC == 0 )) && [[ -z "$ASSERT_FAIL" ]]; then
    RESULT=PASS; RC=0
elif (( CHAIN_RC == 2 )); then
    RESULT=ERROR; RC=2
else
    RESULT=FAIL; RC=1
fi

SIM_SHA=$(sha256sum "$(readlink -f "$BIN_DIR/monerod-sim")" 2>/dev/null | cut -c1-64)
PATCHES=$(grep -c '^patch_sha256:' "$BIN_DIR/monerod-sim.provenance" 2>/dev/null || echo 0)
COMMIT=$(git rev-parse --short=8 HEAD 2>/dev/null || echo unknown)
if [[ ! -f "$HISTORY" ]]; then
    echo "date,commit_hash,scenario,result,monerod_sim_sha256,patch_count,nodes,first_divergence,assertion_failures,wall_seconds,stock_run,sim_run" > "$HISTORY"
fi
echo "$(date -u +%Y-%m-%d),$COMMIT,$SCENARIO,$RESULT,${SIM_SHA:-unknown},$PATCHES,$N_NODES,${FIRST_DIV// /;},${ASSERT_FAIL% },$WALL_S,$(basename "$RUN_DIR_stock"),$(basename "$RUN_DIR_sim")" >> "$HISTORY"

echo
if [[ "$RESULT" == PASS ]]; then
    echo -e "${BOLD}${GREEN}Stock equivalence PASS${NC} (scenario=$SCENARIO, $N_NODES nodes, wall ${WALL_S}s)"
    echo "  monerod-sim ${SIM_SHA:0:16}… with $PATCHES patches behaves as stock monerod on $SCENARIO"
    echo "  history: $HISTORY"
    exit 0
fi
echo -e "${BOLD}${RED}Stock equivalence $RESULT${NC} (scenario=$SCENARIO, wall ${WALL_S}s)"
[[ -n "$ASSERT_FAIL" ]] && echo "  smoke assertions failed: $ASSERT_FAIL"
[[ -n "$FIRST_DIV" ]] && echo "  chains: $FIRST_DIV (node@first divergent height)"
echo "  stock run: $RUN_DIR_stock"
echo "  sim run:   $RUN_DIR_sim"
echo "  history:   $HISTORY"
if [[ -n "$FIRST_DIV" ]]; then
    echo "  A divergence can be run-to-run spread rather than the patches. To tell: run the"
    echo "  scenario again on stock and compare stock against stock:"
    echo "    ./run_sim.sh --config $CONFIG_PATH && scripts/compare_chains.py $RUN_DIR_stock archived_runs/<new run>"
    echo "  If stock differs from stock too, the scenario is not a chain-identity test at this seed."
fi
exit "$RC"
