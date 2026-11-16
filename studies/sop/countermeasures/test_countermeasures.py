"""Tests for the countermeasure MDPs (Nakamoto so far).

Needs scipy, networkx and pymdptoolbox-roi (skipped without them); run on a
lane box with the BLAS threads capped.
"""
import math
import random

import pytest

pytest.importorskip("scipy")
pytest.importorskip("networkx")
pytest.importorskip("mdptoolbox")

from studies.sop.countermeasures import solve as S  # noqa: E402
from studies.sop.countermeasures.nakamoto import NakamotoModel  # noqa: E402
from studies.sop.countermeasures.reorgs import (MAJORITY, MINORITY, TaggedTransitions,  # noqa: E402
                                                reorg_profile, simulate_profile)
from studies.sop.countermeasures.vendor.blockchain_mdps import BitcoinModel, PTOSolver  # noqa: E402
from studies.sop.countermeasures.vendor.blockchain_mdps.base.blockchain_mdps.sparse_blockchain_mdp import (  # noqa: E402
    SparseBlockchainMDP)


def pto(model):
    """Optimal policy and PTO's value V/H (approximate: horizon bias of order 1/H)."""
    policy, value, _, _ = PTOSolver(model, expected_horizon=10 ** 5).calc_opt_policy(epsilon=1e-6, max_iter=200000)
    return tuple(int(x) for x in policy), value


def test_tagged_transitions_accumulate_on_merge():
    t = TaggedTransitions()
    t.add((1,), probability=0.25, reorgs=[(MAJORITY, 2)])
    t.add((1,), probability=0.5, allow_merging=True, reorgs=[(MAJORITY, 2), (MINORITY, 0)])
    assert t.probabilities[(1,)] == 0.75
    assert t.reorgs[(1,)] == {(MAJORITY, 2): 0.75}


def test_transitions_match_pto_and_tags_fit():
    ours = NakamotoModel(0.3, 0.5, 6)
    theirs = BitcoinModel(0.3, 0.5, 6)
    # pto compares enum members with `is`: map states and actions by index
    def keys(d):
        return {ours.state_space.element_to_index(s): v for s, v in d.items()}

    for i in range(ours.state_space.size):
        state = ours.state_space.index_to_element(i)
        for j in range(ours.action_space.size):
            action = ours.action_space.index_to_element(j)
            a = ours.get_state_transitions(state, action)
            b = theirs.get_state_transitions(theirs.state_space.index_to_element(i),
                                             theirs.action_space.index_to_element(j))
            assert keys(a.probabilities) == {theirs.state_space.element_to_index(s): v
                                             for s, v in b.probabilities.items()}
            assert list(a.rewards.values()) == list(b.rewards.values())
            assert list(a.difficulty_contributions.values()) == list(b.difficulty_contributions.values())
            assert math.isclose(sum(a.probabilities.values()), 1, abs_tol=1e-12)
            for next_state, tags in a.reorgs.items():
                assert sum(tags.values()) <= a.probabilities[next_state] * 2 + 1e-12
                assert all(depth > 0 for _, depth in tags)


def test_revenue_reproduces_ssz_and_profile_agrees():
    model = NakamotoModel(0.35, 0.0, 40)
    policy, value = pto(model)
    revenue = SparseBlockchainMDP(model).calc_policy_revenue(policy)
    assert revenue == pytest.approx(0.370754, abs=2e-6)  # SSZ 0.37077 at large caps
    assert value == pytest.approx(revenue, abs=5e-5)
    profile = reorg_profile(model, policy)
    assert profile["revenue"] == pytest.approx(revenue, abs=1e-9)
    assert profile[f"{MINORITY}_reorgs_per_block"] == 0.0  # gamma 0
    assert profile[f"{MAJORITY}_reorgs_per_block"] > 0


def test_honest_policy_has_no_reorgs():
    model = NakamotoModel(0.3, 0.5, 20)
    profile = reorg_profile(model, model.build_honest_policy())
    assert profile["revenue"] == pytest.approx(0.3, abs=1e-9)
    assert profile[f"{MAJORITY}_reorgs_per_block"] == 0.0
    assert profile[f"{MINORITY}_reorgs_per_block"] == 0.0


