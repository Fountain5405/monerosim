#!/usr/bin/env python3
"""Did the attacker overstay its give-up depth? For every attacker reveal on
honest-001 (a SWITCH onto attacker-found blocks), rebuild the race: honest
blocks at the times honest-001 first saw them (`seen` in the SIM-SoP-DEC
main entries) and attacker blocks at the times the attacker's miner found
them. Model B gives up the moment honest leads by d blocks, so a revealed
race never reaches h - a = d there. Reports the largest h - a reached
before the reveal, per reveal.

Usage: race_leads.py D RUN_DIR [RUN_DIR ...]
"""
import calendar
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

FOUND = re.compile(r'^(2000-01-\d\d \d\d:\d\d:\d\d)\.(\d{3}).*Found block <([0-9a-f]{64})>')


def ms(ts: str, frac: str) -> int:
    return calendar.timegm(time.strptime(ts, '%Y-%m-%d %H:%M:%S')) * 1000 + int(frac)


def main():
    d, runs = int(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    tally = Counter()
    for run in runs:
        logs = run / 'daemon_logs'
        out = subprocess.run(['grep', '-a', 'Found block <', str(logs / 'monero-attacker-miner' / 'bitmonero.log')],
                             capture_output=True, text=True).stdout
        att_t = {}
        for line in out.splitlines():
            if m := FOUND.match(line):
                att_t[m.group(3)] = ms(m.group(1), m.group(2))
        out = subprocess.run(['grep', '-a', 'SIM-SoP-DEC ', str(logs / 'monero-honest-001' / 'bitmonero.log')],
                             capture_output=True, text=True).stdout
        print(f'== {run.name}')
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
                print(f'  {line[:19]} a={len(att)} h={len(hon)} max(h-a)={lead}'
                      f'{"  <-- reached give-up depth" if lead >= d else ""}')
    print(f'max(h-a) over all reveals: {dict(sorted(tally.items()))}  (Model B: always < {d})')


if __name__ == '__main__':
    main()
