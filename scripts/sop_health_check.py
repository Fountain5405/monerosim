#!/usr/bin/env python3
"""Daemon-log health check for fork-choice experiments.

Review 2026-09-25 (docs/20260925_e4_code_data_review.md): the SoP v2 cells
"worked" on a binary whose every reorganization threw, and both honest
controls never forked. Both facts were in the daemon logs and nothing
looked. This looks, per node:

  reorg_started    '###### REORGANIZE'
  reorg_success    'REORGANIZE SUCCESS'
  exceptions       'Exception at [add_new_block]'
  alt_added        'BLOCK ADDED AS ALTERNATIVE'
  decisions        'SIM-PoP: fork' / 'SIM-SoP: fork' lines (objective / tie / switch)
  share_weighted   decisions where a chain's weight exceeds unit * length:
                   for SoP (unit = diff/w) at least one share counted; for
                   PoP (unit 1) at least one uncle bonus counted

A run FAILS when any node has reorg_started != reorg_success or
exceptions > 0. --require-forks also fails when no non-attacker node
accepted an alternative block (a fork-free control validates nothing);
--require-share-weight fails when no subjective SoP decision carried a
share-augmented weight (the share term is inert).

Usage: sop_health_check.py <run_dir> [--unit N | --diff D --w W]
                            [--require-forks] [--require-share-weight] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RE_DECISION = re.compile(
    r"SIM-(PoP|SoP): fork (\d+) (OBJECTIVE )?(alt|TIE) (\d+)/(\d+) vs (?:main )?(\d+)/(\d+)"
    r".*?-> (SWITCH|KEEP)")
ATTACKER_NODE = re.compile(r"attacker|bridge", re.I)


def scan_log_text(text: str, unit: int | None = None) -> dict:
    """Count the health markers in one daemon log."""
    n = {"reorg_started": 0, "reorg_success": 0, "exceptions": 0, "alt_added": 0,
         "decisions": 0, "objective": 0, "ties": 0, "switches": 0,
         "sop_subjective": 0, "share_weighted": 0}
    for line in text.splitlines():
        if "###### REORGANIZE" in line:
            n["reorg_started"] += 1
        elif "REORGANIZE SUCCESS" in line:
            n["reorg_success"] += 1
        elif "Exception at [add_new_block]" in line:
            n["exceptions"] += 1
        elif "BLOCK ADDED AS ALTERNATIVE" in line:
            n["alt_added"] += 1
        elif "SIM-PoP: fork" in line or "SIM-SoP: fork" in line:
            m = RE_DECISION.search(line)
            if not m:
                continue
            engine, _fork, objective, kind, w_alt, l_alt, w_main, l_main, outcome = m.groups()
            n["decisions"] += 1
            if objective:
                n["objective"] += 1
            if kind == "TIE":
                n["ties"] += 1
            if outcome == "SWITCH":
                n["switches"] += 1
            if objective:
                continue
            # A block weighs lb*unit*(1+counted shares) under SoP and
            # lb*(1+uncle bonus) under PoP: any chain heavier than
            # unit*length had a share / uncle counted (weights are always
            # multiples of the unit, so divisibility cannot tell).
            u = unit if engine == "SoP" else 1
            if engine == "SoP":
                n["sop_subjective"] += 1
            if u and (int(w_alt) > u * int(l_alt) or int(w_main) > u * int(l_main)):
                n["share_weighted"] += 1
    return n


def check_run(run_dir: Path, unit: int | None = None) -> dict:
    """Scan every daemon log under <run_dir>/daemon_logs; return the report."""
    run_dir = Path(run_dir)
    nodes: dict[str, dict] = {}
    for log in sorted(run_dir.glob("daemon_logs/*/bitmonero.log")):
        name = log.parent.name.removeprefix("monero-")
        nodes[name] = scan_log_text(log.read_text(errors="replace"), unit)
    problems = []
    for name, n in nodes.items():
        if n["reorg_started"] != n["reorg_success"]:
            problems.append(f"{name}: reorg {n['reorg_success']}/{n['reorg_started']} succeeded")
        if n["exceptions"]:
            problems.append(f"{name}: {n['exceptions']} add_new_block exceptions")
    forks_seen = sum(n["alt_added"] for name, n in nodes.items()
                     if not ATTACKER_NODE.search(name))
    share_weighted = sum(n["share_weighted"] for n in nodes.values())
    totals = {k: sum(n[k] for n in nodes.values()) for k in
              ("reorg_started", "reorg_success", "exceptions", "alt_added", "decisions")}
    return {"run_dir": str(run_dir), "nodes": nodes, "totals": totals,
            "forks_seen": forks_seen, "share_weighted": share_weighted,
            "problems": problems, "ok": not problems and bool(nodes)}


def summarize(report: dict | None) -> str:
    """One short token for a results table."""
    if not report:
        return "-"
    if not report.get("nodes"):
        return "no-logs"
    t = report["totals"]
    parts = []
    if t["reorg_started"] != t["reorg_success"]:
        parts.append(f"REORG {t['reorg_success']}/{t['reorg_started']}")
    if t["exceptions"]:
        parts.append(f"EXC {t['exceptions']}")
    if not report.get("forks_seen"):
        parts.append("no-forks")
    return "; ".join(parts) if parts else "ok"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--unit", type=int, help="SoP unit weight diff/w (share-weight detection)")
    ap.add_argument("--diff", type=int, help="block difficulty (with --w, derives --unit)")
    ap.add_argument("--w", type=int, help="workshare ratio w (with --diff)")
    ap.add_argument("--require-forks", action="store_true")
    ap.add_argument("--require-share-weight", action="store_true")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    a = ap.parse_args(argv)
    unit = a.unit or (a.diff // a.w if a.diff and a.w else None)
    rep = check_run(a.run_dir, unit)
    if a.require_forks and not rep["forks_seen"]:
        rep["problems"].append("no non-attacker node accepted an alternative block (fork-free run)")
        rep["ok"] = False
    if a.require_share_weight and not rep["share_weighted"]:
        rep["problems"].append("no fork decision carried a share/uncle-augmented weight")
        rep["ok"] = False
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for name, n in rep["nodes"].items():
            print(f"{name:22s} reorg {n['reorg_success']}/{n['reorg_started']}  exc {n['exceptions']}"
                  f"  alt {n['alt_added']}  decisions {n['decisions']} (obj {n['objective']},"
                  f" tie {n['ties']}, switch {n['switches']})  share-weighted {n['share_weighted']}")
        print(f"forks_seen={rep['forks_seen']} share_weighted={rep['share_weighted']}"
              f" -> {'OK' if rep['ok'] else 'FAIL'}")
        for p in rep["problems"]:
            print(f"  ! {p}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