def explicit_sm1(alpha, gamma, max_fork, steps, seed):
    """SM1 on explicit block lists, independent of the MDP's tags.

    Depths come from comparing the tips honest miners hold before and after
    each event; blocks are counted when they become final for everyone.
    """
    rng = random.Random(seed)
    next_id = [0]

    def block():
        next_id[0] += 1
        return next_id[0]

    final = 0              # main-chain blocks final for everyone (behind the fork point)
    attacker_final = 0
    A, H = [], []          # attacker's and honest branch since the fork point
    active = False          # attacker published len(H) blocks; the gamma share follows A[:len(H)]
    relevant = False        # the last block was honest
    rates = {MAJORITY: {}, MINORITY: {}}

    def reorg(kind, old, new):
        common = 0
        while common < min(len(old), len(new)) and old[common] == new[common]:
            common += 1
        depth = len(old) - common
        if depth > 0:
            rates[kind][depth] = rates[kind].get(depth, 0) + 1

    for _ in range(steps):
        a, h = len(A), len(H)
        # pto's build_sm1_policy, in terms of (a, h, fork)
        if h > a:
            final += h
            A, H, active, relevant = [], [], False, False
            continue
        if (h == a - 1 and a >= 2) or a == max_fork:
            reorg(MAJORITY, H, A[:h + 1])
            final += h + 1
            attacker_final += h + 1
            A, H, active, relevant = A[h + 1:], [], False, False
            continue
        if h == 1 and a == 1 and relevant and not active:
            active = True
            continue
        # wait: one block is mined
        if rng.random() < alpha:
            A.append(block())
            relevant = False
            continue
        x = block()
        if active and rng.random() < gamma:
            # an honest miner on the attacker's published branch: it wins
            reorg(MAJORITY, H, A[:h] + [x])
            final += h
            attacker_final += h
            A, H, active, relevant = A[h:], [x], False, True
        else:
            if active:
                reorg(MINORITY, A[:h], H + [x])
            H.append(x)
            active, relevant = False, True
    return attacker_final / final, {k: {d: n / final for d, n in v.items()} for k, v in rates.items()}


def test_sm1_profile_matches_explicit_chain_simulation():
    alpha, gamma, cap = 0.35, 0.5, 60
    model = NakamotoModel(alpha, gamma, cap)
    profile = reorg_profile(model, model.build_sm1_policy())
    revenue, rates = explicit_sm1(alpha, gamma, cap, 600_000, seed=7)
    assert revenue == pytest.approx(profile["revenue"], rel=0.02)
    for kind in (MAJORITY, MINORITY):
        for depth in (1, 2):
            # SM1 matches only at (1, 1): no minority reorg of depth 2
            expected = profile[f"{kind}_depth_rates"].get(depth, 0.0)
            assert rates[kind].get(depth, 0) == pytest.approx(expected, rel=0.05)
    assert profile[f"{MAJORITY}_depth_rates"][2] > 0


def test_monte_carlo_matches_stationary_profile():
    model = NakamotoModel(0.35, 0.5, 40)
    policy, _ = pto(model)
    exact = reorg_profile(model, policy)
    mc = simulate_profile(model, policy, 400_000, seed=3)
    assert mc["revenue"] == pytest.approx(exact["revenue"], rel=0.02)
    for kind in (MAJORITY, MINORITY):
        assert mc[f"{kind}_reorgs_per_block"] == pytest.approx(exact[f"{kind}_reorgs_per_block"], rel=0.05)


def test_disruption_objective_value_is_the_deep_reorg_rate():
    model = NakamotoModel(0.35, 0.0, 40, objective="disruption", min_depth=3)
    assert model.get_honest_revenue() == 0.0
    policy, value = pto(model)
    profile = reorg_profile(model, policy)
    assert value > 0
    assert profile[f"{MAJORITY}_deep_reorgs_per_block"] == pytest.approx(value, rel=0.02)
    # the revenue-optimal policy causes fewer deep reorgs
    revenue_model = NakamotoModel(0.35, 0.0, 40)
    revenue_policy, _ = pto(revenue_model)
    shallow = reorg_profile(NakamotoModel(0.35, 0.0, 40, min_depth=3), revenue_policy)
    assert shallow[f"{MAJORITY}_deep_reorgs_per_block"] < value


def test_depth_weight_counts_depth():
    model = NakamotoModel(0.3, 0.0, 10, objective="disruption", min_depth=2, weight="depth")
    t = model.get_state_transitions((4, 3, model.Fork.Relevant), model.Action.Override)
    assert list(t.rewards.values()) == [3.0]
    t = model.get_state_transitions((4, 1, model.Fork.Relevant), model.Action.Override)
    assert list(t.rewards.values()) == [0.0]


def test_cli_emits_one_json_line(capsys):
    assert S.main(["nakamoto", "--alpha", "0.3", "--gamma", "0", "--max-fork", "10", "--policy", "sm1",
                   "--mc-steps", "1000"]) == 0
    import json
    out = json.loads(capsys.readouterr().out)
    assert out["policy"] == "sm1" and out["states"] == 3 * 11 ** 2 + 1
    assert "mc" in out and "profile" in out


def test_direct_and_eigs_stationary_agree_on_nakamoto():
    model = NakamotoModel(0.35, 0.5, 40)
    policy, _ = pto(model)
    direct = reorg_profile(model, policy, method="direct")
    eigs = reorg_profile(model, policy, method="eigs")
    assert direct["revenue"] == pytest.approx(eigs["revenue"], abs=1e-9)
    for kind in (MAJORITY, MINORITY):
        assert direct[f"{kind}_reorgs_per_block"] == pytest.approx(eigs[f"{kind}_reorgs_per_block"], rel=1e-6)
