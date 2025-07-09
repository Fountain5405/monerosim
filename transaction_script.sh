#!/bin/bash

# Transaction testing script that runs INSIDE Shadow simulation
# This script connects to the wallet RPC at 127.0.0.1:28091

echo "=== MoneroSim Transaction Test ==="
echo "Starting transaction test at $(date)"

# Wait for wallet to be ready
echo "Waiting for wallet RPC to be ready..."
sleep 1

# Function to call wallet RPC with better error handling
call_wallet() {
    local response=$(curl -s --max-time 30 --connect-timeout 10 "http://11.0.0.6:28091/json_rpc" \
        -d "$1" \
        -H 'Content-Type: application/json' 2>/dev/null)
    echo "$response"
}

# Function to call node RPC
call_node() {
    local response=$(curl -s --max-time 10 "http://11.0.0.1:28090/json_rpc" \
        -d "$1" \
        -H 'Content-Type: application/json' 2>/dev/null)
    echo "$response"
}

echo "Step 1: Test wallet RPC connectivity"
WALLET_TEST=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"get_version"}')
echo "Wallet connectivity test: $WALLET_TEST"

if [[ -z "$WALLET_TEST" || "$WALLET_TEST" == *"error"* ]]; then
    echo "ERROR: Cannot connect to wallet RPC. Retrying..."
    sleep 1
    WALLET_TEST=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"get_version"}')
    echo "Retry result: $WALLET_TEST"
fi

echo "Step 2: Create mining wallet"
CREATE_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"create_wallet","params":{"filename":"mining_wallet","password":"test123","language":"English"}}')
echo "Create wallet response: $CREATE_RESPONSE"

# If wallet already exists, try to open it
if [[ "$CREATE_RESPONSE" == *"already exists"* || "$CREATE_RESPONSE" == *"error"* ]]; then
    echo "Wallet exists or error, trying to open existing wallet..."
    OPEN_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"open_wallet","params":{"filename":"mining_wallet","password":"test123"}}')
    echo "Open wallet response: $OPEN_RESPONSE"
fi

echo "Step 3: Wait for wallet daemon sync"
sleep 1

echo "Step 4: Get wallet address"
ADDRESS_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"get_address","params":{"account_index":0}}')
echo "Wallet address response: $ADDRESS_RESPONSE"

# Extract address from response
WALLET_ADDRESS=$(echo "$ADDRESS_RESPONSE" | grep -o '"address":"[^"]*"' | cut -d'"' -f4)
echo "Extracted wallet address: $WALLET_ADDRESS"

echo "Step 5: Check initial wallet balance"
BALANCE_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"get_balance","params":{"account_index":0}}')
echo "Initial balance response: $BALANCE_RESPONSE"

echo "Step 6: Refresh wallet (sync with daemon)"
REFRESH_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"refresh"}')
echo "Refresh response: $REFRESH_RESPONSE"

# Wait for refresh to complete
sleep 1

echo "Step 7: Check balance after refresh"
BALANCE_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"get_balance","params":{"account_index":0}}')
echo "Balance after refresh: $BALANCE_RESPONSE"

# Extract balance (convert from atomic units)
BALANCE=$(echo "$BALANCE_RESPONSE" | grep -o '"balance":[0-9]*' | cut -d':' -f2)
echo "Raw balance (atomic units): $BALANCE"

if [[ -n "$BALANCE" && "$BALANCE" -gt 0 ]]; then
    BALANCE_XMR=$((BALANCE / 1000000000000))
    echo "Balance in XMR: $BALANCE_XMR"
    
    if [[ "$BALANCE_XMR" -gt 1 ]]; then
        echo "Step 8: CREATE TRANSACTION - Send 1 XMR to new address"
        
        # Generate a new address for testing
        NEW_ADDRESS_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"create_address","params":{"account_index":0}}')
        echo "New address response: $NEW_ADDRESS_RESPONSE"
        
        DEST_ADDRESS=$(echo "$NEW_ADDRESS_RESPONSE" | grep -o '"address":"[^"]*"' | cut -d'"' -f4)
        echo "Destination address: $DEST_ADDRESS"
        
        if [[ -n "$DEST_ADDRESS" ]]; then
            # Create transaction for 1 XMR (1000000000000 atomic units)
            TRANSFER_RESPONSE=$(call_wallet '{"jsonrpc":"2.0","id":"0","method":"transfer","params":{"destinations":[{"amount":1000000000000,"address":"'$DEST_ADDRESS'"}],"priority":1,"get_tx_key":true}}')
            echo "🚀 TRANSACTION CREATED: $TRANSFER_RESPONSE"
            
            # Extract transaction hash
            TX_HASH=$(echo "$TRANSFER_RESPONSE" | grep -o '"tx_hash":"[^"]*"' | cut -d'"' -f4)
            echo "📋 Transaction hash: $TX_HASH"
            
            if [[ -n "$TX_HASH" ]]; then
                echo "✅ SUCCESS: Transaction created and submitted to network!"
                echo "Transaction hash: $TX_HASH"
                
                # Wait for transaction to propagate
                sleep 1
                
                echo "Step 9: Verify transaction in node A0 mempool"
                NODE_POOL=$(call_node '{"jsonrpc":"2.0","id":"0","method":"get_transaction_pool"}')
                echo "Node A0 transaction pool: $NODE_POOL"
                
                echo "Step 10: Verify transaction in node A1 mempool"
                NODE_A1_POOL=$(curl -s --max-time 5 "http://11.0.0.2:28090/json_rpc" \
                    -d '{"jsonrpc":"2.0","id":"0","method":"get_transaction_pool"}' \
                    -H 'Content-Type: application/json' 2>/dev/null)
                echo "Node A1 transaction pool: $NODE_A1_POOL"
                
                echo "🎉 LEVEL 3 (TRANSACTION PROCESSING) TEST COMPLETE!"
                echo "Transaction successfully created and transmitted to network!"
            else
                echo "❌ ERROR: Failed to extract transaction hash"
            fi
        else
            echo "❌ ERROR: Failed to create destination address"
        fi
    else
        echo "❌ ERROR: Insufficient balance for transaction (need > 1 XMR, have $BALANCE_XMR XMR)"
    fi
else
    echo "❌ ERROR: No balance available or balance check failed"
fi

echo "=== Transaction Test Complete ===" 