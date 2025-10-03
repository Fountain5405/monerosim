#!/usr/bin/env python3
"""
Agent-based Block Controller for Monerosim

This stateless coordinator:
- Reads the miner registry from miners.json to find available miners
- Selects a miner using weighted-random selection
- Makes dynamic RPC calls to generate blocks on the winner's daemon
- Does not maintain any local state or wallet
"""

import sys
import time
import argparse
import logging
import random
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Try to import numpy, but handle the case where it's not available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    import warnings
    warnings.warn("NumPy not available, using fallback weighted selection method")

from .base_agent import BaseAgent
from .monero_rpc import MoneroRPC, WalletRPC, RPCError


class BlockControllerAgent(BaseAgent):
    """Stateless coordinator that selects miners and triggers block generation"""
    
    def __init__(self, agent_id: str = "block_controller",
                 target_block_interval: int = 120,
                 blocks_per_generation: int = 1,
                 **kwargs):
        # Call parent constructor without wallet parameters
        super().__init__(
            agent_id=agent_id,
            **kwargs
        )
        
        # Configuration
        self.target_block_interval = target_block_interval
        self.blocks_per_generation = blocks_per_generation
        
        # Timing
        self.last_block_time = 0
        self.start_time = time.time()
        
    def _setup_agent(self):
        """Initialize stateless block controller"""
        self.logger.info("Block Controller initializing...")

        # Register as block controller (without wallet)
        controller_data = {
            "agent_id": self.agent_id,
            "type": "block_controller",
            "target_interval": self.target_block_interval,
            "blocks_per_generation": self.blocks_per_generation,
            "timestamp": time.time()
        }
        self.write_shared_state("block_controller.json", controller_data)

        self.logger.info("Stateless block controller initialized")

        # Wait for wallets to fully start up before attempting connections
        self.logger.info("Waiting 60 seconds for wallet services to fully initialize...")
        time.sleep(60)

        # Initialize all agent wallets and update the agent registry
        self._initialize_all_agent_wallets()
            
    def _initialize_all_agent_wallets(self):
        """
        Iterate through all agents in the registry, initialize their wallets,
        and update the registry with their wallet addresses.
        Includes retry logic for failed wallet initializations.
        """
        self.logger.info("Starting centralized wallet initialization for all agents...")
        agent_registry_path = self.shared_dir / "agent_registry.json"
        if not agent_registry_path.exists():
            self.logger.error(f"Agent registry not found at {agent_registry_path}")
            return

        try:
            with open(agent_registry_path, 'r') as f:
                agent_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load agent_registry.json: {e}")
            return

        # Separate miners from regular agents - miners are critical and need retry logic
        miners = []
        regular_agents = []

        for agent in agent_data.get("agents", []):
            if agent.get("attributes", {}).get("is_miner") == "true":
                miners.append(agent)
            else:
                regular_agents.append(agent)

        self.logger.info(f"Found {len(miners)} miners and {len(regular_agents)} regular agents to initialize")

        # Process miners first with retry logic
        updated_miners = self._initialize_agent_wallets_with_retry(miners, max_retries=5, retry_delay=30)

        # Process regular agents (less critical, single attempt)
        updated_regular = []
        for agent in regular_agents:
            # Only process agents that have a wallet
            if "wallet_rpc_port" not in agent:
                updated_regular.append(agent)
                continue

            wallet_rpc_port = agent["wallet_rpc_port"]
            ip_addr = agent["ip_addr"]
            agent_id = agent["id"]

            try:
                wallet_rpc = WalletRPC(ip_addr, wallet_rpc_port)
                # Increase timeout for wallet readiness check
                wallet_rpc.wait_until_ready(max_wait=180)

                wallet_name = f"{agent_id}_wallet"
                address = None

                try:
                    self.logger.info(f"Attempting to open wallet '{wallet_name}' for agent {agent_id}")
                    wallet_rpc.open_wallet(wallet_name, password="")
                    address = wallet_rpc.get_address()
                    self.logger.info(f"Successfully opened existing wallet '{wallet_name}' for {agent_id}")
                except RPCError:
                    try:
                        self.logger.info(f"Wallet not found, creating '{wallet_name}' for agent {agent_id}")
                        wallet_rpc.create_wallet(wallet_name, password="")
                        address = wallet_rpc.get_address()
                        self.logger.info(f"Successfully created new wallet '{wallet_name}' for {agent_id}")
                    except RPCError as create_err:
                        self.logger.error(f"Failed to create wallet for {agent_id}: {create_err}")
                        updated_regular.append(agent)
                        continue

                if address:
                    self.logger.debug(f"Address type: {type(address)}, value: {address}")
                    agent.update({"wallet_address": address})
                    self.logger.info(f"Updated agent {agent_id} with wallet address.")

            except Exception as e:
                self.logger.error(f"Error processing wallet for agent {agent_id}: {e}")
                updated_regular.append(agent)
            else:
                updated_regular.append(agent)

            # Small delay between agents to avoid overwhelming the system
            time.sleep(2)

        # Combine updated agents
        updated_agents = updated_miners + updated_regular

        # Write the updated agent data back to the registry
        try:
            with open(agent_registry_path, 'w') as f:
                json.dump({"agents": updated_agents}, f, indent=2)
            self.logger.info("Successfully updated agent_registry.json with all wallet addresses.")
        except Exception as e:
            self.logger.error(f"Failed to write updated agent_registry.json: {e}")

    def _initialize_agent_wallets_with_retry(self, agents, max_retries=5, retry_delay=60):
        """
        Initialize wallets for a list of agents with retry logic.
        Critical for miners to ensure they get wallet addresses.
        """
        self.logger.info(f"Initializing wallets for {len(agents)} agents with retry logic (max_retries={max_retries})")

        remaining_agents = agents.copy()
        updated_agents = []

        for attempt in range(max_retries):
            if not remaining_agents:
                break

            self.logger.info(f"Retry attempt {attempt + 1}/{max_retries} for {len(remaining_agents)} remaining agents")

            still_remaining = []

            for agent in remaining_agents:
                wallet_rpc_port = agent["wallet_rpc_port"]
                ip_addr = agent["ip_addr"]
                agent_id = agent["id"]

                try:
                    wallet_rpc = WalletRPC(ip_addr, wallet_rpc_port)
                    # Increase timeout for wallet readiness check
                    wallet_rpc.wait_until_ready(max_wait=180)

                    wallet_name = f"{agent_id}_wallet"
                    
                    if wallet_rpc.ensure_wallet_exists(wallet_name):
                        address = wallet_rpc.get_address()
                        self.logger.info(f"Successfully ensured wallet '{wallet_name}' exists for {agent_id}")
                    else:
                        self.logger.warning(f"Failed to ensure wallet exists for {agent_id}")
                        still_remaining.append(agent)
                        continue

                    if address:
                        self.logger.debug(f"Address type: {type(address)}, value: {address}")
                        agent.update({"wallet_address": address})
                        self.logger.info(f"Updated agent {agent_id} with wallet address.")

                        # Update miners.json with wallet address if this agent is a miner
                        if agent.get("attributes", {}).get("is_miner") == "true":
                            self._update_miner_wallet_address(agent_id, address)

                        updated_agents.append(agent)
                    else:
                        still_remaining.append(agent)

                except Exception as e:
                    self.logger.warning(f"Error processing wallet for agent {agent_id} (attempt {attempt + 1}): {e}")
                    still_remaining.append(agent)

            remaining_agents = still_remaining

            # Wait before next retry attempt (except on the last attempt)
            if remaining_agents and attempt < max_retries - 1:
                self.logger.info(f"Waiting {retry_delay} seconds before next retry attempt...")
                time.sleep(retry_delay)

        if remaining_agents:
            self.logger.error(f"Failed to initialize wallets for {len(remaining_agents)} agents after {max_retries} attempts: {[a['id'] for a in remaining_agents]}")
            # Add failed agents back to updated list without wallet addresses
            updated_agents.extend(remaining_agents)

        return updated_agents

    def _update_miner_wallet_address(self, agent_id: str, wallet_address: str):
        """
        Update the miners.json file with the wallet address for a specific miner.
        """
        miners_registry_path = self.shared_dir / "miners.json"

        if not miners_registry_path.exists():
            self.logger.error(f"Miners registry file not found")
            return

        try:
            with open(miners_registry_path, 'r') as f:
                miner_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load miners.json: {e}")
            return

        # Find and update the miner with matching agent_id
        updated = False
        for miner in miner_data.get("miners", []):
            if miner["agent_id"] == agent_id:
                miner["wallet_address"] = wallet_address
                updated = True
                self.logger.info(f"Updated miners.json for {agent_id} with wallet address.")
                break

        if updated:
            try:
                with open(miners_registry_path, 'w') as f:
                    json.dump(miner_data, f, indent=2)
            except Exception as e:
                self.logger.error(f"Failed to write updated miners.json: {e}")
        else:
            self.logger.warning(f"Miner {agent_id} not found in miners.json to update wallet address.")

    def _load_miner_registry(self) -> List[Dict[str, Any]]:
        """
        Load miner information from miners.json and enrich with wallet addresses
        from the agent_registry.json.
        """
        if not self.shared_dir:
            self.logger.error("Shared directory not configured, cannot load miner registry.")
            return []

        miners_registry_path = self.shared_dir / "miners.json"
        agent_registry_path = self.shared_dir / "agent_registry.json"

        if not miners_registry_path.exists() or not agent_registry_path.exists():
            self.logger.error("Miner or agent registry not found.")
            return []

        try:
            with open(miners_registry_path, 'r') as f:
                miner_data = json.load(f)
            with open(agent_registry_path, 'r') as f:
                agent_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load registry files: {e}")
            return []

        # Create lookup for wallet addresses from the agent registry
        agent_wallets = {agent["id"]: agent.get("wallet_address") for agent in agent_data.get("agents", [])}

        enriched_miners = []
        for miner in miner_data.get("miners", []):
            agent_id = miner["agent_id"]

            # Enrich with wallet address
            if agent_id in agent_wallets and agent_wallets[agent_id] is not None:
                miner["wallet_address"] = agent_wallets[agent_id]
                enriched_miners.append(miner)
            else:
                self.logger.warning(f"Wallet address not found for miner {agent_id} in agent registry.")

        if not enriched_miners:
            self.logger.warning("No miners successfully enriched with wallet addresses.")
        else:
            self.logger.info(f"Successfully loaded and enriched {len(enriched_miners)} miners.")

        return enriched_miners

    def _select_winning_miner(self, miners: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select a winning miner based on hashrate using weighted selection."""
        if not miners:
            self.logger.warning("No miners in registry, cannot select a winner.")
            return None
        
        # Extract weights for each miner (using 'weight' field from miners.json)
        weights = [miner.get("weight", 0) for miner in miners]
        total_weight = sum(weights)

        if total_weight == 0:
            self.logger.warning("Total weight of all miners is zero. Falling back to random choice.")
            return random.choice(miners)

        # Use numpy for weighted random selection if available
        if NUMPY_AVAILABLE:
            normalized_weights = np.array(weights, dtype=float) / total_weight
            winner_index = np.random.choice(len(miners), p=normalized_weights)
        else:
            # Fallback implementation using built-in random module
            # Create a cumulative distribution
            cumulative_weights = []
            cumulative_sum = 0
            for weight in weights:
                cumulative_sum += weight
                cumulative_weights.append(cumulative_sum)
            
            # Select a random value and find the corresponding miner
            random_value = random.uniform(0, total_weight)
            winner_index = 0
            for i, cumulative_weight in enumerate(cumulative_weights):
                if random_value <= cumulative_weight:
                    winner_index = i
                    break
        
        winner = miners[winner_index]
        
        self.logger.info(f"Selected winning miner with IP {winner.get('ip_addr')} with weight {winner.get('weight')}")
        return winner
        
    def _generate_blocks(self) -> bool:
        """Select a winner and generate blocks on their daemon."""
        # Reload the registry each time to get the latest list of miners
        miners = self._load_miner_registry()

        winner = self._select_winning_miner(miners)
        if not winner:
            self.logger.error("Block generation failed: Could not select a winning miner.")
            return False

        # Get wallet address from the agent registry
        winner_address = winner.get("wallet_address")

        # Create dynamic RPC client for the winner's daemon
        winner_ip = winner.get("ip_addr", "127.0.0.1")
        winner_agent_id = winner.get("agent_id")
        
        # Use standard RPC port 28081 for all nodes
        winner_port = 28081
        
        self.logger.info(f"Using standard RPC port {winner_port} for agent {winner_agent_id} at {winner_ip}")
        
        # Create RPC client with improved error handling
        try:
            winner_daemon_rpc = MoneroRPC(winner_ip, winner_port)
        except Exception as e:
            self.logger.error(f"Failed to create RPC client for {winner_ip}:{winner_port}: {e}", exc_info=True)
            return False
        
        self.logger.info(f"Generating {self.blocks_per_generation} block(s) for winner agent at {winner_ip}:{winner_port}")
        
        try:
            result = winner_daemon_rpc.ensure_mining(
                wallet_address=winner_address
            )
            
            if result and result.get("status") == "OK":
                # The actual block hashes are in the "result" field of the response
                # Different methods return different response formats
                method_used = result.get("method", "unknown")
                inner_result = result.get("result", {})
                
                # Extract blocks based on the method used
                blocks = []
                if method_used == "generateblocks":
                    # generateblocks returns blocks directly in the result
                    blocks = inner_result.get("blocks", [])
                elif method_used == "start_mining":
                    # start_mining doesn't return block hashes directly
                    # We'll count it as 1 block generated for logging purposes
                    blocks = ["mining_started"]
                else:
                    self.logger.warning(f"Unknown mining method used: {method_used}")
                
                blocks_generated = len(blocks)
                self.logger.info(f"Successfully generated {blocks_generated} blocks using {method_used} method")
                
                # Log block discovery (only for actual block hashes)
                if method_used == "generateblocks":
                    for block_hash in blocks:
                        block_info = {
                            "miner_ip": winner_ip,
                            "block_hash": block_hash,
                            "timestamp": time.time()
                        }
                        self.append_shared_list("blocks_found.json", block_info)

                self.last_block_time = time.time()
                return True
            else:
                self.logger.warning(f"Unexpected mining response: {result}")
                return False
                
        except RPCError as e:
            self.logger.error(f"Failed to generate blocks on winner agent's daemon at {winner_ip}:{winner_port}: {e}")
            # Log more details about the connection
            self.logger.error(f"Connection details: IP={winner_ip}, Port={winner_port}, Agent={winner.get('agent_id')}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error generating blocks: {e}", exc_info=True)
            self.logger.error(f"Connection details: IP={winner_ip}, Port={winner_port}, Agent={winner.get('agent_id')}")
            return False
            
    def _update_statistics(self):
        """Update and log block controller statistics"""
        stats = {
            "controller_id": self.agent_id,
            "last_block_time": self.last_block_time,
            "timestamp": time.time()
        }
        
        self.write_shared_state("block_controller_stats.json", stats)
                
    def run_iteration(self) -> float:
        """
        Single iteration of block generation.
        Returns:
            float: Recommended sleep time in seconds.
        """
        current_time = time.time()
        time_since_last_block = current_time - self.last_block_time

        if time_since_last_block >= self.target_block_interval:
            self.logger.info(f"Time to generate blocks (last block {time_since_last_block:.1f}s ago)")
            if self._generate_blocks():
                self._update_statistics()
            else:
                self.logger.warning("Block generation failed, will retry next interval")
            
            # After generation, check again in the target interval
            return self.target_block_interval
        else:
            # Calculate time until next block generation
            return self.target_block_interval - time_since_last_block
        
    def _cleanup_agent(self):
        """Clean up block controller resources"""
        # Final statistics
        self._update_statistics()
        
        # Write final summary
        summary = {
            "controller_id": self.agent_id,
            "runtime_seconds": time.time() - self.start_time,
            "final_timestamp": time.time()
        }
        
        try:
            self.write_shared_state("block_controller_final.json", summary)
            self.logger.info("Final summary written")
        except:
            pass


def main():
    """Main entry point for block controller agent"""
    parser = BlockControllerAgent.create_argument_parser("Block Controller Agent for Monerosim")
    parser.add_argument('--interval', type=int, default=120, help='Target interval between blocks in seconds')
    parser.add_argument('--blocks', type=int, default=1, help='Number of blocks per generation')
    
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent (without wallet parameters)
    agent = BlockControllerAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes,
        target_block_interval=args.interval,
        blocks_per_generation=args.blocks
    )
    
    agent.run()


if __name__ == "__main__":
    main()