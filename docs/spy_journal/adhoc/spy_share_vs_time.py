"""Spy share of the relays' outbound slots against simulated time, by relay start order (E16).
Usage: python3 -I spy_share_vs_time.py <run_dir>   (run from the repo root)"""
import sys, re
from collections import defaultdict
sys.path.insert(0, "analysis/spy"); sys.path.insert(0, "analysis"); sys.path.insert(0, ".")
import x0_calibration as x
tm = x.topology_metrics
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
events = tm.load_node_events(run)
t_from, t_to = tm.default_window_bounds(general)
print("activity window %d-%d s" % (t_from, t_to))
order = {}
for n in node_class:
    m = re.match(r"relay-r-([ab])-(\d+)", n)
    if m: order[n] = int(m.group(2)) * 2 + (m.group(1) == "b")
qs = sorted(order.values()); cut = [qs[len(qs) * i // 4] for i in range(1, 4)]
grp = lambda n: sum(order[n] >= c for c in cut)
print("%7s %9s | %s" % ("sim h", "all relays", "by start-order quarter (slots, spy share)"))
for t in range(1800, int(t_to) + 1, 1800):
    out_peers, _ = tm.snapshot_peer_sets(events, by_ip, t - 300, t)
    tot = defaultdict(lambda: [0, 0])
    for node, peers in out_peers.items():
        if node not in order or not peers: continue
        for g in (grp(node), "all"):
            tot[g][0] += len(peers); tot[g][1] += sum(node_class.get(p) == "spy" for p in peers)
    f = lambda g: "%.4f" % (tot[g][1] / tot[g][0]) if tot[g][0] else "  -   "
    print("%7.1f %9s | %s | slots %d" % (t / 3600, f("all"), "  ".join(f(g) for g in range(4)), tot["all"][0]))
