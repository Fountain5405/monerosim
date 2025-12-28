#!/usr/bin/env python3
"""
Autonomous Miner Agent for Monerosim

This agent independently determines when to generate blocks using a Poisson
distribution model. Each miner operates autonomously without central coordination,
creating a realistic, distributed mining simulation.

Key Features:
- Probabilistic block discovery using Poisson distribution
- Deterministic reproducibility via seeded randomness
- RPC-based operation with no shared state dependencies
- Self-contained mining loop with automatic timing recalculation
"""

import sys
import time
import math
import random
import os
import argparse
import logging
from typing import Optional, Dict, Any

from .base_agent import BaseAgent
from .monero_rpc import MoneroRPC, WalletRPC, RPCError, MethodNotAvailableError


class AutonomousMinerAgent(BaseAgent):
    """
    Independent mining agent that autonomously generates blocks
    using Poisson distribution timing model.
    
    This agent replaces centralized block controller architecture with
    distributed, probabilistic mining that more accurately reflects
    real-world mining dynamics.
    """
    
    def __init__(self, agent_id: str, **kwargs):
        """
        Initialize autonomous miner agent.
        
        Args:
            agent_id: Unique identifier for this agent
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(agent_id=agent_id, **kwargs)
        
        # Mining parameters
        self.hashrate_pct = 0.0
        self.total_network_hashrate = 1_000_000  # Default 1M H/s
        self.current_difficulty = None
        self.last_block_height = 0
        
        # Deterministic seeding for reproducibility
        self.global_seed = int(os.getenv('SIMULATION_SEED', '12345'))
        self.agent_seed = self.global_seed + hash(agent_id)
        random.seed(self.agent_seed)
        
        # Mining control
        self.mining_active = False
        
        # Statistics
        self.blocks_generated = 0
        self.total_mining_time = 0.0
        self.mining_start_time = 0.0
        
        # Wallet address (will be populated during setup)
        self.wallet_address = None
        
    def _setup_agent(self):
        """Initialize mining agent and prepare for autonomous operation"""
        self.logger.info("Autonomous Miner initializing...")
        
        # Parse mining configuration from attributes
        self._parse_mining_config()
        
        # Log deterministic seeding information
        self.logger.info(f"Global seed: {self.global_seed}, Agent seed: {self.agent_seed}")
        self.logger.info(f"Configured: {self.hashrate_pct}% of {self.total_network_hashrate} H/s network hashrate")
        
        # Wait for daemon to be ready
        if not self.agent_rpc:
            self.logger.error("Agent RPC not initialized")
            raise RuntimeError("Agent RPC connection required for mining")
            
        self.logger.info("Waiting for daemon to be ready...")
        try:
            self.agent_rpc.wait_until_ready(max_wait=120)
            info = self.agent_rpc.get_info()
            self.logger.info(f"Daemon ready at height {info.get('height', 0)}")
        except RPCError as e:
            self.logger.error(f"Failed to connect to daemon: {e}")
            raise
        
        # Wait for wallet to be ready and get address
        if not self.wallet_rpc:
            self.logger.error("Wallet RPC not initialized")
            raise RuntimeError("Wallet RPC connection required for mining rewards")
            
        self.logger.info("Waiting for wallet to be ready...")
        try:
            self.wallet_rpc.wait_until_ready(max_wait=180)
            
            # Get wallet address for mining rewards
            self.wallet_address = self.wallet_rpc.get_address()
            self.logger.info(f"Mining to wallet address: {self.wallet_address}")
            
        except RPCError as e:
            self.logger.error(f"Failed to connect to wallet: {e}")
            raise
        
        # Activate mining
        self.mining_active = True
        self.mining_start_time = time.time()
        self.logger.info(f"✓ Mining activated with {self.hashrate_pct}% hashrate")
        self.logger.info(f"Using Poisson distribution for block discovery timing")
        
    def _parse_mining_config(self):
        """
        Parse mining-specific configuration from attributes.
        
        Expected attributes:
        - hashrate: Percentage of total network hashrate (required)
        - total_network_hashrate: Total network hashrate in H/s (optional, default: 1M)
        
        Raises:
            ValueError: If hashrate is missing or invalid
        """
        # Get hashrate percentage (required)
        hashrate_str = self.attributes.get('hashrate')
        if not hashrate_str:
            raise ValueError("Missing required attribute 'hashrate'")
            
        try:
            self.hashrate_pct = float(hashrate_str)
        except ValueError:
            raise ValueError(f"Invalid hashrate value: '{hashrate_str}' (must be numeric)")
        
        # Validate hashrate range
        if not (0 < self.hashrate_pct <= 100):
            raise ValueError(f"Invalid hashrate: {self.hashrate_pct}% (must be 0-100)")
        
        # Get total network hashrate (optional)
        total_hr_str = self.attributes.get('total_network_hashrate', '1000000')
        try:
            self.total_network_hashrate = float(total_hr_str)
        except ValueError:
            self.logger.warning(f"Invalid total_network_hashrate: '{total_hr_str}', using default 1M H/s")
            self.total_network_hashrate = 1_000_000
        
        # Validate total network hashrate
        if self.total_network_hashrate <= 0:
            raise ValueError(f"Invalid total network hashrate: {self.total_network_hashrate}")
        
        self.logger.debug(f"Parsed mining config: {self.hashrate_pct}% of {self.total_network_hashrate} H/s")
        
    def _get_current_difficulty(self) -> int:
        """
        Query current network difficulty via RPC.
        
        Returns:
            Current network difficulty, or 1 if query fails
        """
        try:
            info = self.agent_rpc.get_info()
            difficulty = info.get('difficulty', 1)
            
            # Ensure difficulty is positive
            if difficulty <= 0:
                self.logger.warning(f"Invalid difficulty {difficulty}, using minimum value 1")
                return 1
                
            return difficulty
            
        except Exception as e:
            self.logger.error(f"Failed to get difficulty: {e}")
            return 1  # Fallback to minimum difficulty
            
    def _calculate_next_block_time(self) -> float:
        """
        Calculate time until next block discovery using Poisson distribution.
        
        Uses the formula: T = -ln(1 - U) / λ
        Where:
            - U is a uniform random number [0, 1)
            - λ (lambda) = agent_hashrate / network_difficulty
            - T is the time in seconds until next block
        
        Returns:
            Time in seconds until next block discovery attempt
        """
        # Get current difficulty
        difficulty = self._get_current_difficulty()
        
        # Calculate agent's effective hashrate
        agent_hashrate = (self.hashrate_pct / 100.0) * self.total_network_hashrate
        
        # Calculate lambda (success rate)
        # Avoid division by zero
        if difficulty == 0:
            self.logger.warning("Difficulty is zero, using minimum value 1")
            difficulty = 1
            
        lambda_rate = agent_hashrate / difficulty
        
        # Generate uniform random number in [0, 1)
        u = random.random()
        
        # Avoid log(0) edge case
        if u >= 1.0:
            u = 0.999999
        
        # Calculate time using exponential distribution (Poisson interarrival times)
        try:
            time_seconds = -math.log(1.0 - u) / lambda_rate
        except (ValueError, ZeroDivisionError) as e:
            self.logger.error(f"Error calculating block time: {e}")
            # Fallback to a reasonable default (e.g., 120 seconds)
            time_seconds = 120.0
        
        self.logger.debug(f"Next block in {time_seconds:.1f}s "
                         f"(hashrate: {agent_hashrate:.0f} H/s, "
                         f"difficulty: {difficulty}, "
                         f"λ={lambda_rate:.6f})")
        
        return time_seconds
        
    def _generate_block(self) -> bool:
        """
        Generate a single block via RPC.
        
        Returns:
            True if block generation succeeded, False otherwise
        """
        if not self.wallet_address:
            self.logger.error("Cannot generate block: wallet address not available")
            return False
            
        try:
            # Generate block using ensure_mining (tries available methods)
            result = self.agent_rpc.ensure_mining(wallet_address=self.wallet_address)
            
            if result and result.get('status') == 'OK':
                # Extract block information based on method used
                method_used = result.get('method', 'unknown')
                inner_result = result.get('result', {})
                
                # Log block generation
                if method_used == 'generateblocks':
                    blocks = inner_result.get('blocks', [])
                    if blocks:
                        block_hash = blocks[0]
                        self.logger.info(f"✓ Block generated: {block_hash}")
                        return True
                elif method_used == 'start_mining':
                    self.logger.info(f"✓ Mining started successfully")
                    return True
                else:
                    self.logger.warning(f"Unknown mining method: {method_used}")
                    
            return False
            
        except MethodNotAvailableError as e:
            self.logger.error(f"No mining methods available: {e}")
            return False
        except RPCError as e:
            error_str = str(e).lower()
            
            # Handle specific error cases gracefully
            if "not enough money" in error_str or "insufficient funds" in error_str:
                self.logger.warning("Insufficient funds for block generation")
                return False
            elif "wallet not ready" in error_str or "wallet not loaded" in error_str:
                self.logger.warning("Wallet not ready, will retry on next iteration")
                return False
            else:
                self.logger.error(f"RPC error during block generation: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Unexpected error during block generation: {e}", exc_info=True)
            return False
            
    def _update_statistics(self):
        """Update and log mining statistics"""
        current_time = time.time()
        elapsed_time = current_time - self.mining_start_time
        
        avg_block_time = elapsed_time / max(self.blocks_generated, 1)
        
        stats = {
            "agent_id": self.agent_id,
            "hashrate_pct": self.hashrate_pct,
            "blocks_generated": self.blocks_generated,
            "avg_block_time": avg_block_time,
            "current_height": self.last_block_height,
            "elapsed_time": elapsed_time,
            "timestamp": current_time
        }
        
        self.logger.info(f"Mining stats: {self.blocks_generated} blocks, "
                        f"avg {avg_block_time:.1f}s/block, "
                        f"height {self.last_block_height}")
        
    def run_iteration(self) -> float:
        """
        Single iteration of autonomous mining loop.
        
        Process:
        1. Calculate time until next block attempt using Poisson distribution
        2. Sleep for calculated duration
        3. Attempt to generate block
        4. Return minimal sleep to immediately recalculate next attempt
        
        Returns:
            Sleep time in seconds until next iteration (0.1s for immediate recalc)
        """
        if not self.mining_active:
            self.logger.debug("Mining not active, sleeping 60s")
            return 60.0  # Check every minute if not mining
            
        # Calculate time until next block attempt
        next_block_time = self._calculate_next_block_time()
        
        # Sleep for calculated duration
        self.logger.debug(f"Waiting {next_block_time:.1f}s before next block attempt")
        time.sleep(next_block_time)
        
        # Attempt to generate block
        success = self._generate_block()
        
        if success:
            # Update statistics
            self.blocks_generated += 1
            
            # Get current blockchain height
            try:
                info = self.agent_rpc.get_info()
                self.last_block_height = info.get('height', 0)
                current_difficulty = info.get('difficulty', 0)
                
                self.logger.info(f"New height: {self.last_block_height}, "
                               f"difficulty: {current_difficulty}")
                
                # Periodically log statistics (every 10 blocks)
                if self.blocks_generated % 10 == 0:
                    self._update_statistics()
                    
            except Exception as e:
                self.logger.warning(f"Failed to query blockchain info: {e}")
        
        # Immediately calculate next attempt (minimal sleep)
        return 0.1
        
    def _cleanup_agent(self):
        """Clean up autonomous miner resources and log final statistics"""
        self.logger.info("Autonomous miner shutting down...")
        
        # Log final statistics
        self._update_statistics()
        
        # Write final summary
        if self.mining_start_time > 0:
            total_runtime = time.time() - self.mining_start_time
            summary = {
                "agent_id": self.agent_id,
                "hashrate_pct": self.hashrate_pct,
                "total_blocks_generated": self.blocks_generated,
                "total_runtime_seconds": total_runtime,
                "avg_block_time": total_runtime / max(self.blocks_generated, 1),
                "final_height": self.last_block_height,
                "timestamp": time.time()
            }
            
            try:
                self.write_shared_state(f"{self.agent_id}_mining_summary.json", summary)
                self.logger.info(f"Final summary: {self.blocks_generated} blocks in {total_runtime:.1f}s")
            except Exception as e:
                self.logger.error(f"Failed to write final summary: {e}")
        
        self.logger.info("Autonomous miner shutdown complete")


def main():
    """Main entry point for autonomous miner agent"""
    parser = AutonomousMinerAgent.create_argument_parser(
        "Autonomous Miner Agent for Monerosim"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run agent
    agent = AutonomousMinerAgent(
        agent_id=args.id,
        shared_dir=args.shared_dir,
        agent_rpc_port=args.agent_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes
    )
    
    agent.run()


if __name__ == "__main__":
    main()