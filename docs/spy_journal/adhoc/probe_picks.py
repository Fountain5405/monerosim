import sys, re, glob, yaml
from collections import defaultdict
rd = sys.argv[1]
H = yaml.safe_load(open(rd + "/shadow_agents.yaml"))["hosts"]
spy = {v["ip_addr"] for k, v in H.items() if k.startswith("spy")}
ts = lambda s: (int(s[11:13]) * 3600 + int(s[14:16]) * 60 + float(s[17:23]))
R_PORT = re.compile(r"^(\S+ \S+)\t.*?net_node.inl:1643\tLooking at (\d+) port-deduplicated peers out of (\d+)")
R_SUB = re.compile(r"^(\S+ \S+)\t.*?net_node.inl:1754\tLooking at (\d+) subnet-deduplicated peers out of (\d+)")
R_CON = re.compile(r"^(\S+ \S+)\t.*?net_node.inl:1821\tConsidering connecting \(out\) to (white|gray) list peer: \S+ (\d+\.\d+\.\d+\.\d+):\d+.*in loop pass (\d+)")
rows = []   # per relay: list of picks
for f in sorted(glob.glob(rd + "/daemon_logs/monero-relay-r-*/bitmonero.log")):
    name = f.split("/")[-2].replace("monero-", "")
    cur = None; picks = []
    for line in open(f, errors="replace"):
        if "net_node.inl:1643" in line:
            m = R_PORT.match(line)
            if m: cur = {"t": ts(m.group(1)), "peers": int(m.group(2)), "sub": None}
        elif "net_node.inl:1754" in line and cur is not None:
            m = R_SUB.match(line)
            if m: cur["sub"] = int(m.group(2))
        elif "net_node.inl:1821" in line and cur is not None:
            m = R_CON.match(line)
            if m:
                picks.append(dict(cur, kind=m.group(2), ip=m.group(3), spy=m.group(3) in spy, pas=int(m.group(4))))
    rows.append((name, picks))
def summ(label, sel):
    for kind in ("white", "gray", "both"):
        P = [p for _, ps in rows for p in ps if sel(p) and (kind == "both" or p["kind"] == kind) and p["sub"]]
        if not P: continue
        n = len(P); sp = sum(p["spy"] for p in P)
        exp = sum(1.0 / p["sub"] for p in P)       # expected spy picks if uniform over the dedup'd candidates
        print(f"{label:22} {kind:5} picks={n:5d}  spy picks={sp:4d} ({sp/n:.3f})  uniform-over-candidates expects {exp:6.1f} ({exp/n:.3f})  "
              f"mean list={sum(p['peers'] for p in P)/n:6.1f} mean /24 candidates={sum(p['sub'] for p in P)/n:6.1f}")
for name, ps in rows:
    if ps: print(name, "first pick t=%.0f" % ps[0]["t"], "picks", len(ps), "spy", sum(p["spy"] for p in ps))
t0 = {n: ps[0]["t"] for n, ps in rows if ps}
for lo, hi, lab in ((0, 60, "first 60 s"), (60, 600, "60-600 s"), (600, 3600, "10-60 min"), (3600, 10800, "1-3 h"), (10800, 1e9, "after 3 h")):
    summ(lab, lambda p, lo=lo, hi=hi: False)
# per-relay age buckets
import itertools
def age_sel(lo, hi):
    return lambda p: False
for lo, hi, lab in ((0, 60, "age <60 s"), (60, 600, "age 1-10 min"), (600, 3600, "age 10-60 min"), (3600, 10800, "age 1-3 h"), (10800, 1e9, "age >3 h")):
    P_all = []
    for n, ps in rows:
        if not ps: continue
        for p in ps:
            if lo <= p["t"] - t0[n] < hi: P_all.append(p)
    for kind in ("white", "gray"):
        P = [p for p in P_all if p["kind"] == kind and p["sub"]]
        if not P: continue
        n = len(P); sp = sum(p["spy"] for p in P); exp = sum(1.0 / p["sub"] for p in P)
        print(f"{lab:14} {kind:5} picks={n:5d} spy={sp:4d} ({sp/n:.3f}) uniform expects {exp:6.1f} ({exp/n:.3f}) list={sum(p['peers'] for p in P)/n:6.1f} /24 cands={sum(p['sub'] for p in P)/n:6.1f}")

print("\ngray picks at age 1-3 h, by number of /24 candidates (subnet-deduplicated):")
G = [p for n, ps in rows for p in ps if p["kind"] == "gray" and 3600 <= p["t"] - t0[n] < 10800]
for lo, hi in ((0, 0), (1, 1), (2, 5), (6, 20), (21, 60), (61, 1000)):
    P = [p for p in G if p["sub"] is not None and lo <= p["sub"] <= hi]
    if P: print(f"  /24 candidates {lo}-{hi}: picks={len(P):4d} spy={sum(p['spy'] for p in P):4d} mean list size={sum(p['peers'] for p in P)/len(P):6.1f}")
print("gray picks by age (min), spy share:")
for lo in range(0, 240, 30):
    P = [p for n, ps in rows for p in ps if p["kind"] == "gray" and lo*60 <= p["t"] - t0[n] < (lo+30)*60]
    if P: print(f"  age {lo:3d}-{lo+30:3d} min: picks={len(P):4d} spy={sum(p['spy'] for p in P):3d} mean list={sum(p['peers'] for p in P)/len(P):6.1f} mean /24 cands={sum((p['sub'] or 0) for p in P)/len(P):6.1f}")
