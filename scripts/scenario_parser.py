#!/usr/bin/env python3
"""
Scenario parser for compact monerosim configuration files.

Parses scenario.yaml (compact format) and expands to full monerosim.yaml.

Example scenario.yaml:
```yaml
general:
  stop_time: auto  # Calculated based on scenario
  simulation_seed: 12345
  bootstrap_end_time: auto
  # ... other general settings

network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic

agents:
  miner-{001..005}:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    start_time_stagger: 1s
    hashrate: [30, 25, 25, 10, 10]
    can_receive_distributions: true

  user-{001..100}:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 1200s
    start_time_stagger: auto  # Uses batched for large counts
    transaction_interval: 60
    activity_start_time: auto
    can_receive_distributions: true

  miner-distributor:
    script: agents.miner_distributor
    wait_time: auto
    transaction_frequency: 30
```
"""

import re
import yaml
import random
from typing import Dict, Any, List, Tuple, Optional
from collections import OrderedDict
from dataclasses import dataclass, field


# Reuse constants from generate_config
MIN_BOOTSTRAP_END_TIME_S = 14400
BOOTSTRAP_BUFFER_PERCENT = 0.20
FUNDING_PERIOD_S = 3600
DEFAULT_AUTO_THRESHOLD = 50
DEFAULT_INITIAL_DELAY_S = 1200
DEFAULT_BATCH_INTERVAL_S = 1200
DEFAULT_INITIAL_BATCH_SIZE = 5
DEFAULT_GROWTH_FACTOR = 2.0
DEFAULT_MAX_BATCH_SIZE = 200
DEFAULT_INTRA_BATCH_STAGGER_S = 5
DEFAULT_UPGRADE_STAGGER_S = 30
DEFAULT_DAEMON_RESTART_GAP_S = 30


@dataclass
class AgentGroup:
    """Parsed agent group from scenario."""
    id_pattern: str           # e.g., "miner-{001..005}"
    id_prefix: str            # e.g., "miner-"
    id_format: str            # e.g., "{:03d}"
    start_index: int          # e.g., 1
    end_index: int            # e.g., 5
    count: int                # e.g., 5
    properties: Dict[str, Any]

    # Stagger tracking (filled during expansion)
    stagger_fields: Dict[str, Any] = field(default_factory=dict)

    def agent_ids(self) -> List[str]:
        """Generate list of agent IDs."""
        return [f"{self.id_prefix}{self.id_format.format(i)}"
                for i in range(self.start_index, self.end_index + 1)]


@dataclass
class ScenarioConfig:
    """Parsed scenario configuration."""
    general: Dict[str, Any]
    network: Dict[str, Any]
    agent_groups: List[AgentGroup]
    singleton_agents: Dict[str, Dict[str, Any]]

    # Calculated during expansion
    timing: Dict[str, int] = field(default_factory=dict)


def parse_range_pattern(pattern: str) -> Optional[Tuple[str, str, int, int]]:
    """
    Parse agent ID pattern with range syntax.

    Examples:
        "miner-{001..005}" -> ("miner-", "{:03d}", 1, 5)
        "user-{1..100}"    -> ("user-", "{}", 1, 100)
        "spy-{01..10}"     -> ("spy-", "{:02d}", 1, 10)

    Returns:
        (prefix, format_str, start, end) or None if not a range pattern
    """
    match = re.match(r'^(.+?)\{(\d+)\.\.(\d+)\}$', pattern)
    if not match:
        return None

    prefix = match.group(1)
    start_str = match.group(2)
    end_str = match.group(3)

    start = int(start_str)
    end = int(end_str)

    # Determine format based on zero-padding
    if start_str.startswith('0') and len(start_str) > 1:
        width = len(start_str)
        format_str = f"{{:0{width}d}}"
    else:
        format_str = "{}"

    return (prefix, format_str, start, end)


