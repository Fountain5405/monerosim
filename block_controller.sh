#!/bin/bash

# Central Block Controller Script for MoneroSim
# This script uses the daemon's generateblocks RPC to generate blocks
# Updated for 1 block per minute generation rate (realistic timing)

# Configuration
DAEMON_IP="11.0.0.1"
DAEMON_RPC_PORT="28090"
DAEMON_URL="http://${DAEMON_IP}:${DAEMON_RPC_PORT}/json_rpc"
BLOCK_INTERVAL="60.0"  # 60 seconds between blocks (1 block per minute)
BLOCKS_PER_INTERVAL="1"  # number of blocks to generate each interval

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] $1"
}

# Use the address that the wallet actually generates (from transaction test output)
MINING_ADDRESS="48S1ZANZRDGTqF7rdxCh8R4jvBELF63u9MieHNwGNYrRZWka84mN9ttV88eq2QScJRHJsdHJMNg3LDu3Z21hmaE61SWymvv"
log "Using mining address that matches wallet: $MINING_ADDRESS"

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

# Function to generate blocks via RPC using the format from documentation
generate_blocks() {
    local blocks_to_generate=$1
    local nonce=$((RANDOM % 1000))  # Random starting nonce
    
    # Use the exact format from the working documentation example
    local response=$(call_daemon "generateblocks" "{\"amount_of_blocks\":$blocks_to_generate,\"wallet_address\":\"$MINING_ADDRESS\",\"starting_nonce\":$nonce}")
    log "Generate blocks response: $response"
    
    # Check if the response contains height (successful generation)
    if [[ "$response" =~ \"height\":[[:space:]]*[0-9]+ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to get current block height
get_block_height() {
    local response=$(call_daemon "get_info" "")
    echo "$response" | grep -o '"height":[0-9]*' | cut -d':' -f2
}

# Main execution
log "Starting block controller"
log "Target daemon: $DAEMON_IP:$DAEMON_RPC_PORT"
log "Block interval: ${BLOCK_INTERVAL}s (1 block per minute)"
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

# Main block generation loop - generate blocks for 2 hours (120 blocks at 1/minute)
log "Starting block generation loop - generating 120 blocks at 1 block/minute"
TARGET_BLOCKS=120
GENERATED_BLOCKS=0

while [[ $GENERATED_BLOCKS -lt $TARGET_BLOCKS ]]; do
    # Generate one block
    if generate_blocks $BLOCKS_PER_INTERVAL; then
        GENERATED_BLOCKS=$((GENERATED_BLOCKS + BLOCKS_PER_INTERVAL))
        current_minutes=$((GENERATED_BLOCKS))
        log "Successfully generated $BLOCKS_PER_INTERVAL block(s) - Total: $GENERATED_BLOCKS/$TARGET_BLOCKS (${current_minutes} minutes simulated)"
    else
        log "Failed to generate blocks, retrying..."
    fi
    
    # Wait for the specified interval (60 seconds)
    sleep $BLOCK_INTERVAL
done

log "Block generation complete! Generated $GENERATED_BLOCKS blocks"
FINAL_HEIGHT=$(get_block_height)
log "Final blockchain height: $FINAL_HEIGHT" 