#!/bin/bash

# Central Block Controller Script for MoneroSim
# This script programmatically generates blocks every 0.5 seconds using the generateblocks RPC
# This approach is much more efficient than individual node mining in Shadow

# Configuration
DAEMON_IP="11.0.0.1"
DAEMON_RPC_PORT="28090"
BLOCK_INTERVAL="0.5"  # seconds between blocks
BLOCKS_PER_INTERVAL="1"  # number of blocks to generate each interval

# For regtest mode, we can use a deterministic address or let the daemon generate one
# Let's use a standard regtest address format
MINING_ADDRESS="9wviCeWe2D8XS82k2ovp5EUYLzBt9pYNW2LXUFsZiv8S3Mt21FZ5qQaAroko1enzw3eGr9qC7X1D7Geoo2RrAotYPwq9Gm8"

# Function to generate blocks via RPC using the mining address
generate_blocks_with_address() {
    local blocks_to_generate=$1
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"generateblocks\",\"params\":{\"amount_of_blocks\":${blocks_to_generate},\"wallet_address\":\"${MINING_ADDRESS}\"}}" \
        "http://${DAEMON_IP}:${DAEMON_RPC_PORT}/json_rpc")
    
    if [[ $response == *"\"error\""* ]]; then
        return 1
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Generated $blocks_to_generate block(s) with address"
        return 0
    fi
}

# Function to generate blocks via RPC without wallet address (let daemon handle it)
generate_blocks_simple() {
    local blocks_to_generate=$1
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"generateblocks\",\"params\":{\"amount_of_blocks\":${blocks_to_generate}}}" \
        "http://${DAEMON_IP}:${DAEMON_RPC_PORT}/json_rpc")
    
    if [[ $response == *"\"error\""* ]]; then
        return 1
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Generated $blocks_to_generate block(s) (simple)"
        return 0
    fi
}

# Function to generate blocks - try multiple approaches
generate_blocks() {
    local blocks_to_generate=$1
    
    # First try with the mining address
    if generate_blocks_with_address $blocks_to_generate; then
        return 0
    fi
    
    # If that fails, try without wallet address
    if generate_blocks_simple $blocks_to_generate; then
        return 0
    fi
    
    # If both fail, log the error
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] ERROR: Failed to generate blocks with both methods"
    return 1
}

# Function to check daemon status
check_daemon_status() {
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
        "http://${DAEMON_IP}:${DAEMON_RPC_PORT}/json_rpc")
    
    if [[ $response == *"\"result\""* ]]; then
        return 0
    else
        return 1
    fi
}

# Main block generation loop
echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Starting block controller"
echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Target daemon: ${DAEMON_IP}:${DAEMON_RPC_PORT}"
echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Block interval: ${BLOCK_INTERVAL}s"
echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Blocks per interval: ${BLOCKS_PER_INTERVAL}"

# Wait for daemon to be ready
echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Waiting for daemon to be ready..."
while ! check_daemon_status; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Daemon not ready, waiting 0.5s..."
    sleep 0.5
done

echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Daemon is ready, starting block generation"

# Initialize block counter
block_count=0

# Main loop
while true; do
    if generate_blocks $BLOCKS_PER_INTERVAL; then
        block_count=$((block_count + BLOCKS_PER_INTERVAL))
        echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] Total blocks generated: $block_count"
    fi
    
    sleep $BLOCK_INTERVAL
done 