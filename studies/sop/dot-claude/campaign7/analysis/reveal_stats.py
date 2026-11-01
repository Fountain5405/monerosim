#!/usr/bin/env python3
"""Attacker reveals as Model B counts them (scripts/sop_race_model.py), from a
run's logs. On the reference node (honest-001), every successful reorg is
matched to the main-chain blocks it removed and the blocks it applied. A
reveal is a reorg whose applied blocks include attacker-found blocks; its
depth is the honest blocks it orphaned (Model B's reorg_depths). Blocks
found = unique "Found block <id>" over the three miners.

monerod logs each main-chain add as "+++++ BLOCK SUCCESSFULLY ADDED", then
"id: <hash>", "PoW", "HEIGHT N, difficulty" (reorgs re-add the new branch the
same way, on the switching thread), and brackets a reorg with "REORGANIZE on
height: A of B" (A = first alt height, B = old top) and "REORGANIZE SUCCESS!
on height: A, new blockchain size: N".

Usage: reveal_stats.py OUT_JSON RUN_DIR [RUN_DIR ...]
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

LINE = re.compile(r'^(2000-01-\d\d \d\d:\d\d:\d\d\.\d{3})\t\[([^\]]*)\]\t[A-Z]+\t\S+\t\S+\t(.*)$')
# Real tabs (not a raw string): grep -E reads "\t" as a literal "t".
PREFILTER = 'BLOCK SUCCESSFULLY ADDED|\tid:\t<|\tHEIGHT [0-9]+, difficulty|REORGANIZE (on height|SUCCESS)'
REPO = Path('/scratch/monerosim_dev/monerosim')


def found_ids(log: Path) -> set:
    out = subprocess.run(['grep', '-aoE', 'Found block <[0-9a-f]{64}>', str(log)],
                         capture_output=True, text=True).stdout
    return set(re.findall(r'[0-9a-f]{64}', out))


def reorg_events(log: Path) -> list:
    out = subprocess.run(['grep', '-aE', PREFILTER, str(log)], capture_output=True, text=True).stdout
    main, want, open_reorg, events = {}, {}, {}, []
    for raw in out.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        t, th, msg = m.groups()
        if msg.startswith('+++++ BLOCK SUCCESSFULLY ADDED'):
            want[th] = None
        elif msg.startswith('id:') and th in want and want[th] is None:
            want[th] = msg.split('<', 1)[1].split('>', 1)[0]
        elif msg.startswith('HEIGHT ') and want.get(th):
            h = int(msg.split()[1].rstrip(','))
            bid = want.pop(th)
            main[h] = bid
            if th in open_reorg:
                open_reorg[th]['new'].append(bid)
        elif 'REORGANIZE on height:' in msg:
            a, b = map(int, re.search(r'on height: (\d+) of (\d+)', msg).groups())
            open_reorg[th] = {'t': t, 'split': a, 'old_top': b,
                              'old': [main.get(h) for h in range(a, b + 1)], 'new': []}
        elif msg.startswith('REORGANIZE SUCCESS!'):
            a, size = map(int, re.search(r'on height: (\d+), new blockchain size: (\d+)', msg).groups())
            r = open_reorg.pop(th, None)
            if r and r['split'] == a:
                r['new_top'] = size - 1
                events.append(r)
            for h in [h for h in main if h >= size]:
                del main[h]
    return events


def run_stats(run: Path) -> dict:
    logs = run / 'daemon_logs'
    att = found_ids(logs / 'monero-attacker-miner' / 'bitmonero.log')
    hon = found_ids(logs / 'monero-honest-001' / 'bitmonero.log') | found_ids(logs / 'monero-honest-002' / 'bitmonero.log')
    reveals, other, unknown_old = [], [], 0
    for r in reorg_events(logs / 'monero-honest-001' / 'bitmonero.log'):
        unknown_old += sum(1 for x in r['old'] if x is None)
        hon_orph = sum(1 for x in r['old'] if x is not None and x not in att)
        rec = {'t': r['t'], 'split': r['split'], 'removed': len(r['old']), 'honest_orphaned': hon_orph,
               'att_applied': sum(1 for x in r['new'] if x in att), 'applied': len(r['new'])}
        (reveals if rec['att_applied'] else other).append(rec)
    return {'found_att': len(att), 'found_hon': len(hon), 'found': len(att) + len(hon),
            'reveals': reveals, 'other_reorgs': other, 'unknown_old_ids': unknown_old,
            'depth_hist': dict(sorted(Counter(r['honest_orphaned'] for r in reveals).items()))}


def main():
    out_json, runs = sys.argv[1], [Path(p) for p in sys.argv[2:]]
    cells = {}
    for f in REPO.glob('matrix_runs/*/cells/*.json'):
        d = json.loads(f.read_text())
        cells[Path(d['run_dir']).name] = d
    result = {}
    for run in runs:
        s = run_stats(run)
        c = cells.get(run.name, {})
        s.update({k: c.get(k) for k in ('share', 'canonical_blocks', 'attacker_orphan_rate',
                                        'network_orphan_rate', 'attacker_found')})
        result[run.name] = s
        n = len(s['reveals'])
        print(f"{run.name}: found={s['found']} (att {s['found_att']}, cell says {s['attacker_found']}) "
              f"reveals={n} other={len(s['other_reorgs'])} unknown_old={s['unknown_old_ids']} "
              f"per1000={1000 * n / max(1, s['found']):.2f} depths={s['depth_hist']}")
    Path(out_json).write_text(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
