#!/bin/bash

# test_p2p_connectivity.sh - Script to test the enhanced P2P connectivity verification
# This script tests the P2P connectivity between Monero nodes in the Shadow simulation

# Source the central network configuration and error handling library
source "$(dirname "$0")/network_config.sh"
source "$(dirname "$0")/error_handling.sh"

# Component name for logging
COMPONENT="P2P_TEST"

# Configuration
MAX_ATTEMPTS=5
RETRY_DELAY=3
P2P_CHECK_ATTEMPTS=10
P2P_CHECK_DELAY=10

# Main execution
log_info "$COMPONENT" "=== P2P Connectivity Test ==="
log_info "$COMPONENT" "Time: $(date)"

# Verify daemon readiness for both nodes
log_info "$COMPONENT" "Verifying daemon readiness..."

if ! verify_daemon_ready "$A0_RPC" "A0 (mining node)" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    log_critical "$COMPONENT" "A0 is not responsive. Cannot proceed with P2P test."
    handle_exit 1 "$COMPONENT" "Mining node verification failed"
fi

if ! verify_daemon_ready "$A1_RPC" "A1 (sync node)" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    log_critical "$COMPONENT" "A1 is not responsive. Cannot proceed with P2P test."
    handle_exit 1 "$COMPONENT" "Sync node verification failed"
fi

# Get initial node info
log_info "$COMPONENT" "Getting initial node information..."

A0_INFO=$(call_daemon_with_retry "$A0_RPC" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
A1_INFO=$(call_daemon_with_retry "$A1_RPC" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")

if [[ $? -eq 0 ]]; then
    # Extract connection counts
    A0_INCOMING=$(echo "$A0_INFO" | grep -o '"incoming_connections_count":[0-9]*' | cut -d':' -f2)
    A0_OUTGOING=$(echo "$A0_INFO" | grep -o '"outgoing_connections_count":[0-9]*' | cut -d':' -f2)
    A1_INCOMING=$(echo "$A1_INFO" | grep -o '"incoming_connections_count":[0-9]*' | cut -d':' -f2)
    A1_OUTGOING=$(echo "$A1_INFO" | grep -o '"outgoing_connections_count":[0-9]*' | cut -d':' -f2)
    
    log_info "$COMPONENT" "Initial connection state:"
    log_info "$COMPONENT" "A0: $A0_INCOMING incoming, $A0_OUTGOING outgoing connections"
    log_info "$COMPONENT" "A1: $A1_INCOMING incoming, $A1_OUTGOING outgoing connections"
fi

# Test P2P connectivity verification
log_info "$COMPONENT" "Testing P2P connectivity verification..."

if verify_p2p_connectivity "$A0_RPC" "A0 (mining node)" "$A1_RPC" "A1 (sync node)" "$P2P_CHECK_ATTEMPTS" "$P2P_CHECK_DELAY" "$COMPONENT"; then
    log_info "$COMPONENT" "🎉 P2P CONNECTIVITY TEST PASSED: Nodes are properly connected"
    
    # Get detailed connection information
    log_info "$COMPONENT" "Getting detailed connection information..."
    
    # Check connections on A0
    A0_CONNECTIONS=$(call_daemon_with_retry "$A0_RPC" "get_connections" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    if [[ $? -eq 0 ]]; then
        log_info "$COMPONENT" "A0 connections:"
        echo "$A0_CONNECTIONS" | grep -o '{[^}]*"address":"[^"]*'"$A1_IP"'[^}]*}' | while read conn; do
            local state=$(echo "$conn" | grep -o '"state":[0-9]*' | cut -d':' -f2)
            local live_time=$(echo "$conn" | grep -o '"live_time":[0-9]*' | cut -d':' -f2)
            local incoming=$(echo "$conn" | grep -o '"incoming":(true|false)' | cut -d':' -f2)
            log_info "$COMPONENT" "  Connection to $A1_IP: State=$state, Live time=${live_time}s, Incoming=$incoming"
        done
    fi
    
    # Check connections on A1
    A1_CONNECTIONS=$(call_daemon_with_retry "$A1_RPC" "get_connections" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    if [[ $? -eq 0 ]]; then
        log_info "$COMPONENT" "A1 connections:"
        echo "$A1_CONNECTIONS" | grep -o '{[^}]*"address":"[^"]*'"$A0_IP"'[^}]*}' | while read conn; do
            local state=$(echo "$conn" | grep -o '"state":[0-9]*' | cut -d':' -f2)
            local live_time=$(echo "$conn" | grep -o '"live_time":[0-9]*' | cut -d':' -f2)
            local incoming=$(echo "$conn" | grep -o '"incoming":(true|false)' | cut -d':' -f2)
            log_info "$COMPONENT" "  Connection to $A0_IP: State=$state, Live time=${live_time}s, Incoming=$incoming"
        done
    fi
    
    handle_exit 0 "$COMPONENT" "P2P connectivity test passed"
else
    log_critical "$COMPONENT" "❌ P2P CONNECTIVITY TEST FAILED: Nodes are not properly connected"
    
    # Provide detailed diagnostic information
    log_info "$COMPONENT" "Running diagnostic checks..."
    
    # Check node configurations
    log_info "$COMPONENT" "Checking node configurations..."
    
    # Extract P2P port information
    A0_P2P_PORT=$(echo "$A0_INFO" | grep -o '"p2p_port":[0-9]*' | cut -d':' -f2)
    A1_P2P_PORT=$(echo "$A1_INFO" | grep -o '"p2p_port":[0-9]*' | cut -d':' -f2)
    
    log_info "$COMPONENT" "A0 P2P port: $A0_P2P_PORT"
    log_info "$COMPONENT" "A1 P2P port: $A1_P2P_PORT"
    
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
    fi
    
    # Provide troubleshooting guidance
    log_info "$COMPONENT" "Troubleshooting guidance:"
    log_info "$COMPONENT" "1. Verify that A1 has A0 configured as an exclusive or priority node"
    log_info "$COMPONENT" "   Command line should include: --add-exclusive-node=$A0_IP:$A0_P2P_PORT"
    log_info "$COMPONENT" "2. Check for any firewall or network configuration issues"
    log_info "$COMPONENT" "3. Ensure both nodes have the allow-local-ip flag set"
    log_info "$COMPONENT" "4. Verify that the P2P ports are correctly configured and not conflicting"
    log_info "$COMPONENT" "5. Check the node startup timing - A0 should start before A1"
    
    handle_exit 1 "$COMPONENT" "P2P connectivity test failed"
fi