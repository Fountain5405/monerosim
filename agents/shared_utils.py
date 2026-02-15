"""
Shared utility functions for the Monerosim agent framework.

Consolidates duplicated logic that was spread across multiple agent modules:
- Monero address validation
- XMR / atomic-unit conversion
- Deterministic per-agent seeding
"""

import hashlib
import os
from typing import Optional

from .constants import (
    ATOMIC_UNITS_PER_XMR,
    DEFAULT_SIMULATION_SEED,
    MAX_ADDRESS_LENGTH,
    MIN_ADDRESS_LENGTH,
    SEED_HASH_MODULUS,
    VALID_ADDRESS_PREFIXES,
)


def is_valid_monero_address(address: Optional[str]) -> bool:
    """Check whether *address* looks like a valid Monero address.

    Validates prefix (``4`` or ``8``) and length range.  This is a
    quick format check, not a full Base58 + checksum verification.
    """
    if not address or not isinstance(address, str):
        return False
    return (
        address.startswith(VALID_ADDRESS_PREFIXES)
        and MIN_ADDRESS_LENGTH <= len(address) <= MAX_ADDRESS_LENGTH
    )


def xmr_to_atomic(amount: float) -> int:
    """Convert an XMR amount to piconero (atomic units).

    >>> xmr_to_atomic(1.5)
    1500000000000
    """
    return int(amount * ATOMIC_UNITS_PER_XMR)


def atomic_to_xmr(amount: int) -> float:
    """Convert piconero (atomic units) to XMR.

    >>> atomic_to_xmr(1500000000000)
    1.5
    """
    return amount / ATOMIC_UNITS_PER_XMR


def make_deterministic_seed(agent_id: str) -> int:
    """Derive a deterministic per-agent seed from ``SIMULATION_SEED`` env var
    (or ``DEFAULT_SIMULATION_SEED``) and the agent's ID.

    The returned seed is suitable for passing to ``random.seed()``.
    """
    global_seed = int(os.getenv('SIMULATION_SEED', str(DEFAULT_SIMULATION_SEED)))
    agent_hash = int(hashlib.sha256(agent_id.encode()).hexdigest(), 16) % SEED_HASH_MODULUS
    return global_seed + agent_hash
