#!/bin/bash

# Two-Wallet Transaction Testing Script
# This script uses two separate wallet RPC instances:
# - wallet1 (mining wallet) on port 28091
# - wallet2 (recipient wallet) on port 28092
# 
# New strategy: Wait 1 hour for mining rewards to unlock, then create transaction
# Block production: 1 block per minute (realistic timing)
# Mining rewards unlock after 10 confirmations = 10 minutes
# Wait 1 hour to be absolutely sure, then test transaction

echo "=== MoneroSim Two-Wallet Transaction Test ==="
echo "Starting transaction test at $(date)"

# Configuration
WALLET1_RPC="http://11.0.0.6:28091/json_rpc"  # Mining wallet (automatic IP assignment)
WALLET2_RPC="http://11.0.0.7:28092/json_rpc"  # Recipient wallet (automatic IP assignment)
TRANSACTION_TEST_TIME=3600  # 1 hour (3600s) - wait for mining rewards to unlock
WAIT_AFTER_TRANSACTION=3600  # Wait another hour to see transaction propagation

# Function to call wallet1 RPC with retry logic
call_wallet1() {
    local max_retries=3
    local retry_count=0
    local response=""
    
    while [ $retry_count -lt $max_retries ]; do
        response=$(curl -s --max-time 15 --connect-timeout 5 "$WALLET1_RPC" \
            -d "$1" \
            -H 'Content-Type: application/json' 2>/dev/null)
        
        if [[ -n "$response" && "$response" != *"Failed to connect"* && "$response" != *"Connection refused"* ]]; then
            echo "$response"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        echo "Wallet1 RPC call failed (attempt $retry_count/$max_retries), retrying in 2 seconds..."
        sleep 2
    done
    
    echo "ERROR: Failed to get response from wallet1 RPC after $max_retries attempts"
    return 1
}

# Function to call wallet2 RPC with retry logic
call_wallet2() {
    local max_retries=3
    local retry_count=0
    local response=""
    
    while [ $retry_count -lt $max_retries ]; do
        response=$(curl -s --max-time 15 --connect-timeout 5 "$WALLET2_RPC" \
            -d "$1" \
            -H 'Content-Type: application/json' 2>/dev/null)
        
        if [[ -n "$response" && "$response" != *"Failed to connect"* && "$response" != *"Connection refused"* ]]; then
            echo "$response"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        echo "Wallet2 RPC call failed (attempt $retry_count/$max_retries), retrying in 2 seconds..."
        sleep 2
    done
    
    echo "ERROR: Failed to get response from wallet2 RPC after $max_retries attempts"
    return 1
}

# Function to check if RPC response indicates success
check_rpc_success() {
    local response="$1"
    if [[ -z "$response" || "$response" == *'"error"'* ]]; then
        return 1
    fi
    if [[ "$response" == *'"result"'* ]]; then
        return 0
    fi
    return 1
}

# Function to refresh wallet and maintain connection
refresh_wallet() {
    local wallet_num="$1"
    echo "🔄 Refreshing wallet$wallet_num (maintaining connection)..."
    
    if [ "$wallet_num" = "1" ]; then
        local refresh_response=$(call_wallet1 '{"jsonrpc":"2.0","id":"0","method":"refresh"}')
    else
        local refresh_response=$(call_wallet2 '{"jsonrpc":"2.0","id":"0","method":"refresh"}')
    fi
    
    echo "Wallet$wallet_num refresh: $refresh_response"
    return 0
}

echo "Step 1: Wait for wallet RPC services to start"
sleep 10

echo "Step 2: Test wallet RPC connectivity"
WALLET1_TEST=$(call_wallet1 '{"jsonrpc":"2.0","id":"0","method":"get_version"}')
WALLET2_TEST=$(call_wallet2 '{"jsonrpc":"2.0","id":"0","method":"get_version"}')
echo "Wallet1 connectivity: $WALLET1_TEST"
echo "Wallet2 connectivity: $WALLET2_TEST"

if ! check_rpc_success "$WALLET1_TEST" || ! check_rpc_success "$WALLET2_TEST"; then
    echo "ERROR: Cannot connect to wallet RPC services. Exiting."
    exit 1
fi

echo "Step 3: Create mining wallet (wallet1)"
CREATE_WALLET1_RESPONSE=$(call_wallet1 '{"jsonrpc":"2.0","id":"0","method":"create_wallet","params":{"filename":"mining_wallet","password":"test123","language":"English"}}')
echo "Create wallet1 response: $CREATE_WALLET1_RESPONSE"

