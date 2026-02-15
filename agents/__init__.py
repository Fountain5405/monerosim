"""
Monerosim Agent Framework

This module provides agent-based simulation capabilities for Monero network participants.
Agents control pre-launched Monero processes via RPC within Shadow's constraints.
"""

from .base_agent import (
    BaseAgent,
    DEFAULT_SHARED_DIR,
    MONERO_P2P_PORT,
    MONERO_RPC_PORT,
    MONERO_WALLET_RPC_PORT,
    SHADOW_EPOCH,
)
from .constants import (
    ATOMIC_UNITS_PER_XMR,
    TARGET_BLOCK_TIME_SECS,
    VALID_ADDRESS_PREFIXES,
    DEFAULT_SIMULATION_SEED,
)
from .shared_utils import (
    is_valid_monero_address,
    xmr_to_atomic,
    atomic_to_xmr,
    make_deterministic_seed,
)
from .monero_rpc import MoneroRPC, WalletRPC, RPCError

__all__ = [
    'DEFAULT_SHARED_DIR', 'MONERO_P2P_PORT', 'MONERO_RPC_PORT',
    'MONERO_WALLET_RPC_PORT', 'SHADOW_EPOCH',
    'ATOMIC_UNITS_PER_XMR', 'TARGET_BLOCK_TIME_SECS',
    'VALID_ADDRESS_PREFIXES', 'DEFAULT_SIMULATION_SEED',
    'is_valid_monero_address', 'xmr_to_atomic', 'atomic_to_xmr',
    'make_deterministic_seed',
    'BaseAgent', 'MoneroRPC', 'WalletRPC', 'RPCError',
]