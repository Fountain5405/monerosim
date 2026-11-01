"""Per node: SoP fork decisions (SIM-SoP-DEC) and how late the competing (alt) blocks
were first seen, relative to the main block at the same height (seen - ref, s).
Also: KEEP decisions where the alt branch was longer than the main branch."""
import sys, glob, json
base = "/mnt/remote_spinny/20261024_monerosim_research_effort/*/archived_runs/"
for cell in sys.argv[1:]:
    d = sorted(glob.glob(base + "*" + cell))[-1]
    print(f"== {cell}")
    for node in ("honest-001", "honest-002", "attacker-miner", "relay-chain-1", "relay-chain-4", "relay-chain-7"):
        try:
            fh = open(f"{d}/daemon_logs/monero-{node}/bitmonero.log", errors="replace")
        except FileNotFoundError:
            continue
        decs = []
        for line in fh:
            i = line.find("SIM-SoP-DEC ")
            if i >= 0:
                try:
                    decs.append(json.loads(line[i + 12:]))
                except ValueError:
                    pass
        if not decs:
            print(f"  {node}: no decisions"); continue
        dms = decs[0]["d_ms"]
        lags, res, keep_longer = [], {}, 0
        seen_alt = set()
        for x in decs:
            res[x["result"]] = res.get(x["result"], 0) + 1
            for b in x["alt"]:
                if b["id"] in seen_alt or b.get("seen") is None or b.get("ref") is None:
                    continue
                seen_alt.add(b["id"])
                lags.append((b["seen"] - b["ref"]) / 1000)
            if x["result"].startswith("KEEP") and len(x["alt"]) > len(x["main"]):
                keep_longer += 1
        lags.sort()
        q = lambda p: lags[min(len(lags) - 1, int(p * len(lags)))] if lags else float("nan")
        late = sum(1 for v in lags if v > dms / 1000)
        print(f"  {node:15s} d={dms/1000:.0f}s decisions {len(decs):4d} {res}  alt blocks {len(lags):4d}: "
              f"lag median {q(.5):6.1f}s p90 {q(.9):6.1f}s, late (> d) {late}; KEEP with longer alt {keep_longer}")
