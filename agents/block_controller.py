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

        # Wait for miners to register their wallet addresses in shared state
        self._wait_for_miner_wallet_registration()
            
    def _wait_for_miner_wallet_registration(self):
        """
        Wait for miners to register their wallet addresses in shared state.
        This method replaces the centralized wallet initialization approach
        with a decentralized waiting mechanism.
        """
        self.logger.info("Waiting for miners to register their wallet addresses...")
        
        # Get the list of expected miners from miners.json
        miners_registry_path = self.shared_dir / "miners.json"
        if not miners_registry_path.exists():
            self.logger.error("Miners registry file not found, cannot wait for wallet registration")
            return
            
        try:
            with open(miners_registry_path, 'r') as f:
                miner_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load miners.json: {e}")
            return
            
        expected_miners = set(miner["agent_id"] for miner in miner_data.get("miners", []))
        self.logger.info(f"Expecting wallet registration from {len(expected_miners)} miners: {expected_miners}")
        
        # Wait for miners to register their wallets
        max_wait_time = 300  # 5 minutes maximum wait time
        check_interval = 10  # Check every 10 seconds
        start_time = time.time()
        registered_miners = set()
        
        while time.time() - start_time < max_wait_time:
            # Check for individual miner info files
            for agent_id in expected_miners:
                if agent_id not in registered_miners:
                    miner_info_file = self.shared_dir / f"{agent_id}_miner_info.json"
                    if miner_info_file.exists():
                        try:
                            with open(miner_info_file, 'r') as f:
                                miner_info = json.load(f)
                                if "wallet_address" in miner_info:
                                    registered_miners.add(agent_id)
                                    self.logger.info(f"Miner {agent_id} registered wallet address: {miner_info['wallet_address']}")
                        except Exception as e:
                            self.logger.warning(f"Error reading miner info for {agent_id}: {e}")
            
            # Check if all miners have registered
            if len(registered_miners) == len(expected_miners):
                self.logger.info("All miners have registered their wallet addresses!")
                break
                
            # Wait before next check
            time.sleep(check_interval)
            elapsed = time.time() - start_time
            self.logger.info(f"Waiting for miner wallet registration... {len(registered_miners)}/{len(expected_miners)} registered (elapsed: {elapsed:.1f}s)")
        
        # Report final status
        if len(registered_miners) < len(expected_miners):
            missing_miners = expected_miners - registered_miners
            self.logger.warning(f"Not all miners registered their wallets. Missing: {missing_miners}")
        else:
            self.logger.info("All miners successfully registered their wallet addresses!")
        
        # Update the agent registry with the collected wallet addresses
        self._update_agent_registry_with_miner_wallets(registered_miners)

    def _update_agent_registry_with_miner_wallets(self, registered_miners: set):
        """
        Update the agent registry with wallet addresses from miner info files.
        This replaces the centralized wallet initialization approach.
        """
        self.logger.info(f"Updating agent registry with wallet addresses for {len(registered_miners)} registered miners")
        
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
            
        # Update agents with wallet addresses from miner info files
        updated_agents = []
        for agent in agent_data.get("agents", []):
            agent_id = agent["id"]
            
            # If this is a registered miner, update their wallet address
            if agent_id in registered_miners:
                miner_info_file = self.shared_dir / f"{agent_id}_miner_info.json"
                if miner_info_file.exists():
                    try:
                        with open(miner_info_file, 'r') as f:
                            miner_info = json.load(f)
                            if "wallet_address" in miner_info:
                                agent["wallet_address"] = miner_info["wallet_address"]
                                self.logger.info(f"Updated agent {agent_id} with wallet address from miner info file")
                    except Exception as e:
                        self.logger.warning(f"Error reading miner info for {agent_id}: {e}")
            
            updated_agents.append(agent)
            
        # Write the updated agent data back to the registry
        try:
            with open(agent_registry_path, 'w') as f:
                json.dump({"agents": updated_agents}, f, indent=2)
            self.logger.info("Successfully updated agent_registry.json with miner wallet addresses.")
        except Exception as e:
            self.logger.error(f"Failed to write updated agent_registry.json: {e}")

    def _update_miner_wallet_address(self, agent_id: str, wallet_address: str):
        """
        Update the miners.json file with the wallet address for a specific miner.
        This method is kept for backward compatibility but is less used in the new approach.
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
        from miner info files (decentralized approach) or agent_registry.json as fallback.
        """
        if not self.shared_dir:
            self.logger.error("Shared directory not configured, cannot load miner registry.")
            return []

        miners_registry_path = self.shared_dir / "miners.json"

        if not miners_registry_path.exists():
            self.logger.error("Miner registry not found.")
            return []

        try:
            with open(miners_registry_path, 'r') as f:
                miner_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load miners.json: {e}")
            return []

        enriched_miners = []
        for miner in miner_data.get("miners", []):
            agent_id = miner["agent_id"]
            
            # First try to get wallet address from miner info file (decentralized approach)
            miner_info_file = self.shared_dir / f"{agent_id}_miner_info.json"
            wallet_address = None
            
            if miner_info_file.exists():
                try:
                    with open(miner_info_file, 'r') as f:
                        miner_info = json.load(f)
                        wallet_address = miner_info.get("wallet_address")
                        if wallet_address:
                            self.logger.debug(f"Found wallet address for {agent_id} in miner info file")
                except Exception as e:
                    self.logger.warning(f"Error reading miner info file for {agent_id}: {e}")
            
            # Fallback to agent registry if miner info file doesn't exist or doesn't have wallet address
            if not wallet_address:
                agent_registry_path = self.shared_dir / "agent_registry.json"
                if agent_registry_path.exists():
                    try:
                        with open(agent_registry_path, 'r') as f:
                            agent_data = json.load(f)
                        
                        for agent in agent_data.get("agents", []):
                            if agent["id"] == agent_id:
                                wallet_address = agent.get("wallet_address")
                                if wallet_address:
                                    self.logger.debug(f"Found wallet address for {agent_id} in agent registry")
                                break
                    except Exception as e:
                        self.logger.warning(f"Error reading agent registry for {agent_id}: {e}")
            
            # Enrich with wallet address if found
            if wallet_address:
                miner["wallet_address"] = wallet_address
                enriched_miners.append(miner)
            else:
                self.logger.warning(f"Wallet address not found for miner {agent_id} in any source.")

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