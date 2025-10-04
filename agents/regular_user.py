#!/usr/bin/env python3
"""
Regular User Agent for Monerosim

This agent simulates regular users in the Monero network who perform transactions.
Currently a placeholder implementation that will be extended in future tasks.
"""

import logging
import time
import random
from typing import Optional, List, Dict, Any
from pathlib import Path

from .base_agent import BaseAgent


class RegularUserAgent(BaseAgent):
    """Agent that simulates regular user behavior in the Monero network"""
    
    def __init__(self, agent_id: str, tx_frequency: Optional[int] = None, hash_rate: Optional[int] = None, **kwargs):
        """
        Initialize the RegularUserAgent.
        
        Args:
            agent_id: Unique identifier for this agent
            tx_frequency: Transaction frequency in seconds
            hash_rate: Hash rate for mining (if applicable)
            **kwargs: Additional arguments passed to BaseAgent
        """
        # Call parent constructor
        super().__init__(agent_id=agent_id, tx_frequency=tx_frequency, hash_rate=hash_rate, **kwargs)
        
    def _setup_agent(self):
        """Agent-specific setup logic"""
        if self.is_miner:
            self.logger.info("RegularUserAgent initialized as MINER")
            # Miner-specific setup logic
            self._setup_miner()
        else:
            self.logger.info("RegularUserAgent initialized as REGULAR USER")
            # Regular user setup logic
            self._setup_regular_user()
    
    def _setup_miner(self):
        """Setup logic for miner agents"""
        self.logger.info("Setting up miner functionality")
        # Ensure wallet is available for mining rewards
        if not self.wallet_rpc:
            self.logger.warning("No wallet RPC connection available for miner")
            return
            
        try:
            # Extract agent ID to create wallet name
            wallet_name = f"{self.agent_id}_wallet"
            self.wallet_address = None
            
            # First try to open existing wallet
            try:
                self.logger.info(f"Attempting to open wallet '{wallet_name}' for miner {self.agent_id}")
                self.wallet_rpc.wait_until_ready(max_wait=180)
                self.wallet_rpc.open_wallet(wallet_name, password="")
                # If open succeeds, get the address
                self.wallet_address = self.wallet_rpc.get_address()
                self.logger.info(f"Successfully opened existing wallet '{wallet_name}'")
            except Exception as open_err:
                # If wallet doesn't exist or can't be opened, try to create it
                if "Wallet not found" in str(open_err) or "Failed to open wallet" in str(open_err):
                    try:
                        self.logger.info(f"Wallet doesn't exist, creating '{wallet_name}'")
                        self.wallet_rpc.create_wallet(wallet_name, password="")
                        # If creation succeeds, get the address
                        self.wallet_address = self.wallet_rpc.get_address()
                        self.logger.info(f"Successfully created new wallet '{wallet_name}'")
                    except Exception as create_err:
                        self.logger.error(f"Failed to create wallet: {create_err}")
                        # Last attempt - maybe wallet is already loaded
                        try:
                            self.logger.warning("Attempting to get address from current wallet")
                            self.wallet_rpc.wait_until_ready(max_wait=180)
                            self.wallet_address = self.wallet_rpc.get_address()
                        except Exception as addr_err:
                            self.logger.error(f"Failed to get address: {addr_err}")
                            return
                else:
                    # Some other error opening wallet, try to get address anyway
                    self.logger.warning(f"Error opening wallet: {open_err}, trying to get address from current wallet")
                    try:
                        self.wallet_rpc.wait_until_ready(max_wait=180)
                        self.wallet_address = self.wallet_rpc.get_address()
                    except Exception as addr_err:
                        self.logger.error(f"Failed to get address: {addr_err}")
                        return
            
            if self.wallet_address:
                self.logger.info(f"Miner wallet address: {self.wallet_address}")
                # Register miner information for the block controller with improved error handling
                self._register_miner_info()
            else:
                self.logger.error(f"Failed to obtain wallet address for miner {self.agent_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup miner: {e}")
    
    def _setup_regular_user(self):
        """Setup logic for regular user agents"""
        self.logger.info("Setting up regular user functionality")
        # Ensure wallet is available for transactions
        if not self.wallet_rpc:
            self.logger.warning("No wallet RPC connection available for regular user")
            return
            
        try:
            # Extract agent ID to create wallet name
            wallet_name = f"{self.agent_id}_wallet"
            self.wallet_address = None
            
            # First try to open existing wallet
            try:
                self.logger.info(f"Attempting to open wallet '{wallet_name}' for user {self.agent_id}")
                self.wallet_rpc.wait_until_ready(max_wait=180)
                self.wallet_rpc.open_wallet(wallet_name, password="")
                # If open succeeds, get the address
                self.wallet_address = self.wallet_rpc.get_address()
                self.logger.info(f"Successfully opened existing wallet '{wallet_name}'")
            except Exception as open_err:
                # If wallet doesn't exist or can't be opened, try to create it
                if "Wallet not found" in str(open_err) or "Failed to open wallet" in str(open_err):
                    try:
                        self.logger.info(f"Wallet doesn't exist, creating '{wallet_name}'")
                        self.wallet_rpc.create_wallet(wallet_name, password="")
                        # If creation succeeds, get the address
                        self.wallet_address = self.wallet_rpc.get_address()
                        self.logger.info(f"Successfully created new wallet '{wallet_name}'")
                    except Exception as create_err:
                        self.logger.error(f"Failed to create wallet: {create_err}")
                        # Last attempt - maybe wallet is already loaded
                        try:
                            self.logger.warning("Attempting to get address from current wallet")
                            self.wallet_rpc.wait_until_ready(max_wait=180)
                            self.wallet_address = self.wallet_rpc.get_address()
                        except Exception as addr_err:
                            self.logger.error(f"Failed to get address: {addr_err}")
                            return
                else:
                    # Some other error opening wallet, try to get address anyway
                    self.logger.warning(f"Error opening wallet: {open_err}, trying to get address from current wallet")
                    try:
                        self.wallet_rpc.wait_until_ready(max_wait=180)
                        self.wallet_address = self.wallet_rpc.get_address()
                    except Exception as addr_err:
                        self.logger.error(f"Failed to get address: {addr_err}")
                        return
            
            if self.wallet_address:
                self.logger.info(f"User wallet address: {self.wallet_address}")
                # Register user information for the agent discovery system
                self._register_user_info()
                # Initialize transaction parameters
                self._setup_transaction_parameters()
            else:
                self.logger.error(f"Failed to obtain wallet address for user {self.agent_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup regular user: {e}")
    
    def _register_miner_info(self):
        """Register miner information for the block controller with atomic file operations"""
        if not self.wallet_address:
            self.logger.warning(f"No wallet address available for miner {self.agent_id}, skipping registration")
            return
            
        miner_info = {
            "agent_id": self.agent_id,
            "wallet_address": self.wallet_address,
            "hash_rate": self.hash_rate,
            "timestamp": time.time(),
            "agent_type": "miner"
        }
        
        # Use atomic file operations with retry logic
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Write miner info to shared state
                self.write_shared_state(f"{self.agent_id}_miner_info.json", miner_info)
                self.logger.info(f"Successfully registered miner info for {self.agent_id}")
                return
            except Exception as e:
                self.logger.warning(f"Failed to register miner info (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error(f"Failed to register miner info after {max_retries} attempts")
    
    def _register_user_info(self):
        """Register user information for the agent discovery system with atomic file operations"""
        if not self.wallet_address:
            self.logger.warning(f"No wallet address available for user {self.agent_id}, skipping registration")
            return
            
        user_info = {
            "agent_id": self.agent_id,
            "wallet_address": self.wallet_address,
            "timestamp": time.time(),
            "agent_type": "regular_user",
            "tx_frequency": getattr(self, 'tx_frequency', None),
            "min_tx_amount": getattr(self, 'min_tx_amount', None),
            "max_tx_amount": getattr(self, 'max_tx_amount', None)
        }
        
        # Use atomic file operations with retry logic
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Write user info to shared state
                self.write_shared_state(f"{self.agent_id}_user_info.json", user_info)
                self.logger.info(f"Successfully registered user info for {self.agent_id}")
                return
            except Exception as e:
                self.logger.warning(f"Failed to register user info (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error(f"Failed to register user info after {max_retries} attempts")
    
    def _setup_transaction_parameters(self):
        """Setup transaction parameters for regular users"""
        # Get transaction parameters from attributes
        self.min_tx_amount = float(self.attributes.get('min_transaction_amount', '0.1'))
        self.max_tx_amount = float(self.attributes.get('max_transaction_amount', '1.0'))
        self.tx_interval = int(self.attributes.get('transaction_interval', '60'))
        
        self.logger.info(f"Transaction parameters: min={self.min_tx_amount}, max={self.max_tx_amount}, interval={self.tx_interval}")
        
    def run_iteration(self) -> Optional[float]:
        """
        Single iteration of agent behavior.
        
        Returns:
            float: The recommended time to sleep (in seconds) before the next iteration.
        """
        if self.is_miner:
            self.logger.debug("Miner iteration")
            return self._run_miner_iteration()
        else:
            self.logger.debug("Regular user iteration")
            return self._run_user_iteration()
    
    def _run_miner_iteration(self) -> Optional[float]:
        """
        Single iteration for miner behavior.
        
        Returns:
            float: The recommended time to sleep (in seconds) before the next iteration.
        """
        # Mining functionality is primarily handled by the block controller
        # Miners just need to ensure they're available and registered
        self.logger.debug("Miner running iteration - checking status")
        
        # Check if wallet is still available
        if not self.wallet_rpc:
            self.logger.warning("Wallet RPC not available for miner")
            return 30.0
            
        try:
            # Get wallet balance to monitor mining rewards
            balance_info = self.wallet_rpc.get_balance()
            self.logger.debug(f"Miner balance: {balance_info}")
            
            # Update miner info periodically
            self._register_miner_info()
            
            # Miners check status less frequently
            return 60.0
            
        except Exception as e:
            self.logger.error(f"Error in miner iteration: {e}")
            return 30.0
    
    def _run_user_iteration(self) -> Optional[float]:
        """
        Single iteration for regular user behavior.
        
        Returns:
            float: The recommended time to sleep (in seconds) before the next iteration.
        """
        # Regular users perform transactions
        self.logger.debug("Regular user running iteration - checking for transaction opportunities")
        
        # Check if wallet is available
        if not self.wallet_rpc:
            self.logger.warning("Wallet RPC not available for regular user")
            return 30.0
            
        try:
            # Get wallet balance
            balance_info = self.wallet_rpc.get_balance()
            unlocked_balance = balance_info.get('unlocked_balance', 0)
            
            # Only send transactions if we have sufficient balance
            if unlocked_balance > 0:
                self.logger.debug(f"User has unlocked balance: {unlocked_balance}")
                
                # Randomly decide whether to send a transaction
                if self._should_send_transaction():
                    self._send_random_transaction()
            
            # Use configured transaction interval
            return getattr(self, 'tx_interval', 60.0)
            
        except Exception as e:
            self.logger.error(f"Error in user iteration: {e}")
            return 30.0
    
    def _should_send_transaction(self) -> bool:
        """Determine if a transaction should be sent in this iteration"""
        # Simple random decision - can be enhanced with more sophisticated logic
        return random.random() < 0.3  # 30% chance to send transaction
    
    def _send_random_transaction(self):
        """Send a random transaction to a random recipient"""
        # Get list of other agents from shared state
        other_agents = self._get_other_agents()
        
        if not other_agents:
            self.logger.warning("No other agents found for transaction")
            return
            
        # Select random recipient
        recipient = random.choice(other_agents)
        recipient_address = recipient.get('wallet_address')
        
        if not recipient_address:
            self.logger.warning(f"No wallet address for recipient {recipient.get('agent_id')}")
            return
            
        # Generate random amount within configured range
        amount = random.uniform(self.min_tx_amount, self.max_tx_amount)
        
        try:
            # Send transaction
            tx_hash = self.wallet_rpc.transfer(
                destinations=[{
                    'address': recipient_address,
                    'amount': int(amount * 1e12)  # Convert to atomic units
                }],
                priority=1
            )
            
            self.logger.info(f"Sent transaction: {tx_hash} to {recipient.get('agent_id')} for {amount} XMR")
            
            # Record transaction in shared state
            self._record_transaction(tx_hash, recipient.get('agent_id'), amount)
            
        except Exception as e:
            self.logger.error(f"Failed to send transaction: {e}")
    
    def _get_other_agents(self) -> List[Dict[str, Any]]:
        """Get list of other agents from shared state"""
        registry = self.read_shared_state("agent_registry.json")
        agents = registry.get('agents', []) if registry else []
        
        # Filter out self and agents without wallet addresses
        other_agents = [
            agent for agent in agents
            if agent.get('id') != self.agent_id and agent.get('wallet_address')
        ]
        
        return other_agents
    
    def _record_transaction(self, tx_hash: str, recipient_id: str, amount: float):
        """Record transaction in shared state"""
        tx_record = {
            'tx_hash': tx_hash,
            'sender_id': self.agent_id,
            'recipient_id': recipient_id,
            'amount': amount,
            'timestamp': time.time()
        }
        
        self.append_shared_list('transactions.json', tx_record)
        
    def _cleanup_agent(self):
        """Agent-specific cleanup logic"""
        self.logger.info("Cleaning up RegularUserAgent")


def main():
    """Main entry point for regular user agent"""
    parser = RegularUserAgent.create_argument_parser("Regular User Agent for Monerosim")
    
    # Add any agent-specific arguments here if needed
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent
    agent = RegularUserAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        rpc_host=args.rpc_host,
        agent_rpc_port=args.agent_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        log_level=args.log_level,
        attributes=args.attributes,
        tx_frequency=args.tx_frequency,
        hash_rate=args.hash_rate
    )
    
    agent.run()


if __name__ == "__main__":
    main()