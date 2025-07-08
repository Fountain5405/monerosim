#!/bin/bash

# Simple monitor script that outputs raw JSON responses
echo "=== Monero Network Monitor - Raw JSON Output ==="
echo "Time: $(date)"
echo ""

# Node A0
echo "--- Node A0 (11.0.0.1:28090) ---"
echo "get_info:"
curl -s --max-time 5 "http://11.0.0.1:28090/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
    -H 'Content-Type: application/json' 2>/dev/null || echo "RPC call failed"

echo ""
echo "get_connections:"
curl -s --max-time 5 "http://11.0.0.1:28090/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_connections"}' \
    -H 'Content-Type: application/json' 2>/dev/null || echo "RPC call failed"

echo ""
echo "mining_status:"
curl -s --max-time 5 "http://11.0.0.1:28090/mining_status" \
    -H 'Content-Type: application/json' 2>/dev/null || echo "RPC call failed"

echo ""
echo ""

# Node A1
echo "--- Node A1 (11.0.0.2:28090) ---"
echo "get_info:"
curl -s --max-time 5 "http://11.0.0.2:28090/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
    -H 'Content-Type: application/json' 2>/dev/null || echo "RPC call failed"

echo ""
echo "get_connections:"
curl -s --max-time 5 "http://11.0.0.2:28090/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_connections"}' \
    -H 'Content-Type: application/json' 2>/dev/null || echo "RPC call failed"

echo ""
echo "mining_status:"
curl -s --max-time 5 "http://11.0.0.2:28090/mining_status" \
    -H 'Content-Type: application/json' 2>/dev/null || echo "RPC call failed"

echo ""
echo "=== End Monitor ===" 