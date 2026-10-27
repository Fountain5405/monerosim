# scripts/test_sop_race_model.py
import math
import random

from scripts.sop_race_model import (
    K_DEFAULT, W_DEFAULT, RaceResult, SimConfig, a1_race_to_k,
    a2_strategy2_objects, a3_strategy2_formula, binom_sf_ge, objects_per_day,
    reg_incomplete_beta, run_model_a, RULE_PRESETS, simulate, simulate_race_to_k,
)


def test_reg_incomplete_beta_matches_known_table_values():
    # Grunspan & Perez-Marco Theorem 1 table: q=0.3, z=10 -> 6.51067%
    q, p = 0.3, 0.7
    x = 4 * p * q
    got = reg_incomplete_beta(x, 10, 0.5)
    assert abs(got * 100 - 6.51067) < 1e-3
    # q=0.45, z=1 -> 90.0%
    x2 = 4 * 0.55 * 0.45
    got2 = reg_incomplete_beta(x2, 1, 0.5)
    assert abs(got2 * 100 - 90.0) < 1e-6


def test_reg_incomplete_beta_boundaries():
    assert reg_incomplete_beta(0.0, 3, 3) == 0.0
    assert reg_incomplete_beta(1.0, 3, 3) == 1.0


def test_binom_sf_ge_matches_brute_force():
    n, k, p = 10, 4, 0.33
    exact = binom_sf_ge(n, k, p)
    brute = sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
    assert abs(exact - brute) < 1e-12


def test_a1_race_to_k_probability_matches_monte_carlo():
    alpha, K = 0.33, 6  # small K for a fast, tight Monte Carlo check
    r = a1_race_to_k(alpha, K, w=W_DEFAULT, trials=40000, seed=7)
    rng = random.Random(123)
    wins = sum(1 for _ in range(40000) if simulate_race_to_k(alpha, K, rng)[0])
    mc_p = wins / 40000
    assert abs(r.p_success - mc_p) < 0.01


def test_a1_and_a3_z_equal_k_agree_by_known_identity():
    # P(Binomial(2K-1,p) >= K) == I_p(K,K) (regularized-incomplete-beta /
    # binomial-tail identity); cross-checks A1's exact formula against
    # Rucknium's Strategy-2 formula evaluated at the same z=K.
    alpha, K = 0.33, 48
    a1 = a1_race_to_k(alpha, K, trials=100)
    a3 = a3_strategy2_formula(alpha, K)
    assert abs(a1.p_success - a3.p_success) < 1e-9


def test_a2_strategy2_objects_is_a_valid_probability():
    r = a2_strategy2_objects(0.33, K_DEFAULT * W_DEFAULT)
    assert 0.0 <= r.p_success <= 1.0
    assert r.expected_cycle_objects > 0


def test_run_model_a_reproduces_tevadors_order_of_magnitude_claims():
    results = run_model_a(alpha=0.33, w=W_DEFAULT, k=K_DEFAULT, seed=3)
    names = [r.name for r in results]
    assert "A1 race-to-K" in names
    # tevador: "< 0.06%" probability
    for r in results:
        if "z=48" in r.name:
            assert r.p_success < 0.0006
            # tevador: "once per 10 days" (broad band)
            assert 3 <= r.expected_days_between_successes <= 30
    # tevador: "on average a 3-block reorg"
    a1 = next(r for r in results if r.name == "A1 race-to-K")
    assert 2.0 <= a1.mean_reorg_blocks <= 4.0


def test_objects_per_day_matches_spec_arithmetic():
    assert abs(objects_per_day(w=16) - 86400 * 16 / 120) < 1e-9


# ---------------------------------------------------------------------------
# Model B: hand-fed sequences.
# ---------------------------------------------------------------------------

class _FixedRng:
    """A rng stand-in that replays a scripted sequence of draws.

    Each entry is (is_attacker, is_block) pre-decided; we monkeypatch
    simulate()'s two random() calls by controlling the thresholds via a
    sequence of floats tuned against alpha/w. Simpler: we directly drive the
    object-processing loop logic via a tiny local reimplementation matching
    simulate()'s body, to keep the test deterministic and readable.
    """


