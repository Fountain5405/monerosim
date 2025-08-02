#!/usr/bin/env python3
"""
Regular User Agent for Monerosim

Represents a typical Monero user who:
- Maintains a wallet
- Sends transactions to marketplaces
- Monitors transaction confirmations
"""

import random
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from .base_agent import BaseAgent
from .monero_rpc import RPCError


class RegularUserAgent(BaseAgent):
    """Agent representing a regular Monero user"""
    
    def __init__(self, agent_id: str, node_rpc_port: int, wallet_rpc_port: int,
                 transaction_frequency: float = 0.1, min_amount: float = 0.1,
                 max_amount: float = 1.0, rpc_host: str = "127.0.0.1",
                 hash_rate: Optional[int] = None,
                 **kwargs):
        super().__init__(
            agent_id=agent_id,
            node_rpc_port=node_rpc_port,
            wallet_rpc_port=wallet_rpc_port,
            rpc_host=rpc_host,
            hash_rate=hash_rate,
            **kwargs
        )
        
        # Behavior parameters
        self.transaction_frequency = transaction_frequency  # Probability of sending tx per iteration
        self.min_amount = min_amount  # Minimum transaction amount
        self.max_amount = max_amount  # Maximum transaction amount
        
        # State
        self.wallet_address: Optional[str] = None
        self.wallet_initialized = False
        self.last_balance_check = 0
        self.pending_transactions: List[Dict[str, Any]] = []
        
    def _setup_agent(self):
        """Initialize wallet and prepare for transactions"""
        if not self.wallet_rpc:
            raise RuntimeError("Regular user requires wallet RPC connection")
            
        # Initialize or open wallet
        self._setup_wallet()
        
        # Get wallet address
        self.wallet_address = self.wallet_rpc.get_address()
        self.logger.info(f"Wallet address: {self.wallet_address}")
        
        # Register our address in shared state
        self._register_user_address()
        
        # Initial wallet sync
        self.logger.info("Performing initial wallet sync...")
        self.wallet_rpc.refresh()
        
        if self.wait_for_wallet_sync(timeout=60):
            self.logger.info("Wallet sync complete")
        else:
            self.logger.warning("Initial wallet sync timeout")
            
    def _setup_wallet(self):
        """Create or open wallet"""
        wallet_name = f"user_{self.agent_id}"
        
        try:
            # Try to open existing wallet
            self.logger.info(f"Attempting to open wallet: {wallet_name}")
            self.wallet_rpc.open_wallet(wallet_name)
            self.wallet_initialized = True
            self.logger.info("Opened existing wallet")
        except RPCError:
            # Create new wallet
            self.logger.info(f"Creating new wallet: {wallet_name}")
            try:
                self.wallet_rpc.create_wallet(wallet_name)
                self.wallet_initialized = True
                self.logger.info("Created new wallet")
            except RPCError as e:
                self.logger.error(f"Failed to create wallet: {e}")
                raise
                
    def _register_user_address(self):
        """Register user address in shared state"""
        user_data = {
            "agent_id": self.agent_id,
            "address": self.wallet_address,
            "type": "regular_user",
            "timestamp": time.time()
        }
        
        # Add to list of all users
        self.append_shared_list("users.json", user_data)
        
        # Also write individual user file
        self.write_shared_state(f"user_{self.agent_id}.json", user_data)
        
    def _get_marketplace_addresses(self) -> List[Dict[str, Any]]:
        """Get list of marketplace addresses from shared state"""
        marketplaces = self.read_shared_list("marketplaces.json")
        return [m for m in marketplaces if m.get("type") == "marketplace"]
        
    def _should_send_transaction(self) -> bool:
        """Decide whether to send a transaction this iteration"""
        # Check if we have sufficient balance
        balance = self._get_spendable_balance()
        if balance < self.min_amount:
            return False
            
        # Random decision based on frequency
        return random.random() < self.transaction_frequency
        
    def _get_spendable_balance(self) -> float:
        """Get spendable balance in XMR"""
        try:
            balance_info = self.wallet_rpc.get_balance()
            # Convert from atomic units to XMR
            unlocked_balance = balance_info.get("unlocked_balance", 0)
            return unlocked_balance / 1e12
        except RPCError as e:
            self.logger.error(f"Failed to get balance: {e}")
            return 0.0
            
    def _send_transaction(self):
        """Send a transaction to a random marketplace"""
        marketplaces = self._get_marketplace_addresses()
        if not marketplaces:
            self.logger.debug("No marketplaces available")
            return
            
        # Select random marketplace
        marketplace = random.choice(marketplaces)
        recipient_address = marketplace["address"]
        
        # Generate random amount
        amount = random.uniform(self.min_amount, self.max_amount)
        
        # Check balance
        balance = self._get_spendable_balance()
        if balance < amount:
            amount = balance * 0.9  # Use 90% of available balance
            
        if amount < 0.0001:  # Minimum viable transaction
            self.logger.debug("Insufficient balance for transaction")
            return
            
        # Convert to atomic units
        amount_atomic = int(amount * 1e12)
        
        try:
            self.logger.info(f"Sending {amount:.4f} XMR to marketplace {marketplace['agent_id']}")
            
            # Create transaction
            destinations = [{
                "address": recipient_address,
                "amount": amount_atomic
            }]
            
            result = self.wallet_rpc.transfer(destinations, priority=0)
            
            tx_hash = result.get("tx_hash", "")
            fee = result.get("fee", 0) / 1e12
            
            self.logger.info(f"Transaction sent! Hash: {tx_hash}, Fee: {fee:.6f} XMR")
            
            # Track pending transaction
            tx_data = {
                "tx_hash": tx_hash,
                "amount": amount,
                "fee": fee,
                "recipient": marketplace["agent_id"],
                "timestamp": time.time(),
                "confirmed": False
            }
            self.pending_transactions.append(tx_data)
            
            # Log transaction to shared state
            self.append_shared_list("transactions.json", {
                "sender": self.agent_id,
                "recipient": marketplace["agent_id"],
                "amount": amount,
                "tx_hash": tx_hash,
                "timestamp": time.time()
            })
            
        except RPCError as e:
            self.logger.error(f"Failed to send transaction: {e}")
            
    def _check_pending_transactions(self):
        """Check status of pending transactions"""
        if not self.pending_transactions:
            return
            
        try:
            # Get all transfers
            transfers = self.wallet_rpc.get_transfers(out=True)
            out_transfers = transfers.get("out", [])
            
            # Build set of confirmed tx hashes
            confirmed_hashes = {tx["txid"] for tx in out_transfers if tx.get("confirmations", 0) > 0}
            
            # Update pending transactions
            for tx in self.pending_transactions:
                if not tx["confirmed"] and tx["tx_hash"] in confirmed_hashes:
                    tx["confirmed"] = True
                    self.logger.info(f"Transaction confirmed: {tx['tx_hash'][:8]}...")
                    
            # Remove old confirmed transactions (older than 5 minutes)
            current_time = time.time()
            self.pending_transactions = [
                tx for tx in self.pending_transactions
                if not tx["confirmed"] or (current_time - tx["timestamp"]) < 300
            ]
            
        except RPCError as e:
            self.logger.error(f"Failed to check transactions: {e}")
            
    def run_iteration(self) -> float:
        """
        Single iteration of user behavior.
        Returns:
            float: Recommended sleep time in seconds.
        """
        # Periodic wallet refresh
        if time.time() - self.last_balance_check > 30:
            try:
                self.wallet_rpc.refresh()
                balance = self._get_spendable_balance()
                self.logger.debug(f"Current balance: {balance:.4f} XMR")
                self.last_balance_check = time.time()
            except RPCError as e:
                self.logger.error(f"Failed to refresh wallet: {e}")

        # Check pending transactions
        self._check_pending_transactions()

        # Decide whether to send a transaction
        if self._should_send_transaction():
            self._send_transaction()

        # Return a random sleep duration
        return random.uniform(5, 15)
        
    def _cleanup_agent(self):
        """Clean up wallet resources"""
        if self.wallet_rpc and self.wallet_initialized:
            try:
                self.wallet_rpc.store()  # Save wallet
                self.logger.info("Wallet saved")
            except:
                pass


def main():
    """Main entry point for regular user agent"""
    parser = RegularUserAgent.create_argument_parser("Regular User Agent for Monerosim")
    parser.add_argument('--tx-frequency', type=float, default=0.1, help='Transaction frequency (0.0-1.0)')
    parser.add_argument('--min-amount', type=float, default=0.1, help='Minimum transaction amount in XMR')
    parser.add_argument('--max-amount', type=float, default=1.0, help='Maximum transaction amount in XMR')
    parser.add_argument('--hash-rate', type=int, help='Hash rate for mining (if this agent is a miner)')
    
    args = parser.parse_args()
    
    # Set logging level
    import logging
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent
    agent = RegularUserAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        node_rpc_port=args.node_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        transaction_frequency=args.tx_frequency,
        min_amount=args.min_amount,
        max_amount=args.max_amount,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes,
        hash_rate=args.hash_rate
    )
    
    agent.run()


if __name__ == "__main__":
    main()