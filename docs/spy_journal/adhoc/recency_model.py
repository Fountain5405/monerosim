import sys, json, glob, random, yaml
def cubic(m, rng):
    if m == 0: return 0
    x = rng.randrange(16*m+1)
    return (x*x*x)//(m*m*16*16*16)
def run(entries, spy, mode, rng, slots=12):
    """entries: [(ip,last_seen)]. One node's 12 sequential picks; returns spy count."""
    conn = set(); n_spy = 0
    sub = (lambda ip: ip.rsplit('.',1)[0]) if True else None   # sim IPs are a.b.0.x so /24 == /16
    for _ in range(slots):
        if mode == "24":
            order = entries[:]; rng.shuffle(order)
            seen = set(conn); cand = []
            for ip, ls in order:
                s = sub(ip)
                if s not in seen: seen.add(s); cand.append((ip, ls))
            if not cand: break
            cand.sort(key=lambda e: -e[1]); cand = cand[:20]
        else:  # legacy: every IP a candidate, skip connected subnets, recency order
            cand = [e for e in sorted(entries, key=lambda e: (-e[1], rng.random())) if sub(e[0]) not in conn][:20]
            if not cand: break
        ip, _ = cand[cubic(len(cand)-1, rng)]
        conn.add(sub(ip)); n_spy += ip in spy
    return n_spy
def main(rd, trials=300):
    d = yaml.safe_load(open(rd + "/shadow_agents.yaml"))["hosts"]
    spy = {v["ip_addr"] for k, v in d.items() if k.startswith("spy")}
    rng = random.Random(1)
    for tag, frac in (("T=2h", 0.33), ("final", 1.0)):
        res = {"24": [], "legacy": []}
        ranks = []
        for f in sorted(glob.glob(rd + "/daemon_logs/monero-observer-*/peerlist_dump.jsonl")):
            rows = [json.loads(l) for l in open(f)]
            r = rows[min(len(rows)-1, int(len(rows)*frac)-1)]
            ent = [(e[0].rsplit(':',1)[0], e[1]) for e in r["white"]]
            ls = sorted(ent, key=lambda e: -e[1])
            ranks.append(sum(i for i, e in enumerate(ls) if e[0] in spy)/max(1,sum(e[0] in spy for e in ls))/len(ls))
            for mode in res:
                s = sum(run(ent, spy, mode, rng) for _ in range(trials))
                res[mode].append(s / (trials * 12))
        print(rd.split("/")[-1][16:], tag, "mean spy rank pctile %.2f" % (sum(ranks)/len(ranks)),
              {m: round(sum(v)/len(v), 4) for m, v in res.items()})
if __name__ == "__main__":
    for rd in sys.argv[1:]: main(rd)
