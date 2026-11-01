import sys
from collections import defaultdict
sys.path.insert(0, "analysis"); sys.path.insert(0, "analysis/spy")
import topology_metrics as tm
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
ev = tm.load_node_events(run)
t_from, t_to = tm.default_window_bounds(general)
wins = tm.make_windows(t_from, t_to, 300)
pres = defaultdict(list)
for wi, (w0, w1) in enumerate(wins):
    out, _ = tm.snapshot_peer_sets(ev, by_ip, w0, w1)
    for n, peers in out.items():
        if not n.startswith("relay-r-"): continue
        for p in peers: pres[(n, p)].append(wi)
L = {"spy": [], "honest": []}; cens = {"spy": 0, "honest": 0}
for (n, p), idx in pres.items():
    k = "spy" if node_class.get(p) == "spy" else "honest"
    s = idx[0]; prev = idx[0]
    for x in idx[1:] + [None]:
        if x is None or x != prev + 1:
            # stretch s..prev; censored if it touches either end of the window
            L[k].append((prev - s + 1, s == 0 or prev == len(wins) - 1))
            if x is not None: s = x
        if x is not None: prev = x
for k, v in L.items():
    un = [l for l, c in v if not c]
    print(f"{k:6} stretches={len(v):5d}  mean windows (all) {sum(l for l, _ in v)/len(v):5.1f}   uncensored n={len(un):5d} mean {sum(un)/max(1,len(un)):5.1f}   censored {sum(c for _, c in v)}")
