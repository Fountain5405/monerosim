#!/usr/bin/env python3
"""
Monero Transaction Script

This script demonstrates how to send Monero transactions between wallets in the
MoneroSim Shadow network simulation. It uses the agent_discovery module to
dynamically discover wallet agents instead of using hardcoded configuration values.

The script:
1. Discovers wallet agents using the agent_discovery module
2. Creates or opens two wallets
3. Gets the recipient address from the second wallet
4. Checks the balance of the first wallet
5. Sends a transaction from the first wallet to the second
6. Handles fragmented inputs by sweeping dust if necessary

This replaces the previous approach that used hardcoded IP addresses and ports
from environment variables.
"""

import os
import sys
import time
import requests
import json
import argparse

# Import agent discovery
try:
    from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError
except ImportError:
    # Fallback for direct execution
    sys.path.insert(0, '.')
    from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

# Default wallet configuration (will be overridden by agent discovery)
WALLET1_NAME = "mining_wallet"
WALLET1_PASSWORD = "test123"

WALLET2_NAME = "recipient_wallet"
WALLET2_PASSWORD = "test456"

def json_rpc_request(method, params, host, port, timeout=30):
    """Helper function to make a JSON-RPC request"""
    url = f"http://{host}:{port}/json_rpc"
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": method,
        "params": params
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        response.raise_for_status()
        json_response = response.json()
        if 'error' in json_response:
            # Propagate error as a return value to be handled by the caller
            return json_response
        return json_response
    except requests.exceptions.RequestException as e:
        print(f"Error making RPC request to {url}: {e}")
        return {"error": {"code": -999, "message": str(e)}}

def create_or_open_wallet(wallet_name, password, host, port, timeout=30):
    """Create a new wallet if it doesn't exist, and ensure it is open."""
    print(f"Ensuring wallet '{wallet_name}' is created and open at {host}:{port}")

    # Try to create the wallet.
    create_params = {"filename": wallet_name, "password": password, "language": "English"}
    create_response = json_rpc_request("create_wallet", create_params, host, port, timeout)

    # Check if it returned an error because it already exists (-21).
    if 'error' in create_response and create_response.get('error', {}).get('code') == -21:
        print(f"Wallet '{wallet_name}' already exists. Opening it...")
        open_params = {"filename": wallet_name, "password": password}
        open_response = json_rpc_request("open_wallet", open_params, host, port, timeout)
        if 'error' in open_response:
            print(f"CRITICAL: Failed to open existing wallet '{wallet_name}'. Error: {open_response['error']}")
            sys.exit(1)
        print(f"Successfully opened wallet '{wallet_name}'.")
    elif 'error' in create_response:
        print(f"CRITICAL: Failed to create wallet '{wallet_name}'. Error: {create_response['error']}")
        sys.exit(1)
    else:
        print(f"Successfully created new wallet '{wallet_name}'. It is now open.")

