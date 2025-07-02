#!/bin/bash

# Monitor script for Monero nodes in Shadow simulation
# This script continuously queries all nodes for status and connection info

TOTAL_NODES=5
LOG_FILE="/tmp/monitor.log"

echo "Starting Monero node monitor at $(date)" | tee -a $LOG_FILE

# Function to query a single node
query_node() {
    local node_id=$1
    local node_ip="11.0.0.$((node_id + 1))"
    local rpc_port=$((28090 + node_id))
    
    echo "=== Querying node $node_id ($node_ip:$rpc_port) at $(date) ===" | tee -a $LOG_FILE
    
    # Query node info
    echo "Node $node_id - get_info:" | tee -a $LOG_FILE
    curl -s -X POST http://$node_ip:$rpc_port/json_rpc \
        -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
        -H 'Content-Type: application/json' 2>/dev/null | tee -a $LOG_FILE
    
    echo "" | tee -a $LOG_FILE
    
    # Query connections
    echo "Node $node_id - get_connections:" | tee -a $LOG_FILE
    curl -s -X POST http://$node_ip:$rpc_port/json_rpc \
        -d '{"jsonrpc":"2.0","id":"0","method":"get_connections"}' \
        -H 'Content-Type: application/json' 2>/dev/null | tee -a $LOG_FILE
    
    echo "" | tee -a $LOG_FILE
    echo "----------------------------------------" | tee -a $LOG_FILE
}

# Main monitoring loop
while true; do
    echo "=== MONITORING ROUND STARTED at $(date) ===" | tee -a $LOG_FILE
    
    # Query all nodes
    for i in $(seq 0 $((TOTAL_NODES - 1))); do
        query_node $i
    done
    
    echo "=== MONITORING ROUND COMPLETED at $(date) ===" | tee -a $LOG_FILE
    echo "" | tee -a $LOG_FILE
    
    # Wait 10 seconds before next round
    sleep 10
done 