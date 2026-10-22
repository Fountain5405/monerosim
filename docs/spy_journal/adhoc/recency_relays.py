import sys, json, glob, random, yaml
sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from recency_model import run
rd = sys.argv[1]
H = yaml.safe_load(open(rd + "/shadow_agents.yaml"))["hosts"]
spy = {v["ip_addr"] for k, v in H.items() if k.startswith("spy")}
rng = random.Random(7)
tot = {"24": [0, 0]}
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
        for _ in range(40):
            tot["24"][0] += run(ent, spy, "24", rng); tot["24"][1] += 12
print("relay white lists after 3 h: n dumps used", len(ranks), " mean spy rank percentile %.2f" % (sum(ranks) / len(ranks)))
print("white-only /24 selection with recency (top 20, cubic) over those lists: spy share per slot %.4f" % (tot["24"][0] / tot["24"][1]))
