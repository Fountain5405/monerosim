#!/usr/bin/env python3
"""Per node: reorgs onto the attacker's blocks, and whether each was undone
within WINDOW_S of sim time (the re-insertion flip-back), plus honest-only
reorg pairs that undo each other. Usage: flipback_scan.py RUN_DIR [...]"""
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

WINDOW_S = float(os.environ.get('FLIP_WINDOW_S', '1.0'))
TS = re.compile(r'^(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{3})\t\[([^\]]*)\]\t\S+\t\S+\t\S+\t(.*)$')
EPOCH = datetime.date(2000, 1, 1)
PREFILTER = ('REORGANIZE on height|alternative blockchain size|BLOCK SUCCESSFULLY ADDED|'
             'BLOCK ADDED AS ALTERNATIVE|\tid:\t<|\tHEIGHT [0-9]+, difficulty|'
             'SIM-SoP: fork|SIM-PoP|Failed to push ex-main')


def lines(path, unparsed=None):
    """Yield (sim seconds since 2000-01-01, thread, message). Lines the
    prefilter selects but TS rejects are counted in unparsed[0], never dropped
    silently (the first version read only day 1 of a 10-day run)."""
    out = subprocess.run(['grep', '-aE', PREFILTER, str(path)], capture_output=True, text=True)
    for raw in out.stdout.splitlines():
        m = TS.match(raw)
        if m:
            y, mo, d, hh, mm, ss, ms, thread, msg = m.groups()
            day = (datetime.date(int(y), int(mo), int(d)) - EPOCH).days
            if 0 <= day < 366:
                yield day * 86400 + int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000, thread, msg
                continue
        if unparsed is not None:
            unparsed[0] += 1


def attacker_ids(run):
    log = run / 'daemon_logs' / 'monero-attacker-miner' / 'bitmonero.log'
    out = subprocess.run(['grep', '-aoE', 'Found block <[0-9a-f]{64}>', str(log)],
                         capture_output=True, text=True).stdout
    return set(re.findall(r'[0-9a-f]{64}', out))


def scan_node(path, att, unparsed=None):
    reorgs, pending, expect, main_id, last_dec = [], {}, {}, {}, {}
    final_main, failed_push = {}, 0
    for t, th, msg in lines(path, unparsed):
        if 'Failed to push ex-main' in msg:
            failed_push += 1
        elif msg.startswith('SIM-SoP: fork') or msg.startswith('SIM-PoP'):
            last_dec[th] = (t, msg)
        elif 'REORGANIZE on height:' in msg:
            m = re.search(r'REORGANIZE on height: (\d+) of (\d+)', msg)
            r = {'t': t, 'split': int(m.group(1)), 'oldtop': int(m.group(2)), 'n': None,
                 'adds': [], 'dec': last_dec.get(th)}
            reorgs.append(r)
            pending[th] = r
        elif 'alternative blockchain size:' in msg and th in pending:
            pending[th]['n'] = int(re.search(r'size: (\d+)', msg).group(1))
        elif 'BLOCK SUCCESSFULLY ADDED' in msg:
            expect[th] = 'main'
        elif 'BLOCK ADDED AS ALTERNATIVE' in msg:
            expect[th] = 'alt'
        elif msg.startswith('id:\t<'):
            kind = expect.pop(th, None)
            if kind == 'main':
                main_id[th] = re.search(r'<([0-9a-f]{64})>', msg).group(1)
        elif msg.startswith('HEIGHT ') and th in main_id:
            h = int(re.search(r'HEIGHT (\d+)', msg).group(1))
            bid = main_id.pop(th)
            final_main[h] = bid
            r = pending.get(th)
            if r is not None and r['n'] is not None and len(r['adds']) < r['n']:
                r['adds'].append((h, bid))
                if len(r['adds']) == r['n']:
                    pending.pop(th)
    return reorgs, final_main, failed_push


def main():
    for run in map(Path, sys.argv[1:]):
        att = attacker_ids(run)
        print(f'### {run.name}  (attacker blocks found: {len(att)})')
        for log in sorted((run / 'daemon_logs').glob('*/bitmonero.log')):
            node = log.parent.name.replace('monero-', '', 1)
            if node == 'attacker-miner':
                continue
            unparsed = [0]
            reorgs, final_main, failed = scan_node(log, att, unparsed)
            to_att = [r for r in reorgs if any(i in att for _, i in r['adds'])]
            rev = 0
            details = []
            for r in to_att:
                hs = {h for h, _ in r['adds']}
                undo = next((q for q in reorgs if 0 < q['t'] - r['t'] <= WINDOW_S
                             and any(h in hs and i not in att for h, i in q['adds'])), None)
                stuck = sum(1 for h, i in r['adds'] if i in att and final_main.get(h) == i)
                rev += undo is not None
                dec = r['dec'][1][:95] if r['dec'] else '-'
                udec = (undo['dec'][1][:70] if undo and undo['dec'] else '-') if undo else ''
                details.append(f'    {r["t"]:9.3f}s split {r["split"]} +{len(r["adds"])} '
                               f'[{dec}] ' + (f'UNDONE +{undo["t"] - r["t"]:.3f}s by [{udec}]'
                                              if undo else f'kept; attacker blocks main at end: {stuck}'))
            hh_pairs = sum(1 for a in reorgs for b in reorgs
                           if 0 < b['t'] - a['t'] <= WINDOW_S and a not in to_att and b not in to_att
                           and {h for h, _ in a['adds']} & {h for h, _ in b['adds']})
            if reorgs or failed or unparsed[0]:
                print(f'  {node:22s} reorgs={len(reorgs):3d} onto-attacker={len(to_att):2d} '
                      f'undone<{WINDOW_S:g}s={rev:2d} honest-flip-pairs={hh_pairs:2d} failed-push={failed}'
                      + (f' unparsed-lines={unparsed[0]}' if unparsed[0] else ''))
                for d in details:
                    print(d)


if __name__ == '__main__':
    main()
