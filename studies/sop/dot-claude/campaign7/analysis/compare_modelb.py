#!/usr/bin/env python3
"""Sim vs Model B at alpha 0.33, per config (stock d2, SoP d2/d3/d5), pooled
over each config's 240 h runs. Sim side from reveal_stats.json (reveals =
reorgs on honest-001 that applied attacker-found blocks; depth = honest
blocks orphaned). Model B side from modelb/<rule>_d<d>.json (1000 fixed-rate
years each). Canonical day = 720 canonical blocks, as in Model B.

The tail test: given the sim's n reveals and Model B's P(depth >= k | reveal),
the binomial probability of seeing at least the sim's count.
"""
import json
import math
from pathlib import Path

S = Path(__file__).resolve().parent
CONFIGS = [('stock d2', 'block_stock_a033_d2', 'stock_d2'),
           ('SoP d2', 'share_sop2_a033_d2', 'sop_d2'),
           ('SoP d3', 'share_sop2_a033_d3', 'sop_d3'),
           ('SoP d5', 'share_sop2_a033_d5', 'sop_d5')]
KS = (3, 5, 7, 10)


def binom_sf(x, n, p):
    """P(X >= x), X ~ Binomial(n, p), in log space (n can be thousands)."""
    if p <= 0:
        return 0.0 if x > 0 else 1.0
    if p >= 1:
        return 1.0

    def log_pmf(i):
        return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                + i * math.log(p) + (n - i) * math.log1p(-p))
    return min(1.0, sum(math.exp(log_pmf(i)) for i in range(x, n + 1)))


def ge(hist, k):
    return sum(v for d, v in hist.items() if int(d) >= k)


def main():
    sims = json.loads((S / 'out' / 'reveal_stats.json').read_text())
    rows, tails = [], []
    for label, cell, mb_name in CONFIGS:
        runs = {r: s for r, s in sims.items() if r.endswith('__' + cell)}
        hist = {}
        for s in runs.values():
            for d, v in s['depth_hist'].items():
                hist[int(d)] = hist.get(int(d), 0) + v
        n = sum(hist.values())
        found = sum(s['found'] for s in runs.values())
        canon_days = sum(s['canonical_blocks'] for s in runs.values()) * 120 / 86400
        depth_sum = sum(d * v for d, v in hist.items())
        share = sum(s['share'] for s in runs.values()) / len(runs)
        att_orph = sum(s['attacker_orphan_rate'] for s in runs.values()) / len(runs)
        mb = json.loads((S / 'modelb' / f'{mb_name}.json').read_text())
        mh = {int(d): v for d, v in mb['depth_hist'].items()}
        rows.append((label, len(runs), n, f"{1000 * n / found:.2f}", f"{mb['reveals_per_1000_found']:.2f}",
                     f"{n / canon_days:.2f}", f"{mb['reveals_per_day']:.2f}",
                     f"{depth_sum / n:.2f}", f"{mb['mean_depth']:.2f}",
                     str(max(hist)), str(mb['max_depth']),
                     f"{share:.3f}", f"{mb['revenue_share']:.3f}",
                     f"{att_orph:.3f}", f"{mb['att_orphan_frac']:.3f}",
                     f"{365.25 * ge(hist, 10) / canon_days:.1f} ({ge(hist, 10)} in {canon_days:.1f} d)",
                     f"{mb['rate_ge10_per_year']:.3f} ({mb['n_ge10']})"))
        for k in KS:
            p_mb = ge(mh, k) / mb['reveals']
            x = ge(hist, k)
            tails.append((label, k, f"{x}/{n} = {x / n:.4f}", f"{p_mb:.5f}", f"{n * p_mb:.2f}",
                          f"{binom_sf(x, n, p_mb):.3g}" if x else "-"))
    hdr = ("config", "runs", "reveals", "per 1000 found (sim)", "(B)", "per canon day (sim)", "(B)",
           "mean depth (sim)", "(B)", "max (sim)", "(B)", "att share (sim)", "(B)",
           "att orphan (sim)", "(B)", "10+ per canon yr (sim)", "(B, count)")
    print('| ' + ' | '.join(hdr) + ' |')
    print('|' + '---|' * len(hdr))
    for r in rows:
        print('| ' + ' | '.join(map(str, r)) + ' |')
    print()
    hdr = ("config", "k", "sim P(depth>=k)", "Model B P(depth>=k)", "expected in sim", "P(sim count or more | B)")
    print('| ' + ' | '.join(hdr) + ' |')
    print('|' + '---|' * len(hdr))
    for t in tails:
        print('| ' + ' | '.join(map(str, t)) + ' |')


if __name__ == '__main__':
    main()
