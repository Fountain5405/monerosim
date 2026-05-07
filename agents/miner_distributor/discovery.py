"""
Miner discovery helpers for MinerDistributorAgent.

Free functions for resolving miner wallet addresses via RPC. Reading the
agent registry / miner registry is still done by the agent class itself
because that path uses BaseAgent's read_shared_state plumbing.
"""

import logging
from typing import Any, Dict, Optional

from ..monero_rpc import WalletRPC
from ..shared_utils import is_valid_monero_address


def query_miner_wallet_address(
    agent: Dict[str, Any],
    logger: logging.Logger,
) -> Optional[str]:
    """
    Query a miner's wallet address directly via RPC.

    Args:
        agent: Agent information including ip_addr and wallet_rpc_port
        logger: Logger to use for diagnostics

    Returns:
        Wallet address string or None if query fails
    """
    try:
        rpc = WalletRPC(host=agent['ip_addr'], port=agent['wallet_rpc_port'])
        rpc.wait_until_ready(max_wait=30, check_interval=2)
        address = rpc.get_address()
        if is_valid_monero_address(address):
            return address
    except Exception as e:
        logger.debug(f"Failed to query wallet address for {agent.get('id')}: {e}")
    return None