def parse_stagger_value(value: Any, count: int, seed: int) -> Tuple[str, Any]:
    """
    Parse stagger field value.

    Returns:
        (stagger_type, stagger_config)

    Stagger types:
        - "none": No stagger, all same value
        - "linear": Linear stagger (base + i * interval)
        - "batched": Batched spawning for large groups
        - "list": Explicit per-agent values
        - "random": Random value in range per agent
    """
    if value == "auto":
        if count >= DEFAULT_AUTO_THRESHOLD:
            return ("batched", {"auto": True})
        else:
            return ("linear", {"interval": DEFAULT_INTRA_BATCH_STAGGER_S})

    if value == "batched":
        return ("batched", {"auto": True})

    if isinstance(value, list):
        if len(value) == count:
            return ("list", value)
        else:
            raise ValueError(f"List length {len(value)} doesn't match agent count {count}")

    if isinstance(value, dict):
        if "range" in value:
            # Random range: {range: [10, 30]}
            return ("random", {"min": value["range"][0], "max": value["range"][1], "seed": seed})
        if "batch_sizes" in value:
            return ("batched", value)

    if isinstance(value, str):
        # Parse duration string like "5s", "1m"
        return ("linear", {"interval": parse_duration(value)})

    if isinstance(value, (int, float)):
        return ("linear", {"interval": int(value)})

    return ("none", value)


def parse_duration(duration_str: str) -> int:
    """Parse duration string like '4h', '30m', '45s' to seconds."""
    if isinstance(duration_str, (int, float)):
        return int(duration_str)

    duration_str = str(duration_str).strip().lower()

    if duration_str.endswith('h'):
        return int(float(duration_str[:-1]) * 3600)
    elif duration_str.endswith('m'):
        return int(float(duration_str[:-1]) * 60)
    elif duration_str.endswith('s'):
        return int(float(duration_str[:-1]))
    else:
        return int(duration_str)


def parse_scenario(yaml_content: str) -> ScenarioConfig:
    """Parse scenario.yaml content into ScenarioConfig."""
    data = yaml.safe_load(yaml_content)

    general = data.get('general', {})
    network = data.get('network', {})
    agents_raw = data.get('agents', {})

    agent_groups = []
    singleton_agents = {}

    for agent_id, props in agents_raw.items():
        range_info = parse_range_pattern(agent_id)

        if range_info:
            prefix, format_str, start, end = range_info
            count = end - start + 1

            group = AgentGroup(
                id_pattern=agent_id,
                id_prefix=prefix,
                id_format=format_str,
                start_index=start,
                end_index=end,
                count=count,
                properties=props.copy(),
            )
            agent_groups.append(group)
        else:
            singleton_agents[agent_id] = props.copy()

    return ScenarioConfig(
        general=general,
        network=network,
        agent_groups=agent_groups,
        singleton_agents=singleton_agents,
    )


def calculate_batched_schedule(
    count: int,
    initial_delay_s: int = DEFAULT_INITIAL_DELAY_S,
    batch_interval_s: int = DEFAULT_BATCH_INTERVAL_S,
    initial_batch_size: int = DEFAULT_INITIAL_BATCH_SIZE,
    growth_factor: float = DEFAULT_GROWTH_FACTOR,
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
    intra_stagger_s: int = DEFAULT_INTRA_BATCH_STAGGER_S,
) -> List[int]:
    """
    Calculate batched start times for agents.

    Returns list of start times in seconds, one per agent.
    """
    schedule = []
    user_index = 0
    batch_num = 0
    current_batch_size = initial_batch_size

    while user_index < count:
        batch_size = min(current_batch_size, max_batch_size, count - user_index)
        batch_start_time = initial_delay_s + (batch_num * batch_interval_s)

        for i in range(batch_size):
            start_time = batch_start_time + (i * intra_stagger_s)
            schedule.append(start_time)
            user_index += 1

        batch_num += 1
        current_batch_size = int(current_batch_size * growth_factor)

    return schedule


