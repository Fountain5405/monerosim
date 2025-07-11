#!/bin/bash

# Central Block Controller Script for MoneroSim
# This script uses the daemon's generateblocks RPC to generate blocks
# Updated for 1 block per minute generation rate (realistic timing)

# Configuration
DAEMON_IP="11.0.0.1"
DAEMON_RPC_PORT="28090"
WALLET_RPC_IP="11.0.0.6"
WALLET_RPC_PORT="28091"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BLOCK_CONTROLLER] $1"
}

# Function to call daemon RPC
call_daemon() {
    local method="$1"
    local params="$2"
    curl -s --max-time 10 "http://${DAEMON_IP}:${DAEMON_RPC_PORT}/json_rpc" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"${method}\",\"params\":${params}}" \
        -H "Content-Type: application/json"
}

# Function to call wallet RPC
call_wallet() {
    local method="$1"
    local params="$2"
    curl -s --max-time 10 "http://${WALLET_RPC_IP}:${WALLET_RPC_PORT}/json_rpc" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"${method}\",\"params\":${params}}" \
        -H "Content-Type: application/json"
}

# Function to get mining address from the existing wallet created by transaction script
create_mining_wallet() {
    log "Getting mining address from existing wallet..."
    
    # Wait for the transaction script to create the wallet
    local attempts=0
    local max_attempts=30
    while [[ $attempts -lt $max_attempts ]]; do
        # Try to get the address from the existing wallet
        local address_response=$(call_wallet "get_address" "{\"account_index\":0}")
        log "Get address attempt $((attempts + 1)): $address_response"
        
        # Check if we got a valid response
        if [[ ! "$address_response" =~ "error" ]] && [[ "$address_response" =~ "address" ]]; then
            # Extract the address from the response
            local address=$(echo "$address_response" | sed -n 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
            
            if [[ -n "$address" ]]; then
                log "Successfully retrieved mining wallet address: $address"
                echo "$address"
                return 0
            fi
        fi
        
        log "Wallet not ready yet, waiting 2s... (attempt $((attempts + 1))/$max_attempts)"
        sleep 2
        attempts=$((attempts + 1))
    done
    
    log "Failed to get wallet address after $max_attempts attempts"
    return 1
}

# Wait for daemon to be ready
wait_for_daemon() {
    log "Waiting for daemon to be ready..."
    while true; do
        local response=$(call_daemon "get_info" "{}")
        if [[ "$response" =~ "status".*"OK" ]]; then
            log "Daemon is ready!"
            return 0
        fi
        log "Daemon not ready yet, waiting 2s... (response: ${response:0:100})"
        sleep 2
    done
}

# Wait for wallet RPC to be ready
wait_for_wallet() {
    log "Waiting for wallet RPC to be ready..."
    while true; do
        local response=$(call_wallet "get_version" "{}")
        if [[ "$response" =~ "version" ]]; then
            log "Wallet RPC is ready"
            return 0
        fi
        log "Wallet RPC not ready yet, waiting 2s..."
        sleep 2
    done
}

# Function to generate blocks
generate_blocks() {
    local daemon_url="$1"
    local wallet_address="$2"
    
    log "Sending generateblocks request to $daemon_url with address $wallet_address"
    
    # Send the generateblocks request
    local response=$(curl -s --max-time 30 "$daemon_url/json_rpc" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"generateblocks\",\"params\":{\"wallet_address\":\"$wallet_address\",\"amount_of_blocks\":1}}" \
        -H 'Content-Type: application/json' 2>/dev/null)
    
    log "Generate blocks response: $response"
    
    # Check if we got any response at all
    if [[ -z "$response" ]]; then
        log "No response from daemon"
        return 1
    fi
    
    # Check if the response contains height (successful generation)
    if echo "$response" | grep -q '"height"'; then
        log "✅ Block generation successful!"
        return 0
    elif echo "$response" | grep -q '"error"'; then
        log "❌ Daemon returned error response"
        return 1
    elif echo "$response" | grep -q 'BUSY\|busy'; then
        log "⏳ Daemon is busy, will retry"
        return 1
    elif echo "$response" | grep -q 'Block not accepted'; then
        log "❌ Block not accepted by daemon"
        return 1
    else
        log "⚠️ Unexpected response format: $response"
        return 1
    fi
}

# Main execution
log "Starting MoneroSim Block Controller"

# Wait for services to be ready
wait_for_daemon
wait_for_wallet

# Create mining wallet and get address
MINING_ADDRESS=$(create_mining_wallet 2>/dev/null | tail -1)
if [[ $? -ne 0 ]] || [[ -z "$MINING_ADDRESS" ]]; then
    log "Failed to create mining wallet, exiting"
    exit 1
fi

log "Using mining address: $MINING_ADDRESS"

# Configuration for block generation
BLOCKS_PER_INTERVAL=1
INTERVAL_SECONDS=60

# Main block generation loop - generate blocks for 2 hours (120 blocks at 1/minute)
log "Starting block generation loop - generating 120 blocks at 1 block/minute"
TARGET_BLOCKS=120
GENERATED_BLOCKS=0

while [[ $GENERATED_BLOCKS -lt $TARGET_BLOCKS ]]; do
    # Attempt to generate blocks with retries when daemon is busy
    ATTEMPT=0
    MAX_ATTEMPTS=5
    SUCCESS=0
    while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
        if generate_blocks "http://${DAEMON_IP}:${DAEMON_RPC_PORT}" "$MINING_ADDRESS"; then
            SUCCESS=1
            break
        else
            ATTEMPT=$((ATTEMPT + 1))
            log "Daemon returned BUSY (attempt $ATTEMPT/$MAX_ATTEMPTS), retrying in 2s..."
            sleep 2
        fi
    done
    
    if [[ $SUCCESS -eq 1 ]]; then
        GENERATED_BLOCKS=$((GENERATED_BLOCKS + BLOCKS_PER_INTERVAL))
        log "Successfully generated block(s). Total generated: $GENERATED_BLOCKS/$TARGET_BLOCKS"
        
        # Wait for the next interval (1 minute)
        if [[ $GENERATED_BLOCKS -lt $TARGET_BLOCKS ]]; then
            log "Waiting ${INTERVAL_SECONDS}s for next block generation..."
            sleep $INTERVAL_SECONDS
        fi
    else
        log "Failed to generate blocks after $MAX_ATTEMPTS attempts. Waiting ${INTERVAL_SECONDS}s before trying again..."
        sleep $INTERVAL_SECONDS
    fi
done

log "Block generation completed. Generated $GENERATED_BLOCKS blocks total." 