#!/usr/bin/env python3
"""smoke_assertions.py - Tier 2 Shadow smoke test assertions.

Reads an archived simulation run's outputs and applies stricter assertions
than the project's existing 4 PASS/FAIL success criteria. Designed to catch
regressions like "wallets sending only 3 txs each before dying" that slip
past the looser default checks.

This script is additive: it does NOT modify or replace
scripts/analyze_success_criteria.py. It runs against an already-archived run
and parses summary.txt and the run's log directories.

Usage:
    python3 scripts/smoke_assertions.py \\
        --run-dir archived_runs/20260507_184117_quickstart \\
        --baseline tests/baselines/quickstart_metrics.json

Exit codes:
    0  All assertions passed
    1  At least one assertion failed
    2  Run directory missing summary.txt (run did not complete)
    3  Baseline JSON file not found

The script is pure stdlib (argparse, json, re, pathlib). No external deps.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NO_SUMMARY = 2
EXIT_NO_BASELINE = 3


# ----------------------------------------------------------------------
# Parsing summary.txt
# ----------------------------------------------------------------------

# keep in sync with scripts/append_run_history.py:parse_wall_time (byte-identical)
def parse_wall_time(s: str) -> Optional[int]:
    """Convert e.g. '14m 48s' or '1h 2m 3s' to total seconds.

    Returns None (not 0) if `s` contains no parseable h/m/s tokens, so an
    unparseable/missing wall time can't be mistaken for a real 0s measurement.
    """
    total = 0
    matched = False
    for n, u in re.findall(r"(\d+)([hms])", s):
        matched = True
        n = int(n)
        if u == "h":
            total += n * 3600
        elif u == "m":
            total += n * 60
        elif u == "s":
            total += n
    return total if matched else None


def parse_summary(summary_path: Path) -> Dict[str, Any]:
    """Parse archived summary.txt into a dict. Robust to small format drift.

    Returns keys (all optional, fail-soft):
        wall_time_seconds: Optional[int] (None if the "Wall time:" line was
            present but unparseable; key absent entirely if the line was
            never found)
        exit_code: int
        success_criteria: dict[str, bool]   (4 sub-criteria)
        all_success_criteria_pass: bool
        nodes_online: int
        block_height: int
        blocks_mined: int
        alerts: int
        tx_created: int
        tx_in_blocks: int
        per_agent_tx: dict[str, int]
        per_node_height: dict[str, int]
    """
    text = summary_path.read_text()
    out: Dict[str, Any] = {}

    m = re.search(r"^Wall time:\s+(.+)$", text, re.MULTILINE)
    if m:
        out["wall_time_str"] = m.group(1).strip()
        out["wall_time_seconds"] = parse_wall_time(m.group(1))

    m = re.search(r"^Exit code:\s+(-?\d+)$", text, re.MULTILINE)
    if m:
        out["exit_code"] = int(m.group(1))

    sc: Dict[str, bool] = {}
    for label, key in [
        ("Blocks created", "blocks_created"),
        ("Blocks propagated", "blocks_propagated"),
        ("Transactions broadcast", "transactions_created_broadcast"),
        ("Transactions in blocks", "transactions_in_blocks"),
    ]:
        m = re.search(rf"^\s+{re.escape(label)}\s+(PASS|FAIL)$", text, re.MULTILINE)
        if m:
            sc[key] = m.group(1) == "PASS"
    if sc:
        out["success_criteria"] = sc
        out["all_success_criteria_pass"] = all(sc.values())

    m = re.search(r"Nodes online:\s+(\d+)", text)
    if m:
        out["nodes_online"] = int(m.group(1))
    m = re.search(r"Block height:\s+(\d+)", text)
    if m:
        out["block_height"] = int(m.group(1))
    m = re.search(r"Blocks mined:\s+(\d+)", text)
    if m:
        out["blocks_mined"] = int(m.group(1))
    m = re.search(r"Alerts:\s+(\d+)", text)
    if m:
        out["alerts"] = int(m.group(1))

    m = re.search(r"^\s+Created:\s+(\d+)$", text, re.MULTILINE)
    if m:
        out["tx_created"] = int(m.group(1))
    m = re.search(r"^\s+In blocks:\s+(\d+)$", text, re.MULTILINE)
    if m:
        out["tx_in_blocks"] = int(m.group(1))

    # Per-agent tx counts under "Created by:" section.
    cb = re.search(
        r"Created by:\s*\n((?:\s+\S+\s+\d+\s+txs\s*\n)+)",
        text,
    )
    per_agent: Dict[str, int] = {}
    if cb:
        for name, count in re.findall(r"\s+(\S+)\s+(\d+)\s+txs", cb.group(1)):
            per_agent[name] = int(count)
    out["per_agent_tx"] = per_agent

    # Node table: harvest final heights.
    ns = re.search(
        r"NODE STATUS \(final\)\s*\n-+\s*\n.*?Pool TXs\s*\n(.*?)(?:\n=+|\Z)",
        text,
        re.DOTALL,
    )
    per_node_height: Dict[str, int] = {}
    if ns:
        for line in ns.group(1).splitlines():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    per_node_height[parts[0]] = int(parts[1])
                except ValueError:
                    continue
    out["per_node_height"] = per_node_height

    return out


# ----------------------------------------------------------------------
# Assertion runner
# ----------------------------------------------------------------------

class Assertions:
    """Collect PASS/FAIL results and emit a final summary."""

    def __init__(self) -> None:
        self.results: List[Tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str) -> None:
        self.results.append((name, ok, detail))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")

    @property
    def failures(self) -> int:
        return sum(1 for _, ok, _ in self.results if not ok)

    @property
    def passes(self) -> int:
        return sum(1 for _, ok, _ in self.results if ok)


def assert_metrics(parsed: Dict[str, Any], expected: Dict[str, Any], a: Assertions) -> None:
    """Apply each numeric/equality assertion from baseline against parsed data."""

    # exit_code
    if "exit_code" in expected:
        actual = parsed.get("exit_code")
        ok = actual == expected["exit_code"]
        a.check("exit_code", ok, f"actual={actual} expected={expected['exit_code']}")

    # all_success_criteria_pass
    if "all_success_criteria_pass" in expected:
        actual = parsed.get("all_success_criteria_pass")
        ok = actual == expected["all_success_criteria_pass"]
        sc = parsed.get("success_criteria", {})
        detail = f"actual={actual} expected={expected['all_success_criteria_pass']}"
        if not ok:
            failed = [k for k, v in sc.items() if not v]
            detail += f" failing_subcriteria={failed}"
        a.check("all_success_criteria_pass", ok, detail)

    # max_alerts
    if "max_alerts" in expected:
        actual = parsed.get("alerts", -1)
        ok = actual <= expected["max_alerts"]
        a.check("max_alerts", ok, f"alerts={actual} <= {expected['max_alerts']}")

    # wall_time_seconds_max
    if "wall_time_seconds_max" in expected:
        actual = parsed.get("wall_time_seconds", -1)
        if actual is None:
            # "Wall time:" line was present but unparseable - don't let a
            # bogus 0 masquerade as "finished instantly"; fail explicitly.
            a.check(
                "wall_time_seconds_max",
                False,
                f"wall_time unparseable (raw={parsed.get('wall_time_str')!r})",
            )
        else:
            ok = actual <= expected["wall_time_seconds_max"]
            a.check(
                "wall_time_seconds_max",
                ok,
                f"wall_time={actual}s <= {expected['wall_time_seconds_max']}s",
            )

    # block_height_min
    if "block_height_min" in expected:
        actual = parsed.get("block_height", -1)
        ok = actual >= expected["block_height_min"]
        a.check("block_height_min", ok, f"{actual} >= {expected['block_height_min']}")

    # blocks_mined_min
    if "blocks_mined_min" in expected:
        actual = parsed.get("blocks_mined", -1)
        ok = actual >= expected["blocks_mined_min"]
        a.check("blocks_mined_min", ok, f"{actual} >= {expected['blocks_mined_min']}")

    # all_nodes_within_height_range
    if "all_nodes_within_height_range" in expected:
        heights = parsed.get("per_node_height", {})
        if heights:
            heights_list = list(heights.values())
            spread = max(heights_list) - min(heights_list)
            limit = expected["all_nodes_within_height_range"]
            ok = spread <= limit
            detail = f"max-min={spread} <= {limit} (nodes={len(heights)})"
            if not ok:
                detail += (
                    f" min_node={min(heights, key=heights.get)}@{min(heights_list)}"
                    f" max_node={max(heights, key=heights.get)}@{max(heights_list)}"
                )
            a.check("all_nodes_within_height_range", ok, detail)
        else:
            a.check(
                "all_nodes_within_height_range",
                False,
                "no per-node height data parsed from summary.txt",
            )

    # tx_created_min
    if "tx_created_min" in expected:
        actual = parsed.get("tx_created", -1)
        ok = actual >= expected["tx_created_min"]
        a.check("tx_created_min", ok, f"{actual} >= {expected['tx_created_min']}")

    # tx_in_blocks_ratio_min
    if "tx_in_blocks_ratio_min" in expected:
        created = parsed.get("tx_created", 0)
        in_blocks = parsed.get("tx_in_blocks", 0)
        ratio = (in_blocks / created) if created > 0 else 0.0
        ok = ratio >= expected["tx_in_blocks_ratio_min"]
        a.check(
            "tx_in_blocks_ratio_min",
            ok,
            f"{in_blocks}/{created}={ratio:.3f} >= {expected['tx_in_blocks_ratio_min']}",
        )

    # wallets_funded_exact: count of senders in "Created by:" section
    if "wallets_funded_exact" in expected:
        per_agent = parsed.get("per_agent_tx", {})
        actual = len(per_agent)
        ok = actual == expected["wallets_funded_exact"]
        a.check(
            "wallets_funded_exact",
            ok,
            f"{actual} senders == {expected['wallets_funded_exact']}",
        )

    # per_user_tx_floor: each user-* sender must have >= floor
    if "per_user_tx_floor" in expected:
        per_agent = parsed.get("per_agent_tx", {})
        floor = expected["per_user_tx_floor"]
        users = {n: c for n, c in per_agent.items() if n.startswith("user-")}
        if not users:
            a.check("per_user_tx_floor", False, "no user-* agents in tx-by-creator list")
        else:
            min_user, min_count = min(users.items(), key=lambda kv: kv[1])
            ok = min_count >= floor
            a.check(
                "per_user_tx_floor",
                ok,
                f"min user={min_user}@{min_count} >= {floor} (users={users})",
            )

    # per_miner_tx_floor: each miner-* sender must have >= floor.
    # Note: floor of 0 is intentionally permissive (Poisson variance).
    if "per_miner_tx_floor" in expected:
        per_agent = parsed.get("per_agent_tx", {})
        floor = expected["per_miner_tx_floor"]
        miners = {n: c for n, c in per_agent.items() if n.startswith("miner-")}
        if not miners:
            a.check(
                "per_miner_tx_floor",
                False,
                "no miner-* agents in tx-by-creator list",
            )
        else:
            min_miner, min_count = min(miners.items(), key=lambda kv: kv[1])
            ok = min_count >= floor
            a.check(
                "per_miner_tx_floor",
                ok,
                f"min miner={min_miner}@{min_count} >= {floor} (miners={miners})",
            )


# ----------------------------------------------------------------------
# Log-pattern checks
# ----------------------------------------------------------------------

def find_log_files(run_dir: Path) -> List[Path]:
    """Return all files we should grep for disallowed patterns."""
    files: List[Path] = []
    daemon_logs = run_dir / "daemon_logs"
    if daemon_logs.is_dir():
        files.extend(daemon_logs.rglob("bitmonero.log"))
    hosts = run_dir / "shadow.data" / "hosts"
    if hosts.is_dir():
        # Per-agent stdout/stderr from Shadow (Python agent + monerod + wallet-rpc).
        for ext in ("stdout", "stderr"):
            files.extend(hosts.rglob(f"*.{ext}"))
    return files


def grep_patterns(
    files: List[Path], patterns: List[str], a: Assertions
) -> None:
    """For each disallowed pattern, scan all log files. Any match -> FAIL.

    We check each pattern as a single overall assertion (one PASS/FAIL line per
    pattern), with the first offending file:line printed in the detail.
    """
    if not patterns:
        return

    # Pre-compile as case-sensitive (matches how the project surfaces these).
    compiled = [(p, re.compile(re.escape(p))) for p in patterns]
    hits: Dict[str, List[Tuple[Path, int, str]]] = {p: [] for p in patterns}

    for f in files:
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, 1):
                    for pat, regex in compiled:
                        if regex.search(line):
                            hits[pat].append((f, lineno, line.rstrip()))
                            # Don't break: a single line can match multiple patterns.
        except OSError:
            continue

    for pat in patterns:
        matches = hits[pat]
        if not matches:
            a.check(f"log_pattern: {pat!r}", True, "0 matches")
        else:
            first_file, first_line, first_text = matches[0]
            try:
                rel = first_file.relative_to(Path.cwd())
            except ValueError:
                rel = first_file
            a.check(
                f"log_pattern: {pat!r}",
                False,
                (
                    f"{len(matches)} match(es); first @ {rel}:{first_line} -> "
                    f"{first_text[:200]}"
                ),
            )


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def derive_default_baseline(run_dir: Path) -> Optional[Path]:
    """archived_runs/<TS>_<scenario>/  ->  tests/baselines/<scenario>_metrics.json"""
    name = run_dir.name
    # Format: YYYYMMDD_HHMMSS_<scenario>
    m = re.match(r"\d{8}_\d{6}_(.+)$", name)
    if not m:
        return None
    scenario = m.group(1)
    repo_root = Path(__file__).resolve().parent.parent
    cand = repo_root / "tests" / "baselines" / f"{scenario}_metrics.json"
    return cand


def main() -> int:
    p = argparse.ArgumentParser(
        description="Tier 2 smoke assertions over an archived simulation run.",
    )
    p.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Path to the archived run directory (e.g. archived_runs/<TS>_<scenario>/).",
    )
    p.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=(
            "Path to the baseline JSON. Defaults to "
            "tests/baselines/<scenario>_metrics.json derived from --run-dir."
        ),
    )
    args = p.parse_args()

    run_dir: Path = args.run_dir.resolve()
    summary_path = run_dir / "summary.txt"
    if not summary_path.is_file():
        print(
            f"ERROR: run did not complete; missing summary.txt at {summary_path}",
            file=sys.stderr,
        )
        return EXIT_NO_SUMMARY

    if args.baseline is not None:
        baseline_path = args.baseline.resolve()
    else:
        derived = derive_default_baseline(run_dir)
        if derived is None:
            print(
                "ERROR: could not derive baseline path from run-dir name; "
                "pass --baseline explicitly.",
                file=sys.stderr,
            )
            return EXIT_NO_BASELINE
        baseline_path = derived

    if not baseline_path.is_file():
        print(
            f"ERROR: baseline file not found at {baseline_path}; "
            "pass --baseline explicitly or capture one.",
            file=sys.stderr,
        )
        return EXIT_NO_BASELINE

    print(f"Run dir:  {run_dir}")
    print(f"Baseline: {baseline_path}")
    print()

    baseline = json.loads(baseline_path.read_text())
    expected: Dict[str, Any] = baseline.get("expected", {})
    disallowed: List[str] = baseline.get("log_patterns_disallowed", [])

    parsed = parse_summary(summary_path)
    a = Assertions()
    assert_metrics(parsed, expected, a)

    print()
    print("Log pattern checks:")
    log_files = find_log_files(run_dir)
    print(f"  scanning {len(log_files)} log file(s)")
    grep_patterns(log_files, disallowed, a)

    print()
    print(f"Smoke assertions: {a.passes} PASS, {a.failures} FAIL")
    return EXIT_OK if a.failures == 0 else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
