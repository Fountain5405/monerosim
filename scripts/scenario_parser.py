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

# Optional: explicit timing overrides (all fields optional)
timing:
  user_spawn_start: 14h       # When users start spawning (default: 20m batched)
  bootstrap_end_time: 20h     # When bootstrap ends (default: auto-calc)
  md_start_time: 18h          # When miner distributor starts (default: bootstrap_end)
  activity_start_time: 20h    # When users start transacting (default: md_start + 1h)

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
    start_time: 0s
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

# User activity batching defaults (prevents thundering herd when all users try to transact at once)
# Ring signature / Bulletproof construction is CPU-intensive in simulated time, so batches
# need wide spacing to let each batch complete before the next starts.
DEFAULT_ACTIVITY_BATCH_SIZE = 10  # Users per batch
DEFAULT_ACTIVITY_BATCH_INTERVAL_S = 300  # Target seconds between batches (matches generate_config.py)
DEFAULT_ACTIVITY_BATCH_JITTER = 0.30  # +/- 30% randomization per user within batch


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
class TimingOverrides:
    """Explicit timing overrides from scenario file."""
    user_spawn_start: Optional[str] = None      # When users start spawning (e.g., "14h")
    bootstrap_end_time: Optional[str] = None    # When bootstrap ends (e.g., "20h")
    md_start_time: Optional[str] = None         # When miner distributor starts (e.g., "18h")
    activity_start_time: Optional[str] = None   # When users start transacting (e.g., "20h")
    # Activity batching (prevents thundering herd)
    activity_batch_size: Optional[int] = None   # Users per activity batch (default: 10)
    activity_batch_interval: Optional[str] = None  # Time between batches (default: 25s)
    activity_batch_jitter: Optional[float] = None  # Jitter fraction +/- (default: 0.30)


@dataclass
class ScenarioConfig:
    """Parsed scenario configuration."""
    general: Dict[str, Any]
    network: Dict[str, Any]
    agent_groups: List[AgentGroup]
    singleton_agents: Dict[str, Dict[str, Any]]
    timing_overrides: TimingOverrides = field(default_factory=TimingOverrides)

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
    timing_raw = data.get('timing', {})

    # Parse timing overrides
    timing_overrides = TimingOverrides(
        user_spawn_start=timing_raw.get('user_spawn_start'),
        bootstrap_end_time=timing_raw.get('bootstrap_end_time'),
        md_start_time=timing_raw.get('md_start_time'),
        activity_start_time=timing_raw.get('activity_start_time'),
        activity_batch_size=timing_raw.get('activity_batch_size'),
        activity_batch_interval=timing_raw.get('activity_batch_interval'),
        activity_batch_jitter=timing_raw.get('activity_batch_jitter'),
    )

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
        timing_overrides=timing_overrides,
    )


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
        # Always use explicit parameters - they have sensible defaults
        # This allows overrides (like user_spawn_start) to take effect
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

    # Extract timing overrides
    overrides = scenario.timing_overrides
    user_spawn_start_s = parse_duration(overrides.user_spawn_start) if overrides.user_spawn_start else None

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
        is_user_agent = 'regular_user' in str(props.get('script', ''))

        for key, value in base_fields.items():
            if key in stagger_fields:
                stagger_value = stagger_fields[key]
                stagger_type, stagger_config = parse_stagger_value(
                    stagger_value, group.count, seed
                )

                # Apply user_spawn_start override for user agent start_time
                if (key == 'start_time' and is_user_agent and user_spawn_start_s is not None):
                    if stagger_type == 'batched':
                        # Override initial_delay for batched schedule
                        if isinstance(stagger_config, dict):
                            stagger_config['initial_delay'] = user_spawn_start_s
                        else:
                            stagger_config = {'initial_delay': user_spawn_start_s}
                    elif stagger_type == 'linear':
                        # For linear stagger, set base value to user_spawn_start
                        value = f"{user_spawn_start_s}s"

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

    # Calculate timing with override support
    # Priority: explicit override > auto-calculated
    last_bootstrap_spawn_s = max(bootstrap_participant_start_times) if bootstrap_participant_start_times else 0
    auto_bootstrap_end_s = max(MIN_BOOTSTRAP_END_TIME_S, int(last_bootstrap_spawn_s * (1 + BOOTSTRAP_BUFFER_PERCENT)))

    # 1. Bootstrap end time: use override or auto-calc
    if overrides.bootstrap_end_time:
        bootstrap_end_s = parse_duration(overrides.bootstrap_end_time)
    else:
        bootstrap_end_s = auto_bootstrap_end_s

    # 2. Miner distributor start time: use override or default to bootstrap_end
    if overrides.md_start_time:
        md_start_s = parse_duration(overrides.md_start_time)
    else:
        md_start_s = bootstrap_end_s

    # 3. Activity start time: use override or default to md_start + funding period
    if overrides.activity_start_time:
        activity_start_s = parse_duration(overrides.activity_start_time)
    else:
        activity_start_s = md_start_s + FUNDING_PERIOD_S

    # 4. Activity batching settings
    activity_batch_size = overrides.activity_batch_size or DEFAULT_ACTIVITY_BATCH_SIZE
    activity_batch_interval_s = (
        parse_duration(overrides.activity_batch_interval)
        if overrides.activity_batch_interval
        else DEFAULT_ACTIVITY_BATCH_INTERVAL_S
    )
    activity_batch_jitter = overrides.activity_batch_jitter or DEFAULT_ACTIVITY_BATCH_JITTER

    scenario.timing = {
        'last_bootstrap_spawn_s': last_bootstrap_spawn_s,
        'bootstrap_end_s': bootstrap_end_s,
        'md_start_s': md_start_s,
        'activity_start_s': activity_start_s,
        'user_spawn_start_s': user_spawn_start_s,
        'activity_batch_size': activity_batch_size,
        'activity_batch_interval_s': activity_batch_interval_s,
        'activity_batch_jitter': activity_batch_jitter,
    }

    # Resolve 'auto' values in general section
    general = scenario.general.copy()
    if general.get('bootstrap_end_time') == 'auto':
        general['bootstrap_end_time'] = f"{bootstrap_end_s // 3600}h" if bootstrap_end_s % 3600 == 0 else f"{bootstrap_end_s}s"

    # Collect user agents with auto activity_start_time for batching
    user_agents_with_auto_activity = []
    for agent_id, agent_config in agents.items():
        if agent_config.get('activity_start_time') == 'auto':
            is_user = 'regular_user' in str(agent_config.get('script', ''))
            if is_user:
                user_agents_with_auto_activity.append(agent_id)

    # Calculate staggered activity start times for users
    user_activity_times = calculate_activity_start_times(
        num_users=len(user_agents_with_auto_activity),
        base_activity_start_s=activity_start_s,
        batch_size=activity_batch_size,
        batch_interval_s=activity_batch_interval_s,
        jitter_fraction=activity_batch_jitter,
        seed=seed,
    )

    # Map user agent IDs to their staggered activity times
    user_activity_map = dict(zip(user_agents_with_auto_activity, user_activity_times))

    # Resolve 'auto' in agents
    for agent_id, agent_config in agents.items():
        if agent_config.get('activity_start_time') == 'auto':
            # Use staggered time for users, base time for miners/others
            if agent_id in user_activity_map:
                agent_config['activity_start_time'] = user_activity_map[agent_id]
            else:
                agent_config['activity_start_time'] = activity_start_s
        if agent_config.get('wait_time') == 'auto':
            # Miner distributor uses md_start_s, not bootstrap_end_s
            agent_config['wait_time'] = md_start_s
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
