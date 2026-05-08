#!/usr/bin/env python3
"""append_run_history.py - Append one row to a per-scenario run-history CSV.

Reads an archived simulation run's outputs and appends a single row to
``tests/baselines/<scenario>_run_history.csv``. The CSV accumulates one row
per smoke-test invocation and lives alongside the existing baseline JSON.

Designed to be wired into ``scripts/smoke_test.sh`` after the existing
``smoke_assertions.py`` step, so each smoke run leaves a trail.

Usage:
    python3 scripts/append_run_history.py \\
        --run-dir archived_runs/<TS>_<scenario>/ \\
        --scenario <name> \\
        --result PASS|FAIL

Behavior:
    * Creates the CSV (with header) if it does not yet exist.
    * Appends one row per invocation.
    * Pure stdlib (argparse, csv, json, re, subprocess, pathlib, statistics).
    * On any parsing error or missing data, the affected column is written
      empty rather than raising. The script still exits 0 in that case so
      it does not break the surrounding smoke wrapper.
    * Hard failures (run-dir does not exist, missing summary.txt) emit a
      warning to stderr and exit 1. The smoke wrapper is expected to
      tolerate non-zero (i.e. ``|| true``) so the smoke result itself is
      not falsified.

Exit codes:
    0  Row appended successfully.
    1  Run dir or summary.txt not found.
"""

import argparse
import csv
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

EXIT_OK = 0
EXIT_INPUT_MISSING = 1

# Single source of truth for column order. Keep this stable; if you add
# columns, append at the end so existing CSVs stay readable.
COLUMNS = [
    "run_id",
    "date",
    "commit_hash",
    "scenario",
    "smoke_result",
    "wall_seconds",
    "exit_code",
    "success_criteria_pass",
    "block_height",
    "blocks_mined",
    "total_tx_created",
    "total_tx_in_blocks",
    "tx_in_blocks_ratio",
    "alerts",
    "sync_pct",
    "nodes_online",
    "per_user_min",
    "per_user_max",
    "per_user_median",
    "per_miner_min",
    "per_miner_max",
    "per_miner_median",
]


def parse_wall_time(s: str) -> Optional[int]:
    """Convert e.g. '14m 48s' or '1h 2m 3s' to total seconds."""
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
    """Parse archived summary.txt into a dict. Robust to small format drift."""
    text = summary_path.read_text()
    out: Dict[str, Any] = {}

    m = re.search(r"^Wall time:\s+(.+)$", text, re.MULTILINE)
    if m:
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

    cb = re.search(
        r"Created by:\s*\n((?:\s+\S+\s+\d+\s+txs\s*\n)+)",
        text,
    )
    per_agent: Dict[str, int] = {}
    if cb:
        for name, count in re.findall(r"\s+(\S+)\s+(\d+)\s+txs", cb.group(1)):
            per_agent[name] = int(count)
    out["per_agent_tx"] = per_agent
    return out


def parse_sync_pct(run_dir: Path) -> Optional[float]:
    """Extract avg_sync_percentage from monitoring/final_report.json if present."""
    fr = run_dir / "monitoring" / "final_report.json"
    if not fr.is_file():
        return None
    try:
        with fr.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    s = data.get("summary", {})
    val = s.get("avg_sync_percentage")
    if isinstance(val, (int, float)):
        return float(val)
    return None


def derive_date_from_run_id(run_id: str) -> Optional[str]:
    """Extract YYYY-MM-DD from a run_id like '20260508_015955_refactor_gate'."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})_\d{6}_", run_id)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def get_commit_hash(repo_root: Path) -> str:
    """Return short HEAD commit hash, or 'unknown' if git is not available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def split_user_miner(per_agent: Dict[str, int]) -> Dict[str, List[int]]:
    """Bucket per-agent tx counts by name prefix."""
    users = [c for n, c in per_agent.items() if n.startswith("user-")]
    miners = [c for n, c in per_agent.items() if n.startswith("miner-")]
    return {"users": users, "miners": miners}


