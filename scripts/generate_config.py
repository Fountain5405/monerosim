#!/usr/bin/env python3
"""
Generate monerosim configuration files with varying agent counts for scaling tests.

Usage:
    python scripts/generate_config.py --agents 50 -o test_50.yaml
    python scripts/generate_config.py --agents 100 -o test_100.yaml
    python scripts/generate_config.py --agents 1000 --duration 8h -o test_1000.yaml

The generated config has:
- Fixed 5 miners (core network) with hashrates: 25, 25, 30, 10, 10
- Variable users spawning at 3h mark with configurable stagger (default 5s)
- Dynamic bootstrap period that extends based on agent count + 20% buffer
- Miner distributor starts when bootstrap ends (funds users from miner wallets)
- User activity starts 1 hour after bootstrap ends

Timeline (dynamic based on agent count and stagger):
  t=0:            Miners start mining
  t=3h:           Users start spawning (staggered to avoid Shadow overload)
  t=3h+stagger:   Last user spawns
  t=bootstrap:    Bootstrap ends (last_spawn * 1.2, min 4h), distributor starts
  t=activity:     Users start sending transactions (bootstrap + 1h)

This timing ensures:
- All users spawn during bootstrap (high bandwidth, no packet loss)
- 20% buffer for hardware variance in sync time
- Minimum 4h bootstrap for sufficient blocks (60 needed for unlock)
- 1 hour funding period before activity starts
"""

import argparse
import random
import sys
from typing import Dict, Any, List, Tuple
from collections import OrderedDict


# Fixed miner configuration (same as config_32_agents.yaml)
FIXED_MINERS = [
    {"hashrate": 25, "start_offset_s": 0},
    {"hashrate": 25, "start_offset_s": 1},
    {"hashrate": 30, "start_offset_s": 2},
    {"hashrate": 10, "start_offset_s": 3},
    {"hashrate": 10, "start_offset_s": 4},
]

# Bootstrap timing constants (verified for Monero regtest with ring size 16)
# This ensures sufficient blocks for unlock (60) and outputs for ring signatures

# Users spawn at 3h mark (sync during bootstrap period)
USER_START_TIME_S = 10800  # 3 hours in seconds

# Minimum bootstrap time - ensures enough blocks for coinbase unlock (60 blocks)
# At ~2 min/block, 4h gives ~120 blocks which is sufficient
MIN_BOOTSTRAP_END_TIME_S = 14400  # 4 hours minimum

# Buffer percentage added after last user spawn to account for hardware variance
BOOTSTRAP_BUFFER_PERCENT = 0.20  # 20% buffer

# Time after bootstrap ends for miner distributor to fund users before activity starts
FUNDING_PERIOD_S = 3600  # 1 hour for funding

# Minimum activity period (time after activity_start before simulation ends)
MIN_ACTIVITY_PERIOD_S = 7200  # 2 hours minimum for meaningful transaction activity

# Note: monerosim only supports seconds resolution (no ms support in duration parser)
# Default 5s stagger spreads user spawns to reduce simultaneous load on Shadow

# Batched bootstrap defaults
DEFAULT_AUTO_THRESHOLD = 50  # Enable batching when > 50 users
DEFAULT_INITIAL_DELAY_S = 1200  # 20 minutes after miners
DEFAULT_BATCH_INTERVAL_S = 1200  # 20 minutes between batches
DEFAULT_INITIAL_BATCH_SIZE = 5
DEFAULT_GROWTH_FACTOR = 2.0
DEFAULT_MAX_BATCH_SIZE = 200
DEFAULT_INTRA_BATCH_STAGGER_S = 5  # 5 seconds between users in same batch

# Upgrade scenario defaults
DEFAULT_STEADY_STATE_DURATION_S = 7200  # 2 hours of observation before upgrade
DEFAULT_POST_UPGRADE_DURATION_S = 7200  # 2 hours of observation after upgrade
DEFAULT_UPGRADE_STAGGER_S = 30  # 30 seconds between node upgrades
DEFAULT_DAEMON_RESTART_GAP_S = 30  # Gap between stopping old daemon and starting new one

# User activity batching defaults (prevents thundering herd when all users try to transact at once)
# Both values at 0 = auto-detect: batch_size capped at 5 (proven safe concurrency),
# interval spread across one tx_interval period (min 120s between batches)
DEFAULT_ACTIVITY_BATCH_SIZE = 0  # 0 = auto-detect (max 5 concurrent)
DEFAULT_ACTIVITY_BATCH_INTERVAL_S = 0  # 0 = auto-detect from user count and tx_interval
DEFAULT_ACTIVITY_BATCH_JITTER = 0.30  # +/- 30% randomization per user within batch

# Relay node spawn staggering defaults
# Relays are daemon-only (1 process each) so simple linear stagger suffices
DEFAULT_RELAY_SPAWN_START_S = 5   # Start after miners (t=5s)
DEFAULT_RELAY_STAGGER_S = 20      # 20s apart; sim-time moves fast so need wider spacing