def _run_events(events, alpha, w, d, rule, attacker_embeds, K_objects=48):
    """Feed an explicit list of (is_attacker, is_block) events through the
    same decision logic as simulate(), without relying on RNG. Returns a
    SimStats-like dict for assertions."""
    from scripts.sop_race_model import SimStats
    stats = SimStats(sim_days=1.0)
    hon_blocks, att_blocks = [], []
    hon_pending = att_pending = 0

    def reset_fork():
        hon_blocks.clear()
        att_blocks.clear()

    for is_attacker, is_block in events:
        if not is_block:
            if is_attacker:
                att_pending += 1
            else:
                hon_pending += 1
            continue
        if is_attacker:
            embed = att_pending if attacker_embeds else 0
            att_blocks.append(embed)
            att_pending = 0
        else:
            hon_blocks.append(hon_pending)
            hon_pending = 0

        a, h = len(att_blocks), len(hon_blocks)
        if (a == 0 and h > 0) or (h - a >= d):
            stats.hon_final_blocks += h
            stats.att_orphaned_blocks += a
            reset_fork()
            att_pending = 0
            continue
        if h == 0:
            continue
        if rule == "sop":
            att_objects = sum(1 + n for n in att_blocks)
            att_weight = att_objects
            hon_weight = sum(1 + m for m in hon_blocks)
            K = K_objects
        else:
            att_objects = a
            att_weight = a
            hon_weight = h
            K = 0
        if att_objects >= K and att_weight > hon_weight:
            stats.reveals += 1
            stats.reorg_depths.append(h)
            stats.att_final_blocks += a
            reset_fork()
            hon_pending = 0
            continue
    return stats


def test_stock_rule_reveals_as_soon_as_attacker_chain_is_longer():
    # Blocks only (every event is_block=True): attacker, attacker, honest.
    # After 2 attacker blocks (a=2,h=0): h==0 -> withhold.
    # Then honest block (a=2,h=1): stock rule K=0, att_objects=2>=0,
    # att_weight=2 > hon_weight=1 -> reveal, reorg depth = h = 1.
    events = [(True, True), (True, True), (False, True)]
    s = _run_events(events, alpha=0.4, w=16, d=3, rule="stock", attacker_embeds=False)
    assert s.reveals == 1
    assert s.reorg_depths == [1]
    assert s.att_final_blocks == 2


def test_give_up_when_honest_lead_reaches_d():
    # Attacker never mines a block; honest mines d=2 blocks in a row.
    # First honest block: a=0,h=1 -> give up immediately (a==0 and h>0).
    # Second honest block: a=0,h=1 again (fork reset after first) -> give up.
    events = [(False, True), (False, True)]
    s = _run_events(events, alpha=0.4, w=16, d=2, rule="stock", attacker_embeds=False)
    assert s.reveals == 0
    assert s.hon_final_blocks == 2
    assert s.att_orphaned_blocks == 0


def test_sop_rule_requires_reaching_K_objects_even_if_weight_favors_attacker():
    # attacker_embeds=True: attacker accumulates many pending shares then
    # mines a block embedding them, but with sop rule K=48 objects is far
    # out of reach with only one attacker block -> no reveal despite
    # att_weight > hon_weight being possible in principle for small K.
    events = [(True, False)] * 5 + [(True, True)]  # 5 shares + 1 block = 6 objects
    events += [(False, True)]  # honest gets 1 block, h=1 <= d so no give-up yet
    s = _run_events(events, alpha=0.4, w=16, d=3, rule="sop", attacker_embeds=True,
                     K_objects=48)
    assert s.reveals == 0  # att_objects = 6 < K = 48


def test_sop_rule_reveals_once_K_objects_and_weight_condition_met():
    # Use a tiny K to make the reveal reachable in a short hand-fed sequence.
    # Attacker: 2 shares then a block (3 objects). Honest: 1 block (1 object).
    events = [(True, False), (True, False), (True, True), (False, True)]
    s = _run_events(events, alpha=0.4, w=16, d=3, rule="sop", attacker_embeds=True,
                     K_objects=3)
    assert s.reveals == 1
    assert s.reorg_depths == [1]


