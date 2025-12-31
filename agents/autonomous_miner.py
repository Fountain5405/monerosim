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
import fcntl
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
        self.hashrate_pct = 0.0  # This miner's hashrate weight
        self.current_difficulty = None
        self.baseline_difficulty = 1  # Fixed baseline for consistent scaling across all miners
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
        self.logger.info(f"Configured hashrate weight: {self.hashrate_pct}")

        # Wait for daemon to be ready
        if not self.agent_rpc:
            self.logger.error("Agent RPC not initialized")
            raise RuntimeError("Agent RPC connection required for mining")

        self.logger.info("Waiting for daemon to be ready...")
        try:
            self.agent_rpc.wait_until_ready(max_wait=120)
            info = self.agent_rpc.get_info()
            self.logger.info(f"Daemon ready at height {info.get('height', 0)}")

            # Use fixed baseline difficulty of 1 for all miners
            # This ensures consistent timing regardless of when miners join:
            # - Initial miners (hashrates sum to 100): difficulty stays ~1, factor = 1.0
            # - New miner joins (total > 100): blocks faster, difficulty rises, factor > 1.0
            # - All miners use same baseline, so all scale proportionally
            self.baseline_difficulty = 1
            current_difficulty = info.get('difficulty', 1)
            self.logger.info(f"Baseline difficulty: {self.baseline_difficulty}, "
                           f"current difficulty: {current_difficulty}")
        except RPCError as e:
            self.logger.error(f"Failed to connect to daemon: {e}")
            raise

        # Get wallet address for mining - try multiple approaches
        # generateblocks RPC only needs a valid address string, not a loaded wallet
        self.wallet_address = self._get_mining_address()
        if not self.wallet_address:
            self.logger.error("Failed to obtain mining address")
            raise RuntimeError("Mining address required for block rewards")

        # Activate mining
        self.mining_active = True
        self.mining_start_time = time.time()
        self.logger.info(f"✓ Mining activated with hashrate weight {self.hashrate_pct}")
        self.logger.info(f"Using difficulty-only mode: timing scales with LWMA difficulty adjustments")
        self.logger.info(f"Base expected block time: {120.0 / (self.hashrate_pct / 100.0):.1f}s "
                        f"(at baseline difficulty {self.baseline_difficulty})")
        
    def _get_mining_address(self) -> Optional[str]:
        """
        Poll for wallet address from miner_info file (created by regular_user.py).

        In the hybrid approach:
        - regular_user.py runs on this node and creates the wallet
        - regular_user.py writes the address to {agent_id}_miner_info.json
        - autonomous_miner.py polls this file until address is available

        This decouples wallet creation from mining, allowing both to proceed
        without blocking each other.

        Returns:
            Valid Monero address string, or None if polling times out
        """
        import json
        from pathlib import Path

        if not self.shared_dir:
            self.logger.error("No shared directory configured, cannot poll for address")
            return None

        miner_info_file = Path(self.shared_dir) / f"{self.agent_id}_miner_info.json"
        agent_registry_file = Path(self.shared_dir) / "agent_registry.json"

        # Poll configuration
        max_wait_time = 300  # 5 minutes maximum wait
        poll_interval = 5   # Check every 5 seconds
        start_time = time.time()

        self.logger.info(f"Polling for wallet address (regular_user.py should register it)...")

        while time.time() - start_time < max_wait_time:
            # Try miner info file first (preferred - written by regular_user.py)
            if miner_info_file.exists():
                try:
                    with open(miner_info_file, 'r') as f:
                        miner_info = json.load(f)
                        if "wallet_address" in miner_info:
                            address = miner_info["wallet_address"]
                            self.logger.info(f"Found wallet address in miner info file: {address[:20]}...")
                            return address
                except Exception as e:
                    self.logger.debug(f"Error reading miner info file: {e}")

            # Fallback to agent registry (with file locking for determinism)
            if agent_registry_file.exists():
                lock_path = Path(self.shared_dir) / "agent_registry.lock"
                try:
                    with open(lock_path, 'w') as lock_f:
                        fcntl.flock(lock_f, fcntl.LOCK_SH)
                        try:
                            with open(agent_registry_file, 'r') as f:
                                registry = json.load(f)
                        finally:
                            fcntl.flock(lock_f, fcntl.LOCK_UN)
                    for agent in registry.get("agents", []):
                        if agent.get("id") == self.agent_id:
                            if "wallet_address" in agent:
                                address = agent["wallet_address"]
                                self.logger.info(f"Found wallet address in agent registry: {address[:20]}...")
                                return address
                except Exception as e:
                    self.logger.debug(f"Error reading agent registry: {e}")

            # Wait before next poll
            elapsed = time.time() - start_time
            self.logger.debug(f"Waiting for wallet address... (elapsed: {elapsed:.1f}s)")
            time.sleep(poll_interval)

        # Timeout - use fallback address for simulation
        self.logger.warning(f"Timeout waiting for wallet address after {max_wait_time}s")
        self.logger.warning(f"Using fallback simulation address (rewards won't be tracked)")

        # Fallback to a known valid address for simulation purposes
        fallback_address = "44AFFq5kSiGBoZ4NMDwYtN18obc8AemS33DBLWs3H7otXft3XjrpDtQGv7SqSsaBYBb98uNbr2VBBEt7f2wfn3RVGQBEP3A"
        return fallback_address

    def _parse_mining_config(self):
        """
        Parse mining-specific configuration from attributes.

        Expected attributes:
        - hashrate: This miner's hashrate weight (required). The actual percentage
                   is calculated dynamically by discovering all miners' weights.

        Raises:
            ValueError: If hashrate is missing or invalid
        """
        self.logger.info(f"Autonomous miner attributes: {self.attributes}")

        # Get hashrate weight (required)
        hashrate_str = self.attributes.get('hashrate')
        if not hashrate_str:
            self.logger.error(f"Missing 'hashrate' attribute. Available attributes: {self.attributes}")
            raise ValueError("Missing required attribute 'hashrate'")

        try:
            self.hashrate_pct = float(hashrate_str)
        except ValueError:
            raise ValueError(f"Invalid hashrate value: '{hashrate_str}' (must be numeric)")

        # Validate hashrate is positive
        if self.hashrate_pct <= 0:
            raise ValueError(f"Invalid hashrate: {self.hashrate_pct} (must be positive)")

        self.logger.info(f"Parsed mining config: hashrate weight = {self.hashrate_pct}")

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

        Uses difficulty-only mode for timing adjustment:
        - Base timing assumes hashrate weights sum to 100 at simulation start
        - Difficulty factor scales timing based on LWMA adjustments
        - No hashrate discovery in timing (avoids double-counting)

        Formula: T = -ln(1 - U) / λ
        Where:
            - U is a uniform random number [0, 1)
            - λ (lambda) = 1 / expected_agent_block_time
            - expected_agent_block_time = (TARGET_BLOCK_TIME / base_fraction) * difficulty_factor
            - base_fraction = hashrate_pct / 100 (assumes weights sum to 100)
            - T is the time in seconds until next block

        This creates a proper LWMA feedback loop:
        - If new miner joins, blocks arrive faster than 120s target
        - LWMA increases difficulty proportionally
        - All miners see higher difficulty, slow their generation rate
        - Block times stabilize back toward 120s target

        This is more realistic for attack simulations because:
        - Difficulty adjustment is gradual (over ~60 blocks)
        - Network naturally "pushes back" against attackers
        - No instant adjustment that would bypass LWMA dynamics

        Returns:
            Time in seconds until next block discovery attempt
        """
        # Monero target block time is 120 seconds
        TARGET_BLOCK_TIME = 120.0

        # Use hashrate_pct as a fraction of 100 (baseline assumption)
        # This means if weights sum to 100, blocks arrive at 120s average
        # If weights sum to 140 (new miner joined), blocks arrive faster,
        # and LWMA will increase difficulty to compensate
        base_fraction = self.hashrate_pct / 100.0

        if base_fraction <= 0:
            self.logger.warning("Invalid hashrate fraction, using 1%")
            base_fraction = 0.01

        # Calculate base expected time (at baseline difficulty)
        base_expected_time = TARGET_BLOCK_TIME / base_fraction

        # Query current difficulty and calculate scaling factor
        # This is the ONLY adjustment mechanism - lets LWMA do its job
        current_difficulty = self._get_current_difficulty()
        if self.baseline_difficulty and self.baseline_difficulty > 0:
            difficulty_factor = current_difficulty / self.baseline_difficulty
        else:
            difficulty_factor = 1.0

        # Scale expected time by difficulty factor
        # If difficulty doubled (e.g., from new miners), blocks take 2x longer
        expected_agent_block_time = base_expected_time * difficulty_factor

        # Lambda (rate parameter) = 1 / expected_time
        lambda_rate = 1.0 / expected_agent_block_time

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
            # Fallback to expected agent block time
            time_seconds = expected_agent_block_time

        # Log the calculation for debugging
        self.logger.debug(f"Next block in {time_seconds:.1f}s "
                         f"(hashrate: {self.hashrate_pct}%, difficulty: {difficulty_factor:.2f}x, "
                         f"expected avg: {expected_agent_block_time:.1f}s)")

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
        current_difficulty = self._get_current_difficulty()
        difficulty_factor = current_difficulty / self.baseline_difficulty if self.baseline_difficulty else 1.0

        stats = {
            "agent_id": self.agent_id,
            "hashrate_weight": self.hashrate_pct,
            "baseline_difficulty": self.baseline_difficulty,
            "current_difficulty": current_difficulty,
            "difficulty_factor": difficulty_factor,
            "blocks_generated": self.blocks_generated,
            "avg_block_time": avg_block_time,
            "current_height": self.last_block_height,
            "elapsed_time": elapsed_time,
            "timestamp": current_time
        }

        self.logger.info(f"Mining stats: {self.blocks_generated} blocks, "
                        f"avg {avg_block_time:.1f}s/block, "
                        f"difficulty {difficulty_factor:.2f}x, "
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
            final_difficulty = self._get_current_difficulty()
            difficulty_factor = final_difficulty / self.baseline_difficulty if self.baseline_difficulty else 1.0
            summary = {
                "agent_id": self.agent_id,
                "hashrate_weight": self.hashrate_pct,
                "baseline_difficulty": self.baseline_difficulty,
                "final_difficulty": final_difficulty,
                "difficulty_factor": difficulty_factor,
                "total_blocks_generated": self.blocks_generated,
                "total_runtime_seconds": total_runtime,
                "avg_block_time": total_runtime / max(self.blocks_generated, 1),
                "final_height": self.last_block_height,
                "timestamp": time.time()
            }

            try:
                self.write_shared_state(f"{self.agent_id}_mining_summary.json", summary)
                self.logger.info(f"Final summary: {self.blocks_generated} blocks in {total_runtime:.1f}s "
                               f"(difficulty {difficulty_factor:.2f}x from baseline)")
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