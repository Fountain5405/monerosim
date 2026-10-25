"""Tests for scripts/sop_rl.py (the learned SoP attacker; plan
docs/superpowers/plans/2026-10-25-sop-rl-attacker.md)."""
import random

import pytest

from scripts import sop_mdp as M
from scripts import sop_rl as RL


def test_mdp_env_follows_event_then_actions():
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps)
    o = env.reset(7)
    rng = random.Random(7)
    s = M.event(M.START, rng.random() < 0.45, rng.random() < 1 / M.W_SHARES, caps)
    assert o == s
    legal = env.legal()
    assert legal == tuple(any(a == k for a, *_ in M.actions(s, caps, False)) for k in range(4))


def test_mdp_env_stubborn_rollout_matches_scalar_monte_carlo():
    # the 2026-10-25 figure: 0.1334 (VI) / 0.1343 (MC) at 3/3/40/12/12, count/count
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps, own_pending=True)
    env.reset(1)
    pol = lambda o, legal: M.stubborn_action(o, caps, 5, True, True)[0]   # noqa: E731
    r = RL.rollout(env, pol, int(500 * 720 * M.W_SHARES))
    assert abs(r["share"] - 0.134) < 0.006


def test_sim_stubborn_rule():
    W = M.WINDOW
    assert RL.sim_stubborn((0, -1, 0, 0, 1, 0, 0)) == M.GIVE_UP
    assert RL.sim_stubborn((1, 2, 0, 0, 0, 0, 30)) == M.HOLD          # h == 0: hold even 28 objects behind
    assert RL.sim_stubborn((1, 2, W, 0, 1, W, 1)) == M.REVEAL
    assert RL.sim_stubborn((1, 2, W, 0, 1, W, 2)) == M.HOLD           # D == ph: not accepted
    assert RL.sim_stubborn((1, -3, 0, 0, 1, 0, 3)) == M.GIVE_UP       # deficit 6 > 5


def test_race_env_stubborn_reproduces_the_calibration_number():
    env = RL.race_env(0.45, days=2000, seed=1)
    from scripts.sop_race_model import stubborn_policy
    r = RL.rollout(env, lambda o, legal: stubborn_policy(env), env.n_objects)
    assert abs(r["share"] - 0.2806) < 0.003     # hunt --honest-shares, 20261020_noown, o5, seed 1