def stats_or_blank(values: List[int]) -> Dict[str, str]:
    """Return min/max/median as strings; blanks if list empty."""
    if not values:
        return {"min": "", "max": "", "median": ""}
    return {
        "min": str(min(values)),
        "max": str(max(values)),
        # Use round(median, 1) to keep floats like 12.5 readable.
        "median": f"{statistics.median(values):g}",
    }


def build_row(
    run_dir: Path,
    scenario: str,
    result: str,
    commit_hash: str,
) -> Dict[str, str]:
    summary_path = run_dir / "summary.txt"
    parsed = parse_summary(summary_path)
    sync_pct = parse_sync_pct(run_dir)

    per_agent = parsed.get("per_agent_tx", {})
    bucket = split_user_miner(per_agent)
    user_stats = stats_or_blank(bucket["users"])
    miner_stats = stats_or_blank(bucket["miners"])

    tx_created = parsed.get("tx_created")
    tx_in_blocks = parsed.get("tx_in_blocks")
    if (
        isinstance(tx_created, int)
        and isinstance(tx_in_blocks, int)
        and tx_created > 0
    ):
        ratio = f"{tx_in_blocks / tx_created:.4f}"
    else:
        ratio = ""

    def s(v: Any) -> str:
        return "" if v is None else str(v)

    row = {
        "run_id": run_dir.name,
        "date": derive_date_from_run_id(run_dir.name) or "",
        "commit_hash": commit_hash,
        "scenario": scenario,
        "smoke_result": result,
        "wall_seconds": s(parsed.get("wall_time_seconds")),
        "exit_code": s(parsed.get("exit_code")),
        "success_criteria_pass": s(parsed.get("all_success_criteria_pass")),
        "block_height": s(parsed.get("block_height")),
        "blocks_mined": s(parsed.get("blocks_mined")),
        "total_tx_created": s(tx_created),
        "total_tx_in_blocks": s(tx_in_blocks),
        "tx_in_blocks_ratio": ratio,
        "alerts": s(parsed.get("alerts")),
        "sync_pct": "" if sync_pct is None else f"{sync_pct:.4f}",
        "nodes_online": s(parsed.get("nodes_online")),
        "per_user_min": user_stats["min"],
        "per_user_max": user_stats["max"],
        "per_user_median": user_stats["median"],
        "per_miner_min": miner_stats["min"],
        "per_miner_max": miner_stats["max"],
        "per_miner_median": miner_stats["median"],
    }
    return row


def append_row(csv_path: Path, row: Dict[str, str]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Append a single per-run row to "
            "tests/baselines/<scenario>_run_history.csv."
        ),
    )
    p.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Path to the archived run directory (e.g. archived_runs/<TS>_<scenario>/).",
    )
    p.add_argument(
        "--scenario",
        required=True,
        help="Scenario name (used for both the row column and the CSV filename).",
    )
    p.add_argument(
        "--result",
        required=True,
        choices=["PASS", "FAIL"],
        help="Overall smoke-test result.",
    )
    p.add_argument(
        "--commit-hash",
        default=None,
        help=(
            "Override the recorded commit hash. Defaults to "
            "`git rev-parse --short HEAD` in the repo root. Useful for backfill."
        ),
    )
    p.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Override the output CSV path. Defaults to "
            "tests/baselines/<scenario>_run_history.csv."
        ),
    )
    args = p.parse_args()

    run_dir: Path = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run-dir does not exist: {run_dir}", file=sys.stderr)
        return EXIT_INPUT_MISSING

    summary_path = run_dir / "summary.txt"
    if not summary_path.is_file():
        print(
            f"ERROR: missing summary.txt at {summary_path} (run did not complete)",
            file=sys.stderr,
        )
        return EXIT_INPUT_MISSING

    repo_root = Path(__file__).resolve().parent.parent
    commit_hash = args.commit_hash or get_commit_hash(repo_root)

    if args.csv is not None:
        csv_path = args.csv.resolve()
    else:
        csv_path = repo_root / "tests" / "baselines" / f"{args.scenario}_run_history.csv"

    row = build_row(run_dir, args.scenario, args.result, commit_hash)
    append_row(csv_path, row)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
