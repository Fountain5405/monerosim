#!/usr/bin/env python3
"""Tail-emission check (2026-10-20): every block a daemon added to its main
chain at or above the tail height must pay exactly the tail subsidy.

Reads each host's monerod stdout in a run (shadow.data/hosts/*/monerod*.stdout),
pairs "HEIGHT N" with the "block reward: X" line after it, and counts rewards
below and at or above the tail height. Exit 0 only if every block at or above
it paid 0.600000000000 and at least one such block exists.

  venv/bin/python .claude/campaign8/tail_check.py <run dir> [--tail-height 995]
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

TAIL = "0.600000000000"
H = re.compile(r"\bHEIGHT (\d+), difficulty")
RW = re.compile(r"\bblock reward: ([0-9.]+)\(")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--tail-height", type=int, default=995)
    a = ap.parse_args()
    files = sorted(Path(a.run).glob("shadow.data/hosts/*/monerod*.stdout"))
    if not files:
        print(f"no monerod stdout under {a.run}")
        return 2
    below, above = Counter(), Counter()
    for f in files:
        height = None
        with open(f, errors="replace") as fh:
            for line in fh:
                m = H.search(line)
                if m:
                    height = int(m.group(1))
                    continue
                m = RW.search(line)
                if m and height is not None:
                    (above if height >= a.tail_height else below)[m.group(1)] += 1
                    height = None
    print(f"{len(files)} daemons; rewards below height {a.tail_height}: {dict(below.most_common(3))}")
    print(f"rewards at or above {a.tail_height}: {sum(above.values())} block adds, "
          f"{len(above)} distinct values, most common {dict(above.most_common(3))}")
    ok = bool(above) and set(above) == {TAIL}
    print("TAIL CHECK:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
