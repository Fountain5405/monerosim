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

Four analyses share this log-parsing core:
  stats  - reveal_stats.py: per-run reveal/other-reorg counts and depth hist.
  depths - reorg_depths.py: per-node reorg depth histogram, any thread/node.
  shapes - reveal_shapes.py: the SIM-SoP-DEC shape of every attacker reveal.
  leads  - race_leads.py: the largest honest lead (h - a) reached before each
           reveal, to check Model B's give-up-at-depth-d claim.

Usage:
  sop_reveals.py stats OUT_JSON RUN_DIR [RUN_DIR ...]
  sop_reveals.py depths OUT_JSON RUN_DIR [RUN_DIR ...]
  sop_reveals.py shapes OUT_JSON RUN_DIR [RUN_DIR ...]
  sop_reveals.py leads D RUN_DIR [RUN_DIR ...]
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

LINE = re.compile(r'^(2000-01-\d\d \d\d:\d\d:\d\d\.\d{3})\t\[([^\]]*)\]\t[A-Z]+\t\S+\t\S+\t(.*)$')
# Real tabs (not a raw string): grep -E reads "\t" as a literal "t".
PREFILTER = 'BLOCK SUCCESSFULLY ADDED|\tid:\t<|\tHEIGHT [0-9]+, difficulty|REORGANIZE (on height|SUCCESS)'
FOUND = re.compile(r'^(2000-01-\d\d \d\d:\d\d:\d\d)\.(\d{3}).*Found block <([0-9a-f]{64})>')
REPO = Path(__file__).resolve().parents[2]


def found_ids(log: Path) -> set:
    out = subprocess.run(['grep', '-aoE', 'Found block <[0-9a-f]{64}>', str(log)],
                         capture_output=True, text=True).stdout
    return set(re.findall(r'[0-9a-f]{64}', out))


def reorg_events(log: Path) -> list:
    """Every successful reorg on `log`'s node: split height, old top, the
    main-chain block ids it removed ('old', None where unknown), the block
    ids it applied ('new'), and the resulting new top."""
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


def run_stats(run: Path, cells: dict | None = None) -> dict:
    """Reveal/other-reorg stats for one run, keyed as reveal_stats.py's
    main() printed/stored them, plus `cells` (run-dir-name -> cell marker
    dict) merged in, same keys main() merged."""
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
    result = {'found_att': len(att), 'found_hon': len(hon), 'found': len(att) + len(hon),
              'reveals': reveals, 'other_reorgs': other, 'unknown_old_ids': unknown_old,
              'depth_hist': dict(sorted(Counter(r['honest_orphaned'] for r in reveals).items()))}
    c = (cells or {}).get(run.name, {})
    result.update({k: c.get(k) for k in ('share', 'canonical_blocks', 'attacker_orphan_rate',
                                         'network_orphan_rate', 'attacker_found')})
    return result


def load_cell_markers(repo: Path) -> dict:
    """run-dir-name -> cell marker dict, over every matrix_runs/*/cells/*.json."""
    cells = {}
    for f in Path(repo).glob('matrix_runs/*/cells/*.json'):
        d = json.loads(f.read_text())
        cells[Path(d['run_dir']).name] = d
    return cells


def node_depths(log: Path) -> list:
    """Reorg depth per event on `log`'s node: t, split, old_top, new_top,
    depth (= old_top - split + 1, the main-chain blocks disconnected)."""
    return [{'t': r['t'], 'split': r['split'], 'old_top': r['old_top'],
             'new_top': r['new_top'], 'depth': r['old_top'] - r['split'] + 1}
            for r in reorg_events(log)]


def bucket(d: int) -> str:
    if d <= 5:
        return str(d)
    return '6-9' if d < 10 else '10+'


