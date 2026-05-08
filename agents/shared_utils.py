"""
Shared utility functions for the Monerosim agent framework.

Consolidates duplicated logic that was spread across multiple agent modules:
- Monero address validation
- XMR / atomic-unit conversion
- Deterministic per-agent seeding
- Public-nodes registry I/O
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import (
    ATOMIC_UNITS_PER_XMR,
    DEFAULT_SIMULATION_SEED,
    MAX_ADDRESS_LENGTH,
    MIN_ADDRESS_LENGTH,
    SEED_HASH_MODULUS,
    VALID_ADDRESS_PREFIXES,
)

PUBLIC_NODES_REGISTRY_FILENAME = "public_nodes.json"


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


def load_public_nodes_registry(
    shared_dir: Path,
    logger: logging.Logger,
) -> Optional[List[Dict[str, Any]]]:
    """Read ``public_nodes.json`` from *shared_dir* and return its ``nodes`` list.

    Both ``AgentDiscovery`` and ``PublicNodeDiscovery`` independently load this
    registry; this helper is the single source of truth for the file path,
    "missing-file" semantics, and JSON shape extraction.

    Returns ``None`` (with a warning log) if the file does not exist, allowing
    callers to distinguish "registry absent" from "registry empty" so they can
    skip cache updates in the absent case. ``json.JSONDecodeError`` and other
    exceptions are propagated so callers can apply their own error-translation
    policy (e.g. re-raise as ``AgentDiscoveryError`` or log-and-swallow).
    """
    registry_path = shared_dir / PUBLIC_NODES_REGISTRY_FILENAME

    if not registry_path.exists():
        logger.warning(f"Public nodes registry not found at {registry_path}")
        return None

    with open(registry_path, 'r') as f:
        registry = json.load(f)

    return registry.get("nodes", [])
