#!/usr/bin/env python3
"""
Generate monerosim configuration files with varying agent counts for scaling tests.

Usage:
    python scripts/generate_config.py --agents 50 -o test_50.yaml
    python scripts/generate_config.py --agents 100 -o test_100.yaml
    python scripts/generate_config.py --agents 800 --duration 8h -o test_800.yaml

The generated config has:
- Fixed 5 miners (core network) with hashrates: 25, 25, 30, 10, 10
- Variable users spawning at 3h mark (sync during last hour of bootstrap)
- Bootstrap period until 4h with high bandwidth/no packet loss
- Miner distributor starts at 4h (funds users from miner wallets)
- User activity (transactions) starts at 5h

Timeline (verified bootstrap approach for Monero regtest):
  t=0:  Miners start mining
  t=3h: Users spawn (sync blockchain during bootstrap)
  t=4h: Bootstrap ends, miner distributor starts distributing funds
  t=5h: Users start sending transactions

This timing ensures:
- ~120 blocks mined before distributor starts (60 needed for unlock)
- Sufficient outputs on chain for ring signatures (ring size 16)
- Users fully synced before activity begins
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

# Users spawn at 3h mark (sync during last hour of bootstrap)
USER_START_TIME_S = 10800  # 3 hours in seconds

# Bootstrap ends at 4h (high bandwidth/no packet loss period)
# ~120 blocks should exist by this point (enough for 60-block unlock requirement)
BOOTSTRAP_END_TIME_S = 14400  # 4 hours in seconds

# Activity starts at 5h mark (users start sending transactions)
# Gives 1 hour for miner distributor to fund users after bootstrap ends
ACTIVITY_START_TIME_S = 18000  # 5 hours in seconds

# Note: monerosim only supports seconds resolution (no ms support in duration parser)
# Zero stagger is now the default to create an implicit synchronization barrier


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


def format_time_offset(seconds: int) -> str:
    """Format time offset in the most readable way (seconds resolution only)."""
    if seconds % 3600 == 0 and seconds >= 3600:
        return f"{seconds // 3600}h"
    elif seconds % 60 == 0 and seconds >= 60:
        return f"{seconds // 60}m"
    else:
        return f"{seconds}s"


def generate_miner_agent(hashrate: int, start_offset_s: int) -> Dict[str, Any]:
    """Generate a miner agent configuration (new format)."""
    return OrderedDict([
        ("daemon", "monerod"),
        ("wallet", "monero-wallet-rpc"),
        ("script", "agents.autonomous_miner"),
        ("start_time", format_time_offset(start_offset_s)),
        ("hashrate", hashrate),
        ("can_receive_distributions", True),
    ])


def generate_user_agent(start_offset_s: int, tx_interval: int = 60, activity_start_time: int = 0) -> Dict[str, Any]:
    """Generate a regular user agent configuration (new format).

    Args:
        start_offset_s: When the agent process spawns (sim time)
        tx_interval: Interval between transaction attempts
        activity_start_time: Absolute sim time when transactions should start (0 = start immediately)
    """
    return OrderedDict([
        ("daemon", "monerod"),
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
    """

    num_miners = len(FIXED_MINERS)
    num_users = total_agents - num_miners

    if num_users < 0:
        raise ValueError(f"Total agents ({total_agents}) must be at least {num_miners} (fixed miners)")

    # Performance settings for fast mode
    tx_interval = 120 if fast_mode else 60
    poll_interval = 300  # 5 minutes for reasonable monitoring updates
    shadow_log_level = "warning" if fast_mode else "info"
    runahead = "100ms" if fast_mode else None

    # Activity start time: absolute sim time when transaction activity begins
    # Users spawning before this time will wait; users spawning after will start immediately
    activity_start_time = ACTIVITY_START_TIME_S  # 7200s = 2h

    # Build named agents map (OrderedDict to preserve order)
    agents = OrderedDict()

    # Add fixed miners with explicit IDs
    for i, miner in enumerate(FIXED_MINERS):
        agent_id = f"miner-{i+1:03}"
        agents[agent_id] = generate_miner_agent(miner["hashrate"], miner["start_offset_s"])

    # Add variable users starting at 30m mark (during bootstrap period)
    # Zero stagger creates implicit barrier - all users spawn at same sim time
    for i in range(num_users):
        agent_id = f"user-{i+1:03}"
        start_offset_s = USER_START_TIME_S + (i * stagger_interval_s)
        agents[agent_id] = generate_user_agent(start_offset_s, tx_interval, activity_start_time)

    # Add miner-distributor (starts at bootstrap end to fund users)
    agents["miner-distributor"] = OrderedDict([
        ("script", "agents.miner_distributor"),
        ("wait_time", BOOTSTRAP_END_TIME_S),  # Wait 4h - starts when bootstrap ends
        ("initial_fund_amount", "1.0"),
        ("max_transaction_amount", "2.0"),
        ("min_transaction_amount", "0.5"),
        ("transaction_frequency", 30),
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
        # Bootstrap period: high bandwidth, no packet loss until 4h
        ("bootstrap_end_time", format_time_offset(BOOTSTRAP_END_TIME_S)),
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

    return config


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
        default=0,
        help="Seconds between user starts (default: 0 for implicit barrier)"
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
        config = generate_config(
            total_agents=args.agents,
            duration=args.duration,
            stagger_interval_s=args.stagger_interval,
            simulation_seed=args.seed,
            gml_path=args.gml,
            fast_mode=args.fast,
            process_threads=args.threads,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert to YAML
    yaml_content = config_to_yaml(config)

    # Add header comment
    num_users = args.agents - 5
    fast_note = " [FAST MODE]" if args.fast else ""
    stagger_note = f"staggered {args.stagger_interval}s apart" if args.stagger_interval > 0 else "all at once (implicit barrier)"
    header = f"""# Monerosim scaling test configuration{fast_note}
# Generated by generate_config.py
# Total agents: {args.agents} (5 miners + {num_users} users)
# Duration: {args.duration}
# Network topology: {args.gml}
# Timeline (verified bootstrap for Monero regtest):
#   t=0:  Miners start
#   t=3h: Users spawn ({stagger_note})
#   t=4h: Bootstrap ends, miner distributor starts funding users
#   t=5h: Users start sending transactions
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
    print(f"Generated config with {args.agents} agents ({num_users} users){fast_msg}{threads_msg}, GML: {args.gml} -> {args.output}")


if __name__ == "__main__":
    main()
