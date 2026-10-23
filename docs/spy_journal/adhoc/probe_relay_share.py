"""Spy share of outbound slots in the activity window for the probe relays (the 12 that log picks) against the other
relays, and the spy fraction of their white-list picks over the same hours (E21).
Usage: python3 -I probe_relay_share.py <probe_run_dir>   (run from the repo root)"""
import sys, re
from collections import defaultdict
sys.path.insert(0, "analysis/spy"); sys.path.insert(0, "analysis"); sys.path.insert(0, ".")
import x0_calibration as x
tm = x.topology_metrics
run = sys.argv[1]
by_ip, _, _, node_class, general = tm.load_run_meta(run)
ev = tm.load_node_events(run)
t_from, t_to = tm.default_window_bounds(general)
probe = set()
import glob, os
for f in glob.glob(run + "/daemon_logs/monero-relay-r-*/peerlist_dump.jsonl"):
    probe.add(f.split("/")[-2].replace("monero-", ""))
tot = {"probe": [0, 0], "other": [0, 0]}
for w0, w1 in tm.make_windows(t_from, t_to, 300):
    out, _ = tm.snapshot_peer_sets(ev, by_ip, w0, w1)
    for n, peers in out.items():
        if not n.startswith("relay-r-") or not peers: continue
        k = "probe" if n in probe else "other"
        tot[k][0] += len(peers); tot[k][1] += sum(node_class.get(p) == "spy" for p in peers)
print("probe relays:", len(probe))
for k, (a, b) in tot.items():
    print("%-6s outbound slots %7d  spy share %.4f" % (k, a, b / a if a else 0))
