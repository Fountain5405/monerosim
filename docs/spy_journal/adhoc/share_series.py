import sys
sys.path.insert(0, "analysis"); sys.path.insert(0, "analysis/spy")
import topology_metrics as tm
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
events = tm.load_node_events(run)
prev = {}
print("window(sim h)  light_out_share  light_out_slots  out_peers_changed_vs_prev")
for w0, w1 in tm.make_windows(3600, 28800, 1800):
    out, _ = tm.snapshot_peer_sets(events, by_ip, w0, w1)
    s = n = 0; changed = tot = 0
    for node, peers in out.items():
        if node_class.get(node) not in ("user", "relay", "observer") or not peers: continue
        n += len(peers); s += sum(node_class.get(p) == "spy" for p in peers)
        if node in prev:
            tot += len(peers); changed += len(set(peers) - prev[node])
        prev[node] = set(peers)
    print(f"{w0/3600:4.1f}-{w1/3600:4.1f}      {s/n if n else 0:.3f}          {n:6d}           {changed/tot if tot else float('nan'):.2f}")
