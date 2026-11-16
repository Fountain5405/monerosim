"""Tests for the exact average-reward policy iteration (howard.py) against PTO where PTO is reliable."""
import pytest

pytest.importorskip("scipy")
pytest.importorskip("networkx")
pytest.importorskip("mdptoolbox")

from studies.sop.countermeasures.howard import solve_average  # noqa: E402
from studies.sop.countermeasures.nakamoto import NakamotoModel  # noqa: E402
from studies.sop.countermeasures.reorgs import MAJORITY, reorg_profile  # noqa: E402
from studies.sop.countermeasures.sop_walk import SoPWalkModel  # noqa: E402
from studies.sop.countermeasures.vendor.blockchain_mdps import PTOSolver  # noqa: E402
from studies.sop.countermeasures.vendor.blockchain_mdps.base.blockchain_mdps.sparse_blockchain_mdp import (  # noqa: E402
    SparseBlockchainMDP)


def pto(model):
    policy, value, _, _ = PTOSolver(model, expected_horizon=10 ** 5).calc_opt_policy(epsilon=1e-7, max_iter=400000)
    return tuple(int(x) for x in policy), value


def test_howard_reproduces_ssz_revenue():
    model = NakamotoModel(0.35, 0.0, 40)
    policy, g, _ = solve_average(model)
    assert g == pytest.approx(0.370754, abs=2e-6)
    assert SparseBlockchainMDP(model).calc_policy_revenue(policy) == pytest.approx(g, abs=1e-9)


@pytest.mark.parametrize("alpha,gamma", [(0.35, 0.0), (0.40, 0.5)])
def test_howard_matches_pto_on_nakamoto_disruption(alpha, gamma):
    model = NakamotoModel(alpha, gamma, 40, objective="disruption", min_depth=3, normalization="time")
    _, value = pto(model)
    policy, g, _ = solve_average(model)
    assert g >= value * (1 - 1e-4)
    assert g == pytest.approx(value, rel=1e-3)
    assert reorg_profile(model, policy)[f"{MAJORITY}_deep_reorgs_per_block"] == pytest.approx(g, rel=1e-6)


def test_howard_on_the_sop_walk_is_at_least_pto_and_self_consistent():
    model = SoPWalkModel(0.40, min_depth=4, x_min=-30, x_max=30, p_max=24)
    pto_policy, value = pto(model)
    policy, g, _ = solve_average(model, policy0=pto_policy)
    exact_pto = reorg_profile(model, pto_policy)[f"{MAJORITY}_deep_reorgs_per_block"]
    assert g >= exact_pto * (1 - 1e-9)
    assert reorg_profile(model, policy)[f"{MAJORITY}_deep_reorgs_per_block"] == pytest.approx(g, rel=1e-6)
