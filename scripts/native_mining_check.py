#!/usr/bin/env python3
"""Native-mining gate checker (docs/NATIVE_MINING.md).

Reads every miner's daemon stdout under <run_dir>/shadow.data/hosts/<miner>/
and asserts: cadence, difficulty, block share, zero PoW rejections on relays.
Exit 0 = PASS, 1 = FAIL. Prints a table either way.
"""
import argparse
import glob
import re
import statistics
import sys
from datetime import datetime

FOUND = re.compile(r"^(\S+ \S+)\t.*Found block (\S+) at height (\d+) for difficulty: (\d+)")
REJECT = re.compile(r"does not have enough proof of work|verification failed")


def parse_found(path):
    out = []
    with open(path, errors="replace") as f:
        for line in f:
            m = FOUND.match(line)
            if m:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
                out.append((int(m.group(3)), ts, int(m.group(4))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--miners", required=True, help="id:hashrate,id:hashrate,...")
    ap.add_argument("--cadence-tol", type=float, default=0.15)
    ap.add_argument("--difficulty-tol", type=float, default=0.25)
    ap.add_argument("--share-tol", type=float, default=5.0)
    ap.add_argument("--last", type=int, default=30, help="blocks in the steady-state window")
    a = ap.parse_args()

    miners = dict(kv.split(":") for kv in a.miners.split(","))
    miners = {k: int(v) for k, v in miners.items()}
    total_hs = sum(miners.values())
    per_miner, all_blocks = {}, []
    for mid in miners:
        files = glob.glob(f"{a.run_dir}/shadow.data/hosts/{mid}/monerod*.stdout")
        blocks = [b for f in files for b in parse_found(f)]
        per_miner[mid] = blocks
        all_blocks += blocks
    all_blocks.sort()
    ok = True
    rows = []

    def check(name, value, target, tol, fmt="{:.1f}"):
        nonlocal ok
        good = abs(value - target) <= tol
        ok &= good
        rows.append((name, fmt.format(value), fmt.format(target), "PASS" if good else "FAIL"))

    n = len(all_blocks)
    rows.append(("blocks found (all miners)", str(n), ">= %d" % (a.last + 5), "PASS" if n >= a.last + 5 else "FAIL"))
    ok &= n >= a.last + 5
    if n >= a.last + 5:
        tail = all_blocks[-a.last:]
        intervals = [(t2 - t1).total_seconds() for (_, t1, _), (_, t2, _) in zip(tail, tail[1:])]
        check("mean interval, last %d (s)" % a.last, statistics.mean(intervals), 120.0, 120.0 * a.cadence_tol)
        d_eq = 120 * total_hs
        check("difficulty, last block", tail[-1][2], d_eq, d_eq * a.difficulty_tol, "{:.0f}")
        for mid, hs in miners.items():
            share = 100.0 * len(per_miner[mid]) / n
            check(f"share {mid} (%)", share, 100.0 * hs / total_hs, a.share_tol)
    rejects = 0
    for f in glob.glob(f"{a.run_dir}/shadow.data/hosts/relay-*/monerod*.stdout"):
        with open(f, errors="replace") as fh:
            rejects += sum(1 for line in fh if REJECT.search(line))
    rows.append(("PoW rejections on relays", str(rejects), "0", "PASS" if rejects == 0 else "FAIL"))
    ok &= rejects == 0

    w = max(len(r[0]) for r in rows)
    for r in rows:
        print(f"{r[0]:<{w}}  {r[1]:>10}  {r[2]:>10}  {r[3]}")
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
