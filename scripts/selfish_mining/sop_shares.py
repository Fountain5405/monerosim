#!/usr/bin/env python3
"""Share budget per miner, and embedded-vs-judged share counts, from the
miners' own monerod logs (SIM-SoP patch). Model B assumes an honest block
embeds every honest share mined since the previous honest block (mean w-1 =
15), and an attacker block every attacker share since its previous block.

Log lines used (monerod-sim, SIM-SoP patch):
  "SIM-SoP: share <id> nonce N height H slot S"      a share this miner found
  "SIM-SoP: pooled (local|remote) share <id> at height H"
  "SIM-SoP: embedding N workshares (O own, R remote) at height H"   template
  "Found block <id> at height H"                       a block this miner found
The embedding line in force at a find is the last one before it.

judged() reads the n_sh honest-001 actually COUNTED when it judged a block
(any SIM-SoP-DEC record listing that id; 0 when the set does not conform,
conformance doc convention 8).

Usage:
  sop_shares.py budget RUN_DIR [RUN_DIR ...]
  sop_shares.py judged RUN_DIR [RUN_DIR ...]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

PAT = 'SIM-SoP: share <|SIM-SoP: pooled (local|remote) share|SIM-SoP: embedding|Found block <'
SHARE = re.compile(r'SIM-SoP: share <[0-9a-f]+> nonce \d+ height (\d+)')
POOLED = re.compile(r'SIM-SoP: pooled (local|remote) share <[0-9a-f]+> at height (\d+)')
EMBED = re.compile(r'SIM-SoP: embedding (\d+) workshares \((\d+) own, (\d+) remote\) at height (\d+)')
FOUND = re.compile(r'Found block <([0-9a-f]{64})> at height (\d+)')


def miner(log: Path):
    """shares found per height, shares pooled per height, and finds (list of
    dicts: h, n/own/remote embedded at that height, embed_h = the height the
    embedding line in force was for, pooled_at_h)."""
    out = subprocess.run(['grep', '-aE', PAT, str(log)], capture_output=True, text=True).stdout
    shares, pooled, finds, last = Counter(), Counter(), [], None
    for line in out.splitlines():
        if m := SHARE.search(line):
            shares[int(m.group(1))] += 1
        elif m := POOLED.search(line):
            pooled[int(m.group(2))] += 1
        elif m := EMBED.search(line):
            last = tuple(map(int, m.groups()))
        elif m := FOUND.search(line):
            h = int(m.group(2))
            n, own, rem, eh = last if last else (None, None, None, None)
            finds.append({'h': h, 'n': n, 'own': own, 'remote': rem, 'embed_h': eh,
                          'pooled_at_h': pooled[h]})
    return shares, pooled, finds


def miner_blocks(log: Path):
    """Per found block: (height, shares embedded by the MINER). Per-height
    share counter the miner found."""
    out = subprocess.run(['grep', '-aE', 'SIM-SoP: embedding|Found block <|SIM-SoP: share <', str(log)],
                         capture_output=True, text=True).stdout
    embed_at, blocks, shares = {}, {}, Counter()
    for line in out.splitlines():
        if m := EMBED.search(line):
            embed_at[int(m.group(4))] = int(m.group(1))
        elif m := FOUND.search(line):
            h = int(m.group(2))
            blocks[m.group(1)] = (h, embed_at.get(h, 0))
        elif m := SHARE.search(line):
            shares[int(m.group(1))] += 1
    return blocks, shares


def judged(log: Path) -> dict:
    """block id -> n_sh honest-001 counted when it judged it (0 default)."""
    out = subprocess.run(['grep', '-a', 'SIM-SoP-DEC ', str(log)], capture_output=True, text=True).stdout
    nsh = {}
    for line in out.splitlines():
        rec = json.loads(line.split('SIM-SoP-DEC ', 1)[1])
        for b in rec.get('alt', []) + rec.get('main', []):
            nsh[b['id']] = b.get('n_sh', 0)
    return nsh


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_budget(runs: list) -> int:
    for run in map(Path, runs):
        print(f'== {run.name}')
        tot = {}
        for who in ('honest-001', 'honest-002', 'attacker-miner'):
            shares, pooled, finds = miner(run / 'daemon_logs' / f'monero-{who}' / 'bitmonero.log')
            ns = [f['n'] for f in finds if f['n'] is not None]
            stale = sum(1 for f in finds if f['embed_h'] is not None and f['embed_h'] != f['h'])
            gap = [f['pooled_at_h'] - f['n'] for f in finds if f['n'] is not None and f['embed_h'] == f['h']]
            tot[who] = (sum(shares.values()), len(finds))
            print(f'  {who:<15} shares_found={sum(shares.values()):6d} blocks_found={len(finds):5d} '
                  f'shares/block={sum(shares.values()) / max(1, len(finds)):5.2f} '
                  f'embedded mean={statistics.mean(ns) if ns else 0:5.2f} median={statistics.median(ns) if ns else 0:4.1f} '
                  f'own={statistics.mean([f["own"] for f in finds if f["own"] is not None]) if ns else 0:5.2f} '
                  f'remote={statistics.mean([f["remote"] for f in finds if f["remote"] is not None]) if ns else 0:5.2f} '
                  f'embed_h!=h={stale} pooled-minus-embedded mean={statistics.mean(gap) if gap else 0:5.2f}')
        hs = tot['honest-001'][0] + tot['honest-002'][0]
        hb = tot['honest-001'][1] + tot['honest-002'][1]
        print(f'  honest network: shares/block found = {hs / max(1, hb):.2f} (Model B: 15)')
    return 0


def _cmd_judged(runs: list) -> int:
    for run in map(Path, runs):
        logs = run / 'daemon_logs'
        dec = judged(logs / 'monero-honest-001' / 'bitmonero.log')
        print(f'== {run.name}  (blocks judged by honest-001: {len(dec)})')
        for who in ('attacker-miner', 'honest-001', 'honest-002'):
            blocks, shares = miner_blocks(logs / f'monero-{who}' / 'bitmonero.log')
            pairs = [(n, dec[i]) for i, (h, n) in blocks.items() if i in dec]
            same = sum(1 for n, j in pairs if n == j)
            zeroed = sum(1 for n, j in pairs if n > 0 and j == 0)
            other = len(pairs) - same - zeroed
            emb = sum(n for _h, n in blocks.values())
            print(f'  {who:<15} blocks={len(blocks)} judged={len(pairs)} miner==judged {same} '
                  f'miner>0 but judged 0: {zeroed} other mismatch: {other} | '
                  f'shares found {sum(shares.values())} embedded {emb} '
                  f'({100 * emb / max(1, sum(shares.values())):.1f} %)')
            if zeroed or other:
                ex = [(blocks[i][0], blocks[i][1], dec[i]) for i in blocks if i in dec and blocks[i][1] != dec[i]][:8]
                print(f'    examples (height, miner N, judged n_sh): {ex}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('budget')
    p.add_argument('run_dirs', nargs='+')
    p = sub.add_parser('judged')
    p.add_argument('run_dirs', nargs='+')
    a = ap.parse_args(argv)
    if a.cmd == 'budget':
        return _cmd_budget(a.run_dirs)
    if a.cmd == 'judged':
        return _cmd_judged(a.run_dirs)
    return 2


if __name__ == '__main__':
    sys.exit(main())
