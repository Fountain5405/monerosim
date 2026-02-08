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
from .monero_rpc import MoneroRPC, WalletRPC, RPCError

__all__ = [
    'DEFAULT_SHARED_DIR', 'MONERO_P2P_PORT', 'MONERO_RPC_PORT',
    'MONERO_WALLET_RPC_PORT', 'SHADOW_EPOCH',
    'BaseAgent', 'MoneroRPC', 'WalletRPC', 'RPCError',
]