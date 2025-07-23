#!/bin/bash

# error_handling.sh - Standardized error handling library for MoneroSim
# This library provides common error handling, logging, retry mechanisms,
# and verification functions for critical processes.

# ===== ERROR LOGGING FUNCTIONS =====

# Color codes for terminal output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Error severity levels
LEVEL_INFO="INFO"
LEVEL_WARNING="WARNING"
LEVEL_ERROR="ERROR"
LEVEL_CRITICAL="CRITICAL"

# Function to log messages with timestamp and severity level
# Usage: log_message <severity_level> <component> <message>
log_message() {
    local level="$1"
    local component="$2"
    local message="$3"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Set color based on severity level
    local color=""
    case "$level" in
        "$LEVEL_INFO")
            color="$GREEN"
            ;;
        "$LEVEL_WARNING")
            color="$YELLOW"
            ;;
        "$LEVEL_ERROR")
            color="$RED"
            ;;
        "$LEVEL_CRITICAL")
            color="$PURPLE"
            ;;
        *)
            color="$BLUE"
            ;;
    esac
    
    echo -e "${color}${timestamp} [${level}] [${component}] ${message}${NC}"
    
    # If this is a critical error, also log to a file
    if [[ "$level" == "$LEVEL_CRITICAL" || "$level" == "$LEVEL_ERROR" ]]; then
        echo "${timestamp} [${level}] [${component}] ${message}" >> "monerosim_errors.log"
    fi
}

# Convenience functions for different severity levels
log_info() {
    local component="$1"
    local message="$2"
    log_message "$LEVEL_INFO" "$component" "$message"
}

log_warning() {
    local component="$1"
    local message="$2"
    log_message "$LEVEL_WARNING" "$component" "$message"
}

log_error() {
    local component="$1"
    local message="$2"
    log_message "$LEVEL_ERROR" "$component" "$message"
}

log_critical() {
    local component="$1"
    local message="$2"
    log_message "$LEVEL_CRITICAL" "$component" "$message"
}

# ===== RETRY MECHANISMS =====

# Function to execute a command with retries
# Usage: retry_command <max_attempts> <delay> <command> [args...]
retry_command() {
    local max_attempts="$1"
    local delay="$2"
    local command="$3"
    local component="$4"
    shift 4
    
    local attempt=1
    local output=""
    local status=0
    
    while [[ $attempt -le $max_attempts ]]; do
        log_info "$component" "Attempt $attempt/$max_attempts: $command $*"
        output=$("$command" "$@" 2>&1)
        status=$?
        
        if [[ $status -eq 0 ]]; then
            log_info "$component" "Command succeeded on attempt $attempt"
            echo "$output"
            return 0
        else
            if [[ $attempt -lt $max_attempts ]]; then
                log_warning "$component" "Command failed on attempt $attempt. Retrying in ${delay}s..."
                sleep "$delay"
            else
                log_error "$component" "Command failed after $max_attempts attempts"
                echo "$output"
                return 1
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    return 1
}

