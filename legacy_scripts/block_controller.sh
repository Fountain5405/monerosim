#!/bin/bash

# Central Block Controller Script for MoneroSim
# This script uses the daemon's generateblocks RPC to generate blocks.

# Source the central network configuration and error handling library
source "$(dirname "$0")/network_config.sh"
source "$(dirname "$0")/error_handling.sh"

# Component name for logging
COMPONENT="BLOCK_CONTROLLER"

# Configuration
MAX_ATTEMPTS=30
RETRY_DELAY=2
DAEMON_URL="http://${DAEMON_IP}:${DAEMON_RPC_PORT}/json_rpc"
WALLET_URL="$WALLET1_RPC"
WALLET_NAME="$WALLET1_NAME"
WALLET_PASSWORD="$WALLET1_PASSWORD"
WALLET_DIR="/tmp/wallet1_data"

# Function to calculate exponential backoff delay
exponential_backoff() {
    local attempt=$1
    local base_delay=$2
    local max_delay=$3
    local delay=$(( base_delay * 2 ** (attempt - 1) ))
    echo $(( delay > max_delay ? max_delay : delay ))
}

# Function to verify wallet directory exists and is writable
verify_wallet_directory() {
    local wallet_dir="$1"
    local component="$2"
    
    log_info "$component" "Verifying wallet directory: $wallet_dir"
    
    if [[ ! -d "$wallet_dir" ]]; then
        log_warning "$component" "Wallet directory does not exist, creating it: $wallet_dir"
        mkdir -p "$wallet_dir"
        if [[ $? -ne 0 ]]; then
            log_critical "$component" "Failed to create wallet directory: $wallet_dir"
            return 1
        fi
    fi
    
    if [[ ! -w "$wallet_dir" ]]; then
        log_critical "$component" "Wallet directory is not writable: $wallet_dir"
        return 1
    fi
    
    chmod 700 "$wallet_dir"
    if [[ $? -ne 0 ]]; then
        log_warning "$component" "Failed to set permissions on wallet directory, continuing anyway"
    fi
    
    log_info "$component" "Wallet directory verified: $wallet_dir"
    return 0
}

# Function to verify wallet RPC service is ready
verify_wallet_rpc_ready() {
    local wallet_url="$1"
    local max_attempts="$2"
    local retry_delay="$3"
    local component="$4"
    
    log_info "$component" "Verifying wallet RPC service readiness..."
    
    local attempt=1
    while [[ $attempt -le $max_attempts ]]; do
        local current_delay=$(exponential_backoff $attempt $retry_delay 60)
        
        if nc -z $WALLET1_IP $WALLET1_RPC_PORT; then
            local version_response=$(curl -s --max-time 10 "$wallet_url" \
                -d '{"jsonrpc":"2.0","id":"0","method":"get_version","params":{}}' \
                -H 'Content-Type: application/json' 2>&1)
            
            if echo "$version_response" | jq -e '.result' > /dev/null; then
                log_info "$component" "Wallet RPC service is ready"
                return 0
            fi
        fi
        
        log_warning "$component" "Wallet RPC service not ready (attempt $attempt/$max_attempts)"
        sleep $current_delay
        attempt=$((attempt + 1))
    done
    
    log_critical "$component" "Wallet RPC service not ready after $max_attempts attempts"
    return 1
}

# Function to create a new wallet
create_new_wallet() {
    local wallet_url="$1"
    local wallet_name="$2"
    local wallet_password="$3"
    local component="$4"

    log_info "$component" "Creating a new wallet: $wallet_name..."

    local create_response
    create_response=$(call_wallet_with_retry "$wallet_url" "create_wallet" \
        "{\"filename\":\"$wallet_name\",\"password\":\"$wallet_password\",\"language\":\"English\"}" \
        "$MAX_ATTEMPTS" "$RETRY_DELAY" "$component")

    if echo "$create_response" | jq -e '.result' > /dev/null; then
        log_info "$component" "Successfully created new wallet: $wallet_name"
        return 0
    else
        log_critical "$component" "Failed to create new wallet: $wallet_name"
        log_error "$component" "Create response: $create_response"
        return 1
    fi
}

# Function to get wallet address
get_wallet_address() {
    local wallet_url="$1"
    local component="$2"
    
    log_info "$component" "Getting wallet address..."
    
    local address_response
    address_response=$(call_wallet_with_retry "$wallet_url" "get_address" "{\"account_index\":0}" "3" "2" "$component")
    
    if echo "$address_response" | jq -e '.result.address' > /dev/null; then
        local wallet_address=$(echo "$address_response" | jq -r '.result.address')
        log_info "$component" "Successfully retrieved wallet address: $wallet_address"
        echo "$wallet_address"
        return 0
    else
        log_critical "$component" "Failed to get wallet address"
        log_error "$component" "Address response: $address_response"
        return 1
    fi
}

# Main execution
log_info "$COMPONENT" "Starting block controller script"

if ! verify_daemon_ready "$DAEMON_URL" "Daemon" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Daemon verification failed"
fi

if ! verify_wallet_directory "$WALLET_DIR" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Wallet directory verification failed"
fi

if ! verify_wallet_rpc_ready "$WALLET_URL" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Wallet RPC service verification failed"
fi

if ! create_new_wallet "$WALLET_URL" "$WALLET_NAME" "$WALLET_PASSWORD" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Wallet creation failed"
fi

WALLET_ADDRESS=$(get_wallet_address "$WALLET_URL" "$COMPONENT")
if [ -z "$WALLET_ADDRESS" ]; then
    handle_exit 1 "$COMPONENT" "Failed to get wallet address"
fi

log_info "$COMPONENT" "Using wallet address: $WALLET_ADDRESS"

# Start block generation
log_info "$COMPONENT" "Starting block generation with address: $WALLET_ADDRESS"
block_count=0
block_interval=120  # 2 minutes in seconds

while true; do
    log_info "$COMPONENT" "Generating 1 block..."
    
    initial_height_response=$(curl -s --max-time 10 "$DAEMON_URL" -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' -H 'Content-Type: application/json')
    initial_height=$(echo "$initial_height_response" | jq -r '.result.height')

    if [ -z "$initial_height" ]; then
        log_warning "$COMPONENT" "Failed to get initial block height. Retrying..."
        sleep $block_interval
        continue
    fi

    log_info "$COMPONENT" "Initial block height: $initial_height"
    
    generate_response=$(curl -s --max-time 30 "$DAEMON_URL" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"generateblocks\",\"params\":{\"amount_of_blocks\":1,\"wallet_address\":\"$WALLET_ADDRESS\"}}" \
        -H 'Content-Type: application/json')

    log_info "$COMPONENT" "Generate blocks response: $generate_response"
    
    if echo "$generate_response" | jq -e '.result.blocks' > /dev/null; then
        final_height=$(echo "$generate_response" | jq -r '.result.height')
        log_info "$COMPONENT" "Block generation successful! New height: $final_height"
        block_count=$((block_count + 1))
    else
        log_warning "$COMPONENT" "Block generation failed."
    fi
    
    log_info "$COMPONENT" "Total blocks generated in this session: $block_count"
    log_info "$COMPONENT" "Waiting $block_interval seconds for the next block..."
    sleep $block_interval
done