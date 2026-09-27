#!/usr/bin/env python3
"""Attacker stranding in PoP/SoP cells (2026-09-27).

In every PoP/SoP matrix only the honest miners run the countermeasure; the
relays, seeds and the attacker's bridge keep stock fork choice. When the
attacker releases a long private branch, the stock nodes adopt it (most
work) while the flagged miners reject it as late. The attacker watches the
network through its bridge, so it believes it is winning and keeps mining on
a branch the miners never accept, until the honest chain outgrows it.

Per run this reports, from honest-001's fork decisions: the number of
distinct forks where an alternative chain of >= --min-len blocks was KEPT
out (rejected), the blocks in those rejected runs (max alt length per fork),
and the bridge's deepest reorganization. Blocks in rejected long runs are
attacker blocks lost to a stale view, not to a lost race.

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


def run_row(run_dir: Path, min_len: int) -> dict:
    hl = (run_dir / "daemon_logs/monero-honest-001/bitmonero.log").read_text(errors="replace")
    bl = (run_dir / "daemon_logs/monero-attacker-bridge/bitmonero.log").read_text(errors="replace")
    runs = rejected_long_runs(hl, min_len)
    return {"runs": len(runs), "blocks": sum(runs.values()), "bridge_max_reorg": deepest_reorg(bl)}


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
            if not (rd / "daemon_logs/monero-honest-001/bitmonero.log").is_file():
                continue
            s = run_row(rd, args.min_len)
            af = r.get("attacker_found") or 0
            rows.append({"matrix": name, "cell": r["cell"], "share": r.get("share"),
                         "attacker_orphan": r.get("attacker_orphan_rate"), "attacker_found": af,
                         **s, "stranded_frac": (s["blocks"] / af) if af else None})
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    print("| matrix | cell | share | attacker orphan | rejected runs >= %d | blocks in them | of attacker found | bridge max reorg |" % args.min_len)
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        f = "-" if r["stranded_frac"] is None else f"{r['stranded_frac']:.2f}"
        print(f"| {r['matrix']} | {r['cell']} | {r['share']:.3f} | {r['attacker_orphan']:.2f} | {r['runs']} | {r['blocks']} | {f} | {r['bridge_max_reorg']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
