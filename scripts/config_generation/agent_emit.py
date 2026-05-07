"""Per-agent dict construction for monerosim configs.

Each helper returns the OrderedDict for one agent in the YAML output.
Phased variants (``*_phased``) emit the daemon_0 / daemon_1 fields used
by upgrade scenarios.
"""

from collections import OrderedDict
from typing import Any, Dict

from .timeline import format_time_offset


def generate_miner_agent(hashrate: int, start_offset_s: int, daemon_binary: str = "monerod") -> Dict[str, Any]:
    """Generate a miner agent configuration (new format)."""
    return OrderedDict([
        ("daemon", daemon_binary),
        ("wallet", "monero-wallet-rpc"),
        ("script", "agents.autonomous_miner"),
        ("start_time", format_time_offset(start_offset_s)),
        ("hashrate", hashrate),
        ("can_receive_distributions", True),
    ])


def generate_miner_agent_phased(
    hashrate: int,
    start_offset_s: int,
    daemon_v1: str,
    daemon_v2: str,
    phase0_stop_s: int,
    phase1_start_s: int,
) -> Dict[str, Any]:
    """Generate a miner agent with daemon phase switching for upgrade scenario."""
    return OrderedDict([
        ("wallet", "monero-wallet-rpc"),
        ("script", "agents.autonomous_miner"),
        ("start_time", format_time_offset(start_offset_s)),
        ("hashrate", hashrate),
        ("can_receive_distributions", True),
        ("daemon_0", daemon_v1),
        ("daemon_0_start", format_time_offset(start_offset_s)),
        ("daemon_0_stop", format_time_offset(phase0_stop_s)),
        ("daemon_1", daemon_v2),
        ("daemon_1_start", format_time_offset(phase1_start_s)),
    ])


def generate_user_agent(start_offset_s: int, tx_interval: int = 60, activity_start_time: int = 0, daemon_binary: str = "monerod", tx_send_probability: float = 0.75) -> Dict[str, Any]:
    """Generate a regular user agent configuration (new format).

    Args:
        start_offset_s: When the agent process spawns (sim time)
        tx_interval: Interval between transaction attempts
        activity_start_time: Absolute sim time when transactions should start (0 = start immediately)
        daemon_binary: Path to monerod binary (default: "monerod")
        tx_send_probability: Probability of sending a transaction each iteration (default: 0.75)
    """
    return OrderedDict([
        ("daemon", daemon_binary),
        ("wallet", "monero-wallet-rpc"),
        ("script", "agents.regular_user"),
        ("start_time", format_time_offset(start_offset_s)),
        ("transaction_interval", tx_interval),
        ("activity_start_time", activity_start_time),
        ("tx_send_probability", tx_send_probability),
        ("can_receive_distributions", True),
    ])


def generate_user_agent_phased(
    start_offset_s: int,
    tx_interval: int,
    activity_start_time: int,
    daemon_v1: str,
    daemon_v2: str,
    phase0_stop_s: int,
    phase1_start_s: int,
    tx_send_probability: float = 0.75,
) -> Dict[str, Any]:
    """Generate a user agent with daemon phase switching for upgrade scenario."""
    return OrderedDict([
        ("wallet", "monero-wallet-rpc"),
        ("script", "agents.regular_user"),
        ("start_time", format_time_offset(start_offset_s)),
        ("transaction_interval", tx_interval),
        ("activity_start_time", activity_start_time),
        ("tx_send_probability", tx_send_probability),
        ("can_receive_distributions", True),
        ("daemon_0", daemon_v1),
        ("daemon_0_start", format_time_offset(start_offset_s)),
        ("daemon_0_stop", format_time_offset(phase0_stop_s)),
        ("daemon_1", daemon_v2),
        ("daemon_1_start", format_time_offset(phase1_start_s)),
    ])


def generate_relay_agent(start_offset_s: int, daemon_binary: str = "monerod") -> Dict[str, Any]:
    """Generate a daemon-only relay node configuration (no wallet, no script).

    Relay nodes run monerod for P2P block/transaction relay only.
    They increase network size and realism without transacting.
    """
    return OrderedDict([
        ("daemon", daemon_binary),
        ("start_time", format_time_offset(start_offset_s)),
    ])


def generate_relay_agent_phased(
    start_offset_s: int,
    daemon_v1: str,
    daemon_v2: str,
    phase0_stop_s: int,
    phase1_start_s: int,
) -> Dict[str, Any]:
    """Generate a relay node with daemon phase switching for upgrade scenario."""
    return OrderedDict([
        ("start_time", format_time_offset(start_offset_s)),
        ("daemon_0", daemon_v1),
        ("daemon_0_start", format_time_offset(start_offset_s)),
        ("daemon_0_stop", format_time_offset(phase0_stop_s)),
        ("daemon_1", daemon_v2),
        ("daemon_1_start", format_time_offset(phase1_start_s)),
    ])
