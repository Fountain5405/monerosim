"""For each block the slow miner (honest-002) found that is not on honest-001's main chain:
the main-chain block at that height, its miner, and found-time gap (main minus lost, s).
gap < 0: the winner was found first (slow miner mined on a stale tip); gap > 0: the lost
block was found first and still lost the race."""
import sys, glob, re, json
from datetime import datetime
from pathlib import Path
R = "/home/selfishmining/monerosim"
sys.path.insert(0, R); sys.path.insert(0, R + "/scripts")
import selfish_mining_analysis as A
from scripts.honest_chain_from_log import parse_main_chain
M = ["honest-001", "honest-002", "attacker-miner"]
base = "/mnt/remote_spinny/20261024_monerosim_research_effort/*/archived_runs/"
want = sys.argv[1:]
for cell in want:
    d = sorted(glob.glob(base + "*" + cell))[-1]
    run = Path(d); cfg = A.load_raw_config(run / "input_config.yaml")
    chain = json.loads(A._find_chain_file(run, None, frozenset()).read_text())["chain"]
    pre, _ = A.split_preload(chain)
    ph = max([b["height"] for b in pre], default=None) or A._snapshot_height(run, cfg)
    found = [e for e in A.parse_found_blocks(run, M) if e["height"] > ph]
    if cell == want[0]:
        print("found-event keys:", sorted(found[0].keys()))
    tkey = next(k for k in ("time", "t", "ts", "timestamp", "found_at", "sim_time") if k in found[0])
    byhash = {e["hash"]: e for e in found}
    c1 = parse_main_chain((run / "daemon_logs/monero-honest-001/bitmonero.log").read_text(errors="replace"))
    main_at = {b["height"]: b["hash"] for b in c1}
    onmain = set(main_at.values())
    lost = [e for e in found if e["miner"] == "honest-002" and e["hash"] not in onmain]
    first, later, other = [], [], 0
    for e in lost:
        w = byhash.get(main_at.get(e["height"]))
        if not w:
            other += 1; continue
        ts = lambda x: datetime.strptime(x[:23], "%Y-%m-%d %H:%M:%S.%f").timestamp()
        gap = ts(w[tkey]) - ts(e[tkey])
        (later if gap > 0 else first).append((gap, w["miner"]))
    def summ(xs):
        if not xs: return "0"
        g = sorted(x[0] for x in xs)
        who = {}
        for _, m in xs: who[m] = who.get(m, 0) + 1
        far = sum(1 for x in g if abs(x) > 20)
        return f"{len(xs)}, {far} with |gap| > 20 s (gap median {g[len(g)//2]:+.1f} s, range {g[0]:+.1f}..{g[-1]:+.1f}; winners {who})"
    n2 = sum(1 for e in found if e["miner"] == "honest-002")
    print(f"{cell}: slow found {n2}, lost {len(lost)}")
    print(f"   winner found first (stale tip): {summ(first)}")
    print(f"   lost block found first, lost anyway: {summ(later)}")
    print(f"   no main block at that height in found events: {other}")
