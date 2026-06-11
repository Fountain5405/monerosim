#!/usr/bin/env python3
"""Join TCP connection intervals (NEW/CLOSE CONNECTION) with tx-gossip events
(Received NOTIFY_NEW_TRANSACTIONS (N txes)) in a monerod log-level-1 log.

Answers: are Rucknium's ~1.5-min tx-gap "connection durations" at 1000 nodes
(a) genuinely short-lived TX-CARRYING connections (peer rotation/churn), or
(b) long-lived connections with bursty gossip (metric artifact)?

Also: clumping distribution (txs per NOTIFY), per-connection gossip continuity,
"dropping synced peer" eviction stats, R-method span emulation per (ip,dir).
"""
import re, sys, bisect
from collections import defaultdict

LOG = sys.argv[1]
TS = re.compile(r'^(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})')
NEWC = re.compile(r'\[([\d.]+):(\d+) ([0-9a-f-]{36}) (INC|OUT)\] NEW CONNECTION')
CLOSEC = re.compile(r'\[([\d.]+):(\d+) ([0-9a-f-]{36}) (INC|OUT)\] CLOSE CONNECTION')
NOTIFY = re.compile(r'\[([\d.]+):(\d+) (INC|OUT)\] Received NOTIFY_NEW_TRANSACTIONS \((\d+) txes\)')
DROP = re.compile(r'dropping.{0,40}synced peer', re.I)

def ts_to_s(m):
    d = m.group(1)
    day = int(d[8:10])
    return ((day-1)*86400 + int(m.group(2))*3600 + int(m.group(3))*60
            + int(m.group(4)) + int(m.group(5))/1000.0)

conns = {}          # uuid -> [open_ts, close_ts, ip, port, dir]
open_by_key = {}    # (ip,port,dir) -> list of open uuids (stack)
notifies = []       # (ts, ip, port, dir, ntx)
drop_lines = 0
maxts = 0.0

with open(LOG, 'r', errors='replace') as f:
    for line in f:
        m = TS.match(line)
        if not m: continue
        t = ts_to_s(m); maxts = t
        mm = NOTIFY.search(line)
        if mm:
            notifies.append((t, mm.group(1), int(mm.group(2)), mm.group(3), int(mm.group(4))))
            continue
        mm = NEWC.search(line)
        if mm:
            ip, port, uid, d = mm.group(1), int(mm.group(2)), mm.group(3), mm.group(4)
            conns[uid] = [t, None, ip, port, d]
            open_by_key.setdefault((ip, port, d), []).append(uid)
            continue
        mm = CLOSEC.search(line)
        if mm:
            uid = mm.group(3)
            if uid in conns and conns[uid][1] is None:
                conns[uid][1] = t
                key = (conns[uid][2], conns[uid][3], conns[uid][4])
                lst = open_by_key.get(key)
                if lst and uid in lst: lst.remove(uid)
            continue
        if DROP.search(line):
            drop_lines += 1

# close-out unclosed conns at end of log
unclosed = 0
for uid, c in conns.items():
    if c[1] is None:
        c[1] = maxts; unclosed += 1

# index conn intervals per (ip,port,dir) for join
iv = defaultdict(list)
for uid, (o, cl, ip, port, d) in conns.items():
    iv[(ip, port, d)].append((o, cl, uid))
for k in iv: iv[k].sort()

# join notifies -> connections
conn_tx = defaultdict(list)   # uuid -> list of (ts, ntx)
unmatched = 0
for (t, ip, port, d, n) in notifies:
    lst = iv.get((ip, port, d))
    hit = None
    if lst:
        starts = [x[0] for x in lst]
        i = bisect.bisect_right(starts, t) - 1
        # walk back over overlapping candidates
        while i >= 0:
            o, cl, uid = lst[i]
            if o <= t <= cl + 0.001: hit = uid; break
            if t - o > 86400: break
            i -= 1
    if hit: conn_tx[hit].append((t, n))
    else: unmatched += 1

def pct(v, p):
    if not v: return float('nan')
    v = sorted(v); k = (len(v)-1)*p/100.0; f = int(k)
    return v[f] + (v[min(f+1, len(v)-1)]-v[f])*(k-f)

def stats(name, v):
    if not v:
        print(f"  {name}: (none)"); return
    print(f"  {name}: n={len(v)} median={pct(v,50):.1f}s p25={pct(v,25):.1f}s "
          f"p75={pct(v,75):.1f}s p90={pct(v,90):.1f}s max={max(v)/3600:.2f}h mean={sum(v)/len(v):.1f}s")

