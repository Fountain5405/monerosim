#!/usr/bin/env python3

import os
import sys
import time
from monero.wallet import Wallet
from monero.rpc import RPC
from monero.exceptions import MoneroException

# Wallet RPC details from environment variables (set by network_config.sh)
WALLET1_RPC_PORT = os.getenv("WALLET1_RPC_PORT", "28091")
WALLET1_IP = os.getenv("WALLET1_IP", "11.0.0.3")
WALLET1_NAME = os.getenv("WALLET1_NAME", "mining_wallet")
WALLET1_PASSWORD = os.getenv("WALLET1_PASSWORD", "test123")

WALLET2_RPC_PORT = os.getenv("WALLET2_RPC_PORT", "28092")
WALLET2_IP = os.getenv("WALLET2_IP", "11.0.0.4")
WALLET2_NAME = os.getenv("WALLET2_NAME", "recipient_wallet")
WALLET2_PASSWORD = os.getenv("WALLET2_PASSWORD", "test456")

def main():
    """
    Connects to two Monero wallets, gets the address from the second,
    and sends a small amount of Monero from the first to the second.
    """
    print("Initializing wallets...")
    
    try:
        # Initialize wallet1 (sender)
        wallet1_rpc = RPC(host=WALLET1_IP, port=int(WALLET1_RPC_PORT))
        wallet1 = Wallet(wallet1_rpc)
        print(f"Connected to wallet1 at {WALLET1_IP}:{WALLET1_RPC_PORT}")

        # Initialize wallet2 (recipient)
        wallet2_rpc = RPC(host=WALLET2_IP, port=int(WALLET2_RPC_PORT))
        wallet2 = Wallet(wallet2_rpc)
        print(f"Connected to wallet2 at {WALLET2_IP}:{WALLET2_RPC_PORT}")

        # Get recipient address from wallet2
        print("Getting recipient address from wallet2...")
        recipient_address = wallet2.address()
        print(f"Recipient address: {recipient_address}")

        # Send transaction from wallet1 to wallet2
        amount_to_send = 0.1  # Amount in XMR
        print(f"Attempting to send {amount_to_send} XMR from wallet1 to {recipient_address}...")

        # Ensure wallet1 has a balance
        balance = wallet1.balance()
        if balance < amount_to_send:
            print(f"Error: Wallet1 has insufficient balance ({balance} XMR). Cannot send {amount_to_send} XMR.")
            sys.exit(1)
        
        print(f"Wallet1 balance is sufficient: {balance} XMR")

        # Create and send the transaction
        tx = wallet1.transfer(recipient_address, amount_to_send)

        print("-" * 30)
        print("Transaction sent successfully!")
        print(f"  Transaction ID: {tx.hash}")
        print(f"  Transaction Key: {tx.key}")
        print(f"  Amount: {tx.amount} XMR")
        print(f"  Fee: {tx.fee} XMR")
        print("-" * 30)

    except MoneroException as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"A general error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()