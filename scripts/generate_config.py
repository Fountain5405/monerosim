#!/usr/bin/env python3
"""
Generate monerosim configuration files with varying agent counts for scaling tests.

Usage:
    python scripts/generate_config.py --agents 45 -o test_50.yaml   # 5 miners + 45 users = 50 hosts
    python scripts/generate_config.py --agents 95 -o test_100.yaml  # 5 miners + 95 users = 100 hosts
    python scripts/generate_config.py --agents 995 --duration 8h -o test_1000.yaml  # 5 miners + 995 users

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
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# Internal helpers extracted into scripts/config_generation/. Dual-import
# pattern: works both when scripts/ is on sys.path (legacy direct invocation
# via ``python3 scripts/generate_config.py``) and when imported as
# ``scripts.generate_config``.
try:
    from config_generation.timeline import (
        _print_scale_guardrail,
        calculate_activity_start_times,
        calculate_batch_schedule,
        calculate_batch_sizes,
        calculate_bootstrap_timing,
        calculate_upgrade_schedule,
        format_batch_summary,
        format_time_offset,
        parse_duration,
    )
    from config_generation.timeline import USER_START_TIME_S
    from config_generation.agent_emit import (
        generate_miner_agent,
        generate_miner_agent_phased,
        generate_relay_agent,
        generate_relay_agent_phased,
        generate_user_agent,
        generate_user_agent_phased,
    )
    from config_generation.general_emit import (
        DEFAULT_RELAY_SPAWN_START_S,
        DEFAULT_RELAY_STAGGER_S,
        _build_general_config,
        generate_metadata,
    )
    from config_generation.yaml_emit import config_to_yaml, format_yaml_value
except ImportError:
    from .config_generation.timeline import (
        _print_scale_guardrail,
        calculate_activity_start_times,
        calculate_batch_schedule,
        calculate_batch_sizes,
        calculate_bootstrap_timing,
        calculate_upgrade_schedule,
        format_batch_summary,
        format_time_offset,
        parse_duration,
    )
    from .config_generation.timeline import USER_START_TIME_S
    from .config_generation.agent_emit import (
        generate_miner_agent,
        generate_miner_agent_phased,
        generate_relay_agent,
        generate_relay_agent_phased,
        generate_user_agent,
        generate_user_agent_phased,
    )
    from .config_generation.general_emit import (
        DEFAULT_RELAY_SPAWN_START_S,
        DEFAULT_RELAY_STAGGER_S,
        _build_general_config,
        generate_metadata,
    )
    from .config_generation.yaml_emit import config_to_yaml, format_yaml_value

try:
    from calibrate import compute_stagger, disable_auto_calibration, compute_safe_interval
except ImportError:
    from .calibrate import compute_stagger, disable_auto_calibration, compute_safe_interval


# Fixed miner configuration (same as config_32_agents.yaml)
FIXED_MINERS = [
    {"hashrate": 25, "start_offset_s": 0},
    {"hashrate": 25, "start_offset_s": 1},
    {"hashrate": 30, "start_offset_s": 2},
    {"hashrate": 10, "start_offset_s": 3},
    {"hashrate": 10, "start_offset_s": 4},
]

# Number of Monero fallback seed IPs (mirrors src/lib.rs MONERO_FALLBACK_SEED_IPS).
# Bumped to match upstream when monerod's hardcoded fallback list changes.
NUM_MONERO_FALLBACK_SEEDS = 6

# Shared with scenario_parser.py and configure_upgrade.py.
try:
    from timing_constants import (
        MIN_BOOTSTRAP_END_TIME_S, BOOTSTRAP_BUFFER_PERCENT, FUNDING_PERIOD_S,
        DEFAULT_AUTO_THRESHOLD, DEFAULT_INITIAL_DELAY_S, DEFAULT_BATCH_INTERVAL_S,
        DEFAULT_INITIAL_BATCH_SIZE, DEFAULT_GROWTH_FACTOR, DEFAULT_MAX_BATCH_SIZE,
        DEFAULT_INTRA_BATCH_STAGGER_S, DEFAULT_UPGRADE_STAGGER_S,
        DEFAULT_DAEMON_RESTART_GAP_S, DEFAULT_WALLET_RESTART_GAP_S,
        LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD,
    )
except ImportError:
    from .timing_constants import (
        MIN_BOOTSTRAP_END_TIME_S, BOOTSTRAP_BUFFER_PERCENT, FUNDING_PERIOD_S,
        DEFAULT_AUTO_THRESHOLD, DEFAULT_INITIAL_DELAY_S, DEFAULT_BATCH_INTERVAL_S,
        DEFAULT_INITIAL_BATCH_SIZE, DEFAULT_GROWTH_FACTOR, DEFAULT_MAX_BATCH_SIZE,
        DEFAULT_INTRA_BATCH_STAGGER_S, DEFAULT_UPGRADE_STAGGER_S,
        DEFAULT_DAEMON_RESTART_GAP_S, DEFAULT_WALLET_RESTART_GAP_S,
        LARGE_SIM_NATIVE_PREEMPTION_THRESHOLD,
    )

# Generate-config-specific timing.
MIN_ACTIVITY_PERIOD_S = 7200         # 2h minimum activity window after activity_start

# Upgrade scenario windows (only generate_upgrade_config uses these).
DEFAULT_STEADY_STATE_DURATION_S = 7200    # 2h pre-upgrade observation
DEFAULT_POST_UPGRADE_DURATION_S = 7200    # 2h post-upgrade observation

# Activity stagger: see docs/shadow-tx-stagger.md
# stagger = transaction_interval / num_users


# Single GML file for all tests (1200 nodes supports up to 1200 agents)
DEFAULT_GML_PATH = "gml_processing/1200_nodes_caida_with_loops.gml"


@dataclass
class BatchedBootstrap:
    """Batched user-startup configuration.

    Controls the exponential-growth batch schedule used to spawn users in
    waves so Shadow doesn't see all wallet-rpc processes start at once.
    """
    mode: str = "auto"               # "auto", "true", or "false"
    batch_interval: str = "20m"      # Time between batches (duration string)
    initial_batch_size: int = 5
    max_batch_size: int = 200


@dataclass
class TimingOverrides:
    """Explicit timing overrides for the timeline dependency chain.

    Each field is optional; when None, the value is auto-calculated from
    earlier stages of the chain (see generate_config for derivation order).
    """
    user_spawn_start: Optional[str] = None      # When users start spawning
    bootstrap_end_time: Optional[str] = None    # When bootstrap ends
    regular_user_start: Optional[str] = None    # When users start transacting
    md_start_time: Optional[str] = None         # When miner distributor starts
    tx_interval: Optional[int] = None           # Per-user transaction interval


@dataclass
class MinerDistributorConfig:
    """Per-cycle parameters for the miner-distributor agent."""
    n_recipients: int = 8
    out_per_tx: int = 2
    output_amount: float = 5.0
    funding_cycle_interval: str = "5m"


@dataclass
class RelayNodes:
    """Daemon-only relay node configuration."""
    count: int = 0
    spawn_start_s: int = DEFAULT_RELAY_SPAWN_START_S
    stagger_s: int = DEFAULT_RELAY_STAGGER_S


@dataclass
class UpgradeSpec:
    """Network-upgrade scenario configuration.

    When attached to a GenerationConfig as ``upgrade=...``, the generator
    emits phased agents (daemon_0/daemon_1 fields) and the duration is
    stretched to cover the full pre/post-upgrade observation windows.
    When None, the generator produces a regular (non-upgrade) config.
    """
    binary_v1: str = "monerod"
    binary_v2: str = "monerod"
    upgrade_start: Optional[str] = None  # None = activity_start + steady_state
    stagger_s: int = DEFAULT_UPGRADE_STAGGER_S
    order: str = "sequential"  # "sequential" | "random" | "miners-first"
    steady_state_duration_s: int = DEFAULT_STEADY_STATE_DURATION_S
    post_upgrade_duration_s: int = DEFAULT_POST_UPGRADE_DURATION_S


@dataclass
class GenerationConfig:
    """Top-level configuration for generate_config().

    Bundles the ~30 parameters that previously formed generate_config's
    signature into a single struct with nested substructs. The optional
    ``upgrade`` field toggles upgrade-scenario output (phased daemons,
    extended duration, upgrade metadata); when None, a regular config
    is generated.
    """
    total_agents: int = 0
    duration: str = "8h"
    stagger_interval_s: int = 5
    simulation_seed: int = 12345
    gml_path: str = DEFAULT_GML_PATH
    fast_mode: bool = False
    process_threads: int = 1
    daemon_binary: str = "monerod"
    tx_send_probability: float = 0.75
    parallelism: int = 0
    native_preemption: Optional[bool] = None
    fallback_seeds_mode: str = "auto"
    batched_bootstrap: BatchedBootstrap = field(default_factory=BatchedBootstrap)
    timing: TimingOverrides = field(default_factory=TimingOverrides)
    miner_distributor: MinerDistributorConfig = field(default_factory=MinerDistributorConfig)
    relay_nodes: RelayNodes = field(default_factory=RelayNodes)
    upgrade: Optional[UpgradeSpec] = None


def _compute_user_spawn_schedule(
    num_users: int,
    cfg: GenerationConfig,
) -> Tuple[bool, int, int, int, list, list]:
    """Compute user-spawn batching state shared by both scenarios.

    Returns:
        (use_batched, batch_interval_s, user_spawn_start_s,
         last_user_spawn_s, batch_sizes, batch_schedule)
    """
    # Determine if batched bootstrap should be enabled
    use_batched = (
        cfg.batched_bootstrap.mode == "true" or
        (cfg.batched_bootstrap.mode == "auto" and num_users >= DEFAULT_AUTO_THRESHOLD)
    )

    # Parse batch interval
    batch_interval_s = parse_duration(cfg.batched_bootstrap.batch_interval)

    # Calculate user spawn start time
    if cfg.timing.user_spawn_start is not None:
        user_spawn_start_s = parse_duration(cfg.timing.user_spawn_start)
    else:
        # Default: 20m for batched, 3h for non-batched
        user_spawn_start_s = DEFAULT_INITIAL_DELAY_S if use_batched else USER_START_TIME_S

    # Calculate user start times based on batching mode
    batch_sizes: list = []
    batch_schedule: list = []

    if use_batched and num_users > 0:
        # Batched bootstrap: users start in waves
        batch_sizes = calculate_batch_sizes(
            num_users,
            cfg.batched_bootstrap.initial_batch_size,
            2.0,
            cfg.batched_bootstrap.max_batch_size,
        )
        batch_schedule = calculate_batch_schedule(
            num_users,
            user_spawn_start_s,
            batch_interval_s,
            cfg.batched_bootstrap.initial_batch_size,
            2.0,  # growth_factor
            cfg.batched_bootstrap.max_batch_size,
            DEFAULT_INTRA_BATCH_STAGGER_S,
        )
        # Last user spawn time from batch schedule
        last_user_spawn_s = batch_schedule[-1][1] if batch_schedule else 0
    else:
        # Non-batched: users start at user_spawn_start_s with stagger
        if num_users > 0:
            last_user_spawn_s = user_spawn_start_s + ((num_users - 1) * cfg.stagger_interval_s)
        else:
            last_user_spawn_s = user_spawn_start_s

    return (use_batched, batch_interval_s, user_spawn_start_s,
            last_user_spawn_s, batch_sizes, batch_schedule)


def _compute_timing_chain(
    cfg: GenerationConfig,
    last_user_spawn_s: int,
) -> Tuple[int, int, int]:
    """Compute the bootstrap_end / md_start / activity_start dependency chain.

    Step 1: bootstrap_end_time_s -- explicit or auto from last_user_spawn + buffer.
    Step 2: md_start_time_s -- explicit or defaults to bootstrap_end_time_s.
    Step 3: activity_start_time_s -- explicit or defaults to md_start + funding period.
    """
    # Step 1: Bootstrap end time
    if cfg.timing.bootstrap_end_time is not None:
        bootstrap_end_time_s = parse_duration(cfg.timing.bootstrap_end_time)
    else:
        # Auto-calculate: max of minimum time and last spawn + buffer
        spawn_with_buffer_s = int(last_user_spawn_s * (1 + BOOTSTRAP_BUFFER_PERCENT))
        bootstrap_end_time_s = max(MIN_BOOTSTRAP_END_TIME_S, spawn_with_buffer_s)

    # Step 2: Miner distributor start time
    if cfg.timing.md_start_time is not None:
        md_start_time_s = parse_duration(cfg.timing.md_start_time)
        if md_start_time_s < bootstrap_end_time_s:
            print(f"Warning: --md-start-time ({cfg.timing.md_start_time}) is before bootstrap_end_time "
                  f"({format_time_offset(bootstrap_end_time_s)}). Miners may not have accumulated enough funds.",
                  file=sys.stderr)
    else:
        md_start_time_s = bootstrap_end_time_s

    # Step 3: Regular user activity start time
    if cfg.timing.regular_user_start is not None:
        activity_start_time_s = parse_duration(cfg.timing.regular_user_start)
        if activity_start_time_s < md_start_time_s:
            print(f"Warning: --regular-user-start ({cfg.timing.regular_user_start}) is before md_start_time "
                  f"({format_time_offset(md_start_time_s)}). Users may start before receiving funds.",
                  file=sys.stderr)
    else:
        activity_start_time_s = md_start_time_s + FUNDING_PERIOD_S

    return bootstrap_end_time_s, md_start_time_s, activity_start_time_s


def _resolve_tx_interval(
    cfg: GenerationConfig,
    num_users: int,
    total_nodes: int,
) -> int:
    """Resolve tx_interval, applying fast-mode default and safe-interval bumping."""
    tx_interval = cfg.timing.tx_interval
    if tx_interval is None:
        tx_interval = 120 if cfg.fast_mode else 60
    # Bump to calibrated minimum if needed (see calibrate.py SAFETY_FACTOR comment).
    safe_interval = compute_safe_interval(num_users, tx_interval, num_nodes=total_nodes)
    if safe_interval > tx_interval:
        print(f"Warning: tx_interval={tx_interval}s is below the calibrated safe "
              f"minimum for {num_users} users × {total_nodes} nodes; bumping "
              f"to {safe_interval}s. Pass --tx-interval explicitly to override.")
        tx_interval = safe_interval
    return tx_interval


def _maybe_warn_late_relay(
    cfg: GenerationConfig,
    bootstrap_end_time_s: int,
) -> int:
    """Compute last_relay_spawn_s and warn if it lands after bootstrap_end_time."""
    if cfg.relay_nodes.count > 0:
        last_relay_spawn_s = (cfg.relay_nodes.spawn_start_s
                              + ((cfg.relay_nodes.count - 1) * cfg.relay_nodes.stagger_s))
        if last_relay_spawn_s > bootstrap_end_time_s:
            print(f"Warning: Last relay spawn ({format_time_offset(last_relay_spawn_s, for_config=False)}) "
                  f"exceeds bootstrap_end_time ({format_time_offset(bootstrap_end_time_s, for_config=False)}). "
                  f"Late relays may experience packet loss during sync.",
                  file=sys.stderr)
        return last_relay_spawn_s
    return 0


def generate_config(cfg: GenerationConfig) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generate the complete monerosim configuration.

    Handles both regular and upgrade scenarios; pass ``cfg.upgrade=UpgradeSpec(...)``
    to emit phased agents (daemon_0/daemon_1) and upgrade-specific timing/metadata.

    Args:
        cfg: Bundle of generation parameters. See GenerationConfig and its
             nested substructs (BatchedBootstrap, TimingOverrides,
             MinerDistributorConfig, RelayNodes, UpgradeSpec) for the full shape.
    """

    num_miners = len(FIXED_MINERS)
    num_users = cfg.total_agents  # --agents now means user count directly

    if num_users < 0:
        raise ValueError(f"User agent count ({cfg.total_agents}) must be non-negative")

    is_upgrade = cfg.upgrade is not None

    # User-spawn batching/staggering schedule
    (use_batched, batch_interval_s, user_spawn_start_s, last_user_spawn_s,
     batch_sizes, batch_schedule) = _compute_user_spawn_schedule(num_users, cfg)

    # Timing dependency chain (bootstrap -> md_start -> activity_start)
    bootstrap_end_time_s, md_start_time_s, activity_start_time_s = (
        _compute_timing_chain(cfg, last_user_spawn_s)
    )

    # Upgrade scheduling (only when cfg.upgrade is set). Compute schedule before
    # building agents so the per-agent phase times are available below.
    upgrade_schedule: Dict[str, Tuple[int, int]] = {}
    upgrade_start_time_s = 0
    last_upgrade_complete_s = 0
    if is_upgrade:
        spec = cfg.upgrade
        # Calculate upgrade timing
        if spec.upgrade_start is not None:
            upgrade_start_time_s = parse_duration(spec.upgrade_start)
        else:
            # Auto: upgrade starts after steady state observation period
            upgrade_start_time_s = activity_start_time_s + spec.steady_state_duration_s
        # Build agent ID list and calculate per-agent upgrade times
        miner_ids = [f"miner-{i+1:03}" for i in range(num_miners)]
        user_ids = [f"user-{i+1:03}" for i in range(num_users)]
        relay_ids = [f"relay-{i+1:03}" for i in range(cfg.relay_nodes.count)]
        all_agent_ids = miner_ids + user_ids + relay_ids
        upgrade_schedule = calculate_upgrade_schedule(
            all_agent_ids,
            upgrade_start_time_s,
            spec.stagger_s,
            spec.order,
            miner_ids,
            cfg.simulation_seed,
        )
        last_upgrade_complete_s = max(p1_start for _, (_, p1_start) in upgrade_schedule.items())

    # Parse and potentially extend duration. The minimum duration differs:
    # - Regular: at least MIN_ACTIVITY_PERIOD_S of activity after activity_start.
    # - Upgrade: at least last_upgrade_complete + post_upgrade observation window.
    requested_duration_s = parse_duration(cfg.duration) if cfg.duration else 0
    if is_upgrade:
        min_duration_s = last_upgrade_complete_s + cfg.upgrade.post_upgrade_duration_s
    else:
        min_duration_s = activity_start_time_s + MIN_ACTIVITY_PERIOD_S
    duration_s = max(requested_duration_s, min_duration_s)
    duration = format_time_offset(duration_s)  # Update duration string if extended

    # tx_interval (with fast-mode default + safe-interval bumping)
    total_nodes = num_miners + num_users + cfg.relay_nodes.count
    tx_interval = _resolve_tx_interval(cfg, num_users, total_nodes)
    poll_interval = 300  # 5 minutes for reasonable monitoring updates

    _print_scale_guardrail(num_users, duration_s)

    # Build named agents map (OrderedDict to preserve order)
    agents = OrderedDict()

    # Add fixed miners with explicit IDs (phased in upgrade scenario)
    for i, miner in enumerate(FIXED_MINERS):
        agent_id = f"miner-{i+1:03}"
        if is_upgrade:
            phase0_stop, phase1_start = upgrade_schedule[agent_id]
            agents[agent_id] = generate_miner_agent_phased(
                miner["hashrate"],
                miner["start_offset_s"],
                cfg.upgrade.binary_v1,
                cfg.upgrade.binary_v2,
                phase0_stop,
                phase1_start,
            )
        else:
            agents[agent_id] = generate_miner_agent(
                miner["hashrate"], miner["start_offset_s"], cfg.daemon_binary,
            )

    # Calculate staggered activity start times (see docs/shadow-tx-stagger.md)
    activity_stagger_s = compute_stagger(num_users, tx_interval, num_nodes=total_nodes)
    user_activity_times = calculate_activity_start_times(
        num_users=num_users,
        base_activity_start_s=activity_start_time_s,
        tx_interval=tx_interval,
        num_nodes=total_nodes,
    )

    # Activity rollout duration for metadata
    activity_rollout_duration_s = (num_users - 1) * activity_stagger_s if num_users > 0 else 0

    # Add variable users with appropriate start times (phased in upgrade scenario)
    if use_batched and batch_schedule:
        # Batched bootstrap: use calculated batch schedule for spawning
        for user_index, start_time_s in batch_schedule:
            agent_id = f"user-{user_index+1:03}"
            user_activity_time = (user_activity_times[user_index]
                                  if user_index < len(user_activity_times)
                                  else activity_start_time_s)
            if is_upgrade:
                phase0_stop, phase1_start = upgrade_schedule[agent_id]
                agents[agent_id] = generate_user_agent_phased(
                    start_time_s, tx_interval, user_activity_time,
                    cfg.upgrade.binary_v1, cfg.upgrade.binary_v2,
                    phase0_stop, phase1_start, cfg.tx_send_probability,
                )
            else:
                agents[agent_id] = generate_user_agent(
                    start_time_s, tx_interval, user_activity_time,
                    cfg.daemon_binary, cfg.tx_send_probability,
                )
    else:
        # Non-batched bootstrap: start at USER_START_TIME_S with stagger
        for i in range(num_users):
            agent_id = f"user-{i+1:03}"
            start_offset_s = USER_START_TIME_S + (i * cfg.stagger_interval_s)
            user_activity_time = (user_activity_times[i]
                                  if i < len(user_activity_times)
                                  else activity_start_time_s)
            if is_upgrade:
                phase0_stop, phase1_start = upgrade_schedule[agent_id]
                agents[agent_id] = generate_user_agent_phased(
                    start_offset_s, tx_interval, user_activity_time,
                    cfg.upgrade.binary_v1, cfg.upgrade.binary_v2,
                    phase0_stop, phase1_start, cfg.tx_send_probability,
                )
            else:
                agents[agent_id] = generate_user_agent(
                    start_offset_s, tx_interval, user_activity_time,
                    cfg.daemon_binary, cfg.tx_send_probability,
                )

    # Add relay nodes (daemon-only, no wallet or script). Phased in upgrade scenario.
    # Simple linear stagger: start + i * stagger
    for i in range(cfg.relay_nodes.count):
        agent_id = f"relay-{i+1:03}"
        relay_start_s = cfg.relay_nodes.spawn_start_s + (i * cfg.relay_nodes.stagger_s)
        if is_upgrade:
            phase0_stop, phase1_start = upgrade_schedule[agent_id]
            agents[agent_id] = generate_relay_agent_phased(
                relay_start_s, cfg.upgrade.binary_v1, cfg.upgrade.binary_v2,
                phase0_stop, phase1_start,
            )
        else:
            agents[agent_id] = generate_relay_agent(relay_start_s, cfg.daemon_binary)

    # In custom mode, scaffold 6 monero-seed-XXX agents the user can edit
    # before running the sim. (In auto mode the orchestrator injects them
    # automatically; in off mode no seed hosts exist.)
    # Phased daemons aren't applied here -- seed hosts use the v1 binary
    # for the entire run (they don't participate in upgrade scenarios by
    # default).
    if cfg.fallback_seeds_mode == "custom":
        seed_binary = cfg.upgrade.binary_v1 if is_upgrade else cfg.daemon_binary
        for i in range(NUM_MONERO_FALLBACK_SEEDS):
            agents[f"monero-seed-{i+1:03}"] = generate_relay_agent(0, seed_binary)

    # Calculate last relay spawn time for metadata/warnings
    last_relay_spawn_s = _maybe_warn_late_relay(cfg, bootstrap_end_time_s)

    # Add miner-distributor (md_start_time_s calculated earlier in timing chain)
    agents["miner-distributor"] = OrderedDict([
        ("script", "agents.miner_distributor"),
        ("wait_time", md_start_time_s),  # When Shadow starts the process
        ("max_transaction_amount", "2.0"),
        ("min_transaction_amount", "0.5"),
        ("md_n_recipients", cfg.miner_distributor.n_recipients),
        ("md_out_per_tx", cfg.miner_distributor.out_per_tx),
        ("md_output_amount", cfg.miner_distributor.output_amount),
        ("md_funding_cycle_interval", cfg.miner_distributor.funding_cycle_interval),
    ])

    # Add simulation-monitor
    agents["simulation-monitor"] = OrderedDict([
        ("script", "agents.simulation_monitor"),
        ("poll_interval", poll_interval),
        ("detailed_logging", False),
        ("enable_alerts", True),
        ("status_file", "monerosim_monitor.log"),
    ])

    general_config = _build_general_config(
        duration=duration,
        parallelism=cfg.parallelism,
        simulation_seed=cfg.simulation_seed,
        bootstrap_end_time_s=bootstrap_end_time_s,
        fast_mode=cfg.fast_mode,
        process_threads=cfg.process_threads,
        native_preemption=cfg.native_preemption,
        total_agents=cfg.total_agents,
        fallback_seeds_mode=cfg.fallback_seeds_mode,
    )

    # Return config and timing info for header generation
    timing_info: Dict[str, Any] = {
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
        # Activity stagger info (see docs/shadow-tx-stagger.md)
        'activity_stagger_s': activity_stagger_s,
        'tx_interval': tx_interval,
        'activity_rollout_duration_s': activity_rollout_duration_s,
        # Relay timing info
        'relay_spawn_start_s': cfg.relay_nodes.spawn_start_s,
        'relay_stagger_s': cfg.relay_nodes.stagger_s,
        'last_relay_spawn_s': last_relay_spawn_s,
    }

    if is_upgrade:
        spec = cfg.upgrade
        timing_info.update({
            'upgrade_start_time_s': upgrade_start_time_s,
            'last_upgrade_complete_s': last_upgrade_complete_s,
            'upgrade_binary_v1': spec.binary_v1,
            'upgrade_binary_v2': spec.binary_v2,
            'upgrade_order': spec.order,
            'upgrade_stagger_s': spec.stagger_s,
            'steady_state_duration_s': spec.steady_state_duration_s,
            'post_upgrade_duration_s': spec.post_upgrade_duration_s,
        })

    # Generate metadata section
    metadata = generate_metadata(
        scenario="upgrade" if is_upgrade else "default",
        num_miners=num_miners,
        num_users=num_users,
        timing_info=timing_info,
        simulation_seed=cfg.simulation_seed,
        gml_path=cfg.gml_path,
        fast_mode=cfg.fast_mode,
        stagger_interval_s=cfg.stagger_interval_s,
        relay_nodes=cfg.relay_nodes.count,
    )

    # Build full config with metadata first
    config = OrderedDict([
        ("metadata", metadata),
        ("general", general_config),
        ("network", OrderedDict([
            ("path", cfg.gml_path),
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
    # Shadow parallelism and preemption
    parallelism: int = 0,
    native_preemption: bool = None,
    # Relay nodes (daemon-only)
    relay_nodes: int = 0,
    relay_spawn_start_s: int = DEFAULT_RELAY_SPAWN_START_S,
    relay_stagger_s: int = DEFAULT_RELAY_STAGGER_S,
    # Monero fallback-seed handling: auto | custom | off
    fallback_seeds_mode: str = "auto",
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

    Thin keyword-argument wrapper around generate_config(): assembles a
    GenerationConfig with an UpgradeSpec attached and delegates. Kept for
    backwards compatibility with configure_upgrade.py and any external
    callers; new code should construct GenerationConfig directly.

    Timeline:
      t=0:           Miners start
      t=bootstrap:   Bootstrap ends, funding begins
      t=activity:    Users start transacting (steady state)
      t=upgrade:     Nodes begin switching to v2 (staggered)
      t=end:         Simulation ends after post-upgrade observation
    """
    cfg = GenerationConfig(
        total_agents=total_agents,
        duration=duration,
        stagger_interval_s=stagger_interval_s,
        simulation_seed=simulation_seed,
        gml_path=gml_path,
        fast_mode=fast_mode,
        process_threads=process_threads,
        # daemon_binary is unused in upgrade mode (per-agent binaries come
        # from UpgradeSpec.binary_v1/v2); keep the dataclass default.
        tx_send_probability=tx_send_probability,
        parallelism=parallelism,
        native_preemption=native_preemption,
        fallback_seeds_mode=fallback_seeds_mode,
        batched_bootstrap=BatchedBootstrap(
            mode=batched_bootstrap,
            batch_interval=batch_interval,
            initial_batch_size=initial_batch_size,
            max_batch_size=max_batch_size,
        ),
        timing=TimingOverrides(
            user_spawn_start=user_spawn_start,
            bootstrap_end_time=bootstrap_end_time,
            regular_user_start=regular_user_start,
            md_start_time=md_start_time,
            tx_interval=tx_interval,
        ),
        miner_distributor=MinerDistributorConfig(
            n_recipients=md_n_recipients,
            out_per_tx=md_out_per_tx,
            output_amount=md_output_amount,
            funding_cycle_interval=md_funding_cycle_interval,
        ),
        relay_nodes=RelayNodes(
            count=relay_nodes,
            spawn_start_s=relay_spawn_start_s,
            stagger_s=relay_stagger_s,
        ),
        upgrade=UpgradeSpec(
            binary_v1=upgrade_binary_v1,
            binary_v2=upgrade_binary_v2,
            upgrade_start=upgrade_start,
            stagger_s=upgrade_stagger_s,
            order=upgrade_order,
            steady_state_duration_s=steady_state_duration_s,
            post_upgrade_duration_s=post_upgrade_duration_s,
        ),
    )
    return generate_config(cfg)


def main():
    parser = argparse.ArgumentParser(
        description="Generate monerosim configs for scaling tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/generate_config.py --agents 45 -o test_50.yaml   # 5 miners + 45 users = 50 hosts
    python scripts/generate_config.py --agents 95 --duration 8h -o test_100.yaml
    python scripts/generate_config.py --agents 795 --stagger-interval 1 -o test_800.yaml

5 fixed miners are always included (hashrates: 25, 25, 30, 10, 10). --agents specifies user count only.
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
        help="Number of user agents (daemon + wallet + script). 5 miners are always included separately. Required unless using --from."
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
        default=None,
        help="Output filename (default: monerosim.expanded.yaml, or derived from --from input)"
    )

    parser.add_argument(
        "--from", "-f",
        dest="from_scenario",
        type=str,
        default=None,
        help="Expand a scenario.yaml file instead of generating from CLI args"
    )

    parser.add_argument(
        "--no-safe-tx-interval",
        action="store_true",
        default=False,
        help="Don't bump explicit transaction_interval values up to the calibrated safe "
             "minimum. Use when you know your machine handles the configured rate, or "
             "when reproducing a known run. Only applies in --from scenario mode."
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

    parser.add_argument(
        "--fallback-seeds",
        type=str,
        choices=["auto", "custom", "off"],
        default="auto",
        help="Monero fallback-seed handling (default: auto). Distinct from "
             "network.seed_nodes (the explicit peer-discovery list for Hardcoded "
             "mode); this controls Monero's hardcoded fallback IPs. "
             "auto: orchestrator injects 6 monero-seed-001..006 hosts pinned to "
             "those IPs (silences 'no host exists' warnings). "
             "custom: scaffold 6 monero-seed-NNN entries in the YAML so you can "
             "edit start times / phases / etc. before running. "
             "off: legacy behavior — no seed hosts; miners alone serve the role."
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

    parser.add_argument(
        "--no-calibrate",
        action="store_true",
        help="Skip auto-calibration even if no calibration data exists"
    )

    args = parser.parse_args()

    if args.no_calibrate:
        disable_auto_calibration()

    # Derive output filename when not specified
    if args.output is None:
        if args.from_scenario:
            from scenario_parser import derive_expanded_filename
            args.output = derive_expanded_filename(args.from_scenario)
        else:
            args.output = "monerosim.expanded.yaml"

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
        config = expand_scenario(scenario, seed=seed,
                                  respect_safe_tx_interval=not args.no_safe_tx_interval)

        # Convert to YAML
        def to_plain_dict(obj):
            if hasattr(obj, 'items'):
                return {k: to_plain_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [to_plain_dict(i) for i in obj]
            return obj

        plain_config = to_plain_dict(config)

        # Count agents for summary
        agent_count = len(config['agents'])

        # Read actual values from the generated config (not auto-calc timing)
        bootstrap_end_val = config['general'].get('bootstrap_end_time', '')
        if isinstance(bootstrap_end_val, str) and any(bootstrap_end_val.endswith(u) for u in ['s', 'm', 'h']):
            bootstrap_end_s = parse_duration(bootstrap_end_val)
        else:
            bootstrap_end_s = scenario.timing['bootstrap_end_s']

        # Find the earliest activity_start_time across user agents
        activity_start_times = []
        for agent_config in config['agents'].values():
            ast = agent_config.get('activity_start_time')
            if ast is not None:
                if isinstance(ast, str) and any(ast.endswith(u) for u in ['s', 'm', 'h']):
                    activity_start_times.append(parse_duration(ast))
                elif isinstance(ast, (int, float)):
                    activity_start_times.append(int(ast))
        activity_start_s = min(activity_start_times) if activity_start_times else scenario.timing['activity_start_s']

        # Write output
        import yaml as yaml_module
        with open(args.output, 'w') as f:
            yaml_module.dump(plain_config, f, default_flow_style=False, sort_keys=False)

        print(f"Expanded {args.from_scenario} -> {args.output}", file=sys.stderr)
        print(f"  Agents: {agent_count}", file=sys.stderr)
        print(f"  Bootstrap ends: {format_time(bootstrap_end_s)}", file=sys.stderr)
        print(f"  Activity starts: {format_time(activity_start_s)}", file=sys.stderr)
        sys.exit(0)

    # Validate CLI args (only if not using --from)
    if args.agents is None:
        print("Error: --agents is required when not using --from", file=sys.stderr)
        sys.exit(1)

    if args.agents < 0:
        print(f"Error: --agents must be non-negative, got {args.agents}", file=sys.stderr)
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
    num_users = args.agents  # --agents now means user count directly

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
                parallelism=parallelism,
                native_preemption=native_preemption,
                relay_nodes=args.relay_nodes,
                relay_spawn_start_s=parse_duration(args.relay_spawn_start),
                relay_stagger_s=parse_duration(args.relay_stagger),
                fallback_seeds_mode=args.fallback_seeds,
                upgrade_binary_v1=args.upgrade_binary_v1,
                upgrade_binary_v2=args.upgrade_binary_v2,
                upgrade_start=args.upgrade_start,
                upgrade_stagger_s=parse_duration(args.upgrade_stagger),
                upgrade_order=args.upgrade_order,
                steady_state_duration_s=parse_duration(args.steady_state_duration),
                post_upgrade_duration_s=parse_duration(args.post_upgrade_duration),
            )
        else:
            cfg = GenerationConfig(
                total_agents=args.agents,
                duration=args.duration,
                stagger_interval_s=args.stagger_interval,
                simulation_seed=args.seed,
                gml_path=args.gml,
                fast_mode=args.fast,
                process_threads=process_threads,
                daemon_binary=args.daemon_binary,
                tx_send_probability=args.tx_send_probability,
                parallelism=parallelism,
                native_preemption=native_preemption,
                fallback_seeds_mode=args.fallback_seeds,
                batched_bootstrap=BatchedBootstrap(
                    mode=args.batched_bootstrap,
                    batch_interval=args.batch_interval,
                    initial_batch_size=args.initial_batch_size,
                    max_batch_size=args.max_batch_size,
                ),
                timing=TimingOverrides(
                    user_spawn_start=args.user_spawn_start,
                    bootstrap_end_time=args.bootstrap_end_time,
                    regular_user_start=args.regular_user_start,
                    md_start_time=args.md_start_time,
                    tx_interval=args.tx_interval,
                ),
                miner_distributor=MinerDistributorConfig(
                    n_recipients=args.md_n_recipients,
                    out_per_tx=args.md_out_per_tx,
                    output_amount=args.md_output_amount,
                    funding_cycle_interval=args.md_funding_cycle_interval,
                ),
                relay_nodes=RelayNodes(
                    count=args.relay_nodes,
                    spawn_start_s=parse_duration(args.relay_spawn_start),
                    stagger_s=parse_duration(args.relay_stagger),
                ),
            )
            config, timing_info = generate_config(cfg)
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

    # Activity stagger info
    activity_stagger_s = timing_info.get('activity_stagger_s', 0)
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

    # Activity stagger note (see docs/shadow-tx-stagger.md)
    activity_rollout_str = format_time_offset(activity_rollout_s, for_config=False)
    activity_stagger_str = format_time_offset(activity_stagger_s, for_config=False)
    activity_stagger_note = f"""#
# Activity stagger (prevents Shadow CPU starvation):
#   Stagger: {activity_stagger_str} between users (interval/num_users)
#   Total rollout: ~{activity_rollout_str}"""

    # Generate header based on scenario
    if args.scenario == "upgrade":
        upgrade_start = format_time_offset(timing_info['upgrade_start_time_s'], for_config=False)
        upgrade_end = format_time_offset(timing_info['last_upgrade_complete_s'], for_config=False)
        header = f"""# Monerosim upgrade scenario configuration{fast_note}
# Generated by generate_config.py --scenario upgrade
# Total hosts: {5 + num_users + relay_nodes} (5 miners + {num_users} users{relay_agent_note})
# Duration: {actual_duration}{duration_note}
# Network topology: {args.gml}
#
# Upgrade configuration:
#   Binary v1: {timing_info['upgrade_binary_v1']}
#   Binary v2: {timing_info['upgrade_binary_v2']}
#   Upgrade order: {timing_info['upgrade_order']}
#   Upgrade stagger: {args.upgrade_stagger}
{activity_stagger_note}
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
# Total hosts: {5 + num_users + relay_nodes} (5 miners + {num_users} users{relay_agent_note})
# Duration: {actual_duration}{duration_note}
# Network topology: {args.gml}
{activity_stagger_note}
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
        relay_summary = f" + {relay_nodes} relays" if relay_nodes > 0 else ""
        print(f"Generated upgrade scenario config with {num_users} user agents (+ 5 miners{relay_summary}){fast_msg}{threads_msg}{preemption_msg}{deterministic_msg}{duration_msg}")
        print(f"  Binary v1: {args.upgrade_binary_v1} -> v2: {args.upgrade_binary_v2}")
        print(f"  Upgrade order: {args.upgrade_order}, stagger: {args.upgrade_stagger}")
        print(f"  Output: {args.output}")
    else:
        relay_summary = f" + {relay_nodes} relays" if relay_nodes > 0 else ""
        print(f"Generated config with {num_users} user agents (+ 5 miners{relay_summary}){fast_msg}{threads_msg}{preemption_msg}{deterministic_msg}{duration_msg}, GML: {args.gml} -> {args.output}")


if __name__ == "__main__":
    main()