all_life = [c[1]-c[0] for c in conns.values()]
txc = {u: evs for u, evs in conn_tx.items() if any(n >= 1 for _, n in evs)}
tx_life = [conns[u][1]-conns[u][0] for u in txc]
notx_life = [c[1]-c[0] for u, c in conns.items() if u not in txc]

print(f"=== {LOG}")
print(f"log span: {maxts/3600:.2f}h  conns={len(conns)} (unclosed at end: {unclosed})  "
      f"notify_msgs={len(notifies)} (unmatched to a conn: {unmatched})  drop_synced_lines={drop_lines}")
print()
print("--- TCP lifetime: ALL connections ---"); stats("all", all_life)
print("--- TCP lifetime: TX-CARRYING connections (>=1 NOTIFY with >=1 tx) ---")
stats("tx-carrying", tx_life)
for d in ("OUT", "INC"):
    stats(f"tx-carrying {d}", [conns[u][1]-conns[u][0] for u in txc if conns[u][4] == d])
print("--- TCP lifetime: NON-tx connections ---"); stats("no-tx", notx_life)
print()

# how many tx-carrying conns are short vs long
n = len(tx_life)
if n:
    for thr, lbl in ((60,"<=1min"), (180,"<=3min"), (600,"<=10min"), (3600,"<=1h")):
        c = sum(1 for x in tx_life if x <= thr)
        print(f"  tx-carrying conns {lbl}: {100*c/n:.1f}%")
    c = sum(1 for x in tx_life if x > 3600)
    print(f"  tx-carrying conns  >1h: {100*c/n:.1f}%  ({c})")
print()

# gossip continuity within tx-carrying conns
spans, gaps, rates = [], [], []
for u, evs in txc.items():
    ts = sorted(t for t, n in evs if n >= 1)
    if len(ts) >= 2:
        spans.append(ts[-1]-ts[0])
        gaps += [b-a for a, b in zip(ts, ts[1:])]
        life = conns[u][1]-conns[u][0]
        if life > 0: rates.append(len(ts)/life)
single_notify_conns = sum(1 for u, evs in txc.items() if len([1 for t,n in evs if n>=1]) == 1)
print("--- gossip WITHIN tx-carrying connections ---")
print(f"  conns with exactly ONE tx-notify: {single_notify_conns}/{len(txc)} ({100*single_notify_conns/max(1,len(txc)):.1f}%)")
stats("gossip span (first->last notify) per conn", spans)
stats("inter-notify gap within conn", gaps)
print()

# R-method emulation: spans per (ip,dir) with hour-bucket conn.period grouping
evs_by_ipdir = defaultdict(list)
for (t, ip, port, d, n) in notifies:
    if n >= 1: evs_by_ipdir[(ip, d)].append(t)
r_spans = []
for k, ts in evs_by_ipdir.items():
    ts.sort()
    hours = sorted(set(int(t//3600) for t in ts))
    # group consecutive hours
    grp = {}; g = 0
    for i, h in enumerate(hours):
        if i and h - hours[i-1] > 1: g += 1
        grp[h] = g
    by_g = defaultdict(list)
    for t in ts: by_g[grp[int(t//3600)]].append(t)
    for g, tt in by_g.items():
        r_spans.append(max(tt)-min(tt))
print("--- R tx-gap method emulation (span per ip+dir per consecutive-hour period) ---")
stats("R-method 'connection duration'", r_spans)
print(f"  -> median in MINUTES: {pct(r_spans,50)/60:.2f} (Rucknium's 1k figure was 1.52 min)")
print()

# clumping
from collections import Counter
clump = Counter(n for (_, _, _, _, n) in notifies if n >= 1)
tot = sum(clump.values())
print(f"--- clumping: txs per NOTIFY message (n={tot}) ---")
cum = 0
for k in sorted(clump):
    if k <= 10:
        print(f"  {k:>3} tx: {100*clump[k]/tot:5.2f}%")
    else: cum += clump[k]
if cum: print(f"  >10 tx: {100*cum/tot:5.2f}%")
print()

# clumping over time (4h buckets)
buck = defaultdict(Counter)
for (t, _, _, _, n) in notifies:
    if n >= 1: buck[int(t//14400)][n] += 1
print("--- % single-tx messages by 4h sim-time bucket ---")
for b in sorted(buck):
    tot_b = sum(buck[b].values())
    print(f"  h{b*4:>2}-{b*4+4:<2}: {100*buck[b][1]/tot_b:5.1f}% single  (n={tot_b})")