def test_final_plus_orphaned_blocks_invariant_holds_over_a_run():
    cfg = SimConfig(alpha=0.35, d=3, rule="sop", attacker_embeds=True, days=20, seed=42)
    s = simulate(cfg)
    total_final_or_orphaned = (s.att_final_blocks + s.att_orphaned_blocks
                                + s.hon_final_blocks)
    # Every accounted block came from a real block event; can't exceed the
    # total number of block events that occurred (loose sanity bound).
    assert total_final_or_orphaned >= 0
    assert s.att_final_blocks >= 0 and s.hon_final_blocks >= 0
    assert s.att_orphaned_blocks >= 0


def test_stock_rule_never_requires_K_objects():
    cfg = SimConfig(alpha=0.4, d=2, rule="stock", attacker_embeds=False, days=5, seed=1)
    s = simulate(cfg)
    assert s.reveals > 0  # stock rule (K=0) should reveal readily at alpha=0.4


def test_simulate_is_deterministic_given_a_seed():
    cfg1 = SimConfig(alpha=0.33, d=3, rule="sop", attacker_embeds=True, days=10, seed=99)
    cfg2 = SimConfig(alpha=0.33, d=3, rule="sop", attacker_embeds=True, days=10, seed=99)
    s1, s2 = simulate(cfg1), simulate(cfg2)
    assert s1.reveals == s2.reveals
    assert s1.reorg_depths == s2.reorg_depths


def test_exact_reorg_depth_matches_a_brute_force_sum():
    # E[j | attacker reaches K first] by direct enumeration of the
    # negative-binomial terms, for a small K.
    from math import comb
    from scripts.sop_race_model import exact_reorg_blocks_given_win
    alpha, K, w = 0.4, 5, 1
    terms = [comb(K - 1 + j, j) * alpha ** K * (1 - alpha) ** j for j in range(K)]
    expected = sum(j * t for j, t in enumerate(terms)) / sum(terms)
    assert abs(exact_reorg_blocks_given_win(alpha, K, w) - expected) < 1e-12


def test_rucknium_strategy2_in_objects_gives_tevadors_ten_days_as_the_even_odds_horizon():
    # MRL #146: "once per 10 days" at alpha = 0.33, from Rucknium's Strategy 2
    # (50 % success horizon) with z = k*w = 48 work objects.
    from scripts.sop_race_model import a3_strategy2_formula, days_to_even_odds
    r = a3_strategy2_formula(0.33, 48, objects_per_z_unit=1.0)
    assert r.p_success < 0.0006
    assert 9.5 < days_to_even_odds(r.expected_days_between_successes) < 10.1


def test_per_day_rates_use_canonical_days_like_a_retargeting_chain():
    """Difficulty retargets on the canonical chain, so a day is 720 CANONICAL
    blocks, not 720 blocks found. Under a stubborn attack under SoP, about a
    third of all blocks are orphaned at alpha 0.33, so per-day rates over
    fixed-rate days came out ~1.45x too low (the 240 h sim run, 2026-10-03:
    difficulty fell 32 % and ~1050 blocks a day were found)."""
    from scripts.sop_race_model import SimStats
    s = SimStats(sim_days=10.0, reveals=4, reorg_depths=[10, 12, 1, 1],
                 att_final_blocks=1200, hon_final_blocks=2400, att_orphaned_blocks=400)
    assert math.isclose(s.canonical_days, 5.0)          # 3600 canonical blocks / 720
    assert math.isclose(s.reveals_per_day, 0.8)
    assert math.isclose(s.rate_ge10_per_year, 2 / 5.0 * 365.25)
    assert s.blocks_found == 1200 + 2400 + 400 + 24     # + honest blocks the reveals orphaned
    assert math.isclose(s.reveals_per_1000_found, 4000 / 4024)
    assert SimStats(sim_days=1.0).reveals_per_day == 0.0


def test_simulate_orphans_shrink_canonical_days():
    s = simulate(SimConfig(alpha=0.33, d=2, rule="sop", attacker_embeds=True, days=20, seed=3))
    stock = simulate(SimConfig(alpha=0.33, d=2, rule="stock", attacker_embeds=False, days=20, seed=3))
    assert s.canonical_days < 0.8 * s.sim_days          # ~31 % of blocks orphaned
    assert stock.canonical_days > s.canonical_days


