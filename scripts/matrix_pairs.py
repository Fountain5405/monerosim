#!/usr/bin/env python3
"""Pair the draws of a replicated matrix (n=2: `<name>` + `<name>_rep`, or
any list of matrix result files) into one table per cell.

Reads matrix_runs/<name>/results.json (or the per-cell markers under
matrix_runs/<name>/cells/ when results.json is not written yet) and prints,
per cell: alpha, the attacker share of every draw (bridge reference and the
honest-node reference), their mean, the SoP share-weighted decision count,
forks seen, attacker blocks found, and the health tokens. A cell is only
`ok` when EVERY draw's health is ok (reorgs balanced, no exceptions, forks
seen, attacker mined, share term alive on SoP nodes) — a control cell that
never forked proves nothing about fork choice.

Usage:
  venv/bin/python scripts/matrix_pairs.py pop_sop2_h10 pop_sop2_h10_rep [--json out.json]
"""
import argparse
import json
import os
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKROOT = REPO_ROOT / "matrix_runs"


def load_rows(name: str, workroot: Path) -> list:
    d = workroot / name
    results = d / "results.json"
    if results.is_file():
        return json.loads(results.read_text())
    rows = []
    for m in sorted((d / "cells").glob("*.json")):
        rows.append(json.loads(m.read_text()))
    return rows


def _f(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def pair(draws: dict) -> list:
    """draws: {matrix_name: [row, ...]} -> [{cell, values, per_draw, mean_share,
    mean_share_h, ok}] sorted by cell."""
    cells = {}
    for name, rows in draws.items():
        for r in rows:
            cells.setdefault(r["cell"], {"cell": r["cell"], "values": r.get("values") or {}, "draws": {}})
            cells[r["cell"]]["draws"][name] = r
    out = []
    for cell, c in sorted(cells.items()):
        shares = [r.get("share") for r in c["draws"].values() if r.get("share") is not None]
        shares_h = [r.get("share_honest_ref") for r in c["draws"].values() if r.get("share_honest_ref") is not None]
        healths = [(r.get("health") or {}) for r in c["draws"].values()]
        ok = bool(c["draws"]) and all(h.get("ok") for h in healths) and all("error" not in r for r in c["draws"].values())
        out.append({
            "cell": cell,
            "values": c["values"],
            "alpha": next((r.get("alpha") for r in c["draws"].values() if r.get("alpha") is not None), None),
            "per_draw": {name: {
                "share": r.get("share"), "share_h": r.get("share_honest_ref"),
                "blocks": r.get("canonical_blocks"), "preload": r.get("preload_blocks"),
                "attacker_found": r.get("attacker_found"),
                "forks": (r.get("health") or {}).get("forks_seen"),
                "sw": (r.get("health") or {}).get("share_weighted"),
                "health": (r.get("health") or {}).get("summary", "-"),
                "error": (r.get("error") or "")[:120] or None,
                "run": Path(r.get("run_dir", "-")).name,
            } for name, r in c["draws"].items()},
            "n": len(shares),
            "mean_share": statistics.fmean(shares) if shares else None,
            "mean_share_h": statistics.fmean(shares_h) if shares_h else None,
            "spread_share": (max(shares) - min(shares)) if len(shares) > 1 else None,
            "ok": ok,
        })
    return out


def render(paired: list, names: list) -> str:
    head = ["cell", "alpha"] + [f"share@{n}" for n in names] + ["mean", "spread"] \
        + [f"share_h@{n}" for n in names] + ["mean_h", "sw", "forks", "att_found", "health", "ok"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for p in paired:
        pd = p["per_draw"]
        def col(n, k, nd=3):
            v = (pd.get(n) or {}).get(k)
            return "-" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))
        sw = "/".join(col(n, "sw") for n in names)
        forks = "/".join(col(n, "forks") for n in names)
        att = "/".join(col(n, "attacker_found") for n in names)
        health = "; ".join(f"{n}: {(pd.get(n) or {}).get('health', '-')}" for n in names
                           if (pd.get(n) or {}).get("health", "ok") != "ok") or "ok"
        lines.append("| " + " | ".join(
            [p["cell"], _f(p["alpha"])] + [col(n, "share") for n in names]
            + [_f(p["mean_share"]), _f(p["spread_share"])]
            + [col(n, "share_h") for n in names] + [_f(p["mean_share_h"]), sw, forks, att, health,
               "yes" if p["ok"] else "NO"]) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("matrices", nargs="+", help="matrix names under matrix_runs/ (draws of the same cells)")
    ap.add_argument("--json", default=None, help="also write the paired rows as JSON")
    ap.add_argument("--ledger", action="store_true",
                    help="also print reproducibility-ledger rows (one per run) for the manuscript")
    ap.add_argument("--commit", default=None, help="commit to stamp ledger rows with (default: git rev-parse --short HEAD)")
    args = ap.parse_args()
    workroot = Path(os.environ.get("MONEROSIM_MATRIX_WORKROOT", DEFAULT_WORKROOT))
    draws = {n: load_rows(n, workroot) for n in args.matrices}
    missing = [n for n, rows in draws.items() if not rows]
    if missing:
        print(f"WARNING: no rows yet for {missing}", file=sys.stderr)
    paired = pair(draws)
    print(render(paired, args.matrices))
    bad = [p["cell"] for p in paired if not p["ok"]]
    print(f"{len(paired)} cells; {len(paired) - len(bad)} ok" + (f"; NOT ok: {', '.join(bad)}" if bad else ""))
    if args.json:
        Path(args.json).write_text(json.dumps(paired, indent=1, default=str))
    if args.ledger:
        import subprocess
        commit = args.commit or subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                                               capture_output=True, text=True).stdout.strip()
        print()
        print("| Run directory | Commit | Config | What it shows |")
        print("|---|---|---|---|")
        for p in paired:
            for name, d in p["per_draw"].items():
                what = (f"{p['cell']}: share {_f(d['share'])} (honest-ref {_f(d['share_h'])}), "
                        f"blocks {d['blocks']}, forks {d['forks']}, sw {d['sw']}, health {d['health']}")
                if d.get("error"):
                    what = f"{p['cell']}: ERROR {d['error']}"
                print(f"| `{d['run']}` | `{commit}` | `{name}` cell | {what} |")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
