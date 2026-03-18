#!/bin/bash

# This script launches three Python scripts in the background.

# Activate the virtual environment if not already active
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -f "$PROJECT_ROOT/venv/bin/activate" ]]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

echo "Starting Python scripts..."

#python3 scripts/log_processor.py &
python3 scripts/analyze_success_criteria.py &
python3 scripts/analyze_network_connectivity.py &

echo "✅ All scripts have been launched in the background."
