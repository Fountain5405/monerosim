#!/bin/bash

# Two-Wallet Transaction Testing Script
# This script uses two separate wallet RPC instances:
# - wallet1 (mining wallet) on port 28091
# - wallet2 (recipient wallet) on port 28092
#
# Simplified test: Wait 5 minutes for basic setup, then test transaction
# Block production: 1 block per minute (realistic timing)

# Source the central network configuration and error handling library
source "$(dirname "$0")/network_config.sh"
source "$(dirname "$0")/error_handling.sh"

# Component name for logging
COMPONENT="TRANSACTION_SCRIPT"

# Configuration
TRANSACTION_TEST_TIME=300  # 5 minutes (300s) - simplified test
WAIT_AFTER_TRANSACTION=120  # Wait another 2 minutes to see transaction propagation
MAX_ATTEMPTS=3
RETRY_DELAY=2
CHECK_INTERVAL=300  # Check every 5 minutes
TRANSACTION_AMOUNT=1000000000000  # 1 XMR in atomic units

log_info "$COMPONENT" "=== MoneroSim Two-Wallet Transaction Test ==="
log_info "$COMPONENT" "Starting transaction test at $(date)"

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
    local wallet_url="$1"
    local wallet_name="$2"
    
    log_info "$COMPONENT" "Refreshing $wallet_name (maintaining connection)..."
    
    local refresh_response=$(call_wallet_with_retry "$wallet_url" "refresh" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    local status=$?
    
    if [[ $status -eq 0 ]]; then
        log_info "$COMPONENT" "$wallet_name refresh successful"
    else
        log_warning "$COMPONENT" "$wallet_name refresh failed, but continuing"
    fi
    
    return 0
}

log_info "$COMPONENT" "Step 1: Wait for wallet RPC services to start"
sleep 30