# If wallet already exists, try to open it
if [[ "$CREATE_WALLET1_RESPONSE" == *"already exists"* || "$CREATE_WALLET1_RESPONSE" == *"error"* ]]; then
    echo "Mining wallet exists, trying to open existing wallet..."
    OPEN_WALLET1_RESPONSE=$(call_wallet1 '{"jsonrpc":"2.0","id":"0","method":"open_wallet","params":{"filename":"mining_wallet","password":"test123"}}')
    echo "Open wallet1 response: $OPEN_WALLET1_RESPONSE"
fi

echo "Step 4: Create recipient wallet (wallet2)"
CREATE_WALLET2_RESPONSE=$(call_wallet2 '{"jsonrpc":"2.0","id":"0","method":"create_wallet","params":{"filename":"recipient_wallet","password":"test456","language":"English"}}')
echo "Create wallet2 response: $CREATE_WALLET2_RESPONSE"

# If wallet already exists, try to open it
if [[ "$CREATE_WALLET2_RESPONSE" == *"already exists"* || "$CREATE_WALLET2_RESPONSE" == *"error"* ]]; then
    echo "Recipient wallet exists, trying to open existing wallet..."
    OPEN_WALLET2_RESPONSE=$(call_wallet2 '{"jsonrpc":"2.0","id":"0","method":"open_wallet","params":{"filename":"recipient_wallet","password":"test456"}}')
    echo "Open wallet2 response: $OPEN_WALLET2_RESPONSE"
fi

echo "Step 5: Get wallet addresses"
WALLET1_ADDRESS_RESPONSE=$(call_wallet1 '{"jsonrpc":"2.0","id":"0","method":"get_address","params":{"account_index":0}}')
WALLET2_ADDRESS_RESPONSE=$(call_wallet2 '{"jsonrpc":"2.0","id":"0","method":"get_address","params":{"account_index":0}}')

echo "Wallet1 address response: $WALLET1_ADDRESS_RESPONSE"
echo "Wallet2 address response: $WALLET2_ADDRESS_RESPONSE"

