#!/bin/bash

# Transaction testing script that runs INSIDE Shadow simulation
# This script connects to the wallet RPC at 11.0.0.3:28091

echo "=== Transaction Test Inside Shadow ==="
echo "Starting transaction test at $(date)"

# Wait for wallet to be ready
echo "Waiting for wallet RPC to be ready..."
sleep 2

# Function to call wallet RPC
call_wallet() {
    curl -s --max-time 10 "http://127.0.0.1:28091/json_rpc" \
        -d "$1" \
        -H 'Content-Type: application/json'
}

echo "Step 1: Create mining wallet"
WALLET_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"create_wallet","params":{"filename":"mining_wallet","password":"test123","language":"English"}}')
echo "Create wallet response: $WALLET_RESPONSE"

echo "Step 2: Wait for wallet to sync"
sleep 1

echo "Step 3: Check wallet balance"
BALANCE_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"get_balance"}')
echo "Balance response: $BALANCE_RESPONSE"

echo "Step 4: Get wallet address"
ADDRESS_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"get_address"}')
echo "Address response: $ADDRESS_RESPONSE"

echo "Step 5: Create destination address"
DEST_ADDRESS_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"create_address","params":{"account_index":0}}')
echo "Destination address response: $DEST_ADDRESS_RESPONSE"

echo "Step 6: Attempt transaction (if balance > 0)"
# Extract balance from JSON (simple approach)
if echo "$BALANCE_RESPONSE" | grep -q '"balance":[1-9]'; then
    echo "Wallet has balance, attempting transaction..."
    TRANSFER_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"transfer","params":{"destinations":[{"amount":2000000000000,"address":"9wviCeWe2D8XS82k2ovp5EUYLzBt9pYNW2LXUFsZiv8S3Mt21FZ5qQaAroko1enzw3eGr9qC7X1D7Geoo2RrAotYPwq9Gm8"}],"priority":1,"ring_size":11}}')
    echo "Transfer response: $TRANSFER_RESPONSE"
else
    echo "Wallet has no balance, skipping transaction"
fi

echo "Step 7: Check transaction pool on nodes"
echo "Checking node A0 transaction pool..."
curl -s --max-time 5 "http://11.0.0.1:28090/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_transaction_pool_stats"}' \
    -H 'Content-Type: application/json'

echo ""
echo "Checking node A1 transaction pool..."
curl -s --max-time 5 "http://11.0.0.2:28090/json_rpc" \
    -d '{"jsonrpc":"2.0","id":"0","method":"get_transaction_pool_stats"}' \
    -H 'Content-Type: application/json'

echo ""
echo "=== Transaction Test Complete ===" 