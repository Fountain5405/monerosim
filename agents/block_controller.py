#!/usr/bin/env python3
"""
Agent-based Block Controller for Monerosim

Coordinates block generation across multiple mining pools by:
- Monitoring registered mining pools
- Sending mining signals to control block generation
- Ensuring consistent block production
- Tracking overall blockchain progress
"""

import sys
import time
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent
from .monero_rpc import MoneroRPC, RPCError


class BlockControllerAgent(BaseAgent):
    """Agent that coordinates mining across multiple pools"""
    
    def __init__(self, agent_id: str = "block_controller", 
                 target_block_interval: int = 120,
                 blocks_per_generation: int = 1):
        # Block controller doesn't need wallet, just monitors daemons
        super().__init__(agent_id, node_rpc_port=None, wallet_rpc_port=None)
        
        # Configuration
        self.target_block_interval = target_block_interval  # Target seconds between blocks
        self.blocks_per_generation = blocks_per_generation  # Blocks per mining round
        
        # State
        self.mining_pools: List[Dict[str, Any]] = []
        self.active_pool_index = 0
        self.last_block_time = 0
        self.total_blocks_generated = 0
        self.blockchain_height = 0
        
        # Monitoring connections to different nodes
        self.node_connections: Dict[str, MoneroRPC] = {}
        
    def _setup_agent(self):
        """Initialize block controller"""
        self.logger.info("Block Controller initializing...")
        
        # Create mining signals directory
        signals_dir = self.shared_dir / "mining_signals"
        signals_dir.mkdir(exist_ok=True)
        
        # Register as block controller
        controller_data = {
            "agent_id": self.agent_id,
            "type": "block_controller",
            "target_interval": self.target_block_interval,
            "blocks_per_generation": self.blocks_per_generation,
            "timestamp": time.time()
        }
        self.write_shared_state("block_controller.json", controller_data)
        
        # Wait a bit for pools to register
        self.logger.info("Waiting for mining pools to register...")
        time.sleep(10)
        
        # Load initial mining pools
        self._update_mining_pools()
        
    def _update_mining_pools(self):
        """Update list of available mining pools"""
        pools = self.read_shared_list("mining_pools.json")
        if pools:
            self.mining_pools = pools
            self.logger.info(f"Found {len(pools)} mining pools: {[p['agent_id'] for p in pools]}")
            
            # Try to connect to each pool's node
            for pool in pools:
                pool_id = pool['agent_id']
                if pool_id not in self.node_connections:
                    # Derive node RPC port from pool data or use defaults
                    # In a real implementation, this would be in the pool registration
                    if pool_id == "pool_alpha":
                        node_port = 28090  # A0's RPC port
                        node_ip = "11.0.0.1"
                    elif pool_id == "pool_beta":
                        node_port = 28090  # Could be different node
                        node_ip = "11.0.0.2"
                    else:
                        continue
                        
                    try:
                        rpc = MoneroRPC(node_ip, node_port)
                        if rpc.is_ready():
                            self.node_connections[pool_id] = rpc
                            self.logger.info(f"Connected to node for pool {pool_id}")
                    except Exception as e:
                        self.logger.warning(f"Failed to connect to node for pool {pool_id}: {e}")
        else:
            self.logger.warning("No mining pools found")
            
    def _send_mining_signal(self, pool_id: str, action: str):
        """Send mining control signal to a specific pool"""
        signal_data = {
            "action": action,
            "timestamp": time.time(),
            "controller": self.agent_id
        }
        
        signal_file = f"mining_signals/{pool_id}.json"
        self.write_shared_state(signal_file, signal_data)
        self.logger.info(f"Sent '{action}' signal to pool {pool_id}")
        
    def _stop_all_mining(self):
        """Send stop signal to all mining pools"""
        for pool in self.mining_pools:
            self._send_mining_signal(pool['agent_id'], "stop")
            
    def _get_blockchain_height(self) -> int:
        """Get current blockchain height from any available node"""
        for pool_id, rpc in self.node_connections.items():
            try:
                height = rpc.get_height()
                return height
            except RPCError:
                continue
        return 0
        
    def _coordinate_mining_round(self):
        """Coordinate a single round of mining"""
        if not self.mining_pools:
            self.logger.warning("No mining pools available")
            return
            
        # Update blockchain height
        current_height = self._get_blockchain_height()
        if current_height > self.blockchain_height:
            blocks_added = current_height - self.blockchain_height
            self.total_blocks_generated += blocks_added
            self.logger.info(f"Blockchain grew by {blocks_added} blocks to height {current_height}")
            self.blockchain_height = current_height
            
        # Check if it's time for new blocks
        current_time = time.time()
        time_since_last_block = current_time - self.last_block_time
        
        if time_since_last_block >= self.target_block_interval:
            # Stop all mining first
            self._stop_all_mining()
            time.sleep(2)  # Give pools time to stop
            
            # Select next pool (round-robin)
            selected_pool = self.mining_pools[self.active_pool_index]
            pool_id = selected_pool['agent_id']
            
            self.logger.info(f"Starting mining round with pool {pool_id}")
            self.logger.info(f"Target: {self.blocks_per_generation} blocks")
            
            # Send start signal
            self._send_mining_signal(pool_id, "start")
            
            # Wait for blocks to be generated
            # In agent architecture, we don't use generateblocks RPC
            # Instead, we let the pool mine naturally
            start_height = self.blockchain_height
            mining_timeout = 60  # Maximum time to wait for blocks
            mining_start = time.time()
            
            while time.time() - mining_start < mining_timeout:
                current_height = self._get_blockchain_height()
                if current_height >= start_height + self.blocks_per_generation:
                    self.logger.info(f"Mining target reached! New height: {current_height}")
                    break
                time.sleep(1)
                
            # Stop mining
            self._send_mining_signal(pool_id, "stop")
            
            # Update state
            self.last_block_time = current_time
            self.active_pool_index = (self.active_pool_index + 1) % len(self.mining_pools)
            
            # Log statistics
            self._update_statistics()
            
    def _update_statistics(self):
        """Update and log block controller statistics"""
        stats = {
            "controller_id": self.agent_id,
            "total_blocks_generated": self.total_blocks_generated,
            "current_height": self.blockchain_height,
            "active_pools": len(self.mining_pools),
            "last_block_time": self.last_block_time,
            "timestamp": time.time()
        }
        
        self.write_shared_state("block_controller_stats.json", stats)
        
        # Calculate block rate
        runtime = time.time() - self.last_block_time
        if runtime > 0 and self.total_blocks_generated > 0:
            blocks_per_hour = (self.total_blocks_generated / runtime) * 3600
            self.logger.info(
                f"Controller stats - Total blocks: {self.total_blocks_generated}, "
                f"Height: {self.blockchain_height}, "
                f"Rate: {blocks_per_hour:.2f} blocks/hour"
            )
            
    def run_iteration(self):
        """Single iteration of block controller behavior"""
        # Periodically update pool list
        if int(time.time()) % 30 == 0:
            self._update_mining_pools()
            
        # Coordinate mining
        self._coordinate_mining_round()
        
        # Small sleep to prevent tight loops
        time.sleep(1)
        
    def _cleanup_agent(self):
        """Clean up block controller resources"""
        # Stop all mining before shutdown
        self._stop_all_mining()
        
        # Final statistics
        self._update_statistics()
        
        # Write final summary
        summary = {
            "controller_id": self.agent_id,
            "total_blocks_coordinated": self.total_blocks_generated,
            "final_height": self.blockchain_height,
            "pools_managed": len(self.mining_pools),
            "final_timestamp": time.time()
        }
        
        try:
            self.write_shared_state("block_controller_final.json", summary)
            self.logger.info(
                f"Final summary - Coordinated {self.total_blocks_generated} blocks "
                f"across {len(self.mining_pools)} pools"
            )
        except:
            pass


def main():
    """Main entry point for block controller agent"""
    import argparse
    import logging
    
    parser = argparse.ArgumentParser(description="Block Controller Agent for Monerosim")
    parser.add_argument('--id', default='block_controller', help='Agent ID')
    parser.add_argument('--interval', type=int, default=120,
                       help='Target interval between blocks in seconds')
    parser.add_argument('--blocks', type=int, default=1,
                       help='Number of blocks per generation')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent
    agent = BlockControllerAgent(
        agent_id=args.id,
        target_block_interval=args.interval,
        blocks_per_generation=args.blocks
    )
    
    agent.run()


if __name__ == "__main__":
    main()