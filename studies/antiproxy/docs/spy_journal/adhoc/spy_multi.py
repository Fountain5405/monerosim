import sys
from collections import Counter
sys.path.insert(0, "analysis"); sys.path.insert(0, "analysis/spy")
import topology_metrics as tm
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
ev = tm.load_node_events(run)
t_from, t_to = tm.default_window_bounds(general)
wins = tm.make_windows(t_from, t_to, 300)
for tag, wi in (("first window", 0), ("window 12", 12), ("window 24", 24), ("last window", len(wins) - 1)):
    out, _ = tm.snapshot_peer_sets(ev, by_ip, *wins[wi])
    c = Counter(); n = 0
    for node, peers in out.items():
        if not node.startswith("relay-r-"): continue
        c[sum(node_class.get(p) == "spy" for p in peers)] += 1; n += 1
    print(tag, "relays by #spy outbound peers:", dict(sorted(c.items())), "of", n)
