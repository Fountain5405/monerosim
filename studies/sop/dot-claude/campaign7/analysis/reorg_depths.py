#!/usr/bin/env python3
"""Reorg depth per node from monerod logs: for every successful reorg, the
number of main-chain blocks it disconnected (old top - split height + 1).

monerod prints "###### REORGANIZE on height: A of B with cum_difficulty C"
(A = first alt height, B = old top) at the start of a switch and
"REORGANIZE SUCCESS! on height: A, new blockchain size: N" when it lands.
A started reorg only counts once its SUCCESS line follows on the same thread.

Usage: reorg_depths.py OUT_JSON RUN_DIR [RUN_DIR ...]
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

START = re.compile(r'^(2000-01-\d\d \d\d:\d\d:\d\d\.\d{3})\t\[([^\]]*)\].*REORGANIZE on height: (\d+) of (\d+)')
DONE = re.compile(r'^(2000-01-\d\d \d\d:\d\d:\d\d\.\d{3})\t\[([^\]]*)\].*REORGANIZE SUCCESS! on height: (\d+), new blockchain size: (\d+)')


def node_reorgs(log: Path):
    out = subprocess.run(['grep', '-aE', 'REORGANIZE (on height|SUCCESS)', str(log)],
                         capture_output=True, text=True).stdout
    pending, done = {}, []
    for line in out.splitlines():
        m = START.match(line)
        if m:
            t, th, a, b = m.groups()
            pending[th] = (t, int(a), int(b))
            continue
        m = DONE.match(line)
        if m:
            t, th, a, size = m.groups()
            st = pending.pop(th, None)
            if st and st[1] == int(a):
                done.append({'t': t, 'split': int(a), 'old_top': st[2],
                             'new_top': int(size) - 1, 'depth': st[2] - int(a) + 1})
    return done


def bucket(d):
    if d <= 5:
        return str(d)
    return '6-9' if d < 10 else '10+'


def main():
    out_json, runs = sys.argv[1], sys.argv[2:]
    result = {}
    for run in map(Path, runs):
        nodes = {}
        for log in sorted(run.glob('daemon_logs/monero-*/bitmonero.log')):
            name = log.parent.name.removeprefix('monero-')
            nodes[name] = node_reorgs(log)
        result[run.name] = nodes
        deep = sorted({(r['split'], r['depth']) for rs in nodes.values() for r in rs if r['depth'] >= 10})
        print(f'== {run.name}')
        for name, rs in nodes.items():
            c = Counter(bucket(r['depth']) for r in rs)
            mx = max((r['depth'] for r in rs), default=0)
            print(f'  {name:<16} n={len(rs):4d} max={mx:3d} ' +
                  ' '.join(f'{k}:{c.get(k, 0)}' for k in ['1', '2', '3', '4', '5', '6-9', '10+']))
        print(f'  distinct 10+ (split, depth): {deep}')
    Path(out_json).write_text(json.dumps(result))


if __name__ == '__main__':
    main()
