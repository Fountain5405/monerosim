#!/bin/bash

# This script launches three Python scripts in the background.

echo "🚀 Starting Python scripts..."

python3 scripts/log_processor.py &
python3 scripts/analyze_success_criteria.py &
python3 scripts/analyize_network_connectivity.py &

echo "✅ All scripts have been launched in the background."
