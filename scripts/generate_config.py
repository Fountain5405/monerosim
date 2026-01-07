#!/usr/bin/env python3
"""
Generate monerosim configuration files with varying agent counts for scaling tests.

Usage:
    python scripts/generate_config.py --agents 50 -o test_50.yaml
    python scripts/generate_config.py --agents 100 -o test_100.yaml
    python scripts/generate_config.py --agents 800 --duration 4h -o test_800.yaml

The generated config has:
- Fixed 5 miners (core network) with hashrates: 25, 25, 30, 10, 10
- Variable users (total - 5) starting at 1h mark, staggered 1s apart (seconds resolution)
"""

import argparse
import sys
from typing import List, Dict, Any


# Fixed miner configuration (same as config_32_agents.yaml)
FIXED_MINERS = [
    {"hashrate": 25, "start_offset_s": 0},
    {"hashrate": 25, "start_offset_s": 1},
    {"hashrate": 30, "start_offset_s": 2},
    {"hashrate": 10, "start_offset_s": 3},
    {"hashrate": 10, "start_offset_s": 4},
]

# Users start at 1 hour (after block unlock time)
USER_START_TIME_S = 3600  # 1 hour in seconds

# Note: monerosim only supports seconds resolution (no ms support in duration parser)
# So we stagger users by 1 second intervals


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


def generate_miner_agent(index: int, hashrate: int, start_offset_s: int) -> Dict[str, Any]:
    """Generate a miner agent configuration."""
    return {
        "daemon": "monerod",
        "wallet": "monero-wallet-rpc",
        "mining_script": "agents.autonomous_miner",
        "start_time_offset": format_time_offset(start_offset_s),
        "attributes": {
            "is_miner": "true",
            "hashrate": str(hashrate),
            "can_receive_distributions": True,
        },
    }


def generate_user_agent(index: int, start_offset_s: int) -> Dict[str, Any]:
    """Generate a regular user agent configuration."""
    return {
        "daemon": "monerod",
        "wallet": "monero-wallet-rpc",
        "user_script": "agents.regular_user",
        "start_time_offset": format_time_offset(start_offset_s),
        "attributes": {
            "transaction_interval": "60",
            "can_receive_distributions": True,
        },
    }


DEFAULT_GML_PATH = "gml_processing/caida_connected_sparse_with_loops_fixed.gml"


def generate_config(
    total_agents: int,
    duration: str,
    stagger_interval_s: int,
    simulation_seed: int = 12345,
    gml_path: str = DEFAULT_GML_PATH,
) -> Dict[str, Any]:
    """Generate the complete monerosim configuration."""

    num_miners = len(FIXED_MINERS)
    num_users = total_agents - num_miners

    if num_users < 0:
        raise ValueError(f"Total agents ({total_agents}) must be at least {num_miners} (fixed miners)")

    # Build user_agents list
    user_agents: List[Dict[str, Any]] = []

    # Add fixed miners
    for i, miner in enumerate(FIXED_MINERS):
        user_agents.append(generate_miner_agent(i, miner["hashrate"], miner["start_offset_s"]))

    # Add variable users starting at 1h mark
    for i in range(num_users):
        start_offset_s = USER_START_TIME_S + (i * stagger_interval_s)
        user_agents.append(generate_user_agent(num_miners + i, start_offset_s))

    # Build full config
    config = {
        "general": {
            "stop_time": duration,
            "parallelism": 0,
            "simulation_seed": simulation_seed,
            "enable_dns_server": True,
        },
        "network": {
            "path": gml_path,
            "peer_mode": "Dynamic",
        },
        "agents": {
            "miner_distributor": {
                "script": "agents.miner_distributor",
                "attributes": {
                    "initial_fund_amount": "1.0",
                    "max_transaction_amount": "2.0",
                    "min_transaction_amount": "0.5",
                    "transaction_frequency": "30",
                    "wait_time": "3900",  # Wait ~1h5m for blocks to mature
                },
            },
            "simulation_monitor": {
                "script": "agents.simulation_monitor",
                "poll_interval": 500,
                "detailed_logging": False,
                "enable_alerts": True,
                "status_file": "shadow.data/monerosim_monitor.log",
            },
            "user_agents": user_agents,
        },
    }

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
    python scripts/generate_config.py --agents 100 --duration 4h -o test_100.yaml
    python scripts/generate_config.py --agents 800 --stagger-interval 50 -o test_800.yaml

The config always includes 5 fixed miners (hashrates: 25, 25, 30, 10, 10).
Additional agents are regular users starting at the 1-hour mark.
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
        default="6h",
        help="Simulation duration (default: 6h)"
    )

    parser.add_argument(
        "--stagger-interval",
        type=int,
        default=5,
        help="Seconds between user starts (default: 5)"
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
        help=f"Path to GML network topology file (default: {DEFAULT_GML_PATH})"
    )

    args = parser.parse_args()

    # Validate
    if args.agents < 5:
        print(f"Error: Need at least 5 agents (for fixed miners), got {args.agents}", file=sys.stderr)
        sys.exit(1)

    if args.stagger_interval < 1:
        print(f"Error: Stagger interval must be at least 1 second, got {args.stagger_interval}", file=sys.stderr)
        sys.exit(1)

    # Generate config
    try:
        config = generate_config(
            total_agents=args.agents,
            duration=args.duration,
            stagger_interval_s=args.stagger_interval,
            simulation_seed=args.seed,
            gml_path=args.gml,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert to YAML
    yaml_content = config_to_yaml(config)

    # Add header comment
    num_users = args.agents - 5
    header = f"""# Monerosim scaling test configuration
# Generated by generate_config.py
# Total agents: {args.agents} (5 miners + {num_users} users)
# Duration: {args.duration}
# Network topology: {args.gml}
# Users start at: 1h mark, staggered {args.stagger_interval}s apart

"""

    # Write output
    with open(args.output, 'w') as f:
        f.write(header + yaml_content + "\n")

    print(f"Generated config with {args.agents} agents ({num_users} users), GML: {args.gml} -> {args.output}")


if __name__ == "__main__":
    main()
