"""Timeline math for monerosim config generation.

Pure helpers that compute durations, batch schedules, bootstrap windows,
upgrade staggers and activity-stagger times. None of them touch
``GenerationConfig`` directly; the orchestrator in
``scripts/generate_config.py`` glues them to the dataclass fields.
"""

import random
import re
import sys
from typing import Dict, List, Tuple

# Dual-import pattern: works both when scripts/ is on sys.path (legacy
# direct invocation) and when imported as scripts.config_generation.timeline.
try:
    from calibrate import (
        compute_stagger,
        estimate_wall_time_s,
        max_safe_users,
    )
except ImportError:
    from ..calibrate import (
        compute_stagger,
        estimate_wall_time_s,
        max_safe_users,
    )

try:
    from timing_constants import (
        BOOTSTRAP_BUFFER_PERCENT,
        DEFAULT_DAEMON_RESTART_GAP_S,
        FUNDING_PERIOD_S,
        MIN_BOOTSTRAP_END_TIME_S,
    )
except ImportError:
    from ..timing_constants import (
        BOOTSTRAP_BUFFER_PERCENT,
        DEFAULT_DAEMON_RESTART_GAP_S,
        FUNDING_PERIOD_S,
        MIN_BOOTSTRAP_END_TIME_S,
    )


# Generate-config-specific timing.
USER_START_TIME_S = 10800            # users spawn at 3h


def _print_scale_guardrail(num_users: int, duration_s: int) -> None:
    """Print wall-time estimate and safe-N cap warnings for a scenario.

    Mirrors the guardrail in scenario_parser.py so both entry points give
    the same pre-flight feedback. See docs/PERFORMANCE_AND_SCALE.md.
    """
    if num_users <= 0:
        return
    est_wall_s = estimate_wall_time_s(num_users)
    cap = max_safe_users()
    est_ratio = (duration_s / est_wall_s) if est_wall_s > 0 else 0
    print(f"Estimated wall time for N={num_users} users: "
          f"~{est_wall_s // 60} min "
          f"(stop_time={duration_s // 60} min, predicted ratio ≈ {est_ratio:.2f}).")
    if duration_s > 0 and est_wall_s > duration_s:
        print(f"⚠ Warning: estimated wall time exceeds stop_time. "
              f"Consider reducing --users or increasing --duration.")
    if num_users > cap:
        print(f"⚠ Warning: --users={num_users} exceeds the per-machine "
              f"safe cap (~{cap} for this hardware). Expect stalls. "
              f"See docs/PERFORMANCE_AND_SCALE.md.")


def calculate_activity_start_times(
    num_users: int,
    base_activity_start_s: int,
    tx_interval: int,
    num_nodes: int = None,
) -> List[int]:
    """Calculate evenly staggered activity start times.

    Uses the stagger formula: stagger = transaction_interval / num_users
    This ensures transaction generation is evenly distributed across
    simulated time, preventing Shadow CPU starvation.

    See docs/shadow-tx-stagger.md for the full explanation.

    Args:
        num_users: Total number of users
        base_activity_start_s: When the first user starts transacting (sim seconds)
        tx_interval: Transaction interval in seconds
        num_nodes: Total nodes in the simulated network (for scale-aware
                   interval calibration). Defaults to num_users (conservative
                   fallback when network size is not known).

    Returns:
        List of activity_start_time values for each user (in order)
    """
    if num_users == 0:
        return []

    stagger = compute_stagger(num_users, tx_interval, num_nodes=num_nodes)
    return [base_activity_start_s + i * stagger for i in range(num_users)]


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


_DURATION_TOKEN_RE = re.compile(r'(\d+(?:\.\d+)?)(h|m|s)')


def parse_duration(duration_str: str) -> int:
    """Parse duration string to seconds.

    Accepts bare digit strings ('5400' -> 5400 seconds), a single unit with
    optional decimal ('4h', '2.5h', '30m', '45s'), and compound forms with
    units concatenated and no separators ('1h30m', '3h30m'). This is a
    user-facing path (scenario YAML fields like stop_time/bootstrap_end_time
    flow through scenario_parser.py, and CLI args/interactive prompts flow
    through generate_config.py and configure_upgrade.py) and
    docs/SCENARIO_FORMAT.md documents compound forms as supported, so this
    matches the semantics of scripts/ai_config/validator.py:parse_time_to_seconds.

    Raises ValueError if the string cannot be parsed.
    """
    original = duration_str
    duration_str = duration_str.strip().lower()

    if not duration_str:
        raise ValueError(f"Empty duration value: {original!r}")

    # Pure number (assume seconds)
    if duration_str.isdigit():
        return int(duration_str)

    total = 0.0
    pos = 0
    for match in _DURATION_TOKEN_RE.finditer(duration_str):
        if match.start() != pos:
            break
        value = float(match.group(1))
        unit = match.group(2)
        total += value * {'h': 3600, 'm': 60, 's': 1}[unit]
        pos = match.end()

    if pos != len(duration_str):
        raise ValueError(
            f"Invalid duration value: {original!r} "
            "(expected forms like '4h', '2.5h', '30m', '1h30m', or plain seconds like '5400')"
        )

    return int(total)


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
