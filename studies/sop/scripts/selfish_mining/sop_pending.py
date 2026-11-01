#!/usr/bin/env python3
"""Honest workshares pending at each reveal. At every objective SWITCH that
puts attacker blocks on honest-001's chain, count the workshares the node had
received since the last block of the branch being displaced (the node logs
"SIM-SoP: workshare received" only for shares gossiped by others; the
attacker never gossips, so these are honest). A share arrives once per peer
connection, so lines within DUP_GAP_MS of each other count once; this is an
estimate, as the line has no share id. They are in no block, so the
fork choice does not count them. `flips_if_counted` says whether counting
them would have stopped the reveal. Needs share-receive lines (the banfix
runs). Usage: sop_pending.py RUN_DIR [...]"""
import datetime
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

from scripts.selfish_mining.flipback_scan import attacker_ids

TS = re.compile(r'^(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{3})\t')
EPOCH_MS = 946684800000          # 2000-01-01 00:00:00 UTC, the sim clock
EPOCH = datetime.date(2000, 1, 1)


def _ms(line):
    m = TS.match(line)
    if not m:
        return None
    y, mo, d, hh, mm, ss, ms = map(int, m.groups())
    day = (datetime.date(y, mo, d) - EPOCH).days
    return EPOCH_MS + ((day * 24 + hh) * 60 + mm) * 60_000 + ss * 1000 + ms


DUP_GAP_MS = 2000   # lines closer than this are one share relayed by several peers


def _distinct(times):
    """The log line carries no share id, and a share arrives once per peer
    connection, within a second or two. Distinct shares are ~12 s apart
    (about 10 honest shares per 120 s block interval), so cluster by gap."""
    n, last = 0, None
    for s in sorted(times):
        if last is None or s - last > DUP_GAP_MS:
            n += 1
        last = s
    return n


def reveal_pending(log, att_ids=None):
    """One dict per objective SWITCH (onto attacker blocks when att_ids is
    given) in this honest node's log."""
    out = subprocess.run(['grep', '-aE', 'SIM-SoP-DEC|workshare received', str(log)],
                         capture_output=True, text=True).stdout
    shares, rows = [], []
    for line in out.splitlines():
        t = _ms(line)
        if t is None:
            continue
        if 'workshare received' in line:
            shares.append(t)
            continue
        rec = json.loads(line[line.index('SIM-SoP-DEC') + len('SIM-SoP-DEC'):])
        if rec.get('skipped') or rec['regime'] != 'objective' or rec['result'] != 'SWITCH':
            continue
        if att_ids is not None and not any(b['id'] in att_ids for b in rec['alt']):
            continue
        last_main = rec['main'][-1]['seen']
        pending = _distinct([s for s in shares if last_main < s <= t])
        unit = int(rec['main'][-1]['diff']) / rec['w']
        att_obj, hon_obj = round(int(rec['w_alt']) / unit), round(int(rec['w_main']) / unit)
        rows.append({'t_ms': t, 'pending': pending, 'att_obj': att_obj, 'hon_obj': hon_obj,
                     'gap': att_obj - hon_obj, 'flips_if_counted': att_obj <= hon_obj + pending,
                     'main_blocks': len(rec['main']), 'alt_blocks': len(rec['alt'])})
    return rows


def main(argv=None):
    allrows = []
    for run in map(Path, argv or sys.argv[1:]):
        rows = reveal_pending(run / 'daemon_logs' / 'monero-honest-001' / 'bitmonero.log', attacker_ids(run))
        allrows += rows
        n = len(rows)
        f = sum(r['flips_if_counted'] for r in rows)
        pend = [r['pending'] for r in rows]
        print(f'{run.name}: reveals={n} pending mean={statistics.mean(pend) if n else 0:.1f} '
              f'median={statistics.median(pend) if n else 0:.0f} would-be-blocked={f}')
    n = len(allrows)
    if n:
        pend = [r['pending'] for r in allrows]
        gaps = [r['gap'] for r in allrows]
        print(f'ALL: reveals={n} pending mean={statistics.mean(pend):.1f} median={statistics.median(pend):.0f} '
              f'max={max(pend)}; attacker lead at reveal (objects) mean={statistics.mean(gaps):.1f} '
              f'median={statistics.median(gaps):.0f}; blocked if pending counted: '
              f'{sum(r["flips_if_counted"] for r in allrows)} of {n}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