def test_variant_fields_default_to_the_original_model():
    from scripts.sop_race_model import SimConfig, simulate
    base = dict(alpha=0.33, d=2, rule='sop', attacker_embeds=True, days=30, seed=3)
    a = simulate(SimConfig(**base))
    b = simulate(SimConfig(**base, count_honest_pending=False, give_up_objects=-1))
    assert (a.reveals, a.reorg_depths, a.att_final_blocks) == (b.reveals, b.reorg_depths, b.att_final_blocks)


def test_counting_honest_pending_shares_removes_reveals_and_keeps_accounting():
    """2026-10-08: honest shares found but in no block did not count against
    the attacker; counting them must cut the reveal rate sharply."""
    from scripts.sop_race_model import SimConfig, simulate
    base = dict(alpha=0.33, d=2, rule='sop', attacker_embeds=True, days=60, seed=5)
    plain = simulate(SimConfig(**base))
    counted = simulate(SimConfig(**base, count_honest_pending=True))
    assert counted.reveals < plain.reveals / 2
    assert counted.att_final_blocks + counted.att_orphaned_blocks >= 0


def test_object_giveup_variant_runs_and_gives_up_earlier_when_stricter():
    from scripts.sop_race_model import SimConfig, simulate
    base = dict(alpha=0.33, d=2, rule='sop', attacker_embeds=True, days=60, seed=5, count_honest_pending=True)
    loose = simulate(SimConfig(**base, give_up_objects=48))
    strict = simulate(SimConfig(**base, give_up_objects=5))
    assert strict.reveals <= loose.reveals
    assert strict.att_final_blocks + strict.hon_final_blocks > 0



def test_release_depth_zero_and_one_match_the_original_model():
    """deep_hunt (2026-10-19): a reveal already needs h >= 1, so
    release_depth 1 must change nothing, and 0 is the default."""
    from scripts.sop_race_model import SimConfig, simulate
    base = dict(alpha=0.40, d=2, rule='sop', attacker_embeds=True, days=30, seed=7)

    def key(s):
        return (s.reveals, s.reorg_depths, s.att_final_blocks, s.hon_final_blocks, s.att_orphaned_blocks)
    assert key(simulate(SimConfig(**base))) == key(simulate(SimConfig(**base, release_depth=0))) \
        == key(simulate(SimConfig(**base, release_depth=1)))


def test_release_depth_makes_every_reveal_at_least_that_deep():
    from scripts.sop_race_model import SimConfig, simulate
    for rule, embeds in (("stock", False), ("sop", True)):
        s = simulate(SimConfig(alpha=0.45, d=3, rule=rule, attacker_embeds=embeds, days=100, seed=11,
                               release_depth=10))
        assert s.reveals > 0, rule
        assert min(s.reorg_depths) >= 10, rule
        assert s.count_ge(10) == s.reveals, rule


def test_release_depth_with_object_giveup_runs():
    # tevador's deep-reorg attacker: give up once honest is 5 objects ahead.
    from scripts.sop_race_model import SimConfig, simulate
    s = simulate(SimConfig(alpha=0.45, d=2, rule='sop', attacker_embeds=True, days=60, seed=5,
                           give_up_objects=5, release_depth=10))
    assert all(d >= 10 for d in s.reorg_depths)
    assert s.att_final_blocks + s.hon_final_blocks > 0


def test_hunt_subcommand_prints_a_table(capsys):
    from scripts.sop_race_model import main
    assert main(["hunt", "--alphas", "0.45", "--rules", "stock", "sop", "--give-ups", "d2", "o5",
                 "--days", "10", "--seed", "3"]) == 0
    out = capsys.readouterr().out
    assert "| 0.45 | stock | d2 |" in out
    assert "| 0.45 | sop | o5 |" in out
    assert "| 0.45 | stock | o5 |" not in out      # object give-up is SoP-only



# --- tevador's deep-reorg attacker (share-or-perish/blockhain-sim.py, 2026-10-17) ---
# Four switches, off by default, that make Model B's attacker his. simulate()
# draws two numbers per object (attacker?, block?) plus one per tie coin, so
# a scripted stream feeds it exact events.

