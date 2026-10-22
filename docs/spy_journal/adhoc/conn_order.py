import sys, re
from collections import defaultdict, Counter
sys.path.insert(0, "analysis"); sys.path.insert(0, "analysis/spy")
import topology_metrics as tm
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
ev = tm.load_node_events(run)
n0 = next(n for n in ev if n.startswith("relay-r-a-001"))
print(n0, ev[n0][:6], len(ev[n0]))
kinds = Counter(e[2] for e in ev[n0]); print(kinds)
# order of outbound connection formation per relay
byorder = defaultdict(lambda: [0, 0]); first_t = {}
for n, es in ev.items():
    if not n.startswith("relay-r-"): continue
    seen = []; 
    for t, ip, d in es:
        if d != "OUT" or ip in seen: continue
        seen.append(ip)
    for i, ip in enumerate(seen[:30]):
        byorder[i][0] += 1; byorder[i][1] += node_class.get(by_ip.get(ip)) == "spy"
    byorder["distinct_total"][0] += 1; byorder["distinct_total"][1] += len(seen)
for k in sorted((k for k in byorder if k != "distinct_total")):
    a, b = byorder[k]; print("conn #%2d spy rate %.3f (n=%d)" % (k + 1, b / a, a))
a, b = byorder["distinct_total"]; print("mean distinct out peers seen per relay over whole run: %.1f" % (b / a))
