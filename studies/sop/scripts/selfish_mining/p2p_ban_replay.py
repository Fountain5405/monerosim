#!/usr/bin/env python3
"""Replay stock monero's per-host fail score from a run's net.cn:DEBUG logs
and check that every logged ban is explained.

monerod (net_node.inl add_host_fail): fails[host] += score; when it passes
P2P_IP_FAILS_BEFORE_BLOCK (10) the host is blocked for 24 h and the score
resets to 5. It never decays. Scored drops log (net.cn DEBUG)
"[IP:port DIR] dropping connection id <uuid> (...), score S, ...". A
connection's height-drop hits log (net.cn INFO) "[IP:port DIR] Claims N,
claimed M before"; the second hit on a connection drops it with score 5.
Peer-list failures add 1 (WARNING lines, also replayed).

Also: for every "Claims" hit, did the claiming peer switch to a branch with
FEWER blocks (SoP "SIM-SoP: fork F ... alt X/a vs main Y/b ... -> SWITCH"
with a < b) shortly before? That is the hypothesised cause.

group_drops(run) groups drops.sh's per-node fail-score lines (drops.sh): one
whole-run summary, per node, of drop/ban/score lines with the volatile parts
(host IP, Claims N/M, block hash) stripped and counted.

Usage:
  p2p_ban_replay.py replay RUN_DIR [RUN_DIR ...]
  p2p_ban_replay.py drops RUN_DIR
"""
from __future__ import annotations

import argparse
import calendar
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml

PAT = ('Claims [0-9]+, claimed [0-9]+ before|dropping connection id|Host [0-9.]+ blocked|'
       'failed to handle_remote_peerlist|came not from incoming|WRONG NETWORK')
TS = re.compile(r'^(2000-01-\d\d \d\d:\d\d:\d\d)\.(\d{3})\t')
CONN = re.compile(r'\[(\d+\.\d+\.\d+\.\d+):(\d+) (INC|OUT)\]')
SWITCH = re.compile(r'SIM-SoP: fork \d+ (?:OBJECTIVE )?alt \d+/(\d+) vs main \d+/(\d+).*-> SWITCH')
WINDOW_MS = 30 * 60 * 1000   # a chain-entry hit can come well after the switch
DROP_PAT = ('dropping connection|Host [0-9.]+ blocked|Claims [0-9]+, claimed|'
            'Negative score|Sent invalid chain|sent wrong block')
DROP_CONN = re.compile(r'\[[0-9.]+:[0-9]+ (?:INC|OUT)\] ')
DROP_HOST = re.compile(r'Host [0-9.]+')
DROP_CLAIMS = re.compile(r'Claims [0-9]+, claimed [0-9]+')
DROP_BLOCK = re.compile(r'block: [0-9a-f]+')


