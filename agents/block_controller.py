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
            
    def _load_miner_registry(self) -> List[Dict[str, Any]]:
        """
        Load miner information from the miners.json file.
        """
        if not self.shared_dir:
            self.logger.error("Shared directory not configured, cannot load miner registry.")
            return []

        miners_registry_path = self.shared_dir / "miners.json"
        if not miners_registry_path.exists():
            self.logger.error(f"Miners registry not found at {miners_registry_path}")
            return []

        try:
            with open(miners_registry_path, 'r') as f:
                miner_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load miners.json: {e}")
            return []

        miners = []
        for miner in miner_data.get("miners", []):
            # Get wallet RPC port (standard port 28082 for all agents)
            wallet_rpc_port = 28082
            
            try:
                wallet_rpc = WalletRPC(miner["ip_addr"], wallet_rpc_port)
                wallet_rpc.wait_until_ready()
                
                # Try to create wallet first, then get address
                # Extract agent ID from IP address (e.g., 11.0.0.10 -> user000)
                ip_parts = miner["ip_addr"].split('.')
                if len(ip_parts) == 4:
                    agent_index = int(ip_parts[3]) - 10
                    agent_id = f"user{agent_index:03d}"
                else:
                    agent_id = "unknown"
                
                wallet_name = f"{agent_id}_wallet"
                address = None
                
                # First try to open existing wallet
                try:
                    self.logger.info(f"Attempting to open wallet '{wallet_name}' for miner at {miner['ip_addr']}")
                    wallet_rpc.open_wallet(wallet_name, password="")
                    # If open succeeds, get the address
                    address = wallet_rpc.get_address()
                    self.logger.info(f"Successfully opened existing wallet '{wallet_name}'")
                except RPCError as open_err:
                    # If wallet doesn't exist or can't be opened, try to create it
                    if "Wallet not found" in str(open_err) or "Failed to open wallet" in str(open_err):
                        try:
                            self.logger.info(f"Wallet doesn't exist, creating '{wallet_name}'")
                            wallet_rpc.create_wallet(wallet_name, password="")
                            # If creation succeeds, get the address
                            address = wallet_rpc.get_address()
                            self.logger.info(f"Successfully created new wallet '{wallet_name}'")
                        except RPCError as create_err:
                            self.logger.error(f"Failed to create wallet: {create_err}")
                            # Last attempt - maybe wallet is already loaded
                            try:
                                self.logger.warning("Attempting to get address from current wallet")
                                address = wallet_rpc.get_address()
                            except RPCError as addr_err:
                                self.logger.error(f"Failed to get address: {addr_err}")
                                continue  # Skip this miner
                    else:
                        # Some other error opening wallet, try to get address anyway
                        self.logger.warning(f"Error opening wallet: {open_err}, trying to get address from current wallet")
                        try:
                            address = wallet_rpc.get_address()
                        except RPCError as addr_err:
                            self.logger.error(f"Failed to get address: {addr_err}")
                            continue  # Skip this miner
                
                if address:
                    miner["wallet_address"] = address
                    miner["agent_id"] = agent_id
                    miners.append(miner)
                    self.logger.info(f"Successfully added miner {agent_id} with address {address[:12]}...")
                else:
                    self.logger.warning(f"No address obtained for miner at {miner['ip_addr']}, skipping")
                
            except RPCError as e:
                self.logger.error(f"Failed to setup miner at {miner['ip_addr']}: {e}")
                continue  # Skip this miner and continue with the next one
            except Exception as e:
                self.logger.error(f"Unexpected error for miner at {miner['ip_addr']}: {e}")
                continue  # Skip this miner and continue with the next one

        if not miners:
            self.logger.warning("No miners found in registry.")
        else:
            self.logger.info(f"Loaded {len(miners)} miners from {miners_registry_path}.")

        return miners

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
        
        # Get winner IP address
        winner_agent_id = winner.get("agent_id")
        winner_ip = winner.get("ip_addr", "127.0.0.1")
        
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
            result = winner_daemon_rpc.generate_block(
                wallet_address=winner_address,
                amount_of_blocks=self.blocks_per_generation
            )
            
            if result and result.get("status") == "OK":
                blocks_generated = len(result.get("blocks", []))
                self.logger.info(f"Successfully generated {blocks_generated} blocks")
                
                # Log block discovery
                for block_hash in result.get("blocks", []):
                    block_info = {
                        "miner_ip": winner_ip,
                        "block_hash": block_hash,
                        "timestamp": time.time()
                    }
                    self.append_shared_list("blocks_found.json", block_info)

                self.last_block_time = time.time()
                return True
            else:
                self.logger.warning(f"Unexpected generateblocks response: {result}")
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