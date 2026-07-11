#!/bin/bash

set -euo pipefail

# This script launches Python analysis scripts in the background, then waits
# for them and reports per-job exit status.
#
# Usage: ./post_run_analysis.sh [CONFIG_FILE]
#   CONFIG_FILE - optional path to the simulation config file.
#                  analyze_network_connectivity.py requires --config
#                  (argparse required=True); if no config is given here,
#                  that analyzer is skipped instead of being launched to fail.

# Activate the virtual environment if not already active
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -f "$PROJECT_ROOT/venv/bin/activate" ]]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

CONFIG_FILE="${1:-}"

echo "Starting Python scripts..."

# (log_processor.py is now at attic/log_processor.py and unmaintained;
#  invoke manually with PYTHONPATH=. if needed)
pids=()
names=()

python3 scripts/analyze_success_criteria.py &
pids+=("$!")
names+=("analyze_success_criteria.py")

if [[ -n "$CONFIG_FILE" ]]; then
    python3 scripts/analyze_network_connectivity.py --config "$CONFIG_FILE" &
    pids+=("$!")
    names+=("analyze_network_connectivity.py")
else
    echo "No config file provided; skipping analyze_network_connectivity.py (needs --config)."
fi

status=0
for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
        echo "✅ ${names[$i]} finished successfully."
    else
        rc=$?
        echo "FAILED: ${names[$i]} exited with code $rc."
        status=1
    fi
done

exit $status
