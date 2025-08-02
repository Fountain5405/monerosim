#!/usr/bin/env python3
"""
Agent-based Block Controller for Monerosim

This stateless coordinator:
- Reads the node registry to find available miners
- Selects a miner using weighted-random selection
- Makes dynamic RPC calls to generate blocks on the winner's daemon
- Does not maintain any local state or wallet
"""

import sys
import time
import argparse
import logging
import random
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
        """Load miner information from the shared state file."""
        self.logger.info("Loading miner registry from node_registry.json...")
        registry_data = self.read_shared_state("node_registry.json")
        all_agents = registry_data.get("agents", []) if registry_data else []
        
        # Filter for agents with the 'mining' attribute
        miners = [
            agent for agent in all_agents
            if "mining" in agent.get("attributes", []) and agent.get("wallet_address")
        ]
        
        if not miners:
            self.logger.warning("No mining-enabled agents found in the registry.")
        else:
            self.logger.info(f"Loaded {len(miners)} mining-enabled agents from registry.")
            
        return miners

    def _select_winning_miner(self, miners: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select a winning miner based on hashrate using weighted selection."""
        if not miners:
            self.logger.warning("No miners in registry, cannot select a winner.")
            return None
        
        # Extract weights for each miner
        weights = [miner.get("hash_rate", 0) for miner in miners]
        total_weight = sum(weights)

        if total_weight == 0:
            self.logger.warning("Total hash rate of all miners is zero. Falling back to random choice.")
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
        
        self.logger.info(f"Selected winning miner: {winner.get('agent_id')} with hash rate {winner.get('hash_rate')}")
        return winner
        
    def _generate_blocks(self) -> bool:
        """Select a winner and generate blocks on their daemon."""
        # Reload the registry each time to get the latest list of miners
        miners = self._load_miner_registry()

        winner = self._select_winning_miner(miners)
        if not winner:
            self.logger.error("Block generation failed: Could not select a winning miner.")
            return False

        winner_address = winner.get("wallet_address")
        if not winner_address:
            self.logger.error(f"Block generation failed: Winning miner {winner.get('agent_id')} has no wallet_address.")
            return False
            
        # Create dynamic RPC client for the winner's daemon
        winner_ip = winner.get("ip_addr", "127.0.0.1")
        winner_port = winner.get("node_rpc_port", 28080)  # Default port if not specified
        winner_daemon_rpc = MoneroRPC(winner_ip, winner_port)
        
        self.logger.info(f"Generating {self.blocks_per_generation} block(s) for winner: {winner.get('agent_id')} at {winner_ip}:{winner_port}")
        
        try:
            result = winner_daemon_rpc.generate_block(
                wallet_address=winner_address,
                amount_of_blocks=self.blocks_per_generation
            )
            
            if result and result.get("status") == "OK":
                blocks_generated = len(result.get("blocks", []))
                self.logger.info(f"Successfully generated {blocks_generated} blocks for {winner.get('agent_id')}")
                
                # Log block discovery
                for block_hash in result.get("blocks", []):
                    block_info = {
                        "miner_id": winner.get("agent_id"),
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
            self.logger.error(f"Failed to generate blocks on winner's daemon: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error generating blocks: {e}", exc_info=True)
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