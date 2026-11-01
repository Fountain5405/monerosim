#!/usr/bin/env python3
"""Per found block: shares the MINER embedded (its last "SIM-SoP: embedding N
workshares ... at height H" before "Found block <id> at height H"; no
embedding line at H means 0) vs shares honest-001 COUNTED when it judged the
block (n_sh in any SIM-SoP-DEC record listing that id; 0 when the set does
not conform, conformance doc convention 8). Also, per miner, every share it
found at a height vs what its block at that height embedded.

Usage: embed_vs_judged.py RUN_DIR [RUN_DIR ...]
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

EMBED = re.compile(r'SIM-SoP: embedding (\d+) workshares \((\d+) own, (\d+) remote\) at height (\d+)')
FOUND = re.compile(r'Found block <([0-9a-f]{64})> at height (\d+)')
SHARE = re.compile(r'SIM-SoP: share <[0-9a-f]+> nonce \d+ height (\d+)')


def miner_blocks(log: Path):
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
    out = subprocess.run(['grep', '-a', 'SIM-SoP-DEC ', str(log)], capture_output=True, text=True).stdout
    nsh = {}
    for line in out.splitlines():
        rec = json.loads(line.split('SIM-SoP-DEC ', 1)[1])
        for b in rec.get('alt', []) + rec.get('main', []):
            nsh[b['id']] = b.get('n_sh', 0)
    return nsh


def main():
    for run in map(Path, sys.argv[1:]):
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


if __name__ == '__main__':
    main()
