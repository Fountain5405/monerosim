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


def test_key_of_clips_and_bins():
    assert RL.key_of((1, 300, 5, 60, 2, 7, 1)) == (1, 128, 5, 48, 2, 7, 1)
    assert RL.key_of((1, -300, 5, 0, 2, 7, 60)) == (1, -128, 5, 0, 2, 7, 48)
    assert RL.key_of((1, 7, 0, 0, 0, 0, 0), d_bin=2) == (1, 3, 0, 0, 0, 0, 0)


def test_train_finds_publish_at_cap_when_window_is_unreachable():
    # 3/3/40/12/12 cannot reach the window (docs/20261025_sop_mdp_notes.md): the exact
    # optimum is honest mining, 0.4500, reached by publishing at a == 3 and giving up otherwise.
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps)
    env.reset(1)
    q = RL.train(env, 0.45, rho=0.45, budget=2_000_000, seed=1)
    pol = RL.TablePolicy(q)
    env2 = RL.MdpEnv(0.45, caps)
    env2.reset(2)
    r = RL.rollout(env2, pol, 2_000_000)
    assert r["share"] > 0.43


def test_table_policy_falls_back_and_respects_legality():
    q = RL.QTable()
    pol = RL.TablePolicy(q)
    a, stored = pol((0, -1, 0, 0, 1, 0, 0), (True, False, False, True))
    assert (a, stored) == (M.GIVE_UP, False)
    k = q.key((1, 2, 0, 0, 0, 0, 0))
    q.seed_row(k, [0.0, 1.0, 0.0, 0.0], legal=(True, True, False, True), tried=(True, True, False, True))
    assert pol((1, 2, 0, 0, 0, 0, 0), (True, True, False, True)) == (M.PUBLISH, True)
    assert pol((1, 2, 0, 0, 0, 0, 0), (True, False, False, True))[0] == M.HOLD   # publish illegal -> next best
    # an action never tried must not win on its 0.0: only give_up was tried, at -0.2
    q.seed_row(q.key((1, 3, 0, 0, 0, 0, 0)), [0.0, 0.0, 0.0, -0.2], legal=(True, True, False, True),
               tried=(False, False, False, True))
    assert pol((1, 3, 0, 0, 0, 0, 0), (True, True, False, True)) == (M.GIVE_UP, True)


@pytest.mark.slow
def test_train_matches_exact_solver_on_a_small_window_reaching_game():
    # Caps(3,3,32,16,16): (3-1)*(1+16) = 34 >= 32, so reveals are possible; exact solve ~minutes.
    caps = M.Caps(3, 3, 32, 16, 16)
    keys = M.enumerate_keys(caps, False)
    rho_exact, _ = M.Compact(keys, caps, False).share(0.45, optimise=True, lo=0.05, hi=0.8, tol=1e-3)
    env = RL.MdpEnv(0.45, caps)
    env.reset(1)
    q = RL.train(env, 0.45, rho=rho_exact, budget=40_000_000, seed=1)   # at the exact rho the gain must be ~0
    env2 = RL.MdpEnv(0.45, caps)
    env2.reset(2)
    r = RL.rollout(env2, RL.TablePolicy(q), 20_000_000)
    assert abs(r["share"] - rho_exact) < 0.01, (r["share"], rho_exact)


def test_share_search_terminates_and_reports_best_when_nothing_learns():
    # a budget of 0 steps leaves Q empty: every rollout is sim_stubborn through the MDP game
    caps = M.Caps(3, 3, 40, 12, 12)
    out = RL.share_search(lambda seed: RL.MdpEnv(0.45, caps), 0.45, budget=0, eval_objects=200_000, seeds=(1,))
    assert out["converged"] in (True, False) and len(out["history"]) <= 12
    assert 0.0 <= out["share"] <= 1.0


def test_export_only_stores_differences_from_sim_stubborn_and_round_trips(tmp_path):
    q = RL.QTable()
    s_same = (1, -3, 0, 0, 1, 0, 3)           # sim_stubborn gives up; table agrees
    s_diff = (1, 2, M.WINDOW, 0, 1, M.WINDOW, 1)     # sim_stubborn reveals; table says hold
    legal = (True, False, True, True)
    for s, row in ((s_same, [0, 0, 0, 1.0]), (s_diff, [1.0, 0, 0, 0])):
        q.seed_row(q.key(s), row, legal=legal, tried=legal)
    n = RL.export_policy(q, str(tmp_path / "p.json.gz"), {"alpha": 0.45, "env": "race", "share": 0.3})
    assert n == 1
    pol, meta = RL.load_policy(str(tmp_path / "p.json.gz"))
    assert pol == {s_diff: M.HOLD} and meta["alpha"] == 0.45
    fp = RL.FilePolicy(str(tmp_path / "p.json.gz"))
    assert fp(s_diff, (True, False, True, True)) == (M.HOLD, True)
    assert fp(s_same, (True, False, False, True)) == (M.GIVE_UP, False)


def test_cli_train_and_eval_smoke(tmp_path):
    import subprocess
    import sys
    out = tmp_path / "p.json.gz"
    subprocess.run([sys.executable, "scripts/sop_rl.py", "train", "--alpha", "0.45", "--env", "mdp",
                    "--a-max", "3", "--h-max", "3", "--d-max", "40", "--p-max", "12", "--deficit", "12",
                    "--budget", "200000", "--days-eval", "2", "--out", str(out)], check=True)
    r = subprocess.run([sys.executable, "scripts/sop_rl.py", "eval", "--policy", str(out), "--alpha", "0.45",
                        "--env", "mdp", "--a-max", "3", "--h-max", "3", "--d-max", "40", "--p-max", "12",
                        "--deficit", "12", "--days", "2", "--seeds", "1"], check=True, capture_output=True, text=True)
    assert "share" in r.stdout and "sim_stubborn" in r.stdout
