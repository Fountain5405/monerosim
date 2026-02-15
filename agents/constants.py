"""
Shared constants for the Monerosim agent framework.

Centralizes magic numbers and protocol constants that were previously
scattered across multiple agent modules.
"""

# ---------------------------------------------------------------------------
# Monero protocol constants
# ---------------------------------------------------------------------------

ATOMIC_UNITS_PER_XMR: int = 10**12
"""1 XMR = 10^12 piconero (atomic units)."""

TARGET_BLOCK_TIME_SECS: float = 120.0
"""Monero's target block interval in seconds."""

# ---------------------------------------------------------------------------
# Address validation
# ---------------------------------------------------------------------------

VALID_ADDRESS_PREFIXES: tuple = ('4', '8')
"""Mainnet standard (4) and subaddress (8) prefixes."""

MIN_ADDRESS_LENGTH: int = 4
MAX_ADDRESS_LENGTH: int = 95

# ---------------------------------------------------------------------------
# Simulation reproducibility
# ---------------------------------------------------------------------------

DEFAULT_SIMULATION_SEED: int = 12345
"""Default global seed when SIMULATION_SEED env var is unset."""

SEED_HASH_MODULUS: int = 2**31
"""Modulus for deriving per-agent seeds from the global seed + agent ID hash."""

# ---------------------------------------------------------------------------
# Transaction safety limits
# ---------------------------------------------------------------------------

MAX_REASONABLE_TX_XMR: float = 1000.0
"""Sanity-check ceiling for a single transaction amount (XMR)."""
