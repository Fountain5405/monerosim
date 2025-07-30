#!/usr/bin/env python3
"""
Agent-based Block Controller for Monerosim

This version uses the proven wallet-based block generation approach from scripts/block_controller.py
instead of trying to control mining pools through RPC methods that don't exist.

The block controller:
- Creates its own wallet to get a mining address
- Uses the daemon's generateblocks RPC method
- Generates blocks at regular intervals
- Tracks blockchain progress
"""

import sys
import time
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .base_agent import BaseAgent
from .monero_rpc import MoneroRPC, WalletRPC, RPCError


class BlockControllerAgent(BaseAgent):
    """Agent that generates blocks using daemon's generateblocks method"""
    
    def __init__(self, agent_id: str = "block_controller",
                 wallet_rpc_port: int = 29200,
                 wallet_host: str = "11.0.0.254",
                 daemon_host: str = "11.0.0.252",
                 daemon_rpc_port: int = 29100,
                 target_block_interval: int = 120,
                 blocks_per_generation: int = 1):
        # Initialize without wallet RPC port to prevent base class from creating connection
        super().__init__(agent_id, node_rpc_port=None, wallet_rpc_port=None)
        
        # Store wallet connection info
        self.wallet_host = wallet_host
        self.wallet_rpc_port = wallet_rpc_port
        
        # Direct daemon connection for generateblocks
        self.daemon_host = daemon_host
        self.daemon_rpc_port = daemon_rpc_port
        self.daemon_rpc = MoneroRPC(daemon_host, daemon_rpc_port)
        
        # Configuration
        self.target_block_interval = target_block_interval
        self.blocks_per_generation = blocks_per_generation
        
        # State
        self.wallet_address = None
        self.last_block_time = 0
        self.total_blocks_generated = 0
        self.blockchain_height = 0
        self.start_time = time.time()
        
    def setup(self):
        """Override setup to handle wallet RPC connection with custom host"""
        # Skip base class wallet setup, we'll do it ourselves
        # Call agent-specific setup
        self._setup_agent()
        
    def _setup_agent(self):
        """Initialize block controller with wallet"""
        self.logger.info("Block Controller initializing...")
        
        # Create wallet RPC connection with specific host
        self.logger.info(f"Connecting to wallet RPC at {self.wallet_host}:{self.wallet_rpc_port}")
        self.wallet_rpc = WalletRPC(self.wallet_host, self.wallet_rpc_port)
        
        # Wait for daemon to be ready
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                if self.daemon_rpc.is_ready():
                    self.logger.info("Daemon RPC is ready")
                    break
            except Exception as e:
                self.logger.warning(f"Daemon not ready yet (attempt {attempt + 1}/{max_attempts}): {e}")
                time.sleep(2)
        else:
            raise RuntimeError("Daemon RPC failed to become ready")
        
        # Wait for wallet RPC to be ready
        for attempt in range(max_attempts):
            try:
                if self.wallet_rpc.is_ready():
                    self.logger.info("Wallet RPC is ready")
                    break
            except Exception as e:
                self.logger.warning(f"Wallet RPC not ready yet (attempt {attempt + 1}/{max_attempts}): {e}")
                time.sleep(2)
        else:
            raise RuntimeError("Wallet RPC failed to become ready")
        
        # Create or open wallet
        wallet_name = "blockcontroller"
        wallet_password = ""
        
        try:
            # Try to create wallet
            self.logger.info(f"Creating wallet '{wallet_name}'...")
            self.wallet_rpc.create_wallet(wallet_name, wallet_password)
            self.logger.info("Successfully created new wallet")
        except RPCError as e:
            if "already exists" in str(e):
                # Wallet exists, try to open it
                self.logger.info("Wallet already exists, opening it...")
                try:
                    self.wallet_rpc.open_wallet(wallet_name, wallet_password)
                    self.logger.info("Successfully opened existing wallet")
                except RPCError as e:
                    self.logger.error(f"Failed to open wallet: {e}")
                    raise
            else:
                self.logger.error(f"Failed to create wallet: {e}")
                raise
        
        # Get wallet address
        try:
            self.wallet_address = self.wallet_rpc.get_address()
            self.logger.info(f"Using wallet address: {self.wallet_address}")
        except RPCError as e:
            self.logger.error(f"Failed to get wallet address: {e}")
            raise
        
        # Register as block controller
        controller_data = {
            "agent_id": self.agent_id,
            "type": "block_controller",
            "wallet_address": self.wallet_address,
            "target_interval": self.target_block_interval,
            "blocks_per_generation": self.blocks_per_generation,
            "daemon_host": self.daemon_host,
            "daemon_port": self.daemon_rpc_port,
            "timestamp": time.time()
        }
        self.write_shared_state("block_controller.json", controller_data)
        
        # Get initial blockchain height
        try:
            self.blockchain_height = self.daemon_rpc.get_height()
            self.logger.info(f"Initial blockchain height: {self.blockchain_height}")
        except RPCError as e:
            self.logger.warning(f"Failed to get initial height: {e}")
            
    def _generate_blocks(self):
        """Generate blocks using daemon's generateblocks RPC method"""
        try:
            # Get current height before generation
            initial_height = self.daemon_rpc.get_height()
            
            self.logger.info(f"Generating {self.blocks_per_generation} block(s)...")
            self.logger.info(f"Initial height: {initial_height}")
            
            # Call generateblocks on daemon (same as working scripts/block_controller.py)
            result = self.daemon_rpc._make_request("generateblocks", {
                "amount_of_blocks": self.blocks_per_generation,
                "wallet_address": self.wallet_address
            })
            
            if result:
                blocks_generated = len(result.get("blocks", []))
                new_height = result.get("height", initial_height)
                
                self.logger.info(f"Successfully generated {blocks_generated} blocks")
                self.logger.info(f"New height: {new_height}")
                
                self.total_blocks_generated += blocks_generated
                self.blockchain_height = new_height
                self.last_block_time = time.time()
                
                return True
            else:
                self.logger.warning(f"Unexpected generateblocks response: {result}")
                return False
                
        except RPCError as e:
            self.logger.error(f"Failed to generate blocks: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error generating blocks: {e}")
            return False
            
    def _update_statistics(self):
        """Update and log block controller statistics"""
        stats = {
            "controller_id": self.agent_id,
            "wallet_address": self.wallet_address,
            "total_blocks_generated": self.total_blocks_generated,
            "current_height": self.blockchain_height,
            "last_block_time": self.last_block_time,
            "daemon_host": self.daemon_host,
            "daemon_port": self.daemon_rpc_port,
            "timestamp": time.time()
        }
        
        self.write_shared_state("block_controller_stats.json", stats)
        
        # Calculate block rate
        if self.last_block_time > 0:
            runtime = time.time() - self.start_time
            if runtime > 0 and self.total_blocks_generated > 0:
                blocks_per_hour = (self.total_blocks_generated / runtime) * 3600
                self.logger.info(
                    f"Stats - Total blocks: {self.total_blocks_generated}, "
                    f"Height: {self.blockchain_height}, "
                    f"Rate: {blocks_per_hour:.2f} blocks/hour"
                )
                
    def run_iteration(self):
        """Single iteration of block generation"""
        current_time = time.time()
        time_since_last_block = current_time - self.last_block_time
        
        # Check if it's time to generate new blocks
        if time_since_last_block >= self.target_block_interval:
            self.logger.info(f"Time to generate blocks (last block {time_since_last_block:.1f}s ago)")
            
            if self._generate_blocks():
                self._update_statistics()
            else:
                self.logger.warning("Block generation failed, will retry next interval")
        
        # Small sleep to prevent tight loops
        time.sleep(1)
        
    def _cleanup_agent(self):
        """Clean up block controller resources"""
        # Final statistics
        self._update_statistics()
        
        # Write final summary
        summary = {
            "controller_id": self.agent_id,
            "wallet_address": self.wallet_address,
            "total_blocks_generated": self.total_blocks_generated,
            "final_height": self.blockchain_height,
            "runtime_seconds": time.time() - self.start_time,
            "final_timestamp": time.time()
        }
        
        try:
            self.write_shared_state("block_controller_final.json", summary)
            self.logger.info(
                f"Final summary - Generated {self.total_blocks_generated} blocks, "
                f"final height: {self.blockchain_height}"
            )
        except:
            pass


