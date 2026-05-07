"""General-section + metadata-section construction for monerosim configs.

Both helpers return OrderedDicts that the orchestrator slots into the
top-level config structure. ``_build_general_config`` produces the
``general:`` section; ``generate_metadata`` produces the machine-parseable
``metadata:`` block consumed by analysis tools.
"""

from collections import OrderedDict
from typing import Any, Dict

from .timeline import format_time_offset

# Dual-import pattern: works both when scripts/ is on sys.path and when
# imported as scripts.config_generation.general_emit.
try:
    from timing_constants import LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD
except ImportError:
    from ..timing_constants import LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD


# Relay node spawn staggering defaults (mirrored at the package edge in
# scripts/generate_config.py, where they appear as the public constants
# DEFAULT_RELAY_SPAWN_START_S and DEFAULT_RELAY_STAGGER_S).
DEFAULT_RELAY_SPAWN_START_S = 5   # Start after miners (t=5s)
DEFAULT_RELAY_STAGGER_S = 20      # 20s apart; sim-time moves fast so need wider spacing


def _build_general_config(
    duration: str,
    parallelism: int,
    simulation_seed: int,
    bootstrap_end_time_s: int,
    fast_mode: bool,
    process_threads: int,
    native_preemption: bool = None,
    total_agents: int = 0,
    shared_dir: str = None,
    daemon_data_dir: str = None,
    fallback_seeds_mode: str = "auto",
) -> OrderedDict:
    """Build the general config section shared by generate_config and generate_upgrade_config."""
    shadow_log_level = "warning" if fast_mode else "info"
    runahead = "100ms" if fast_mode else None

    # Auto-enable native_preemption for large sims (see timing_constants.py
    # for the failure mode this guards against). Caller can pass
    # native_preemption=False explicitly to disable.
    if native_preemption is None and total_agents >= LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD:
        print(f"Note: enabling native_preemption=true for large sim "
              f"({total_agents} agents >= {LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD} threshold). "
              f"Pass native_preemption=False to disable.")
        native_preemption = True

    general_config = OrderedDict([
        ("stop_time", duration),
        ("parallelism", parallelism),
        ("simulation_seed", simulation_seed),
        ("enable_dns_server", True),
        ("fallback_seeds", fallback_seeds_mode),
        ("shadow_log_level", shadow_log_level),
        ("bootstrap_end_time", format_time_offset(bootstrap_end_time_s)),
        ("progress", True),
    ])

    if runahead:
        general_config["runahead"] = runahead

    if process_threads != 1:
        general_config["process_threads"] = process_threads

    if native_preemption is not None:
        general_config["native_preemption"] = native_preemption

    # Only emit non-default directory paths
    if shared_dir and shared_dir != "/tmp/monerosim_shared":
        general_config["shared_dir"] = shared_dir
    if daemon_data_dir and daemon_data_dir != "/tmp":
        general_config["daemon_data_dir"] = daemon_data_dir

    general_config["daemon_defaults"] = OrderedDict([
        ("log-level", 1),
        ("max-log-file-size", 0),
        ("db-sync-mode", "fastest"),
        ("no-zmq", True),
        ("non-interactive", True),
    ])

    general_config["wallet_defaults"] = OrderedDict([
        ("log-level", 1),
    ])

    return general_config


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

    # Activity stagger configuration (see docs/shadow-tx-stagger.md)
    metadata["activity_stagger"] = OrderedDict([
        ("stagger_s", timing_info.get('activity_stagger_s', 0)),
        ("tx_interval", timing_info.get('tx_interval', 60)),
        ("total_rollout_s", timing_info.get('activity_rollout_duration_s', 0)),
    ])

    # Simulation settings
    metadata["settings"] = OrderedDict([
        ("seed", simulation_seed),
        ("gml_topology", gml_path),
        ("fast_mode", fast_mode),
    ])

    return metadata
