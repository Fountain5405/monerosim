"""Tests for the SoP walk model (disruption) and the Nakamoto time normalization.

Needs scipy, networkx and pymdptoolbox-roi (skipped without them); run on a
lane box with the BLAS threads capped.
"""
import math
import random

import pytest

pytest.importorskip("scipy")
pytest.importorskip("networkx")
pytest.importorskip("mdptoolbox")

from studies.sop.countermeasures.nakamoto import NakamotoModel  # noqa: E402
from studies.sop.countermeasures.reorgs import MAJORITY, reorg_profile, simulate_profile  # noqa: E402
from studies.sop.countermeasures.sop_walk import SoPWalkModel, exact_rate, to_walk_state  # noqa: E402
from studies.sop.countermeasures.vendor.blockchain_mdps import PTOSolver  # noqa: E402
from studies.sop.scripts import sop_mdp as M  # noqa: E402


def pto(model):
    policy, value, _, _ = PTOSolver(model, expected_horizon=10 ** 5).calc_opt_policy(epsilon=1e-7, max_iter=400000)
    return tuple(int(x) for x in policy), value


def test_lead_moves_one_per_object_and_acceptance_is_lead_minus_pending():
    """The walk model's derivation, checked on sop_mdp's own rules."""
    rng = random.Random(5)
    caps = M.Caps(a_max=10 ** 6, h_max=10 ** 6, d_max=10 ** 6, p_max=10 ** 6, deficit=10 ** 6)
    s = M.START
    checked = 0
    for _ in range(200_000):
        is_att = rng.random() < 0.42
        is_blk = rng.random() < 1 / M.W_SHARES
        a, D, xa, pa, h, xh, ph = s
        before = D + pa - ph
        s = M.event(s, is_att, is_blk, caps)
        a, D, xa, pa, h, xh, ph = s
        assert D + pa - ph == before + (1 if is_att else -1)
        if M.past_window(s) and a >= 1:
            assert M.accepted(s, False) == (D + pa - ph - pa > 0)
            checked += 1
        if rng.random() < 0.002 and (a or h):
            s = rng.choice([M.do_reveal, M.do_give_up])(s)[0] if h else M.do_publish(s)[0]
    assert checked > 1000


def test_transitions_sum_to_one_and_illegal_actions_end():
    model = SoPWalkModel(0.4, w=4, min_depth=3, x_min=-6, x_max=6, p_max=4)
    for i in range(model.state_space.size):
        state = model.state_space.index_to_element(i)
        for j in range(model.action_space.size):
            action = model.action_space.index_to_element(j)
            t = model.get_state_transitions(state, action)
            assert math.isclose(sum(t.probabilities.values()), 1, abs_tol=1e-12)
            if state != model.final_state and not model.legal(state, action):
                assert list(t.probabilities) == [model.final_state]


def test_solved_policy_profile_and_monte_carlo_agree():
    model = SoPWalkModel(0.45, min_depth=3, x_min=-40, x_max=40, p_max=32)
    policy, value = pto(model)
    profile = reorg_profile(model, policy)
    assert value > 0
    assert profile[f"{MAJORITY}_deep_reorgs_per_block"] == pytest.approx(value, rel=0.02)
    mc = simulate_profile(model, policy, 2_000_000, seed=2)
    assert mc[f"{MAJORITY}_deep_reorgs_per_block"] == pytest.approx(value, rel=0.1)


def test_exact_game_rate_does_not_exceed_the_walk_optimum():
    model = SoPWalkModel(0.45, min_depth=3, x_min=-40, x_max=40, p_max=32)
    policy, value = pto(model)
    exact = exact_rate(model, policy, 3_000_000, seed=4)
    assert exact["deep_reveals"] > 100
    assert exact["deep_per_block_time"] <= value * 1.05   # 5 % for Monte Carlo noise


def test_walk_state_mapping():
    model = SoPWalkModel(0.4, min_depth=11, x_min=-80, x_max=80, p_max=64)
    assert to_walk_state(model, (2, 5, 32, 3, 14, 32, 1)) == (11, 1, 7, 3)
    assert to_walk_state(model, (0, -200, 0, 0, 1, 0, 0)) == (1, 0, -80, 0)


def test_nakamoto_time_normalization():
    honest = NakamotoModel(0.3, 0.0, 20, normalization="time")
    assert reorg_profile(honest, honest.build_honest_policy())["revenue"] == pytest.approx(0.3, abs=1e-9)
    main = NakamotoModel(0.35, 0.0, 40, objective="disruption", min_depth=3)
    timed = NakamotoModel(0.35, 0.0, 40, objective="disruption", min_depth=3, normalization="time")
    policy, _ = pto(main)
    per_block = reorg_profile(main, policy)[f"{MAJORITY}_deep_reorgs_per_block"]
    per_time = reorg_profile(timed, policy)[f"{MAJORITY}_deep_reorgs_per_block"]
    # the disruption attacker discards most of its blocks: fewer main-chain blocks than blocks mined
    assert 0 < per_time < per_block
