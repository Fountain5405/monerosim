#!/usr/bin/env python3

import os
import sys
import time
import requests
import json

# Wallet RPC details from environment variables (set by network_config.sh)
WALLET1_RPC_PORT = os.getenv("WALLET1_RPC_PORT", "28091")
WALLET1_IP = os.getenv("WALLET1_IP", "11.0.0.3")
WALLET1_NAME = os.getenv("WALLET1_NAME", "mining_wallet")
WALLET1_PASSWORD = os.getenv("WALLET1_PASSWORD", "test123")

WALLET2_RPC_PORT = os.getenv("WALLET2_RPC_PORT", "28092")
WALLET2_IP = os.getenv("WALLET2_IP", "11.0.0.4")
WALLET2_NAME = os.getenv("WALLET2_NAME", "recipient_wallet")
WALLET2_PASSWORD = os.getenv("WALLET2_PASSWORD", "test456")

def json_rpc_request(method, params, host, port):
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
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        json_response = response.json()
        if 'error' in json_response:
            # Propagate error as a return value to be handled by the caller
            return json_response
        return json_response
    except requests.exceptions.RequestException as e:
        print(f"Error making RPC request to {url}: {e}")
        return {"error": {"code": -999, "message": str(e)}}

def create_or_open_wallet(wallet_name, password, host, port):
    """Create a new wallet if it doesn't exist, and ensure it is open."""
    print(f"Ensuring wallet '{wallet_name}' is created and open at {host}:{port}")

    # Try to create the wallet.
    create_params = {"filename": wallet_name, "password": password, "language": "English"}
    create_response = json_rpc_request("create_wallet", create_params, host, port)

    # Check if it returned an error because it already exists (-21).
    if 'error' in create_response and create_response.get('error', {}).get('code') == -21:
        print(f"Wallet '{wallet_name}' already exists. Opening it...")
        open_params = {"filename": wallet_name, "password": password}
        open_response = json_rpc_request("open_wallet", open_params, host, port)
        if 'error' in open_response:
            print(f"CRITICAL: Failed to open existing wallet '{wallet_name}'. Error: {open_response['error']}")
            sys.exit(1)
        print(f"Successfully opened wallet '{wallet_name}'.")
    elif 'error' in create_response:
        print(f"CRITICAL: Failed to create wallet '{wallet_name}'. Error: {create_response['error']}")
        sys.exit(1)
    else:
        print(f"Successfully created new wallet '{wallet_name}'. It is now open.")

def main():
    """
    Connects to two Monero wallets via JSON-RPC, gets the address from the second,
    and sends a small amount of Monero from the first to the second.
    """
    print("Initializing wallets...")
    
    try:
        # Create or open both wallets
        create_or_open_wallet(WALLET1_NAME, WALLET1_PASSWORD, WALLET1_IP, WALLET1_RPC_PORT)
        create_or_open_wallet(WALLET2_NAME, WALLET2_PASSWORD, WALLET2_IP, WALLET2_RPC_PORT)

        # Get recipient address from wallet2
        print("Getting recipient address from wallet2...")
        addr_params = {"account_index": 0}
        addr_response = json_rpc_request("get_address", addr_params, WALLET2_IP, WALLET2_RPC_PORT)
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
             balance_response = json_rpc_request("get_balance", balance_params, WALLET1_IP, WALLET1_RPC_PORT)
             if 'result' in balance_response and balance_response['result'].get('balance', 0) > 0:
                 break
             print(f"Waiting for balance to appear... (attempt {i+1}/30)")
             time.sleep(10)

        if 'result' not in balance_response or 'balance' not in balance_response['result']:
            print(f"Error: Could not get balance from wallet1. Response: {balance_response}")
            sys.exit(1)
        
        balance = balance_response['result']['balance'] / 1e12  # Convert atomic units to XMR
        amount_to_send = 0.1

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

        transfer_response = json_rpc_request("transfer", transfer_params, WALLET1_IP, WALLET1_RPC_PORT)

        if 'error' in transfer_response and transfer_response.get('error', {}).get('code') == -19:
            print("Transaction failed due to fragmented inputs. Sweeping dust...")
            sweep_response = json_rpc_request("sweep_dust", {}, WALLET1_IP, WALLET1_RPC_PORT)
            if 'error' in sweep_response:
                print(f"Failed to sweep dust. Error: {sweep_response['error']}")
                sys.exit(1)

            print(f"Sweep successful. Waiting for sweep transaction to be mined... TX Hashes: {sweep_response.get('result', {}).get('tx_hash_list')}")
            # Wait for the sweep transaction to be mined and unlocked
            time.sleep(120)
            
            print("Retrying transaction after sweep...")
            transfer_response = json_rpc_request("transfer", transfer_params, WALLET1_IP, WALLET1_RPC_PORT)

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