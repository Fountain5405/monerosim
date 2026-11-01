#!/usr/bin/env python3
"""One Model B (scripts/sop_race_model.py simulate) run at alpha 0.33; dumps
the stats and the full honest-orphan depth histogram as JSON.
Usage: run_one.py RULE D EMBEDS DAYS SEED OUT_JSON"""
import json
import sys
import time
from collections import Counter

sys.path.insert(0, '/scratch/monerosim_dev/monerosim')
from scripts.sop_race_model import SimConfig, simulate

rule, d, embeds, days, seed, out = sys.argv[1], int(sys.argv[2]), sys.argv[3] == 'True', float(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
t0 = time.time()
s = simulate(SimConfig(alpha=0.33, d=d, rule=rule, attacker_embeds=embeds, days=days, seed=seed))
json.dump(dict(rule=rule, d=d, embeds=embeds, days=days, seed=seed, reveals=s.reveals,
               depth_hist={str(k): v for k, v in sorted(Counter(s.reorg_depths).items())},
               att_final=s.att_final_blocks, hon_final=s.hon_final_blocks,
               att_orphaned=s.att_orphaned_blocks, canonical_days=s.canonical_days,
               blocks_found=s.blocks_found, reveals_per_1000_found=s.reveals_per_1000_found,
               reveals_per_day=s.reveals_per_day, mean_depth=s.mean_reorg_depth,
               max_depth=s.max_reorg_depth, n_ge10=s.count_ge(10),
               rate_ge10_per_year=s.rate_ge10_per_year, revenue_share=s.attacker_revenue_share,
               att_orphan_frac=s.attacker_orphan_fraction, wall_s=time.time() - t0),
          open(out, 'w'), indent=1)