def reveal_shapes(run: Path) -> list:
    """The SIM-SoP-DEC record of every attacker reveal on honest-001: a
    SWITCH onto attacker-found blocks (not reinsert/skipped)."""
    att = found_ids(run / 'daemon_logs' / 'monero-attacker-miner' / 'bitmonero.log')
    out = subprocess.run(['grep', '-a', 'SIM-SoP-DEC ',
                          str(run / 'daemon_logs' / 'monero-honest-001' / 'bitmonero.log')],
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        rec = json.loads(line.split('SIM-SoP-DEC ', 1)[1])
        if rec.get('result') != 'SWITCH' or rec.get('reinsert') or rec.get('skipped'):
            continue
        alt, main = rec['alt'], rec['main']
        if not any(b['id'] in att for b in alt):
            continue
        rows.append({'t': line[:23], 'regime': rec.get('regime'), 'nf': rec.get('nf'),
                     'w_alt': int(rec['w_alt']), 'w_main': int(rec['w_main']),
                     'alt_nsh': [b['n_sh'] for b in alt],
                     'alt_is_att': [b['id'] in att for b in alt],
                     'main_nsh': [b['n_sh'] for b in main],
                     'main_is_att': [b['id'] in att for b in main]})
    return rows


def _ms(ts: str, frac: str) -> int:
    return calendar.timegm(time.strptime(ts, '%Y-%m-%d %H:%M:%S')) * 1000 + int(frac)


def race_leads(run: Path, d: int):
    """Largest honest lead (h - a) reached before each attacker reveal on
    honest-001, rebuilding the race from honest 'seen' times (SIM-SoP-DEC
    main entries) and attacker 'Found block' times. Returns (tally, rows):
    tally is a Counter of max(h-a) over every reveal; rows are the ones
    race_leads.py printed (lead >= d, or the honest side reached 7 blocks)."""
    logs = run / 'daemon_logs'
    out = subprocess.run(['grep', '-a', 'Found block <', str(logs / 'monero-attacker-miner' / 'bitmonero.log')],
                         capture_output=True, text=True).stdout
    att_t = {}
    for line in out.splitlines():
        if m := FOUND.match(line):
            att_t[m.group(3)] = _ms(m.group(1), m.group(2))
    out = subprocess.run(['grep', '-a', 'SIM-SoP-DEC ', str(logs / 'monero-honest-001' / 'bitmonero.log')],
                         capture_output=True, text=True).stdout
    tally = Counter()
    rows = []
    for line in out.splitlines():
        rec = json.loads(line.split('SIM-SoP-DEC ', 1)[1])
        if rec.get('result') != 'SWITCH' or rec.get('reinsert') or rec.get('skipped'):
            continue
        alt = [b for b in rec['alt'] if b['id'] in att_t]
        if not alt:
            continue
        hon = [b['seen'] for b in rec['main'] if b['id'] not in att_t and b.get('seen')]
        att = sorted(att_t[b['id']] for b in alt)
        reveal_t = max(b['seen'] for b in rec['alt'] if b.get('seen'))
        events = sorted([(t, 'h') for t in hon] + [(t, 'a') for t in att])
        a = h = lead = 0
        for t, kind in events:
            if t > reveal_t:
                break
            if kind == 'a':
                a += 1
            else:
                h += 1
            lead = max(lead, h - a)
        tally[lead] += 1
        if lead >= d or len(hon) >= 7:
            rows.append({'t': line[:19], 'a': len(att), 'h': len(hon), 'lead': lead})
    return tally, rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_stats(out_json: str, runs: list) -> int:
    cells = load_cell_markers(REPO)
    result = {}
    for run in map(Path, runs):
        s = run_stats(run, cells)
        result[run.name] = s
        n = len(s['reveals'])
        print(f"{run.name}: found={s['found']} (att {s['found_att']}, cell says {s['attacker_found']}) "
              f"reveals={n} other={len(s['other_reorgs'])} unknown_old={s['unknown_old_ids']} "
              f"per1000={1000 * n / max(1, s['found']):.2f} depths={s['depth_hist']}")
    Path(out_json).write_text(json.dumps(result, indent=1))
    return 0


def _cmd_depths(out_json: str, runs: list) -> int:
    result = {}
    for run in map(Path, runs):
        nodes = {}
        for log in sorted(run.glob('daemon_logs/monero-*/bitmonero.log')):
            name = log.parent.name.removeprefix('monero-')
            nodes[name] = node_depths(log)
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
    return 0


def _cmd_shapes(out_json: str, runs: list) -> int:
    result = {}
    for run in map(Path, runs):
        rows = reveal_shapes(run)
        result[run.name] = rows
        print(f'== {run.name}: {len(rows)} reveals')
        for r in rows:
            if len(r['main_nsh']) >= 5:
                a_obj = len(r['alt_nsh']) + sum(r['alt_nsh'])
                m_obj = len(r['main_nsh']) + sum(r['main_nsh'])
                print(f"  {r['t'][:19]} {r['regime']:<10} depth={len(r['main_nsh']):2d} alt={r['alt_nsh']} "
                      f"main={r['main_nsh']} objects alt/main={a_obj}/{m_obj}")
    Path(out_json).write_text(json.dumps(result, indent=1))
    return 0


def _cmd_leads(d: int, runs: list) -> int:
    tally = Counter()
    for run in map(Path, runs):
        print(f'== {run.name}')
        run_tally, rows = race_leads(run, d)
        tally.update(run_tally)
        for row in rows:
            flag = '  <-- reached give-up depth' if row['lead'] >= d else ''
            print(f"  {row['t']} a={row['a']} h={row['h']} max(h-a)={row['lead']}{flag}")
    print(f'max(h-a) over all reveals: {dict(sorted(tally.items()))}  (Model B: always < {d})')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('stats')
    p.add_argument('out_json')
    p.add_argument('run_dirs', nargs='+')

    p = sub.add_parser('depths')
    p.add_argument('out_json')
    p.add_argument('run_dirs', nargs='+')

    p = sub.add_parser('shapes')
    p.add_argument('out_json')
    p.add_argument('run_dirs', nargs='+')

    p = sub.add_parser('leads')
    p.add_argument('d', type=int)
    p.add_argument('run_dirs', nargs='+')

    a = ap.parse_args(argv)
    if a.cmd == 'stats':
        return _cmd_stats(a.out_json, a.run_dirs)
    if a.cmd == 'depths':
        return _cmd_depths(a.out_json, a.run_dirs)
    if a.cmd == 'shapes':
        return _cmd_shapes(a.out_json, a.run_dirs)
    if a.cmd == 'leads':
        return _cmd_leads(a.d, a.run_dirs)
    return 2


if __name__ == '__main__':
    sys.exit(main())