def initialize_wallet_agents():
    """Initialize wallet agents using agent discovery."""
    global WALLET1_IP, WALLET1_RPC_PORT, WALLET1_NAME, WALLET1_PASSWORD
    global WALLET2_IP, WALLET2_RPC_PORT, WALLET2_NAME, WALLET2_PASSWORD
    
    try:
        agent_discovery = AgentDiscovery()
        
        # Get wallet agents
        wallet_agents = agent_discovery.get_wallet_agents()
        
        if len(wallet_agents) < 2:
            print(f"Error: Insufficient wallet agents found: {len(wallet_agents)}")
            return False
            
        # Sort by ID to ensure consistent ordering
        wallet_agents.sort(key=lambda x: x.get("id", ""))
        
        # Extract wallet configuration from agents
        wallet1 = wallet_agents[0]
        wallet2 = wallet_agents[1]
        
        # Initialize with values from agent discovery
        WALLET1_IP = wallet1.get("ip_addr", "")
        WALLET1_RPC_PORT = wallet1.get("wallet_rpc_port", "")
        WALLET1_NAME = wallet1.get("wallet_name", WALLET1_NAME)
        WALLET1_PASSWORD = wallet1.get("wallet_password", WALLET1_PASSWORD)
        
        WALLET2_IP = wallet2.get("ip_addr", "")
        WALLET2_RPC_PORT = wallet2.get("wallet_rpc_port", "")
        WALLET2_NAME = wallet2.get("wallet_name", WALLET2_NAME)
        WALLET2_PASSWORD = wallet2.get("wallet_password", WALLET2_PASSWORD)
        
        # Validate required fields
        if not WALLET1_IP or not WALLET1_RPC_PORT:
            print(f"Error: Missing required IP or port for wallet1")
            return False
            
        if not WALLET2_IP or not WALLET2_RPC_PORT:
            print(f"Error: Missing required IP or port for wallet2")
            return False
        
        print(f"Discovered wallet agents:")
        print(f"  Wallet1: {WALLET1_IP}:{WALLET1_RPC_PORT} ({WALLET1_NAME})")
        print(f"  Wallet2: {WALLET2_IP}:{WALLET2_RPC_PORT} ({WALLET2_NAME})")
        
        return True
        
    except AgentDiscoveryError as e:
        print(f"Error: Agent discovery failed: {e}")
        return False
    except Exception as e:
        print(f"Error: Unexpected error during agent discovery: {e}")
        return False


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the send transaction script.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="MoneroSim Send Transaction - Send transactions between discovered wallet agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/send_transaction.py --help
  python3 scripts/send_transaction.py --amount 0.5 --timeout 60
  python3 scripts/send_transaction.py --wallet1-name sender --wallet2-name recipient
        """
    )
    
    parser.add_argument(
        "--amount",
        type=float,
        default=0.1,
        help="Amount of XMR to send (default: 0.1)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="RPC request timeout in seconds (default: 30)"
    )
    
    parser.add_argument(
        "--wallet1-name",
        type=str,
        default="mining_wallet",
        help="Name for the first wallet (default: mining_wallet)"
    )
    
    parser.add_argument(
        "--wallet1-password",
        type=str,
        default="test123",
        help="Password for the first wallet (default: test123)"
    )
    
    parser.add_argument(
        "--wallet2-name",
        type=str,
        default="recipient_wallet",
        help="Name for the second wallet (default: recipient_wallet)"
    )
    
    parser.add_argument(
        "--wallet2-password",
        type=str,
        default="test456",
        help="Password for the second wallet (default: test456)"
    )
    
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Test mode - only discover agents and exit"
    )
    
    return parser.parse_args()


def main():
    """
    Connects to two Monero wallets via JSON-RPC, gets the address from the second,
    and sends a small amount of Monero from the first to the second.
    """
    args = parse_arguments()
    
    # Update global variables with command-line arguments
    global WALLET1_NAME, WALLET1_PASSWORD, WALLET2_NAME, WALLET2_PASSWORD
    
    WALLET1_NAME = args.wallet1_name
    WALLET1_PASSWORD = args.wallet1_password
    WALLET2_NAME = args.wallet2_name
    WALLET2_PASSWORD = args.wallet2_password
    
    print("Initializing wallets...")
    
    # Initialize wallet agents using agent discovery
    if not initialize_wallet_agents():
        sys.exit(1)
    
    # Exit early if in test mode
    if args.test_mode:
        print("Test mode completed successfully - wallet agents discovered")
        return
    
    try:
        # Create or open both wallets
        create_or_open_wallet(WALLET1_NAME, WALLET1_PASSWORD, WALLET1_IP, WALLET1_RPC_PORT, args.timeout)
        create_or_open_wallet(WALLET2_NAME, WALLET2_PASSWORD, WALLET2_IP, WALLET2_RPC_PORT, args.timeout)

        # Get recipient address from wallet2
        print("Getting recipient address from wallet2...")
        addr_params = {"account_index": 0}
        addr_response = json_rpc_request("get_address", addr_params, WALLET2_IP, WALLET2_RPC_PORT, args.timeout)
        if 'result' not in addr_response or 'address' not in addr_response['result']:
            print(f"Error: Could not get address from wallet2. Response: {addr_response}")
            sys.exit(1)
        recipient_address = addr_response['result']['address']
        print(f"Recipient address: {recipient_address}")

        # Check balance of wallet1
        print("Checking balance of wallet1...")
        # Adding a loop to wait for the wallet to sync and balance to appear
        for i in range(30): # Wait up to 300 seconds
             balance_params = {"account_index": 0}
             balance_response = json_rpc_request("get_balance", balance_params, WALLET1_IP, WALLET1_RPC_PORT, args.timeout)
             if 'result' in balance_response and balance_response['result'].get('balance', 0) > 0:
                 break
             print(f"Waiting for balance to appear... (attempt {i+1}/30)")
             time.sleep(10)

        if 'result' not in balance_response or 'balance' not in balance_response['result']:
            print(f"Error: Could not get balance from wallet1. Response: {balance_response}")
            sys.exit(1)
        
        balance = balance_response['result']['balance'] / 1e12  # Convert atomic units to XMR
        amount_to_send = args.amount

        if balance < amount_to_send:
            print(f"Error: Wallet1 has insufficient balance ({balance} XMR). Cannot send {amount_to_send} XMR.")
            sys.exit(1)
        
        print(f"Wallet1 balance is sufficient: {balance} XMR")

        # Send transaction from wallet1 to wallet2
        print(f"Attempting to send {amount_to_send} XMR from wallet1 to {recipient_address}...")
        
        destinations = [{"amount": int(amount_to_send * 1e12), "address": recipient_address}]
        transfer_params = {
            "destinations": destinations,
            "account_index": 0,
            "priority": 0,
            "ring_size": 7,
            "get_tx_key": True
        }

        transfer_response = json_rpc_request("transfer", transfer_params, WALLET1_IP, WALLET1_RPC_PORT, args.timeout)

        if 'error' in transfer_response and transfer_response.get('error', {}).get('code') == -19:
            print("Transaction failed due to fragmented inputs. Sweeping dust...")
            sweep_response = json_rpc_request("sweep_dust", {}, WALLET1_IP, WALLET1_RPC_PORT, args.timeout)
            if 'error' in sweep_response:
                print(f"Failed to sweep dust. Error: {sweep_response['error']}")
                sys.exit(1)

            print(f"Sweep successful. Waiting for sweep transaction to be mined... TX Hashes: {sweep_response.get('result', {}).get('tx_hash_list')}")
            # Wait for the sweep transaction to be mined and unlocked
            time.sleep(120)
            
            print("Retrying transaction after sweep...")
            transfer_response = json_rpc_request("transfer", transfer_params, WALLET1_IP, WALLET1_RPC_PORT, args.timeout)

        if 'result' not in transfer_response:
            print(f"Error sending transaction after potential sweep. Response: {transfer_response}")
            sys.exit(1)

        tx_info = transfer_response['result']
        
        print("-" * 30)
        print("Transaction sent successfully!")
        print(f"  Transaction ID: {tx_info.get('tx_hash')}")
        print(f"  Transaction Key: {tx_info.get('tx_key')}")
        print(f"  Amount: {tx_info.get('amount', 0) / 1e12} XMR")
        print(f"  Fee: {tx_info.get('fee', 0) / 1e12} XMR")
        print("-" * 30)

    except Exception as e:
        print(f"A general error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()