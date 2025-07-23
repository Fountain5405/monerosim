#!/bin/bash

# Central Block Controller Script for MoneroSim
# This script uses the daemon's generateblocks RPC to generate blocks
# Updated for 1 block per 2 minutes generation rate (realistic timing)

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
    
    # Create directory if it doesn't exist
    if [[ ! -d "$wallet_dir" ]]; then
        log_warning "$component" "Wallet directory does not exist, creating it: $wallet_dir"
        mkdir -p "$wallet_dir"
        if [[ $? -ne 0 ]]; then
            log_critical "$component" "Failed to create wallet directory: $wallet_dir"
            return 1
        fi
    fi
    
    # Check if directory is writable
    if [[ ! -w "$wallet_dir" ]]; then
        log_critical "$component" "Wallet directory is not writable: $wallet_dir"
        return 1
    fi
    
    # Set appropriate permissions
    chmod 700 "$wallet_dir"
    if [[ $? -ne 0 ]]; then
        log_warning "$component" "Failed to set permissions on wallet directory, continuing anyway"
    fi
    
    log_info "$component" "Wallet directory verified: $wallet_dir"
    log_info "$component" "Directory contents:"
    ls -la "$wallet_dir" 2>&1 | while read line; do
        log_info "$component" "  $line"
    done
    
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
        # Calculate exponential backoff delay
        local current_delay=$(exponential_backoff $attempt $retry_delay 60)
        
        # First check if the port is open
        if ! nc -z $WALLET1_IP $WALLET1_RPC_PORT; then
            log_warning "$component" "Wallet RPC port not open (attempt $attempt/$max_attempts)"
            sleep $current_delay
            attempt=$((attempt + 1))
            continue
        fi
        
        # Then check if the RPC service is responding
        local ping_result=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$wallet_url" 2>/dev/null)
        
        if [[ "$ping_result" != "200" && "$ping_result" != "405" ]]; then
            log_warning "$component" "Wallet RPC service not responding properly (HTTP code: $ping_result, attempt $attempt/$max_attempts)"
            sleep $current_delay
            attempt=$((attempt + 1))
            continue
        fi
        
        # Finally, check if the service can process a simple request
        local version_response=$(curl -s --max-time 10 "$wallet_url" \
            -d '{"jsonrpc":"2.0","id":"0","method":"get_version","params":{}}' \
            -H 'Content-Type: application/json' 2>&1)
        
        if [[ "$version_response" == *'"result"'* ]]; then
            log_info "$component" "Wallet RPC service is ready"
            return 0
        else
            log_warning "$component" "Wallet RPC service not fully initialized (attempt $attempt/$max_attempts)"
            sleep $current_delay
            attempt=$((attempt + 1))
            continue
        fi
    done
    
    log_critical "$component" "Wallet RPC service not ready after $max_attempts attempts"
    return 1
}

# Function to create or open wallet with robust error handling
create_or_open_wallet() {
    local wallet_url="$1"
    local wallet_name="$2"
    local wallet_password="$3"
    local max_attempts="$4"
    local retry_delay="$5"
    local component="$6"
    
    log_info "$component" "Creating or opening wallet $wallet_name..."
    
    # First try to open the wallet in case it already exists
    log_info "$component" "Attempting to open existing wallet..."
    local open_response=$(call_wallet_with_retry "$wallet_url" "open_wallet" "{\"filename\":\"$wallet_name\",\"password\":\"$wallet_password\"}" "$max_attempts" "$retry_delay" "$component")
    local open_status=$?
    
    if [[ $open_status -eq 0 ]]; then
        log_info "$component" "Wallet $wallet_name opened successfully"
        return 0
    fi
    
    # If opening failed, try to create a new wallet
    log_info "$component" "Opening failed, creating new wallet $wallet_name..."
    local create_response=$(call_wallet_with_retry "$wallet_url" "create_wallet" "{\"filename\":\"$wallet_name\",\"password\":\"$wallet_password\",\"language\":\"English\"}" "$max_attempts" "$retry_delay" "$component")
    local create_status=$?
    
    if [[ $create_status -eq 0 ]]; then
        log_info "$component" "Wallet $wallet_name created successfully"
        return 0
    fi
    
    # If both failed, try to restore from seed (if we have a seed)
    log_error "$component" "Failed to create or open wallet $wallet_name"
    return 1
}

