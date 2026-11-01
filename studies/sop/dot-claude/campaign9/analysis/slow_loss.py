import sys, glob, json, re
from pathlib import Path
R = "/home/selfishmining/monerosim"
sys.path.insert(0, R); sys.path.insert(0, R + "/scripts")
import selfish_mining_analysis as A
from scripts.honest_chain_from_log import parse_main_chain
M = ["honest-001", "honest-002", "attacker-miner"]
pat = "/mnt/remote_spinny/20261024_monerosim_research_effort/*/archived_runs/*_sop_v4_slow_72h__honest_*_a047_l*_s1"
cells = {}
for d in glob.glob(pat):
    m = re.search(r"/(\d{8}_\d{6})_sop_v4_slow_72h__honest_(\w+)_a047_l(\d+)_s1$", d)
    if not m or m.group(3) not in ("3", "6", "12"): continue
    k = (m.group(2), int(m.group(3)))
    if k not in cells or m.group(1) > cells[k][0]: cells[k] = (m.group(1), d)
def tip(run, node):
    c = parse_main_chain((Path(run)/"daemon_logs"/f"monero-{node}"/"bitmonero.log").read_text(errors="replace"))
    return c
rows = []
for (rule, l), (_, d) in sorted(cells.items(), key=lambda x: (x[0][1], x[0][0])):
    run = Path(d); cfg = A.load_raw_config(run/"input_config.yaml")
    chain = json.loads(A._find_chain_file(run, None, frozenset()).read_text())["chain"]
    pre, _ = A.split_preload(chain)
    ph = max([b["height"] for b in pre], default=None)
    sh = A._snapshot_height(run, cfg)
    if ph is None: ph = sh
    elif sh and sh != ph: print("WARN preload mismatch", d, ph, sh)
    found = A.parse_found_blocks(run, M)
    h2m = {}
    for e in found:
        if e["height"] > ph: h2m.setdefault(e["hash"], e["miner"])
    c1 = tip(run, "honest-001"); c2 = tip(run, "honest-002")
    kept = {}
    for b in c1:
        if b["height"] > ph and b["hash"] in h2m: kept[h2m[b["hash"]]] = kept.get(h2m[b["hash"]], 0) + 1
    F = {m: sum(1 for v in h2m.values() if v == m) for m in M}
    K = {m: kept.get(m, 0) for m in M}
    tf, tk = sum(F.values()), sum(K.values())
    rows.append((f"{rule} l{l}", ph, M and [f"{K[m]}/{F[m]} ({100*(F[m]-K[m])/F[m]:.1f}%)" for m in M], (tf-tk)/tf,
                 c1[-1]["hash"] == c2[-1]["hash"], c1[-1]["height"], c2[-1]["height"]))
print("cell | preload | h001 kept/found (lost%) | h002 | attacker-miner | net orphan | tips equal (h1,h2)")
for r in rows: print(r[0], r[1], *r[2], f"{r[3]:.3f}", r[4], r[5], r[6], sep=" | ")
