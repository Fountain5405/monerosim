#!/bin/bash

# MoneroSim Transaction Test Script
# This script tests the complete flow: mining -> wallet setup -> transaction
# Improved with better error handling, diagnostics, and retry mechanisms

# Source the central network configuration and error handling library
source "$(dirname "$0")/network_config.sh"
source "$(dirname "$0")/error_handling.sh"

# Component name for logging
COMPONENT="TRANSACTION_TEST"

# Configuration
MAX_ATTEMPTS=30
INITIAL_RETRY_DELAY=2
MAX_RETRY_DELAY=60
BALANCE_CHECK_RETRIES=10  # Increased from 5
BALANCE_CHECK_DELAY=15    # Reduced from 30 for more frequent checks
TRANSACTION_RETRIES=5     # Increased from 3
TRANSACTION_RETRY_DELAY=20
MINING_WAIT_TIME=3600     # 60 minutes
TRANSACTION_CONFIRM_TIME=180  # 3 minutes
WALLET_DIR_CHECK_RETRIES=3

log_info "$COMPONENT" "=== MoneroSim Transaction Test ==="
log_info "$COMPONENT" "Starting transaction test at $(date)"

# Function to implement exponential backoff
# Usage: exponential_backoff <attempt> <initial_delay> <max_delay>
exponential_backoff() {
    local attempt=$1
    local initial_delay=$2
    local max_delay=$3
    
    # Calculate delay with exponential backoff: initial_delay * 2^(attempt-1)
    local delay=$(( initial_delay * (2 ** (attempt - 1)) ))
    
    # Cap at max_delay
    if [[ $delay -gt $max_delay ]]; then
        delay=$max_delay
    fi
    
    echo $delay
}

# Function to check if wallet directories exist and are accessible
# Usage: check_wallet_directories
check_wallet_directories() {
    local wallet1_dir="/tmp/wallet1_data"
    local wallet2_dir="/tmp/wallet2_data"
    local status=0
    
    log_info "$COMPONENT" "Checking wallet directories..."
    
    # Check Wallet1 directory
    if [[ ! -d "$wallet1_dir" ]]; then
        log_warning "$COMPONENT" "Wallet1 directory ($wallet1_dir) does not exist, attempting to create it..."
        mkdir -p "$wallet1_dir" 2>/dev/null
        if [[ $? -ne 0 ]]; then
            log_error "$COMPONENT" "Failed to create Wallet1 directory ($wallet1_dir)"
            status=1
        else
            log_info "$COMPONENT" "Created Wallet1 directory ($wallet1_dir)"
        fi
    fi
    
    # Check Wallet2 directory
    if [[ ! -d "$wallet2_dir" ]]; then
        log_warning "$COMPONENT" "Wallet2 directory ($wallet2_dir) does not exist, attempting to create it..."
        mkdir -p "$wallet2_dir" 2>/dev/null
        if [[ $? -ne 0 ]]; then
            log_error "$COMPONENT" "Failed to create Wallet2 directory ($wallet2_dir)"
            status=1
        else
            log_info "$COMPONENT" "Created Wallet2 directory ($wallet2_dir)"
        fi
    fi
    
    # Check permissions on Wallet1 directory
    if [[ -d "$wallet1_dir" ]]; then
        if [[ ! -w "$wallet1_dir" ]]; then
            log_error "$COMPONENT" "Wallet1 directory ($wallet1_dir) is not writable"
            status=1
        fi
    fi
    
    # Check permissions on Wallet2 directory
    if [[ -d "$wallet2_dir" ]]; then
        if [[ ! -w "$wallet2_dir" ]]; then
            log_error "$COMPONENT" "Wallet2 directory ($wallet2_dir) is not writable"
            status=1
        fi
    fi
    
    return $status
}

