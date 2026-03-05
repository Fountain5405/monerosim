#!/bin/bash
set -e

# Quick simulation runner for monerosim
# Usage: ./run_sim.sh [config_file]
# Default: test_configs/ultra_minimal_test.yaml (2 miners, 1 user, 2.5h sim)

CONFIG="${1:-test_configs/ultra_minimal_test.yaml}"

if [[ ! -f "$CONFIG" ]]; then
    echo "Error: Config file not found: $CONFIG"
    echo "Usage: ./run_sim.sh [config_file]"
    exit 1
fi

echo "Building monerosim..."
cargo build --release

echo "Generating Shadow configuration from $CONFIG..."
./target/release/monerosim --config "$CONFIG" --output shadow_output

echo "Cleaning previous simulation data..."
rm -rf shadow.data/ shadow.log

echo "Starting simulation..."
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
SHADOW_PID=$!

echo "Simulation started (PID: $SHADOW_PID)"
echo "Monitor with: tail shadow.log"
echo "Check status: ./scripts/check_sim.sh"
