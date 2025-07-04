#!/bin/bash

# Monitor script for Monero nodes in Shadow simulation
# This script polls the RPC endpoints of all nodes to check their status

NODES=("a0" "a1" "a2" "a3" "a4")
RPC_PORTS=(28090 28091 28092 28093 28094)
P2P_PORTS=(28080 28081 28082 28083 28084)

echo "=== Monero Network Monitor ==="
echo "Time: $(date)"
echo ""

for i in "${!NODES[@]}"; do
    NODE=${NODES[$i]}
    RPC_PORT=${RPC_PORTS[$i]}
    P2P_PORT=${P2P_PORTS[$i]}
    NODE_IP="11.0.0.$((i+1))"
    
    echo "--- Node $NODE ($NODE_IP) ---"
    echo "RPC Port: $RPC_PORT, P2P Port: $P2P_PORT"
    
    # Check if RPC is responding
    if curl -s --max-time 5 "http://$NODE_IP:$RPC_PORT/json_rpc" -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' > /dev/null 2>&1; then
        echo "✅ RPC is responding"
        
        # Get node info
        INFO=$(curl -s --max-time 5 "http://$NODE_IP:$RPC_PORT/json_rpc" -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}')
        if [ $? -eq 0 ]; then
            echo "Node Info: $INFO"
        fi
        
        # Get connection count
        CONNECTIONS=$(curl -s --max-time 5 "http://$NODE_IP:$RPC_PORT/json_rpc" -d '{"jsonrpc":"2.0","id":"0","method":"get_connections_count"}')
        if [ $? -eq 0 ]; then
            echo "Connections: $CONNECTIONS"
        fi
        
        # Get peer list
        PEERS=$(curl -s --max-time 5 "http://$NODE_IP:$RPC_PORT/json_rpc" -d '{"jsonrpc":"2.0","id":"0","method":"get_peer_list"}')
        if [ $? -eq 0 ]; then
            echo "Peers: $PEERS"
        fi
        
    else
        echo "❌ RPC not responding"
    fi
    
    echo ""
done

echo "=== End Monitor ===" 