def expand_stagger(
    base_value: Any,
    stagger_type: str,
    stagger_config: Any,
    count: int,
    global_offset: int = 0,
    seed: int = 12345,
) -> List[Any]:
    """
    Expand a value with stagger into per-agent values.

    Args:
        base_value: Base value (e.g., "1200s" for start_time)
        stagger_type: Type of stagger ("linear", "batched", "list", "random", "none")
        stagger_config: Configuration for stagger
        count: Number of agents
        global_offset: Offset for continuing staggers across groups
        seed: Random seed for reproducibility

    Returns:
        List of values, one per agent
    """
    if stagger_type == "none":
        return [base_value] * count

    if stagger_type == "list":
        return stagger_config

    if stagger_type == "random":
        rng = random.Random(seed)
        min_val = stagger_config["min"]
        max_val = stagger_config["max"]
        return [rng.randint(min_val, max_val) for _ in range(count)]

    # Parse base value to seconds if it's a time
    if isinstance(base_value, str) and any(base_value.endswith(u) for u in ['s', 'm', 'h']):
        base_seconds = parse_duration(base_value)
    else:
        base_seconds = base_value if isinstance(base_value, (int, float)) else 0

    if stagger_type == "linear":
        interval = stagger_config.get("interval", 0)
        return [base_seconds + (global_offset + i) * interval for i in range(count)]

    if stagger_type == "batched":
        if stagger_config.get("auto"):
            schedule = calculate_batched_schedule(count)
        else:
            schedule = calculate_batched_schedule(
                count,
                initial_delay_s=stagger_config.get("initial_delay", DEFAULT_INITIAL_DELAY_S),
                batch_interval_s=stagger_config.get("batch_interval", DEFAULT_BATCH_INTERVAL_S),
                initial_batch_size=stagger_config.get("initial_batch", DEFAULT_INITIAL_BATCH_SIZE),
                growth_factor=stagger_config.get("growth_factor", DEFAULT_GROWTH_FACTOR),
                max_batch_size=stagger_config.get("max_batch", DEFAULT_MAX_BATCH_SIZE),
                intra_stagger_s=stagger_config.get("intra_stagger", DEFAULT_INTRA_BATCH_STAGGER_S),
            )
        # Add base offset
        return [base_seconds + t for t in schedule]

    return [base_value] * count


def expand_scenario(scenario: ScenarioConfig, seed: int = 12345) -> Dict[str, Any]:
    """
    Expand scenario config into full monerosim.yaml structure.

    Returns:
        Full configuration dict ready for YAML output
    """
    config = OrderedDict()

    # Track global stagger offsets for upgrade phases (continue across groups)
    upgrade_stagger_offset = 0

    # Track timing for auto calculations
    # Only track start times of "bootstrap participants" - agents with activity_start_time: auto
    # Late-joining agents (with explicit activity_start_time) don't need to sync from genesis
    bootstrap_participant_start_times = []

    # First pass: expand agents and collect timing info
    agents = OrderedDict()

    for group in scenario.agent_groups:
        agent_ids = group.agent_ids()
        props = group.properties

        # Identify stagger fields (fields ending in _stagger)
        stagger_fields = {}
        base_fields = {}

        for key, value in list(props.items()):
            if key.endswith('_stagger'):
                base_key = key[:-8]  # Remove '_stagger'
                stagger_fields[base_key] = value
            else:
                base_fields[key] = value

        # Expand each field
        expanded_values = {}
        for key, value in base_fields.items():
            if key in stagger_fields:
                stagger_value = stagger_fields[key]
                stagger_type, stagger_config = parse_stagger_value(
                    stagger_value, group.count, seed
                )

                # Determine if this stagger continues across groups
                # daemon_* fields continue, others reset
                if key.startswith('daemon_') and ('stop' in key or 'start' in key and '0' not in key):
                    offset = upgrade_stagger_offset
                else:
                    offset = 0

                expanded = expand_stagger(
                    value, stagger_type, stagger_config,
                    group.count, offset, seed
                )
                expanded_values[key] = expanded

                # Update global offset for daemon phases
                if key.startswith('daemon_') and ('stop' in key):
                    upgrade_stagger_offset += group.count
            else:
                # No stagger - same value for all or list
                if isinstance(value, list) and len(value) == group.count:
                    expanded_values[key] = value
                else:
                    expanded_values[key] = [value] * group.count

        # Create individual agent entries
        for i, agent_id in enumerate(agent_ids):
            agent_config = OrderedDict()
            for key, values in expanded_values.items():
                val = values[i]
                # Format time values
                if key in ['start_time', 'daemon_0_start', 'daemon_0_stop',
                          'daemon_1_start', 'daemon_1_stop'] and isinstance(val, (int, float)):
                    agent_config[key] = f"{int(val)}s"
                else:
                    agent_config[key] = val

            agents[agent_id] = agent_config

            # Track start times for bootstrap timing calculation
            # Only count "bootstrap participants" - agents that need to sync from genesis
            # Late-joining agents (start_time > 1h OR explicit activity_start_time) don't affect bootstrap
            if 'start_time' in agent_config:
                st = agent_config['start_time']
                start_time_s = parse_duration(st) if isinstance(st, str) else st

                activity_st = agent_config.get('activity_start_time')
                # Bootstrap participants: start early (< 1h) AND have auto activity_start
                # OR are miners that start early (need to mine during bootstrap)
                is_early_start = start_time_s < 3600  # Within first hour
                has_auto_activity = activity_st == 'auto'
                is_early_miner = (is_early_start and
                                 agent_config.get('script') == 'agents.autonomous_miner')

                is_bootstrap_participant = is_early_start and (has_auto_activity or is_early_miner)

                if is_bootstrap_participant:
                    bootstrap_participant_start_times.append(start_time_s)

    # Add singleton agents
    for agent_id, props in scenario.singleton_agents.items():
        agents[agent_id] = props.copy()

    # Calculate timing based on bootstrap participants only
    last_bootstrap_spawn_s = max(bootstrap_participant_start_times) if bootstrap_participant_start_times else 0
    bootstrap_end_s = max(MIN_BOOTSTRAP_END_TIME_S, int(last_bootstrap_spawn_s * (1 + BOOTSTRAP_BUFFER_PERCENT)))
    activity_start_s = bootstrap_end_s + FUNDING_PERIOD_S

    scenario.timing = {
        'last_bootstrap_spawn_s': last_bootstrap_spawn_s,
        'bootstrap_end_s': bootstrap_end_s,
        'activity_start_s': activity_start_s,
    }

    # Resolve 'auto' values in general section
    general = scenario.general.copy()
    if general.get('bootstrap_end_time') == 'auto':
        general['bootstrap_end_time'] = f"{bootstrap_end_s // 3600}h" if bootstrap_end_s % 3600 == 0 else f"{bootstrap_end_s}s"

    # Resolve 'auto' in agents
    for agent_id, agent_config in agents.items():
        if agent_config.get('activity_start_time') == 'auto':
            agent_config['activity_start_time'] = activity_start_s
        if agent_config.get('wait_time') == 'auto':
            agent_config['wait_time'] = bootstrap_end_s
        if agent_config.get('daemon_0_start') == 'auto':
            agent_config['daemon_0_start'] = agent_config.get('start_time', '0s')
        if agent_config.get('daemon_1_start') == 'auto':
            # daemon_1_start = daemon_0_stop + gap
            stop_time = agent_config.get('daemon_0_stop', '0s')
            if isinstance(stop_time, str):
                stop_s = parse_duration(stop_time)
            else:
                stop_s = stop_time
            agent_config['daemon_1_start'] = f"{stop_s + DEFAULT_DAEMON_RESTART_GAP_S}s"

    # Build final config
    config['general'] = general
    config['network'] = scenario.network
    config['agents'] = agents

    return config


