#!/usr/bin/env python3
"""
Autonomous Miner Agent for Monerosim

This agent independently determines when to generate blocks using a Poisson
distribution model. Each miner operates autonomously without central coordination,
creating a realistic, distributed mining simulation.
"""

import json
import time
import math
import random
import os
import fcntl
import logging
from typing import Optional, Dict, Any

from .base_agent import BaseAgent
from .constants import TARGET_BLOCK_TIME_SECS, DEFAULT_SIMULATION_SEED
from .file_locking import acquire_flock, release_flock
from .monero_rpc import MoneroRPC, WalletRPC, RPCError, MethodNotAvailableError
from .shared_utils import make_deterministic_seed


class AutonomousMinerAgent(BaseAgent):
    """Mining agent using Poisson distribution timing for autonomous block generation."""
    
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
        self.global_seed = int(os.getenv('SIMULATION_SEED', str(DEFAULT_SIMULATION_SEED)))
        self.agent_seed = make_deterministic_seed(agent_id)
        random.seed(self.agent_seed)

        # Difficulty caching to reduce RPC calls
        self._cached_difficulty = None
        self._difficulty_cache_time = 0.0
        self._difficulty_cache_ttl = float(os.getenv('DIFFICULTY_CACHE_TTL', '30'))

        # Synthetic difficulty adjustment (see _get_daa_multiplier).
        # Window is in blocks: long enough that Poisson noise averages out
        # (relative error ~1/sqrt(N)), short enough to track a real hashrate
        # change within a plausible retarget period. DAA_WINDOW=0 disables
        # the correction entirely (pure fixed-rate pacing).
        self.daa_window = int(os.getenv('DAA_WINDOW', '30'))
        self.daa_min = float(os.getenv('DAA_MIN', '0.1'))
        self.daa_max = float(os.getenv('DAA_MAX', '10.0'))
        # Corrections begin only once every block in the window is a
        # mining-regime block: startup blocks (agent stagger, wallet
        # creation) are slow for non-mining reasons, and letting them into a
        # window measurably poisoned the estimate (baseline ran 13% fast).
        self.daa_start = int(os.getenv('DAA_START', str(2 * self.daa_window)))
        self._daa_d = {}               # height -> synthetic per-block multiplier
        self._daa_ts = {}              # height -> block timestamp (replay cache)
        self._daa_last_height = None   # last height replayed into _daa_d
        self._daa_last_multiplier = 1.0  # last returned value (wait rescaling)

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
        if not self.daemon_rpc:
            self.logger.error("Daemon RPC not initialized")
            raise RuntimeError("Daemon RPC connection required for mining")

        self.logger.info("Waiting for daemon to be ready...")
        try:
            self.daemon_rpc.wait_until_ready(max_wait=120)
            info = self.daemon_rpc.get_info()
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
        self.logger.info(f"Mining activated with hashrate weight {self.hashrate_pct}")
        self.logger.info(f"Using difficulty-only mode: timing scales with LWMA difficulty adjustments")
        self.logger.info(f"Base expected block time: {120.0 / (self.hashrate_pct / 100.0):.1f}s "
                        f"(at baseline difficulty {self.baseline_difficulty})")
        
    def _get_mining_address(self) -> Optional[str]:
        """
        Poll for wallet address from miner_info file (created by regular_user.py).

        In the hybrid approach:
        - regular_user.py runs on this host and creates the wallet
        - regular_user.py writes the address to {agent_id}_miner_info.json
        - autonomous_miner.py polls this file until address is available

        This decouples wallet creation from mining, allowing both to proceed
        without blocking each other.

        Returns:
            Valid Monero address string, or None if polling times out
        """
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
                        acquire_flock(lock_f, fcntl.LOCK_SH)
                        try:
                            with open(agent_registry_file, 'r') as f:
                                registry = json.load(f)
                        finally:
                            release_flock(lock_f)
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

        # Timeout - no valid address available
        self.logger.error(f"Timeout waiting for wallet address after {max_wait_time}s")
        return None

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

    def _get_current_difficulty(self, force_refresh: bool = False) -> int:
        """
        Query current network difficulty via RPC with caching.

        Uses cached value if available and TTL hasn't expired.
        TTL is configured via DIFFICULTY_CACHE_TTL environment variable (default: 30s).

        Args:
            force_refresh: If True, bypass cache and fetch fresh value

        Returns:
            Current network difficulty, or 1 if query fails
        """
        current_time = time.time()

        # Return cached value if valid and not forcing refresh
        if not force_refresh and self._cached_difficulty is not None:
            cache_age = current_time - self._difficulty_cache_time
            if cache_age < self._difficulty_cache_ttl:
                return self._cached_difficulty

        try:
            info = self.daemon_rpc.get_info()
            difficulty = info.get('difficulty', 1)

            # Ensure difficulty is positive
            if difficulty <= 0:
                self.logger.warning(f"Invalid difficulty {difficulty}, using minimum value 1")
                difficulty = 1

            # Update cache
            self._cached_difficulty = difficulty
            self._difficulty_cache_time = current_time

            return difficulty

        except Exception as e:
            self.logger.error(f"Failed to get difficulty: {e}")
            # Return cached value if available, otherwise fallback
            if self._cached_difficulty is not None:
                return self._cached_difficulty
            return 1  # Fallback to minimum difficulty
            
    def _get_daa_multiplier(self) -> float:
        m = self._get_daa_multiplier_inner()
        self._daa_last_multiplier = m
        return m

    def _get_daa_multiplier_inner(self) -> float:
        """Synthetic difficulty adjustment from this chain's block timestamps.

        Returns a factor to MULTIPLY the expected inter-block time by:
          >1 recent blocks came too fast  -> miners slow down
          <1 recent blocks came too slow  -> miners speed up
          =1 on target, or window not yet available (warmup)

        LWMA-form recurrence, one value per BLOCK HEIGHT, replayed
        deterministically from headers:

            d[k] = 1                                        for k <= START
            d[k] = mean(d[k-W .. k-1]) * (W*T) / (ts[k-1] - ts[k-1-W])
                                                            for k >  START
            multiplier for the next block = d[top+1]

        The structural choice that made this attempt different: real DAAs
        recompute next-difficulty from the WINDOW-AVERAGE of past
        difficulties (a finite-impulse-response form — any transient's
        influence washes out after one window). The previous attempt used a
        pure multiplicative accumulator (m *= ratio^gain), an
        infinite-impulse integrator behind a trailing window — a textbook
        ringing recipe, and it rang: overshoot to 5.0 against a correct
        value of 3.0, final-hour cadence 215s vs the 120s target.

        Properties carried forward from the earlier failures:
        - state accumulates ACROSS the series (a stateless estimator's fixed
          point is off by exactly sqrt(H): measured 78s vs predicted 69s at
          3x hashrate);
        - one update per HEIGHT via replay, so every miner computes the
          identical series from the same headers (verified coherent to
          within 5% before this rewrite);
        - corrections start only at START = 2*W, so agent-startup blocks
          (slow for non-mining reasons) never enter any window — letting
          them in made the fixed-cohort baseline run 13% fast.

        Computed from headers, deliberately NOT from chain difficulty (that
        signal is integer-quantized at regtest scale and was the original
        issue-#8 instability). Timestamps are per-CHAIN, so a partitioned
        minority retargets on its own chain independently.
        """
        window = self.daa_window
        if window <= 0 or not self.daemon_rpc:
            return 1.0
        try:
            info = self.daemon_rpc.get_info()
            height = int(info.get('height', 0))  # block COUNT (top index + 1)
        except Exception as e:
            self.logger.debug(f"DAA: get_info failed ({e}); holding")
            return self._daa_d.get(self._daa_last_height or 0, 1.0)

        top = height - 1
        if top <= self.daa_start:
            return 1.0

        # A shorter chain than last time means a reorg (e.g. the pop-blocks
        # path after a late upgrade): drop caches and replay from scratch.
        if self._daa_last_height is not None and top < self._daa_last_height:
            self.logger.debug(f"DAA: chain shortened {self._daa_last_height}->{top}, replaying")
            self._daa_ts.clear()
            self._daa_d.clear()
            self._daa_last_height = None

        def ts(h):
            cached = self._daa_ts.get(h)
            if cached is None:
                cached = int(self.daemon_rpc.get_block_header_by_height(h).get('timestamp', 0))
                self._daa_ts[h] = cached
            return cached

        def d(h):
            return self._daa_d.get(h, 1.0)  # d = 1 for all heights <= START

        start = (self.daa_start + 1 if self._daa_last_height is None
                 else self._daa_last_height + 1)
        expected = window * TARGET_BLOCK_TIME_SECS
        try:
            # Replay: compute d[k] for every height up to top+1, so the value
            # we return is the multiplier in force for the block being mined
            # NOW (index top+1). Window for d[k] ends at block k-1.
            for k in range(start, top + 2):
                observed = ts(k - 1) - ts(k - 1 - window)
                if observed <= 0:
                    self._daa_d[k] = d(k - 1)
                    continue
                mean_d = sum(d(i) for i in range(k - window, k)) / window
                nd = mean_d * expected / observed
                self._daa_d[k] = max(self.daa_min, min(self.daa_max, nd))
        except Exception as e:
            self.logger.debug(f"DAA: header fetch failed ({e}); holding")
            return d(self._daa_last_height + 1) if self._daa_last_height else 1.0

        self._daa_last_height = top
        # Keep replay caches bounded; only the trailing window is reused.
        if len(self._daa_ts) > 4 * window:
            for h in [k for k in self._daa_ts if k < top - 2 * window - 2]:
                del self._daa_ts[h]
            for h in [k for k in self._daa_d if k < top - 2 * window - 2]:
                del self._daa_d[h]
        m = d(top + 1)
        self.logger.debug(f"DAA: replayed to {top} window={window} multiplier={m:.3f}")
        return m

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
        TARGET_BLOCK_TIME = TARGET_BLOCK_TIME_SECS

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

        # SYNTHETIC DIFFICULTY ADJUSTMENT (GitHub issue #8).
        #
        # Rate is corrected by an estimator computed from this chain's own
        # block-header timestamps — the same principle as LWMA, but it does
        # NOT read chain difficulty. History: pacing used to scale by
        # (chain difficulty / baseline), which was unstable and produced
        # 38-minute stalls on seed 8. The instability was not inherent to
        # feedback (real Monero's DAA is exactly this shape and is stable) —
        # it came from four defects in that specific signal, all removed here:
        #   * regtest difficulty is a SMALL INTEGER (1,2,3..22): stepping
        #     1->2 is an instant 2x rate change. Here the correction is a
        #     continuous float.
        #   * the retarget window at genesis is ~3 blocks, so warmup noise
        #     was treated as signal. Here the estimator is silent until a
        #     full window exists (and with a fixed cohort summing to 100 the
        #     uncorrected rate is already correct during warmup).
        #   * the difficulty read was CACHED for 30s, adding phase lag —
        #     the classic oscillation ingredient. This reads fresh headers.
        #   * baseline=1 vs the loop's difficulty-2 equilibrium made every
        #     historical run pace at ~2.8 min/block instead of 2.0.
        #
        # Estimator: over the last DAA_WINDOW blocks, multiplier =
        # (expected elapsed) / (actual elapsed). Blocks too fast => >1 =>
        # miners wait longer. Every miner on a chain reads the same headers,
        # so the correction is coherent across the cohort without consensus
        # difficulty being involved; a partitioned minority retargets on its
        # OWN chain, which is the behavior real Monero has and the previous
        # (no-feedback) model lacked.
        difficulty_factor = self._get_daa_multiplier()
        expected_agent_block_time = base_expected_time * difficulty_factor
        # Kept for logs/statistics only; no longer steers pacing.
        current_difficulty = self._get_current_difficulty()

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
            result = self.daemon_rpc.ensure_mining(wallet_address=self.wallet_address)
            
            if result and result.get('status') == 'OK':
                # Extract block information based on method used
                method_used = result.get('method', 'unknown')
                inner_result = result.get('result', {})
                
                # Log block generation
                if method_used == 'generateblocks':
                    blocks = inner_result.get('blocks', [])
                    if blocks:
                        block_hash = blocks[0]
                        self.logger.info(f"Block generated: {block_hash}")
                        return True
                elif method_used == 'start_mining':
                    self.logger.info(f"Mining started successfully")
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

        # Sleep in slices, rescaling the REMAINING wait whenever the DAA
        # multiplier moves. Without this, a wait sampled while m was high
        # (an hour-plus for a small miner) blocks downward corrections until
        # it expires — measured as a one-sided slow decay: the hashjoin
        # battery run settled 28% slow (153.7s vs the 120s target) while the
        # split run, whose stale waits were short, passed. Rescaling the
        # remainder by m_new/m_old is exact for exponential waits
        # (memorylessness + scaling), i.e. this samples the inhomogeneous
        # Poisson process the time-varying rate implies.
        self.logger.debug(f"Waiting {next_block_time:.1f}s before next block attempt")
        m_at_sample = self._daa_last_multiplier
        remaining = next_block_time
        SLICE = 30.0
        while remaining > 0 and self.running:
            self.interruptible_sleep(min(remaining, SLICE))
            remaining -= SLICE
            if remaining <= 0:
                break
            m_now = self._get_daa_multiplier()
            if m_at_sample and m_now and abs(m_now - m_at_sample) / m_at_sample > 0.01:
                remaining *= m_now / m_at_sample
                self.logger.debug(
                    f"DAA moved {m_at_sample:.3f}->{m_now:.3f}; "
                    f"remaining wait rescaled to {remaining:.1f}s")
                m_at_sample = m_now
        if not self.running:
            return 0.0
        
        # Attempt to generate block
        success = self._generate_block()
        
        if success:
            # Update statistics
            self.blocks_generated += 1
            
            # Get current blockchain height
            try:
                info = self.daemon_rpc.get_info()
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
        daemon_rpc_port=args.daemon_rpc_port,
        wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port,
        rpc_host=args.rpc_host,
        log_level=args.log_level,
        attributes=args.attributes
    )
    
    agent.run()


if __name__ == "__main__":
    main()