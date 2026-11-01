#!/usr/bin/env python3
"""Reveal depth (honest blocks orphaned) in the sim vs Model B's exact reveal
distribution, by resampling: for n sim reveals, how often does a Model B
sample of n reveals have a mean depth, a count of depth >= 7 and a count of
depth >= 10 at least as large as the sim's? Inputs: out/reveal_stats.json
(the campaign's 240 h runs), out/reveal_stats_banlog.json (the banlog runs)
and modelb/shapes_d5.json (modelb_shapes.py 5 50 1). Usage: depth_mc.py"""
import json
import random
from pathlib import Path
from statistics import mean

D = Path(__file__).resolve().parent
new = json.loads((D / 'out' / 'reveal_stats_banlog.json').read_text())
old = json.loads((D / 'out' / 'reveal_stats.json').read_text())
hs = [r['h'] for r in json.loads((D / 'modelb' / 'shapes_d5.json').read_text())['reveals']]


def depths(runs):
    return [r['honest_orphaned'] for s in runs for r in s['reveals']]


sets = {'banlog (3 runs)': depths(new.values()),
        'long_depth d5 (2 runs)': depths(s for k, s in old.items() if k.endswith('__share_sop2_a033_d5'))}
sets['all 5 runs'] = sets['banlog (3 runs)'] + sets['long_depth d5 (2 runs)']
rng, N = random.Random(11), 50_000
for name, obs in sets.items():
    n, m = len(obs), mean(obs)
    ge7, ge10 = sum(x >= 7 for x in obs), sum(x >= 10 for x in obs)
    hi = c7 = c10 = 0
    for _ in range(N):
        s = rng.choices(hs, k=n)
        hi += sum(s) / n >= m
        c7 += sum(x >= 7 for x in s) >= ge7
        c10 += sum(x >= 10 for x in s) >= ge10
    print(f"{name}: n={n} mean {m:.2f} (B {mean(hs):.2f}) P(mean>=)={hi / N:.3f} "
          f"P(#>=7 >= {ge7})={c7 / N:.3f} P(#>=10 >= {ge10})={c10 / N:.4f}")
