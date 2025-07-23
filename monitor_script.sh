#!/bin/bash

# Enhanced network monitoring script with connectivity and P2P status

# Source the central network configuration and error handling library
source "$(dirname "$0")/network_config.sh"
source "$(dirname "$0")/error_handling.sh"

# Component name for logging
COMPONENT="MONITOR"

# Configuration
MAX_ATTEMPTS=3
RETRY_DELAY=2
P2P_CHECK_ATTEMPTS=2
P2P_CHECK_DELAY=5

log_info "$COMPONENT" "=== Enhanced Monero Network Monitor ==="
log_info "$COMPONENT" "Time: $(date)"

# Function to check daemon connectivity with improved error handling
check_daemon() {
    local name="$1"
    local ip="$2"
    local port="$3"
    local daemon_url="http://$ip:$port/json_rpc"
    
    log_info "$COMPONENT" "--- Node $name ($ip:$port) ---"
    
    # Check get_info
    log_info "$COMPONENT" "🔍 Checking get_info:"
    local info_response=$(call_daemon_with_retry "$daemon_url" "get_info" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    local info_status=$?
    
    if [[ $info_status -eq 0 ]]; then
        # Extract key info
        local height=$(echo "$info_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
        local incoming=$(echo "$info_response" | grep -o '"incoming_connections_count":[0-9]*' | cut -d':' -f2)
        local outgoing=$(echo "$info_response" | grep -o '"outgoing_connections_count":[0-9]*' | cut -d':' -f2)
        local status=$(echo "$info_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        
        if [[ -n "$height" && -n "$incoming" && -n "$outgoing" && -n "$status" ]]; then
            log_info "$COMPONENT" "  ✅ Status: $status, Height: $height, Connections: $incoming in/$outgoing out"
        else
            log_warning "$COMPONENT" "  ⚠️ Could not extract all info fields"
        fi
    else
        log_error "$COMPONENT" "  ❌ RPC call failed for get_info"
    fi
    
    # Check P2P connections
    log_info "$COMPONENT" "🌐 Checking get_connections:"
    local conn_response=$(call_daemon_with_retry "$daemon_url" "get_connections" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    local conn_status=$?
    
    if [[ $conn_status -eq 0 ]]; then
        local connection_count=$(echo "$conn_response" | grep -o '"address"' | wc -l)
        log_info "$COMPONENT" "  🔗 Active P2P connections: $connection_count"
        
        # Show peer addresses if any
        if [[ $connection_count -gt 0 ]]; then
            echo "$conn_response" | grep -o '"address":"[^"]*"' | sed 's/"address":"//g; s/"//g' | while read addr; do
                log_info "$COMPONENT" "    -> Peer: $addr"
            done
        fi
    else
        log_error "$COMPONENT" "  ❌ P2P query failed"
    fi
    
    # Check mining status
    log_info "$COMPONENT" "⛏️  Checking mining_status:"
    local mining_url="http://$ip:$port/mining_status"
    local mining_response=$(curl -s --max-time 5 "$mining_url" -H 'Content-Type: application/json' 2>/dev/null)
    
    if [[ -n "$mining_response" && "$mining_response" != *"Connection refused"* ]]; then
        local active=$(echo "$mining_response" | grep -o '"active":[^,}]*' | cut -d':' -f2)
        if [[ -n "$active" ]]; then
            log_info "$COMPONENT" "  ⛏️  Mining active: $active"
        else
            log_warning "$COMPONENT" "  ⚠️ Could not extract mining status"
        fi
    else
        log_error "$COMPONENT" "  ❌ Mining status query failed"
    fi
}

# Check both daemons
check_daemon "A0" "$A0_IP" "$A0_RPC_PORT"
check_daemon "A1" "$A1_IP" "$A1_RPC_PORT"

# Test inter-node connectivity
log_info "$COMPONENT" "🔗 Testing Inter-Node Connectivity:"
log_info "$COMPONENT" "Note: Ping tests disabled in Shadow simulation"
log_info "$COMPONENT" "  A0 <-> A1: Testing via P2P connection status"

# Check wallet connectivity
log_info "$COMPONENT" "🏦 Wallet Connectivity Test:"

# Check Wallet1
log_info "$COMPONENT" "Wallet1 (${WALLET1_IP}:${WALLET1_RPC_PORT}):"
wallet1_response=$(call_wallet_with_retry "$WALLET1_RPC" "get_version" "{}" 2 1 "$COMPONENT")
wallet1_status=$?

if [[ $wallet1_status -eq 0 ]]; then
    log_info "$COMPONENT" "  ✅ Wallet1 RPC responding"
else
    log_error "$COMPONENT" "  ❌ Wallet1 RPC not responding"
fi

# Check Wallet2
log_info "$COMPONENT" "Wallet2 (${WALLET2_IP}:${WALLET2_RPC_PORT}):"
wallet2_response=$(call_wallet_with_retry "$WALLET2_RPC" "get_version" "{}" 2 1 "$COMPONENT")
wallet2_status=$?

if [[ $wallet2_status -eq 0 ]]; then
    log_info "$COMPONENT" "  ✅ Wallet2 RPC responding"
else
    log_error "$COMPONENT" "  ❌ Wallet2 RPC not responding"
fi

# Check for P2P connectivity between nodes using the enhanced verification function
log_info "$COMPONENT" "🌐 Enhanced P2P Network Analysis:"

# Use the new P2P connectivity verification function with fewer retries for monitoring
if verify_p2p_connectivity "$A0_RPC" "A0" "$A1_RPC" "A1" "$P2P_CHECK_ATTEMPTS" "$P2P_CHECK_DELAY" "$COMPONENT"; then
    log_info "$COMPONENT" "  ✅ P2P connectivity verified: Nodes are properly connected"
else
    log_warning "$COMPONENT" "  ⚠️ P2P connectivity check failed"
    
    # Fallback to basic peer discovery check
    log_info "$COMPONENT" "  Falling back to basic peer discovery check..."
    
    # Try to check if A0 knows about A1 as a peer
    a0_peers=$(call_daemon_with_retry "$A0_RPC" "get_peer_list" "{}" 2 1 "$COMPONENT")
    a0_peers_status=$?
    
    if [[ $a0_peers_status -eq 0 ]]; then
        log_info "$COMPONENT" "  📡 A0 peer discovery working"
        if [[ "$a0_peers" == *"${A1_IP}"* ]]; then
            log_info "$COMPONENT" "  ✅ A0 knows about A1"
        else
            log_warning "$COMPONENT" "  ⏳ A0 hasn't discovered A1 yet"
        fi
    else
        log_error "$COMPONENT" "  ❌ A0 peer discovery failed"
    fi
    
    # Try to check if A1 knows about A0 as a peer
    a1_peers=$(call_daemon_with_retry "$A1_RPC" "get_peer_list" "{}" 2 1 "$COMPONENT")
    a1_peers_status=$?
    
    if [[ $a1_peers_status -eq 0 ]]; then
        log_info "$COMPONENT" "  📡 A1 peer discovery working"
        if [[ "$a1_peers" == *"${A0_IP}"* ]]; then
            log_info "$COMPONENT" "  ✅ A1 knows about A0"
        else
            log_warning "$COMPONENT" "  ⏳ A1 hasn't discovered A0 yet"
        fi
    else
        log_error "$COMPONENT" "  ❌ A1 peer discovery failed"
    fi
fi

# Display P2P connection summary
log_info "$COMPONENT" "📊 P2P Connection Summary:"

# Get connection counts from both nodes
a0_info=$(call_daemon_with_retry "$A0_RPC" "get_info" "{}" 2 1 "$COMPONENT")
a1_info=$(call_daemon_with_retry "$A1_RPC" "get_info" "{}" 2 1 "$COMPONENT")

if [[ $? -eq 0 ]]; then
    # Extract connection counts
    a0_incoming=$(echo "$a0_info" | grep -o '"incoming_connections_count":[0-9]*' | cut -d':' -f2)
    a0_outgoing=$(echo "$a0_info" | grep -o '"outgoing_connections_count":[0-9]*' | cut -d':' -f2)
    a1_incoming=$(echo "$a1_info" | grep -o '"incoming_connections_count":[0-9]*' | cut -d':' -f2)
    a1_outgoing=$(echo "$a1_info" | grep -o '"outgoing_connections_count":[0-9]*' | cut -d':' -f2)
    
    log_info "$COMPONENT" "  A0: $a0_incoming incoming, $a0_outgoing outgoing connections"
    log_info "$COMPONENT" "  A1: $a1_incoming incoming, $a1_outgoing outgoing connections"
    
    # Check for potential issues
    if [[ $a0_incoming -eq 0 && $a0_outgoing -eq 0 ]]; then
        log_error "$COMPONENT" "  ❌ A0 has no connections at all!"
    fi
    
    if [[ $a1_incoming -eq 0 && $a1_outgoing -eq 0 ]]; then
        log_error "$COMPONENT" "  ❌ A1 has no connections at all!"
    fi
    
    # Check for expected connection pattern
    if [[ $a0_incoming -gt 0 && $a1_outgoing -gt 0 ]]; then
        log_info "$COMPONENT" "  ✅ A1 has outgoing connections to A0 as expected"
    else
        log_warning "$COMPONENT" "  ⚠️ A1 should have outgoing connections to A0"
    fi
fi

log_info "$COMPONENT" "=== End Enhanced Monitor ==="