#!/bin/bash

# Central Block Controller Script for MoneroSim
# This script uses the daemon's start_mining/stop_mining RPC to generate blocks
# This approach works better in regtest mode than generateblocks

# Configuration
DAEMON_IP="11.0.0.1"
DAEMON_RPC_PORT="28090"
DAEMON_URL="http://${DAEMON_IP}:${DAEMON_RPC_PORT}/json_rpc"
BLOCK_INTERVAL="0.5"  # seconds between blocks
MINING_ADDRESS="44AFFq5kSiGBoZ4NrCW6p7qX5sT2q5PmPLVGBYatcjCQSjfjqTVFHjhysjJjSBNgRL6kn9qCqy8bMZWFNWDj3uBbNYJYvZf"

# Function to call daemon RPC
call_daemon() {
    local method="$1"
    local params="$2"
    local data="{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"$method\""
    if [[ -n "$params" ]]; then
        data+=",\"params\":$params"
    fi
    data+="}"
    
    curl -s --max-time 10 --connect-timeout 5 "$DAEMON_URL" \
        -H 'Content-Type: application/json' \
        -d "$data" 2>/dev/null
}

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] $1"
}

# Function to check if daemon is ready
check_daemon_ready() {
    local response=$(call_daemon "get_info" "")
    log "Daemon response: $response"
    
    # Check if we have a valid JSON response with result and status OK
    if [[ "$response" == *"\"result\""* ]]; then
        log "Found result field in response"
        # More flexible status matching to handle whitespace
        if [[ "$response" =~ \"status\"[[:space:]]*:[[:space:]]*\"OK\" ]]; then
            log "Found status OK in response"
            # Also check if daemon is synchronized (required for mining)
            if [[ "$response" =~ \"synchronized\"[[:space:]]*:[[:space:]]*true ]]; then
                log "Daemon is synchronized - ready for mining!"
                return 0
            else
                log "Daemon not synchronized yet, waiting..."
                return 1
            fi
        else
            log "No status OK found in response"
            return 1
        fi
    else
        log "No result field found in response"
        return 1
    fi
}

# Function to generate blocks via RPC
generate_blocks() {
    local blocks_to_generate=$1
    # Try generateblocks without wallet address first (works in regtest)
    local response=$(call_daemon "generateblocks" "{\"amount_of_blocks\":$blocks_to_generate}")
    log "Generate blocks response: $response"
    
    # Check if the response contains height (successful generation)
    if [[ "$response" =~ \"height\":[[:space:]]*[0-9]+ ]]; then
        return 0
    else
        # If that fails, try with wallet address
        response=$(call_daemon "generateblocks" "{\"amount_of_blocks\":$blocks_to_generate,\"wallet_address\":\"$MINING_ADDRESS\"}")
        log "Generate blocks with address response: $response"
        if [[ "$response" =~ \"height\":[[:space:]]*[0-9]+ ]]; then
            return 0
        else
            return 1
        fi
    fi
}

# Function to start mining (now using generateblocks)
start_mining() {
    log "Starting block generation with generateblocks RPC"
    return 0  # generateblocks doesn't need a separate "start" call
}

# Function to stop mining (not needed for generateblocks)
stop_mining() {
    log "Stopping block generation"
    return 0  # generateblocks doesn't need a separate "stop" call
}

# Function to get current block height
get_block_height() {
    local response=$(call_daemon "get_info" "")
    echo "$response" | grep -o '"height":[0-9]*' | cut -d':' -f2
}

# Main execution
log "Starting block controller"
log "Target daemon: $DAEMON_IP:$DAEMON_RPC_PORT"
log "Block interval: ${BLOCK_INTERVAL}s"
log "Mining address: $MINING_ADDRESS"

# Wait for daemon to be ready
log "Waiting for daemon to be ready..."
READY_TIMEOUT=10
READY_COUNT=0
while ! check_daemon_ready; do
    sleep 0.1
    READY_COUNT=$((READY_COUNT + 1))
    if [[ $READY_COUNT -gt $((READY_TIMEOUT * 10)) ]]; then
        log "ERROR: Daemon not ready after ${READY_TIMEOUT}s, exiting"
        exit 1
    fi
done
log "Daemon is ready, starting block generation"

# Record initial height
INITIAL_HEIGHT=$(get_block_height)
log "Initial blockchain height: $INITIAL_HEIGHT"

# Main block generation loop
log "Starting block generation loop"
BLOCKS_PER_INTERVAL=1 # Generate one block per interval
while true; do
    # Generate one block
    if generate_blocks $BLOCKS_PER_INTERVAL; then
        log "Successfully generated $BLOCKS_PER_INTERVAL block(s)"
    else
        log "Failed to generate blocks, retrying..."
    fi
    
    # Wait for the specified interval
    sleep $BLOCK_INTERVAL
done 