# Extract addresses
WALLET1_ADDRESS=$(echo "$WALLET1_ADDRESS_RESPONSE" | tr -d '\n\r\t' | sed 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
WALLET2_ADDRESS=$(echo "$WALLET2_ADDRESS_RESPONSE" | tr -d '\n\r\t' | sed 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

echo "🏦 WALLET SETUP COMPLETE:"
echo "  Mining wallet (wallet1): $WALLET1_ADDRESS"
echo "  Recipient wallet (wallet2): $WALLET2_ADDRESS"
echo "  Expected mining address: 48S1ZANZRDGTqF7rdxCh8R4jvBELF63u9MieHNwGNYrRZWka84mN9ttV88eq2QScJRHJsdHJMNg3LDu3Z21hmaE61SWymvv"

echo "Step 6: Wait for mining rewards to unlock (1 hour)"
echo "With 1 block per minute, mining rewards need 10 minutes to unlock."
echo "Waiting 1 hour to be absolutely certain rewards are available..."
echo "Target transaction time: $TRANSACTION_TEST_TIME seconds (1 hour)"

# Simple wait approach - let Monero's natural refresh handle synchronization
echo "⏰ Waiting ${TRANSACTION_TEST_TIME} seconds for mining rewards to accumulate and unlock..."
sleep $TRANSACTION_TEST_TIME

echo "Step 7: Final refresh before transaction"
echo "🔄 Performing final refresh after 1-hour wait..."
refresh_wallet 1
refresh_wallet 2

echo "Step 8: Check wallet1 balance after synchronization period"
WALLET1_BALANCE_RESPONSE=$(call_wallet1 '{"jsonrpc":"2.0","id":"0","method":"get_balance","params":{"account_index":0}}')
echo "Wallet1 balance response: $WALLET1_BALANCE_RESPONSE"

# Extract balance information
UNLOCKED_BALANCE=$(echo "$WALLET1_BALANCE_RESPONSE" | tr -d '\n' | grep -o '"unlocked_balance":[[:space:]]*[0-9]*' | sed 's/.*://')
TOTAL_BALANCE=$(echo "$WALLET1_BALANCE_RESPONSE" | tr -d '\n' | grep -o '"balance":[[:space:]]*[0-9]*' | sed 's/.*://')

echo "Raw total balance (atomic units): $TOTAL_BALANCE"
echo "Raw unlocked balance (atomic units): $UNLOCKED_BALANCE"

# Convert to XMR (divide by 1e12)
if [[ -n "$UNLOCKED_BALANCE" && "$UNLOCKED_BALANCE" -gt 0 ]]; then
    UNLOCKED_XMR=$((UNLOCKED_BALANCE / 1000000000000))
    TOTAL_XMR=$((TOTAL_BALANCE / 1000000000000))
    echo "💰 WALLET1 BALANCE: $TOTAL_XMR XMR total, $UNLOCKED_XMR XMR unlocked"
    
    if [[ "$UNLOCKED_XMR" -gt 0 ]]; then
        echo "Step 9: Create inter-wallet transaction (1 XMR from wallet1 to wallet2)"
        
        # Create transaction for 1 XMR (1000000000000 atomic units)
        TRANSFER_RESPONSE=$(call_wallet1 '{"jsonrpc":"2.0","id":"0","method":"transfer","params":{"destinations":[{"amount":1000000000000,"address":"'$WALLET2_ADDRESS'"}],"priority":1,"get_tx_key":true}}')
        echo "🚀 TRANSACTION CREATED: $TRANSFER_RESPONSE"
        
        # Check if transfer was successful
        if check_rpc_success "$TRANSFER_RESPONSE"; then
            # Extract transaction hash
            TX_HASH=$(echo "$TRANSFER_RESPONSE" | grep -o '"tx_hash":"[^"]*"' | cut -d'"' -f4)
            echo "📋 Transaction hash: $TX_HASH"
            
            if [[ -n "$TX_HASH" ]]; then
                echo "✅ SUCCESS: Inter-wallet transaction created successfully!"
                echo "📊 TRANSACTION SUMMARY:"
                echo "  From: Wallet1 (mining) - $WALLET1_ADDRESS"
                echo "  To: Wallet2 (recipient) - $WALLET2_ADDRESS"
                echo "  Amount: 1 XMR"
                echo "  Transaction hash: $TX_HASH"
                echo "  Sender balance after: $((UNLOCKED_XMR - 1)) XMR unlocked"
                
                # Wait for transaction to propagate
                echo "Step 10: Wait for transaction to propagate in network"
                sleep 30  # Brief wait for immediate propagation
                
                # Refresh recipient wallet to see incoming transaction
                echo "Step 11: Check recipient wallet for incoming transaction"
                refresh_wallet 2
                WALLET2_BALANCE_RESPONSE=$(call_wallet2 '{"jsonrpc":"2.0","id":"0","method":"get_balance","params":{"account_index":0}}')
                echo "Wallet2 balance response: $WALLET2_BALANCE_RESPONSE"
                
                echo "Step 12: Continue simulation for another hour to observe transaction confirmation"
                echo "⏰ Waiting another ${WAIT_AFTER_TRANSACTION} seconds to observe transaction processing..."
                sleep $WAIT_AFTER_TRANSACTION
                
                echo "Step 13: Final check of recipient wallet balance"
                refresh_wallet 2
                WALLET2_FINAL_BALANCE=$(call_wallet2 '{"jsonrpc":"2.0","id":"0","method":"get_balance","params":{"account_index":0}}')
                echo "Wallet2 final balance: $WALLET2_FINAL_BALANCE"
                
                echo "🎉 TWO-WALLET TRANSACTION TEST COMPLETE!"
                echo "✅ Successfully created transaction between separate wallet instances"
                echo "✅ Mining wallet (wallet1) sent 1 XMR to recipient wallet (wallet2)"
                echo "✅ Transaction hash: $TX_HASH"
                echo "✅ Simulation ran for 2 hours with realistic 1-block-per-minute timing"
                echo "✅ Transaction created at 1-hour mark, observed for additional hour"
                
                # Exit successfully
                exit 0
            else
                echo "❌ ERROR: Failed to extract transaction hash"
                exit 1
            fi
        else
            echo "❌ ERROR: Transaction creation failed: $TRANSFER_RESPONSE"
            exit 1
        fi
    else
        echo "❌ ERROR: Insufficient unlocked balance (need > 0 XMR, have $UNLOCKED_XMR XMR)"
        echo "ℹ️  Mining rewards may need more time to unlock (10 confirmations)"
        exit 1
    fi
else
    echo "❌ ERROR: Failed to get valid balance from wallet1"
    echo "ℹ️  This could indicate connection issues or insufficient sync time"
    exit 1
fi

echo "=== Two-Wallet Transaction Test Complete ===" 