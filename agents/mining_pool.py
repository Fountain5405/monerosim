#!/usr/bin/env python3
"""
Mining Pool Agent for Monerosim

Represents a mining pool that:
- Participates in coordinated mining
- Responds to mining signals from block controller
- Tracks mining statistics
"""

import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from .base_agent import BaseAgent
from .monero_rpc import RPCError


class MiningPoolAgent(BaseAgent):
    """Agent representing a mining pool"""
    
    def __init__(self, agent_id: str, node_rpc_port: int,
                 wallet_rpc_port: Optional[int] = None,
                 mining_threads: int = 1, rpc_host: str = "127.0.0.1"):
        super().__init__(agent_id, node_rpc_port, wallet_rpc_port, rpc_host)
        
        # Mining configuration
        self.mining_threads = mining_threads
        self.mining_address: Optional[str] = None
        
        # State
        self.is_mining = False
        self.blocks_found = 0
        self.last_height = 0
        self.mining_start_time: Optional[float] = None
        self.total_mining_time = 0.0
        
        # Mining coordination
        self.signal_check_interval = 1.0  # Check for signals every second
        self.last_signal_check = 0
        
    def _setup_agent(self):
        """Initialize mining pool"""
        if not self.node_rpc:
            raise RuntimeError("Mining pool requires node RPC connection")
            
        # Get or create mining address
        if self.wallet_rpc:
            # Use wallet address if available
            self._setup_wallet()
            self.mining_address = self.wallet_rpc.get_address()
        else:
            # Use a fixed address for mining (in real scenario, this would be pool's address)
            self.mining_address = self._get_pool_address()
            
        self.logger.info(f"Mining pool address: {self.mining_address}")
        
        # Register as mining pool
        self._register_mining_pool()
        
        # Check initial mining status
        self._check_mining_status()
        
    def _setup_wallet(self):
        """Create or open mining pool wallet"""
        wallet_name = f"pool_{self.agent_id}"
        
        try:
            self.wallet_rpc.open_wallet(wallet_name)
            self.logger.info("Opened existing wallet")
        except RPCError:
            try:
                self.wallet_rpc.create_wallet(wallet_name)
                self.logger.info("Created new wallet")
            except RPCError as e:
                self.logger.error(f"Failed to create wallet: {e}")
                raise
                
    def _get_pool_address(self) -> str:
        """Get a fixed pool address when no wallet is available"""
        # In a real implementation, this would be the pool's payout address
        # For simulation, we use a deterministic address based on pool ID
        return f"pool_{self.agent_id}_address_placeholder"
        
    def _register_mining_pool(self):
        """Register mining pool in shared state"""
        pool_data = {
            "agent_id": self.agent_id,
            "address": self.mining_address,
            "type": "mining_pool",
            "threads": self.mining_threads,
            "timestamp": time.time()
        }
        
        # Add to list of mining pools
        self.append_shared_list("mining_pools.json", pool_data)
        
        # Write individual pool file
        self.write_shared_state(f"pool_{self.agent_id}.json", pool_data)
        
        self.logger.info("Registered mining pool in shared state")
        
    def _check_mining_signal(self) -> Optional[str]:
        """Check for mining control signals"""
        signal_file = f"mining_signals/{self.agent_id}.json"
        signal_data = self.read_shared_state(signal_file)
        
        if signal_data:
            return signal_data.get("action")
        return None
        
    def _start_mining(self):
        """Start mining process"""
        if self.is_mining:
            self.logger.debug("Already mining")
            return
            
        try:
            self.logger.info(f"Starting mining with {self.mining_threads} threads")
            result = self.node_rpc.start_mining(self.mining_address, self.mining_threads)
            
            if result:
                self.is_mining = True
                self.mining_start_time = time.time()
                self.logger.info("Mining started successfully")
                
                # Update pool status
                self._update_pool_status("mining")
            else:
                self.logger.error("Failed to start mining")
                
        except RPCError as e:
            self.logger.error(f"Error starting mining: {e}")
            
    def _stop_mining(self):
        """Stop mining process"""
        if not self.is_mining:
            self.logger.debug("Not currently mining")
            return
            
        try:
            self.logger.info("Stopping mining")
            result = self.node_rpc.stop_mining()
            
            if result:
                self.is_mining = False
                if self.mining_start_time:
                    self.total_mining_time += time.time() - self.mining_start_time
                    self.mining_start_time = None
                self.logger.info("Mining stopped successfully")
                
                # Update pool status
                self._update_pool_status("idle")
            else:
                self.logger.error("Failed to stop mining")
                
        except RPCError as e:
            self.logger.error(f"Error stopping mining: {e}")
            
    def _check_mining_status(self):
        """Check current mining status and update statistics"""
        try:
            status = self.node_rpc.mining_status()
            active = status.get("active", False)
            
            # Update mining state
            if active != self.is_mining:
                self.logger.info(f"Mining status changed: {self.is_mining} -> {active}")
                self.is_mining = active
                
            # Check for new blocks
            current_height = self.node_rpc.get_height()
            if current_height > self.last_height:
                blocks_diff = current_height - self.last_height
                if self.is_mining and self.last_height > 0:
                    # Assume we found these blocks (simplified)
                    self.blocks_found += blocks_diff
                    self.logger.info(f"Found {blocks_diff} new blocks! Total: {self.blocks_found}")
                    
                    # Log block discovery
                    for i in range(blocks_diff):
                        block_data = {
                            "pool": self.agent_id,
                            "height": self.last_height + i + 1,
                            "timestamp": time.time()
                        }
                        self.append_shared_list("blocks_found.json", block_data)
                        
                self.last_height = current_height
                
            # Log current status
            if self.is_mining:
                threads = status.get("threads", 0)
                speed = status.get("speed", 0)
                self.logger.debug(f"Mining active - Threads: {threads}, Speed: {speed} H/s")
                
        except RPCError as e:
            self.logger.error(f"Failed to check mining status: {e}")
            
    def _update_pool_status(self, status: str):
        """Update pool status in shared state"""
        status_data = {
            "agent_id": self.agent_id,
            "status": status,
            "is_mining": self.is_mining,
            "blocks_found": self.blocks_found,
            "total_mining_time": self.total_mining_time,
            "current_height": self.last_height,
            "timestamp": time.time()
        }
        
        self.write_shared_state(f"pool_{self.agent_id}_status.json", status_data)
        
    def _update_statistics(self):
        """Update and log mining pool statistics"""
        # Calculate effective mining time
        effective_time = self.total_mining_time
        if self.is_mining and self.mining_start_time:
            effective_time += time.time() - self.mining_start_time
            
        stats = {
            "pool_id": self.agent_id,
            "blocks_found": self.blocks_found,
            "total_mining_time": effective_time,
            "current_height": self.last_height,
            "is_mining": self.is_mining,
            "mining_threads": self.mining_threads,
            "timestamp": time.time()
        }
        
        # Write statistics
        self.write_shared_state(f"pool_{self.agent_id}_stats.json", stats)
        
        # Calculate blocks per hour if we've been mining
        if effective_time > 0:
            blocks_per_hour = (self.blocks_found / effective_time) * 3600
            self.logger.info(
                f"Pool stats - Blocks found: {self.blocks_found}, "
                f"Mining time: {effective_time:.1f}s, "
                f"Rate: {blocks_per_hour:.2f} blocks/hour"
            )
        else:
            self.logger.info(f"Pool stats - Blocks found: {self.blocks_found}")
            
    def run_iteration(self):
        """Single iteration of mining pool behavior"""
        current_time = time.time()
        
        # Check for mining control signals
        if current_time - self.last_signal_check >= self.signal_check_interval:
            signal = self._check_mining_signal()
            if signal == "start" and not self.is_mining:
                self._start_mining()
            elif signal == "stop" and self.is_mining:
                self._stop_mining()
            self.last_signal_check = current_time
            
        # Periodically check mining status
        if current_time % 5 < 0.1:  # Every 5 seconds
            self._check_mining_status()
            
        # Update statistics every 30 seconds
        if current_time % 30 < 0.1:
            self._update_statistics()
            
        # Small sleep to prevent tight loops
        time.sleep(0.1)
        
    def _cleanup_agent(self):
        """Clean up mining pool resources"""
        # Stop mining if active
        if self.is_mining:
            self._stop_mining()
            
        # Final statistics update
        self._update_statistics()
        
        # Write final summary
        summary = {
            "pool_id": self.agent_id,
            "total_blocks_found": self.blocks_found,
            "total_mining_time": self.total_mining_time,
            "final_height": self.last_height,
            "final_timestamp": time.time()
        }
        
        try:
            self.write_shared_state(f"pool_{self.agent_id}_final.json", summary)
            self.logger.info(
                f"Final summary - Found {self.blocks_found} blocks in "
                f"{self.total_mining_time:.1f} seconds of mining"
            )
        except:
            pass


def main():
    """Main entry point for mining pool agent"""
    parser = MiningPoolAgent.create_argument_parser("Mining Pool Agent for Monerosim")
    parser.add_argument('--mining-threads', type=int, default=1,
                       help='Number of mining threads')
    
    args = parser.parse_args()
    
    # Set logging level
    import logging
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent
    agent = MiningPoolAgent(
        agent_id=args.id,
        node_rpc_port=args.node_rpc,
        wallet_rpc_port=args.wallet_rpc,
        mining_threads=args.mining_threads,
        rpc_host=args.rpc_host
    )
    
    agent.run()


if __name__ == "__main__":
    main()