def format_time(seconds: int) -> str:
    """Format seconds to human-readable time string."""
    if seconds % 3600 == 0 and seconds >= 3600:
        return f"{seconds // 3600}h"
    elif seconds % 60 == 0 and seconds >= 60:
        return f"{seconds // 60}m"
    else:
        return f"{seconds}s"


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Expand scenario.yaml to full monerosim.yaml")
    parser.add_argument("input", help="Input scenario.yaml file")
    parser.add_argument("-o", "--output", default="monerosim.yaml", help="Output file")
    parser.add_argument("--seed", type=int, default=12345, help="Random seed")

    args = parser.parse_args()

    with open(args.input) as f:
        scenario = parse_scenario(f.read())

    config = expand_scenario(scenario, seed=args.seed)

    # Convert OrderedDicts to regular dicts for clean YAML output
    def to_plain_dict(obj):
        if isinstance(obj, OrderedDict):
            return {k: to_plain_dict(v) for k, v in obj.items()}
        elif isinstance(obj, dict):
            return {k: to_plain_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [to_plain_dict(i) for i in obj]
        return obj

    plain_config = to_plain_dict(config)

    with open(args.output, 'w') as f:
        yaml.dump(plain_config, f, default_flow_style=False, sort_keys=False)

    print(f"Expanded {args.input} -> {args.output}")
    print(f"  Agents: {len(config['agents'])}")
    print(f"  Bootstrap ends: {format_time(scenario.timing['bootstrap_end_s'])}")
    print(f"  Activity starts: {format_time(scenario.timing['activity_start_s'])}")
