#!/usr/bin/env python3
"""Stuck time of the window_stubborn attacker in archived runs (2026-10-23).

A "gap" is a stretch longer than --gap hours between consecutive attacker
events (a concession, a reveal, a rejected reveal) in the attacker agent's
log, shadow.data/hosts/attacker-miner/bash.*.stdout. Under the block-depth
give-up the attacker spends such stretches mining a private branch it can
neither reveal (past the window, behind by weight) nor abandon (honest never
leads by give_up_depth blocks); every block mined there is orphaned. See
docs/20261023_sop_scale_n300_smoke.md.

usage: sop_stuck_time.py [--gap H] RUN_DIR [RUN_DIR ...]
"""
import argparse
import datetime as dt
import glob

EVENTS = ("strategy conceded", "window_stubborn: reveal", "reveal rejected",
          "committed block", "deep_hunt: reveal")


def stuck(run_dir: str, gap_h: float):
    ts, stop = [], None
    for f in glob.glob(f"{run_dir}/shadow.data/hosts/attacker-miner/bash.*.stdout"):
        for line in open(f, errors="replace"):
            if "attacker-miner - " in line:          # the duplicated, agent-prefixed copy
                continue
            if any(e in line for e in EVENTS):
                ts.append(dt.datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S"))
            elif "Final summary" in line:
                stop = dt.datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
    ts.sort()
    if stop:
        ts.append(stop)
    t0 = dt.datetime(2000, 1, 1)
    prev, total, gaps = t0, 0.0, []
    for t in ts:
        g = (t - prev).total_seconds() / 3600
        if g > gap_h:
            total += g
            gaps.append((prev, g))
        prev = t
    run_h = (stop - t0).total_seconds() / 3600 if stop else float("nan")
    return total, run_h, gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--gap", type=float, default=2.0, help="gap threshold in sim hours (default 2)")
    args = ap.parse_args()
    for r in args.runs:
        total, run_h, gaps = stuck(r.rstrip("/"), args.gap)
        name = r.rstrip("/").split("/")[-1]
        detail = ", ".join(f"{s.strftime('%d %H:%M')}+{g:.1f}h" for s, g in gaps)
        print(f"{name[:72]:72s} stuck {total:5.1f} h of {run_h:5.1f} ({len(gaps)} gaps > {args.gap:g} h) {detail}")


if __name__ == "__main__":
    main()