def ms(line: str):
    m = TS.match(line)
    return calendar.timegm(time.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')) * 1000 + int(m.group(2)) if m else None


def grep(pat: str, path) -> list:
    # -e before the pattern: a pattern starting with '-' would otherwise be
    # read as an option.
    return subprocess.run(['grep', '-aE', '-e', pat, str(path)], capture_output=True, text=True).stdout.splitlines()


def replay(run: Path) -> dict:
    """Everything ban_replay.py printed for one run: bans logged/replayed/
    matched, scored-drop kinds, height-drop-hit causes, lag stats, the total
    shorter-branch switches seen, and the unexplained-bans list."""
    run = Path(run)
    agents = yaml.safe_load((run / 'shadow_agents.yaml').read_text())
    hosts = agents.get('hosts', agents)
    ip_of = {name: h.get('ip_addr') for name, h in hosts.items() if isinstance(h, dict)}
    node_of = {ip: name for name, ip in ip_of.items() if ip}
    logs = {p.parent.name.removeprefix('monero-'): p for p in (run / 'daemon_logs').glob('monero-*/bitmonero.log')}
    shorter = {}
    for name, log in logs.items():
        shorter[name] = [ms(l) for l in grep('-> SWITCH', log)
                         if (m := SWITCH.search(l)) and int(m.group(1)) < int(m.group(2))]
    bans_actual = bans_pred = matched = 0
    drop_kinds, claim_cause, unexplained, lags = Counter(), Counter(), [], []
    for name, log in sorted(logs.items()):
        fails, hits = defaultdict(int), defaultdict(int)
        pred = []
        for line in grep(PAT, log):
            t = ms(line)
            if 'blocked.' in line:
                ip = re.search(r'Host (\d+\.\d+\.\d+\.\d+) blocked', line).group(1)
                bans_actual += 1
                hit = next((p for p in pred if p[1] == ip and abs(p[0] - t) <= 5), None)
                if hit:
                    matched += 1
                    pred.remove(hit)
                else:
                    unexplained.append((name, line[:23], ip, fails[ip]))
                continue
            c = CONN.search(line)
            if not c:
                continue
            ip, conn = c.group(1), c.group(0)
            if 'Claims ' in line:
                hits[conn] += 1
                peer = node_of.get(ip, ip)
                sw = shorter.get(peer, [])
                lag = min((t - s for s in sw if 0 <= t - s <= WINDOW_MS), default=None)
                claim_cause['after a shorter-branch switch by the peer' if lag is not None
                            else ('no shorter switch found' if peer in shorter else 'peer log missing')] += 1
                if lag is not None:
                    lags.append(lag)
                continue
            score = 1
            if 'dropping connection id' in line:
                score = int(re.search(r'score (\d+)', line).group(1))
                if score == 0:
                    continue
                drop_kinds['score %d after %s' % (score, 'height-drop hits' if hits[conn] else 'no height-drop hit')] += 1
                hits[conn] = 0
            else:
                drop_kinds['peer-list/handshake +1'] += 1
            fails[ip] += score
            if fails[ip] > 10:
                fails[ip] = 5
                bans_pred += 1
                pred.append((t, ip))
    lags.sort()
    lag_stats = None
    if lags:
        lag_stats = {'median_s': lags[len(lags) // 2] / 1000, 'p90_s': lags[int(len(lags) * 0.9)] / 1000,
                     'max_s': lags[-1] / 1000}
    return {'bans_logged': bans_actual, 'bans_replayed': bans_pred, 'matched': matched,
            'drop_kinds': dict(drop_kinds), 'claim_cause': dict(claim_cause),
            'lags': lags, 'lag_stats': lag_stats,
            'shorter_switches_total': sum(len(v) for v in shorter.values()),
            'unexplained': unexplained}


def group_drops(run: Path) -> dict:
    """drops.sh's grouping: per node, drop/ban/score lines with the
    volatile parts (host IP, Claims N/M, block hash) stripped and counted,
    whole run."""
    run = Path(run)
    result = {}
    for log in sorted(run.glob('daemon_logs/monero-*/bitmonero.log')):
        name = log.parent.name.removeprefix('monero-')
        counts = Counter()
        for line in grep(DROP_PAT, log):
            fields = line.split('\t')
            msg = fields[-1]
            msg = DROP_CONN.sub('', msg)
            msg = DROP_HOST.sub('Host X', msg)
            msg = DROP_CLAIMS.sub('Claims N, claimed M', msg)
            msg = DROP_BLOCK.sub('block: ...', msg)
            key = fields[0][:13] + '|' + msg
            counts[key] += 1
        result[name] = dict(counts)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_replay(runs: list) -> int:
    for run in map(Path, runs):
        r = replay(run)
        print(f'== {run.name}')
        print(f"  bans logged {r['bans_logged']}, replayed {r['bans_replayed']}, "
              f"matched (same host, within 5 ms) {r['matched']}")
        print(f"  scored drops: {r['drop_kinds']}")
        print(f"  height-drop hits: {r['claim_cause']}")
        if r['lag_stats']:
            s = r['lag_stats']
            print(f"  lag switch -> hit: median {s['median_s']:.1f} s, 90th pct {s['p90_s']:.1f} s, "
                  f"max {s['max_s']:.1f} s")
        print(f"  shorter-branch switches per node: {r['shorter_switches_total']} total")
        if r['unexplained']:
            print(f"  UNEXPLAINED bans (node, time, host, replayed score): {r['unexplained'][:10]}")
    return 0


def _cmd_drops(run: str) -> int:
    groups = group_drops(Path(run))
    for name, counts in groups.items():
        for key, n in counts.items():
            print(f'{name} {n:6d} {key}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('replay')
    p.add_argument('run_dirs', nargs='+')
    p = sub.add_parser('drops')
    p.add_argument('run_dir')
    a = ap.parse_args(argv)
    if a.cmd == 'replay':
        return _cmd_replay(a.run_dirs)
    if a.cmd == 'drops':
        return _cmd_drops(a.run_dir)
    return 2


if __name__ == '__main__':
    sys.exit(main())
