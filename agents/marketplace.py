#!/usr/bin/env python3
"""
Marketplace Agent for Monerosim

Represents a marketplace that:
- Receives payments from users
- Tracks incoming transactions
- Maintains transaction history
"""

import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Set

from .base_agent import BaseAgent
from .monero_rpc import RPCError


class MarketplaceAgent(BaseAgent):
    """Agent representing a marketplace that receives payments"""
    
    def __init__(self, agent_id: str, wallet_rpc_port: int,
                 node_rpc_port: Optional[int] = None, rpc_host: str = "127.0.0.1"):
        # Marketplaces typically only need wallet RPC
        super().__init__(agent_id, node_rpc_port, wallet_rpc_port, rpc_host)
        
        # State
        self.wallet_address: Optional[str] = None
        self.wallet_initialized = False
        self.total_received = 0.0
        self.transaction_count = 0
        self.known_tx_hashes: Set[str] = set()
        self.last_balance_check = 0
        self.last_height = 0
        
    def _setup_agent(self):
        """Initialize marketplace wallet and register address"""
        if not self.wallet_rpc:
            raise RuntimeError("Marketplace requires wallet RPC connection")
            
        # Initialize or open wallet
        self._setup_wallet()
        
        # Get wallet address
        self.wallet_address = self.wallet_rpc.get_address()
        self.logger.info(f"Marketplace address: {self.wallet_address}")
        
        # Register marketplace address in shared state
        self._register_marketplace()
        
        # Initial wallet sync
        self.logger.info("Performing initial wallet sync...")
        self.wallet_rpc.refresh()
        
        # Get initial state
        self._update_transaction_history()
        
    def _setup_wallet(self):
        """Create or open marketplace wallet"""
        wallet_name = f"marketplace_{self.agent_id}"
        
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
                
    def _register_marketplace(self):
        """Register marketplace address in shared state"""
        marketplace_data = {
            "agent_id": self.agent_id,
            "address": self.wallet_address,
            "type": "marketplace",
            "timestamp": time.time()
        }
        
        # Add to list of marketplaces
        self.append_shared_list("marketplaces.json", marketplace_data)
        
        # Also write individual marketplace file
        self.write_shared_state(f"marketplace_{self.agent_id}.json", marketplace_data)
        
        self.logger.info("Registered marketplace in shared state")
        
    def _update_transaction_history(self):
        """Check for new incoming transactions"""
        try:
            # Get all incoming transfers
            transfers = self.wallet_rpc.incoming_transfers(transfer_type="all")
            incoming = transfers.get("transfers", [])
            
            new_transactions = 0
            new_amount = 0.0
            
            for transfer in incoming:
                tx_hash = transfer.get("tx_hash", "")
                if tx_hash and tx_hash not in self.known_tx_hashes:
                    # New transaction
                    amount = transfer.get("amount", 0) / 1e12  # Convert to XMR
                    height = transfer.get("height", 0)
                    unlocked = transfer.get("unlocked", False)
                    
                    self.known_tx_hashes.add(tx_hash)
                    new_transactions += 1
                    new_amount += amount
                    
                    self.logger.info(
                        f"Received payment: {amount:.4f} XMR "
                        f"(tx: {tx_hash[:8]}..., height: {height}, unlocked: {unlocked})"
                    )
                    
                    # Log to shared state
                    payment_data = {
                        "marketplace": self.agent_id,
                        "tx_hash": tx_hash,
                        "amount": amount,
                        "height": height,
                        "timestamp": time.time(),
                        "unlocked": unlocked
                    }
                    self.append_shared_list("marketplace_payments.json", payment_data)
                    
            if new_transactions > 0:
                self.total_received += new_amount
                self.transaction_count += new_transactions
                self.logger.info(
                    f"New payments summary: {new_transactions} transactions, "
                    f"{new_amount:.4f} XMR received"
                )
                
        except RPCError as e:
            self.logger.error(f"Failed to check incoming transfers: {e}")
            
    def _get_balance_info(self) -> Dict[str, float]:
        """Get current balance information"""
        try:
            balance_info = self.wallet_rpc.get_balance()
            return {
                "balance": balance_info.get("balance", 0) / 1e12,
                "unlocked_balance": balance_info.get("unlocked_balance", 0) / 1e12
            }
        except RPCError as e:
            self.logger.error(f"Failed to get balance: {e}")
            return {"balance": 0.0, "unlocked_balance": 0.0}
            
    def _update_statistics(self):
        """Update and log marketplace statistics"""
        balance_info = self._get_balance_info()
        
        stats = {
            "marketplace_id": self.agent_id,
            "total_received": self.total_received,
            "transaction_count": self.transaction_count,
            "current_balance": balance_info["balance"],
            "unlocked_balance": balance_info["unlocked_balance"],
            "wallet_height": self.last_height,
            "timestamp": time.time()
        }
        
        # Write current stats
        self.write_shared_state(f"marketplace_{self.agent_id}_stats.json", stats)
        
        # Log summary
        self.logger.info(
            f"Marketplace stats - Transactions: {self.transaction_count}, "
            f"Total received: {self.total_received:.4f} XMR, "
            f"Current balance: {balance_info['balance']:.4f} XMR"
        )
        
    def run_iteration(self):
        """Single iteration of marketplace behavior"""
        # Periodic wallet refresh
        current_time = time.time()
        if current_time - self.last_balance_check > 20:  # Check every 20 seconds
            try:
                # Refresh wallet
                self.wallet_rpc.refresh()
                
                # Get current height
                height = self.wallet_rpc.get_height()
                if height > self.last_height:
                    self.logger.debug(f"Wallet synced to height {height}")
                    self.last_height = height
                    
                # Check for new transactions
                self._update_transaction_history()
                
                # Update statistics
                self._update_statistics()
                
                self.last_balance_check = current_time
                
            except RPCError as e:
                self.logger.error(f"Failed to refresh wallet: {e}")
                
        # Sleep for a bit
        time.sleep(5)
        
    def _cleanup_agent(self):
        """Clean up marketplace resources"""
        # Final statistics update
        try:
            self._update_statistics()
        except:
            pass
            
        # Save wallet
        if self.wallet_rpc and self.wallet_initialized:
            try:
                self.wallet_rpc.store()
                self.logger.info("Wallet saved")
            except:
                pass
                
        # Write final summary
        summary = {
            "marketplace_id": self.agent_id,
            "total_transactions": self.transaction_count,
            "total_received": self.total_received,
            "known_tx_count": len(self.known_tx_hashes),
            "final_timestamp": time.time()
        }
        
        try:
            self.write_shared_state(f"marketplace_{self.agent_id}_final.json", summary)
            self.logger.info(
                f"Final summary - Received {self.transaction_count} transactions "
                f"totaling {self.total_received:.4f} XMR"
            )
        except:
            pass


def main():
    """Main entry point for marketplace agent"""
    parser = MarketplaceAgent.create_argument_parser("Marketplace Agent for Monerosim")
    
    args = parser.parse_args()
    
    # Set logging level
    import logging
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent
    agent = MarketplaceAgent(
        agent_id=args.id,
        wallet_rpc_port=args.wallet_rpc,
        node_rpc_port=args.node_rpc,
        rpc_host=args.rpc_host
    )
    
    agent.run()


if __name__ == "__main__":
    main()