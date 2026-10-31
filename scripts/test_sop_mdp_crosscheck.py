"""Tests for sop_mdp_crosscheck.py (needs scipy and pymdptoolbox: run in the
cross-check venv on a lane box, e.g. ~/mdpcheck/venv/bin/python -m pytest)."""
import pytest

pytest.importorskip("scipy")
pytest.importorskip("mdptoolbox")

import sop_mdp as M  # noqa: E402
import sop_mdp_crosscheck as X  # noqa: E402


def test_btc_honest_policy_earns_alpha():
    rho, _ = X.hand_share(*X.btc_tables(0.3, 0.5, 20, policy=X.honest_action), False, 1e-7)
    assert rho == pytest.approx(0.3, abs=1e-6)


def test_btc_sm1_matches_eyal_sirer_closed_form():
    # T large enough that the near-balanced lead walk almost never reaches the cap
    rho, _ = X.hand_share(*X.btc_tables(0.3, 0.5, 200, policy=X.sm1_action), False, 1e-7)
    assert rho == pytest.approx(X.es_sm1(0.3, 0.5), abs=2e-6)


def test_lp_solves_a_fixed_policy_chain():
    # HiGHS called a single-action chain infeasible while the flow rows were
    # linearly dependent (they always sum to zero); the LP drops one
    succ, att, hon, probs = X.btc_tables(0.35, 0.0, 30, policy=X.sm1_action)
    s, ra, rh, legal = X.fill_illegal(succ, att, hon)
    rho, _ = X.hand_share(succ, att, hon, probs, False, 1e-7)
    assert X.lp_share(s, ra, rh, legal, probs)[0] == pytest.approx(rho, abs=2e-6)


def test_btc_optimum_agrees_across_solvers():
    succ, att, hon, probs = X.btc_tables(0.35, 0.0, 30)
    rho, _ = X.hand_share(succ, att, hon, probs, True, 1e-6)
    out = X.library_checks(succ, att, hon, probs, 1e-6, 1.0)
    assert out["toolbox_rvi"] == pytest.approx(rho, abs=2e-6)
    assert out["highs_lp"] == pytest.approx(rho, abs=2e-6)


def test_compact_tables_agree_across_solvers_on_a_small_window():
    try:
        X.set_window(4, 12)
        caps = M.Caps(3, 3, 16, 4, 6)
        keys = M.enumerate_keys(caps, False)
        for bound in ("lower", "upper"):
            C = M.Compact(keys, caps, False, bound=bound)
            rho, _ = X.compact_share(C, 0.45, True, 1e-6)
            out = X.library_checks(*X.compact_tables(C, 0.45), 1e-6, 1.0)
            assert out["toolbox_rvi"] == pytest.approx(rho, abs=2e-6), bound
            assert out["highs_lp"] == pytest.approx(rho, abs=2e-6), bound
    finally:
        X.set_window(16, 48)