# Function to call daemon RPC with retry
# Usage: call_daemon_with_retry <daemon_url> <method> <params> <max_attempts> <delay> <component>
call_daemon_with_retry() {
    local daemon_url="$1"
    local method="$2"
    local params="$3"
    local max_attempts="$4"
    local delay="$5"
    local component="$6"
    
    local attempt=1
    local response=""
    
    while [[ $attempt -le $max_attempts ]]; do
        # Calculate exponential backoff delay
        local current_delay=$(exponential_backoff $attempt $delay 60)
        
        log_info "$component" "RPC call attempt $attempt/$max_attempts: $method"
        
        # Check if the daemon URL is reachable first
        local ping_result=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$daemon_url" 2>/dev/null)
        
        if [[ "$ping_result" != "200" && "$ping_result" != "405" ]]; then
            log_warning "$component" "Daemon URL $daemon_url is not reachable (HTTP code: $ping_result)"
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$component" "Daemon URL $daemon_url is not reachable after $max_attempts attempts"
                echo "ERROR: Daemon URL not reachable"
                return 1
            fi
        fi
        
        # Make the actual RPC call with increased timeout
        response=$(curl -s --max-time 30 "$daemon_url" \
            -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"$method\",\"params\":$params}" \
            -H 'Content-Type: application/json' 2>&1)
        
        # Check for curl errors
        if [[ $? -ne 0 ]]; then
            log_warning "$component" "Curl command failed on attempt $attempt"
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$component" "Curl command failed after $max_attempts attempts"
                echo "ERROR: Curl command failed"
                return 1
            fi
        fi
        
        # Check if the response is empty
        if [[ -z "$response" ]]; then
            log_warning "$component" "Empty response received on attempt $attempt"
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$component" "Empty response received after $max_attempts attempts"
                echo "ERROR: Empty response"
                return 1
            fi
        fi
        
        # Check if the response contains a result field (success)
        if [[ "$response" == *'"result"'* ]]; then
            log_info "$component" "RPC call succeeded on attempt $attempt"
            echo "$response"
            return 0
        # Check if the response contains an error field
        elif [[ "$response" == *'"error"'* ]]; then
            local error_code=$(echo "$response" | grep -o '"code":[0-9-]*' | cut -d':' -f2)
            local error_message=$(echo "$response" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
            
            log_warning "$component" "RPC call returned error on attempt $attempt: code=$error_code, message=$error_message"
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
            else
                log_error "$component" "RPC call failed after $max_attempts attempts: $response"
                echo "$response"
                return 1
            fi
        else
            log_warning "$component" "Invalid response format on attempt $attempt: $response"
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
            else
                log_error "$component" "Invalid response format after $max_attempts attempts: $response"
                echo "$response"
                return 1
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    return 1
}

# Function to call wallet RPC with retry
# Usage: call_wallet_with_retry <wallet_url> <method> <params> <max_attempts> <delay> <component>
call_wallet_with_retry() {
    local wallet_url="$1"
    local method="$2"
    local params="$3"
    local max_attempts="$4"
    local delay="$5"
    local component="$6"
    
    local attempt=1
    local response=""
    
    while [[ $attempt -le $max_attempts ]]; do
        # Calculate exponential backoff delay
        local current_delay=$(exponential_backoff $attempt $delay 60)
        
        log_info "$component" "Wallet RPC call attempt $attempt/$max_attempts: $method"
        
        # Check if the wallet URL is reachable first
        local ping_result=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$wallet_url" 2>/dev/null)
        
        if [[ "$ping_result" != "200" && "$ping_result" != "405" ]]; then
            log_warning "$component" "Wallet URL $wallet_url is not reachable (HTTP code: $ping_result)"
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$component" "Wallet URL $wallet_url is not reachable after $max_attempts attempts"
                echo "ERROR: Wallet URL not reachable"
                return 1
            fi
        fi
        
        # Make the actual RPC call with increased timeout
        response=$(curl -s --max-time 30 "$wallet_url" \
            -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"$method\",\"params\":$params}" \
            -H 'Content-Type: application/json' 2>&1)
        
        # Check for curl errors
        if [[ $? -ne 0 ]]; then
            log_warning "$component" "Curl command failed on attempt $attempt"
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$component" "Curl command failed after $max_attempts attempts"
                echo "ERROR: Curl command failed"
                return 1
            fi
        fi
        
        # Check if the response is empty
        if [[ -z "$response" ]]; then
            log_warning "$component" "Empty response received on attempt $attempt"
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
                attempt=$((attempt + 1))
                continue
            else
                log_error "$component" "Empty response received after $max_attempts attempts"
                echo "ERROR: Empty response"
                return 1
            fi
        fi
        
        # Check if the response contains a result field (success)
        if [[ "$response" == *'"result"'* ]]; then
            log_info "$component" "Wallet RPC call succeeded on attempt $attempt"
            echo "$response"
            return 0
        # Check if the response contains an error field
        elif [[ "$response" == *'"error"'* ]]; then
            local error_code=$(echo "$response" | grep -o '"code":[0-9-]*' | cut -d':' -f2)
            local error_message=$(echo "$response" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
            
            log_warning "$component" "Wallet RPC call returned error on attempt $attempt: code=$error_code, message=$error_message"
            
            # Special handling for specific error codes
            if [[ "$error_code" == "-1" && "$method" == "create_wallet" && "$error_message" == *"already exists"* ]]; then
                # Wallet already exists, try to open it instead
                log_info "$component" "Wallet already exists, trying to open it instead..."
                local wallet_filename=$(echo "$params" | grep -o '"filename":"[^"]*"' | cut -d'"' -f4)
                local wallet_password=$(echo "$params" | grep -o '"password":"[^"]*"' | cut -d'"' -f4)
                
                local open_response=$(curl -s --max-time 30 "$wallet_url" \
                    -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"open_wallet\",\"params\":{\"filename\":\"$wallet_filename\",\"password\":\"$wallet_password\"}}" \
                    -H 'Content-Type: application/json' 2>&1)
                
                if [[ "$open_response" == *'"result"'* ]]; then
                    log_info "$component" "Successfully opened existing wallet"
                    echo "$open_response"
                    return 0
                fi
            fi
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
            else
                log_error "$component" "Wallet RPC call failed after $max_attempts attempts: $response"
                echo "$response"
                return 1
            fi
        else
            log_warning "$component" "Invalid response format on attempt $attempt: $response"
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "$component" "Retrying in $current_delay seconds..."
                sleep $current_delay
            else
                log_error "$component" "Invalid response format after $max_attempts attempts: $response"
                echo "$response"
                return 1
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    return 1
}

# ===== VERIFICATION FUNCTIONS =====

# Function to verify daemon readiness
# Usage: verify_daemon_ready <daemon_url> <daemon_name> <max_attempts> <delay> <component>
verify_daemon_ready() {
    local daemon_url="$1"
    local daemon_name="$2"
    local max_attempts="$3"
    local delay="$4"
    local component="$5"
    
    log_info "$component" "Verifying $daemon_name readiness..."
    
    local response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" "$max_attempts" "$delay" "$component")
    local status=$?
    
    if [[ $status -eq 0 ]]; then
        # Extract status and height from response
        local daemon_status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        local height=$(echo "$response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
        
        log_info "$component" "$daemon_name is ready. Status: $daemon_status, Height: $height"
        return 0
    else
        log_critical "$component" "Failed to verify $daemon_name readiness"
        return 1
    fi
}

# Function to verify wallet creation
# Usage: verify_wallet_created <wallet_url> <wallet_name> <wallet_password> <max_attempts> <delay> <component>
verify_wallet_created() {
    local wallet_url="$1"
    local wallet_name="$2"
    local wallet_password="$3"
    local max_attempts="$4"
    local delay="$5"
    local component="$6"
    
    log_info "$component" "Verifying wallet creation for $wallet_name..."
    
    # First check if wallet already exists by trying to open it
    local open_response=$(call_wallet_with_retry "$wallet_url" "open_wallet" "{\"filename\":\"$wallet_name\",\"password\":\"$wallet_password\"}" "$max_attempts" "$delay" "$component")
    local open_status=$?
    
    if [[ $open_status -eq 0 ]]; then
        log_info "$component" "Wallet $wallet_name already exists and was opened successfully"
        return 0
    fi
    
    # If opening failed, try to create a new wallet
    log_info "$component" "Creating new wallet $wallet_name..."
    local create_response=$(call_wallet_with_retry "$wallet_url" "create_wallet" "{\"filename\":\"$wallet_name\",\"password\":\"$wallet_password\",\"language\":\"English\"}" "$max_attempts" "$delay" "$component")
    local create_status=$?
    
    if [[ $create_status -eq 0 ]]; then
        log_info "$component" "Wallet $wallet_name created successfully"
        return 0
    else
        log_critical "$component" "Failed to create wallet $wallet_name"
        return 1
    fi
}

# Function to verify wallet opening
# Usage: verify_wallet_open <wallet_url> <wallet_name> <wallet_password> <max_attempts> <delay> <component>
verify_wallet_open() {
    local wallet_url="$1"
    local wallet_name="$2"
    local wallet_password="$3"
    local max_attempts="$4"
    local delay="$5"
    local component="$6"
    
    log_info "$component" "Verifying wallet opening for $wallet_name..."
    
    local response=$(call_wallet_with_retry "$wallet_url" "open_wallet" "{\"filename\":\"$wallet_name\",\"password\":\"$wallet_password\"}" "$max_attempts" "$delay" "$component")
    local status=$?
    
    if [[ $status -eq 0 ]]; then
        log_info "$component" "Wallet $wallet_name opened successfully"
        
        # Verify we can get the address as an additional check
        local address_response=$(call_wallet_with_retry "$wallet_url" "get_address" "{\"account_index\":0}" "$max_attempts" "$delay" "$component")
        local address_status=$?
        
        if [[ $address_status -eq 0 ]]; then
            local address=$(echo "$address_response" | grep -o '"address":"[^"]*"' | cut -d'"' -f4)
            log_info "$component" "Wallet address verified: $address"
            return 0
        else
            log_warning "$component" "Wallet opened but address verification failed"
            return 0  # Still consider it a success since the wallet opened
        fi
    else
        log_critical "$component" "Failed to open wallet $wallet_name"
        return 1
    fi
}

# Function to verify block generation
# Usage: verify_block_generation <daemon_url> <wallet_address> <num_blocks> <max_attempts> <delay> <component>
verify_block_generation() {
    local daemon_url="$1"
    local wallet_address="$2"
    local num_blocks="$3"
    local max_attempts="$4"
    local delay="$5"
    local component="$6"
    
    log_info "$component" "Verifying block generation..."
    
    # Get initial height
    local initial_response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" "$max_attempts" "$delay" "$component")
    local initial_status=$?
    
    if [[ $initial_status -ne 0 ]]; then
        log_critical "$component" "Failed to get initial block height"
        return 1
    fi
    
    local initial_height=$(echo "$initial_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
    log_info "$component" "Initial block height: $initial_height"
    
    # Generate blocks
    log_info "$component" "Generating $num_blocks blocks..."
    local generate_response=$(call_daemon_with_retry "$daemon_url" "generateblocks" "{\"amount_of_blocks\":$num_blocks,\"reserve_size\":1,\"wallet_address\":\"$wallet_address\"}" "$max_attempts" "$delay" "$component")
    local generate_status=$?
    
    if [[ $generate_status -ne 0 ]]; then
        log_critical "$component" "Failed to generate blocks"
        return 1
    fi
    
    # Extract block hashes
    local blocks_generated=$(echo "$generate_response" | grep -o '"blocks":\[[^]]*\]' | grep -o '"[^"]*"' | grep -v "blocks" | tr -d '"' | wc -l)
    log_info "$component" "Blocks generated: $blocks_generated"
    
    # Verify new height
    local final_response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" "$max_attempts" "$delay" "$component")
    local final_status=$?
    
    if [[ $final_status -ne 0 ]]; then
        log_critical "$component" "Failed to get final block height"
        return 1
    fi
    
    local final_height=$(echo "$final_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
    log_info "$component" "Final block height: $final_height"
    
    # Check if height increased by the expected amount
    local expected_height=$((initial_height + num_blocks))
    if [[ $final_height -ge $expected_height ]]; then
        log_info "$component" "Block generation verified: Height increased from $initial_height to $final_height"
        return 0
    else
        log_error "$component" "Block generation verification failed: Expected height $expected_height, got $final_height"
        return 1
    fi
}

# Function to verify transaction processing
# Usage: verify_transaction <from_wallet_url> <to_address> <amount> <max_attempts> <delay> <component>
verify_transaction() {
    local from_wallet_url="$1"
    local to_address="$2"
    local amount="$3"
    local max_attempts="$4"
    local delay="$5"
    local component="$6"
    
    log_info "$component" "Verifying transaction of $amount atomic units to $to_address..."
    
    # Get initial balance
    local initial_balance_response=$(call_wallet_with_retry "$from_wallet_url" "get_balance" "{\"account_index\":0}" "$max_attempts" "$delay" "$component")
    local initial_balance_status=$?
    
    if [[ $initial_balance_status -ne 0 ]]; then
        log_critical "$component" "Failed to get initial balance"
        return 1
    fi
    
    local initial_balance=$(echo "$initial_balance_response" | grep -o '"unlocked_balance":[0-9]*' | cut -d':' -f2)
    log_info "$component" "Initial unlocked balance: $initial_balance atomic units"
    
    # Check if we have enough funds
    if [[ $initial_balance -lt $amount ]]; then
        log_error "$component" "Insufficient funds: Have $initial_balance, need $amount"
        return 1
    fi
    
    # Send transaction
    log_info "$component" "Sending transaction..."
    local transfer_response=$(call_wallet_with_retry "$from_wallet_url" "transfer" "{\"destinations\":[{\"amount\":$amount,\"address\":\"$to_address\"}],\"account_index\":0,\"priority\":1,\"get_tx_key\":true}" "$max_attempts" "$delay" "$component")
    local transfer_status=$?
    
    if [[ $transfer_status -ne 0 ]]; then
        log_critical "$component" "Failed to send transaction"
        return 1
    fi
    
    # Extract transaction hash
    local tx_hash=$(echo "$transfer_response" | grep -o '"tx_hash":"[^"]*"' | cut -d'"' -f4)
    if [[ -z "$tx_hash" ]]; then
        log_error "$component" "Failed to extract transaction hash"
        return 1
    fi
    
    log_info "$component" "Transaction sent successfully. Hash: $tx_hash"
    return 0
}

# Function to verify network synchronization
# Usage: verify_network_sync <node1_url> <node2_url> <max_height_diff> <max_attempts> <delay> <component>
verify_network_sync() {
    local node1_url="$1"
    local node2_url="$2"
    local max_height_diff="$3"
    local max_attempts="$4"
    local delay="$5"
    local component="$6"
    
    log_info "$component" "Verifying network synchronization..."
    
    local attempt=1
    while [[ $attempt -le $max_attempts ]]; do
        log_info "$component" "Sync check attempt $attempt/$max_attempts"
        
        # Get info from both nodes
        local node1_response=$(call_daemon_with_retry "$node1_url" "get_info" "{}" "3" "2" "$component")
        local node1_status=$?
        
        local node2_response=$(call_daemon_with_retry "$node2_url" "get_info" "{}" "3" "2" "$component")
        local node2_status=$?
        
        if [[ $node1_status -ne 0 || $node2_status -ne 0 ]]; then
            log_warning "$component" "Failed to get info from one or both nodes"
            sleep "$delay"
            attempt=$((attempt + 1))
            continue
        fi
        
        # Extract heights
        local node1_height=$(echo "$node1_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
        local node2_height=$(echo "$node2_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
        
        # Extract top block hashes
        local node1_hash=$(echo "$node1_response" | grep -o '"top_block_hash":"[^"]*"' | cut -d'"' -f4)
        local node2_hash=$(echo "$node2_response" | grep -o '"top_block_hash":"[^"]*"' | cut -d'"' -f4)
        
        log_info "$component" "Node1 height: $node1_height, hash: $node1_hash"
        log_info "$component" "Node2 height: $node2_height, hash: $node2_hash"
        
        # Calculate height difference
        local height_diff=$((node1_height - node2_height))
        if [[ $height_diff -lt 0 ]]; then
            height_diff=$((height_diff * -1))  # Absolute value
        fi
        
        log_info "$component" "Height difference: $height_diff blocks"
        
        # Check if synchronized
        if [[ $height_diff -le $max_height_diff ]]; then
            if [[ "$node1_hash" == "$node2_hash" || $node1_height -eq $node2_height ]]; then
                log_info "$component" "Synchronization verified: Nodes are in sync"
                return 0
            else
                log_warning "$component" "Heights are close but top block hashes differ"
            fi
        else
            log_warning "$component" "Nodes are not yet synchronized (diff: $height_diff)"
        fi
        
        sleep "$delay"
        attempt=$((attempt + 1))
    done
    
    log_error "$component" "Synchronization verification failed after $max_attempts attempts"
    return 1
}

# Function to verify P2P connectivity between nodes
# Usage: verify_p2p_connectivity <node1_url> <node1_name> <node2_url> <node2_name> <max_attempts> <retry_delay> <component>
verify_p2p_connectivity() {
    local node1_url="$1"
    local node1_name="$2"
    local node2_url="$3"
    local node2_name="$4"
    local max_attempts="$5"
    local retry_delay="$6"
    local component="$7"
    
    log_info "$component" "Verifying P2P connectivity between $node1_name and $node2_name..."
    
    local attempt=1
    while [[ $attempt -le $max_attempts ]]; do
        log_info "$component" "P2P connectivity check attempt $attempt/$max_attempts"
        
        # Check connections on node1
        log_info "$component" "Checking connections on $node1_name..."
        local node1_conn_response=$(call_daemon_with_retry "$node1_url" "get_connections" "{}" "3" "2" "$component")
        local node1_conn_status=$?
        
        # Check connections on node2
        log_info "$component" "Checking connections on $node2_name..."
        local node2_conn_response=$(call_daemon_with_retry "$node2_url" "get_connections" "{}" "3" "2" "$component")
        local node2_conn_status=$?
        
        # Check if both RPC calls were successful
        if [[ $node1_conn_status -ne 0 || $node2_conn_status -ne 0 ]]; then
            log_warning "$component" "Failed to get connection information from one or both nodes"
            sleep "$retry_delay"
            attempt=$((attempt + 1))
            continue
        fi
        
        # Extract connection counts
        local node1_conn_count=$(echo "$node1_conn_response" | grep -o '"address"' | wc -l)
        local node2_conn_count=$(echo "$node2_conn_response" | grep -o '"address"' | wc -l)
        
        log_info "$component" "$node1_name has $node1_conn_count P2P connections"
        log_info "$component" "$node2_name has $node2_conn_count P2P connections"
        
        # Check if nodes have any connections
        if [[ $node1_conn_count -eq 0 && $node2_conn_count -eq 0 ]]; then
            log_warning "$component" "Both nodes have no P2P connections. Retrying in ${retry_delay}s..."
            sleep "$retry_delay"
            attempt=$((attempt + 1))
            continue
        fi
        
        # Check if nodes are connected to each other
        local node1_connected_to_node2=false
        local node2_connected_to_node1=false
        
        # Extract IP addresses from node1's connections
        local node1_peer_ips=$(echo "$node1_conn_response" | grep -o '"address":"[^"]*"' | sed 's/"address":"//g; s/"//g' | cut -d':' -f1)
        
        # Extract IP addresses from node2's connections
        local node2_peer_ips=$(echo "$node2_conn_response" | grep -o '"address":"[^"]*"' | sed 's/"address":"//g; s/"//g' | cut -d':' -f1)
        
        # Get node IPs from network_config.sh
        local node1_ip=$(echo "$node1_url" | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+')
        local node2_ip=$(echo "$node2_url" | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+')
        
        # Check if node1 is connected to node2
        if echo "$node1_peer_ips" | grep -q "$node2_ip"; then
            node1_connected_to_node2=true
            log_info "$component" "✅ $node1_name is connected to $node2_name"
        else
            log_warning "$component" "❌ $node1_name is NOT connected to $node2_name"
        fi
        
        # Check if node2 is connected to node1
        if echo "$node2_peer_ips" | grep -q "$node1_ip"; then
            node2_connected_to_node1=true
            log_info "$component" "✅ $node2_name is connected to $node1_name"
        else
            log_warning "$component" "❌ $node2_name is NOT connected to $node1_name"
        fi
        
        # Check incoming and outgoing connections
        local node1_incoming=$(echo "$node1_conn_response" | grep -o '"incoming":true' | wc -l)
        local node1_outgoing=$(echo "$node1_conn_response" | grep -o '"incoming":false' | wc -l)
        local node2_incoming=$(echo "$node2_conn_response" | grep -o '"incoming":true' | wc -l)
        local node2_outgoing=$(echo "$node2_conn_response" | grep -o '"incoming":false' | wc -l)
        
        log_info "$component" "$node1_name has $node1_incoming incoming and $node1_outgoing outgoing connections"
        log_info "$component" "$node2_name has $node2_incoming incoming and $node2_outgoing outgoing connections"
        
        # Check if both nodes are connected to each other
        if [[ "$node1_connected_to_node2" = true && "$node2_connected_to_node1" = true ]]; then
            log_info "$component" "✅ P2P connectivity verified: Bidirectional connection established between $node1_name and $node2_name"
            
            # Get additional connection details for logging
            log_info "$component" "Connection details:"
            
            # Log node1's connections to node2
            echo "$node1_conn_response" | grep -o '{[^}]*"address":"[^"]*'"$node2_ip"'[^}]*}' | while read conn; do
                local state=$(echo "$conn" | grep -o '"state":[0-9]*' | cut -d':' -f2)
                local live_time=$(echo "$conn" | grep -o '"live_time":[0-9]*' | cut -d':' -f2)
                local incoming=$(echo "$conn" | grep -o '"incoming":(true|false)' | cut -d':' -f2)
                log_info "$component" "  $node1_name -> $node2_name: State=$state, Live time=${live_time}s, Incoming=$incoming"
            done
            
            # Log node2's connections to node1
            echo "$node2_conn_response" | grep -o '{[^}]*"address":"[^"]*'"$node1_ip"'[^}]*}' | while read conn; do
                local state=$(echo "$conn" | grep -o '"state":[0-9]*' | cut -d':' -f2)
                local live_time=$(echo "$conn" | grep -o '"live_time":[0-9]*' | cut -d':' -f2)
                local incoming=$(echo "$conn" | grep -o '"incoming":(true|false)' | cut -d':' -f2)
                log_info "$component" "  $node2_name -> $node1_name: State=$state, Live time=${live_time}s, Incoming=$incoming"
            done
            
            return 0
        else
            # If we're on the last attempt, provide detailed diagnostics
            if [[ $attempt -eq $max_attempts ]]; then
                log_error "$component" "❌ P2P connectivity verification failed after $max_attempts attempts"
                
                # Check peer list to see if nodes know about each other
                log_info "$component" "Checking peer lists for diagnostic information..."
                
                local node1_peer_list=$(call_daemon_with_retry "$node1_url" "get_peer_list" "{}" "3" "2" "$component")
                local node2_peer_list=$(call_daemon_with_retry "$node2_url" "get_peer_list" "{}" "3" "2" "$component")
                
                if [[ $? -eq 0 ]]; then
                    # Check if node1 knows about node2
                    if echo "$node1_peer_list" | grep -q "$node2_ip"; then
                        log_info "$component" "$node1_name knows about $node2_name in its peer list"
                    else
                        log_error "$component" "$node1_name does NOT have $node2_name in its peer list"
                    fi
                    
                    # Check if node2 knows about node1
                    if echo "$node2_peer_list" | grep -q "$node1_ip"; then
                        log_info "$component" "$node2_name knows about $node1_name in its peer list"
                    else
                        log_error "$component" "$node2_name does NOT have $node1_name in its peer list"
                    fi
                    
                    # Check for any connection errors in logs
                    log_error "$component" "Possible reasons for P2P connectivity failure:"
                    log_error "$component" "1. Firewall or network configuration issues"
                    log_error "$component" "2. Incorrect exclusive/priority node settings"
                    log_error "$component" "3. P2P port conflicts"
                    log_error "$component" "4. Node startup timing issues"
                fi
                
                return 1
            fi
            
            log_warning "$component" "Nodes are not fully connected. Retrying in ${retry_delay}s..."
            sleep "$retry_delay"
            attempt=$((attempt + 1))
        fi
    done
    
    log_error "$component" "P2P connectivity verification failed after $max_attempts attempts"
    return 1
}

# Function to handle script exit
# Usage: handle_exit <exit_code> <component> <message>
handle_exit() {
    local exit_code="$1"
    local component="$2"
    local message="$3"
    
    if [[ $exit_code -eq 0 ]]; then
        log_info "$component" "Script completed successfully: $message"
    else
        log_critical "$component" "Script failed with exit code $exit_code: $message"
    fi
    
    exit "$exit_code"
}

# Export all functions
export -f log_message log_info log_warning log_error log_critical
export -f retry_command call_daemon_with_retry call_wallet_with_retry
export -f verify_daemon_ready verify_wallet_created verify_wallet_open
export -f verify_block_generation verify_transaction verify_network_sync
export -f verify_p2p_connectivity handle_exit

# Export constants
export LEVEL_INFO LEVEL_WARNING LEVEL_ERROR LEVEL_CRITICAL
export RED YELLOW GREEN BLUE PURPLE NC