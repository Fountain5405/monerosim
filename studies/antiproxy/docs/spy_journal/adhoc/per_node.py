import sys, re
from collections import Counter, defaultdict
sys.path.insert(0, "analysis/spy"); sys.path.insert(0, "analysis"); sys.path.insert(0, ".")
import x0_calibration as x
tm = x.topology_metrics
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
events = tm.load_node_events(run)
t_from, t_to = tm.default_window_bounds(general)
per = defaultdict(lambda: [0, 0])
for w0, w1 in tm.make_windows(t_from, t_to, 300):
    out_peers, _ = tm.snapshot_peer_sets(events, by_ip, w0, w1)
    for node, peers in out_peers.items():
        if node_class.get(node) == "spy" or not peers: continue
        per[node][0] += len(peers)
        per[node][1] += sum(node_class.get(p) == "spy" for p in peers)
rel = []
for n, (a, b) in per.items():
    m = re.match(r"relay-r-([ab])-(\d+)", n)
    if m: rel.append((int(m.group(2)) * 2 + (m.group(1) == "b"), n, a, b))
rel.sort()
k = len(rel) // 4 or 1
for i in range(0, len(rel), k):
    ch = rel[i:i + k]
    print("relays by start order %3d-%3d: spy share %.4f" % (i, i + len(ch) - 1, sum(c[3] for c in ch) / sum(c[2] for c in ch)))
cls = defaultdict(lambda: [0, 0])
for n, (a, b) in per.items():
    c = node_class.get(n, "?"); cls[c][0] += a; cls[c][1] += b
for c, (a, b) in sorted(cls.items()): print(c, round(b / a, 4), a)
