#!/bin/bash

# Simple MoneroSim Test Script
# This script tests basic mining and synchronization functionality

# Source the central network configuration and error handling library
source "$(dirname "$0")/network_config.sh"
source "$(dirname "$0")/error_handling.sh"

# Component name for logging
COMPONENT="SIMPLE_TEST"

# Configuration
MAX_ATTEMPTS=30
RETRY_DELAY=2
SYNC_WAIT_TIME=30
SYNC_THRESHOLD=0  # Exact match required for this simple test
MINING_ADDRESS="48S1ZANZRDGTqF7rdxCh8R4jvBELF63u9MieHNwGNYrRZWka84mN9ttV88eq2QScJRHJsdHJMNg3LDu3Z21hmaE61SWymvv"
NUM_BLOCKS=3

log_info "$COMPONENT" "=== MoneroSim Simple Test ==="
log_info "$COMPONENT" "Starting simple test at $(date)"

# Function to get blockchain height with retry
get_height() {
    local daemon_url="$1"
    local daemon_name="$2"
    
    log_info "$COMPONENT" "Getting $daemon_name height..."
    local response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    local status=$?
    
    if [[ $status -ne 0 ]]; then
        log_error "$COMPONENT" "Failed to get $daemon_name height"
        return 1
    fi
    
    local height=$(echo "$response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
    
    if [[ -z "$height" ]]; then
        log_error "$COMPONENT" "Failed to extract height from response: $response"
        return 1
    fi
    
    log_info "$COMPONENT" "$daemon_name height: $height"
    echo "$height"
    return 0
}

# Main test execution
log_info "$COMPONENT" "Step 1: Verifying daemon readiness"

# Verify daemon readiness for both nodes
if ! verify_daemon_ready "$A0_RPC" "A0" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "A0 daemon verification failed"
fi

if ! verify_daemon_ready "$A1_RPC" "A1" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    handle_exit 1 "$COMPONENT" "A1 daemon verification failed"
fi

log_info "$COMPONENT" "Step 2: Getting initial daemon info"
# Get initial daemon info
A0_INFO=$(call_daemon_with_retry "$A0_RPC" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get A0 info"
    handle_exit 1 "$COMPONENT" "A0 info retrieval failed"
fi

A1_INFO=$(call_daemon_with_retry "$A1_RPC" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get A1 info"
    handle_exit 1 "$COMPONENT" "A1 info retrieval failed"
fi

log_info "$COMPONENT" "Step 3: Getting initial blockchain heights"
A0_HEIGHT=$(get_height "$A0_RPC" "A0")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get A0 height"
    handle_exit 1 "$COMPONENT" "A0 height retrieval failed"
fi

A1_HEIGHT=$(get_height "$A1_RPC" "A1")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get A1 height"
    handle_exit 1 "$COMPONENT" "A1 height retrieval failed"
fi

log_info "$COMPONENT" "Initial heights - A0: $A0_HEIGHT, A1: $A1_HEIGHT"

log_info "$COMPONENT" "Step 4: Generating blocks on A0"
# Verify block generation
if ! verify_block_generation "$A0_RPC" "$MINING_ADDRESS" "$NUM_BLOCKS" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    log_critical "$COMPONENT" "Block generation failed"
    handle_exit 1 "$COMPONENT" "Block generation verification failed"
fi

log_info "$COMPONENT" "Step 5: Waiting $SYNC_WAIT_TIME seconds for synchronization"
sleep $SYNC_WAIT_TIME

log_info "$COMPONENT" "Step 6: Verifying network synchronization"
# Verify network synchronization
if verify_network_sync "$A0_RPC" "$A1_RPC" "$SYNC_THRESHOLD" 1 1 "$COMPONENT"; then
    log_info "$COMPONENT" "✅ SUCCESS: Nodes are synchronized"
else
    # Get final heights for diagnostic information
    log_info "$COMPONENT" "Getting final blockchain heights"
    A0_FINAL_HEIGHT=$(get_height "$A0_RPC" "A0")
    A1_FINAL_HEIGHT=$(get_height "$A1_RPC" "A1")
    
    log_critical "$COMPONENT" "❌ FAILURE: Nodes have different blockchain heights"
    log_critical "$COMPONENT" "❌ A0: $A0_FINAL_HEIGHT, A1: $A1_FINAL_HEIGHT"
    handle_exit 1 "$COMPONENT" "Synchronization verification failed"
fi

log_info "$COMPONENT" "✅ Basic mining and synchronization test PASSED"
log_info "$COMPONENT" "=== Simple test completed ==="

handle_exit 0 "$COMPONENT" "Simple test completed successfully"