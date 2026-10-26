"""Tests for scripts/sop_attacker_search.py and sop_policy.param_stubborn: the
parametric stubborn family searched in the race model (2026-10-26, the
experiment after the learned attacker's ladder stopped at step 3)."""
import random

import pytest

from scripts import sop_policy as P
from scripts import sop_attacker_search as S

W = P.WINDOW


def test_param_stubborn_defaults_are_sim_stubborn():
    rng = random.Random(3)
    for _ in range(3000):
        obs = (rng.randint(0, 6), rng.randint(-60, 60), rng.choice([0, 5, 31, W]), rng.randint(0, 40),
               rng.randint(0, 6), rng.choice([0, 5, 31, W]), rng.randint(0, 40))
        assert P.param_stubborn(obs) == P.sim_stubborn(obs), obs


def test_publish_lead_releases_an_unopposed_lead():
    assert P.param_stubborn((2, 30, 16, 0, 0, 0, 3), L=2) == P.PUBLISH
    assert P.param_stubborn((1, 10, 0, 0, 0, 0, 3), L=2) == P.HOLD
    assert P.param_stubborn((2, 30, 16, 0, 0, 0, 3)) == P.HOLD          # L 0: never publish, as the sim's rule


def test_reveal_margin_and_depth_delay_the_reveal():
    obs = (2, 6, W, 0, 1, W, 3)          # accepted: D 6 > ph 3 (margin 3), past the window, h 1
    assert P.param_stubborn(obs) == P.REVEAL
    assert P.param_stubborn(obs, M=3) == P.REVEAL
    assert P.param_stubborn(obs, M=4) == P.HOLD
    assert P.param_stubborn(obs, R=2) == P.HOLD
    assert P.param_stubborn((2, 6, W, 0, 2, W, 3), R=2) == P.REVEAL


def test_holding_without_blocks_keeps_the_pending_shares_in_play():
    assert P.param_stubborn((0, -2, 0, 4, 1, 0, 1)) == P.GIVE_UP          # the sim's rule: a == 0 with an honest block
    assert P.param_stubborn((0, -2, 0, 4, 1, 0, 1), Z=1) == P.HOLD         # deficit 2 + 1 - 4 = -1 <= G
    assert P.param_stubborn((0, -9, 0, 0, 1, 0, 0), Z=1) == P.GIVE_UP      # deficit 9 > G 5


def test_block_deficit_give_up():
    assert P.param_stubborn((1, 1, 0, 0, 3, 0, 0), B=2) == P.GIVE_UP       # h - a = 2 >= B
    assert P.param_stubborn((1, 1, 0, 0, 3, 0, 0)) == P.HOLD               # off by default; objects deficit -1


def test_grid_and_crossing_helpers():
    combos = S.parse_grid("G=3,5 Z=0,1")
    assert len(combos) == 4 and {"G": 5, "Z": 1} in combos
    assert S.parse_grid("") == [{}]
    assert S.crossing([(0.45, 0.30), (0.48, 0.47), (0.50, 0.60)]) == pytest.approx(0.48 + 0.02 * (0.01 / 0.11))
    assert S.crossing([(0.45, 0.30), (0.48, 0.40)]) is None


def test_evaluate_runs_the_race_model_with_the_family():
    r = S.evaluate({"G": 5, "Z": 1}, alpha=0.5, days=2, seed=1)
    assert 0.0 <= r["share"] <= 1.0 and r["reveals"] >= 0
    assert r["knobs"] == {"G": 5, "Z": 1} and r["alpha"] == 0.5 and r["seed"] == 1 and r["days"] == 2
    base = S.evaluate({}, alpha=0.5, days=2, seed=1)
    assert base["share"] != r["share"]       # Z changes the play within 2 days


def test_run_key_identifies_a_result_line():
    assert S.run_key({"Z": 1, "G": 5}, 0.5, 1) == S.run_key({"G": 5, "Z": 1}, 0.5, 1)
    assert S.run_key({"G": 5}, 0.5, 1) != S.run_key({"G": 5}, 0.5, 2)
