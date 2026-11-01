#!/usr/bin/env python3
"""The stock network's selfish-mining crossing in the race model, for the
comparison with SoP's (docs/20261026_sop_attacker_search.md). The attacker
is the model's stock stubborn rule (scripts/sop_race_model.py
stubborn_policy under rule "stock": withhold while unopposed, reveal once
ahead by a block after an honest block, give up when behind by d blocks),
swept over d and alpha; the sims measured 0.398 at 0.40 and 0.528 at 0.45
for the stock network's window_stubborn attacker.

    python scripts/sop_stock_crossing.py --alphas 0.30 0.32 0.34 0.36 0.38 0.40 0.42 \\
        --d 1 2 3 --days 2000 --seeds 1 2 3 --workers 12 --out data/sop_search/stock_crossing.jsonl

One JSON line per run (resumable), then the share per (d, alpha) and the
crossing per d. Never on the control box.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Tuple

if __name__ == "__main__":   # run as `python scripts/sop_stock_crossing.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sop_attacker_search import crossing
from scripts.sop_race_model import SimConfig, simulate


def stock_config(alpha: float, days: float, seed: int, d: int = 2) -> SimConfig:
    """The stock network: no window, no shares, the block give-up d."""
    return SimConfig(alpha=alpha, d=d, rule="stock", attacker_embeds=False, days=days, seed=seed)


def evaluate(d: int, alpha: float, days: float, seed: int) -> dict:
    st = simulate(stock_config(alpha, days, seed, d))
    hon_orphaned = sum(st.reorg_depths)
    found = st.att_final_blocks + st.att_orphaned_blocks + st.hon_final_blocks + hon_orphaned
    return {"d": d, "alpha": alpha, "seed": seed, "days": days, "share": st.attacker_revenue_share,
            "reveals": st.reveals, "mean_reorg": st.mean_reorg_depth if hasattr(st, "mean_reorg_depth") else
            (hon_orphaned / st.reveals if st.reveals else 0.0),
            "att_orphan_rate": st.attacker_orphan_fraction,
            "net_orphan_rate": (st.att_orphaned_blocks + hon_orphaned) / found if found else 0.0}


def _work(task):
    return evaluate(*task)


def report(rows: List[dict], out=sys.stdout) -> None:
    by: Dict[Tuple[int, float], List[float]] = defaultdict(list)
    for r in rows:
        by[(r["d"], r["alpha"])].append(r["share"])
    ds = sorted({d for d, _ in by})
    alphas = sorted({a for _, a in by})
    print("alpha  | " + " ".join(f"d={d:<6}" for d in ds), file=out)
    for a in alphas:
        print(f"{a:5.2f}  | " + " ".join(f"{sum(by[(d, a)]) / len(by[(d, a)]):.4f}  " if (d, a) in by else "   -     "
                                         for d in ds), file=out)
    for d in ds:
        pts = [(a, sum(by[(d, a)]) / len(by[(d, a)])) for a in alphas if (d, a) in by]
        c = crossing(pts) if len(pts) >= 3 else None
        print(f"crossing d={d}: {('%.4f' % c) if c is not None else 'none'}", file=out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alphas", type=float, nargs="+", required=True)
    ap.add_argument("--d", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--days", type=float, default=2000.0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, done = [], set()
    if out.exists():
        for line in out.open():
            if line.strip():
                r = json.loads(line)
                rows.append(r)
                done.add((r["d"], r["alpha"], r["seed"]))
    tasks = [(d, a, args.days, s) for d in args.d for a in args.alphas for s in args.seeds if (d, a, s) not in done]
    print(f"{len(tasks)} runs to do, {len(done)} already in {out}", file=sys.stderr, flush=True)
    t0 = time.time()
    if tasks:
        with Pool(args.workers) as pool, out.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(_work, tasks), 1):
                f.write(json.dumps(r) + "\n")
                f.flush()
                rows.append(r)
                if i % 10 == 0 or i == len(tasks):
                    print(f"  {i}/{len(tasks)} done [{time.time() - t0:.0f}s]", file=sys.stderr, flush=True)
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
