#!/bin/bash
#
# smoke_test.sh - Tier 2 Shadow smoke test wrapper.
#
# Runs an end-to-end Shadow simulation for the named scenario and then
# evaluates the resulting archive against a baseline of stricter
# assertions than the default 4 PASS/FAIL success criteria.
#
# Usage:
#   ./scripts/smoke_test.sh                     # quickstart (default)
#   ./scripts/smoke_test.sh quickstart
#   ./scripts/smoke_test.sh refactor_gate
#
# Exit codes:
#   0  Both run_sim.sh and the smoke assertions passed.
#   1  smoke_assertions.py reported one or more FAILs.
#   2  smoke_assertions.py: run did not complete (missing summary.txt).
#   3  smoke_assertions.py: baseline JSON file not found.
#   4  Required input(s) missing: scenario YAML or baseline JSON.
#   5  Could not locate the archive directory after run_sim.sh.
#   *  Any other non-zero from run_sim.sh is propagated.

set -euo pipefail

# --- Setup ---------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors (BOLD, RED, GREEN, YELLOW, BLUE, CYAN, NC)
# shellcheck disable=SC1091
source "$SCRIPT_DIR/colors.sh"

SCENARIO="${1:-quickstart}"
CONFIG_PATH="test_configs/${SCENARIO}.yaml"
BASELINE_PATH="tests/baselines/${SCENARIO}_metrics.json"

# --- Preflight: configs exist --------------------------------------------
missing=()
[[ ! -f "$CONFIG_PATH" ]]   && missing+=("$CONFIG_PATH")
[[ ! -f "$BASELINE_PATH" ]] && missing+=("$BASELINE_PATH")
if (( ${#missing[@]} > 0 )); then
    echo -e "${RED}Smoke test FAIL: missing required input(s) for scenario '${SCENARIO}':${NC}" >&2
    for f in "${missing[@]}"; do
        echo "  - $f" >&2
    done
    exit 4
fi

echo -e "${BOLD}${BLUE}=== Tier 2 Smoke Test: ${SCENARIO} ===${NC}"
echo "Config:   $CONFIG_PATH"
echo "Baseline: $BASELINE_PATH"
echo

# --- Run simulation -------------------------------------------------------
START_TS=$(date +%s)
echo -e "${BOLD}Running ./run_sim.sh --config ${CONFIG_PATH} ...${NC}"
echo

# Don't let `set -e` abort on a non-zero run_sim.sh: we evaluate it explicitly.
SIM_EXIT=0
./run_sim.sh --config "$CONFIG_PATH" || SIM_EXIT=$?

END_TS=$(date +%s)
WALL_S=$(( END_TS - START_TS ))
echo
echo -e "${BOLD}run_sim.sh exit code: ${SIM_EXIT} (wall ${WALL_S}s)${NC}"

# --- Locate the archive ---------------------------------------------------
ARCHIVE_DIR=""
if [[ -d "archived_runs" ]]; then
    # Most recent archive directory.
    candidate=$(find archived_runs -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
                | sort -nr | head -1 | awk '{print $2}')
    if [[ -n "$candidate" && -d "$candidate" ]]; then
        ARCHIVE_DIR="$candidate"
    fi
fi

if [[ -z "$ARCHIVE_DIR" ]]; then
    echo -e "${RED}Smoke test FAIL: could not locate archive directory under archived_runs/${NC}" >&2
    exit 5
fi

# Sanity-check: archive name should end with the scenario name.
arch_base=$(basename "$ARCHIVE_DIR")
if [[ "$arch_base" != *"_${SCENARIO}" ]]; then
    echo -e "${YELLOW}Warning: latest archive '${arch_base}' does not end with '_${SCENARIO}'.${NC}" >&2
    echo -e "${YELLOW}Continuing anyway, but the archive may be from a different scenario.${NC}" >&2
fi

echo
echo -e "${BOLD}Archive: ${ARCHIVE_DIR}${NC}"

# --- Smoke assertions -----------------------------------------------------
echo
echo -e "${BOLD}${BLUE}=== Running smoke assertions ===${NC}"
ASSERT_EXIT=0
python3 "$SCRIPT_DIR/smoke_assertions.py" \
    --run-dir "$ARCHIVE_DIR" \
    --baseline "$BASELINE_PATH" || ASSERT_EXIT=$?

# --- Append run-history row -----------------------------------------------
# One row per smoke run (PASS or FAIL) into tests/baselines/<scenario>_run_history.csv.
# Failures here MUST NOT change the smoke-test outcome: log a warning and continue.
if (( SIM_EXIT == 0 && ASSERT_EXIT == 0 )); then
    SMOKE_RESULT="PASS"
else
    SMOKE_RESULT="FAIL"
fi
APPEND_EXIT=0
python3 "$SCRIPT_DIR/append_run_history.py" \
    --run-dir "$ARCHIVE_DIR" \
    --scenario "$SCENARIO" \
    --result "$SMOKE_RESULT" || APPEND_EXIT=$?
if (( APPEND_EXIT != 0 )); then
    echo -e "${YELLOW}Warning: append_run_history.py exited ${APPEND_EXIT}; not failing the smoke run.${NC}" >&2
fi

# --- Final result ---------------------------------------------------------
echo
if (( SIM_EXIT == 0 && ASSERT_EXIT == 0 )); then
    echo -e "${BOLD}${GREEN}Smoke test PASS${NC} (scenario=${SCENARIO}, wall ${WALL_S}s)"
    exit 0
fi

echo -e "${BOLD}${RED}Smoke test FAIL${NC} (scenario=${SCENARIO}, wall ${WALL_S}s)"
echo "  run_sim.sh exit:           ${SIM_EXIT}"
echo "  smoke_assertions.py exit:  ${ASSERT_EXIT}"
echo "  archive dir:               ${ARCHIVE_DIR}"

# Propagate the first non-zero exit code.
if (( SIM_EXIT != 0 )); then
    exit "$SIM_EXIT"
else
    exit "$ASSERT_EXIT"
fi
