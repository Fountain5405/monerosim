#!/usr/bin/env python3
"""
Calibrate MoneroSim timing parameters for the current hardware.

Runs a short simulation with 2 miners and 1 user, measures how long
transaction verification takes under Shadow's scheduler, and saves the
results to ~/.monerosim/calibration.json.

These measurements are used by generate_config.py and scenario_parser.py
to compute safe activity_start_time stagger and transaction_interval values.

Usage:
    python scripts/calibrate.py                    # Run calibration
    python scripts/calibrate.py --from-run DIR     # Extract from existing run
    python scripts/calibrate.py --show             # Show current calibration
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CALIBRATION_PATH = Path.home() / ".monerosim" / "calibration.json"

# Minimal config for calibration: 2 miners, 1 user, 1 relay
# Short sim: 8h bootstrap + 1h funding + 30min activity = ~9.5h sim time
# With fast mining (high hashrate), this completes in ~5 min wall time
CALIBRATION_CONFIG = """\
general:
  stop_time: 10h
  simulation_seed: 99999
  bootstrap_end_time: 7h
  enable_dns_server: true
  shadow_log_level: warning
  progress: true
  runahead: 500ms
  process_threads: 1
  native_preemption: true
  daemon_defaults:
    log-level: 1
    max-log-file-size: 0
    db-sync-mode: fastest
    no-zmq: true
    non-interactive: true
    disable-rpc-ban: true
    allow-local-ip: true
    no-igd: true
    out-peers: 3
  wallet_defaults:
    log-level: 1
network:
  path: gml_processing/1200_nodes_caida_with_loops.gml
  peer_mode: Dynamic
agents:
  miner-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 0s
    hashrate: 50
    can_receive_distributions: true
  miner-002:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.autonomous_miner
    start_time: 1s
    hashrate: 50
    can_receive_distributions: true
  user-001:
    daemon: monerod
    wallet: monero-wallet-rpc
    script: agents.regular_user
    start_time: 21600s
    transaction_interval: 60
    activity_start_time: 28800
    can_receive_distributions: true
  relay-001:
    daemon: monerod
    start_time: 2h
  miner-distributor:
    script: agents.miner_distributor
    wait_time: 25200
    transaction_frequency: 30
  simulation-monitor:
    script: agents.simulation_monitor
    poll_interval: 300
