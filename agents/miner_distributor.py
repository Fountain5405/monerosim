#!/usr/bin/env python3
"""
Miner Distributor Agent for Monerosim

This agent distributes Monero from miner wallets to other participants in the network.
It discovers available miners, selects one based on configurable criteria, and uses
its wallet to send transactions to other agents.

Phase 1 Implementation: Core functionality for can_receive_distributions attribute
"""

import argparse
import json
import logging
import random
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base_agent import BaseAgent


class MinerDistributorAgent(BaseAgent):
    """
    Agent that distributes Monero from miner wallets to other agents.
    
    This agent:
    1. Discovers available miners from the agent registry
    2. Selects a miner wallet based on configurable strategy
    3. Distributes Monero to other agents in the network
    4. Records transaction history in shared state
    """
    
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        
        # Initialize transaction-specific parameters
        self.min_transaction_amount = 0.1
        self.max_transaction_amount = 1.0
        self.transaction_frequency = 60
        self.miner_selection_strategy = "weighted"
        self.transaction_priority = 1
        self.max_retries = 3
        self.recipient_selection = "random"
        
        # Runtime state
        self.miners = []
        self.selected_miner = None
        self.last_transaction_time = 0
        self.recipient_index = 0
    
    def _setup_agent(self):
        """Initialize the miner distributor agent"""
        # Parse configuration attributes
        self._parse_configuration()
        
        # Register in agent registry
        self._register_as_miner_distributor_agent()
    
    def _parse_configuration(self):
        """Parse configuration attributes from self.attributes"""
        try:
            # Parse transaction frequency
            if 'transaction_frequency' in self.attributes:
                self.transaction_frequency = int(self.attributes['transaction_frequency'])
                self.logger.info(f"Transaction frequency set to {self.transaction_frequency} seconds")
            
            # Parse transaction amount range
            if 'min_transaction_amount' in self.attributes:
                self.min_transaction_amount = float(self.attributes['min_transaction_amount'])
                self.logger.info(f"Minimum transaction amount set to {self.min_transaction_amount} XMR")
            
            if 'max_transaction_amount' in self.attributes:
                self.max_transaction_amount = float(self.attributes['max_transaction_amount'])
                self.logger.info(f"Maximum transaction amount set to {self.max_transaction_amount} XMR")
            
            # Parse miner selection strategy
            if 'miner_selection_strategy' in self.attributes:
                strategy = self.attributes['miner_selection_strategy'].lower()
                if strategy in ['weighted', 'balance', 'random']:
                    self.miner_selection_strategy = strategy
                    self.logger.info(f"Miner selection strategy set to {strategy}")
                else:
                    self.logger.warning(f"Invalid miner selection strategy: {strategy}, using default 'weighted'")
            
            # Parse transaction priority
            if 'transaction_priority' in self.attributes:
                priority = int(self.attributes['transaction_priority'])
                if 0 <= priority <= 3:
                    self.transaction_priority = priority
                    self.logger.info(f"Transaction priority set to {priority}")
                else:
                    self.logger.warning(f"Invalid transaction priority: {priority}, using default 1")
            
            # Parse max retries
            if 'max_retries' in self.attributes:
                retries = int(self.attributes['max_retries'])
                if retries > 0:
                    self.max_retries = retries
                    self.logger.info(f"Max retries set to {retries}")
                else:
                    self.logger.warning(f"Invalid max retries: {retries}, using default 3")
            
            # Parse recipient selection strategy
            if 'recipient_selection' in self.attributes:
                strategy = self.attributes['recipient_selection'].lower()
                if strategy in ['random', 'round_robin']:
                    self.recipient_selection = strategy
                    self.logger.info(f"Recipient selection strategy set to {strategy}")
                else:
                    self.logger.warning(f"Invalid recipient selection strategy: {strategy}, using default 'random'")
            
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error parsing configuration attributes: {e}")
            self.logger.info("Using default configuration values")
    
    def _discover_miners(self):
        """
        Discover available miners from agent and miner registries.
        Updates self.miners with discovered miner information.
        """
        # Read agent registry
        agent_registry = self.read_shared_state("agent_registry.json")
        if not agent_registry:
            self.logger.warning("Agent registry not found")
            return
        
        # Read miner registry
        miner_registry = self.read_shared_state("miners.json")
        if not miner_registry:
            self.logger.warning("Miner registry not found")
            return
        
        # Combine information from both registries
        self.miners = []
        for agent in agent_registry.get("agents", []):
            # Check if this agent is a miner
            if agent.get("attributes", {}).get("is_miner") == "true":
                # Find corresponding miner in miner registry
                miner_info = None
                for miner in miner_registry.get("miners", []):
                    if miner.get("ip_addr") == agent.get("ip_addr"):
                        miner_info = miner
                        break
                
                if miner_info:
                    # Combine agent and miner information
                    combined_miner = {
                        "agent_id": agent.get("id"),
                        "ip_addr": agent.get("ip_addr"),
                        "wallet_rpc_port": agent.get("wallet_rpc_port"),
                        "wallet_address": miner_info.get("wallet_address"),
                        "weight": miner_info.get("weight", 0)
                    }
                    self.miners.append(combined_miner)
        
        self.logger.info(f"Discovered {len(self.miners)} miners")
    
    def _register_as_miner_distributor_agent(self):
        """Register this agent as a miner distributor in the shared state"""
        distributor_info = {
            "agent_id": self.agent_id,
            "type": "miner_distributor",
            "timestamp": time.time()
        }
        
        self.write_shared_state(f"{self.agent_id}_distributor_info.json", distributor_info)
        self.logger.info(f"Registered miner distributor info for {self.agent_id}")
    
    def run_iteration(self) -> float:
        """Single iteration of Monero distribution behavior"""
        # Re-discover miners each iteration to get updated wallet addresses
        self._discover_miners()
        
        current_time = time.time()
        
        # Check if it's time to send a transaction
        if current_time - self.last_transaction_time >= self.transaction_frequency:
            try:
                # Select a miner wallet
                miner = self._select_miner()
                if not miner:
                    self.logger.warning("No suitable miner found, will retry later")
                    return 30.0
                
                # Select a recipient
                recipient = self._select_recipient()
                if not recipient:
                    self.logger.warning("No suitable recipient found, will retry later")
                    return 30.0
                
                # Send transaction
                success = self._send_transaction(miner, recipient)
                if success:
                    self.last_transaction_time = current_time
                
                # Return time until next transaction
                return self.transaction_frequency
                
            except Exception as e:
                self.logger.error(f"Error in transaction iteration: {e}")
                return 30.0
        
        # Calculate time until next transaction
        return self.transaction_frequency - (current_time - self.last_transaction_time)
    
    def _select_miner(self) -> Optional[Dict[str, Any]]:
        """
        Select a miner based on the configured strategy.
        
        Returns:
            Selected miner information or None if no suitable miner found
        """
        if not self.miners:
            self.logger.warning("No miners available for selection")
            return None
        
        # Filter miners that have wallet addresses
        available_miners = [m for m in self.miners if m.get("wallet_address")]
        if not available_miners:
            self.logger.warning("No miners with wallet addresses available")
            return None
        
        # Apply selection strategy
        if self.miner_selection_strategy == "weighted":
            return self._select_miner_by_weight(available_miners)
        elif self.miner_selection_strategy == "balance":
            return self._select_miner_by_balance(available_miners)
        else:  # random
            return random.choice(available_miners)
    
    def _select_miner_by_weight(self, miners: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select a miner based on hashrate weight"""
        # Extract weights
        weights = [miner.get("weight", 0) for miner in miners]
        total_weight = sum(weights)
        
        if total_weight == 0:
            self.logger.warning("Total weight is zero, falling back to random selection")
            return random.choice(miners)
        
        # Use cumulative weights for selection
        cumulative_weights = []
        cumulative_sum = 0
        for weight in weights:
            cumulative_sum += weight
            cumulative_weights.append(cumulative_sum)
        
        random_value = random.uniform(0, total_weight)
        winner_index = 0
        for i, cumulative_weight in enumerate(cumulative_weights):
            if random_value <= cumulative_weight:
                winner_index = i
                break
        
        winner = miners[winner_index]
        self.logger.info(f"Selected miner {winner.get('agent_id')} with weight {winner.get('weight')}")
        return winner
    
    def _select_miner_by_balance(self, miners: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select a miner with the highest balance"""
        # Placeholder implementation - would need RPC connection to check balances
        # For now, just select randomly
        self.logger.warning("Balance-based selection not fully implemented, using random selection")
        return random.choice(miners)
    
    def _select_recipient(self) -> Optional[Dict[str, Any]]:
        """
        Select a recipient for the transaction based on can_receive_distributions attribute.
        
        Returns:
            Recipient information or None if no suitable recipient found
        """
        # Read agent registry to find all agents with wallets
        agent_registry = self.read_shared_state("agent_registry.json")
        if not agent_registry:
            self.logger.warning("Agent registry not found")
            return None
        
        # Find all agents with wallets that are not the selected miner
        potential_recipients = []
        distribution_enabled_recipients = []
        
        for agent in agent_registry.get("agents", []):
            # Skip if this is the selected miner
            if self.selected_miner and agent.get("id") == self.selected_miner.get("agent_id"):
                continue
            
            # Only consider agents with wallets
            if not agent.get("wallet_rpc_port"):
                continue
                
            # Check if agent can receive distributions
            can_receive = self._parse_boolean_attribute(
                agent.get("attributes", {}).get("can_receive_distributions", "false")
            )
            
            potential_recipients.append(agent)
            if can_receive:
                distribution_enabled_recipients.append(agent)
        
        # Use distribution-enabled recipients if available, otherwise fall back to all recipients
        recipients_to_use = distribution_enabled_recipients if distribution_enabled_recipients else potential_recipients
        
        if not recipients_to_use:
            self.logger.warning("No potential recipients found")
            return None
        
        # Log which recipient pool we're using
        if distribution_enabled_recipients:
            self.logger.info(f"Selecting from {len(distribution_enabled_recipients)} distribution-enabled recipients")
        else:
            self.logger.info("No distribution-enabled recipients found, falling back to all wallet agents")
        
        # Apply recipient selection strategy
        if self.recipient_selection == "round_robin":
            # Round-robin selection
            recipient = recipients_to_use[self.recipient_index % len(recipients_to_use)]
            self.recipient_index += 1
            return recipient
        else:  # random
            # Random selection
            return random.choice(recipients_to_use)
    
    def _parse_boolean_attribute(self, value: str) -> bool:
        """
        Parse a boolean attribute value, supporting multiple formats.
        
        Args:
            value: String value to parse
            
        Returns:
            Boolean interpretation of the value
        """
        if not value:
            return False
            
        # Handle string representations
        value_lower = value.lower()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        elif value_lower in ("false", "0", "no", "off"):
            return False
        
        # Try to parse as boolean directly
        try:
            return value.lower() == "true"
        except:
            self.logger.warning(f"Invalid boolean attribute value: '{value}', defaulting to False")
            return False
    
    def _get_recipient_address(self, recipient: Dict[str, Any]) -> Optional[str]:
        """
        Get the wallet address for a recipient.
        
        Args:
            recipient: Recipient agent information
            
        Returns:
            Wallet address or None if unable to retrieve
        """
        # Placeholder implementation - would need RPC connection to get address
        # For now, try to get from registry
        wallet_address = recipient.get("wallet_address")
        self.logger.debug(f"Inside _get_recipient_address: recipient.get('wallet_address') returned {wallet_address}")
        return wallet_address
    
    def _send_transaction(self, miner: Dict[str, Any], recipient: Dict[str, Any]) -> bool:
        """
        Send a transaction from the selected miner to the recipient.
        
        Args:
            miner: Miner information including wallet details
            recipient: Recipient information including address
            
        Returns:
            True if transaction was sent successfully, False otherwise
        """
        # Placeholder implementation - would need RPC connection to send transactions
        self.logger.info(f"Would send transaction from {miner.get('agent_id')} to {recipient.get('id')}")
        
        # Generate random transaction amount
        amount = random.uniform(self.min_transaction_amount, self.max_transaction_amount)
        
        self.logger.debug(f"Recipient object before getting address: {recipient}")
        # Get recipient's wallet address
        recipient_address = self._get_recipient_address(recipient)
        self.logger.debug(f"Recipient address retrieved: {recipient_address}")
        if not recipient_address:
            self.logger.error(f"Failed to get recipient address for {recipient.get('id')}")
            return False
        
        # Record transaction in shared state (simulated)
        tx_hash = f"simulated_tx_{int(time.time())}"
        self._record_transaction(
            tx_hash=tx_hash,
            sender_id=miner.get("agent_id"),
            recipient_id=recipient.get("id"),
            amount=amount
        )
        
        self.logger.info(f"Simulated transaction: {tx_hash} "
                      f"from {miner.get('agent_id')} to {recipient.get('id')} "
                      f"for {amount} XMR")
        return True
    
    def _record_transaction(self, tx_hash: str, sender_id: str, recipient_id: str, amount: float):
        """Record transaction in shared state"""
        tx_record = {
            "tx_hash": tx_hash,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "amount": amount,
            "timestamp": time.time()
        }
        
        self.append_shared_list("transactions.json", tx_record)
    
    def _cleanup_agent(self):
        """Agent-specific cleanup logic"""
        self.logger.info("Cleaning up MinerDistributorAgent")


def main():
    """Main entry point for miner distributor agent"""
    parser = BaseAgent.create_argument_parser("Miner Distributor Agent for Monerosim")
    
    args = parser.parse_args()
    
    # Create and run agent
    agent = MinerDistributorAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        rpc_host=args.rpc_host,
        agent_rpc_port=args.agent_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        log_level=args.log_level,
        attributes=args.attributes
    )
    
    agent.run()


if __name__ == "__main__":
    main()