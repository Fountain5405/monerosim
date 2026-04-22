#!/usr/bin/env python3
"""
Calibrate MoneroSim timing parameters for the current hardware.

Runs Monero's built-in performance_tests binary to measure the real CPU cost
of transaction verification (CLSAG ring signatures, Bulletproofs+ range proofs)
on this machine.  Results are saved to ~/.monerosim/calibration.json and used
by generate_config.py and scenario_parser.py to compute safe stagger and
transaction_interval values.

Usage:
    python scripts/calibrate.py              # Run calibration (~30 s)
    python scripts/calibrate.py --show       # Show current calibration
    python scripts/calibrate.py --build      # Build perf binary first
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CALIBRATION_PATH = Path.home() / ".monerosim" / "calibration.json"

# Relative from this script's directory to the Monero source root
_MONERO_SRC_RELATIVE = "../../monero"
_PERF_BINARY_SUBPATH = "build/release/tests/performance_tests/performance_tests"


# ---------------------------------------------------------------------------
# Binary discovery / build
# ---------------------------------------------------------------------------

def _monero_root() -> Path:
    return (Path(__file__).resolve().parent / _MONERO_SRC_RELATIVE).resolve()


def find_perf_binary() -> "Path | None":
    """Return the performance_tests binary path, or None."""
    p = _monero_root() / _PERF_BINARY_SUBPATH
    return p if p.is_file() else None


def build_perf_binary() -> Path:
    """Enable BUILD_TESTS in CMake and compile performance_tests."""
    build_dir = _monero_root() / "build" / "release"
    if not build_dir.is_dir():
        raise CalibrationError(
            f"Monero build dir not found at {build_dir}")

    print("Configuring CMake with BUILD_TESTS=ON ...")
    r = subprocess.run(
        ["cmake", "-DBUILD_TESTS=ON", "../.."],
        cwd=str(build_dir), capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise CalibrationError(
            f"cmake configure failed:\n{r.stderr[-2000:]}")

    nproc = os.cpu_count() or 4
    print(f"Building performance_tests (make -j{nproc}) ...")
    r = subprocess.run(
        ["cmake", "--build", ".", "--target", "performance_tests",
         "--", f"-j{nproc}"],
        cwd=str(build_dir), capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise CalibrationError(
            f"Build failed:\n{r.stderr[-2000:]}")

    binary = build_dir / "tests" / "performance_tests" / "performance_tests"
    if not binary.is_file():
        raise CalibrationError(
            f"binary not produced at {binary}")

    print(f"  Built: {binary}")
    return binary


# ---------------------------------------------------------------------------
# Benchmark execution & parsing
# ---------------------------------------------------------------------------

def _run_bench(binary: Path, filt: str, timeout: int = 600) -> str:
    """Run performance_tests with --filter/--stats/--verbose, return stdout."""
    r = subprocess.run(
        [str(binary), f"--filter={filt}", "--stats", "--verbose"],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Benchmark failed (rc={r.returncode}):\n{r.stderr}")
    return r.stdout


def parse_bench_output(stdout: str) -> dict:
    """Parse verbose+stats output into {test_name: {metric: value_ns}}."""
    tests = {}
    cur = None

    for line in stdout.splitlines():
        # Header: "test_sig_clsag<16, 2, 2> - OK:"
        m = re.match(r"^(test_\w+<[^>]+>)\s*-\s*OK:", line)
        if m:
            cur = m.group(1)
            tests[cur] = {}
            continue
        if cur is None:
            continue

        # Raw stat lines (always in ns): "  median:    23464559 ns"
        m = re.match(r"^\s+(min|max|median|std dev|loop count|elapsed):\s+(\S+)", line)
        if m:
            key = m.group(1).replace(" ", "_")
            try:
                tests[cur][key] = float(m.group(2))
            except ValueError:
                pass
            continue

        # Summary line with dynamic units:
        #  (min 22966 µs, 90th 23877 µs, median 23464 µs, std dev 644 µs)
        #  (min 112 ms, 90th 115 ms, median 112 ms, std dev 1 ms)
        m = re.match(
            r"\s*\(min\s+([\d.]+)\s+(µs|ms),\s*90th\s+([\d.]+)\s+(µs|ms)",
            line,
        )
        if m:
            def _to_us(val, unit):
                v = float(val)
                return int(v * 1000) if unit == "ms" else int(v)
            tests[cur]["p90_us"] = _to_us(m.group(3), m.group(4))

    return tests


# ---------------------------------------------------------------------------
# Calibration logic
# ---------------------------------------------------------------------------

class CalibrationError(RuntimeError):
    """Raised when calibration cannot complete."""


def run_calibration(do_build: bool = False):
    """Run crypto benchmarks and save calibration data.

    Raises CalibrationError on failure (instead of sys.exit) so callers
    like ensure_calibrated() can catch and fall back gracefully.
    """
    binary = find_perf_binary()
    if binary is None or do_build:
        binary = build_perf_binary()
    if binary is None:
        raise CalibrationError(
            "performance_tests not found. Run with --build to compile.")

    print(f"Binary: {binary}\n")

    # -- CLSAG ring-signature verification --
    # Ring size 16, 2 inputs, 2 outputs — standard Monero tx since hard-fork 14
    print("Benchmarking CLSAG verification (ring 16, 2-in/2-out) ...")
    clsag_out = _run_bench(binary, "*clsag<16*")
    clsag_data = parse_bench_output(clsag_out)

    clsag_key = "test_sig_clsag<16, 2, 2>"
    if clsag_key not in clsag_data:
        raise CalibrationError(
            f"{clsag_key} not in results: {list(clsag_data)}")
    clsag = clsag_data[clsag_key]

    # -- Bulletproofs+ range-proof verification --
    # false = verify (not prove), 2 outputs
    print("Benchmarking Bulletproofs+ verification (2 outputs) ...")
    bp_out = _run_bench(binary, "*bulletproof_plus<false, 2>*")
    bp_data = parse_bench_output(bp_out)

    bp_key = "test_bulletproof_plus<false, 2>"
    if bp_key not in bp_data:
        raise CalibrationError(
            f"{bp_key} not in results: {list(bp_data)}")
    bp = bp_data[bp_key]

    # -- Compose total tx verification estimate --
    def _ns_to_us(v): return int(v / 1000)

    clsag_median_us = _ns_to_us(clsag["median"])
    bp_median_us    = _ns_to_us(bp["median"])

    # p90 from summary line, fall back to raw p90 ≈ median + 1.3·σ
    clsag_p90_us = clsag.get("p90_us", clsag_median_us + int(1.3 * clsag.get("std_dev", 0) / 1000))
    bp_p90_us    = bp.get("p90_us",    bp_median_us    + int(1.3 * bp.get("std_dev", 0) / 1000))

    # p95 ≈ p90 + 0.5·σ  (a rough approximation, fine given 3× safety factor)
    clsag_sigma_us = _ns_to_us(clsag.get("std_dev", 0))
    bp_sigma_us    = _ns_to_us(bp.get("std_dev", 0))
    combined_sigma = int(math.sqrt(clsag_sigma_us**2 + bp_sigma_us**2))

    total_p50 = clsag_median_us + bp_median_us
    total_p90 = clsag_p90_us + bp_p90_us
    total_p95 = total_p90 + combined_sigma // 2
    total_max = _ns_to_us(clsag.get("max", 0)) + _ns_to_us(bp.get("max", 0))

    clsag_loops = int(clsag.get("loop_count", 0))
    bp_loops    = int(bp.get("loop_count", 0))

    calibration = {
        "verify_time_us": {
            "p50": total_p50,
            "p95": total_p95,
            "p99": total_max,
            "max": total_max,
            "samples": min(clsag_loops, bp_loops),
        },
        "components": {
            "clsag_ring16_2in_2out": {
                "median_us": clsag_median_us,
                "p90_us": clsag_p90_us,
                "stddev_us": clsag_sigma_us,
                "loops": clsag_loops,
            },
            "bulletproof_plus_verify_2out": {
                "median_us": bp_median_us,
                "p90_us": bp_p90_us,
                "stddev_us": bp_sigma_us,
                "loops": bp_loops,
            },
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": "performance_tests",
        "binary": str(binary),
    }

    save_calibration(calibration)
    print()
    show_calibration()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_calibration(data: dict):
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nCalibration saved to {CALIBRATION_PATH}")


def load_calibration() -> "dict | None":
    """Load calibration data.  Returns None if file is missing."""
    try:
        with open(CALIBRATION_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Auto-calibration
# ---------------------------------------------------------------------------

_auto_calibrate_disabled = False
_auto_calibrate_attempted = False


def disable_auto_calibration():
    """Suppress auto-calibration for this process (--no-calibrate)."""
    global _auto_calibrate_disabled
    _auto_calibrate_disabled = True


def ensure_calibrated():
    """Run calibration automatically if no data exists yet.

    Called by compute_stagger() on first use.  Safe to call multiple times —
    only attempts once per process and only if calibration.json is missing.
    Skipped entirely if disable_auto_calibration() was called.
    """
    global _auto_calibrate_attempted
    if _auto_calibrate_disabled or _auto_calibrate_attempted:
        return
    _auto_calibrate_attempted = True

    if load_calibration() is not None:
        return

    print("No calibration data found — running first-time calibration (~30 s) ...")
    try:
        run_calibration()
    except (CalibrationError, Exception) as e:
        print(f"Warning: auto-calibration failed: {e}", file=sys.stderr)
        print("  Falling back to stagger = transaction_interval / num_users",
              file=sys.stderr)


# ---------------------------------------------------------------------------
# Stagger computation  (imported by generate_config / scenario_parser)
# ---------------------------------------------------------------------------
#
# There are two independent reasons to floor transaction_interval:
#
# 1) **Per-wallet crypto cost** (CRYPTO_SAFETY_FACTOR × N × p95). Each tx
#    needs CLSAG + Bulletproofs+ verification locally. This dominates for
#    small single-box simulations with few network nodes.
#
# 2) **Shadow event-storm cost** (N × M × SHADOW_EVENT_COST_S / C). Each tx
#    propagates to every daemon (M nodes), each propagation is a Shadow
#    event, and Shadow can only process so many events per real second
#    across its worker threads (C cores). Past a certain event rate the
#    sim's wall-clock time explodes or the clock stalls entirely.
#
# The effective minimum is max(crypto_floor, shadow_floor). For small
# sims (few nodes, lots of cores) crypto_floor dominates; for large sims
# (1000+ nodes) shadow_floor dominates by orders of magnitude.
#
# CRYPTO_SAFETY_FACTOR derivation: a small multiple of p95 accounts for
# multi-input txs and variance. 3 is fine since the Shadow floor almost
# always dominates.
CRYPTO_SAFETY_FACTOR = 3

# SHADOW_EVENT_COST_S derivation: empirical from a known-good run that
# produced 100/100 surviving wallets over 48h:
#   N=100 users, M=1000 nodes, C=256 cores, interval=1200s → works
#   K = interval × C / (N × M) = 1200 × 256 / (100 × 1000) = 3.07
# This represents "real CPU-seconds per user-per-node-per-(1/interval)".
# Raising it is safer/slower; lowering it is faster but risks Shadow
# stalling under event load. 3.0 matches the empirical data point.
SHADOW_EVENT_COST_S = 3.0


def _get_core_count(num_cores=None):
    """Resolve core count: explicit > nproc > conservative fallback."""
    if num_cores and num_cores > 0:
        return num_cores
    try:
        n = os.cpu_count()
        return n if n else 4
    except Exception:
        return 4


def compute_min_safe_interval(num_users, num_nodes=None, num_cores=None):
    """Return the minimum safe transaction_interval (seconds).

    Args:
        num_users: number of agents that will send user transactions
        num_nodes: total nodes in the simulated network (tx-propagation target
                   count). Defaults to num_users if unknown (conservative).
        num_cores: Shadow worker cores available on this machine. Defaults
                   to os.cpu_count().

    Returns 0 if no calibration data exists.
    """
    if num_users <= 0:
        return 0
    ensure_calibrated()
    cal = load_calibration()
    if not cal or cal.get("verify_time_us", {}).get("samples", 0) <= 0:
        return 0

    # Crypto floor: per-tx verification cost.
    p95_s = cal["verify_time_us"]["p95"] / 1_000_000
    crypto_floor = int(num_users * p95_s * CRYPTO_SAFETY_FACTOR)

    # Shadow event-storm floor: prevents the simulator from being overwhelmed
    # by tx-propagation events at the configured user count × network size.
    if num_nodes is None:
        num_nodes = num_users  # fallback: assume worst-case every node is a user
    cores = _get_core_count(num_cores)
    shadow_floor = int(num_users * num_nodes * SHADOW_EVENT_COST_S / cores)

    return max(crypto_floor, shadow_floor)


def compute_safe_interval(num_users, requested_interval,
                          num_nodes=None, num_cores=None):
    """Return the requested interval, or the calibrated minimum if higher.

    Callers should overwrite the user's transaction_interval with this value
    (and warn) so the actual sustained tx rate matches what the calibrator
    deems safe for this user count, network size, and hardware.
    """
    return max(requested_interval,
               compute_min_safe_interval(num_users, num_nodes, num_cores))


def compute_stagger(num_users, tx_interval, num_nodes=None, num_cores=None):
    """Compute the activity_start_time stagger between users.

    Formula:  stagger = max(1, safe_interval / num_users)

    Automatically runs calibration on first call if no data exists.
    See docs/shadow-tx-stagger.md for the full explanation.
    """
    if num_users <= 0:
        return 0
    effective_interval = compute_safe_interval(num_users, tx_interval,
                                               num_nodes, num_cores)
    return max(1, effective_interval // num_users)


# ---------------------------------------------------------------------------
# Polling-interval calibration
# ---------------------------------------------------------------------------
#
# simulation-monitor and miner-distributor both periodically iterate every
# node in the network and call its RPC. That's M RPC events per poll cycle,
# so events/sim-sec from polling = M / poll_interval. If this value gets
# close to Shadow's per-core throughput, polling alone stalls the simulation
# during bootstrap (before any user activity starts).
#
# Empirical anchor: the working full-scale run used poll_interval=300 at
# M=1000 nodes -> 3.3 RPC events/sec. Combined with mining propagation
# (~M/120 = 8.3 events/sec), total baseline was ~11.7 events/sec on 256
# cores -- comfortable. Setting MONITOR_TARGET_RATE = 3 keeps monitor cost
# in the same ballpark across scales.

MONITOR_TARGET_RATE = 3.0   # max RPC events/sim-sec from polling
MIN_POLL_INTERVAL_S = 60    # don't poll faster than this regardless


def compute_safe_poll_interval(num_nodes):
    """Recommended poll_interval (sec) for monitor / distributor at this scale."""
    if num_nodes is None or num_nodes <= 0:
        return MIN_POLL_INTERVAL_S
    rate_based = int(num_nodes / MONITOR_TARGET_RATE)
    return max(MIN_POLL_INTERVAL_S, rate_based)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def show_calibration():
    data = load_calibration()
    if data is None:
        print("No calibration data found.  Run:  python scripts/calibrate.py")
        return

    v = data.get("verify_time_us", {})
    samples = v.get("samples", 0)
    print(f"MoneroSim Calibration  ({data.get('timestamp', '?')})")
    print(f"  Method:  {data.get('method', '?')}")

    comp = data.get("components", {})
    for label, key in [("CLSAG (ring 16, 2-in/2-out)", "clsag_ring16_2in_2out"),
                       ("Bulletproofs+ verify (2-out)", "bulletproof_plus_verify_2out")]:
        c = comp.get(key, {})
        if c:
            print(f"  {label}:  median {c['median_us']:,} µs  "
                  f"p90 {c['p90_us']:,} µs  ({c.get('loops', '?')} loops)")

    if samples > 0:
        print(f"\n  Combined tx verification estimate:")
        print(f"    p50: {v['p50']:,} µs  ({v['p50']/1000:.1f} ms)")
        print(f"    p95: {v['p95']:,} µs  ({v['p95']/1000:.1f} ms)")
        print(f"    max: {v['max']:,} µs  ({v['max']/1000:.1f} ms)")

        p95_s = v["p95"] / 1_000_000
        safety = SAFETY_FACTOR
        print(f"\n  Recommended min transaction_interval (p95×{safety}×N):")
        print(f"  {'Users':>6}  {'Min interval':>14}  {'Stagger (iv=60s)':>18}")
        print(f"  {'-----':>6}  {'-'*14:>14}  {'-'*18:>18}")
        for n in [3, 5, 10, 20, 50, 100, 500, 1000]:
            min_iv = max(1, int(n * p95_s * safety))
            eff_iv = max(60, min_iv)
            stagger = max(MIN_WAKEUP_STAGGER_S, eff_iv // n, 1)
            print(f"  {n:>6}  {min_iv:>12} s  {stagger:>16} s")
        print(f"\n  Stagger floor: MIN_WAKEUP_STAGGER_S = {MIN_WAKEUP_STAGGER_S}s")
    else:
        print("  No data — stagger = transaction_interval / num_users")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Calibrate MoneroSim timing for this hardware")
    ap.add_argument("--show", action="store_true",
                    help="Show current calibration data")
    ap.add_argument("--build", action="store_true",
                    help="(Re)build the performance_tests binary before running")
    args = ap.parse_args()

    if args.show:
        show_calibration()
        return

    try:
        run_calibration(do_build=args.build)
    except CalibrationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
