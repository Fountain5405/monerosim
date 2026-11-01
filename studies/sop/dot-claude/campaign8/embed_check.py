#!/usr/bin/env python3
"""Own and remote (gossiped) workshares embedded per node in one archived run.

Scans every log under archived_runs/<run>/ for the patch's
"SIM-SoP: embedding ... own, ... remote" template lines
(patches/monero-sim-pop.patch:360-361) and prints, per file, the number of
template builds and the summed own and remote share counts. A share pending
on the tip is counted once per template that embeds it, so the sums are
template-share counts, not unique shares.

Used for campaign 8 §6.2: the attacker's offline miner embeds no remote
shares. Run from the repo root:
    venv/bin/python .claude/campaign8/embed_check.py <run name>
"""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAT = re.compile(rb"SIM-SoP: embedding.*?(\d+) own, (\d+) remote")


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    run = REPO / "archived_runs" / argv[1]
    if not run.is_dir():
        print(f"no run dir archived_runs/{argv[1]}")
        return 1
    print(f"run: archived_runs/{argv[1]}")
    rows = []
    for dirpath, _dirs, files in os.walk(run):
        for f in files:
            p = os.path.join(dirpath, f)
            n = own = rem = mx = 0
            try:
                with open(p, "rb") as fh:
                    for line in fh:
                        if b"SIM-SoP: embedding" not in line:
                            continue
                        m = PAT.search(line)
                        if not m:
                            continue
                        n += 1
                        o, r = int(m.group(1)), int(m.group(2))
                        own += o
                        rem += r
                        mx = max(mx, r)
            except OSError:
                continue
            if n:
                rows.append((os.path.relpath(p, run), n, own, rem, mx))
    rows.sort()
    print(f"{'file':60} {'templates':>9} {'own':>8} {'remote':>8} {'max remote':>10}")
    for rel, n, own, rem, mx in rows:
        print(f"{rel[:60]:60} {n:9d} {own:8d} {rem:8d} {mx:10d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
