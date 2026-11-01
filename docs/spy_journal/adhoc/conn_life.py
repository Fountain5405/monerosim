import sys
from collections import defaultdict
sys.path.insert(0, "analysis"); sys.path.insert(0, "analysis/spy")
import topology_metrics as tm
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
ev = tm.load_node_events(run)
t_from, t_to = tm.default_window_bounds(general)
wins = tm.make_windows(t_from, t_to, 300)
print("activity window", t_from, t_to, "n windows", len(wins))
# first-seen order and per-window sets for relays
share_by_w = []
life = {"spy": [], "honest": []}
runs = defaultdict(list)   # (relay, peer) -> list of window idx present
for wi, (w0, w1) in enumerate(wins):
    out, _ = tm.snapshot_peer_sets(ev, by_ip, w0, w1)
    a = b = 0
    for n, peers in out.items():
        if not n.startswith("relay-r-"): continue
        for p in peers:
            runs[(n, p)].append(wi)
            a += 1; b += node_class.get(p) == "spy"
    share_by_w.append((b, a))
print("relay spy share by window (every 6th):", [round(b / a, 3) for b, a in share_by_w[::6] if a])
for (n, p), idx in runs.items():
    k = "spy" if node_class.get(p) == "spy" else "honest"
    # count contiguous stretches
    stretches = 1 + sum(1 for x, y in zip(idx, idx[1:]) if y != x + 1)
    life[k].append((len(idx), stretches))
for k, v in life.items():
    print(k, "distinct (relay,peer) pairs", len(v), "mean windows present %.1f" % (sum(x for x, _ in v) / len(v)),
          "mean stretches %.2f" % (sum(s for _, s in v) / len(v)))
