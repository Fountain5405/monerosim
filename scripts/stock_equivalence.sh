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
#   - the two runs have the same block timeline: for every archived chain, at
#     every height both runs reached, the same timestamp, block version and
#     difficulty, and transaction totals within 2 %
#     (scripts/compare_block_timeline.py, headers read from the archived chain
#     databases with a stock monerod started offline).
#
# Why the timeline and not the block ids: the coinbase key comes from the
# daemon's random stream, and any change to the binary shifts that stream, so
# two binaries never produce the same block ids even when they behave the
# same (2026-11-03: stock vs unflagged monerod-sim on quickstart differed in
# every block id from height 1, and in nothing the agents drive). The
# timeline is what the agents drive and what a patch that quietly changed
# consensus or mining would disturb. docs/20261103_sim_patch_inertness_audit.md.
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
# (commit, monerod-sim sha256, its patch count, verdict, first difference).
#
# Exit codes:
#   0  PASS: both runs pass the assertions and the timelines are the same.
#   1  FAIL: a timeline differs, tx totals are apart, or an assertion failed.
#   2  compare_block_timeline.py could not compare (no chain archived in
#      both runs, monerod not answering).
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

# --- Block timeline ------------------------------------------------------------
echo -e "${BOLD}${BLUE}=== Block timeline: archived chains, stock vs monerod-sim ===${NC}"
CHAIN_JSON="$WORK/timeline.json"
CHAIN_RC=0
python3 "$SCRIPT_DIR/compare_block_timeline.py" "$RUN_DIR_stock" "$RUN_DIR_sim" \
    --monerod "$BIN_DIR/monerod" --json "$CHAIN_JSON" || CHAIN_RC=$?
echo

# --- Verdict + history -------------------------------------------------------
FIRST_DIV=""; N_CHAINS=0
if [[ -f "$CHAIN_JSON" ]]; then
    read -r N_CHAINS FIRST_DIV < <(python3 - "$CHAIN_JSON" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
out = []
for n in d["nodes"]:
    if n["first_difference"]:
        h, f, a, b = n["first_difference"]
        out.append(f"{n['node']}@{h}:{f}={a}/{b}")
    if not n["tx_ok"] and not n["error"]:
        out.append(f"{n['node']}:txs={n['tx_total'][0]}/{n['tx_total'][1]}")
    if n["error"]:
        out.append(f"{n['node']}:error")
print(len(d["nodes"]), " ".join(out))
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
    echo "date,commit_hash,scenario,result,monerod_sim_sha256,patch_count,chains,difference,assertion_failures,wall_seconds,stock_run,sim_run" > "$HISTORY"
fi
echo "$(date -u +%Y-%m-%d),$COMMIT,$SCENARIO,$RESULT,${SIM_SHA:-unknown},$PATCHES,$N_CHAINS,${FIRST_DIV// /;},${ASSERT_FAIL% },$WALL_S,$(basename "$RUN_DIR_stock"),$(basename "$RUN_DIR_sim")" >> "$HISTORY"

echo
if [[ "$RESULT" == PASS ]]; then
    echo -e "${BOLD}${GREEN}Stock equivalence PASS${NC} (scenario=$SCENARIO, $N_CHAINS archived chains, wall ${WALL_S}s)"
    echo "  monerod-sim ${SIM_SHA:0:16}… with $PATCHES patches has stock monerod's block timeline on $SCENARIO"
    echo "  history: $HISTORY"
    exit 0
fi
echo -e "${BOLD}${RED}Stock equivalence $RESULT${NC} (scenario=$SCENARIO, wall ${WALL_S}s)"
[[ -n "$ASSERT_FAIL" ]] && echo "  smoke assertions failed: $ASSERT_FAIL"
[[ -n "$FIRST_DIV" ]] && echo "  timeline: $FIRST_DIV (chain@height:field=stock/sim, or chain:txs=stock/sim)"
echo "  stock run: $RUN_DIR_stock"
echo "  sim run:   $RUN_DIR_sim"
echo "  history:   $HISTORY"
if [[ -n "$FIRST_DIV" ]]; then
    echo "  A timeline difference means a daemon timed or valued a block differently: look at that"
    echo "  height in both runs' daemon logs. Block ids, nonces and sizes differ between binaries"
    echo "  by design (random stream) and are not judged. The archives keep the two runs:"
    echo "    scripts/compare_block_timeline.py $RUN_DIR_stock $RUN_DIR_sim"
fi
exit "$RC"