def main():
    """Main entry point for block controller agent"""
    parser = argparse.ArgumentParser(description="Block Controller Agent for Monerosim")
    parser.add_argument('--id', default='block_controller', help='Agent ID')
    parser.add_argument('--interval', type=int, default=120,
                       help='Target interval between blocks in seconds')
    parser.add_argument('--blocks', type=int, default=1,
                       help='Number of blocks per generation')
    parser.add_argument('--wallet-rpc', type=int, default=29200,
                       help='Wallet RPC port')
    parser.add_argument('--wallet-host', default='11.0.0.254',
                       help='Wallet RPC host')
    parser.add_argument('--daemon-host', default='11.0.0.252',
                       help='Daemon RPC host')
    parser.add_argument('--daemon-rpc', type=int, default=29100,
                       help='Daemon RPC port')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(level=getattr(logging, args.log_level))
    
    # Create and run agent
    agent = BlockControllerAgent(
        agent_id=args.id,
        wallet_rpc_port=args.wallet_rpc,
        wallet_host=args.wallet_host,
        daemon_host=args.daemon_host,
        daemon_rpc_port=args.daemon_rpc,
        target_block_interval=args.interval,
        blocks_per_generation=args.blocks
    )
    
    agent.run()


if __name__ == "__main__":
    main()