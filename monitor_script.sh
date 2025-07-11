#!/bin/bash

# Enhanced network monitoring script with connectivity and P2P status
echo "=== Enhanced Monero Network Monitor ==="
echo "Time: $(date)"
echo ""

# Function to check daemon connectivity
check_daemon() {
    local name="$1"
    local ip="$2"
    local port="$3"
    
    echo "--- Node $name ($ip:$port) ---"
    
    # Check get_info
    echo "🔍 get_info:"
    local info_response=$(curl -s --max-time 5 "http://$ip:$port/json_rpc" \
        -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
        -H 'Content-Type: application/json' 2>/dev/null)
    
    if [[ -n "$info_response" && "$info_response" != *"Connection refused"* ]]; then
        # Extract key info
        local height=$(echo "$info_response" | grep -o '"height":[0-9]*' | cut -d':' -f2)
        local incoming=$(echo "$info_response" | grep -o '"incoming_connections_count":[0-9]*' | cut -d':' -f2)
        local outgoing=$(echo "$info_response" | grep -o '"outgoing_connections_count":[0-9]*' | cut -d':' -f2)
        local status=$(echo "$info_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        
        echo "  ✅ Status: $status, Height: $height, Connections: $incoming in/$outgoing out"
    else
        echo "  ❌ RPC call failed: $info_response"
    fi
    
    # Check P2P connections
    echo "🌐 get_connections:"
    local conn_response=$(curl -s --max-time 5 "http://$ip:$port/json_rpc" \
        -d '{"jsonrpc":"2.0","id":"0","method":"get_connections"}' \
        -H 'Content-Type: application/json' 2>/dev/null)
    
    if [[ -n "$conn_response" && "$conn_response" != *"Connection refused"* ]]; then
        local connection_count=$(echo "$conn_response" | grep -o '"address"' | wc -l)
        echo "  🔗 Active P2P connections: $connection_count"
        
        # Show peer addresses if any
        if [[ $connection_count -gt 0 ]]; then
            echo "$conn_response" | grep -o '"address":"[^"]*"' | sed 's/"address":"//g; s/"//g' | while read addr; do
                echo "    -> Peer: $addr"
            done
        fi
    else
        echo "  ❌ P2P query failed: $conn_response"
    fi
    
    # Check mining status
    echo "⛏️  mining_status:"
    local mining_response=$(curl -s --max-time 5 "http://$ip:$port/mining_status" \
        -H 'Content-Type: application/json' 2>/dev/null)
    
    if [[ -n "$mining_response" && "$mining_response" != *"Connection refused"* ]]; then
        local active=$(echo "$mining_response" | grep -o '"active":[^,}]*' | cut -d':' -f2)
        echo "  ⛏️  Mining active: $active"
    else
        echo "  ❌ Mining status failed: $mining_response"
    fi
    
    echo ""
}

# Check both daemons
check_daemon "A0" "11.0.0.1" "28090"
check_daemon "A1" "11.0.0.2" "28090"

# Test inter-node connectivity
echo "🔗 Testing Inter-Node Connectivity:"
echo "Note: Ping tests disabled in Shadow simulation"
echo "  A0 <-> A1: Testing via P2P connection status"
echo ""

# Check wallet connectivity
echo "🏦 Wallet Connectivity Test:"
echo "Wallet1 (11.0.0.6:28091):"
wallet1_response=$(curl -s --max-time 3 "http://11.0.0.6:28091/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_version"}' \
    -H 'Content-Type: application/json' 2>/dev/null)

if [[ -n "$wallet1_response" && "$wallet1_response" != *"Connection refused"* ]]; then
    echo "  ✅ Wallet1 RPC responding"
else
    echo "  ❌ Wallet1 RPC not responding"
fi

echo "Wallet2 (11.0.0.7:28092):"
wallet2_response=$(curl -s --max-time 3 "http://11.0.0.7:28092/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_version"}' \
    -H 'Content-Type: application/json' 2>/dev/null)

if [[ -n "$wallet2_response" && "$wallet2_response" != *"Connection refused"* ]]; then
    echo "  ✅ Wallet2 RPC responding"
else
    echo "  ❌ Wallet2 RPC not responding"
fi

# Check for P2P connectivity between nodes
echo ""
echo "🌐 P2P Network Analysis:"
echo "Checking if nodes can discover each other..."

# Try to check if A0 knows about A1 as a peer
a0_peers=$(curl -s --max-time 3 "http://11.0.0.1:28090/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_peer_list"}' \
    -H 'Content-Type: application/json' 2>/dev/null)

if [[ -n "$a0_peers" && "$a0_peers" != *"Connection refused"* ]]; then
    echo "  📡 A0 peer discovery working"
    if [[ "$a0_peers" == *"11.0.0.2"* ]]; then
        echo "  ✅ A0 knows about A1"
    else
        echo "  ⏳ A0 hasn't discovered A1 yet"
    fi
else
    echo "  ❌ A0 peer discovery failed"
fi

echo ""
echo "=== End Enhanced Monitor ===" 