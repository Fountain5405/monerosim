#!/usr/bin/env python3
"""Attacker stranding in PoP/SoP cells (2026-09-27; attacker-side 2026-09-28).

The selfish strategy assumes every reveal wins: it moves its fork to its own
tip and from then on compares chain heights only. When the countermeasure
rejects a reveal as late, the attacker keeps racing on a branch the network
never accepts, until the honest chain is taller, and then abandons it.
Blocks in those long abandoned branches are lost to the attacker's blind
spot, not to a lost race.

Per run this reports:
- from the attacker's own daemon (the primary measure): every
  `REORGANIZE on height: h of top` disconnects top - h + 1 blocks of the
  attacker's branch; abandonments of >= --min-len blocks, the blocks in
  them, their share of the attacker's found blocks, and the deepest one;
- the longest alternative chain the bridge KEPT out (subjective decisions
  only: OBJECTIVE KEEPs after a switch re-weigh the displaced branch);
- the honest-side view used in the 2026-09-27 table: forks where honest-001
  kept out an alternative chain of >= --min-len blocks. A stock bridge adopts
  the rejected branch and so shows it to honest nodes; a bridge that runs the
  countermeasure rejects it and never announces it, so this view reads ~0
  there while the attacker still strands
  (docs/20260926_exact_uncles_and_sop_controls.md §6);
- the bridge's deepest reorganization.

Usage:
  venv/bin/python scripts/attacker_stranding.py <matrix-name> [...] [--min-len 10]
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RE_F = re.compile(r"SIM-(?:PoP|SoP): fork (\d+) alt (\d+)/(\d+) vs main (\d+)/(\d+) -> (KEEP|SWITCH)")
RE_R = re.compile(r"REORGANIZE SUCCESS! on height: (\d+), new blockchain size: (\d+)")
RE_A = re.compile(r"REORGANIZE on height: (\d+) of (\d+)")


def rejected_long_runs(honest_log: str, min_len: int = 10) -> dict:
    """{fork height: longest alt chain length KEPT out at that fork}."""
    out = {}
    for m in RE_F.finditer(honest_log):
        fork, alt_len = int(m.group(1)), int(m.group(3))
        if alt_len >= min_len and m.group(6) == "KEEP":
            out[fork] = max(out.get(fork, 0), alt_len)
    return out


def deepest_reorg(log: str) -> int:
    return max([int(size) - int(h) for h, size in RE_R.findall(log)] or [0])


def abandoned_depths(log: str) -> list:
    """Blocks disconnected by each reorganization, in log order."""
    return [int(top) - int(h) + 1 for h, top in RE_A.findall(log)]


def run_row(run_dir: Path, min_len: int) -> dict:
    logs = run_dir / "daemon_logs"
    hl = (logs / "monero-honest-001/bitmonero.log").read_text(errors="replace")
    bl = (logs / "monero-attacker-bridge/bitmonero.log").read_text(errors="replace")
    al = (logs / "monero-attacker-miner/bitmonero.log").read_text(errors="replace")
    runs = rejected_long_runs(hl, min_len)
    depths = abandoned_depths(al)
    long_ = [d for d in depths if d >= min_len]
    return {"abandoned_runs": len(long_), "abandoned_blocks": sum(long_),
            "attacker_max_abandon": max(depths or [0]),
            "bridge_kept_out": max(rejected_long_runs(bl, 1).values() or [0]),
            "runs": len(runs), "blocks": sum(runs.values()), "bridge_max_reorg": deepest_reorg(bl)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("matrices", nargs="+")
    ap.add_argument("--min-len", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = []
    for name in args.matrices:
        for cj in sorted((REPO_ROOT / "matrix_runs" / name / "cells").glob("*.json")):
            r = json.loads(cj.read_text())
            rd = Path(r.get("run_dir") or "")
            if not rd.is_dir():
                rd = next((REPO_ROOT / "archived_runs").glob(f"*_{r['run_name']}"), rd)
            if not all((rd / "daemon_logs" / f"monero-{n}" / "bitmonero.log").is_file()
                       for n in ("honest-001", "attacker-bridge", "attacker-miner")):
                continue
            s = run_row(rd, args.min_len)
            af = r.get("attacker_found") or 0
            rows.append({"matrix": name, "cell": r["cell"], "share": r.get("share"),
                         "attacker_orphan": r.get("attacker_orphan_rate"), "attacker_found": af,
                         **s, "abandoned_frac": (s["abandoned_blocks"] / af) if af else None})
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    n = args.min_len
    print(f"| matrix | cell | share | attacker orphan | abandoned runs >= {n} | blocks in them | of attacker found "
          f"| deepest abandon | bridge kept out | honest-001 rejected runs >= {n} (blocks) | bridge max reorg |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        f = "-" if r["abandoned_frac"] is None else f"{r['abandoned_frac']:.2f}"
        print(f"| {r['matrix']} | {r['cell']} | {r['share']:.3f} | {r['attacker_orphan']:.2f} | {r['abandoned_runs']} "
              f"| {r['abandoned_blocks']} | {f} | {r['attacker_max_abandon']} | {r['bridge_kept_out']} "
              f"| {r['runs']} ({r['blocks']}) | {r['bridge_max_reorg']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