def auto_detect_activity_batching(num_users: int, tx_interval: int) -> tuple:
    """Auto-detect activity batch size and interval for safe ring construction.

    Ring signature decoy selection is CPU-intensive. In Shadow, too many
    concurrent wallet-rpcs doing ring construction causes thread starvation
    and permanent freezes. Miner wallets (max 5 concurrent) never freeze,
    so we target a similar concurrency level.

    Strategy:
    - batch_size: max 5 concurrent wallets (proven safe)
    - interval: spread all batches across one tx_interval period,
      with a minimum of 120s between batches for ring construction headroom

    Returns:
        (batch_size, batch_interval_s)
    """
    batch_size = max(3, min(5, num_users))
    num_batches = (num_users + batch_size - 1) // batch_size
    if num_batches <= 1:
        return (batch_size, 300)
    interval = max(120, tx_interval // num_batches)
    return (batch_size, interval)


def resolve_activity_batching(batch_size: int, batch_interval_s: int,
                               num_users: int, tx_interval: int) -> tuple:
    """Resolve activity batching, auto-detecting whichever value is 0."""
    if batch_size <= 0 or batch_interval_s <= 0:
        auto_size, auto_interval = auto_detect_activity_batching(num_users, tx_interval)
        if batch_size <= 0:
            batch_size = auto_size
        if batch_interval_s <= 0:
            batch_interval_s = auto_interval
    return (batch_size, batch_interval_s)


def calculate_activity_start_times(
    num_users: int,
    base_activity_start_s: int,
    batch_size: int,
    batch_interval_s: int,
    jitter_fraction: float,
    seed: int,
) -> List[int]:
    """Calculate staggered activity start times to prevent thundering herd.

    Instead of all users starting transactions at the same time, this staggers
    their start times in batches with randomization to spread the load.

    Args:
        num_users: Total number of users
        base_activity_start_s: When the first batch should start (sim time seconds)
        batch_size: Number of users per batch
        batch_interval_s: Target time between batch starts
        jitter_fraction: Random jitter as fraction of batch_interval (e.g., 0.3 = +/-30%)
        seed: Random seed for reproducible jitter

    Returns:
        List of activity_start_time values for each user (in order)
    """
    if num_users == 0:
        return []

    rng = random.Random(seed)
    activity_times = []

    # Calculate jitter range in seconds
    jitter_range_s = int(batch_interval_s * jitter_fraction)

    for user_idx in range(num_users):
        batch_num = user_idx // batch_size
        batch_start_s = base_activity_start_s + (batch_num * batch_interval_s)

        # Add random jitter: +/- jitter_range_s
        if jitter_range_s > 0:
            jitter_s = rng.randint(-jitter_range_s, jitter_range_s)
        else:
            jitter_s = 0

        # Ensure we don't go before base_activity_start_s
        activity_time = max(base_activity_start_s, batch_start_s + jitter_s)
        activity_times.append(activity_time)

    return activity_times


def calculate_upgrade_schedule(
    agents: List[str],
    upgrade_start_s: int,
    upgrade_stagger_s: int,
    upgrade_order: str,
    miner_ids: List[str],
    seed: int,
) -> Dict[str, Tuple[int, int]]:
    """Calculate when each agent's daemon phases switch.

    Args:
        agents: List of agent IDs to upgrade
        upgrade_start_s: When upgrades begin (sim time in seconds)
        upgrade_stagger_s: Time between consecutive node upgrades
        upgrade_order: "sequential" | "random" | "miners-first"
        miner_ids: List of miner agent IDs (used for miners-first ordering)
        seed: Random seed for reproducible ordering

    Returns:
        Dict mapping agent_id to (phase0_stop_s, phase1_start_s)
    """
    # Determine upgrade order
    if upgrade_order == "random":
        rng = random.Random(seed)
        ordered_agents = list(agents)
        rng.shuffle(ordered_agents)
    elif upgrade_order == "miners-first":
        miners = [a for a in agents if a in miner_ids]
        users = [a for a in agents if a not in miner_ids]
        ordered_agents = miners + users
    else:  # sequential (default)
        ordered_agents = list(agents)

    # Calculate upgrade times for each agent
    schedule = {}
    for i, agent_id in enumerate(ordered_agents):
        phase0_stop = upgrade_start_s + (i * upgrade_stagger_s)
        phase1_start = phase0_stop + DEFAULT_DAEMON_RESTART_GAP_S
        schedule[agent_id] = (phase0_stop, phase1_start)

    return schedule


def calculate_batch_sizes(num_users: int, initial_size: int, growth_factor: float, max_size: int) -> list:
    """Calculate batch sizes using exponential growth strategy.

    Args:
        num_users: Total number of users to distribute
        initial_size: Size of first batch
        growth_factor: Multiplier for each subsequent batch
        max_size: Maximum batch size cap

    Returns:
        List of batch sizes
    """
    if num_users == 0:
        return []

    batches = []
    remaining = num_users
    current_size = initial_size

    while remaining > 0:
        # Cap at max_size and remaining
        batch_size = min(current_size, max_size, remaining)
        batches.append(batch_size)
        remaining -= batch_size

        # Calculate next batch size (exponential growth)
        current_size = int(current_size * growth_factor + 0.5)  # Round
        current_size = max(current_size, 1)  # Ensure at least 1

    return batches


def calculate_batch_schedule(
    num_users: int,
    initial_delay_s: int,
    batch_interval_s: int,
    initial_batch_size: int,
    growth_factor: float,
    max_batch_size: int,
    intra_batch_stagger_s: int,
) -> list:
    """Calculate complete batch schedule with user start times.

    Returns:
        List of (user_index, start_time_seconds) tuples
    """
    batch_sizes = calculate_batch_sizes(num_users, initial_batch_size, growth_factor, max_batch_size)

    schedule = []
    user_index = 0

    for batch_num, batch_size in enumerate(batch_sizes):
        batch_start_time = initial_delay_s + (batch_num * batch_interval_s)

        for i in range(batch_size):
            user_start_time = batch_start_time + (i * intra_batch_stagger_s)
            schedule.append((user_index, user_start_time))
            user_index += 1

    return schedule


def format_batch_summary(batch_sizes: list, initial_delay_s: int, batch_interval_s: int) -> str:
    """Format batch schedule for display (with # comment prefixes)."""
    lines = [f"Batched bootstrap: {sum(batch_sizes)} users in {len(batch_sizes)} batches"]
    for i, size in enumerate(batch_sizes):
        start_time = initial_delay_s + (i * batch_interval_s)
        lines.append(f"#   Batch {i+1}: {size} users starting at {format_time_offset(start_time, for_config=False)}")
    return "\n".join(lines)


def calculate_bootstrap_timing(num_users: int, stagger_interval_s: int) -> tuple:
    """Calculate dynamic bootstrap timing based on user count and stagger.

    Returns:
        (bootstrap_end_time_s, activity_start_time_s, last_user_spawn_s)
    """
    # Calculate when the last user spawns
    if num_users > 0:
        last_user_spawn_s = USER_START_TIME_S + ((num_users - 1) * stagger_interval_s)
    else:
        last_user_spawn_s = USER_START_TIME_S

    # Add buffer for hardware variance (users need time to actually sync after spawning)
    spawn_with_buffer_s = int(last_user_spawn_s * (1 + BOOTSTRAP_BUFFER_PERCENT))

    # Bootstrap must be at least MIN_BOOTSTRAP_END_TIME_S to ensure enough blocks
    bootstrap_end_time_s = max(MIN_BOOTSTRAP_END_TIME_S, spawn_with_buffer_s)

    # Activity starts after funding period
    activity_start_time_s = bootstrap_end_time_s + FUNDING_PERIOD_S

    return (bootstrap_end_time_s, activity_start_time_s, last_user_spawn_s)


def parse_duration(duration_str: str) -> int:
    """Parse duration string like '4h', '30m', '45s' to seconds."""
    duration_str = duration_str.strip().lower()

    if duration_str.endswith('h'):
        return int(duration_str[:-1]) * 3600
    elif duration_str.endswith('m'):
        return int(duration_str[:-1]) * 60
    elif duration_str.endswith('s'):
        return int(duration_str[:-1])
    else:
        # Assume seconds if no unit
        return int(duration_str)


def format_time_offset(seconds: int, for_config: bool = True) -> str:
    """Format time offset in the most readable way.

    Args:
        seconds: Time in seconds
        for_config: If True, use simple format for YAML config (e.g., "4h", "90m", "30s")
                   If False, use human-readable format (e.g., "4h 22m")
    """
    if for_config:
        # Simple format for YAML config values
        if seconds % 3600 == 0 and seconds >= 3600:
            return f"{seconds // 3600}h"
        elif seconds % 60 == 0 and seconds >= 60:
            return f"{seconds // 60}m"
        else:
            return f"{seconds}s"
    else:
        # Human-readable format for comments
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 and hours == 0:  # Only show seconds if less than an hour
            parts.append(f"{secs}s")
        return " ".join(parts) if parts else "0s"


def generate_metadata(
    scenario: str,
    num_miners: int,
    num_users: int,
    timing_info: Dict[str, Any],
    simulation_seed: int,
    gml_path: str,
    fast_mode: bool,
    stagger_interval_s: int,
    relay_nodes: int = 0,
) -> OrderedDict:
    """Generate machine-parseable metadata section for analysis tools.

    Args:
        scenario: "default" or "upgrade"
        num_miners: Number of miner agents
        num_users: Number of user agents
        timing_info: Dictionary with timing calculations
        simulation_seed: Random seed used
        gml_path: Path to GML topology file
        fast_mode: Whether fast mode is enabled
        stagger_interval_s: User stagger interval
        relay_nodes: Number of daemon-only relay nodes

    Returns:
        OrderedDict with metadata structure
    """
    metadata = OrderedDict([
        ("scenario", scenario),
        ("generator", "generate_config.py"),
        ("version", "1.0"),
    ])

    # Agent counts
    agents_meta = OrderedDict([
        ("total", num_miners + num_users + relay_nodes),
        ("miners", num_miners),
        ("users", num_users),
    ])
    if relay_nodes > 0:
        agents_meta["relay_nodes"] = relay_nodes
        agents_meta["relay_spawn_start_s"] = timing_info.get('relay_spawn_start_s', DEFAULT_RELAY_SPAWN_START_S)
        agents_meta["relay_stagger_s"] = timing_info.get('relay_stagger_s', DEFAULT_RELAY_STAGGER_S)
        agents_meta["last_relay_spawn_s"] = timing_info.get('last_relay_spawn_s', 0)
    metadata["agents"] = agents_meta

    # Core timing (all in seconds for easy parsing)
    metadata["timing"] = OrderedDict([
        ("duration_s", timing_info['duration_s']),
        ("bootstrap_end_s", timing_info['bootstrap_end_time_s']),
        ("activity_start_s", timing_info['activity_start_time_s']),
        ("last_user_spawn_s", timing_info['last_user_spawn_s']),
    ])

    # Upgrade-specific metadata
    if scenario == "upgrade":
        metadata["upgrade"] = OrderedDict([
            ("binary_v1", timing_info.get('upgrade_binary_v1', 'monerod')),
            ("binary_v2", timing_info.get('upgrade_binary_v2', 'monerod')),
            ("order", timing_info.get('upgrade_order', 'sequential')),
            ("start_s", timing_info.get('upgrade_start_time_s', 0)),
            ("complete_s", timing_info.get('last_upgrade_complete_s', 0)),
            ("stagger_s", timing_info.get('upgrade_stagger_s', 30)),
            ("steady_state_duration_s", timing_info.get('steady_state_duration_s', 7200)),
            ("post_upgrade_duration_s", timing_info.get('post_upgrade_duration_s', 7200)),
        ])

    # Bootstrap batching configuration (user spawning)
    if timing_info.get('use_batched', False):
        metadata["batching"] = OrderedDict([
            ("enabled", True),
            ("batch_sizes", timing_info.get('batch_sizes', [])),
            ("batch_interval_s", timing_info.get('batch_interval_s', 1200)),
        ])
    else:
        metadata["batching"] = OrderedDict([
            ("enabled", False),
            ("stagger_interval_s", stagger_interval_s),
        ])

    # Activity batching configuration (transaction start staggering)
    metadata["activity_batching"] = OrderedDict([
        ("enabled", timing_info.get('activity_batching_enabled', True)),
        ("batch_size", timing_info.get('activity_batch_size', DEFAULT_ACTIVITY_BATCH_SIZE)),
        ("batch_interval_s", timing_info.get('activity_batch_interval_s', DEFAULT_ACTIVITY_BATCH_INTERVAL_S)),
        ("jitter_fraction", timing_info.get('activity_batch_jitter', DEFAULT_ACTIVITY_BATCH_JITTER)),
        ("total_rollout_s", timing_info.get('activity_rollout_duration_s', 0)),
    ])

    # Simulation settings
    metadata["settings"] = OrderedDict([
        ("seed", simulation_seed),
        ("gml_topology", gml_path),
        ("fast_mode", fast_mode),
    ])

    return metadata


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


# Single GML file for all tests (1200 nodes supports up to 1200 agents)
DEFAULT_GML_PATH = "gml_processing/1200_nodes_caida_with_loops.gml"


def generate_config(
    total_agents: int,
    duration: str,
    stagger_interval_s: int,
    simulation_seed: int = 12345,
    gml_path: str = DEFAULT_GML_PATH,
    fast_mode: bool = False,
    process_threads: int = 1,
    batched_bootstrap: str = "auto",
    batch_interval: str = "20m",
    initial_batch_size: int = 5,
    max_batch_size: int = 200,
    daemon_binary: str = "monerod",
    user_spawn_start: str = None,
    bootstrap_end_time: str = None,
    regular_user_start: str = None,
    md_start_time: str = None,
    md_n_recipients: int = 8,
    md_out_per_tx: int = 2,
    md_output_amount: float = 5.0,
    md_funding_cycle_interval: str = "5m",
    tx_interval: int = None,
    tx_send_probability: float = 0.75,
    # User activity batching (prevents thundering herd)
    activity_batch_size: int = DEFAULT_ACTIVITY_BATCH_SIZE,
    activity_batch_interval_s: int = DEFAULT_ACTIVITY_BATCH_INTERVAL_S,
    activity_batch_jitter: float = DEFAULT_ACTIVITY_BATCH_JITTER,
    # Shadow parallelism and preemption
    parallelism: int = 0,
    native_preemption: bool = None,
    # Relay nodes (daemon-only)
    relay_nodes: int = 0,
    relay_spawn_start_s: int = DEFAULT_RELAY_SPAWN_START_S,
    relay_stagger_s: int = DEFAULT_RELAY_STAGGER_S,
) -> Dict[str, Any]:
    """Generate the complete monerosim configuration.

    Args:
        total_agents: Total number of agents (5 miners + N users)
        duration: Simulation duration (e.g., "6h")
        stagger_interval_s: Seconds between user starts
        simulation_seed: Random seed for reproducibility
        gml_path: Path to GML topology file
        fast_mode: If True, use performance-friendly settings
        process_threads: Thread count for monerod/wallet-rpc (0=auto, 1=single, 2+=explicit)
        batched_bootstrap: "auto", "true", or "false" for batched user startup
        batch_interval: Time between batches (e.g., "20m")
        initial_batch_size: Size of first user batch
        max_batch_size: Maximum users per batch
        daemon_binary: Path to monerod binary (default: "monerod")
        tx_interval: Seconds between user transaction attempts (default: 120 in fast mode, 60 otherwise)
        tx_send_probability: Probability of sending a TX each iteration (default: 0.75)
        user_spawn_start: When users start spawning (default: 20m batched, 3h non-batched)
        bootstrap_end_time: When bootstrap ends (default: auto-calc from user spawns)
        regular_user_start: When users start transacting (default: md_start_time + 1h)
        md_start_time: When miner distributor starts (default: bootstrap_end_time)
        md_n_recipients: Recipients per batch transaction (default: 8)
        md_out_per_tx: Outputs per recipient per transaction (default: 2)
        md_output_amount: XMR amount per output (default: 5.0)
        md_funding_cycle_interval: Interval between continuous funding cycles (default: 5m)
        tx_interval: Seconds between user transaction attempts (default: 120 fast, 60 normal)
        activity_batch_size: Users per activity batch (default: 10)
        activity_batch_interval_s: Target seconds between activity batches (default: 300)
        activity_batch_jitter: Random jitter fraction +/- (default: 0.30 = 30%)
        relay_spawn_start_s: When relay nodes start spawning (default: 5s)
        relay_stagger_s: Interval between relay node spawns (default: 5s)
    """

    num_miners = len(FIXED_MINERS)
    num_users = total_agents - num_miners

    if num_users < 0:
        raise ValueError(f"Total agents ({total_agents}) must be at least {num_miners} (fixed miners)")

    # Determine if batched bootstrap should be enabled
    use_batched = (
        batched_bootstrap == "true" or
        (batched_bootstrap == "auto" and num_users >= DEFAULT_AUTO_THRESHOLD)
    )

    # Parse batch interval
    batch_interval_s = parse_duration(batch_interval)

    # Calculate user spawn start time
    if user_spawn_start is not None:
        user_spawn_start_s = parse_duration(user_spawn_start)
    else:
        # Default: 20m for batched, 3h for non-batched
        user_spawn_start_s = DEFAULT_INITIAL_DELAY_S if use_batched else USER_START_TIME_S

    # Calculate user start times based on batching mode
    batch_sizes = []
    batch_schedule = []

    if use_batched and num_users > 0:
        # Batched bootstrap: users start in waves
        batch_sizes = calculate_batch_sizes(num_users, initial_batch_size, 2.0, max_batch_size)
        batch_schedule = calculate_batch_schedule(
            num_users,
            user_spawn_start_s,
            batch_interval_s,
            initial_batch_size,
            2.0,  # growth_factor
            max_batch_size,
            DEFAULT_INTRA_BATCH_STAGGER_S,
        )
        # Last user spawn time from batch schedule
        last_user_spawn_s = batch_schedule[-1][1] if batch_schedule else 0
    else:
        # Non-batched: users start at user_spawn_start_s with stagger
        if num_users > 0:
            last_user_spawn_s = user_spawn_start_s + ((num_users - 1) * stagger_interval_s)
        else:
            last_user_spawn_s = user_spawn_start_s

    # Calculate timing with dependency chain:
    # 1. bootstrap_end_time_s: explicit or auto-calc
    # 2. md_start_time_s: explicit or defaults to bootstrap_end_time_s
    # 3. activity_start_time_s: explicit or defaults to md_start_time_s + 1h

    # Step 1: Bootstrap end time
    if bootstrap_end_time is not None:
        bootstrap_end_time_s = parse_duration(bootstrap_end_time)
    else:
        # Auto-calculate: max of minimum time and last spawn + buffer
        spawn_with_buffer_s = int(last_user_spawn_s * (1 + BOOTSTRAP_BUFFER_PERCENT))
        bootstrap_end_time_s = max(MIN_BOOTSTRAP_END_TIME_S, spawn_with_buffer_s)

    # Step 2: Miner distributor start time
    if md_start_time is not None:
        md_start_time_s = parse_duration(md_start_time)
        if md_start_time_s < bootstrap_end_time_s:
            print(f"Warning: --md-start-time ({md_start_time}) is before bootstrap_end_time "
                  f"({format_time_offset(bootstrap_end_time_s)}). Miners may not have accumulated enough funds.",
                  file=sys.stderr)
    else:
        md_start_time_s = bootstrap_end_time_s

    # Step 3: Regular user activity start time
    if regular_user_start is not None:
        activity_start_time_s = parse_duration(regular_user_start)
        if activity_start_time_s < md_start_time_s:
            print(f"Warning: --regular-user-start ({regular_user_start}) is before md_start_time "
                  f"({format_time_offset(md_start_time_s)}). Users may start before receiving funds.",
                  file=sys.stderr)
    else:
        activity_start_time_s = md_start_time_s + FUNDING_PERIOD_S

    # Parse and potentially extend duration to ensure minimum activity period
    requested_duration_s = parse_duration(duration)
    min_duration_s = activity_start_time_s + MIN_ACTIVITY_PERIOD_S
    duration_s = max(requested_duration_s, min_duration_s)
    duration = format_time_offset(duration_s)  # Update duration string if extended

    # Performance settings for fast mode
    if tx_interval is None:
        tx_interval = 120 if fast_mode else 60
    poll_interval = 300  # 5 minutes for reasonable monitoring updates
    shadow_log_level = "warning" if fast_mode else "info"
    runahead = "100ms" if fast_mode else None

    # Build named agents map (OrderedDict to preserve order)
    agents = OrderedDict()

    # Add fixed miners with explicit IDs
    for i, miner in enumerate(FIXED_MINERS):
        agent_id = f"miner-{i+1:03}"
        agents[agent_id] = generate_miner_agent(miner["hashrate"], miner["start_offset_s"], daemon_binary)

    # Resolve auto-detected activity batching (0 = auto from user count and tx_interval)
    activity_batch_size, activity_batch_interval_s = resolve_activity_batching(
        activity_batch_size, activity_batch_interval_s, num_users, tx_interval)

    # Calculate staggered activity start times to prevent thundering herd
    # Each user gets a slightly different activity_start_time based on batching
    user_activity_times = calculate_activity_start_times(
        num_users=num_users,
        base_activity_start_s=activity_start_time_s,
        batch_size=activity_batch_size,
        batch_interval_s=activity_batch_interval_s,
        jitter_fraction=activity_batch_jitter,
        seed=simulation_seed,
    )

    # Calculate activity rollout duration for metadata
    if num_users > 0:
        num_activity_batches = (num_users + activity_batch_size - 1) // activity_batch_size
        activity_rollout_duration_s = (num_activity_batches - 1) * activity_batch_interval_s
    else:
        activity_rollout_duration_s = 0

    # Add variable users with appropriate start times
    if use_batched and batch_schedule:
        # Batched bootstrap: use calculated batch schedule for spawning
        for user_index, start_time_s in batch_schedule:
            agent_id = f"user-{user_index+1:03}"
            user_activity_time = user_activity_times[user_index] if user_index < len(user_activity_times) else activity_start_time_s
            agents[agent_id] = generate_user_agent(start_time_s, tx_interval, user_activity_time, daemon_binary, tx_send_probability)
    else:
        # Non-batched bootstrap: start at USER_START_TIME_S with stagger
        for i in range(num_users):
            agent_id = f"user-{i+1:03}"
            start_offset_s = USER_START_TIME_S + (i * stagger_interval_s)
            user_activity_time = user_activity_times[i] if i < len(user_activity_times) else activity_start_time_s
            agents[agent_id] = generate_user_agent(start_offset_s, tx_interval, user_activity_time, daemon_binary, tx_send_probability)

    # Add relay nodes (daemon-only, no wallet or script)
    # Simple linear stagger: start + i * stagger
    for i in range(relay_nodes):
        agent_id = f"relay-{i+1:03}"
        relay_start_s = relay_spawn_start_s + (i * relay_stagger_s)
        agents[agent_id] = generate_relay_agent(relay_start_s, daemon_binary)

    # Calculate last relay spawn time for metadata/warnings
    if relay_nodes > 0:
        last_relay_spawn_s = relay_spawn_start_s + ((relay_nodes - 1) * relay_stagger_s)
        if last_relay_spawn_s > bootstrap_end_time_s:
            print(f"Warning: Last relay spawn ({format_time_offset(last_relay_spawn_s, for_config=False)}) "
                  f"exceeds bootstrap_end_time ({format_time_offset(bootstrap_end_time_s, for_config=False)}). "
                  f"Late relays may experience packet loss during sync.",
                  file=sys.stderr)
    else:
        last_relay_spawn_s = 0

    # Add miner-distributor (md_start_time_s calculated earlier in timing chain)
    agents["miner-distributor"] = OrderedDict([
        ("script", "agents.miner_distributor"),
        ("wait_time", md_start_time_s),  # When Shadow starts the process
        ("initial_wait_time", 0),  # No additional Python wait (Shadow handles timing)
        ("max_transaction_amount", "2.0"),
        ("min_transaction_amount", "0.5"),
        ("transaction_frequency", 30),
        ("md_n_recipients", md_n_recipients),
        ("md_out_per_tx", md_out_per_tx),
        ("md_output_amount", md_output_amount),
        ("md_funding_cycle_interval", md_funding_cycle_interval),
    ])

    # Add simulation-monitor
    agents["simulation-monitor"] = OrderedDict([
        ("script", "agents.simulation_monitor"),
        ("poll_interval", poll_interval),
        ("detailed_logging", False),
        ("enable_alerts", True),
        ("status_file", "monerosim_monitor.log"),
    ])

    # Build general config with daemon_defaults
    general_config = OrderedDict([
        ("stop_time", duration),
        ("parallelism", parallelism),
        ("simulation_seed", simulation_seed),
        ("enable_dns_server", True),
        ("shadow_log_level", shadow_log_level),
        # Bootstrap period: high bandwidth, no packet loss until all users spawned + buffer
        ("bootstrap_end_time", format_time_offset(bootstrap_end_time_s)),
        # Show simulation progress on stderr for visibility
        ("progress", True),
    ])

    # Add runahead for fast mode
    if runahead:
        general_config["runahead"] = runahead

    # Add process_threads if not default (1)
    if process_threads != 1:
        general_config["process_threads"] = process_threads

    # Add native_preemption only when explicitly set
    if native_preemption is not None:
        general_config["native_preemption"] = native_preemption

    # Add daemon_defaults - these were previously hardcoded
    general_config["daemon_defaults"] = OrderedDict([
        ("log-level", 1),
        ("log-file", "/dev/stdout"),
        ("db-sync-mode", "fastest"),
        ("no-zmq", True),
        ("non-interactive", True),
        ("disable-rpc-ban", True),
        ("allow-local-ip", True),
    ])

    # Add wallet_defaults
    general_config["wallet_defaults"] = OrderedDict([
        ("log-level", 1),
        ("log-file", "/dev/stdout"),
    ])

    # Return config and timing info for header generation
    timing_info = {
        'bootstrap_end_time_s': bootstrap_end_time_s,
        'md_start_time_s': md_start_time_s,
        'activity_start_time_s': activity_start_time_s,
        'last_user_spawn_s': last_user_spawn_s,
        'user_spawn_start_s': user_spawn_start_s,
        'duration_s': duration_s,
        'requested_duration_s': requested_duration_s,
        'use_batched': use_batched,
        'batch_sizes': batch_sizes,
        'batch_interval_s': batch_interval_s,
        # Activity batching info
        'activity_batching_enabled': True,
        'activity_batch_size': activity_batch_size,
        'activity_batch_interval_s': activity_batch_interval_s,
        'activity_batch_jitter': activity_batch_jitter,
        'activity_rollout_duration_s': activity_rollout_duration_s,
        # Relay timing info
        'relay_spawn_start_s': relay_spawn_start_s,
        'relay_stagger_s': relay_stagger_s,
        'last_relay_spawn_s': last_relay_spawn_s,
    }

    # Generate metadata section
    metadata = generate_metadata(
        scenario="default",
        num_miners=num_miners,
        num_users=num_users,
        timing_info=timing_info,
        simulation_seed=simulation_seed,
        gml_path=gml_path,
        fast_mode=fast_mode,
        stagger_interval_s=stagger_interval_s,
        relay_nodes=relay_nodes,
    )

    # Build full config with metadata first
    config = OrderedDict([
        ("metadata", metadata),
        ("general", general_config),
        ("network", OrderedDict([
            ("path", gml_path),
            ("peer_mode", "Dynamic"),
        ])),
        ("agents", agents),
    ])

    return config, timing_info


def generate_upgrade_config(
    total_agents: int,
    duration: str,
    stagger_interval_s: int,
    simulation_seed: int = 12345,
    gml_path: str = DEFAULT_GML_PATH,
    fast_mode: bool = False,
    process_threads: int = 1,
    batched_bootstrap: str = "auto",
    batch_interval: str = "20m",
    initial_batch_size: int = 5,
    max_batch_size: int = 200,
    user_spawn_start: str = None,
    bootstrap_end_time: str = None,
    regular_user_start: str = None,
    md_start_time: str = None,
    md_n_recipients: int = 8,
    md_out_per_tx: int = 2,
    md_output_amount: float = 5.0,
    md_funding_cycle_interval: str = "5m",
    tx_interval: int = None,
    tx_send_probability: float = 0.75,
    # User activity batching (prevents thundering herd)
    activity_batch_size: int = DEFAULT_ACTIVITY_BATCH_SIZE,
    activity_batch_interval_s: int = DEFAULT_ACTIVITY_BATCH_INTERVAL_S,
    activity_batch_jitter: float = DEFAULT_ACTIVITY_BATCH_JITTER,
    # Shadow parallelism and preemption
    parallelism: int = 0,
    native_preemption: bool = None,
    # Relay nodes (daemon-only)
    relay_nodes: int = 0,
    relay_spawn_start_s: int = DEFAULT_RELAY_SPAWN_START_S,
    relay_stagger_s: int = DEFAULT_RELAY_STAGGER_S,
    # Upgrade-specific parameters
    upgrade_binary_v1: str = "monerod",
    upgrade_binary_v2: str = "monerod",
    upgrade_start: str = None,  # None = auto-calculate
    upgrade_stagger_s: int = DEFAULT_UPGRADE_STAGGER_S,
    upgrade_order: str = "sequential",
    steady_state_duration_s: int = DEFAULT_STEADY_STATE_DURATION_S,
    post_upgrade_duration_s: int = DEFAULT_POST_UPGRADE_DURATION_S,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generate monerosim configuration for upgrade scenario.

    This creates a config where all nodes run daemon_v1 initially, then switch
    to daemon_v2 in a staggered fashion after a steady-state observation period.

    Timeline:
      t=0:           Miners start
      t=bootstrap:   Bootstrap ends, funding begins
      t=activity:    Users start transacting (steady state)
      t=upgrade:     Nodes begin switching to v2 (staggered)
      t=end:         Simulation ends after post-upgrade observation

    Args:
        upgrade_binary_v1: Phase 0 binary (e.g., "monerod-v1")
        upgrade_binary_v2: Phase 1 binary (e.g., "monerod-v2")
        upgrade_start: When upgrades begin (None = activity_start + steady_state_duration)
        upgrade_stagger_s: Time between consecutive node upgrades
        upgrade_order: "sequential" | "random" | "miners-first"
        steady_state_duration_s: How long to observe before upgrade
        post_upgrade_duration_s: How long to observe after upgrade
    """
    num_miners = len(FIXED_MINERS)
    num_users = total_agents - num_miners

    if num_users < 0:
        raise ValueError(f"Total agents ({total_agents}) must be at least {num_miners} (fixed miners)")

    # Determine if batched bootstrap should be enabled
    use_batched = (
        batched_bootstrap == "true" or
        (batched_bootstrap == "auto" and num_users >= DEFAULT_AUTO_THRESHOLD)
    )

    # Parse batch interval
    batch_interval_s = parse_duration(batch_interval)

    # Calculate user spawn start time
    if user_spawn_start is not None:
        user_spawn_start_s = parse_duration(user_spawn_start)
    else:
        # Default: 20m for batched, 3h for non-batched
        user_spawn_start_s = DEFAULT_INITIAL_DELAY_S if use_batched else USER_START_TIME_S

    # Calculate user start times based on batching mode
    batch_sizes = []
    batch_schedule = []

    if use_batched and num_users > 0:
        batch_sizes = calculate_batch_sizes(num_users, initial_batch_size, 2.0, max_batch_size)
        batch_schedule = calculate_batch_schedule(
            num_users,
            user_spawn_start_s,
            batch_interval_s,
            initial_batch_size,
            2.0,
            max_batch_size,
            DEFAULT_INTRA_BATCH_STAGGER_S,
        )
        last_user_spawn_s = batch_schedule[-1][1] if batch_schedule else 0
    else:
        if num_users > 0:
            last_user_spawn_s = user_spawn_start_s + ((num_users - 1) * stagger_interval_s)
        else:
            last_user_spawn_s = user_spawn_start_s

    # Calculate timing with dependency chain:
    # 1. bootstrap_end_time_s: explicit or auto-calc
    # 2. md_start_time_s: explicit or defaults to bootstrap_end_time_s
    # 3. activity_start_time_s: explicit or defaults to md_start_time_s + 1h

    # Step 1: Bootstrap end time
    if bootstrap_end_time is not None:
        bootstrap_end_time_s = parse_duration(bootstrap_end_time)
    else:
        # Auto-calculate: max of minimum time and last spawn + buffer
        spawn_with_buffer_s = int(last_user_spawn_s * (1 + BOOTSTRAP_BUFFER_PERCENT))
        bootstrap_end_time_s = max(MIN_BOOTSTRAP_END_TIME_S, spawn_with_buffer_s)

    # Step 2: Miner distributor start time
    if md_start_time is not None:
        md_start_time_s = parse_duration(md_start_time)
        if md_start_time_s < bootstrap_end_time_s:
            print(f"Warning: --md-start-time ({md_start_time}) is before bootstrap_end_time "
                  f"({format_time_offset(bootstrap_end_time_s)}). Miners may not have accumulated enough funds.",
                  file=sys.stderr)
    else:
        md_start_time_s = bootstrap_end_time_s

    # Step 3: Regular user activity start time
    if regular_user_start is not None:
        activity_start_time_s = parse_duration(regular_user_start)
        if activity_start_time_s < md_start_time_s:
            print(f"Warning: --regular-user-start ({regular_user_start}) is before md_start_time "
                  f"({format_time_offset(md_start_time_s)}). Users may start before receiving funds.",
                  file=sys.stderr)
    else:
        activity_start_time_s = md_start_time_s + FUNDING_PERIOD_S

    # Calculate upgrade timing
    if upgrade_start is not None:
        upgrade_start_time_s = parse_duration(upgrade_start)
    else:
        # Auto: upgrade starts after steady state observation period
        upgrade_start_time_s = activity_start_time_s + steady_state_duration_s

    # Performance settings
    if tx_interval is None:
        tx_interval = 120 if fast_mode else 60
    poll_interval = 300
    shadow_log_level = "warning" if fast_mode else "info"
    runahead = "100ms" if fast_mode else None

    # Build list of all agent IDs for upgrade scheduling
    miner_ids = [f"miner-{i+1:03}" for i in range(num_miners)]
    user_ids = [f"user-{i+1:03}" for i in range(num_users)]
    relay_ids = [f"relay-{i+1:03}" for i in range(relay_nodes)]
    all_agent_ids = miner_ids + user_ids + relay_ids

    # Calculate upgrade schedule for all agents
    upgrade_schedule = calculate_upgrade_schedule(
        all_agent_ids,
        upgrade_start_time_s,
        upgrade_stagger_s,
        upgrade_order,
        miner_ids,
        simulation_seed,
    )

    # Calculate when the last upgrade completes
    last_upgrade_complete_s = max(p1_start for _, (_, p1_start) in upgrade_schedule.items())

    # Calculate total simulation duration
    requested_duration_s = parse_duration(duration) if duration else 0
    min_duration_s = last_upgrade_complete_s + post_upgrade_duration_s
    duration_s = max(requested_duration_s, min_duration_s)
    duration = format_time_offset(duration_s)

    # Build agents with phased daemons
    agents = OrderedDict()

    # Add miners with phased daemons
    for i, miner in enumerate(FIXED_MINERS):
        agent_id = f"miner-{i+1:03}"
        phase0_stop, phase1_start = upgrade_schedule[agent_id]
        agents[agent_id] = generate_miner_agent_phased(
            miner["hashrate"],
            miner["start_offset_s"],
            upgrade_binary_v1,
            upgrade_binary_v2,
            phase0_stop,
            phase1_start,
        )

    # Resolve auto-detected activity batching (0 = auto from user count and tx_interval)
    activity_batch_size, activity_batch_interval_s = resolve_activity_batching(
        activity_batch_size, activity_batch_interval_s, num_users, tx_interval)

    # Calculate staggered activity start times to prevent thundering herd
    user_activity_times = calculate_activity_start_times(
        num_users=num_users,
        base_activity_start_s=activity_start_time_s,
        batch_size=activity_batch_size,
        batch_interval_s=activity_batch_interval_s,
        jitter_fraction=activity_batch_jitter,
        seed=simulation_seed,
    )

    # Calculate activity rollout duration for metadata
    if num_users > 0:
        num_activity_batches = (num_users + activity_batch_size - 1) // activity_batch_size
        activity_rollout_duration_s = (num_activity_batches - 1) * activity_batch_interval_s
    else:
        activity_rollout_duration_s = 0

    # Add users with phased daemons
    if use_batched and batch_schedule:
        for user_index, start_time_s in batch_schedule:
            agent_id = f"user-{user_index+1:03}"
            phase0_stop, phase1_start = upgrade_schedule[agent_id]
            user_activity_time = user_activity_times[user_index] if user_index < len(user_activity_times) else activity_start_time_s
            agents[agent_id] = generate_user_agent_phased(
                start_time_s,
                tx_interval,
                user_activity_time,
                upgrade_binary_v1,
                upgrade_binary_v2,
                phase0_stop,
                phase1_start,
                tx_send_probability,
            )
    else:
        for i in range(num_users):
            agent_id = f"user-{i+1:03}"
            start_offset_s = USER_START_TIME_S + (i * stagger_interval_s)
            phase0_stop, phase1_start = upgrade_schedule[agent_id]
            user_activity_time = user_activity_times[i] if i < len(user_activity_times) else activity_start_time_s
            agents[agent_id] = generate_user_agent_phased(
                start_offset_s,
                tx_interval,
                user_activity_time,
                upgrade_binary_v1,
                upgrade_binary_v2,
                phase0_stop,
                phase1_start,
                tx_send_probability,
            )

    # Add relay nodes with phased daemons (daemon-only, no wallet or script)
    # Simple linear stagger: start + i * stagger
    for i in range(relay_nodes):
        agent_id = f"relay-{i+1:03}"
        relay_start_s = relay_spawn_start_s + (i * relay_stagger_s)
        phase0_stop, phase1_start = upgrade_schedule[agent_id]
        agents[agent_id] = generate_relay_agent_phased(
            relay_start_s,
            upgrade_binary_v1,
            upgrade_binary_v2,
            phase0_stop,
            phase1_start,
        )

    # Calculate last relay spawn time for metadata/warnings
    if relay_nodes > 0:
        last_relay_spawn_s = relay_spawn_start_s + ((relay_nodes - 1) * relay_stagger_s)
        if last_relay_spawn_s > bootstrap_end_time_s:
            print(f"Warning: Last relay spawn ({format_time_offset(last_relay_spawn_s, for_config=False)}) "
                  f"exceeds bootstrap_end_time ({format_time_offset(bootstrap_end_time_s, for_config=False)}). "
                  f"Late relays may experience packet loss during sync.",
                  file=sys.stderr)
    else:
        last_relay_spawn_s = 0

    # Add miner-distributor (md_start_time_s calculated earlier in timing chain)
    agents["miner-distributor"] = OrderedDict([
        ("script", "agents.miner_distributor"),
        ("wait_time", md_start_time_s),  # When Shadow starts the process
        ("initial_wait_time", 0),  # No additional Python wait (Shadow handles timing)
        ("max_transaction_amount", "2.0"),
        ("min_transaction_amount", "0.5"),
        ("transaction_frequency", 30),
        ("md_n_recipients", md_n_recipients),
        ("md_out_per_tx", md_out_per_tx),
        ("md_output_amount", md_output_amount),
        ("md_funding_cycle_interval", md_funding_cycle_interval),
    ])

    # Add simulation-monitor
    agents["simulation-monitor"] = OrderedDict([
        ("script", "agents.simulation_monitor"),
        ("poll_interval", poll_interval),
        ("detailed_logging", False),
        ("enable_alerts", True),
        ("status_file", "monerosim_monitor.log"),
    ])

    # Build general config
    general_config = OrderedDict([
        ("stop_time", duration),
        ("parallelism", parallelism),
        ("simulation_seed", simulation_seed),
        ("enable_dns_server", True),
        ("shadow_log_level", shadow_log_level),
        ("bootstrap_end_time", format_time_offset(bootstrap_end_time_s)),
        ("progress", True),
    ])

    if runahead:
        general_config["runahead"] = runahead

    if process_threads != 1:
        general_config["process_threads"] = process_threads

    # Add native_preemption only when explicitly set
    if native_preemption is not None:
        general_config["native_preemption"] = native_preemption

    general_config["daemon_defaults"] = OrderedDict([
        ("log-level", 1),
        ("log-file", "/dev/stdout"),
        ("db-sync-mode", "fastest"),
        ("no-zmq", True),
        ("non-interactive", True),
        ("disable-rpc-ban", True),
        ("allow-local-ip", True),
    ])

    general_config["wallet_defaults"] = OrderedDict([
        ("log-level", 1),
        ("log-file", "/dev/stdout"),
    ])

    timing_info = {
        'bootstrap_end_time_s': bootstrap_end_time_s,
        'md_start_time_s': md_start_time_s,
        'activity_start_time_s': activity_start_time_s,
        'last_user_spawn_s': last_user_spawn_s,
        'user_spawn_start_s': user_spawn_start_s,
        'duration_s': duration_s,
        'requested_duration_s': requested_duration_s,
        'use_batched': use_batched,
        'batch_sizes': batch_sizes,
        'batch_interval_s': batch_interval_s,
        # Activity batching info
        'activity_batching_enabled': True,
        'activity_batch_size': activity_batch_size,
        'activity_batch_interval_s': activity_batch_interval_s,
        'activity_batch_jitter': activity_batch_jitter,
        'activity_rollout_duration_s': activity_rollout_duration_s,
        # Relay timing info
        'relay_spawn_start_s': relay_spawn_start_s,
        'relay_stagger_s': relay_stagger_s,
        'last_relay_spawn_s': last_relay_spawn_s,
        # Upgrade-specific timing info
        'upgrade_start_time_s': upgrade_start_time_s,
        'last_upgrade_complete_s': last_upgrade_complete_s,
        'upgrade_binary_v1': upgrade_binary_v1,
        'upgrade_binary_v2': upgrade_binary_v2,
        'upgrade_order': upgrade_order,
        'upgrade_stagger_s': upgrade_stagger_s,
        'steady_state_duration_s': steady_state_duration_s,
        'post_upgrade_duration_s': post_upgrade_duration_s,
    }

    # Generate metadata section
    metadata = generate_metadata(
        scenario="upgrade",
        num_miners=num_miners,
        num_users=num_users,
        timing_info=timing_info,
        simulation_seed=simulation_seed,
        gml_path=gml_path,
        fast_mode=fast_mode,
        stagger_interval_s=stagger_interval_s,
        relay_nodes=relay_nodes,
    )

    # Build full config with metadata first
    config = OrderedDict([
        ("metadata", metadata),
        ("general", general_config),
        ("network", OrderedDict([
            ("path", gml_path),
            ("peer_mode", "Dynamic"),
        ])),
        ("agents", agents),
    ])

    return config, timing_info


def config_to_yaml(config: Dict[str, Any], indent: int = 0) -> str:
    """Convert config dict to YAML string manually for clean output."""
    lines = []
    prefix = "  " * indent

    for key, value in config.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(config_to_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    # First key-value on same line as dash
                    first = True
                    for k, v in item.items():
                        if first:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}  - {k}:")
                                lines.append(config_to_yaml(v, indent + 3))
                            elif isinstance(v, bool):
                                lines.append(f"{prefix}  - {k}: {str(v).lower()}")
                            else:
                                lines.append(f"{prefix}  - {k}: {format_yaml_value(v)}")
                            first = False
                        else:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}    {k}:")
                                lines.append(config_to_yaml(v, indent + 3))
                            elif isinstance(v, bool):
                                lines.append(f"{prefix}    {k}: {str(v).lower()}")
                            else:
                                lines.append(f"{prefix}    {k}: {format_yaml_value(v)}")
                else:
                    lines.append(f"{prefix}  - {format_yaml_value(item)}")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {str(value).lower()}")
        else:
            lines.append(f"{prefix}{key}: {format_yaml_value(value)}")

    return "\n".join(lines)


def format_yaml_value(value: Any) -> str:
    """Format a value for YAML output."""
    if isinstance(value, str):
        # Quote strings that might be parsed as other types
        if value.lower() in ('true', 'false', 'yes', 'no', 'on', 'off', 'null', 'none'):
            return f"'{value}'"
        # Quote strings with special characters
        if any(c in value for c in ':{}[]&*#?|-<>=!%@\\'):
            return f"'{value}'"
        # Quote strings that look like numbers
        try:
            float(value)
            return f"'{value}'"
        except ValueError:
            pass
        return value
    elif isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)


def main():
    parser = argparse.ArgumentParser(
        description="Generate monerosim configs for scaling tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/generate_config.py --agents 50 -o test_50.yaml
    python scripts/generate_config.py --agents 100 --duration 8h -o test_100.yaml
    python scripts/generate_config.py --agents 800 --stagger-interval 1 -o test_800.yaml

The config includes 5 fixed miners (hashrates: 25, 25, 30, 10, 10).
Timeline (verified bootstrap for Monero regtest):
  t=0:  Miners start
  t=3h: Users spawn (sync during last hour of bootstrap)
  t=4h: Bootstrap ends, miner distributor starts funding users
  t=5h: Users start sending transactions
        """
    )

    parser.add_argument(
        "--agents", "-n",
        type=int,
        default=None,
        help="Total agent count (5 miners + N-5 users). Required unless using --from."
    )

    parser.add_argument(
        "--duration", "-d",
        type=str,
        default="8h",
        help="Simulation duration (default: 8h, activity starts at 5h)"
    )

    parser.add_argument(
        "--stagger-interval",
        type=int,
        default=5,
        help="Seconds between user starts (default: 5, use 0 for all-at-once)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="Simulation seed (default: 12345)"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output filename"
    )

    parser.add_argument(
        "--from", "-f",
        dest="from_scenario",
        type=str,
        default=None,
        help="Expand a scenario.yaml file instead of generating from CLI args"
    )

    parser.add_argument(
        "--gml",
        type=str,
        default=DEFAULT_GML_PATH,
        help=f"Path to GML topology file (default: {DEFAULT_GML_PATH})"
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use performance-friendly settings: runahead=100ms, shadow_log_level=warning, poll_interval=300, tx_interval=120"
    )

    parser.add_argument(
        "--tx-interval",
        type=int,
        default=None,
        help="Seconds between user transaction attempts (default: 120 in fast mode, 60 otherwise). "
             "Overrides the fast-mode default when specified."
    )

    parser.add_argument(
        "--tx-send-probability",
        type=float,
        default=0.75,
        help="Probability (0.0-1.0) that a user sends a transaction each iteration (default: 0.75)"
    )

    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Thread count for monerod/wallet-rpc (0=auto, 1=single-threaded for determinism, 2+=explicit count)"
    )

    parser.add_argument(
        "--native-preemption",
        action="store_true",
        default=False,
        help="Enable Shadow native preemption (timer-based thread preemption). "
             "Prevents thread starvation but breaks simulation determinism."
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        default=0,
        help="Shadow worker thread count (0=auto-detect CPU cores, default). "
             "Shadow parallelism is deterministic — it doesn't affect simulation results, just wall-clock speed."
    )

    parser.add_argument(
        "--close-to-deterministic",
        action="store_true",
        default=False,
        help="Meta-flag for maximum reproducibility. Forces native_preemption=false and process_threads=1. "
             "Overrides --native-preemption and --threads if specified."
    )

    # Batched bootstrap options for large-scale simulations
    parser.add_argument(
        "--batched-bootstrap",
        choices=["auto", "true", "false"],
        default="auto",
        help="Enable batched user startup for large sims (auto=enable if >50 users, true=always, false=never)"
    )

    parser.add_argument(
        "--batch-interval",
        type=str,
        default="20m",
        help="Time between batches (default: 20m)"
    )

    parser.add_argument(
        "--initial-batch-size",
        type=int,
        default=5,
        help="Size of first user batch (default: 5)"
    )

    parser.add_argument(
        "--max-batch-size",
        type=int,
        default=200,
        help="Maximum users per batch (default: 200)"
    )

    parser.add_argument(
        "--daemon-binary",
        type=str,
        default="monerod",
        help="Daemon binary path or name (default: monerod, resolves to ~/.monerosim/bin/monerod)"
    )

    parser.add_argument(
        "--relay-nodes",
        type=int,
        default=0,
        help="Number of daemon-only relay nodes (no wallet/script, P2P relay only). Default: 0"
    )

    parser.add_argument(
        "--relay-spawn-start",
        type=str,
        default="5s",
        help="When relay nodes start spawning (default: 5s, after miners)"
    )

    parser.add_argument(
        "--relay-stagger",
        type=str,
        default="20s",
        help="Interval between relay node spawns (default: 20s). "
             "With 895 relays at 20s stagger, all online in ~5h."
    )

    # Timing control flags
    parser.add_argument(
        "--user-spawn-start",
        type=str,
        default=None,
        help="When users start spawning (default: 20m for batched, 3h for non-batched)"
    )

    parser.add_argument(
        "--bootstrap-end-time",
        type=str,
        default=None,
        help="When bootstrap ends and network transitions to normal mode (default: auto-calc from user spawns)"
    )

    parser.add_argument(
        "--regular-user-start",
        type=str,
        default=None,
        help="When regular users start transacting (default: md_start_time + 1h)"
    )

    # Miner distributor options (all prefixed with md_)
    parser.add_argument(
        "--md-start-time",
        type=str,
        default=None,
        help="Miner distributor: when to start (default: bootstrap_end_time)"
    )

    parser.add_argument(
        "--md-n-recipients",
        type=int,
        default=8,
        help="Miner distributor: recipients per batch transaction (default: 8). "
             "NOTE: recipients * outputs_per_tx must be <= 16 (Monero tx size limit)"
    )

    parser.add_argument(
        "--md-out-per-tx",
        type=int,
        default=2,
        help="Miner distributor: outputs per recipient per transaction (default: 2). "
             "NOTE: recipients * outputs_per_tx must be <= 16 (Monero tx size limit)"
    )

    parser.add_argument(
        "--md-output-amount",
        type=float,
        default=5.0,
        help="Miner distributor: XMR amount per output (default: 5.0)"
    )

    parser.add_argument(
        "--md-funding-cycle-interval",
        type=str,
        default="5m",
        help="Miner distributor: interval between continuous funding cycles (default: 5m). "
             "Accepts time durations like '2m', '300s', '5m'."
    )

    # User activity batching options (prevents thundering herd when all users try to transact at once)
    parser.add_argument(
        "--activity-batch-size",
        type=int,
        default=DEFAULT_ACTIVITY_BATCH_SIZE,
        help="Users per activity batch (0=auto-detect, default). "
             "Auto-detection caps at 5 concurrent wallets (proven safe for ring construction). "
             "Staggers when users start sending transactions to prevent overwhelming the network."
    )

    parser.add_argument(
        "--activity-batch-interval",
        type=str,
        default="auto",
        help="Target time between activity batches (default: auto). "
             "'auto' spreads batches across one tx_interval period (min 120s between batches). "
             "Accepts time durations like '2m', '300s', '5m' for explicit override."
    )

    parser.add_argument(
        "--activity-batch-jitter",
        type=float,
        default=DEFAULT_ACTIVITY_BATCH_JITTER,
        help=f"Random jitter fraction +/- for activity start times (default: {DEFAULT_ACTIVITY_BATCH_JITTER}). "
             "E.g., 0.3 means each user's start time varies +/-30%% of the batch interval."
    )

    # Upgrade scenario options
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["default", "upgrade"],
        default="default",
        help="Scenario type: 'default' for standard scaling test, 'upgrade' for network upgrade simulation"
    )

    parser.add_argument(
        "--upgrade-binary-v1",
        type=str,
        default="monerod",
        help="Phase 0 daemon binary for upgrade scenario (default: monerod)"
    )

    parser.add_argument(
        "--upgrade-binary-v2",
        type=str,
        default="monerod",
        help="Phase 1 daemon binary for upgrade scenario (default: monerod)"
    )

    parser.add_argument(
        "--upgrade-start",
        type=str,
        default=None,
        help="When upgrades begin in upgrade scenario (default: auto = activity_start + steady_state_duration)"
    )

    parser.add_argument(
        "--upgrade-stagger",
        type=str,
        default="30s",
        help="Time between node upgrades (default: 30s)"
    )

    parser.add_argument(
        "--upgrade-order",
        type=str,
        choices=["sequential", "random", "miners-first"],
        default="sequential",
        help="Order in which nodes upgrade: sequential, random, or miners-first (default: sequential)"
    )

    parser.add_argument(
        "--steady-state-duration",
        type=str,
        default="2h",
        help="How long to observe before upgrade (default: 2h)"
    )

    parser.add_argument(
        "--post-upgrade-duration",
        type=str,
        default="2h",
        help="How long to observe after upgrade completes (default: 2h)"
    )

    args = parser.parse_args()

    # Handle --from scenario.yaml mode
    if args.from_scenario:
        from scenario_parser import (
            parse_scenario, expand_scenario, format_time,
            DEFAULT_AUTO_THRESHOLD, calculate_batched_schedule
        )

        print(f"Expanding scenario: {args.from_scenario}", file=sys.stderr)

        with open(args.from_scenario) as f:
            scenario = parse_scenario(f.read())

        # Expand with seed from args (or scenario if specified)
        seed = scenario.general.get('simulation_seed', args.seed)
        config = expand_scenario(scenario, seed=seed)

        # Convert to YAML
        def to_plain_dict(obj):
            if hasattr(obj, 'items'):
                return {k: to_plain_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [to_plain_dict(i) for i in obj]
            return obj

        plain_config = to_plain_dict(config)

        # Count agents for summary
        agent_count = len([k for k in config['agents'].keys()
                          if k not in ['miner-distributor', 'simulation-monitor']])

        # Write output
        import yaml as yaml_module
        with open(args.output, 'w') as f:
            yaml_module.dump(plain_config, f, default_flow_style=False, sort_keys=False)

        print(f"Expanded {args.from_scenario} -> {args.output}", file=sys.stderr)
        print(f"  Agents: {agent_count}", file=sys.stderr)
        print(f"  Bootstrap ends: {format_time(scenario.timing['bootstrap_end_s'])}", file=sys.stderr)
        print(f"  Activity starts: {format_time(scenario.timing['activity_start_s'])}", file=sys.stderr)
        sys.exit(0)

    # Validate CLI args (only if not using --from)
    if args.agents is None:
        print("Error: --agents is required when not using --from", file=sys.stderr)
        sys.exit(1)

    if args.agents < 5:
        print(f"Error: Need at least 5 agents (for fixed miners), got {args.agents}", file=sys.stderr)
        sys.exit(1)

    if args.stagger_interval < 0:
        print(f"Error: Stagger interval must be >= 0, got {args.stagger_interval}", file=sys.stderr)
        sys.exit(1)

    # Apply --close-to-deterministic overrides
    native_preemption = None  # Default: don't set (Shadow default false applies)
    parallelism = args.parallelism
    process_threads = args.threads

    if args.close_to_deterministic:
        # Force deterministic settings, overriding --native-preemption and --threads
        native_preemption = False  # Explicitly disable timer-based preemption
        process_threads = 1  # Single-threaded Monero processes
        if args.native_preemption:
            print("Note: --close-to-deterministic overrides --native-preemption (forcing off)", file=sys.stderr)
        if args.threads != 1:
            print(f"Note: --close-to-deterministic overrides --threads {args.threads} (forcing 1)", file=sys.stderr)
    elif args.native_preemption:
        native_preemption = True  # Explicitly enable

    # Generate config based on scenario
    num_users = args.agents - 5

    try:
        if args.scenario == "upgrade":
            config, timing_info = generate_upgrade_config(
                total_agents=args.agents,
                duration=args.duration,
                stagger_interval_s=args.stagger_interval,
                simulation_seed=args.seed,
                gml_path=args.gml,
                fast_mode=args.fast,
                process_threads=process_threads,
                batched_bootstrap=args.batched_bootstrap,
                batch_interval=args.batch_interval,
                initial_batch_size=args.initial_batch_size,
                max_batch_size=args.max_batch_size,
                user_spawn_start=args.user_spawn_start,
                bootstrap_end_time=args.bootstrap_end_time,
                regular_user_start=args.regular_user_start,
                md_start_time=args.md_start_time,
                md_n_recipients=args.md_n_recipients,
                md_out_per_tx=args.md_out_per_tx,
                md_output_amount=args.md_output_amount,
                md_funding_cycle_interval=args.md_funding_cycle_interval,
                tx_interval=args.tx_interval,
                tx_send_probability=args.tx_send_probability,
                activity_batch_size=args.activity_batch_size,
                activity_batch_interval_s=0 if args.activity_batch_interval == "auto" else parse_duration(args.activity_batch_interval),
                activity_batch_jitter=args.activity_batch_jitter,
                parallelism=parallelism,
                native_preemption=native_preemption,
                relay_nodes=args.relay_nodes,
                relay_spawn_start_s=parse_duration(args.relay_spawn_start),
                relay_stagger_s=parse_duration(args.relay_stagger),
                upgrade_binary_v1=args.upgrade_binary_v1,
                upgrade_binary_v2=args.upgrade_binary_v2,
                upgrade_start=args.upgrade_start,
                upgrade_stagger_s=parse_duration(args.upgrade_stagger),
                upgrade_order=args.upgrade_order,
                steady_state_duration_s=parse_duration(args.steady_state_duration),
                post_upgrade_duration_s=parse_duration(args.post_upgrade_duration),
            )
        else:
            config, timing_info = generate_config(
                total_agents=args.agents,
                duration=args.duration,
                stagger_interval_s=args.stagger_interval,
                simulation_seed=args.seed,
                gml_path=args.gml,
                fast_mode=args.fast,
                process_threads=process_threads,
                batched_bootstrap=args.batched_bootstrap,
                batch_interval=args.batch_interval,
                initial_batch_size=args.initial_batch_size,
                max_batch_size=args.max_batch_size,
                daemon_binary=args.daemon_binary,
                user_spawn_start=args.user_spawn_start,
                bootstrap_end_time=args.bootstrap_end_time,
                regular_user_start=args.regular_user_start,
                md_start_time=args.md_start_time,
                md_n_recipients=args.md_n_recipients,
                md_out_per_tx=args.md_out_per_tx,
                md_output_amount=args.md_output_amount,
                md_funding_cycle_interval=args.md_funding_cycle_interval,
                tx_interval=args.tx_interval,
                tx_send_probability=args.tx_send_probability,
                activity_batch_size=args.activity_batch_size,
                activity_batch_interval_s=0 if args.activity_batch_interval == "auto" else parse_duration(args.activity_batch_interval),
                activity_batch_jitter=args.activity_batch_jitter,
                parallelism=parallelism,
                native_preemption=native_preemption,
                relay_nodes=args.relay_nodes,
                relay_spawn_start_s=parse_duration(args.relay_spawn_start),
                relay_stagger_s=parse_duration(args.relay_stagger),
            )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert to YAML
    yaml_content = config_to_yaml(config)

    # Format timing values (human-readable for header comments)
    bootstrap_end = format_time_offset(timing_info['bootstrap_end_time_s'], for_config=False)
    activity_start = format_time_offset(timing_info['activity_start_time_s'], for_config=False)
    last_spawn = format_time_offset(timing_info['last_user_spawn_s'], for_config=False)
    actual_duration = format_time_offset(timing_info['duration_s'], for_config=False)

    # Check if duration was extended
    duration_extended = timing_info['duration_s'] > timing_info['requested_duration_s']
    duration_note = f" (extended from {args.duration})" if duration_extended else ""

    # Batched bootstrap info
    use_batched = timing_info['use_batched']
    batch_sizes = timing_info['batch_sizes']
    batch_interval_s = timing_info['batch_interval_s']

    # Activity batching info
    activity_batch_size = timing_info.get('activity_batch_size', DEFAULT_ACTIVITY_BATCH_SIZE)
    activity_batch_interval_s = timing_info.get('activity_batch_interval_s', DEFAULT_ACTIVITY_BATCH_INTERVAL_S)
    activity_batch_jitter = timing_info.get('activity_batch_jitter', DEFAULT_ACTIVITY_BATCH_JITTER)
    activity_rollout_s = timing_info.get('activity_rollout_duration_s', 0)

    fast_note = " [FAST MODE]" if args.fast else ""
    stagger_note = f"staggered {args.stagger_interval}s apart" if args.stagger_interval > 0 else "all at once"

    # Relay node info for header
    relay_nodes = args.relay_nodes
    relay_agent_note = f" + {relay_nodes} relays" if relay_nodes > 0 else ""
    if relay_nodes > 0:
        last_relay_spawn_s = timing_info['last_relay_spawn_s']
        relay_spawn_start_s_val = timing_info['relay_spawn_start_s']
        relay_stagger_s_val = timing_info['relay_stagger_s']
        last_relay_str = format_time_offset(last_relay_spawn_s, for_config=False)
        relay_timeline_note = f"\n#   t={format_time_offset(relay_spawn_start_s_val, for_config=False)}:      Relay nodes start spawning ({relay_nodes} nodes, {relay_stagger_s_val}s apart)\n#   t={last_relay_str}:  Last relay spawns"
    else:
        relay_timeline_note = ""

    user_spawn_start_s = timing_info['user_spawn_start_s']
    if use_batched and batch_sizes:
        batch_summary = format_batch_summary(batch_sizes, user_spawn_start_s, batch_interval_s)
        batched_note = f"\n# {batch_summary}"
        spawn_note = "Users spawn in batches (see below)"
    else:
        batched_note = ""
        spawn_note = f"Users spawn ({stagger_note})"

    # Activity batching note
    activity_rollout_str = format_time_offset(activity_rollout_s, for_config=False)
    activity_interval_str = format_time_offset(activity_batch_interval_s, for_config=False)
    activity_batching_note = f"""#
# Activity batching (prevents thundering herd):
#   Batch size: {activity_batch_size} users
#   Batch interval: {activity_interval_str} (+/-{int(activity_batch_jitter*100)}% jitter)
#   Total rollout: ~{activity_rollout_str}"""

    # Generate header based on scenario
    if args.scenario == "upgrade":
        upgrade_start = format_time_offset(timing_info['upgrade_start_time_s'], for_config=False)
        upgrade_end = format_time_offset(timing_info['last_upgrade_complete_s'], for_config=False)
        header = f"""# Monerosim upgrade scenario configuration{fast_note}
# Generated by generate_config.py --scenario upgrade
# Total agents: {args.agents} (5 miners + {num_users} users{relay_agent_note})
# Duration: {actual_duration}{duration_note}
# Network topology: {args.gml}
#
# Upgrade configuration:
#   Binary v1: {timing_info['upgrade_binary_v1']}
#   Binary v2: {timing_info['upgrade_binary_v2']}
#   Upgrade order: {timing_info['upgrade_order']}
#   Upgrade stagger: {args.upgrade_stagger}
{activity_batching_note}
#
# Timeline:
#   t=0:           Miners start{relay_timeline_note}
#   t={format_time_offset(user_spawn_start_s, for_config=False)}:         {spawn_note}
#   t={last_spawn}:     Last user spawns
#   t={bootstrap_end}:     Bootstrap ends (+20% buffer), distributor starts funding
#   t={activity_start}:     Users start sending transactions (staggered over ~{activity_rollout_str})
#   t={upgrade_start}:     Network upgrade begins (nodes switch v1 -> v2)
#   t={upgrade_end}:    Last node completes upgrade
#   t={actual_duration}:    Simulation ends (post-upgrade observation){batched_note}
"""
    else:
        header = f"""# Monerosim scaling test configuration{fast_note}
# Generated by generate_config.py
# Total agents: {args.agents} (5 miners + {num_users} users{relay_agent_note})
# Duration: {actual_duration}{duration_note}
# Network topology: {args.gml}
{activity_batching_note}
#
# Timeline:
#   t=0:       Miners start{relay_timeline_note}
#   t={format_time_offset(user_spawn_start_s, for_config=False)}:      {spawn_note}
#   t={last_spawn}:  Last user spawns
#   t={bootstrap_end}:  Bootstrap ends (+20% buffer), distributor starts funding
#   t={activity_start}:  Users start sending transactions (staggered over ~{activity_rollout_str}){batched_note}
"""

    if args.fast:
        header += """# Fast mode settings: runahead=100ms, shadow_log_level=warning, poll_interval=300, tx_interval=120
"""
    header += "\n"

    # Write output
    with open(args.output, 'w') as f:
        f.write(header + yaml_content + "\n")

    # Print summary
    fast_msg = " (fast mode)" if args.fast else ""
    threads_msg = f", threads={process_threads}" if process_threads != 1 else ""
    deterministic_msg = " [close-to-deterministic]" if args.close_to_deterministic else ""
    preemption_msg = ", native_preemption=true" if native_preemption is True else ""
    duration_msg = f", duration extended to {actual_duration}" if duration_extended else ""

    if args.scenario == "upgrade":
        print(f"Generated upgrade scenario config with {args.agents} agents ({num_users} users){fast_msg}{threads_msg}{preemption_msg}{deterministic_msg}{duration_msg}")
        print(f"  Binary v1: {args.upgrade_binary_v1} -> v2: {args.upgrade_binary_v2}")
        print(f"  Upgrade order: {args.upgrade_order}, stagger: {args.upgrade_stagger}")
        print(f"  Output: {args.output}")
    else:
        print(f"Generated config with {args.agents} agents ({num_users} users){fast_msg}{threads_msg}{preemption_msg}{deterministic_msg}{duration_msg}, GML: {args.gml} -> {args.output}")


if __name__ == "__main__":
    main()
