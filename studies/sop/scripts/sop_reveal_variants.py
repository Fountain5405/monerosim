#!/usr/bin/env python3
"""Why Model B reveals about 30x more often than MRL #146's "once per 10
days": run Model B with one assumption changed at a time (results doc 4.1).

  base            Model B as it is: the honest side counts only the shares in
                  its blocks, the attacker gives up d blocks behind.
  +pending        the honest side also counts shares found but not yet in a
                  block.
  +pending, G=n   as above, and the attacker gives up once honest leads by
                  more than n work objects (counted since the fork) instead
                  of d blocks. G=5 is tevador's T5 rule.

Usage: sop_reveal_variants.py [--alpha 0.33] [--d 2] [--days 2000] [--seed 11]
"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor

from scripts.sop_race_model import SimConfig, simulate

VARIANTS = [
    ('base', dict()),
    ('+pending', dict(count_honest_pending=True)),
    ('G=48 (objects), no pending', dict(give_up_objects=48)),
    ('+pending, G=48', dict(count_honest_pending=True, give_up_objects=48)),
    ('+pending, G=32', dict(count_honest_pending=True, give_up_objects=32)),
    ('+pending, G=16', dict(count_honest_pending=True, give_up_objects=16)),
    ('+pending, G=5 (T5)', dict(count_honest_pending=True, give_up_objects=5)),
]


def _run(args):
    name, extra, alpha, d, days, seed = args
    s = simulate(SimConfig(alpha=alpha, d=d, rule='sop', attacker_embeds=True, days=days, seed=seed, **extra))
    return (name, s.reveals, s.canonical_days, s.reveals_per_day, s.mean_reorg_depth,
            s.attacker_revenue_share)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--alpha', type=float, default=0.33)
    ap.add_argument('--d', type=int, default=2)
    ap.add_argument('--days', type=float, default=2000)
    ap.add_argument('--seed', type=int, default=11)
    a = ap.parse_args(argv)
    jobs = [(n, e, a.alpha, a.d, a.days, a.seed) for n, e in VARIANTS]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(_run, jobs))
    print(f'alpha={a.alpha} d={a.d} days={a.days:g} seed={a.seed} (fixed-rate days; rates per canonical day)\n')
    print('| variant | reveals | canonical days | reveals / day | one per (days) | mean depth | attacker share |')
    print('|---|--:|--:|--:|--:|--:|--:|')
    for name, n, cd, rpd, md, share in rows:
        per = f'{1 / rpd:.1f}' if rpd else 'never'
        print(f'| {name} | {n} | {cd:.0f} | {rpd:.3f} | {per} | {md:.2f} | {share:.4f} |')
    return 0


if __name__ == '__main__':
    sys.exit(main())
