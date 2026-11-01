#!/usr/bin/env python3
"""Share budget per miner: shares found vs shares embedded in the blocks it
found, from the miners' own monerod logs. Model B assumes an honest block
embeds every honest share mined since the previous honest block (mean w-1 =
15), and an attacker block every attacker share since its previous block.

Log lines used (monerod-sim, SIM-SoP patch):
  "SIM-SoP: share <id> nonce N height H slot S"      a share this miner found
  "SIM-SoP: pooled (local|remote) share <id> at height H"
  "SIM-SoP: embedding N workshares (O own, R remote) at height H"   template
  "Found block <id> at height H"                       a block this miner found
The embedding line in force at a find is the last one before it.

Usage: share_budget.py RUN_DIR [RUN_DIR ...]
"""
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


def main():
    for run in map(Path, sys.argv[1:]):
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


if __name__ == '__main__':
    main()
