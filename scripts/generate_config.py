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
import sys
from typing import Dict, Any
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


def generate_user_agent(start_offset_s: int, tx_interval: int = 60, activity_start_time: int = 0, daemon_binary: str = "monerod") -> Dict[str, Any]:
    """Generate a regular user agent configuration (new format).

    Args:
        start_offset_s: When the agent process spawns (sim time)
        tx_interval: Interval between transaction attempts
        activity_start_time: Absolute sim time when transactions should start (0 = start immediately)
        daemon_binary: Path to monerod binary (default: "monerod")
    """
    return OrderedDict([
        ("daemon", daemon_binary),
        ("wallet", "monero-wallet-rpc"),
        ("script", "agents.regular_user"),
        ("start_time", format_time_offset(start_offset_s)),
        ("transaction_interval", tx_interval),
        ("activity_start_time", activity_start_time),
        ("can_receive_distributions", True),
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
    outputs_per_transaction: int = 10,
    output_amount: float = 100.0,
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
        outputs_per_transaction: Number of outputs per transaction (multiple to same recipient)
        output_amount: Fixed XMR amount per output
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

    # Calculate user start times based on batching mode
    batch_sizes = []
    batch_schedule = []

    if use_batched and num_users > 0:
        # Batched bootstrap: users start in waves
        batch_sizes = calculate_batch_sizes(num_users, initial_batch_size, 2.0, max_batch_size)
        batch_schedule = calculate_batch_schedule(
            num_users,
            DEFAULT_INITIAL_DELAY_S,
            batch_interval_s,
            initial_batch_size,
            2.0,  # growth_factor
            max_batch_size,
            DEFAULT_INTRA_BATCH_STAGGER_S,
        )
        # Last user spawn time from batch schedule
        last_user_spawn_s = batch_schedule[-1][1] if batch_schedule else 0
    else:
        # Non-batched: users start at USER_START_TIME_S with stagger
        if num_users > 0:
            last_user_spawn_s = USER_START_TIME_S + ((num_users - 1) * stagger_interval_s)
        else:
            last_user_spawn_s = USER_START_TIME_S

    # Calculate dynamic bootstrap timing
    spawn_with_buffer_s = int(last_user_spawn_s * (1 + BOOTSTRAP_BUFFER_PERCENT))
    bootstrap_end_time_s = max(MIN_BOOTSTRAP_END_TIME_S, spawn_with_buffer_s)
    activity_start_time_s = bootstrap_end_time_s + FUNDING_PERIOD_S

    # Parse and potentially extend duration to ensure minimum activity period
    requested_duration_s = parse_duration(duration)
    min_duration_s = activity_start_time_s + MIN_ACTIVITY_PERIOD_S
    duration_s = max(requested_duration_s, min_duration_s)
    duration = format_time_offset(duration_s)  # Update duration string if extended

    # Performance settings for fast mode
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

    # Add variable users with appropriate start times
    if use_batched and batch_schedule:
        # Batched: use calculated batch schedule
        for user_index, start_time_s in batch_schedule:
            agent_id = f"user-{user_index+1:03}"
            agents[agent_id] = generate_user_agent(start_time_s, tx_interval, activity_start_time_s, daemon_binary)
    else:
        # Non-batched: start at USER_START_TIME_S with stagger
        for i in range(num_users):
            agent_id = f"user-{i+1:03}"
            start_offset_s = USER_START_TIME_S + (i * stagger_interval_s)
            agents[agent_id] = generate_user_agent(start_offset_s, tx_interval, activity_start_time_s, daemon_binary)

    # Add miner-distributor (starts at bootstrap end to fund users)
    agents["miner-distributor"] = OrderedDict([
        ("script", "agents.miner_distributor"),
        ("wait_time", bootstrap_end_time_s),  # Starts when bootstrap ends
        ("initial_fund_amount", "1.0"),
        ("max_transaction_amount", "2.0"),
        ("min_transaction_amount", "0.5"),
        ("transaction_frequency", 30),
        ("outputs_per_transaction", outputs_per_transaction),
        ("output_amount", output_amount),
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
        ("parallelism", 0),
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

    # Build full config
    config = OrderedDict([
        ("general", general_config),
        ("network", OrderedDict([
            ("path", gml_path),
            ("peer_mode", "Dynamic"),
        ])),
        ("agents", agents),
    ])

    # Return config and timing info for header generation
    timing_info = {
        'bootstrap_end_time_s': bootstrap_end_time_s,
        'activity_start_time_s': activity_start_time_s,
        'last_user_spawn_s': last_user_spawn_s,
        'duration_s': duration_s,
        'requested_duration_s': requested_duration_s,
        'use_batched': use_batched,
        'batch_sizes': batch_sizes,
        'batch_interval_s': batch_interval_s,
    }

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
        required=True,
        help="Total agent count (5 miners + N-5 users)"
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
        "--threads",
        type=int,
        default=1,
        help="Thread count for monerod/wallet-rpc (0=auto, 1=single-threaded for determinism, 2+=explicit count)"
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

    # Multi-output transaction options for miner distributor
    parser.add_argument(
        "--md-outputs-per-tx",
        type=int,
        default=10,
        help="Miner distributor: outputs per transaction to same recipient (default: 10)"
    )

    parser.add_argument(
        "--md-output-amount",
        type=float,
        default=100.0,
        help="Miner distributor: XMR amount per output (default: 100)"
    )

    args = parser.parse_args()

    # Validate
    if args.agents < 5:
        print(f"Error: Need at least 5 agents (for fixed miners), got {args.agents}", file=sys.stderr)
        sys.exit(1)

    if args.stagger_interval < 0:
        print(f"Error: Stagger interval must be >= 0, got {args.stagger_interval}", file=sys.stderr)
        sys.exit(1)

    # Generate config
    try:
        config, timing_info = generate_config(
            total_agents=args.agents,
            duration=args.duration,
            stagger_interval_s=args.stagger_interval,
            simulation_seed=args.seed,
            gml_path=args.gml,
            fast_mode=args.fast,
            process_threads=args.threads,
            batched_bootstrap=args.batched_bootstrap,
            batch_interval=args.batch_interval,
            initial_batch_size=args.initial_batch_size,
            max_batch_size=args.max_batch_size,
            daemon_binary=args.daemon_binary,
            outputs_per_transaction=args.md_outputs_per_tx,
            output_amount=args.md_output_amount,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert to YAML
    yaml_content = config_to_yaml(config)

    # Add header comment with dynamic timing
    num_users = args.agents - 5
    fast_note = " [FAST MODE]" if args.fast else ""
    stagger_note = f"staggered {args.stagger_interval}s apart" if args.stagger_interval > 0 else "all at once"

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

    if use_batched and batch_sizes:
        batch_summary = format_batch_summary(batch_sizes, DEFAULT_INITIAL_DELAY_S, batch_interval_s)
        batched_note = f"\n# {batch_summary}"
        spawn_note = "Users spawn in batches (see below)"
    else:
        batched_note = ""
        spawn_note = f"Users spawn ({stagger_note})"

    header = f"""# Monerosim scaling test configuration{fast_note}
# Generated by generate_config.py
# Total agents: {args.agents} (5 miners + {num_users} users)
# Duration: {actual_duration}{duration_note}
# Network topology: {args.gml}
# Timeline:
#   t=0:       Miners start
#   t={format_time_offset(DEFAULT_INITIAL_DELAY_S, for_config=False) if use_batched else "3h"}:      {spawn_note}
#   t={last_spawn}:  Last user spawns
#   t={bootstrap_end}:  Bootstrap ends (+20% buffer), distributor starts funding
#   t={activity_start}:  Users start sending transactions{batched_note}
"""
    if args.fast:
        header += """# Fast mode settings: runahead=100ms, shadow_log_level=warning, poll_interval=300, tx_interval=120
"""
    header += "\n"

    # Write output
    with open(args.output, 'w') as f:
        f.write(header + yaml_content + "\n")

    fast_msg = " (fast mode)" if args.fast else ""
    threads_msg = f", threads={args.threads}" if args.threads != 1 else ""
    duration_msg = f", duration extended to {actual_duration}" if duration_extended else ""
    print(f"Generated config with {args.agents} agents ({num_users} users){fast_msg}{threads_msg}{duration_msg}, GML: {args.gml} -> {args.output}")


if __name__ == "__main__":
    main()
