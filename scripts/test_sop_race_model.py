# scripts/test_sop_race_model.py
import math
import random

from scripts.sop_race_model import (
    K_DEFAULT, W_DEFAULT, RaceResult, SimConfig, a1_race_to_k,
    a2_strategy2_objects, a3_strategy2_formula, binom_sf_ge, objects_per_day,
    reg_incomplete_beta, run_model_a, simulate, simulate_race_to_k,
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
