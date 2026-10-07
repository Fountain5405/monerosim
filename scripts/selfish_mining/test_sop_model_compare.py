"""Tests for scripts/selfish_mining/sop_model_compare.py (ported from the
campaign 7 analysis tooling: modelb_shapes, run_one, compare_modelb,
depth_mc and the per-config depth test)."""
import json

from scripts.selfish_mining.sop_model_compare import (binom_sf, comparison_tables, depth_by_config,
                                                      depth_test, simulate_shapes)
from scripts.sop_race_model import SimConfig, simulate


def test_simulate_shapes_agrees_with_sop_race_model_simulate():
    cfg = SimConfig(alpha=0.33, d=3, rule='sop', attacker_embeds=True, days=30, seed=7)
    s = simulate(cfg)
    found, reveals = simulate_shapes(cfg)

    assert len(reveals) == s.reveals
    assert sorted(r['h'] for r in reveals) == sorted(s.reorg_depths)
    assert found['hon_blocks'] >= s.hon_final_blocks
    # every reveal's attacker block count matches what simulate() finalized
    assert sum(r['a'] for r in reveals) == s.att_final_blocks


def test_binom_sf_matches_direct_sum_for_small_n():
    import math

    def direct(x, n, p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(x, n + 1))

    for x, n, p in [(2, 10, 0.3), (0, 5, 0.5), (5, 5, 0.9)]:
        assert abs(binom_sf(x, n, p) - direct(x, n, p)) < 1e-9


def test_binom_sf_edge_cases():
    assert binom_sf(0, 10, 0.0) == 1.0
    assert binom_sf(1, 10, 0.0) == 0.0
    assert binom_sf(5, 10, 1.0) == 1.0
    assert binom_sf(0, 10, 1.0) == 1.0


def test_depth_test_is_deterministic_and_probabilities_in_range():
    obs = [1, 2, 3, 7, 10]
    model = [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 2, 3]
    r1 = depth_test(obs, model, n_iter=2000, seed=11)
    r2 = depth_test(obs, model, n_iter=2000, seed=11)
    assert r1 == r2
    for key in ('p_mean_ge', 'p_ge7', 'p_ge10'):
        assert 0.0 <= r1[key] <= 1.0
    assert r1['ge7'] == 2 and r1['ge10'] == 1


def test_depth_by_config_pools_each_sop_config_with_one_shared_rng(tmp_path):
    """Results doc §4: each SoP give-up depth's pooled reveal depths against
    Model B's reveals at that depth, d2 then d3 then d5 from one seeded rng
    (the order fixes the draws). Stock cells are not part of it."""
    sims = {'r1__share_sop2_a033_d2': {'reveals': [{'honest_orphaned': 1}, {'honest_orphaned': 2}]},
            'r2__share_sop2_a033_d2': {'reveals': [{'honest_orphaned': 3}]},
            'r1__share_sop2_a033_d3': {'reveals': [{'honest_orphaned': 7}]},
            'r1__share_sop2_a033_d5': {'reveals': [{'honest_orphaned': 10}, {'honest_orphaned': 1}]},
            'r1__block_stock_a033_d2': {'reveals': [{'honest_orphaned': 1}]}}
    for d in (2, 3, 5):
        (tmp_path / f'shapes_d{d}.json').write_text(
            json.dumps({'reveals': [{'h': 1}, {'h': 2}, {'h': 12}]}))
    rows = depth_by_config(sims, tmp_path, n_iter=500, seed=7)
    assert [r['d'] for r in rows] == [2, 3, 5]
    assert [r['n'] for r in rows] == [3, 1, 2]
    assert rows[1]['ge7'] == 1 and rows[2]['ge10'] == 1
    for r in rows:
        for key in ('p_mean_ge', 'p_mean_le', 'p_ge7', 'p_ge10'):
            assert 0.0 <= r[key] <= 1.0
    assert rows == depth_by_config(sims, tmp_path, n_iter=500, seed=7)


def test_comparison_tables_renders_header_and_one_row_per_config(tmp_path):
    sims = {
        'run1__block_stock_a033_d2': {'depth_hist': {'1': 2, '2': 1}, 'found': 100,
                                       'canonical_blocks': 720, 'share': 0.3, 'attacker_orphan_rate': 0.2},
        'run1__share_sop2_a033_d2': {'depth_hist': {'1': 1}, 'found': 50,
                                      'canonical_blocks': 720, 'share': 0.1, 'attacker_orphan_rate': 0.9},
        'run1__share_sop2_a033_d3': {'depth_hist': {'2': 1}, 'found': 50,
                                      'canonical_blocks': 720, 'share': 0.1, 'attacker_orphan_rate': 0.9},
        'run1__share_sop2_a033_d5': {'depth_hist': {'3': 1}, 'found': 50,
                                      'canonical_blocks': 720, 'share': 0.1, 'attacker_orphan_rate': 0.9},
    }
    modelb_dir = tmp_path
    for name in ('stock_d2', 'sop_d2', 'sop_d3', 'sop_d5'):
        (modelb_dir / f'{name}.json').write_text(
            '{"depth_hist": {"1": 10, "2": 5}, "reveals": 15, "reveals_per_1000_found": 1.0, '
            '"reveals_per_day": 1.0, "mean_depth": 1.5, "max_depth": 5, "revenue_share": 0.3, '
            '"att_orphan_frac": 0.5, "rate_ge10_per_year": 0.0, "n_ge10": 0}')
    table = comparison_tables(sims, modelb_dir)
    lines = table.splitlines()
    first_table = lines[:lines.index('')]
    assert first_table[0].startswith('| config |')
    assert sum(1 for l in first_table if l.startswith('| stock d2 |')) == 1
    assert sum(1 for l in first_table if l.startswith('| SoP d2 |')) == 1
    assert sum(1 for l in first_table if l.startswith('| SoP d3 |')) == 1
    assert sum(1 for l in first_table if l.startswith('| SoP d5 |')) == 1