"""


def parse_perf_add_tx(log_path: str) -> list:
    """Extract PERF add_tx times (in microseconds) from a daemon log."""
    times = []
    pattern = re.compile(r"PERF\s+(\d+)\s+add_tx")
    try:
        with open(log_path, "r") as f:
            for line in f:
                m = pattern.search(line)
                if m:
                    times.append(int(m.group(1)))
    except FileNotFoundError:
        pass
    return times


def extract_from_run(run_dir: str) -> dict:
    """Extract calibration data from an existing archived run."""
    run_path = Path(run_dir)
    daemon_logs = run_path / "daemon_logs"

    if not daemon_logs.exists():
        print(f"Error: {daemon_logs} not found", file=sys.stderr)
        sys.exit(1)

    all_times = []
    agents_sampled = []
    notify_counts = {}

    for agent_dir in sorted(daemon_logs.iterdir()):
        log_file = agent_dir / "bitmonero.log"
        if log_file.exists():
            times = parse_perf_add_tx(str(log_file))
            if times:
                all_times.extend(times)
                agents_sampled.append(agent_dir.name)
            notifs = count_notify_events(str(log_file))
            if notifs:
                notify_counts[agent_dir.name] = len(notifs)

    if not all_times:
        print("Warning: no PERF add_tx entries found, using notify counts only",
              file=sys.stderr)

    return build_calibration(all_times, agents_sampled, str(run_path), notify_counts)


def count_notify_events(log_path: str) -> list:
    """Count NOTIFY_NEW_TRANSACTIONS events and measure inter-arrival times."""
    timestamps = []
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*NOTIFY_NEW_TRANSACTIONS")
    try:
        with open(log_path, "r") as f:
            for line in f:
                m = pattern.search(line)
                if m:
                    timestamps.append(m.group(1))
    except FileNotFoundError:
        pass
    return timestamps


def build_calibration(times_us: list, agents: list, source: str,
                      notify_counts: dict = None) -> dict:
    """Build calibration data from raw measurements.

    Note: Under Shadow, PERF add_tx times measure simulated time (not real
    CPU time), so they appear near-zero. The meaningful metric is the tx
    notification rate — how many NOTIFY_NEW_TRANSACTIONS a daemon receives
    per unit of simulated time. The stagger formula (interval / num_users)
    ensures notifications are spread evenly.
    """
    times_us.sort()
    n = len(times_us)
    p50 = times_us[n // 2] if n > 0 else 0
    p95 = times_us[int(n * 0.95)] if n > 0 else 0
    p99 = times_us[int(n * 0.99)] if n >= 100 else (times_us[-1] if n > 0 else 0)
    max_val = times_us[-1] if n > 0 else 0

    result = {
        "verify_time_us": {
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "max": max_val,
            "samples": n,
        },
        "agents_sampled": agents,
        "source": source,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": (
            "Under Shadow, PERF times are simulated (near-zero). "
            "Use stagger = transaction_interval / num_users as the primary rule. "
            "See docs/shadow-tx-stagger.md for details."
        ),
        "formula": {
            "description": "stagger = transaction_interval / num_users",
            "stagger": "interval / num_users",
        },
    }

    if notify_counts:
        result["notify_events"] = notify_counts

    return result


def save_calibration(data: dict):
    """Save calibration data to ~/.monerosim/calibration.json."""
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Calibration saved to {CALIBRATION_PATH}")


def load_calibration() -> dict:
    """Load calibration data. Returns None if not found."""
    try:
        with open(CALIBRATION_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def show_calibration():
    """Display current calibration data and recommended settings."""
    data = load_calibration()
    if data is None:
        print("No calibration data found. Run: python scripts/calibrate.py")
        print()
        print("Default stagger formula: stagger = transaction_interval / num_users")
        print()
        print("  Example settings (interval=60s):")
        for n in [3, 5, 10, 20, 50]:
            stagger = compute_stagger(n, 60)
            print(f"    {n:3d} users: stagger = {stagger:3d}s")
        return

    v = data["verify_time_us"]
    print(f"MoneroSim Calibration ({data['timestamp']})")
    print(f"  Source: {data['source']}")
    print(f"  PERF add_tx samples: {v['samples']}")
    if data.get("notify_events"):
        total_notifs = sum(data["notify_events"].values())
        print(f"  NOTIFY_NEW_TRANSACTIONS events: {total_notifs} across {len(data['notify_events'])} daemons")
    print()
    print(f"  Stagger formula: stagger = transaction_interval / num_users")
    print()
    print(f"  Recommended settings (interval=60s):")
    for n in [3, 5, 10, 20, 50]:
        stagger = compute_stagger(n, 60)
        print(f"    {n:3d} users: stagger = {stagger:3d}s")


def compute_stagger(num_users: int, tx_interval: int, calibration: dict = None) -> int:
    """Compute the ideal activity_start_time stagger.

    The formula is: stagger = transaction_interval / num_users

    This ensures transaction generation is evenly distributed across
    simulated time, preventing any single daemon from being overwhelmed
    by verification work from other users' transactions.

    See docs/shadow-tx-stagger.md for the full explanation.

    Args:
        num_users: Number of user agents
        tx_interval: Transaction interval in seconds
        calibration: Unused (kept for API compatibility). The stagger
            depends only on interval and user count, not hardware.

    Returns:
        Stagger in seconds between consecutive users' activity_start_time
    """
    if num_users <= 0:
        return 0
    return max(1, tx_interval // num_users)


def run_calibration(monerosim_dir: str):
    """Run a calibration simulation and extract measurements."""
    print("Running calibration simulation (~5 min)...")

    # Write temporary config
    config_path = os.path.join(monerosim_dir, "test_configs", "_calibration.yaml")
    with open(config_path, "w") as f:
        f.write(CALIBRATION_CONFIG)

    try:
        # Run the simulation
        result = subprocess.run(
            ["bash", "run_sim.sh", "--config", config_path, "--no-monitor",
             "--name", "calibration"],
            cwd=monerosim_dir,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min max
        )

        if result.returncode != 0:
            print(f"Simulation failed (exit {result.returncode}):", file=sys.stderr)
            print(result.stderr[-500:] if result.stderr else "(no stderr)", file=sys.stderr)
            sys.exit(1)

        # Find the archived run
        archive_dir = Path(monerosim_dir) / "archived_runs"
        cal_runs = sorted(archive_dir.glob("*_calibration"), reverse=True)
        if not cal_runs:
            print("Error: calibration run not found in archived_runs/", file=sys.stderr)
            sys.exit(1)

        run_dir = str(cal_runs[0])
        print(f"Extracting from {run_dir}")

        data = extract_from_run(run_dir)
        save_calibration(data)
        show_calibration()

    finally:
        # Clean up temp config
        if os.path.exists(config_path):
            os.remove(config_path)


def main():
    parser = argparse.ArgumentParser(description="Calibrate MoneroSim timing parameters")
    parser.add_argument("--from-run", metavar="DIR",
                        help="Extract calibration from an existing archived run")
    parser.add_argument("--show", action="store_true",
                        help="Show current calibration data")
    args = parser.parse_args()

    if args.show:
        show_calibration()
        return

    if args.from_run:
        data = extract_from_run(args.from_run)
        save_calibration(data)
        show_calibration()
        return

    # Determine monerosim directory
    script_dir = Path(__file__).resolve().parent
    monerosim_dir = str(script_dir.parent)
    run_calibration(monerosim_dir)


if __name__ == "__main__":
    main()
