#!/usr/bin/env python3
"""Shape of every attacker reveal on honest-001: the SIM-SoP-DEC record of
each SWITCH onto attacker-found blocks (not reinsert/skipped). Per reveal:
attacker blocks' n_sh in branch order, honest blocks' n_sh, objects on each
side (blocks + shares), the regime and the weights.

Usage: reveal_shapes.py OUT_JSON RUN_DIR [RUN_DIR ...]
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def att_ids(run: Path) -> set:
    out = subprocess.run(['grep', '-aoE', 'Found block <[0-9a-f]{64}>',
                          str(run / 'daemon_logs' / 'monero-attacker-miner' / 'bitmonero.log')],
                         capture_output=True, text=True).stdout
    return set(re.findall(r'[0-9a-f]{64}', out))


def main():
    out_json, runs = sys.argv[1], [Path(p) for p in sys.argv[2:]]
    result = {}
    for run in runs:
        att = att_ids(run)
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
        result[run.name] = rows
        print(f'== {run.name}: {len(rows)} reveals')
        for r in rows:
            if len(r['main_nsh']) >= 5:
                a_obj = len(r['alt_nsh']) + sum(r['alt_nsh'])
                m_obj = len(r['main_nsh']) + sum(r['main_nsh'])
                print(f"  {r['t'][:19]} {r['regime']:<10} depth={len(r['main_nsh']):2d} alt={r['alt_nsh']} "
                      f"main={r['main_nsh']} objects alt/main={a_obj}/{m_obj}")
    Path(out_json).write_text(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