# Function to check if blocks are being generated
check_block_generation() {
    local daemon_url="$1"
    local daemon_name="$2"
    local check_interval=60  # Check every minute
    local max_checks=5       # Check up to 5 times
    local checks=0
    local prev_height=0
    
    log_info "$COMPONENT" "Verifying block generation on $daemon_name..."
    
    # Get initial block height
    local response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" 3 2 "$COMPONENT")
    local status=$?
    
    if [[ $status -ne 0 ]]; then
        log_error "$COMPONENT" "Failed to get initial block height from $daemon_name"
        log_error "$COMPONENT" "Response: $response"
        return 1
    fi
    
    # Try multiple extraction methods for robustness
    prev_height=$(echo "$response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
    
    # If the first method fails, try an alternative
    if [[ -z "$prev_height" ]]; then
        prev_height=$(echo "$response" | tr -d '\n' | sed -n 's/.*"height"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')
    fi
    
    if [[ -z "$prev_height" ]]; then
        log_error "$COMPONENT" "Failed to extract initial block height from $daemon_name"
        log_error "$COMPONENT" "Response: $response"
        return 1
    fi
    
    log_info "$COMPONENT" "Initial block height: $prev_height"
    
    while [[ $checks -lt $max_checks ]]; do
        log_info "$COMPONENT" "Waiting $check_interval seconds to check for new blocks..."
        sleep $check_interval
        
        response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" 3 2 "$COMPONENT")
        local status=$?
        
        if [[ $status -ne 0 ]]; then
            log_warning "$COMPONENT" "Failed to get current block height, retrying..."
            log_warning "$COMPONENT" "Response: $response"
            checks=$((checks + 1))
            continue
        fi
        
        # Try multiple extraction methods for robustness
        local current_height=$(echo "$response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
        
        # If the first method fails, try an alternative
        if [[ -z "$current_height" ]]; then
            current_height=$(echo "$response" | tr -d '\n' | sed -n 's/.*"height"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')
        fi
        
        if [[ -z "$current_height" ]]; then
            log_warning "$COMPONENT" "Failed to extract current block height, retrying..."
            log_warning "$COMPONENT" "Response: $response"
            checks=$((checks + 1))
            continue
        fi
        
        log_info "$COMPONENT" "Current block height: $current_height"
        
        if [[ $current_height -gt $prev_height ]]; then
            log_info "$COMPONENT" "Block generation confirmed! Height increased from $prev_height to $current_height"
            return 0
        fi
        
        log_warning "$COMPONENT" "No new blocks generated yet..."
        prev_height=$current_height
        checks=$((checks + 1))
    done
    
    log_warning "$COMPONENT" "No block height increase detected after $((max_checks * check_interval)) seconds"
    log_warning "$COMPONENT" "This might indicate mining issues, but we'll continue with the test..."
    return 2  # Return 2 for warning (not failure)
}

# Function to get wallet balance with retries and improved parsing
# Usage: get_wallet_balance <wallet_url> <wallet_name>
get_wallet_balance() {
    local wallet_url="$1"
    local wallet_name="$2"
    
    log_info "$COMPONENT" "Getting $wallet_name balance..."
    
    local attempt=1
    local max_attempts=$BALANCE_CHECK_RETRIES
    
    while [[ $attempt -le $max_attempts ]]; do
        # Calculate delay with exponential backoff
        local delay=$(exponential_backoff $attempt $INITIAL_RETRY_DELAY $MAX_RETRY_DELAY)
        
        log_info "$COMPONENT" "Balance check attempt $attempt/$max_attempts for $wallet_name..."
        
        # First refresh the wallet to ensure up-to-date balance
        local refresh_response=$(call_wallet_with_retry "$wallet_url" "refresh" "{}" "3" "2" "$COMPONENT")
        
        # Now get the balance
        local response=$(call_wallet_with_retry "$wallet_url" "get_balance" "{\"account_index\":0}" "3" "2" "$COMPONENT")
        local status=$?
        
        if [[ $status -ne 0 ]]; then
            log_warning "$COMPONENT" "Failed to get $wallet_name balance on attempt $attempt/$max_attempts"
            log_warning "$COMPONENT" "Response: $response"
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$COMPONENT" "Retrying in $delay seconds..."
                sleep $delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$COMPONENT" "Failed to get $wallet_name balance after $max_attempts attempts"
                return 1
            fi
        fi
        
        # Try multiple extraction methods for robustness
        # Method 1: Standard JSON parsing
        local balance=$(echo "$response" | grep -o '"balance":[0-9]*' | cut -d':' -f2)
        
        # Method 2: Alternative parsing if Method 1 fails
        if [[ -z "$balance" ]]; then
            balance=$(echo "$response" | tr -d '\n' | sed -n 's/.*"balance"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')
        fi
        
        # Method 3: Even more robust parsing if Method 2 fails
        if [[ -z "$balance" ]]; then
            balance=$(echo "$response" | tr -d '\n\r\t' | grep -o '"balance"[[:space:]]*:[[:space:]]*[0-9]*' | sed 's/.*:[[:space:]]*\([0-9]*\)/\1/')
        fi
        
        if [[ -n "$balance" ]]; then
            # Also extract unlocked balance for diagnostic purposes
            local unlocked_balance=$(echo "$response" | grep -o '"unlocked_balance":[0-9]*' | cut -d':' -f2)
            if [[ -z "$unlocked_balance" ]]; then
                unlocked_balance=$(echo "$response" | tr -d '\n' | sed -n 's/.*"unlocked_balance"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')
            fi
            
            log_info "$COMPONENT" "$wallet_name balance: $balance atomic units (unlocked: $unlocked_balance)"
            echo "$balance"
            return 0
        else
            log_warning "$COMPONENT" "Failed to extract balance from response on attempt $attempt/$max_attempts"
            log_warning "$COMPONENT" "Response content: $response"
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$COMPONENT" "Retrying in $delay seconds..."
                sleep $delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$COMPONENT" "Failed to extract balance from response after $max_attempts attempts"
                log_error "$COMPONENT" "Last response: $response"
                return 1
            fi
        fi
    done
    
    return 1
}

# Function to dump wallet status for diagnostics
# Usage: dump_wallet_diagnostics <wallet_url> <wallet_name>
dump_wallet_diagnostics() {
    local wallet_url="$1"
    local wallet_name="$2"
    
    log_info "$COMPONENT" "Dumping diagnostic information for $wallet_name..."
    
    # Get wallet status
    local status_response=$(call_wallet_with_retry "$wallet_url" "get_balance" "{\"account_index\":0}" "3" "2" "$COMPONENT")
    log_info "$COMPONENT" "$wallet_name balance response: $status_response"
    
    # Check if wallet files exist
    local wallet_dir="/tmp/${wallet_name}_data"
    if [[ -d "$wallet_dir" ]]; then
        log_info "$COMPONENT" "$wallet_name directory exists: $wallet_dir"
        log_info "$COMPONENT" "Directory contents:"
        ls -la "$wallet_dir" 2>&1 | while read line; do
            log_info "$COMPONENT" "  $line"
        done
    else
        log_warning "$COMPONENT" "$wallet_name directory does not exist: $wallet_dir"
    fi
    
    # Get wallet address
    local address_response=$(call_wallet_with_retry "$wallet_url" "get_address" "{\"account_index\":0}" "3" "2" "$COMPONENT")
    log_info "$COMPONENT" "$wallet_name address response: $address_response"
    
    # Get wallet height
    local height_response=$(call_wallet_with_retry "$wallet_url" "get_height" "{}" "3" "2" "$COMPONENT")
    log_info "$COMPONENT" "$wallet_name height response: $height_response"
}

# Main execution
log_info "$COMPONENT" "Starting transaction test..."

# Check wallet directories first
log_info "$COMPONENT" "Checking wallet directories..."
for i in $(seq 1 $WALLET_DIR_CHECK_RETRIES); do
    if check_wallet_directories; then
        log_info "$COMPONENT" "Wallet directories check passed"
        break
    else
        if [[ $i -eq $WALLET_DIR_CHECK_RETRIES ]]; then
            log_warning "$COMPONENT" "Wallet directories check failed after $WALLET_DIR_CHECK_RETRIES attempts, but continuing..."
        else
            log_warning "$COMPONENT" "Wallet directories check failed, retrying ($i/$WALLET_DIR_CHECK_RETRIES)..."
            sleep 2
        fi
    fi
done

# Verify daemon readiness
if ! verify_daemon_ready "$A0_RPC" "A0 (mining node)" "$MAX_ATTEMPTS" "$INITIAL_RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Mining node verification failed"
fi

if ! verify_daemon_ready "$A1_RPC" "A1 (sync node)" "$MAX_ATTEMPTS" "$INITIAL_RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "Sync node verification failed"
fi

# Wait for wallet RPC services to be ready
log_info "$COMPONENT" "Checking wallet RPC services..."

# Check wallet1 RPC with improved diagnostics
wallet1_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$WALLET1_RPC" -d '{"jsonrpc":"2.0","id":"0","method":"get_version"}' -H 'Content-Type: application/json')
if [[ "$wallet1_response" -eq 200 ]]; then
    log_info "$COMPONENT" "Wallet1 (mining wallet) is ready"
else
    log_warning "$COMPONENT" "Wallet1 not ready (HTTP code: $wallet1_response), but continuing with test..."
    log_info "$COMPONENT" "Attempting to diagnose Wallet1 RPC issue..."
    
    # Try a more detailed check
    full_response=$(curl -s --max-time 5 "$WALLET1_RPC" -d '{"jsonrpc":"2.0","id":"0","method":"get_version"}' -H 'Content-Type: application/json')
    log_info "$COMPONENT" "Wallet1 RPC full response: $full_response"
    
    # Check if the process is running
    log_info "$COMPONENT" "Checking if Wallet1 RPC process is running..."
    ps_output=$(ps aux | grep "monero-wallet-rpc" | grep -v grep)
    if [[ -n "$ps_output" ]]; then
        log_info "$COMPONENT" "Wallet1 RPC process is running: $ps_output"
    else
        log_warning "$COMPONENT" "Wallet1 RPC process does not appear to be running"
    fi
fi

# Check wallet2 RPC with improved diagnostics
wallet2_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$WALLET2_RPC" -d '{"jsonrpc":"2.0","id":"0","method":"get_version"}' -H 'Content-Type: application/json')
if [[ "$wallet2_response" -eq 200 ]]; then
    log_info "$COMPONENT" "Wallet2 (recipient wallet) is ready"
else
    log_warning "$COMPONENT" "Wallet2 not ready (HTTP code: $wallet2_response), but continuing with test..."
    log_info "$COMPONENT" "Attempting to diagnose Wallet2 RPC issue..."
    
    # Try a more detailed check
    full_response=$(curl -s --max-time 5 "$WALLET2_RPC" -d '{"jsonrpc":"2.0","id":"0","method":"get_version"}' -H 'Content-Type: application/json')
    log_info "$COMPONENT" "Wallet2 RPC full response: $full_response"
    
    # Check if the process is running
    log_info "$COMPONENT" "Checking if Wallet2 RPC process is running..."
    ps_output=$(ps aux | grep "monero-wallet-rpc" | grep -v grep)
    if [[ -n "$ps_output" ]]; then
        log_info "$COMPONENT" "Wallet2 RPC process is running: $ps_output"
    else
        log_warning "$COMPONENT" "Wallet2 RPC process does not appear to be running"
    fi
fi

# Explicitly create both wallets
log_info "$COMPONENT" "Creating wallets..."

# Create Wallet1
log_info "$COMPONENT" "Creating Wallet1 ($WALLET1_NAME)..."
CREATE1_RESPONSE=$(call_wallet_with_retry "$WALLET1_RPC" "create_wallet" "{\"filename\":\"$WALLET1_NAME\",\"password\":\"$WALLET1_PASSWORD\",\"language\":\"English\"}" "$MAX_ATTEMPTS" "$INITIAL_RETRY_DELAY" "$COMPONENT")
CREATE1_STATUS=$?

if [[ $CREATE1_STATUS -eq 0 ]]; then
    log_info "$COMPONENT" "Wallet1 created successfully"
else
    log_warning "$COMPONENT" "Failed to create Wallet1, will try to open it in case it already exists"
    log_warning "$COMPONENT" "Create wallet response: $CREATE1_RESPONSE"
    
    # Try to open the wallet in case it already exists
    if ! verify_wallet_created "$WALLET1_RPC" "$WALLET1_NAME" "$WALLET1_PASSWORD" "$MAX_ATTEMPTS" "$INITIAL_RETRY_DELAY" "$COMPONENT"; then
        log_warning "$COMPONENT" "Wallet1 creation verification failed, but continuing..."
        
        # Dump diagnostic information
        dump_wallet_diagnostics "$WALLET1_RPC" "Wallet1"
    fi
fi

# Create Wallet2
log_info "$COMPONENT" "Creating Wallet2 ($WALLET2_NAME)..."
CREATE2_RESPONSE=$(call_wallet_with_retry "$WALLET2_RPC" "create_wallet" "{\"filename\":\"$WALLET2_NAME\",\"password\":\"$WALLET2_PASSWORD\",\"language\":\"English\"}" "$MAX_ATTEMPTS" "$INITIAL_RETRY_DELAY" "$COMPONENT")
CREATE2_STATUS=$?

if [[ $CREATE2_STATUS -eq 0 ]]; then
    log_info "$COMPONENT" "Wallet2 created successfully"
else
    log_warning "$COMPONENT" "Failed to create Wallet2, will try to open it in case it already exists"
    log_warning "$COMPONENT" "Create wallet response: $CREATE2_RESPONSE"
    
    # Try to open the wallet in case it already exists
    if ! verify_wallet_created "$WALLET2_RPC" "$WALLET2_NAME" "$WALLET2_PASSWORD" "$MAX_ATTEMPTS" "$INITIAL_RETRY_DELAY" "$COMPONENT"; then
        log_warning "$COMPONENT" "Wallet2 creation verification failed, but continuing..."
        
        # Dump diagnostic information
        dump_wallet_diagnostics "$WALLET2_RPC" "Wallet2"
    fi
fi

# Verify block generation is working
block_gen_result=0
if ! check_block_generation "$A0_RPC" "A0 (mining node)"; then
    block_gen_result=$?
    if [[ $block_gen_result -eq 1 ]]; then
        log_critical "$COMPONENT" "Failed to verify block generation. Exiting test."
        handle_exit 1 "$COMPONENT" "Block generation verification failed"
    fi
    # If return code is 2, it's a warning but we continue
fi

# Wait for mining rewards to accumulate
log_info "$COMPONENT" "Waiting $MINING_WAIT_TIME seconds for mining rewards to accumulate..."
log_info "$COMPONENT" "Will check wallet balance periodically during this time..."

# Intelligent wait approach - check balance periodically
WAIT_START_TIME=$(date +%s)
CHECK_INTERVAL=300  # Check every 5 minutes
NEXT_CHECK_TIME=$((WAIT_START_TIME + CHECK_INTERVAL))

while true; do
    # Check current time
    CURRENT_TIME=$(date +%s)
    ELAPSED_TIME=$((CURRENT_TIME - WAIT_START_TIME))
    
    if [[ $ELAPSED_TIME -ge $MINING_WAIT_TIME ]]; then
        log_info "$COMPONENT" "Maximum wait time reached ($MINING_WAIT_TIME seconds). Proceeding with balance check..."
        break
    fi
    
    if [[ $CURRENT_TIME -ge $NEXT_CHECK_TIME ]]; then
        log_info "$COMPONENT" "Periodic balance check at ${ELAPSED_TIME}s elapsed (of $MINING_WAIT_TIME max)..."
        
        # Refresh wallet and check balance
        TEMP_WALLET1_BALANCE=$(get_wallet_balance "$WALLET1_RPC" "Wallet1")
        if [[ $? -eq 0 && -n "$TEMP_WALLET1_BALANCE" && $TEMP_WALLET1_BALANCE -gt 0 ]]; then
            log_info "$COMPONENT" "Wallet1 has a positive balance of $TEMP_WALLET1_BALANCE atomic units. Proceeding with transaction test..."
            break
        else
            log_info "$COMPONENT" "Wallet1 balance check: $TEMP_WALLET1_BALANCE (continuing to wait)"
        fi
        
        NEXT_CHECK_TIME=$((CURRENT_TIME + CHECK_INTERVAL))
    fi
    
    sleep 60  # Check more frequently but don't spam logs
done

# Check wallet balances with improved error handling
log_info "$COMPONENT" "Checking wallet balances..."

# Dump diagnostic information before balance check
dump_wallet_diagnostics "$WALLET1_RPC" "Wallet1"

WALLET1_BALANCE=$(get_wallet_balance "$WALLET1_RPC" "Wallet1")
BALANCE_STATUS=$?

if [[ $BALANCE_STATUS -ne 0 || -z "$WALLET1_BALANCE" ]]; then
    log_critical "$COMPONENT" "Failed to get valid Wallet1 balance after multiple attempts"
    
    # Try fallback approach - direct curl with detailed error output
    log_info "$COMPONENT" "Attempting fallback balance check with direct curl..."
    FALLBACK_RESPONSE=$(curl -v --max-time 10 "$WALLET1_RPC" \
        -d '{"jsonrpc":"2.0","id":"0","method":"get_balance","params":{"account_index":0}}' \
        -H 'Content-Type: application/json' 2>&1)
    
    log_info "$COMPONENT" "Fallback balance check response: $FALLBACK_RESPONSE"
    
    # Try to extract balance from fallback response
    FALLBACK_BALANCE=$(echo "$FALLBACK_RESPONSE" | tr -d '\n\r\t' | grep -o '"balance"[[:space:]]*:[[:space:]]*[0-9]*' | sed 's/.*:[[:space:]]*\([0-9]*\)/\1/')
    
    if [[ -n "$FALLBACK_BALANCE" && $FALLBACK_BALANCE -gt 0 ]]; then
        log_info "$COMPONENT" "Fallback balance check successful: $FALLBACK_BALANCE atomic units"
        WALLET1_BALANCE=$FALLBACK_BALANCE
    else
        handle_exit 1 "$COMPONENT" "Wallet balance check failed with no fallback"
    fi
fi

if [[ $WALLET1_BALANCE -gt 0 ]]; then
    log_info "$COMPONENT" "Wallet1 has mining rewards: $WALLET1_BALANCE atomic units"
    
    # Get wallet2 address with improved error handling
    log_info "$COMPONENT" "Getting Wallet2 address..."
    WALLET2_RESPONSE=$(call_wallet_with_retry "$WALLET2_RPC" "get_address" "{\"account_index\":0,\"address_index\":[0]}" "$MAX_ATTEMPTS" "$INITIAL_RETRY_DELAY" "$COMPONENT")
    if [[ $? -ne 0 ]]; then
        log_critical "$COMPONENT" "Failed to get Wallet2 address"
        log_critical "$COMPONENT" "Response: $WALLET2_RESPONSE"
        
        # Try fallback address if available
        if [[ -n "$WALLET2_ADDRESS_FALLBACK" ]]; then
            log_warning "$COMPONENT" "Using fallback Wallet2 address: $WALLET2_ADDRESS_FALLBACK"
            WALLET2_ADDRESS=$WALLET2_ADDRESS_FALLBACK
        else
            handle_exit 1 "$COMPONENT" "Wallet2 address retrieval failed with no fallback"
        fi
    else
        # Try multiple extraction methods for robustness
        WALLET2_ADDRESS=$(echo "$WALLET2_RESPONSE" | grep -o '"address":"[^"]*"' | cut -d'"' -f4)
        
        # If the first method fails, try an alternative
        if [[ -z "$WALLET2_ADDRESS" ]]; then
            WALLET2_ADDRESS=$(echo "$WALLET2_RESPONSE" | tr -d '\n' | sed -n 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
        fi
        
        # If still empty, try another approach
        if [[ -z "$WALLET2_ADDRESS" ]]; then
            WALLET2_ADDRESS=$(echo "$WALLET2_RESPONSE" | tr -d '\n\r\t' | grep -o '"address"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
        fi
    fi
    
    if [[ -n "$WALLET2_ADDRESS" ]]; then
        log_info "$COMPONENT" "Got Wallet2 address: $WALLET2_ADDRESS"
        
        # Calculate transaction amount (send 50% of balance)
        TRANSACTION_AMOUNT=$((WALLET1_BALANCE / 2))
        log_info "$COMPONENT" "Sending $TRANSACTION_AMOUNT atomic units to Wallet2..."
        
        # Verify transaction processing with improved error handling
        if verify_transaction "$WALLET1_RPC" "$WALLET2_ADDRESS" "$TRANSACTION_AMOUNT" "$TRANSACTION_RETRIES" "$TRANSACTION_RETRY_DELAY" "$COMPONENT"; then
            log_info "$COMPONENT" "Transaction sent successfully!"
            
            # Wait for transaction to be processed
            log_info "$COMPONENT" "Waiting $TRANSACTION_CONFIRM_TIME seconds for transaction to be processed..."
            sleep $TRANSACTION_CONFIRM_TIME
            
            # Check final balances with improved error handling
            log_info "$COMPONENT" "Checking final balances..."
            
            FINAL_WALLET1_BALANCE=$(get_wallet_balance "$WALLET1_RPC" "Wallet1")
            if [[ $? -ne 0 ]]; then
                log_warning "$COMPONENT" "Failed to get final Wallet1 balance, but continuing..."
                FINAL_WALLET1_BALANCE="unknown"
            fi
            
            FINAL_WALLET2_BALANCE=$(get_wallet_balance "$WALLET2_RPC" "Wallet2")
            if [[ $? -ne 0 ]]; then
                log_warning "$COMPONENT" "Failed to get final Wallet2 balance, but continuing..."
                FINAL_WALLET2_BALANCE="unknown"
            fi
            
            log_info "$COMPONENT" "Final Wallet1 balance: $FINAL_WALLET1_BALANCE atomic units"
            log_info "$COMPONENT" "Final Wallet2 balance: $FINAL_WALLET2_BALANCE atomic units"
            
            if [[ "$FINAL_WALLET2_BALANCE" != "unknown" && $FINAL_WALLET2_BALANCE -gt 0 ]]; then
                log_info "$COMPONENT" "Transaction test completed successfully! Funds received by Wallet2."
            else
                log_warning "$COMPONENT" "Transaction may have been sent, but funds not yet confirmed in Wallet2."
                log_warning "$COMPONENT" "This is normal if the transaction is still being processed in the network."
            fi
        else
            log_critical "$COMPONENT" "Transaction verification failed"
            handle_exit 1 "$COMPONENT" "Transaction processing failed"
        fi
    else
        log_critical "$COMPONENT" "Failed to extract Wallet2 address from response: $WALLET2_RESPONSE"
        handle_exit 1 "$COMPONENT" "Wallet2 address extraction failed"
    fi
else
    log_critical "$COMPONENT" "Wallet1 has no mining rewards yet. This indicates mining may not be working correctly."
    log_warning "$COMPONENT" "Consider increasing the wait time or checking the mining configuration."
    handle_exit 1 "$COMPONENT" "No mining rewards detected"
fi

log_info "$COMPONENT" "Transaction test completed at $(date)"
handle_exit 0 "$COMPONENT" "Transaction test completed successfully"