# Function to sanitize and validate a Monero address
# Removes ANSI color codes, log messages, and ensures only a valid address is returned
sanitize_monero_address() {
    local input="$1"
    local component="$2"
    
    # Remove ANSI color codes
    local no_ansi=$(echo "$input" | sed 's/\x1B\[[0-9;]*[JKmsu]//g')
    
    # Extract potential Monero address - standard addresses are 95 characters
    # Monero addresses start with 4 (mainnet) or 8 (testnet)
    local potential_address=$(echo "$no_ansi" | grep -o '[48][a-zA-Z0-9]\{94\}' | head -1)
    
    if [ -z "$potential_address" ]; then
        # Try a more lenient pattern if the strict one fails
        potential_address=$(echo "$no_ansi" | grep -o '[48][a-zA-Z0-9]\{90,110\}' | head -1)
    fi
    
    if [ -n "$potential_address" ]; then
        log_info "$component" "Extracted clean Monero address: $potential_address"
        echo "$potential_address"
        return 0
    else
        log_warning "$component" "Could not extract a valid Monero address pattern from: $no_ansi"
        return 1
    fi
}

# Function to get wallet address with enhanced error handling
get_wallet_address() {
    local wallet_url="$1"
    local max_attempts="$2"
    local retry_delay="$3"
    local component="$4"
    
    log_info "$component" "Getting wallet address..."
    
    local attempt=1
    local wallet_address=""
    local raw_address=""
    
    while [[ $attempt -le $max_attempts ]]; do
        # Calculate exponential backoff delay
        local current_delay=$(exponential_backoff $attempt $retry_delay 60)
        
        # Method 1: Standard get_address call
        log_info "$component" "Getting wallet address (attempt $attempt/$max_attempts, method 1)..."
        local address_response=$(call_wallet_with_retry "$wallet_url" "get_address" "{\"account_index\":0}" "3" "2" "$component")
        
        if [[ $? -eq 0 && -n "$address_response" && "$address_response" == *'"address"'* ]]; then
            # Extract the address with improved parsing
            local flat_response=$(echo "$address_response" | tr -d '\n' | tr -s ' ')
            
            # Try multiple extraction methods
            raw_address=$(echo "$flat_response" | sed -n 's/.*"result"[^{]*{[^}]*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
            
            if [ -z "$raw_address" ]; then
                raw_address=$(echo "$flat_response" | grep -o '"address"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)".*/\1/')
            fi
            
            if [ -n "$raw_address" ]; then
                # Sanitize the address to ensure it's clean
                wallet_address=$(sanitize_monero_address "$raw_address" "$component")
                if [ $? -eq 0 ] && [ -n "$wallet_address" ]; then
                    log_info "$component" "Successfully retrieved and sanitized wallet address: $wallet_address"
                    echo "$wallet_address"
                    return 0
                else
                    log_warning "$component" "Retrieved address failed sanitization: $raw_address"
                fi
            fi
        fi
        
        # Method 2: Try get_address with address_index parameter
        log_info "$component" "Getting wallet address (attempt $attempt/$max_attempts, method 2)..."
        address_response=$(call_wallet_with_retry "$wallet_url" "get_address" "{\"account_index\":0,\"address_index\":[0]}" "3" "2" "$component")
        
        if [[ $? -eq 0 && -n "$address_response" ]]; then
            flat_response=$(echo "$address_response" | tr -d '\n' | tr -s ' ')
            raw_address=$(echo "$flat_response" | grep -o '"address":"[^"]*"' | cut -d'"' -f4)
            
            if [ -n "$raw_address" ]; then
                # Sanitize the address to ensure it's clean
                wallet_address=$(sanitize_monero_address "$raw_address" "$component")
                if [ $? -eq 0 ] && [ -n "$wallet_address" ]; then
                    log_info "$component" "Successfully retrieved and sanitized wallet address (method 2): $wallet_address"
                    echo "$wallet_address"
                    return 0
                else
                    log_warning "$component" "Retrieved address failed sanitization (method 2): $raw_address"
                fi
            fi
        fi
        
        # Method 3: Try to generate a new address
        if [[ $attempt -gt $((max_attempts / 2)) ]]; then
            log_info "$component" "Trying to generate a new address (attempt $attempt/$max_attempts)..."
            local new_address_response=$(call_wallet_with_retry "$wallet_url" "create_address" "{\"account_index\":0}" "3" "2" "$component")
            
            if [[ $? -eq 0 && -n "$new_address_response" ]]; then
                flat_response=$(echo "$new_address_response" | tr -d '\n' | tr -s ' ')
                raw_address=$(echo "$flat_response" | grep -o '"address":"[^"]*"' | cut -d'"' -f4)
                
                if [ -n "$raw_address" ]; then
                    # Sanitize the address to ensure it's clean
                    wallet_address=$(sanitize_monero_address "$raw_address" "$component")
                    if [ $? -eq 0 ] && [ -n "$wallet_address" ]; then
                        log_info "$component" "Successfully generated and sanitized a new wallet address: $wallet_address"
                        echo "$wallet_address"
                        return 0
                    else
                        log_warning "$component" "Generated address failed sanitization: $raw_address"
                    fi
                fi
            fi
        fi
        
        log_warning "$component" "Failed to get wallet address (attempt $attempt/$max_attempts)"
        
        # If we're halfway through our attempts, try reopening the wallet
        if [[ $attempt -eq $((max_attempts / 2)) ]]; then
            log_info "$component" "Reopening wallet before next attempt..."
            call_wallet_with_retry "$wallet_url" "close_wallet" "{}" "3" "2" "$component" > /dev/null
            sleep 2
            call_wallet_with_retry "$wallet_url" "open_wallet" "{\"filename\":\"$WALLET_NAME\",\"password\":\"$WALLET_PASSWORD\"}" "3" "2" "$component" > /dev/null
        fi
        
        attempt=$((attempt + 1))
        sleep $current_delay
    done
    
    log_critical "$component" "Failed to get wallet address after $max_attempts attempts"
    return 1
}

# Main execution starts here
log_info "$COMPONENT" "Starting block controller script"

# Verify daemon readiness
if ! verify_daemon_ready "$DAEMON_URL" "Daemon" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Daemon verification failed"
fi

# Verify and create wallet directory if needed
if ! verify_wallet_directory "$WALLET_DIR" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Wallet directory verification failed"
fi

# Verify wallet RPC service is ready
if ! verify_wallet_rpc_ready "$WALLET_URL" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Wallet RPC service verification failed"
fi

# Create or open wallet with consolidated logic
if ! create_or_open_wallet "$WALLET_URL" "$WALLET_NAME" "$WALLET_PASSWORD" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Wallet creation/opening failed"
fi

# Get wallet address with enhanced error handling
WALLET_ADDRESS=""
if ! WALLET_ADDRESS=$(get_wallet_address "$WALLET_URL" 15 5 "$COMPONENT"); then
    log_critical "$COMPONENT" "Failed to get wallet address"
    
    # Fallback to hardcoded address if available in network_config.sh
    if [ -n "$WALLET1_ADDRESS_FALLBACK" ]; then
        log_warning "$COMPONENT" "Using fallback wallet address: $WALLET1_ADDRESS_FALLBACK"
        WALLET_ADDRESS="$WALLET1_ADDRESS_FALLBACK"
    else
        handle_exit 1 "$COMPONENT" "Address retrieval failed with no fallback available"
    fi
fi

log_info "$COMPONENT" "Using wallet address: $WALLET_ADDRESS"

# Ensure the wallet address is properly sanitized
if [ -n "$WALLET_ADDRESS" ]; then
    # Apply additional sanitization to ensure clean address
    CLEAN_ADDRESS=$(sanitize_monero_address "$WALLET_ADDRESS" "$COMPONENT")
    if [ $? -eq 0 ] && [ -n "$CLEAN_ADDRESS" ]; then
        WALLET_ADDRESS="$CLEAN_ADDRESS"
        log_info "$COMPONENT" "Final sanitized wallet address: $WALLET_ADDRESS"
    else
        log_warning "$COMPONENT" "Final sanitization failed, using best available address: $WALLET_ADDRESS"
        # Last resort basic sanitization
        WALLET_ADDRESS=$(echo "$WALLET_ADDRESS" | tr -d '\n\r' | sed 's/\x1B\[[0-9;]*[JKmsu]//g' | xargs)
    fi
fi

# Start block generation
log_info "$COMPONENT" "Starting block generation with address: $WALLET_ADDRESS"
block_count=0
block_interval=120  # 2 minutes in seconds

while true; do
    log_info "$COMPONENT" "Generating 1 block..."
    
    # Get initial height directly with enhanced error handling
    log_info "$COMPONENT" "Getting initial block height..."
    initial_response=$(curl -s --max-time 10 "$DAEMON_URL" \
        -d '{"jsonrpc":"2.0","id":"0","method":"get_info","params":{}}' \
        -H 'Content-Type: application/json')
    
    if [[ -n "$initial_response" && "$initial_response" == *'"height"'* ]]; then
        initial_height=$(echo "$initial_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
        log_info "$COMPONENT" "Initial block height: $initial_height"
    else
        log_warning "$COMPONENT" "Failed to get initial block height. Response: $initial_response"
        log_warning "$COMPONENT" "Will retry in $block_interval seconds"
        sleep $block_interval
        continue
    fi
    
    # Generate block with direct RPC call for better debugging
    log_info "$COMPONENT" "Directly calling generateblocks RPC..."
    generate_response=$(curl -s --max-time 30 "$DAEMON_URL" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"generateblocks\",\"params\":{\"amount_of_blocks\":1,\"reserve_size\":1,\"wallet_address\":\"$WALLET_ADDRESS\"}}" \
        -H 'Content-Type: application/json')
    
    log_info "$COMPONENT" "Generate blocks response: $generate_response"
    
    if [[ -n "$generate_response" && "$generate_response" == *'"blocks"'* ]]; then
        blocks_generated=$(echo "$generate_response" | grep -o '"blocks":\[[^]]*\]' | grep -o '"[^"]*"' | grep -v "blocks" | tr -d '"' | wc -l)
        log_info "$COMPONENT" "Blocks generated: $blocks_generated"
        
        # Get final height
        sleep 5  # Give some time for the block to be processed
        final_response=$(curl -s --max-time 10 "$DAEMON_URL" \
            -d '{"jsonrpc":"2.0","id":"0","method":"get_info","params":{}}' \
            -H 'Content-Type: application/json')
        
        if [[ -n "$final_response" && "$final_response" == *'"height"'* ]]; then
            final_height=$(echo "$final_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
            log_info "$COMPONENT" "Final block height: $final_height"
            
            # Check if height increased
            if [[ -n "$initial_height" && -n "$final_height" && $final_height -gt $initial_height ]]; then
                block_count=$((block_count + 1))
                log_info "$COMPONENT" "Block generation successful! Height increased from $initial_height to $final_height"
                log_info "$COMPONENT" "Total blocks generated: $block_count"
            else
                log_warning "$COMPONENT" "Block height did not increase as expected. Initial: $initial_height, Final: $final_height"
            fi
        else
            log_warning "$COMPONENT" "Failed to get final block height. Response: $final_response"
        fi
    else
        log_warning "$COMPONENT" "Block generation failed. Response: $generate_response"
    fi
    
    log_info "$COMPONENT" "Waiting $block_interval seconds before generating next block..."
    sleep $block_interval
done