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
import os
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

        # Deterministic seeding for reproducibility
        self.global_seed = int(os.getenv('SIMULATION_SEED', '12345'))
        self.agent_seed = self.global_seed + hash(agent_id)
        random.seed(self.agent_seed)

        # Initialize transaction-specific parameters
        self.min_transaction_amount = 0.1
        self.max_transaction_amount = 1.0
        self.transaction_frequency = 60
        self.miner_selection_strategy = "weighted"
        self.transaction_priority = 1
        self.max_retries = 5
        self.recipient_selection = "random"

        # Miner distributor transaction parameters (all prefixed with md_)
        # NOTE: Monero has a limit of ~16 outputs per transaction.
        # Ensure md_n_recipients * md_out_per_tx <= 16 to avoid "tx too large" errors.
        # md_n_recipients: How many different recipients per batch transaction
        self.md_n_recipients = 8
        # md_out_per_tx: How many outputs (UTXOs) each recipient gets per transaction
        self.md_out_per_tx = 2
        # md_output_amount: XMR amount per output
        self.md_output_amount = 5.0
        
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

        # Continuous funding cycle state
        self._funding_cycle_index = 0  # Current position in funding cycle
        self._last_funding_cycle_time = 0  # Last time we ran a funding cycle
        self._funding_cycle_interval = 300  # Run funding cycle every 5 minutes
    
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
            'initial_wait_time': ('time_duration', 'initial_wait_time', 3600),
            'balance_check_interval': ('int_min', 'balance_check_interval', 30, 1),
            'max_wait_time': ('time_duration', 'max_wait_time', 7200),
            'md_n_recipients': ('int_min', 'md_n_recipients', 8, 1),
            'md_out_per_tx': ('int_min', 'md_out_per_tx', 2, 1),
            'md_output_amount': ('float_min', 'md_output_amount', 5.0, 0.001)
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

    def _read_funding_status(self) -> Dict[str, Any]:
        """Read initial funding status from shared state"""
        status = self.read_shared_state("initial_funding_status.json")
        if not status:
            return {
                "funded_recipients": [],
                "failed_recipients": [],
                "completed": False,
                "last_updated": None
            }
        return status

    def _write_funding_status(self, funded: List[str], failed: List[str], completed: bool):
        """Write initial funding status to shared state"""
        status = {
            "funded_recipients": funded,
            "failed_recipients": failed,
            "completed": completed,
            "last_updated": time.time()
        }
        self.write_shared_state("initial_funding_status.json", status)
        self.logger.debug(f"Updated funding status: {len(funded)} funded, {len(failed)} failed, completed={completed}")

    def _perform_initial_funding(self):
        """
        Perform initial funding of eligible agents before the main mining cycle begins.
        Sends md_out_per_tx outputs of md_output_amount XMR to each eligible recipient.
        Tracks progress in initial_funding_status.json to support resumption.
        """
        # Check existing funding status
        funding_status = self._read_funding_status()
        if funding_status.get("completed"):
            self.logger.info("Initial funding already completed (from status file)")
            self.initial_funding_completed = True
            return

        already_funded = set(funding_status.get("funded_recipients", []))
        previously_failed = set(funding_status.get("failed_recipients", []))

        if already_funded:
            self.logger.info(f"Resuming initial funding: {len(already_funded)} already funded, {len(previously_failed)} previously failed")

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

        # Check if any miners have wallet addresses
        miners_with_wallets = [m for m in self.miners if m.get("wallet_address")]
        if not miners_with_wallets:
            self.logger.warning("No miner with wallet address available for initial funding")
            self.logger.info("Will attempt to fund miners first to create wallet addresses")
            self._fund_miners_first()
            return

        self.logger.info(f"Found {len(miners_with_wallets)} miners with wallet addresses for initial funding")

        # Find all eligible recipients (agents with can_receive_distributions=true and wallets)
        agent_registry = self.read_shared_state("agent_registry.json")
        if not agent_registry:
            self.logger.warning("Agent registry not found, cannot perform initial funding")
            return

        # Get miner IDs to exclude from recipients
        miner_ids = {m.get("agent_id") for m in self.miners}

        # Build list of eligible recipients, excluding already funded ones
        all_eligible = []
        unfunded_recipients = []
        for agent in agent_registry.get("agents", []):
            # Skip miners
            if agent.get("id") in miner_ids:
                continue

            # Check if agent has wallet
            if not agent.get("wallet_rpc_port"):
                continue

            # Check if agent can receive distributions
            can_receive = self._parse_boolean_attribute(
                agent.get("attributes", {}).get("can_receive_distributions", "false")
            )

            if can_receive:
                all_eligible.append(agent)
                # Only add to unfunded if not already funded
                if agent.get("id") not in already_funded:
                    unfunded_recipients.append(agent)

        if not all_eligible:
            self.logger.info("No eligible recipients found for initial funding")
            self._write_funding_status(list(already_funded), list(previously_failed), True)
            self.initial_funding_completed = True
            return

        if not unfunded_recipients:
            self.logger.info(f"All {len(all_eligible)} eligible recipients already funded!")
            self._write_funding_status(list(already_funded), list(previously_failed), True)
            self.initial_funding_completed = True
            return

        self.logger.info(f"Found {len(unfunded_recipients)} unfunded recipients (of {len(all_eligible)} total eligible)")

        # Batch recipients for efficient multi-output transactions
        batch_size = max(1, self.md_n_recipients)
        recipient_batches = [
            unfunded_recipients[i:i + batch_size]
            for i in range(0, len(unfunded_recipients), batch_size)
        ]

        self.logger.info(f"Batching {len(unfunded_recipients)} recipients into {len(recipient_batches)} batches of up to {batch_size}")

        # Track funding progress (start with existing data)
        funded_recipients = set(already_funded)
        failed_recipients = set(previously_failed)
        exhausted_miners = set()
        total_miners = len(miners_with_wallets)

        for batch_idx, batch in enumerate(recipient_batches):
            # Select a miner for this batch using configured strategy
            selected_miner = self._select_miner_excluding(exhausted_miners)

            # If all miners exhausted, reset and give them another chance
            if not selected_miner and len(exhausted_miners) >= total_miners:
                self.logger.info("All miners exhausted, resetting exhausted list to retry")
                exhausted_miners.clear()
                selected_miner = self._select_miner_excluding(exhausted_miners)

            if not selected_miner:
                self.logger.warning(f"No miners with sufficient funds available for batch {batch_idx + 1}")
                for r in batch:
                    failed_recipients.add(r.get('id'))
                # Persist progress and return - will retry on next iteration
                self._write_funding_status(list(funded_recipients), list(failed_recipients), False)
                self.logger.info(f"Pausing initial funding: {len(funded_recipients)} funded so far, will retry later")
                return

            self.logger.info(f"Processing batch {batch_idx + 1}/{len(recipient_batches)} "
                           f"({len(batch)} recipients) using miner {selected_miner.get('agent_id')}")

            # Send batch transaction
            success, funded_ids, batch_failed = self._send_batch_transaction(
                selected_miner, batch
            )

            if success:
                for rid in funded_ids:
                    funded_recipients.add(rid)
                    failed_recipients.discard(rid)  # Remove from failed if previously failed
                for rid in batch_failed:
                    failed_recipients.add(rid)
                self.logger.info(f"Batch {batch_idx + 1} completed: {len(funded_ids)} funded")
                # Persist progress after each successful batch
                self._write_funding_status(list(funded_recipients), list(failed_recipients), False)
            else:
                # Mark miner as exhausted and retry with different miner
                self.logger.warning(f"Batch {batch_idx + 1} failed with miner {selected_miner.get('agent_id')}")
                exhausted_miners.add(selected_miner.get('agent_id'))

                retry_miner = self._select_miner_excluding(exhausted_miners)

                if not retry_miner and len(exhausted_miners) >= total_miners:
                    self.logger.info("All miners exhausted after failure, resetting for retry")
                    exhausted_miners.clear()
                    retry_miner = self._select_miner_excluding(exhausted_miners)

                if retry_miner:
                    self.logger.info(f"Retrying batch {batch_idx + 1} with miner {retry_miner.get('agent_id')}")
                    success, funded_ids, batch_failed = self._send_batch_transaction(
                        retry_miner, batch
                    )
                    if success:
                        for rid in funded_ids:
                            funded_recipients.add(rid)
                            failed_recipients.discard(rid)
                        for rid in batch_failed:
                            failed_recipients.add(rid)
                        self._write_funding_status(list(funded_recipients), list(failed_recipients), False)
                    else:
                        exhausted_miners.add(retry_miner.get('agent_id'))
                        for r in batch:
                            failed_recipients.add(r.get('id'))
                        # Persist and return - will retry later
                        self._write_funding_status(list(funded_recipients), list(failed_recipients), False)
                        self.logger.info(f"Pausing initial funding: {len(funded_recipients)} funded, will retry later")
                        return
                else:
                    for r in batch:
                        failed_recipients.add(r.get('id'))
                    self._write_funding_status(list(funded_recipients), list(failed_recipients), False)
                    self.logger.info(f"Pausing initial funding: {len(funded_recipients)} funded, will retry later")
                    return

        # Check if all eligible recipients are now funded
        all_funded = len(funded_recipients) >= len(all_eligible)
        self._write_funding_status(list(funded_recipients), list(failed_recipients), all_funded)

        self.logger.info(f"Initial funding progress: {len(funded_recipients)}/{len(all_eligible)} agents funded")
        if failed_recipients:
            self.logger.warning(f"Failed recipients: {len(failed_recipients)}")

        if all_funded:
            self.initial_funding_completed = True
            self.logger.info("Initial funding phase completed - ALL recipients funded!")
    
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

                # Get wallet balance (returns values in atomic units / piconero)
                balance_info = miner_rpc.get_balance()
                if not balance_info:
                    self.logger.warning(f"Could not get balance for miner {miner.get('agent_id')}")
                    continue

                # Convert from atomic units to XMR (1 XMR = 10^12 piconero)
                balance_atomic = balance_info.get('balance', 0)
                unlocked_atomic = balance_info.get('unlocked_balance', 0)
                balance_xmr = balance_atomic / 1e12
                unlocked_xmr = unlocked_atomic / 1e12

                self.logger.info(f"Miner {miner.get('agent_id')} - Balance: {balance_xmr:.6f} XMR, Unlocked: {unlocked_xmr:.6f} XMR")

                # If we find a miner with sufficient unlocked balance, we can proceed
                # Check if miner has enough for at least one batch (n_recipients * out_per_tx * output_amount)
                min_required = self.md_n_recipients * self.md_out_per_tx * self.md_output_amount
                if unlocked_xmr >= min_required:
                    self.logger.info(f"Miner {miner.get('agent_id')} has sufficient unlocked balance ({unlocked_xmr:.6f} XMR)")
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

    def _run_funding_cycle(self):
        """
        Continuously cycle through funded users and send them more funds.
        This ensures users always have funds to transact with.
        """
        self.logger.info("Running continuous funding cycle")

        # Read the funding status to get previously funded recipients
        funding_status = self._read_funding_status()
        funded_recipients = funding_status.get("funded_recipients", [])

        if not funded_recipients:
            self.logger.debug("No funded recipients to cycle through")
            return

        # Read agent registry to get wallet info for funded recipients
        agent_registry = self.read_shared_state("agent_registry.json")
        if not agent_registry:
            self.logger.warning("Agent registry not found, cannot run funding cycle")
            return

        # Build lookup of agents by ID
        agents_by_id = {agent.get("id"): agent for agent in agent_registry.get("agents", [])}

        # Sort recipients for deterministic ordering
        sorted_recipients = sorted(funded_recipients)

        # Get the next batch of recipients to fund (cycling through the list)
        batch_size = max(1, self.md_n_recipients)
        start_idx = self._funding_cycle_index % len(sorted_recipients)

        # Build the batch, wrapping around if necessary
        batch_ids = []
        for i in range(batch_size):
            idx = (start_idx + i) % len(sorted_recipients)
            batch_ids.append(sorted_recipients[idx])

        # Update cycle index for next iteration
        self._funding_cycle_index = (start_idx + batch_size) % len(sorted_recipients)

        self.logger.info(f"Funding cycle: batch of {len(batch_ids)} recipients starting at index {start_idx}")

        # Build list of agent objects for the batch
        batch_agents = []
        for recipient_id in batch_ids:
            agent = agents_by_id.get(recipient_id)
            if agent and agent.get("wallet_rpc_port"):
                batch_agents.append(agent)
            else:
                self.logger.debug(f"Skipping {recipient_id}: not found or no wallet RPC port")

        if not batch_agents:
            self.logger.warning("No valid agents in this funding batch")
            return

        # Select a miner for funding
        selected_miner = self._select_miner()
        if not selected_miner:
            self.logger.warning("No miner available for funding cycle, will retry later")
            return

        # Refresh miner's wallet before sending (handles post-upgrade daemon state)
        try:
            miner_rpc = WalletRPC(host=selected_miner['ip_addr'], port=selected_miner['wallet_rpc_port'])
            miner_rpc.wait_until_ready(max_wait=30, check_interval=2)
            miner_rpc.refresh()
            self.logger.debug(f"Refreshed miner {selected_miner.get('agent_id')} wallet before funding cycle")
        except Exception as e:
            self.logger.warning(f"Failed to refresh miner wallet: {e}")

        # Send batch transaction to fund the recipients
        self.logger.info(f"Funding {len(batch_agents)} agents: {[a.get('id') for a in batch_agents]}")

        success, funded_ids, failed_ids = self._send_batch_transaction(
            selected_miner, batch_agents
        )

        if success:
            self.logger.info(f"Funding cycle complete: funded {len(funded_ids)} agents")
        else:
            self.logger.warning(f"Funding cycle failed for batch, will retry next cycle")

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

        # After initial funding is complete, continuously cycle through funded users
        if self.initial_funding_completed:
            if current_time - self._last_funding_cycle_time >= self._funding_cycle_interval:
                self._run_funding_cycle()
                self._last_funding_cycle_time = current_time
                return self._funding_cycle_interval

        # Fallback: if not time for funding cycle yet, wait
        time_until_next = self._funding_cycle_interval - (current_time - self._last_funding_cycle_time)
        return max(30.0, time_until_next)
    
    def _select_miner(self) -> Optional[Dict[str, Any]]:
        """
        Select a miner based on the configured strategy.

        Returns:
            Selected miner information or None if no suitable miner found
        """
        return self._select_miner_excluding(set())

    def _select_miner_excluding(self, excluded_miner_ids: set) -> Optional[Dict[str, Any]]:
        """
        Select a miner based on the configured strategy, excluding specified miners.

        Args:
            excluded_miner_ids: Set of miner agent IDs to exclude from selection

        Returns:
            Selected miner information or None if no suitable miner found
        """
        if not self.miners:
            self.logger.warning("No miners available for selection")
            return None

        # Filter miners that have wallet addresses and are not excluded
        available_miners = [
            m for m in self.miners
            if m.get("wallet_address") and m.get("agent_id") not in excluded_miner_ids
        ]
        if not available_miners:
            self.logger.warning(f"No miners with wallet addresses available (excluded: {len(excluded_miner_ids)})")
            return None

        # Sort miners by agent_id for deterministic random selection
        available_miners.sort(key=lambda m: m.get("agent_id", ""))

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

        # Sort recipients by agent ID for deterministic selection
        recipients_to_use.sort(key=lambda r: r.get("id", ""))

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
    
    def _validate_transaction_params(self, address: str, amount: float, skip_max_check: bool = False) -> bool:
        """
        Validate transaction parameters before sending.

        Args:
            address: Recipient wallet address
            amount: Transaction amount in XMR
            skip_max_check: If True, skip max_transaction_amount validation (used for
                           batch funding where md_output_amount is explicitly configured)

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
        
        # Check maximum transaction amount (skip for batch funding with explicit md_output_amount)
        if not skip_max_check and amount > self.max_transaction_amount:
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
        Get the wallet address for a recipient, checking cached sources first.

        Lookup order:
        1. Check if recipient dict already has wallet_address
        2. Check {agent_id}_user_info.json file
        3. Fall back to wallet RPC connection (with retries)

        Args:
            recipient: Recipient agent information

        Returns:
            Wallet address or None if unable to retrieve
        """
        recipient_id = recipient.get('id')

        # 1. Check if recipient dict already has wallet_address
        if recipient.get('wallet_address'):
            address = recipient['wallet_address']
            self.logger.debug(f"Using cached address from recipient dict for {recipient_id}")
            return address

        # 2. Check user_info.json file
        user_info = self.read_shared_state(f"{recipient_id}_user_info.json")
        if user_info and user_info.get('wallet_address'):
            address = user_info['wallet_address']
            self.logger.debug(f"Using cached address from user_info.json for {recipient_id}")
            return address

        # 3. Fall back to wallet RPC connection
        self.logger.debug(f"No cached address for {recipient_id}, connecting to wallet RPC")
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
                    self.logger.warning(f"Empty address returned for recipient {recipient_id}")
                    return None

                # Validate address format
                if not (address.startswith(('4', '8')) and 4 <= len(address) <= 95):
                    self.logger.error(f"Invalid address format for recipient {recipient_id}: {address}")
                    return None

                self.logger.debug(f"Retrieved address via RPC for recipient {recipient_id}: {address}")
                return address

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to get address for recipient {recipient_id}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error(f"Failed to get address for recipient {recipient_id} after {max_retries} attempts: {e}")
                    return None
    
    def _send_transaction(self, miner: Dict[str, Any], recipient: Dict[str, Any]) -> bool:
        """
        Send a transaction from the selected miner to a single recipient.
        Uses md_out_per_tx outputs of md_output_amount each.

        Args:
            miner: Miner information including wallet details
            recipient: Recipient information including address

        Returns:
            True if transaction was sent successfully, False otherwise
        """
        # Delegate to batch transaction with single recipient (uses md_ defaults)
        success, _, _ = self._send_batch_transaction(miner, [recipient])
        return success

    def _send_batch_transaction(
        self,
        miner: Dict[str, Any],
        recipients: List[Dict[str, Any]],
        outputs_per_recipient: Optional[int] = None,
        amount_per_output: Optional[float] = None
    ) -> tuple[bool, List[str], List[str]]:
        """
        Send a transaction from the selected miner to multiple recipients.
        Each recipient receives multiple outputs (UTXOs) for independent spending.

        Args:
            miner: Miner information including wallet details
            recipients: List of recipient information dicts
            outputs_per_recipient: Outputs per recipient (default: md_out_per_tx)
            amount_per_output: XMR per output (default: md_output_amount)

        Returns:
            Tuple of (success, list of funded recipient IDs, list of failed recipient IDs)
        """
        if not recipients:
            self.logger.warning("No recipients provided for batch transaction")
            return False, [], []

        # Use configured defaults if not specified
        num_outputs_per_recipient = outputs_per_recipient if outputs_per_recipient is not None else self.md_out_per_tx
        per_output_amount = amount_per_output if amount_per_output is not None else self.md_output_amount

        # Build destinations for all recipients
        destinations = []
        recipient_addresses = {}  # Map address -> recipient for logging
        failed_recipients = []
        valid_recipients = []

        for recipient in recipients:
            recipient_address = self._get_recipient_address(recipient)
            if not recipient_address:
                self.logger.warning(f"Failed to get address for recipient {recipient.get('id')}, skipping")
                failed_recipients.append(recipient.get('id'))
                continue

            recipient_addresses[recipient_address] = recipient
            valid_recipients.append((recipient, recipient_address))

        if not valid_recipients:
            self.logger.error("No valid recipients with addresses for batch transaction")
            return False, [], [r.get('id') for r in recipients]

        # Convert XMR to atomic units
        try:
            amount_atomic = int(per_output_amount * 10**12)
            if amount_atomic <= 0:
                self.logger.error(f"Invalid atomic unit conversion: {per_output_amount} XMR -> {amount_atomic} atomic units")
                return False, [], [r.get('id') for r in recipients]
        except (ValueError, OverflowError) as e:
            self.logger.error(f"Failed to convert amount {per_output_amount} to atomic units: {e}")
            return False, [], [r.get('id') for r in recipients]

        # Build destinations: md_out_per_tx outputs for EACH recipient
        for recipient, recipient_address in valid_recipients:
            # Validate params for this recipient (skip max check since md_output_amount is explicit)
            if not self._validate_transaction_params(recipient_address, per_output_amount, skip_max_check=True):
                self.logger.warning(f"Invalid params for recipient {recipient.get('id')}, skipping")
                failed_recipients.append(recipient.get('id'))
                continue

            # Add multiple outputs to same recipient address
            for _ in range(num_outputs_per_recipient):
                destinations.append({'address': recipient_address, 'amount': amount_atomic})

        if not destinations:
            self.logger.error("No valid destinations after validation")
            return False, [], [r.get('id') for r in recipients]

        num_recipients = len(valid_recipients) - len([r for r in failed_recipients if r in [v[0].get('id') for v in valid_recipients]])
        num_outputs = len(destinations)
        total_amount = per_output_amount * num_outputs
        per_recipient_total = per_output_amount * num_outputs_per_recipient

        # Connect to miner's wallet RPC with retries
        for attempt in range(self.max_retries):
            try:
                miner_rpc = WalletRPC(host=miner['ip_addr'], port=miner['wallet_rpc_port'])

                # Prepare transaction parameters
                tx_params = {
                    'destinations': destinations,
                    'priority': self.transaction_priority,
                    'get_tx_key': True,
                    'do_not_relay': False
                }

                self.logger.debug(f"Batch transaction parameters: {json.dumps(tx_params, indent=2)}")
                self.logger.info(f"Preparing batch transaction: {num_recipients} recipients x {num_outputs_per_recipient} outputs x {per_output_amount} XMR = {total_amount} XMR total")

                # Send transaction using transfer_split to automatically handle large transactions
                tx = miner_rpc.transfer_split(**tx_params)

                # transfer_split returns tx_hash_list instead of tx_hash
                tx_hash_list = tx.get('tx_hash_list', [])
                if not tx_hash_list:
                    # Fallback to single tx_hash if present
                    single_hash = tx.get('tx_hash', '')
                    if single_hash:
                        tx_hash_list = [single_hash]
                    else:
                        self.logger.error(f"Transaction response missing tx_hash_list: {tx}")
                        return False, [], [r.get('id') for r in recipients]

                tx_hash = tx_hash_list[0]  # Use first hash for recording
                num_splits = len(tx_hash_list)
                if num_splits > 1:
                    self.logger.info(f"Transaction was split into {num_splits} parts: {tx_hash_list}")

                # Record transaction for each recipient (once per recipient, with total outputs)
                funded_recipient_ids = []
                seen_recipients = set()
                for recipient, recipient_address in valid_recipients:
                    recipient_id = recipient.get('id')
                    if recipient_id in seen_recipients or recipient_id in failed_recipients:
                        continue
                    seen_recipients.add(recipient_id)
                    funded_recipient_ids.append(recipient_id)
                    self._record_transaction(
                        tx_hash=tx_hash,
                        sender_id=miner.get("agent_id"),
                        recipient_id=recipient_id,
                        amount=per_recipient_total,
                        num_outputs=num_outputs_per_recipient,
                        amount_per_output=per_output_amount
                    )

                self.logger.info(f"Batch transaction sent successfully: {tx_hash} "
                              f"({num_splits} split(s)) from {miner.get('agent_id')} to {len(funded_recipient_ids)} recipients "
                              f"for {total_amount} XMR ({per_recipient_total} XMR each = {num_outputs_per_recipient} x {per_output_amount})")
                return True, funded_recipient_ids, failed_recipients

            except Exception as e:
                error_msg = str(e).lower()

                # Check for specific error types to determine retry strategy
                if "not enough money" in error_msg or "insufficient funds" in error_msg:
                    self.logger.warning(f"Batch transaction attempt {attempt + 1}/{self.max_retries} failed: Insufficient funds in miner wallet")
                    # Don't retry insufficient funds - caller should try different miner
                    return False, [], [r.get('id') for r in recipients]

                elif "invalid params" in error_msg:
                    self.logger.error(f"Batch transaction attempt {attempt + 1}/{self.max_retries} failed: Invalid parameters")
                    self.logger.error(f"Invalid parameters detected - {num_outputs} outputs x {per_output_amount} XMR ({amount_atomic} atomic units each)")
                    return False, [], [r.get('id') for r in recipients]

                elif "wallet is not ready" in error_msg or "wallet not ready" in error_msg:
                    self.logger.warning(f"Batch transaction attempt {attempt + 1}/{self.max_retries} failed: Wallet not ready")
                    if attempt < self.max_retries - 1:
                        time.sleep(5 * (attempt + 1))
                        continue
                    else:
                        self.logger.error(f"Wallet still not ready after {self.max_retries} attempts")
                        return False, [], [r.get('id') for r in recipients]

                else:
                    self.logger.warning(f"Batch transaction attempt {attempt + 1}/{self.max_retries} failed: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        self.logger.error(f"Failed to send batch transaction after {self.max_retries} attempts: {e}")
                        return False, [], [r.get('id') for r in recipients]

        # Should not reach here, but return failure if we do
        return False, [], [r.get('id') for r in recipients]
    
    def _record_transaction(self, tx_hash: str, sender_id: str, recipient_id: str, amount: float,
                            num_outputs: int = 1, amount_per_output: Optional[float] = None):
        """Record transaction in shared state"""
        tx_record = {
            "tx_hash": tx_hash,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "amount": amount,
            "num_outputs": num_outputs,
            "amount_per_output": amount_per_output if amount_per_output is not None else amount,
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