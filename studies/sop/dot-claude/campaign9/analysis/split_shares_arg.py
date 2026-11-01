import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "/home/selfishmining/monerosim/scripts")
sys.path.insert(0, "/home/selfishmining/monerosim")
import selfish_mining_analysis as sma
from scripts.honest_chain_from_log import parse_main_chain

BASE = "/mnt/remote_spinny/20261024_monerosim_research_effort/phantom/archived_runs/"
RUNS = {Path(a).name.split("__")[-1]: a for a in sys.argv[1:]}
NODES = ["honest-001", "honest-002", "honest-003", "honest-004"]

for name, rd in RUNS.items():
    rd = Path(rd)
    cfg = sma.load_raw_config(rd / "input_config.yaml")
    att = sma._attacker_ids(cfg)
    miners = sorted(att | sma._honest_miner_ids(cfg))
    h2m = sma.found_by_hash(sma.parse_found_blocks(rd, miners))
    snap = sma._snapshot_height(rd, cfg)
    print(f"\n== Run {name}: {rd.name}  snapshot_height={snap} attackers={sorted(att)}")
    chains = {}
    for n in NODES:
        log = rd / "daemon_logs" / f"monero-{n}" / "bitmonero.log"
        if not log.is_file():
            print(f"{n}: no daemon log"); continue
        chains[n] = parse_main_chain(log.read_text(errors="replace"))
    ref = {b["height"]: b["hash"] for b in chains.get("honest-001", [])}
    hm = sorted(m for m in miners if m not in att)
    print("node | inrun | att | share | unk | " + " ".join(m.replace("honest-", "h") for m in hm)
          + " | final_h | tip | fork")
    for n, ch in chains.items():
        inr = [b for b in ch if b["height"] > snap]
        c = Counter(h2m.get(b["hash"], "unknown") for b in inr)
        na = sum(c[a] for a in att)
        fork = max((b["height"] for b in ch if ref.get(b["height"]) == b["hash"]), default=None)
        print(f"{n} | {len(inr)} | {na} | {na/len(inr):.4f} | {c['unknown']} | "
              + " ".join(str(c[m]) for m in hm)
              + f" | {ch[-1]['height']} | {ch[-1]['hash'][:10]} | {fork}")