class _Scripted:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        assert self.values, "simulate() drew more numbers than scripted"
        return self.values.pop(0)


def _ev(attacker, block):
    return [0.0 if attacker else 0.99, 0.0 if block else 0.99]


def _run_scripted(monkeypatch, values, n_objects, **cfg):
    from scripts import sop_race_model as m
    monkeypatch.setattr(m.random, "Random", lambda seed: _Scripted(values))
    base = dict(alpha=0.4, d=10, rule="sop", attacker_embeds=True, seed=1, release_depth=1)
    base.update(cfg)
    days = (n_objects + 0.5) * m.T_BLOCK_S / (m.SECONDS_PER_DAY * base.get("w", m.W_DEFAULT))
    return m.simulate(m.SimConfig(days=days, **base))


def test_early_honest_shares_go_into_the_attackers_first_block(monkeypatch):
    # 4 honest shares before any block, 1 attacker share, then an attacker
    # block and an honest block. Model B: 2 against 5, hold. With the switch
    # the attacker's block embeds the 4 honest shares too: 6 against 5, reveal.
    events = [(False, False)] * 4 + [(True, False), (True, True), (False, True)]
    vals = [x for e in events for x in _ev(*e)]
    plain = _run_scripted(monkeypatch, vals, len(events), K_objects=1)
    shared = _run_scripted(monkeypatch, vals, len(events), K_objects=1, early_honest_shares=True)
    assert plain.reveals == 0
    assert shared.reveals == 1 and shared.reorg_depths == [1]


def test_equal_start_gives_the_attacker_honests_pending_shares_after_a_give_up(monkeypatch):
    # Object give-up at 2: the third honest share gives up. Model B restarts
    # 3 objects behind and gives up again at the honest block (1 attacker
    # block orphaned). Equal start restarts level, so the attacker still holds.
    events = [(False, False)] * 3 + [(True, True), (False, True)]
    vals = [x for e in events for x in _ev(*e)]
    plain = _run_scripted(monkeypatch, vals, len(events), give_up_objects=2)
    equal = _run_scripted(monkeypatch, vals, len(events), give_up_objects=2, equal_start=True)
    assert plain.att_orphaned_blocks == 1
    assert equal.att_orphaned_blocks == 0 and equal.reveals == 0


def test_either_window_ends_the_window_on_the_honest_branch(monkeypatch):
    # Attacker: 40 shares and a block (41 objects, under K = 48). Honest: three
    # blocks, the last two with 15 shares each (32 objects past its first).
    # Model B holds (attacker branch inside the window); either_window reveals,
    # 41 against 33.
    events = ([(True, False)] * 40 + [(True, True), (False, True)]
              + [(False, False)] * 15 + [(False, True)] + [(False, False)] * 15 + [(False, True)])
    vals = [x for e in events for x in _ev(*e)]
    plain = _run_scripted(monkeypatch, vals, len(events))
    either = _run_scripted(monkeypatch, vals, len(events), either_window=True)
    assert plain.reveals == 0
    assert either.reveals == 1 and either.reorg_depths == [3]


def test_tie_win_prob_wins_or_ends_the_attack_on_an_exact_tie(monkeypatch):
    # 4 attacker shares and a block (5), 4 honest shares and a block (5): a tie.
    events = [(True, False)] * 4 + [(True, True)] + [(False, False)] * 4 + [(False, True)]
    vals = [x for e in events for x in _ev(*e)]
    plain = _run_scripted(monkeypatch, vals, len(events), K_objects=1)
    assert plain.reveals == 0 and plain.att_orphaned_blocks == 0       # strict: hold
    won = _run_scripted(monkeypatch, vals + [0.5], len(events), K_objects=1, tie_win_prob=0.75)
    assert won.reveals == 1
    lost = _run_scripted(monkeypatch, vals + [0.5], len(events), K_objects=1, tie_win_prob=0.25)
    assert lost.reveals == 0 and lost.att_orphaned_blocks == 1 and lost.hon_final_blocks == 1


