#!/usr/bin/env python3
"""Model B (scripts/sop_race_model.py simulate()) vs the sim's logged reveals.

simulate_shapes() is simulate() copied line for line with the same RNG draws,
plus instrumentation: shares found vs embedded per side, and the shape of
every reveal (attacker blocks a, honest blocks h, per-block embedded shares).

comparison_tables() is sim vs Model B at alpha 0.33, per config (stock d2,
SoP d2/d3/d5), pooled over each config's runs. Sim side from a reveal_stats
dict (sop_reveals.py stats; reveals = reorgs on honest-001 that applied
attacker-found blocks; depth = honest blocks orphaned). Model B side from
<modelb_dir>/<rule>_d<d>.json (fixed-rate years). Canonical day = 720
canonical blocks, as in Model B. The tail test: given the sim's n reveals and
Model B's P(depth >= k | reveal), the binomial probability of seeing at
least the sim's count.

depth_test() is reveal depth (honest blocks orphaned) in the sim vs Model
B's exact reveal distribution, by resampling: for n sim reveals, how often
does a Model B sample of n reveals have a mean depth, and counts of depth
>= 7 and >= 10, at least as large as the sim's.

Usage:
  sop_model_compare.py model RULE D EMBEDS DAYS SEED OUT_JSON
  sop_model_compare.py shapes D YEARS SEED OUT_JSON
  sop_model_compare.py table SIM_JSON MODELB_DIR
  sop_model_compare.py depth-test SIM_JSON BANLOG_JSON SHAPES_D5_JSON
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import mean

# Allow `python scripts/selfish_mining/sop_model_compare.py` (no -m): put the
# repo root on sys.path so `scripts.*` resolves, same mechanism as
# scripts/selfish_matrix.py's sys.path.append, generalized (no hard-coded path).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.sop_race_model import SECONDS_PER_DAY, SimConfig, T_BLOCK_S, simulate

CONFIGS = [('stock d2', 'block_stock_a033_d2', 'stock_d2'),
           ('SoP d2', 'share_sop2_a033_d2', 'sop_d2'),
           ('SoP d3', 'share_sop2_a033_d3', 'sop_d3'),
           ('SoP d5', 'share_sop2_a033_d5', 'sop_d5')]
KS = (3, 5, 7, 10)


def simulate_shapes(cfg: SimConfig):
    """simulate() (scripts/sop_race_model.py), copied line for line with the
    same RNG draws, plus instrumentation."""
    rng = random.Random(cfg.seed)
    rate = cfg.w / T_BLOCK_S
    n_objects = int(cfg.days * SECONDS_PER_DAY * rate)
    hon_blocks, att_blocks = [], []
    hon_pending = att_pending = 0
    found = {'att_shares': 0, 'hon_shares': 0, 'att_embedded_final': 0, 'att_embedded_any': 0,
             'hon_embedded_any': 0, 'att_blocks': 0, 'hon_blocks': 0}
    reveals = []
    for _ in range(n_objects):
        is_attacker = rng.random() < cfg.alpha
        is_block = rng.random() < (1.0 / cfg.w)
        if not is_block:
            if is_attacker:
                att_pending += 1
                found['att_shares'] += 1
            else:
                hon_pending += 1
                found['hon_shares'] += 1
            continue
        if is_attacker:
            embed = att_pending if cfg.attacker_embeds else 0
            att_blocks.append(embed)
            found['att_embedded_any'] += embed
            found['att_blocks'] += 1
            att_pending = 0
        else:
            hon_blocks.append(hon_pending)
            found['hon_embedded_any'] += hon_pending
            found['hon_blocks'] += 1
            hon_pending = 0
        a, h = len(att_blocks), len(hon_blocks)
        if (a == 0 and h > 0) or (h - a >= cfg.d):
            hon_blocks.clear()
            att_blocks.clear()
            att_pending = 0
            continue
        if h == 0:
            continue
        att_objects = sum(1 + n for n in att_blocks)
        hon_weight = sum(1 + m for m in hon_blocks)
        if att_objects >= cfg.K_objects and att_objects > hon_weight:
            reveals.append({'a': a, 'h': h, 'att': list(att_blocks), 'hon': list(hon_blocks)})
            found['att_embedded_final'] += sum(att_blocks)
            hon_blocks.clear()
            att_blocks.clear()
            hon_pending = 0
            continue
    return found, reveals


def run_model(rule: str, d: int, embeds: bool, days: float, seed: int) -> dict:
    """One Model B simulate() run; the stats and full honest-orphan depth
    histogram, as run_one.py dumped them."""
    t0 = time.time()
    s = simulate(SimConfig(alpha=0.33, d=d, rule=rule, attacker_embeds=embeds, days=days, seed=seed))
    return dict(rule=rule, d=d, embeds=embeds, days=days, seed=seed, reveals=s.reveals,
                depth_hist={str(k): v for k, v in sorted(Counter(s.reorg_depths).items())},
                att_final=s.att_final_blocks, hon_final=s.hon_final_blocks,
                att_orphaned=s.att_orphaned_blocks, canonical_days=s.canonical_days,
                blocks_found=s.blocks_found, reveals_per_1000_found=s.reveals_per_1000_found,
                reveals_per_day=s.reveals_per_day, mean_depth=s.mean_reorg_depth,
                max_depth=s.max_reorg_depth, n_ge10=s.count_ge(10),
                rate_ge10_per_year=s.rate_ge10_per_year, revenue_share=s.attacker_revenue_share,
                att_orphan_frac=s.attacker_orphan_fraction, wall_s=time.time() - t0)


def binom_sf(x: int, n: int, p: float) -> float:
    """P(X >= x), X ~ Binomial(n, p), in log space (n can be thousands)."""
    if p <= 0:
        return 0.0 if x > 0 else 1.0
    if p >= 1:
        return 1.0

    def log_pmf(i):
        return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                + i * math.log(p) + (n - i) * math.log1p(-p))
    return min(1.0, sum(math.exp(log_pmf(i)) for i in range(x, n + 1)))


def _ge(hist: dict, k: int) -> int:
    return sum(v for d, v in hist.items() if int(d) >= k)


def comparison_tables(sims: dict, modelb_dir) -> str:
    """Sim vs Model B markdown tables (compare_modelb.py's two tables, as a
    single rendered string). `sims` is a reveal_stats dict (sop_reveals.py
    stats); `modelb_dir` holds <rule>_d<d>.json files."""
    modelb_dir = Path(modelb_dir)
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
        mb = json.loads((modelb_dir / f'{mb_name}.json').read_text())
        mh = {int(d): v for d, v in mb['depth_hist'].items()}
        rows.append((label, len(runs), n, f"{1000 * n / found:.2f}", f"{mb['reveals_per_1000_found']:.2f}",
                     f"{n / canon_days:.2f}", f"{mb['reveals_per_day']:.2f}",
                     f"{depth_sum / n:.2f}", f"{mb['mean_depth']:.2f}",
                     str(max(hist)), str(mb['max_depth']),
                     f"{share:.3f}", f"{mb['revenue_share']:.3f}",
                     f"{att_orph:.3f}", f"{mb['att_orphan_frac']:.3f}",
                     f"{365.25 * _ge(hist, 10) / canon_days:.1f} ({_ge(hist, 10)} in {canon_days:.1f} d)",
                     f"{mb['rate_ge10_per_year']:.3f} ({mb['n_ge10']})"))
        for k in KS:
            p_mb = _ge(mh, k) / mb['reveals']
            x = _ge(hist, k)
            tails.append((label, k, f"{x}/{n} = {x / n:.4f}", f"{p_mb:.5f}", f"{n * p_mb:.2f}",
                          f"{binom_sf(x, n, p_mb):.3g}" if x else "-"))
    out = []
    hdr = ("config", "runs", "reveals", "per 1000 found (sim)", "(B)", "per canon day (sim)", "(B)",
           "mean depth (sim)", "(B)", "max (sim)", "(B)", "att share (sim)", "(B)",
           "att orphan (sim)", "(B)", "10+ per canon yr (sim)", "(B, count)")
    out.append('| ' + ' | '.join(hdr) + ' |')
    out.append('|' + '---|' * len(hdr))
    for r in rows:
        out.append('| ' + ' | '.join(map(str, r)) + ' |')
    out.append('')
    hdr = ("config", "k", "sim P(depth>=k)", "Model B P(depth>=k)", "expected in sim", "P(sim count or more | B)")
    out.append('| ' + ' | '.join(hdr) + ' |')
    out.append('|' + '---|' * len(hdr))
    for t in tails:
        out.append('| ' + ' | '.join(map(str, t)) + ' |')
    return '\n'.join(out)


def depth_test(obs: list, model: list, n_iter: int = 50_000, seed: int = 11) -> dict:
    """Resampling test for one (obs, model) pair: mean depth, P(mean>=), and
    counts of depth >= 7 and >= 10 and their P values, as one line of
    depth_mc.py. Draws n_iter samples of len(obs) from `model`."""
    rng = random.Random(seed)
    n, m = len(obs), mean(obs)
    ge7, ge10 = sum(x >= 7 for x in obs), sum(x >= 10 for x in obs)
    hi = c7 = c10 = 0
    for _ in range(n_iter):
        s = rng.choices(model, k=n)
        hi += sum(s) / n >= m
        c7 += sum(x >= 7 for x in s) >= ge7
        c10 += sum(x >= 10 for x in s) >= ge10
    return {'n': n, 'mean': m, 'model_mean': mean(model), 'p_mean_ge': hi / n_iter,
            'ge7': ge7, 'p_ge7': c7 / n_iter, 'ge10': ge10, 'p_ge10': c10 / n_iter}


def _depths(runs) -> list:
    return [r['honest_orphaned'] for s in runs for r in s['reveals']]


def depth_by_config(sims: dict, modelb_dir, n_iter: int = 100_000, seed: int = 7) -> list:
    """Each SoP give-up depth's pooled reveal depths (runs ending in
    `__share_sop2_a033_d{d}`) against Model B's reveals at that depth
    (`shapes_d{d}.json` from the `shapes` subcommand): mean depth, both tail
    probabilities of the mean, and counts of depth >= 7 and >= 10 with their
    P values. One rng serves d = 2, 3, 5 in that order, so the order fixes
    the draws (results doc 2026-10-07 §4)."""
    rng = random.Random(seed)
    rows = []
    for d in (2, 3, 5):
        obs = _depths(s for k, s in sims.items() if k.endswith(f'__share_sop2_a033_d{d}'))
        hs = [r['h'] for r in json.loads((Path(modelb_dir) / f'shapes_d{d}.json').read_text())['reveals']]
        n, m = len(obs), mean(obs)
        ge7, ge10 = sum(x >= 7 for x in obs), sum(x >= 10 for x in obs)
        hi = lo = c7 = c10 = 0
        for _ in range(n_iter):
            s = rng.choices(hs, k=n)
            sm = sum(s) / n
            hi += sm >= m
            lo += sm <= m
            c7 += sum(x >= 7 for x in s) >= ge7
            c10 += sum(x >= 10 for x in s) >= ge10
        rows.append({'d': d, 'n': n, 'mean': m, 'model_mean': mean(hs), 'p_mean_ge': hi / n_iter,
                     'p_mean_le': lo / n_iter, 'ge7': ge7, 'p_ge7': c7 / n_iter,
                     'ge10': ge10, 'p_ge10': c10 / n_iter})
    return rows


def depth_pooled(sim_dicts: list, hs: list, n_iter: int = 100_000, seed: int = 11) -> dict:
    """Every d5 share_sop2 a033 run in every stats dict (key contains
    `__share_sop2_a033_d5`, so suffixed keys such as `_netcn_debug` count),
    pooled and tested against Model B's d5 reveal depths `hs`, both tails.
    The 2026-10-08 review asked for the pool over all eight d5 runs."""
    obs, runs = [], 0
    for sims in sim_dicts:
        for k, s in sims.items():
            if '__share_sop2_a033_d5' in k:
                runs += 1
                obs += _depths([s])
    rng = random.Random(seed)
    n, m = len(obs), mean(obs)
    ge7, ge10 = sum(x >= 7 for x in obs), sum(x >= 10 for x in obs)
    hi = lo = c7 = c10 = 0
    for _ in range(n_iter):
        s = rng.choices(hs, k=n)
        sm = sum(s) / n
        hi += sm >= m
        lo += sm <= m
        c7 += sum(x >= 7 for x in s) >= ge7
        c10 += sum(x >= 10 for x in s) >= ge10
    return {'runs': runs, 'n': n, 'mean': m, 'model_mean': mean(hs), 'p_mean_ge': hi / n_iter,
            'p_mean_le': lo / n_iter, 'ge7': ge7, 'p_ge7': c7 / n_iter,
            'ge10': ge10, 'p_ge10': c10 / n_iter}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_model(rule: str, d: int, embeds: bool, days: float, seed: int, out: str) -> int:
    r = run_model(rule, d, embeds, days, seed)
    Path(out).write_text(json.dumps(r, indent=1))
    return 0


def _cmd_shapes(d: int, years: float, seed: int, out: str) -> int:
    cfg = SimConfig(alpha=0.33, d=d, rule='sop', attacker_embeds=True, days=years * 365.25, seed=seed)
    found, reveals = simulate_shapes(cfg)
    Path(out).write_text(json.dumps({'d': d, 'years': years, 'found': found, 'reveals': reveals}))
    print(json.dumps(found), len(reveals))
    return 0


def _cmd_table(sim_json: str, modelb_dir: str) -> int:
    sims = json.loads(Path(sim_json).read_text())
    print(comparison_tables(sims, modelb_dir))
    return 0


def _cmd_depth_test(sim_json: str, banlog_json: str, shapes_d5_json: str) -> int:
    new = json.loads(Path(banlog_json).read_text())
    old = json.loads(Path(sim_json).read_text())
    hs = [r['h'] for r in json.loads(Path(shapes_d5_json).read_text())['reveals']]
    sets = {'banlog (3 runs)': _depths(new.values()),
            'long_depth d5 (2 runs)': _depths(s for k, s in old.items() if k.endswith('__share_sop2_a033_d5'))}
    sets['all 5 runs'] = sets['banlog (3 runs)'] + sets['long_depth d5 (2 runs)']
    rng = random.Random(11)
    N = 50_000
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
    return 0


def _cmd_depth_by_config(sim_json: str, modelb_dir: str) -> int:
    for r in depth_by_config(json.loads(Path(sim_json).read_text()), modelb_dir):
        print(f"d{r['d']}: n={r['n']} sim mean depth {r['mean']:.2f} vs Model B {r['model_mean']:.2f}; "
              f"P(mean >= sim)={r['p_mean_ge']:.3f} P(mean <= sim)={r['p_mean_le']:.3f}; "
              f"P(#>=7 >= {r['ge7']})={r['p_ge7']:.3f}; P(#>=10 >= {r['ge10']})={r['p_ge10']:.4f}")
    return 0


def _cmd_depth_pooled(shapes_d5_json: str, sim_jsons: list) -> int:
    hs = [r['h'] for r in json.loads(Path(shapes_d5_json).read_text())['reveals']]
    r = depth_pooled([json.loads(Path(p).read_text()) for p in sim_jsons], hs)
    print(f"pooled d5 ({r['runs']} runs): n={r['n']} mean {r['mean']:.2f} (B {r['model_mean']:.2f}) "
          f"P(mean>=)={r['p_mean_ge']:.3f} P(mean<=)={r['p_mean_le']:.3f} "
          f"P(#>=7 >= {r['ge7']})={r['p_ge7']:.3f} P(#>=10 >= {r['ge10']})={r['p_ge10']:.4f}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('model')
    p.add_argument('rule')
    p.add_argument('d', type=int)
    p.add_argument('embeds')
    p.add_argument('days', type=float)
    p.add_argument('seed', type=int)
    p.add_argument('out_json')

    p = sub.add_parser('shapes')
    p.add_argument('d', type=int)
    p.add_argument('years', type=float)
    p.add_argument('seed', type=int)
    p.add_argument('out_json')

    p = sub.add_parser('table')
    p.add_argument('sim_json')
    p.add_argument('modelb_dir')

    p = sub.add_parser('depth-test')
    p.add_argument('sim_json')
    p.add_argument('banlog_json')
    p.add_argument('shapes_d5_json')

    p = sub.add_parser('depth-by-config')
    p.add_argument('sim_json')
    p.add_argument('modelb_dir')

    p = sub.add_parser('depth-pooled')
    p.add_argument('shapes_d5_json')
    p.add_argument('sim_json', nargs='+')

    a = ap.parse_args(argv)
    if a.cmd == 'model':
        return _cmd_model(a.rule, a.d, a.embeds == 'True', a.days, a.seed, a.out_json)
    if a.cmd == 'shapes':
        return _cmd_shapes(a.d, a.years, a.seed, a.out_json)
    if a.cmd == 'table':
        return _cmd_table(a.sim_json, a.modelb_dir)
    if a.cmd == 'depth-test':
        return _cmd_depth_test(a.sim_json, a.banlog_json, a.shapes_d5_json)
    if a.cmd == 'depth-by-config':
        return _cmd_depth_by_config(a.sim_json, a.modelb_dir)
    if a.cmd == 'depth-pooled':
        return _cmd_depth_pooled(a.shapes_d5_json, a.sim_json)
    return 2


if __name__ == '__main__':
    sys.exit(main())
