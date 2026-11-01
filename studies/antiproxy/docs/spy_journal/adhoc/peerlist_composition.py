"""White and gray list size and spy count over time for the probe relays' peerlist_dump.jsonl (E16).
Usage: python3 -I peerlist_composition.py <run_dir> [relay-name ...]"""
import json, sys, yaml
R = sys.argv[1]
H = yaml.safe_load(open(R + "/shadow_agents.yaml"))["hosts"]
spy = {v["ip_addr"] for k, v in H.items() if k.startswith("spy")}
relays = sys.argv[2:] or ["relay-r-a-001", "relay-r-b-114"]
for relay in relays:
    rows = [json.loads(l) for l in open(f"{R}/daemon_logs/monero-{relay}/peerlist_dump.jsonl")]
    t0 = rows[0]["t"]
    print(relay)
    last = -1e9
    for r in rows:
        if r["t"] - last < 1800: continue
        last = r["t"]
        w = [e[0].split(":")[0] for e in r["white"]]; g = [e[0].split(":")[0] for e in r["gray"]]
        gs = sum(x in spy for x in g)
        print("  +%5.2f h  white %4d (spy %3d)  gray %4d (spy %3d = %3.0f%%)  honest gray %4d" % (
            (r["t"] - t0) / 3600, len(w), sum(x in spy for x in w), len(g), gs, 100 * gs / max(1, len(g)), len(g) - gs))