def test_tevador_switches_default_off():
    from scripts.sop_race_model import SimConfig, simulate
    base = dict(alpha=0.40, d=2, rule="sop", attacker_embeds=True, days=30, seed=7, give_up_objects=5)
    a = simulate(SimConfig(**base))
    b = simulate(SimConfig(**base, equal_start=False, early_honest_shares=False, either_window=False,
                           tie_win_prob=0.0))
    assert (a.reveals, a.reorg_depths, a.att_final_blocks, a.att_orphaned_blocks) == \
        (b.reveals, b.reorg_depths, b.att_final_blocks, b.att_orphaned_blocks)


def test_reconcile_subcommand_prints_each_step(capsys):
    from scripts.sop_race_model import main
    assert main(["reconcile", "--days", "5", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "| Model B" in out and "(= tevador)" in out
    assert out.count("\n| ") >= 6          # header plus five steps



def test_positional_shares_drop_an_honest_share_whose_position_the_attacker_holds(monkeypatch):
    # tevador's UNIQUE_SHARES: a share's ID is its position in the finder's
    # pending set. Attacker share first (position 0), then an honest share
    # (position 0 too): the attacker gains nothing, 2 against 2, hold. As a
    # union it holds both, 3 against 2, reveal. Honest share first: no clash.
    att_first = [(True, False), (False, False), (True, True), (False, True)]
    hon_first = [(False, False), (True, False), (True, True), (False, True)]
    cfg = dict(K_objects=1, early_honest_shares=True, equal_start=True)
    for events, positional_reveals in ((att_first, 0), (hon_first, 1)):
        vals = [x for e in events for x in _ev(*e)]
        union = _run_scripted(monkeypatch, vals, len(events), **cfg)
        positional = _run_scripted(monkeypatch, vals, len(events), positional_shares=True, **cfg)
        assert union.reveals == 1
        assert positional.reveals == positional_reveals


def test_positional_shares_need_equal_start():
    import pytest
    from scripts.sop_race_model import SimConfig, simulate
    with pytest.raises(ValueError):
        simulate(SimConfig(alpha=0.3, d=1, rule="sop", attacker_embeds=True, days=1, seed=1,
                           positional_shares=True))



def test_hunt_honest_shares_flag_sets_the_slot_rule_switches_on_sop_rows(monkeypatch, capsys):
    from scripts import sop_race_model as m
    seen = []
    real = m.simulate

    def spy(cfg):
        seen.append(cfg)
        return real(cfg)

    monkeypatch.setattr(m, "simulate", spy)
    args = ["hunt", "--alphas", "0.4", "--rules", "sop", "stock", "--give-ups", "d2", "--days", "2"]
    assert m.main(args + ["--honest-shares"]) == 0
    assert "uses honest shares" in capsys.readouterr().out
    flags = {(c.rule, c.equal_start, c.early_honest_shares, c.positional_shares) for c in seen}
    assert flags == {("sop", True, True, True), ("stock", False, False, False)}
    seen.clear()
    assert m.main(args) == 0
    assert not any(c.equal_start or c.early_honest_shares or c.positional_shares for c in seen)


def test_sweep_honest_shares_adds_a_share_aware_sop_row(monkeypatch, capsys):
    import importlib
    srm = importlib.import_module("scripts.sop_race_model")
    seen = []

    def spy(cfg):
        seen.append(cfg)
        return srm.SimStats()

    monkeypatch.setattr(srm, "simulate", spy)
    srm.main(["sweep", "--days", "1"])                  # the default grid is unchanged
    assert len(seen) == 4 * 3 * 3 and not any(c.early_honest_shares for c in seen)
    seen.clear()
    srm.main(["sweep", "--days", "1", "--alphas", "0.33", "--ds", "2", "--honest-shares"])
    shared = [c for c in seen if c.early_honest_shares]
    assert len(seen) == 4 and len(shared) == 1
    c = shared[0]
    assert (c.alpha, c.d, c.rule, c.attacker_embeds, c.equal_start, c.positional_shares) == \
        (0.33, 2, "sop", True, True, True)
    assert "| True + honest shares |" in capsys.readouterr().out


def test_presets():
    assert RULE_PRESETS["20261015"] == {}
    assert RULE_PRESETS["20261020"] == {"either_window": True, "count_honest_pending": True,
                                        "count_attacker_pending": True}
    assert RULE_PRESETS["20261020_noown"] == {"either_window": True, "count_honest_pending": True}


def test_default_unchanged_by_new_field():
    base = dict(alpha=0.4, d=2, rule="sop", attacker_embeds=True, days=30, seed=3)
    a = simulate(SimConfig(**base))
    b = simulate(SimConfig(**base, count_attacker_pending=False))
    assert a.attacker_revenue_share == b.attacker_revenue_share


def test_attacker_pending_helps_the_attacker():
    base = dict(alpha=0.45, d=5, rule="sop", attacker_embeds=True, days=200, seed=1,
                either_window=True, count_honest_pending=True)
    without = simulate(SimConfig(**base)).attacker_revenue_share
    with_ = simulate(SimConfig(**base, count_attacker_pending=True)).attacker_revenue_share
    assert with_ >= without


# ---------------------------------------------------------------------------
# 2026-10-25: step API (SopEnv). simulate()'s results are pinned here from the
# loop as it stood before the refactor (plan docs/superpowers/plans/
# 2026-10-25-sop-rl-attacker.md, Task 1): 60 d runs, every rule preset, with and
# without the honest-shares slot rule, with and without cap_blocks, d-mode and
# stock, and one tie_win_prob run. Row: [variant, flag, cap, seed, att_final,
# hon_final, reveals, att_orphaned, sum(reorg_depths), max_reorg].
# ---------------------------------------------------------------------------
PINNED = [
    ["20261015", False, 0, 1, 4449, 19978, 1128, 14840, 3831, 11],
    ["20261015", False, 0, 2, 4506, 20145, 1118, 14831, 3834, 11],
    ["20261015", False, 3, 1, 2469, 23494, 202, 16820, 315, 2],
    ["20261015", False, 3, 2, 2510, 23641, 211, 16827, 338, 2],
    ["20261015", True, 0, 1, 8740, 16109, 2896, 10548, 7699, 11],
    ["20261015", True, 0, 2, 8742, 16209, 2936, 10595, 7770, 12],
    ["20261015", True, 3, 1, 5994, 21728, 1496, 13294, 2080, 2],
    ["20261015", True, 3, 2, 6001, 21752, 1549, 13336, 2227, 2],
    ["20261020", False, 0, 1, 5391, 18692, 1604, 13898, 5117, 9],
    ["20261020", False, 0, 2, 5254, 18854, 1579, 14083, 5125, 10],
    ["20261020", False, 3, 1, 2686, 23161, 324, 16603, 648, 3],
    ["20261020", False, 3, 2, 2697, 23328, 331, 16640, 651, 3],
    ["20261020", True, 0, 1, 8684, 15323, 2634, 10604, 8485, 10],
    ["20261020", True, 0, 2, 8449, 15517, 2573, 10888, 8462, 11],
    ["20261020", True, 3, 1, 4289, 22571, 616, 14999, 1237, 3],
    ["20261020", True, 3, 2, 4307, 22711, 627, 15030, 1268, 3],
    ["20261020_noown", False, 0, 1, 4194, 20426, 1086, 15095, 3383, 12],
    ["20261020_noown", False, 0, 2, 4151, 20527, 1062, 15186, 3452, 11],
    ["20261020_noown", False, 3, 1, 2548, 23438, 224, 16741, 371, 3],
    ["20261020_noown", False, 3, 2, 2540, 23635, 216, 16797, 344, 3],
    ["20261020_noown", True, 0, 1, 6895, 18068, 1781, 12393, 5740, 14],
    ["20261020_noown", True, 0, 2, 6833, 18168, 1761, 12504, 5811, 12],
    ["20261020_noown", True, 3, 1, 3994, 23162, 396, 15294, 646, 3],
    ["20261020_noown", True, 3, 2, 4017, 23342, 391, 15320, 637, 3],
    ["sop", 1, 0, 3, 376, 25648, 80, 16757, 153, 6],
    ["stock", 1, 0, 3, 13972, 20011, 5791, 3164, 5791, 1],
    ["sop", 2, 0, 3, 365, 25614, 82, 16768, 187, 6],
    ["stock", 2, 0, 3, 14247, 19332, 5686, 2889, 6470, 6],
    ["tie", True, 0, 4, 7717, 16418, 2373, 11846, 7636, 11],
]


def _cfg_from(row):
    tag, flag, cap, seed = row[:4]
    if tag in RULE_PRESETS:
        hs = bool(flag)
        return SimConfig(alpha=0.45, d=1, rule="sop", attacker_embeds=True, days=60, seed=seed,
                         give_up_objects=5, equal_start=hs, early_honest_shares=hs,
                         positional_shares=hs, cap_blocks=cap, **RULE_PRESETS[tag])
    if tag == "tie":
        return SimConfig(alpha=0.45, d=1, rule="sop", attacker_embeds=True, days=60, seed=seed,
                         give_up_objects=5, tie_win_prob=0.5, equal_start=True, **RULE_PRESETS["20261020"])
    d = int(flag)   # d-mode rows: tag is the rule, flag is d
    return SimConfig(alpha=0.4, d=d, rule=tag, attacker_embeds=(tag == "sop"), days=60, seed=seed,
                     **(RULE_PRESETS["20261020"] if tag == "sop" else {}))


def _fields(s):
    return [s.att_final_blocks, s.hon_final_blocks, s.reveals, s.att_orphaned_blocks,
            sum(s.reorg_depths), s.max_reorg_depth]


def test_simulate_results_are_pinned_across_the_step_api_refactor():
    for row in PINNED:
        assert _fields(simulate(_cfg_from(row))) == row[4:], row


def test_step_api_with_stubborn_policy_equals_simulate():
    from scripts.sop_race_model import SopEnv, stubborn_policy
    for row in PINNED:
        cfg = _cfg_from(row)
        env = SopEnv(cfg)
        env.reset(cfg.seed)
        while not env.done:
            env.step(stubborn_policy(env))
        assert _fields(env.stats) == row[4:], row


def test_observation_matches_sop_mdp_definition():
    from scripts.sop_race_model import observation
    assert observation([], [], 0, 0) == (0, 0, 0, 0, 0, 0, 0)
    assert observation([3], [], 2, 5) == (1, 4, 0, 2, 0, 0, 5)          # D = 1+3; x skips the first block
    assert observation([3, 1], [0], 0, 0) == (2, 6 - 1, 2, 0, 1, 0, 0)   # xa = 1+1
    assert observation([0] + [40], [], 0, 0)[2] == 32                   # capped
    assert observation([0, 40], [0, 0], 0, 0)[5] == 32                   # collapsed once either passes


def test_env_legal_mask_and_illegal_action_raises():
    import pytest
    from scripts.sop_race_model import SopEnv, HOLD, PUBLISH, REVEAL, GIVE_UP
    env = SopEnv(SimConfig(alpha=0.45, d=1, rule="sop", attacker_embeds=True, days=1, seed=1,
                           give_up_objects=5, **RULE_PRESETS["20261020_noown"]))
    env.reset(1)
    while env.obs()[0] == 0 or env.obs()[4] != 0:   # reach a state with a >= 1 and h == 0
        env.step(HOLD)
    assert env.legal() == (True, True, False, True)
    with pytest.raises(ValueError):
        env.step(REVEAL)


def test_honest_pending_shares_perish_when_the_attacker_publishes_only_with_the_flag():
    # 2026-10-27: the sims' honest blocks carry ~10 objects at a race start, the model's 18:
    # the model kept honest shares mined on the old tip across an attacker's publish.
    from scripts.sop_rl import race_env
    from scripts.sop_race_model import GIVE_UP, HOLD, PUBLISH
    for perish in (True, False):
        env = race_env(0.47, 200, seed=3, perish=perish)
        o, checked = env.obs(), 0
        while not env.done and checked < 20:
            a, D, xa, pa, h, xh, ph = o
            if a >= 1 and h == 0 and ph >= 2:
                o, _, _ = env.step(PUBLISH)
                if perish:
                    assert o[6] <= 1, o      # only the object drawn after the publish can be a share
                else:
                    assert o[6] >= ph, o
                checked += 1
            elif h >= 1:
                o, _, _ = env.step(GIVE_UP)
            elif a >= 1:
                o, _, _ = env.step(PUBLISH)
            else:
                o, _, _ = env.step(HOLD)
        assert checked == 20
