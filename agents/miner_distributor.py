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
from .monero_rpc import WalletRPC


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
        self.max_retries = 5
        self.recipient_selection = "random"
        self.initial_fund_amount = 1.0
        
        # Wait time parameters for mining reward maturation
        self.initial_wait_time = 3600  # 1 hour in seconds (default)
        self.balance_check_interval = 30  # Check balance every 30 seconds
        self.max_wait_time = 7200  # Maximum 2 hours to wait before giving up

        # Runtime state
        self.miners = []
        self.selected_miner = None
        self.last_transaction_time = 0
        self.recipient_index = 0
        self.startup_time = time.time()
        self.waiting_for_maturity = True
        self.last_balance_check = 0
        self.balance_check_attempts = 0
        self.initial_funding_completed = False
    
    def _setup_agent(self):
        """Initialize the miner distributor agent"""
        # Parse configuration attributes
        self._parse_configuration()

        # Register in agent registry
        self._register_as_miner_distributor_agent()

        # Perform initial funding of eligible agents
        self._perform_initial_funding()
    
    def _parse_configuration(self):
        """Parse configuration attributes from self.attributes"""
        config_mappings = {
            'transaction_frequency': ('int', 'transaction_frequency', 60),
            'min_transaction_amount': ('float', 'min_transaction_amount', 0.1),
            'max_transaction_amount': ('float', 'max_transaction_amount', 1.0),
            'miner_selection_strategy': ('choice', 'miner_selection_strategy', 'weighted', ['weighted', 'balance', 'random']),
            'transaction_priority': ('int_range', 'transaction_priority', 1, 0, 3),
            'max_retries': ('int_min', 'max_retries', 5, 1),
            'recipient_selection': ('choice', 'recipient_selection', 'random', ['random', 'round_robin']),
            'initial_fund_amount': ('float_min', 'initial_fund_amount', 1.0, 0),
            'initial_wait_time': ('time_duration', 'initial_wait_time', 3600),
            'balance_check_interval': ('int_min', 'balance_check_interval', 30, 1),
            'max_wait_time': ('time_duration', 'max_wait_time', 7200)
        }

        for attr_name, (type_name, field_name, *args) in config_mappings.items():
            self._parse_single_attribute(attr_name, type_name, field_name, *args)

    def _parse_single_attribute(self, attr_name: str, type_name: str, field_name: str, *args):
        """Parse a single configuration attribute"""
        if attr_name not in self.attributes:
            return

        value = self.attributes[attr_name]
        try:
            if type_name == 'int':
                parsed = int(value)
                setattr(self, field_name, parsed)
                self.logger.info(f"{field_name} set to {parsed}")
            elif type_name == 'float':
                parsed = float(value)
                setattr(self, field_name, parsed)
                self.logger.info(f"{field_name} set to {parsed}")
            elif type_name == 'choice':
                default, choices = args
                choice = value.lower()
                if choice in choices:
                    setattr(self, field_name, choice)
                    self.logger.info(f"{field_name} set to {choice}")
                else:
                    self.logger.warning(f"Invalid {field_name}: {choice}, using default {default}")
            elif type_name == 'int_range':
                default, min_val, max_val = args
                parsed = int(value)
                if min_val <= parsed <= max_val:
                    setattr(self, field_name, parsed)
                    self.logger.info(f"{field_name} set to {parsed}")
                else:
                    self.logger.warning(f"Invalid {field_name}: {parsed}, using default {default}")
            elif type_name == 'int_min':
                default, min_val = args
                parsed = int(value)
                if parsed >= min_val:
                    setattr(self, field_name, parsed)
                    self.logger.info(f"{field_name} set to {parsed}")
                else:
                    self.logger.warning(f"Invalid {field_name}: {parsed}, using default {default}")
            elif type_name == 'float_min':
                default, min_val = args
                parsed = float(value)
                if parsed > min_val:
                    setattr(self, field_name, parsed)
                    self.logger.info(f"{field_name} set to {parsed}")
                else:
                    self.logger.warning(f"Invalid {field_name}: {parsed}, using default {default}")
            elif type_name == 'time_duration':
                default = args[0]
                parsed = self._parse_time_duration(value)
                if parsed is not None:
                    setattr(self, field_name, parsed)
                    self.logger.info(f"{field_name} set to {parsed} seconds")
                else:
                    self.logger.warning(f"Invalid {field_name} format: {value}, using default {default} seconds")
        except (ValueError, TypeError) as e:
            default = args[0] if args else 'default'
            self.logger.warning(f"Error parsing {field_name}: {e}, using default {default}")

    def _parse_time_duration(self, value: str) -> Optional[int]:
        """Parse time duration string (e.g., '1h', '30m', '3600s')"""
        if isinstance(value, (int, float)):
            return int(value)
        elif isinstance(value, str):
            try:
                if value.endswith('h'):
                    return int(float(value[:-1]) * 3600)
                elif value.endswith('m'):
                    return int(float(value[:-1]) * 60)
                elif value.endswith('s'):
                    return int(float(value[:-1]))
                else:
                    return int(float(value))
            except ValueError:
                return None
        return None
    
    def _discover_miners(self):
        """
        Discover available miners from agent and miner registries.
        Updates self.miners with discovered miner information.

        Wallet addresses are looked up in this order:
        1. miners.json (may be populated by block controller)
        2. {agent_id}_miner_info.json (written by regular_user.py for miners)
        3. Query wallet RPC directly if above sources don't have it
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
                agent_id = agent.get("id")

                # Find corresponding miner in miner registry
                miner_info = None
                for miner in miner_registry.get("miners", []):
                    if miner.get("ip_addr") == agent.get("ip_addr"):
                        miner_info = miner
                        break

                if miner_info:
                    # Try to get wallet address from multiple sources
                    wallet_address = miner_info.get("wallet_address")

                    # Source 2: Check {agent_id}_miner_info.json file
                    if not wallet_address:
                        miner_info_file = self.read_shared_state(f"{agent_id}_miner_info.json")
                        if miner_info_file:
                            wallet_address = miner_info_file.get("wallet_address")
                            if wallet_address:
                                self.logger.debug(f"Found wallet address for {agent_id} in miner_info.json")

                    # Source 3: Query wallet RPC directly
                    if not wallet_address and agent.get("wallet_rpc_port"):
                        wallet_address = self._query_miner_wallet_address(agent)
                        if wallet_address:
                            self.logger.debug(f"Retrieved wallet address for {agent_id} via RPC")

                    # Combine agent and miner information
                    combined_miner = {
                        "agent_id": agent_id,
                        "ip_addr": agent.get("ip_addr"),
                        "wallet_rpc_port": agent.get("wallet_rpc_port"),
                        "wallet_address": wallet_address,
                        "weight": miner_info.get("weight", 0)
                    }
                    self.miners.append(combined_miner)

        # Log discovery results
        miners_with_wallets = sum(1 for m in self.miners if m.get("wallet_address"))
        self.logger.info(f"Discovered {len(self.miners)} miners ({miners_with_wallets} with wallet addresses)")

    def _query_miner_wallet_address(self, agent: Dict[str, Any]) -> Optional[str]:
        """
        Query a miner's wallet address directly via RPC.

        Args:
            agent: Agent information including ip_addr and wallet_rpc_port

        Returns:
            Wallet address string or None if query fails
        """
        try:
            rpc = WalletRPC(host=agent['ip_addr'], port=agent['wallet_rpc_port'])
            rpc.wait_until_ready(max_wait=30, check_interval=2)
            address = rpc.get_address()
            if address and address.startswith(('4', '8')):
                return address
        except Exception as e:
            self.logger.debug(f"Failed to query wallet address for {agent.get('id')}: {e}")
        return None
    
    def _register_as_miner_distributor_agent(self):
        """Register this agent as a miner distributor in the shared state"""
        distributor_info = {
            "agent_id": self.agent_id,
            "type": "miner_distributor",
            "timestamp": time.time()
        }
        
        self.write_shared_state(f"{self.agent_id}_distributor_info.json", distributor_info)
        self.logger.info(f"Registered miner distributor info for {self.agent_id}")

    def _perform_initial_funding(self):
        """
        Perform initial funding of eligible agents before the main mining cycle begins.
        Sends initial_fund_amount to all agents with can_receive_distributions=true.
        """
        self.logger.info("Starting initial funding of eligible agents")

        # Check if we should wait for mining rewards to mature
        current_time = time.time()
        elapsed_time = current_time - self.startup_time
        
        if self.waiting_for_maturity:
            if elapsed_time < self.initial_wait_time:
                remaining_wait = self.initial_wait_time - elapsed_time
                self.logger.info(f"Waiting for mining rewards to mature... {remaining_wait:.0f} seconds remaining")
                
                # Check if it's time to check balance
                if current_time - self.last_balance_check >= self.balance_check_interval:
                    self._check_miner_balance()
                    self.last_balance_check = current_time
                
                return
            else:
                self.logger.info("Initial wait period completed, proceeding with funding")
                self.waiting_for_maturity = False
        
        # Discover available miners
        self._discover_miners()
        if not self.miners:
            self.logger.warning("No miners available for initial funding")
            return

        # Select a miner for initial funding (use the first available miner with wallet)
        selected_miner = None
        for miner in self.miners:
            if miner.get("wallet_address"):
                selected_miner = miner
                break

        if not selected_miner:
            self.logger.warning("No miner with wallet address available for initial funding")
            self.logger.info("Will attempt to fund miners first to create wallet addresses")
            self._fund_miners_first()
            return

        self.logger.info(f"Selected miner {selected_miner.get('agent_id')} for initial funding")

        # Find all eligible recipients (agents with can_receive_distributions=true and wallets)
        agent_registry = self.read_shared_state("agent_registry.json")
        if not agent_registry:
            self.logger.warning("Agent registry not found, cannot perform initial funding")
            return

        eligible_recipients = []
        for agent in agent_registry.get("agents", []):
            # Skip the selected miner
            if agent.get("id") == selected_miner.get("agent_id"):
                continue

            # Check if agent has wallet
            if not agent.get("wallet_rpc_port"):
                continue

            # Check if agent can receive distributions
            can_receive = self._parse_boolean_attribute(
                agent.get("attributes", {}).get("can_receive_distributions", "false")
            )

            if can_receive:
                eligible_recipients.append(agent)

        if not eligible_recipients:
            self.logger.info("No eligible recipients found for initial funding")
            return

        self.logger.info(f"Found {len(eligible_recipients)} eligible recipients for initial funding")

        # Send initial funding to each eligible recipient
        funded_count = 0
        for recipient in eligible_recipients:
            success = self._send_transaction(selected_miner, recipient, self.initial_fund_amount)
            if success:
                funded_count += 1
                self.logger.info(f"Initial funding sent to {recipient.get('id')}: {self.initial_fund_amount} XMR")
            else:
                self.logger.warning(f"Failed to send initial funding to {recipient.get('id')}")

        self.logger.info(f"Initial funding completed: {funded_count}/{len(eligible_recipients)} agents funded")

        # Mark initial funding as completed if we funded at least one agent
        if funded_count > 0:
            self.initial_funding_completed = True
            self.logger.info("Initial funding phase completed successfully")
    
    def _fund_miners_first(self):
        """
        Fund miners first to ensure they have wallet addresses before distributing to others.
        This addresses the bootstrapping issue where miners need to be funded before they can send transactions.
        """
        self.logger.info("Starting miner funding to address bootstrapping issue")
        
        # Find all miners that need funding
        miners_to_fund = []
        for miner in self.miners:
            if not miner.get("wallet_address"):
                miners_to_fund.append(miner)
        
        if not miners_to_fund:
            self.logger.info("All miners already have wallet addresses")
            return
        
        self.logger.info(f"Found {len(miners_to_fund)} miners that need funding")
        
        # For now, we'll use a simple approach: fund each miner with a small amount
        # In a real implementation, this might involve a special funding mechanism
        funded_count = 0
        for miner in miners_to_fund:
            # Create a temporary recipient entry for the miner
            miner_recipient = {
                "id": miner.get("agent_id"),
                "ip_addr": miner.get("ip_addr"),
                "wallet_rpc_port": miner.get("wallet_rpc_port"),
                "attributes": {}
            }
            
            # Try to get the miner's wallet address
            address = self._get_recipient_address(miner_recipient)
            if address:
                self.logger.info(f"Miner {miner.get('agent_id')} already has address: {address}")
                funded_count += 1
            else:
                self.logger.warning(f"Could not retrieve wallet address for miner {miner.get('agent_id')}")
        
        self.logger.info(f"Miner funding completed: {funded_count}/{len(miners_to_fund)} miners have addresses")
        
        # If we successfully funded some miners, try initial funding again
        if funded_count > 0:
            self.logger.info("Re-attempting initial funding after miner funding")
            self._perform_initial_funding()
    
    def _check_miner_balance(self):
        """
        Check if any miner has sufficient unlocked balance for transactions.
        This helps distinguish between "no money" and "money not yet unlocked" scenarios.
        """
        self.balance_check_attempts += 1
        self.logger.info(f"Checking miner balances (attempt {self.balance_check_attempts})")
        
        for miner in self.miners:
            try:
                miner_rpc = WalletRPC(host=miner['ip_addr'], port=miner['wallet_rpc_port'])
                
                # Get wallet information
                wallet_info = miner_rpc.get_wallet_info()
                if not wallet_info:
                    self.logger.warning(f"Could not get wallet info for miner {miner.get('agent_id')}")
                    continue
                
                # Check balance
                balance = wallet_info.get('balance', 0)
                unlocked_balance = wallet_info.get('unlocked_balance', 0)
                
                self.logger.info(f"Miner {miner.get('agent_id')} - Balance: {balance} XMR, Unlocked: {unlocked_balance} XMR")
                
                # If we find a miner with sufficient unlocked balance, we can proceed
                if unlocked_balance >= self.initial_fund_amount:
                    self.logger.info(f"Miner {miner.get('agent_id')} has sufficient unlocked balance ({unlocked_balance} XMR)")
                    self.waiting_for_maturity = False
                    return True
                
            except Exception as e:
                self.logger.warning(f"Error checking balance for miner {miner.get('agent_id')}: {e}")
                continue
        
        # Check if we've exceeded the maximum wait time
        current_time = time.time()
        elapsed_time = current_time - self.startup_time
        
        if elapsed_time >= self.max_wait_time:
            self.logger.warning(f"Maximum wait time ({self.max_wait_time} seconds) exceeded, proceeding with funding attempt")
            self.waiting_for_maturity = False
            return True
        
        self.logger.info("No miners have sufficient unlocked balance yet, continuing to wait")
        return False

    def run_iteration(self) -> float:
        """Single iteration of Monero distribution behavior"""
        # Re-discover miners each iteration to get updated wallet addresses
        self._discover_miners()

        current_time = time.time()

        # Check if we need to perform or retry initial funding
        if not self.initial_funding_completed:
            # Check if we're still waiting for maturity
            if self.waiting_for_maturity:
                elapsed_time = current_time - self.startup_time
                if elapsed_time >= self.initial_wait_time:
                    self.logger.info("Initial wait period completed, proceeding with funding")
                    self.waiting_for_maturity = False
                elif current_time - self.last_balance_check >= self.balance_check_interval:
                    # Periodically check if miners have unlocked balance
                    self._check_miner_balance()
                    self.last_balance_check = current_time

            # If no longer waiting, attempt initial funding
            if not self.waiting_for_maturity:
                self._perform_initial_funding()
                # Return early to give time for initial funds to propagate
                return 30.0
        
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
    
    def _validate_transaction_params(self, address: str, amount: float) -> bool:
        """
        Validate transaction parameters before sending.
        
        Args:
            address: Recipient wallet address
            amount: Transaction amount in XMR
            
        Returns:
            True if parameters are valid, False otherwise
        """
        # Validate address format
        if not address or not isinstance(address, str):
            self.logger.error(f"Invalid address: {address}")
            return False
        
        # Basic Monero address validation (4-95 characters, starts with 4 or 8)
        if not (address.startswith(('4', '8')) and 4 <= len(address) <= 95):
            self.logger.error(f"Invalid Monero address format: {address}")
            return False
        
        # Validate amount
        if not isinstance(amount, (int, float)) or amount <= 0:
            self.logger.error(f"Invalid amount: {amount} (must be positive)")
            return False
        
        # Check minimum transaction amount
        if amount < self.min_transaction_amount:
            self.logger.error(f"Amount {amount} is below minimum {self.min_transaction_amount}")
            return False
        
        # Check maximum transaction amount
        if amount > self.max_transaction_amount:
            self.logger.error(f"Amount {amount} exceeds maximum {self.max_transaction_amount}")
            return False
        
        # Check for reasonable maximum (1000 XMR as sanity check)
        if amount > 1000:
            self.logger.error(f"Amount {amount} exceeds reasonable maximum (1000 XMR)")
            return False
        
        # Additional validation: check if amount would result in valid atomic units
        # Monero uses 12 decimal places, so we need to ensure the amount can be properly converted
        try:
            amount_atomic = int(amount * 10**12)
            if amount_atomic <= 0:
                self.logger.error(f"Amount {amount} XMR converts to invalid atomic units: {amount_atomic}")
                return False
            
            # Check for dust amount (minimum atomic unit is 1)
            if amount_atomic < 1:  # This should never happen with positive amounts, but good to check
                self.logger.error(f"Amount {amount} XMR is below minimum atomic unit (1 piconero)")
                return False
        except (ValueError, OverflowError) as e:
            self.logger.error(f"Failed to convert amount {amount} to atomic units: {e}")
            return False
        
        self.logger.debug(f"Transaction parameters validated: address={address}, amount={amount} XMR ({amount_atomic} atomic)")
        return True
    
    def _get_recipient_address(self, recipient: Dict[str, Any]) -> Optional[str]:
        """
        Get the wallet address for a recipient with improved error handling and retries.

        Args:
            recipient: Recipient agent information

        Returns:
            Wallet address or None if unable to retrieve
        """
        max_retries = 5
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                rpc = WalletRPC(host=recipient['ip_addr'], port=recipient['wallet_rpc_port'])
                
                # Wait for wallet to be ready
                rpc.wait_until_ready(max_wait=180, check_interval=2)
                
                # Get address with error handling
                address = rpc.get_address()
                
                if not address:
                    self.logger.warning(f"Empty address returned for recipient {recipient['id']}")
                    return None
                
                # Validate address format
                if not (address.startswith(('4', '8')) and 4 <= len(address) <= 95):
                    self.logger.error(f"Invalid address format for recipient {recipient['id']}: {address}")
                    return None
                
                self.logger.debug(f"Retrieved address for recipient {recipient['id']}: {address}")
                return address
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to get address for recipient {recipient['id']}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error(f"Failed to get address for recipient {recipient['id']} after {max_retries} attempts: {e}")
                    return None
    
    def _send_transaction(self, miner: Dict[str, Any], recipient: Dict[str, Any], amount: Optional[float] = None) -> bool:
        """
        Send a transaction from the selected miner to the recipient.

        Args:
            miner: Miner information including wallet details
            recipient: Recipient information including address

        Returns:
            True if transaction was sent successfully, False otherwise
        """
        # Get recipient's wallet address
        recipient_address = self._get_recipient_address(recipient)
        if not recipient_address:
            self.logger.error(f"Failed to get recipient address for {recipient.get('id')}")
            return False

        # Validate and set transaction amount
        if amount is None:
            amount = random.uniform(self.min_transaction_amount, self.max_transaction_amount)
        
        # Validate transaction parameters
        if not self._validate_transaction_params(recipient_address, amount):
            return False

        # Convert XMR to atomic units (picomonero) for the RPC call
        # 1 XMR = 10^12 picomonero (atomic units)
        try:
            amount_atomic = int(amount * 10**12)
            if amount_atomic <= 0:
                self.logger.error(f"Invalid atomic unit conversion: {amount} XMR -> {amount_atomic} atomic units")
                return False
        except (ValueError, OverflowError) as e:
            self.logger.error(f"Failed to convert amount {amount} to atomic units: {e}")
            return False

        # Connect to miner's wallet RPC with retries
        for attempt in range(self.max_retries):
            try:
                miner_rpc = WalletRPC(host=miner['ip_addr'], port=miner['wallet_rpc_port'])
                
                # Prepare transaction parameters with detailed logging
                tx_params = {
                    'destinations': [{'address': recipient_address, 'amount': amount_atomic}],
                    'priority': self.transaction_priority,
                    'get_tx_key': True,
                    'do_not_relay': False
                }
                
                self.logger.debug(f"Transaction parameters: {json.dumps(tx_params, indent=2)}")
                self.logger.info(f"Preparing transaction: {amount} XMR ({amount_atomic} atomic units) to {recipient_address}")
                
                # Send transaction
                tx = miner_rpc.transfer(**tx_params)
                tx_hash = tx.get('tx_hash', '')
                
                if not tx_hash:
                    self.logger.error(f"Transaction response missing tx_hash: {tx}")
                    return False

                # Record transaction in shared state (store original XMR amount)
                self._record_transaction(
                    tx_hash=tx_hash,
                    sender_id=miner.get("agent_id"),
                    recipient_id=recipient.get("id"),
                    amount=amount
                )

                self.logger.info(f"Transaction sent successfully: {tx_hash} "
                              f"from {miner.get('agent_id')} to {recipient.get('id')} "
                              f"for {amount} XMR ({amount_atomic} atomic units)")
                return True

            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for specific error types to determine retry strategy
                if "not enough money" in error_msg or "insufficient funds" in error_msg:
                    self.logger.warning(f"Transaction attempt {attempt + 1}/{self.max_retries} failed: Insufficient funds in miner wallet")
                    
                    # If this is a permanent failure (no money at all), don't retry
                    if attempt == 0:
                        # Check if this might be a "money not yet unlocked" issue
                        self.logger.info("Checking if this is a 'money not yet unlocked' issue...")
                        if self._check_miner_balance():
                            self.logger.info("Miner has balance but it's not yet unlocked, will wait and retry")
                            if attempt < self.max_retries - 1:
                                time.sleep(60)  # Wait longer for unlock
                                continue
                        else:
                            self.logger.error("Miner has insufficient funds, cannot complete transaction")
                            return False
                    else:
                        self.logger.error(f"Miner still has insufficient funds after {attempt + 1} attempts")
                        return False
                        
                elif "invalid params" in error_msg:
                    self.logger.error(f"Transaction attempt {attempt + 1}/{self.max_retries} failed: Invalid parameters")
                    self.logger.error(f"Invalid parameters detected - Amount: {amount} XMR ({amount_atomic} atomic units), Address: {recipient_address}")
                    self.logger.error(f"Transaction parameters that caused error: {json.dumps(tx_params, indent=2)}")
                    # Invalid params are usually not recoverable, so don't retry
                    return False
                    
                elif "wallet is not ready" in error_msg or "wallet not ready" in error_msg:
                    self.logger.warning(f"Transaction attempt {attempt + 1}/{self.max_retries} failed: Wallet not ready")
                    if attempt < self.max_retries - 1:
                        time.sleep(5 * (attempt + 1))  # Progressive wait for wallet to be ready
                        continue
                    else:
                        self.logger.error(f"Wallet still not ready after {self.max_retries} attempts")
                        return False
                        
                else:
                    # Generic error - could be network issue, temporary failure, etc.
                    self.logger.warning(f"Transaction attempt {attempt + 1}/{self.max_retries} failed: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        self.logger.error(f"Failed to send transaction after {self.max_retries} attempts due to: {e}")
                        return False
    
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