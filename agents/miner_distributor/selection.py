"""
Miner selection helpers for MinerDistributorAgent.

Free functions implementing the per-strategy miner picks. The
``MinerDistributorAgent._select_miner_excluding`` method on the agent
class is responsible for filtering eligible miners and dispatching to the
right strategy here.
"""

import logging
import random
from typing import Any, Dict, List, Optional


def select_miner_by_weight(
    miners: List[Dict[str, Any]],
    logger: logging.Logger,
) -> Optional[Dict[str, Any]]:
    """Select a miner based on hashrate weight"""
    # Extract weights
    weights = [miner.get("weight", 0) for miner in miners]
    total_weight = sum(weights)

    if total_weight == 0:
        logger.warning("Total weight is zero, falling back to random selection")
        return random.choice(miners)

    # Use cumulative weights for selection
    cumulative_weights = []
    cumulative_sum = 0
    for weight in weights:
        cumulative_sum += weight
        cumulative_weights.append(cumulative_sum)

    random_value = random.uniform(0, total_weight)
    winner_index = 0
    for i, cumulative_weight in enumerate(cumulative_weights):
        if random_value <= cumulative_weight:
            winner_index = i
            break

    winner = miners[winner_index]
    logger.info(f"Selected miner {winner.get('agent_id')} with weight {winner.get('weight')}")
    return winner


def select_miner_by_balance(
    miners: List[Dict[str, Any]],
    logger: logging.Logger,
) -> Optional[Dict[str, Any]]:
    """Select a miner with the highest balance"""
    # Placeholder implementation - would need RPC connection to check balances
    # For now, just select randomly
    logger.warning("Balance-based selection not fully implemented, using random selection")
    return random.choice(miners)
