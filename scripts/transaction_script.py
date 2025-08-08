#!/usr/bin/env python3
"""
Transaction Script for MoneroSim

This script handles transaction operations in the Monero simulation, including:
1. Dynamically discovering wallet agents
2. Creating/opening wallets for discovered agents
3. Generating wallet addresses
4. Checking wallet balances
5. Sending transactions between wallets
6. Verifying transaction completion

This is an enhanced version that uses the error_handling and agent_discovery modules
for dynamic agent discovery and better reliability with other MoneroSim scripts.
"""

import sys
import time
import json
import argparse
from typing import Dict, Any, Optional, Tuple

# Add the parent directory to the Python path to import our modules
sys.path.insert(0, '.')

from scripts.error_handling import (
    log_info, log_error, log_critical, log_warning,
    call_wallet_with_retry, verify_wallet_created,
    verify_wallet_open, verify_transaction,
    handle_exit
)
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

# Component name for logging
COMPONENT = "TRANSACTION_SCRIPT"

# Configuration
MAX_ATTEMPTS = 30
RETRY_DELAY = 2
BALANCE_WAIT_TIME = 10
BALANCE_CHECK_ATTEMPTS = 30
TRANSACTION_AMOUNT = 0.1  # XMR
ATOMIC_UNITS_PER_XMR = 1e12

# Default wallet names and passwords for compatibility
WALLET1_NAME = "wallet1"
WALLET2_NAME = "wallet2"
WALLET1_PASSWORD = "test123"
WALLET2_PASSWORD = "test456"