log_info "$COMPONENT" "Step 2: Test wallet RPC connectivity"
# Verify wallet RPC connectivity
WALLET1_TEST=$(call_wallet_with_retry "$WALLET1_RPC" "get_version" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
WALLET1_STATUS=$?

WALLET2_TEST=$(call_wallet_with_retry "$WALLET2_RPC" "get_version" "{}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
WALLET2_STATUS=$?

if [[ $WALLET1_STATUS -ne 0 || $WALLET2_STATUS -ne 0 ]]; then
    log_critical "$COMPONENT" "Cannot connect to wallet RPC services. Exiting."
    handle_exit 1 "$COMPONENT" "Wallet RPC connectivity test failed"
fi

log_info "$COMPONENT" "Step 3-4: Verify wallet creation for both wallets"
# Verify wallet creation for both wallets
if ! verify_wallet_created "$WALLET1_RPC" "$WALLET1_NAME" "$WALLET1_PASSWORD" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    log_critical "$COMPONENT" "Wallet1 creation verification failed"
    handle_exit 1 "$COMPONENT" "Wallet1 creation failed"
fi

if ! verify_wallet_created "$WALLET2_RPC" "$WALLET2_NAME" "$WALLET2_PASSWORD" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
    log_critical "$COMPONENT" "Wallet2 creation verification failed"
    handle_exit 1 "$COMPONENT" "Wallet2 creation failed"
fi

log_info "$COMPONENT" "Step 5: Get wallet addresses"
# Get wallet addresses
WALLET1_ADDRESS_RESPONSE=$(call_wallet_with_retry "$WALLET1_RPC" "get_address" "{\"account_index\":0}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get Wallet1 address"
    handle_exit 1 "$COMPONENT" "Wallet1 address retrieval failed"
fi

WALLET2_ADDRESS_RESPONSE=$(call_wallet_with_retry "$WALLET2_RPC" "get_address" "{\"account_index\":0}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get Wallet2 address"
    handle_exit 1 "$COMPONENT" "Wallet2 address retrieval failed"
fi

# Extract addresses
WALLET1_ADDRESS=$(echo "$WALLET1_ADDRESS_RESPONSE" | tr -d '\n\r\t' | sed 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
WALLET2_ADDRESS=$(echo "$WALLET2_ADDRESS_RESPONSE" | tr -d '\n\r\t' | sed 's/.*"address"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -z "$WALLET1_ADDRESS" || -z "$WALLET2_ADDRESS" ]]; then
    log_critical "$COMPONENT" "Failed to extract wallet addresses"
    handle_exit 1 "$COMPONENT" "Wallet address extraction failed"
fi

log_info "$COMPONENT" "🏦 WALLET SETUP COMPLETE:"
log_info "$COMPONENT" "  Mining wallet (wallet1): $WALLET1_ADDRESS"
log_info "$COMPONENT" "  Recipient wallet (wallet2): $WALLET2_ADDRESS"

log_info "$COMPONENT" "Step 6: Wait for mining rewards to unlock"
log_info "$COMPONENT" "With 1 block per minute, mining rewards need 60 confirmations to unlock."
log_info "$COMPONENT" "Waiting up to $TRANSACTION_TEST_TIME seconds for rewards to unlock, checking balance every $CHECK_INTERVAL seconds..."

# Intelligent wait approach - check balance periodically
WAIT_START_TIME=$(date +%s)
MAX_WAIT_TIME=$TRANSACTION_TEST_TIME

while true; do
    # Check current time
    CURRENT_TIME=$(date +%s)
    ELAPSED_TIME=$((CURRENT_TIME - WAIT_START_TIME))
    
    if [[ $ELAPSED_TIME -ge $MAX_WAIT_TIME ]]; then
        log_info "$COMPONENT" "⏰ Maximum wait time reached (${MAX_WAIT_TIME}s). Proceeding with transaction attempt..."
        break
    fi
    
    # Refresh wallet and check balance
    log_info "$COMPONENT" "🔄 Checking wallet balance (${ELAPSED_TIME}s elapsed)..."
    refresh_wallet "$WALLET1_RPC" "Wallet1"
    
    WALLET1_BALANCE_RESPONSE=$(call_wallet_with_retry "$WALLET1_RPC" "get_balance" "{\"account_index\":0}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
    if [[ $? -ne 0 ]]; then
        log_warning "$COMPONENT" "Failed to get wallet balance, retrying later..."
        sleep $CHECK_INTERVAL
        continue
    fi
    
    UNLOCKED_BALANCE=$(echo "$WALLET1_BALANCE_RESPONSE" | tr -d '\n' | grep -o '"unlocked_balance":[[:space:]]*[0-9]*' | sed 's/.*://')
    
    if [[ -n "$UNLOCKED_BALANCE" && "$UNLOCKED_BALANCE" -gt 1000000000000 ]]; then
        # Convert to XMR for display
        UNLOCKED_XMR=$((UNLOCKED_BALANCE / 1000000000000))
        log_info "$COMPONENT" "💰 SUCCESS: Found unlocked balance of $UNLOCKED_XMR XMR! Proceeding with transaction..."
        break
    else
        log_info "$COMPONENT" "⏳ Still waiting for rewards to unlock... (${ELAPSED_TIME}s elapsed, ${MAX_WAIT_TIME}s max)"
        sleep $CHECK_INTERVAL
    fi
done

log_info "$COMPONENT" "Step 7: Final refresh before transaction"
refresh_wallet "$WALLET1_RPC" "Wallet1"
refresh_wallet "$WALLET2_RPC" "Wallet2"

log_info "$COMPONENT" "Step 8: Check wallet1 balance after synchronization period"
WALLET1_BALANCE_RESPONSE=$(call_wallet_with_retry "$WALLET1_RPC" "get_balance" "{\"account_index\":0}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
if [[ $? -ne 0 ]]; then
    log_critical "$COMPONENT" "Failed to get final wallet balance"
    handle_exit 1 "$COMPONENT" "Wallet balance check failed"
fi

# Extract balance information
UNLOCKED_BALANCE=$(echo "$WALLET1_BALANCE_RESPONSE" | tr -d '\n' | grep -o '"unlocked_balance":[[:space:]]*[0-9]*' | sed 's/.*://')
TOTAL_BALANCE=$(echo "$WALLET1_BALANCE_RESPONSE" | tr -d '\n' | grep -o '"balance":[[:space:]]*[0-9]*' | sed 's/.*://')

log_info "$COMPONENT" "Raw total balance (atomic units): $TOTAL_BALANCE"
log_info "$COMPONENT" "Raw unlocked balance (atomic units): $UNLOCKED_BALANCE"

# Convert to XMR (divide by 1e12)
if [[ -n "$UNLOCKED_BALANCE" && "$UNLOCKED_BALANCE" -gt 0 ]]; then
    UNLOCKED_XMR=$((UNLOCKED_BALANCE / 1000000000000))
    TOTAL_XMR=$((TOTAL_BALANCE / 1000000000000))
    log_info "$COMPONENT" "💰 WALLET1 BALANCE: $TOTAL_XMR XMR total, $UNLOCKED_XMR XMR unlocked"
    
    if [[ "$UNLOCKED_XMR" -gt 0 ]]; then
        log_info "$COMPONENT" "Step 9: Create inter-wallet transaction (1 XMR from wallet1 to wallet2)"
        
        # Verify transaction processing
        if verify_transaction "$WALLET1_RPC" "$WALLET2_ADDRESS" "$TRANSACTION_AMOUNT" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT"; then
            # Get transaction details from the response
            TRANSFER_RESPONSE=$(call_wallet_with_retry "$WALLET1_RPC" "get_transfers" "{\"out\":true,\"pending\":true,\"pool\":true}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
            TX_HASH=$(echo "$TRANSFER_RESPONSE" | grep -o '"txid":"[^"]*"' | head -1 | cut -d'"' -f4)
            
            log_info "$COMPONENT" "✅ SUCCESS: Inter-wallet transaction created successfully!"
            log_info "$COMPONENT" "📊 TRANSACTION SUMMARY:"
            log_info "$COMPONENT" "  From: Wallet1 (mining) - $WALLET1_ADDRESS"
            log_info "$COMPONENT" "  To: Wallet2 (recipient) - $WALLET2_ADDRESS"
            log_info "$COMPONENT" "  Amount: 1 XMR"
            log_info "$COMPONENT" "  Transaction hash: $TX_HASH"
            log_info "$COMPONENT" "  Sender balance after: $((UNLOCKED_XMR - 1)) XMR unlocked"
            
            # Wait for transaction to propagate
            log_info "$COMPONENT" "Step 10: Wait for transaction to propagate in network"
            sleep 30  # Brief wait for immediate propagation
            
            # Refresh recipient wallet to see incoming transaction
            log_info "$COMPONENT" "Step 11: Check recipient wallet for incoming transaction"
            refresh_wallet "$WALLET2_RPC" "Wallet2"
            WALLET2_BALANCE_RESPONSE=$(call_wallet_with_retry "$WALLET2_RPC" "get_balance" "{\"account_index\":0}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
            log_info "$COMPONENT" "Wallet2 balance response: $WALLET2_BALANCE_RESPONSE"
            
            log_info "$COMPONENT" "Step 12: Continue simulation to observe transaction confirmation"
            log_info "$COMPONENT" "⏰ Waiting another ${WAIT_AFTER_TRANSACTION} seconds to observe transaction processing..."
            sleep $WAIT_AFTER_TRANSACTION
            
            log_info "$COMPONENT" "Step 13: Final check of recipient wallet balance"
            refresh_wallet "$WALLET2_RPC" "Wallet2"
            WALLET2_FINAL_BALANCE=$(call_wallet_with_retry "$WALLET2_RPC" "get_balance" "{\"account_index\":0}" "$MAX_ATTEMPTS" "$RETRY_DELAY" "$COMPONENT")
            log_info "$COMPONENT" "Wallet2 final balance: $WALLET2_FINAL_BALANCE"
            
            log_info "$COMPONENT" "🎉 TWO-WALLET TRANSACTION TEST COMPLETE!"
            log_info "$COMPONENT" "✅ Successfully created transaction between separate wallet instances"
            log_info "$COMPONENT" "✅ Mining wallet (wallet1) sent 1 XMR to recipient wallet (wallet2)"
            log_info "$COMPONENT" "✅ Transaction hash: $TX_HASH"
            
            # Exit successfully
            handle_exit 0 "$COMPONENT" "Transaction test completed successfully"
        else
            log_critical "$COMPONENT" "Transaction verification failed"
            handle_exit 1 "$COMPONENT" "Transaction creation failed"
        fi
    else
        log_critical "$COMPONENT" "Insufficient unlocked balance (need > 0 XMR, have $UNLOCKED_XMR XMR)"
        log_warning "$COMPONENT" "Mining rewards may need more time to unlock (10 confirmations)"
        handle_exit 1 "$COMPONENT" "Insufficient balance"
    fi
else
    log_critical "$COMPONENT" "Failed to get valid balance from wallet1"
    log_warning "$COMPONENT" "This could indicate connection issues or insufficient sync time"
    handle_exit 1 "$COMPONENT" "Invalid wallet balance"
fi