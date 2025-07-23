#!/bin/bash

# sync_check.sh - Script to verify network synchronization between Monero nodes
# This script checks if the sync node (A1) is properly synchronized with the mining node (A0)

# Source the central network configuration and error handling library
source "$(dirname "$0")/network_config.sh"
source "$(dirname "$0")/error_handling.sh"

# Component name for logging
COMPONENT="SYNC_CHECK"

# Configuration
CHECK_INTERVAL=30  # Check every 30 seconds
MAX_CHECKS=20      # Maximum number of checks (10 minutes total)
SYNC_THRESHOLD=2   # Maximum acceptable block height difference
MAX_ATTEMPTS=5     # Maximum attempts for RPC calls
RETRY_DELAY=2      # Delay between retry attempts
P2P_CHECK_INTERVAL=15  # Check P2P connectivity every 15 seconds
P2P_MAX_CHECKS=10      # Maximum number of P2P connectivity checks

# Function to get node info with retry
get_node_info() {
    local daemon_url="$1"
    local node_name="$2"
    
    log_info "$COMPONENT" "Getting $node_name info..."
    local response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    local status=$?
    
    if [[ $status -ne 0 ]]; then
        log_error "$COMPONENT" "Failed to get $node_name info"
        return 1
    fi
    
    # Extract height
    local height=$(echo "$response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
    
    # Extract top block hash
    local top_hash=$(echo "$response" | grep -o '"top_block_hash":"[^"]*"' | cut -d'"' -f4)
    
    # Extract status
    local status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    
    if [[ -z "$height" || -z "$top_hash" || -z "$status" ]]; then
        log_error "$COMPONENT" "Failed to extract node info from response: $response"
        return 1
    fi
    
    # Return as space-separated values
    echo "$height $top_hash $status"
    return 0
}

# Main execution
log_info "$COMPONENT" "Starting synchronization check between A0 (mining node) and A1 (sync node)"

# Verify daemon readiness for both nodes
if ! verify_daemon_ready "$A0_RPC" "A0 (mining node)" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    log_critical "$COMPONENT" "A0 is not responsive. Cannot proceed with sync check."
    handle_exit 1 "$COMPONENT" "Mining node verification failed"
fi

if ! verify_daemon_ready "$A1_RPC" "A1 (sync node)" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    log_critical "$COMPONENT" "A1 is not responsive. Cannot proceed with sync check."
    handle_exit 1 "$COMPONENT" "Sync node verification failed"
fi

# Verify P2P connectivity between nodes
log_info "$COMPONENT" "Verifying P2P connectivity between nodes..."
if ! verify_p2p_connectivity "$A0_RPC" "A0 (mining node)" "$A1_RPC" "A1 (sync node)" "$P2P_MAX_CHECKS" "$P2P_CHECK_INTERVAL" "$COMPONENT"; then
    log_critical "$COMPONENT" "P2P connectivity verification failed. Cannot proceed with sync check."
    
    # Provide detailed diagnostic information
    log_info "$COMPONENT" "Running diagnostic checks..."
    
    # Check node configurations
    log_info "$COMPONENT" "Checking node configurations..."
    A0_INFO=$(call_daemon_with_retry "$A0_RPC" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    A1_INFO=$(call_daemon_with_retry "$A1_RPC" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    
    if [[ $? -eq 0 ]]; then
        # Extract P2P port information
        A0_P2P_PORT=$(echo "$A0_INFO" | grep -o '"p2p_port":[0-9]*' | cut -d':' -f2)
        A1_P2P_PORT=$(echo "$A1_INFO" | grep -o '"p2p_port":[0-9]*' | cut -d':' -f2)
        
        log_info "$COMPONENT" "A0 P2P port: $A0_P2P_PORT"
        log_info "$COMPONENT" "A1 P2P port: $A1_P2P_PORT"
        
        # Check if exclusive/priority nodes are configured
        log_info "$COMPONENT" "Checking exclusive/priority node settings..."
        
        # This would require additional RPC methods that might not be available
        # For now, we'll just provide general guidance
        log_info "$COMPONENT" "Verify that A1 has A0 configured as an exclusive or priority node"
        log_info "$COMPONENT" "Command line should include: --add-exclusive-node=$A0_IP:$A0_P2P_PORT"
    fi
    
    handle_exit 1 "$COMPONENT" "P2P connectivity verification failed"
fi

log_info "$COMPONENT" "✅ P2P connectivity verified. Proceeding with synchronization check."

# Initial check
log_info "$COMPONENT" "Performing initial synchronization check..."
A0_INFO=$(get_node_info "$A0_RPC" "A0")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get initial A0 info"
    handle_exit 1 "$COMPONENT" "Initial A0 info retrieval failed"
fi

A1_INFO=$(get_node_info "$A1_RPC" "A1")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get initial A1 info"
    handle_exit 1 "$COMPONENT" "Initial A1 info retrieval failed"
fi

A0_HEIGHT=$(echo "$A0_INFO" | cut -d' ' -f1)
A0_HASH=$(echo "$A0_INFO" | cut -d' ' -f2)
A1_HEIGHT=$(echo "$A1_INFO" | cut -d' ' -f1)
A1_HASH=$(echo "$A1_INFO" | cut -d' ' -f2)

log_info "$COMPONENT" "Initial state:"
log_info "$COMPONENT" "A0: Height=$A0_HEIGHT, Top Hash=$A0_HASH"
log_info "$COMPONENT" "A1: Height=$A1_HEIGHT, Top Hash=$A1_HASH"

# Use the network synchronization verification function
log_info "$COMPONENT" "Verifying network synchronization..."
if verify_network_sync "$A0_RPC" "$A1_RPC" "$SYNC_THRESHOLD" "$MAX_CHECKS" "$CHECK_INTERVAL" "$COMPONENT"; then
    log_info "$COMPONENT" "🎉 SYNCHRONIZATION TEST PASSED: A1 successfully synchronized with A0"
    handle_exit 0 "$COMPONENT" "Synchronization test passed"
else
    log_critical "$COMPONENT" "❌ SYNCHRONIZATION TEST FAILED: A1 did not synchronize with A0 within the time limit"
    
    # Get final state for diagnostic information
    log_info "$COMPONENT" "Getting final state for diagnostic information..."
    
    A0_FINAL_INFO=$(get_node_info "$A0_RPC" "A0")
    A1_FINAL_INFO=$(get_node_info "$A1_RPC" "A1")
    
    if [[ $? -eq 0 ]]; then
        A0_FINAL_HEIGHT=$(echo "$A0_FINAL_INFO" | cut -d' ' -f1)
        A0_FINAL_HASH=$(echo "$A0_FINAL_INFO" | cut -d' ' -f2)
        A1_FINAL_HEIGHT=$(echo "$A1_FINAL_INFO" | cut -d' ' -f1)
        A1_FINAL_HASH=$(echo "$A1_FINAL_INFO" | cut -d' ' -f2)
        
        # Calculate final height difference
        height_diff=$((A0_FINAL_HEIGHT - A1_FINAL_HEIGHT))
        if [[ $height_diff -lt 0 ]]; then
            height_diff=$((height_diff * -1))  # Absolute value
        fi
        
        log_error "$COMPONENT" "Final state:"
        log_error "$COMPONENT" "A0: Height=$A0_FINAL_HEIGHT, Top Hash=$A0_FINAL_HASH"
        log_error "$COMPONENT" "A1: Height=$A1_FINAL_HEIGHT, Top Hash=$A1_FINAL_HASH"
        log_error "$COMPONENT" "Height difference: $height_diff blocks"
    else
        log_error "$COMPONENT" "Failed to get final state information"
    fi
    
    # Provide diagnostic information
    log_info "$COMPONENT" "Collecting diagnostic information..."
    
    # Perform detailed P2P connectivity diagnostics
    log_info "$COMPONENT" "Performing detailed P2P connectivity diagnostics..."
    
    # Check P2P connections on both nodes
    log_info "$COMPONENT" "Checking P2P connections on A0..."
    A0_CONNECTIONS=$(call_daemon_with_retry "$A0_RPC" "get_connections" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    
    log_info "$COMPONENT" "Checking P2P connections on A1..."
    A1_CONNECTIONS=$(call_daemon_with_retry "$A1_RPC" "get_connections" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    
    if [[ $? -eq 0 ]]; then
        a0_connection_count=$(echo "$A0_CONNECTIONS" | grep -o '"address"' | wc -l)
        a1_connection_count=$(echo "$A1_CONNECTIONS" | grep -o '"address"' | wc -l)
        
        log_info "$COMPONENT" "A0 has $a0_connection_count P2P connections"
        log_info "$COMPONENT" "A1 has $a1_connection_count P2P connections"
        
        if [[ $a0_connection_count -eq 0 && $a1_connection_count -eq 0 ]]; then
            log_error "$COMPONENT" "Both nodes have no P2P connections, which explains synchronization failure"
        elif [[ $a1_connection_count -eq 0 ]]; then
            log_error "$COMPONENT" "A1 has no P2P connections, which explains synchronization failure"
        elif [[ $a0_connection_count -eq 0 ]]; then
            log_error "$COMPONENT" "A0 has no P2P connections, which explains synchronization failure"
        fi
        
        # Check if nodes are connected to each other
        if echo "$A0_CONNECTIONS" | grep -q "$A1_IP"; then
            log_info "$COMPONENT" "A0 is connected to A1"
        else
            log_error "$COMPONENT" "A0 is NOT connected to A1"
        fi
        
        if echo "$A1_CONNECTIONS" | grep -q "$A0_IP"; then
            log_info "$COMPONENT" "A1 is connected to A0"
        else
            log_error "$COMPONENT" "A1 is NOT connected to A0"
        fi
    else
        log_error "$COMPONENT" "Failed to get P2P connections"
    fi
    
    # Check peer lists
    log_info "$COMPONENT" "Checking peer lists..."
    A0_PEERS=$(call_daemon_with_retry "$A0_RPC" "get_peer_list" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    A1_PEERS=$(call_daemon_with_retry "$A1_RPC" "get_peer_list" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    
    if [[ $? -eq 0 ]]; then
        # Check if A0 knows about A1
        if echo "$A0_PEERS" | grep -q "$A1_IP"; then
            log_info "$COMPONENT" "A0 has A1 in its peer list"
        else
            log_error "$COMPONENT" "A0 does NOT have A1 in its peer list"
        fi
        
        # Check if A1 knows about A0
        if echo "$A1_PEERS" | grep -q "$A0_IP"; then
            log_info "$COMPONENT" "A1 has A0 in its peer list"
        else
            log_error "$COMPONENT" "A1 does NOT have A0 in its peer list"
        fi
    else
        log_error "$COMPONENT" "Failed to get peer lists"
    fi
    
    handle_exit 1 "$COMPONENT" "Synchronization test failed"
fi