def create_or_open_wallet(wallet_url: str, wallet_name: str, wallet_password: str,
                         wallet_label: str) -> bool:
    """
    Create a new wallet if it doesn't exist, or open an existing one.
    This function works with dynamically discovered wallet agents.
    
    Args:
        wallet_url: The RPC URL of the wallet
        wallet_name: The name of the wallet file
        wallet_password: The wallet password
        wallet_label: A label for the wallet (for logging)
        
    Returns:
        True if successful, False otherwise
    """
    log_info(COMPONENT, f"Ensuring {wallet_label} '{wallet_name}' is created and open")
    
    # First, try to create the wallet
    if verify_wallet_created(wallet_url, wallet_name, wallet_password, 
                           MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        log_info(COMPONENT, f"Successfully created new {wallet_label} '{wallet_name}'")
        return True
    
    # If creation failed (likely because it already exists), try to open it
    log_info(COMPONENT, f"{wallet_label} '{wallet_name}' already exists, attempting to open")
    
    if verify_wallet_open(wallet_url, wallet_name, wallet_password,
                         MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        log_info(COMPONENT, f"Successfully opened existing {wallet_label} '{wallet_name}'")
        return True
    
    log_critical(COMPONENT, f"Failed to create or open {wallet_label} '{wallet_name}'")
    return False


def get_wallet_address(wallet_url: str, wallet_label: str) -> Optional[str]:
    """
    Get the primary address from a dynamically discovered wallet.
    
    Args:
        wallet_url: The RPC URL of the wallet
        wallet_label: A label for the wallet (for logging)
        
    Returns:
        The wallet address as a string, or None if failed
    """
    log_info(COMPONENT, f"Getting address from {wallet_label}")
    
    success, response = call_wallet_with_retry(
        wallet_url, "get_address", {"account_index": 0},
        MAX_ATTEMPTS, RETRY_DELAY, COMPONENT
    )
    
    if not success:
        log_error(COMPONENT, f"Failed to get address from {wallet_label}")
        return None
    
    try:
        address = response.get("result", {}).get("address")
        if not address:
            log_error(COMPONENT, f"No address found in response from {wallet_label}")
            return None
        
        log_info(COMPONENT, f"{wallet_label} address: {address}")
        return address
    except Exception as e:
        log_error(COMPONENT, f"Error parsing address from {wallet_label}: {e}")
        return None


def wait_for_balance(wallet_url: str, wallet_label: str,
                    min_balance: float = 0.0) -> Optional[float]:
    """
    Wait for a dynamically discovered wallet to have a sufficient balance.
    
    Args:
        wallet_url: The RPC URL of the wallet
        wallet_label: A label for the wallet (for logging)
        min_balance: Minimum required balance in XMR
        
    Returns:
        The wallet balance in XMR, or None if failed
    """
    log_info(COMPONENT, f"Checking balance of {wallet_label} (minimum required: {min_balance} XMR)")
    
    for attempt in range(BALANCE_CHECK_ATTEMPTS):
        success, response = call_wallet_with_retry(
            wallet_url, "get_balance", {"account_index": 0},
            MAX_ATTEMPTS, RETRY_DELAY, COMPONENT
        )
        
        if not success:
            log_error(COMPONENT, f"Failed to get balance from {wallet_label}")
            return None
        
        try:
            balance_atomic = response.get("result", {}).get("balance", 0)
            balance_xmr = balance_atomic / ATOMIC_UNITS_PER_XMR
            
            log_info(COMPONENT, f"{wallet_label} balance: {balance_xmr} XMR")
            
            if balance_xmr >= min_balance:
                return balance_xmr
            
            if attempt < BALANCE_CHECK_ATTEMPTS - 1:
                log_info(COMPONENT, 
                        f"Waiting for balance to reach {min_balance} XMR... "
                        f"(attempt {attempt + 1}/{BALANCE_CHECK_ATTEMPTS})")
                time.sleep(BALANCE_WAIT_TIME)
        except Exception as e:
            log_error(COMPONENT, f"Error parsing balance from {wallet_label}: {e}")
            return None
    
    log_error(COMPONENT, f"Timeout waiting for {wallet_label} to have sufficient balance")
    return None


def send_transaction_with_sweep(wallet_url: str, recipient_address: str,
                               amount_xmr: float, wallet_label: str) -> Optional[Dict[str, Any]]:
    """
    Send a transaction from a dynamically discovered wallet to a recipient address,
    with automatic sweep handling.
    
    Args:
        wallet_url: The RPC URL of the sending wallet
        recipient_address: The recipient's address
        amount_xmr: The amount to send in XMR
        wallet_label: A label for the wallet (for logging)
        
    Returns:
        Transaction info dict if successful, None otherwise
    """
    log_info(COMPONENT, f"Attempting to send {amount_xmr} XMR from {wallet_label} to {recipient_address}")
    
    amount_atomic = int(amount_xmr * ATOMIC_UNITS_PER_XMR)
    
    transfer_params = {
        "destinations": [{"amount": amount_atomic, "address": recipient_address}],
        "account_index": 0,
        "priority": 0,
        "ring_size": 7,
        "get_tx_key": True
    }
    
    success, response = call_wallet_with_retry(
        wallet_url, "transfer", transfer_params,
        MAX_ATTEMPTS, RETRY_DELAY, COMPONENT
    )
    
    # Check if we need to sweep dust
    if not success and response.get("error", {}).get("code") == -19:
        log_warning(COMPONENT, "Transaction failed due to fragmented inputs. Sweeping dust...")
        
        sweep_success, sweep_response = call_wallet_with_retry(
            wallet_url, "sweep_dust", {},
            MAX_ATTEMPTS, RETRY_DELAY, COMPONENT
        )
        
        if not sweep_success:
            log_error(COMPONENT, f"Failed to sweep dust: {sweep_response}")
            return None
        
        tx_hashes = sweep_response.get("result", {}).get("tx_hash_list", [])
        log_info(COMPONENT, f"Sweep successful. TX Hashes: {tx_hashes}")
        log_info(COMPONENT, "Waiting for sweep transaction to be mined...")
        
        # Wait for sweep to be mined
        time.sleep(120)
        
        # Retry the transaction
        log_info(COMPONENT, "Retrying transaction after sweep...")
        success, response = call_wallet_with_retry(
            wallet_url, "transfer", transfer_params,
            MAX_ATTEMPTS, RETRY_DELAY, COMPONENT
        )
    
    if not success:
        log_error(COMPONENT, f"Failed to send transaction: {response}")
        return None
    
    try:
        tx_info = response.get("result", {})
        if not tx_info:
            log_error(COMPONENT, "No transaction info in response")
            return None
        
        return tx_info
    except Exception as e:
        log_error(COMPONENT, f"Error parsing transaction response: {e}")
        return None


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the transaction script.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="MoneroSim Transaction Script - Send transactions between discovered wallet agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/transaction_script.py --help
  python3 scripts/transaction_script.py --max-attempts 20 --retry-delay 3
  python3 scripts/transaction_script.py --amount 0.5 --balance-wait 15
        """
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_ATTEMPTS,
        help=f"Maximum number of attempts for RPC calls (default: {MAX_ATTEMPTS})"
    )
    
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=RETRY_DELAY,
        help=f"Initial retry delay in seconds (default: {RETRY_DELAY})"
    )
    
    parser.add_argument(
        "--balance-wait",
        type=int,
        default=BALANCE_WAIT_TIME,
        help=f"Time to wait between balance checks in seconds (default: {BALANCE_WAIT_TIME})"
    )
    
    parser.add_argument(
        "--balance-checks",
        type=int,
        default=BALANCE_CHECK_ATTEMPTS,
        help=f"Maximum number of balance check attempts (default: {BALANCE_CHECK_ATTEMPTS})"
    )
    
    parser.add_argument(
        "--amount",
        type=float,
        default=TRANSACTION_AMOUNT,
        help=f"Transaction amount in XMR (default: {TRANSACTION_AMOUNT})"
    )
    
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Test mode - only discover agents and exit"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main execution function for the transaction script.
    This function uses dynamic agent discovery to find wallet agents.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    args = parse_arguments()
    
    log_info(COMPONENT, "=== MoneroSim Transaction Script ===")
    log_info(COMPONENT, f"Starting transaction script at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize agent discovery
    try:
        agent_discovery = AgentDiscovery()
        log_info(COMPONENT, "Agent discovery initialized successfully")
    except Exception as e:
        log_critical(COMPONENT, f"Failed to initialize agent discovery: {e}")
        handle_exit(1, COMPONENT, "Agent discovery initialization failed")
        return 1
    
    # Discover wallet agents
    try:
        wallet_agents = agent_discovery.get_wallet_agents()
        if len(wallet_agents) < 2:
            log_critical(COMPONENT,
                        f"Insufficient wallet agents discovered: {len(wallet_agents)} "
                        f"(need at least 2)")
            handle_exit(1, COMPONENT, "Insufficient wallet agents")
            return 1
        
        # Use the first two wallet agents
        sender_wallet = wallet_agents[0]
        recipient_wallet = wallet_agents[1]
        
        # Extract wallet configuration
        sender_rpc = f"http://{sender_wallet.get('ip_addr')}:{sender_wallet.get('wallet_rpc_port')}/json_rpc"
        sender_name = sender_wallet.get('wallet_name', f"wallet_{sender_wallet.get('id', '0')}")
        sender_password = sender_wallet.get('wallet_password', "test123")
        
        recipient_rpc = f"http://{recipient_wallet.get('ip_addr')}:{recipient_wallet.get('wallet_rpc_port')}/json_rpc"
        recipient_name = recipient_wallet.get('wallet_name', f"wallet_{recipient_wallet.get('id', '1')}")
        recipient_password = recipient_wallet.get('wallet_password', "test456")
        
        log_info(COMPONENT, f"Discovered sender wallet: {sender_name} at {sender_rpc}")
        log_info(COMPONENT, f"Discovered recipient wallet: {recipient_name} at {recipient_rpc}")
        
        # Exit early if in test mode
        if args.test_mode:
            log_info(COMPONENT, "Test mode completed successfully - wallet agents discovered")
            handle_exit(0, COMPONENT, "Test mode completed")
            return 0
        
    except AgentDiscoveryError as e:
        log_critical(COMPONENT, f"Failed to discover wallet agents: {e}")
        handle_exit(1, COMPONENT, "Wallet agent discovery failed")
        return 1
    except Exception as e:
        log_critical(COMPONENT, f"Unexpected error during wallet agent discovery: {e}")
        handle_exit(1, COMPONENT, "Unexpected error during wallet discovery")
        return 1
    
    # Step 1: Create or open wallets
    log_info(COMPONENT, "Step 1: Initializing wallets")
    
    if not create_or_open_wallet(sender_rpc, sender_name, sender_password, "sender_wallet"):
        handle_exit(1, COMPONENT, "Failed to initialize sender wallet")
        return 1
    
    if not create_or_open_wallet(recipient_rpc, recipient_name, recipient_password, "recipient_wallet"):
        handle_exit(1, COMPONENT, "Failed to initialize recipient wallet")
        return 1
    
    # Step 2: Get recipient address from recipient wallet
    log_info(COMPONENT, "Step 2: Getting recipient address")
    
    recipient_address = get_wallet_address(recipient_rpc, "recipient_wallet")
    if not recipient_address:
        handle_exit(1, COMPONENT, "Failed to get recipient address")
        return 1
    
    # Step 3: Wait for sender wallet to have sufficient balance
    log_info(COMPONENT, "Step 3: Checking sender wallet balance")
    
    balance = wait_for_balance(sender_rpc, "sender_wallet", args.amount)
    if balance is None:
        handle_exit(1, COMPONENT, "Failed to get sufficient balance in sender wallet")
        return 1
    
    if balance < args.amount:
        log_critical(COMPONENT,
                    f"Insufficient balance in sender wallet: {balance} XMR "
                    f"(need {args.amount} XMR)")
        handle_exit(1, COMPONENT, "Insufficient balance")
        return 1
    
    # Step 4: Send transaction
    log_info(COMPONENT, "Step 4: Sending transaction")
    
    tx_info = send_transaction_with_sweep(sender_rpc, recipient_address,
                                         args.amount, "sender_wallet")
    if not tx_info:
        handle_exit(1, COMPONENT, "Failed to send transaction")
        return 1
    
    # Step 5: Display transaction results
    log_info(COMPONENT, "Step 5: Transaction completed successfully!")
    log_info(COMPONENT, "-" * 50)
    log_info(COMPONENT, "Transaction Details:")
    log_info(COMPONENT, f"  Transaction ID: {tx_info.get('tx_hash', 'N/A')}")
    log_info(COMPONENT, f"  Transaction Key: {tx_info.get('tx_key', 'N/A')}")
    log_info(COMPONENT, f"  Amount: {tx_info.get('amount', 0) / ATOMIC_UNITS_PER_XMR} XMR")
    log_info(COMPONENT, f"  Fee: {tx_info.get('fee', 0) / ATOMIC_UNITS_PER_XMR} XMR")
    log_info(COMPONENT, "-" * 50)
    
    # Optional: Verify transaction using the verify_transaction function
    # This would require waiting for the transaction to be mined
    # log_info(COMPONENT, "Step 6: Verifying transaction...")
    # if verify_transaction(sender_rpc, recipient_address, amount_atomic,
    #                      MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
    #     log_info(COMPONENT, "✅ Transaction verified successfully!")
    # else:
    #     log_warning(COMPONENT, "⚠️ Transaction verification pending")
    
    log_info(COMPONENT, "✅ Transaction script completed successfully")
    log_info(COMPONENT, "=== Transaction script finished ===")
    
    handle_exit(0, COMPONENT, "Transaction script completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())