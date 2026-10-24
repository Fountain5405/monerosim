import sys, json, glob, random, yaml
sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from recency_model import run
rd = sys.argv[1]
H = yaml.safe_load(open(rd + "/shadow_agents.yaml"))["hosts"]
spy = {v["ip_addr"] for k, v in H.items() if k.startswith("spy")}
rng = random.Random(7)
MODES = sys.argv[2].split(",") if len(sys.argv) > 2 else ["24"]
tot = {m: [0, 0] for m in MODES}
ranks = []
for f in sorted(glob.glob(rd + "/daemon_logs/monero-relay-r-*/peerlist_dump.jsonl")):
    rows = [json.loads(l) for l in open(f)]
    t0 = rows[0]["t"]
    late = [r for r in rows if r["t"] - t0 > 3 * 3600][::40]
    for r in late:
        ent = [(e[0].rsplit(":", 1)[0], e[1]) for e in r["white"]]
        ls = sorted(ent, key=lambda e: -e[1])
        sp = [i for i, e in enumerate(ls) if e[0] in spy]
        if sp: ranks.append(sum(sp) / len(sp) / len(ls))
        for m in MODES:
            for _ in range(40):
                tot[m][0] += run(ent, spy, m, rng); tot[m][1] += 12
print("relay white lists after 3 h: n dumps used", len(ranks), " mean spy rank percentile %.2f" % (sum(ranks) / len(ranks)))
for m in MODES:
    print("mode %-6s spy share per slot %.4f  (24: 20 newest /24s, cubic; 24u: same 20, uniform; 24all: every unconnected /24, uniform)" % (m, tot[m][0] / tot[m][1]))
