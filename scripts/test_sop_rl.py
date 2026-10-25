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
    assert RL.key_of((1, 7, 0, 5, 0, 0, 9), p_bin=2) == (1, 7, 0, 2, 0, 0, 4)
    assert RL.key_of((1, -7, 0, 60, 0, 0, 1), d_bin=2, p_bin=4) == (1, -3, 0, 12, 0, 0, 0)


class _ChainEnv:
    """s0 (settled) -hold-> s1 -hold-> s2 -hold-> s3 -reveal, fa=3-> s0 ...:
    one race whose only reward arrives at its last step."""
    S0, S1, S2, S3 = (0, 0, 0, 0, 0, 0, 0), (1, 1, 0, 0, 1, 0, 0), (2, 2, 0, 0, 1, 0, 0), (3, 3, 32, 0, 1, 32, 0)

    def __init__(self):
        self.s, self.done = self.S0, False

    def obs(self):
        return self.s

    def legal(self):
        return (False, False, True, False) if self.s == self.S3 else (True, False, False, False)

    def step(self, a):
        nxt = {self.S0: self.S1, self.S1: self.S2, self.S2: self.S3, self.S3: self.S0}
        fa = 3 if self.s == self.S3 else 0
        self.s = nxt[self.s]
        return self.s, fa, 0


@pytest.mark.parametrize("race_returns, expected", [(False, 0.0), (True, 3.0)])
def test_race_returns_carry_a_reveal_back_to_the_first_hold_in_one_pass(race_returns, expected):
    # one-step bootstrapping leaves the first hold at 0 after one race (its successor was untried
    # when it was updated); the per-race backward return credits the reveal's 3 blocks to every
    # hold of the race in that same pass (rho 0, vref 0: the target is the raw return).
    q = RL.train(_ChainEnv(), 0.5, rho=0.0, budget=4, seed=1, eps_start=0.0, eps_end=0.0,
                 race_returns=race_returns)
    assert q.q[q.key(_ChainEnv.S1)][RL.HOLD] == pytest.approx(expected)
    assert q.q[q.key(_ChainEnv.S3)][RL.REVEAL] == pytest.approx(3.0)


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


def test_greedy_needs_n_min_updates_before_an_action_can_win():
    # 2026-10-25: the greedy policies were patchworks of actions whose values rested on one
    # sample (one-step: honest drift; race returns: a collapse to 0.129). With n_min, an action
    # competes only after n_min updates; elsewhere the policy and the bootstrap fall back.
    q = RL.QTable(n_min=3)
    k = (1, 2, 0, 0, 1, 0, 0)
    legal = (True, False, False, True)
    q.seed_row(k, [0.1, 0.0, 0.0, 0.9], legal=legal, tried=legal, n=[5, 0, 0, 1])
    assert q.greedy_tried(k, legal) == M.HOLD                     # give_up's 0.9 rests on one update
    assert q.value_tried(k, legal, default=-7.0) == pytest.approx(0.1)
    q.n[k][M.GIVE_UP] = 3
    assert q.greedy_tried(k, legal) == M.GIVE_UP
    k2 = (2, 3, 0, 0, 1, 0, 0)
    q.seed_row(k2, [0.4, 0.0, 0.0, 0.0], legal=legal, tried=(True, False, False, False), n=[2, 0, 0, 0])
    assert q.greedy_tried(k2, legal) == -1                         # nothing confident: the policy falls back
    assert q.value_tried(k2, legal, default=-7.0) == -7.0          # and so does the bootstrap ...
    assert q.value_tried(k2, legal, default=-7.0, fallback=M.HOLD) == pytest.approx(0.4)   # ... unless the fallback action was updated
    assert RL.QTable().greedy_tried(k, legal) == -1 and RL._copy_table(q).n[k] == [5, 0, 0, 3]


def test_train_follows_the_behaviour_policy_where_nothing_is_confident():
    # beta 0: every non-random step takes the greedy branch; with an unreachable n_min nothing is
    # ever confident, so those steps play sim_stubborn, and the random steps (eps 0.2) give other
    # actions updates without ever making them greedy
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps)
    env.reset(1)
    q = RL.train(env, 0.45, rho=0.3, budget=200_000, seed=1, behaviour=RL.sim_stubborn, beta_start=0.0,
                 beta_end=0.0, eps_start=0.2, eps_end=0.2, n_min=10**9)
    assert len(q) > 100 and q.n_min == 10**9
    assert all(q.greedy_tried(k, q.legal_of(k)) == -1 for k in q.q)
    assert sum(sum(1 for c in q.n[k] if c > 0) > 1 for k in q.q) > 50       # alternatives were tried ...
    stub = sum(q.n[k][RL.legal_fallback(RL.sim_stubborn(k), q.legal_of(k))] for k in q.q)
    assert stub > 0.7 * sum(sum(q.n[k]) for k in q.q)                     # ... but stubborn's action dominates


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
@pytest.mark.parametrize("race_returns", [False, True])
def test_train_matches_exact_solver_on_a_small_window_reaching_game(race_returns):
    # Caps(3,3,32,16,16): (3-1)*(1+16) = 34 >= 32, so reveals are possible; exact solve ~minutes.
    caps = M.Caps(3, 3, 32, 16, 16)
    keys = M.enumerate_keys(caps, False)
    rho_exact, _ = M.Compact(keys, caps, False).share(0.45, optimise=True, lo=0.05, hi=0.8, tol=1e-3)
    env = RL.MdpEnv(0.45, caps)
    env.reset(1)
    q = RL.train(env, 0.45, rho=rho_exact, budget=40_000_000, seed=1,   # at the exact rho the gain must be ~0
                 race_returns=race_returns)
    env2 = RL.MdpEnv(0.45, caps)
    env2.reset(2)
    r = RL.rollout(env2, RL.TablePolicy(q), 20_000_000)
    assert abs(r["share"] - rho_exact) < 0.01, (r["share"], rho_exact)


def test_share_search_trains_each_step_from_the_best_table_so_far(monkeypatch):
    # a probe at a rho above the optimum degenerates (settling always loses, holding scores 0):
    # its table must not seed the next step; the best table so far does (2026-10-25 21:51Z:
    # race+bins at rho 0.575 -> share 0.311, table carried into the 0.5125 step)
    seen, shares = [], iter([0.60, 0.30, 0.55, 0.40])

    def fake_train(env, alpha, rho, budget, q=None, **kw):
        seen.append(sorted(q.q) if q is not None else None)
        t = RL.QTable()
        t.q[(len(seen),)] = [0.0, 0.0, 0.0, 0.0]
        return t

    monkeypatch.setattr(RL, "train", fake_train)
    monkeypatch.setattr(RL, "rollout", lambda env, policy, n: {"share": next(shares), "reveals": 7, "mean_reorg": 2.5,
                                                               "max_reorg": 9, "decisions": 100, "stored_hits": 40})

    class E:
        def reset(self, seed):
            pass

    import io
    log = io.StringIO()
    out = RL.share_search(lambda seed: E(), 0.5, budget=1, lo=0.5, hi=0.6, tol=0.01, eval_objects=1, seeds=(1,),
                          log=log)
    assert seen == [[], [(1,)], [(1,)], [(1,)]]     # steps 3 and 4 start from step 1's table (0.60)
    assert out["share"] == 0.60 and sorted(out["q"].q) == [(1,)]
    # the log line says what the greedy rollout did, not only its share
    assert "reveals=7" in log.getvalue() and "reorg=2.50/9" in log.getvalue() and "stored=0.400" in log.getvalue()


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
    q3 = RL.QTable(n_min=2)        # hold's 1.0 at s_diff rests on one update: not a deviation yet
    q3.seed_row(q3.key(s_diff), [1.0, 0, 0, 0], legal=legal, tried=legal, n=[1, 0, 3, 3])
    assert RL.export_policy(q3, str(tmp_path / "p3.json.gz"), {"alpha": 0.45, "env": "race", "share": 0.3}) == 0


def test_export_records_bins_and_file_policy_keys_through_them(tmp_path):
    q = RL.QTable(d_bin=2, p_bin=2)
    s = (1, 5, M.WINDOW, 5, 1, M.WINDOW, 1)       # sim_stubborn reveals; its bin says hold
    legal = (True, False, True, True)
    assert q.key(s) == (1, 2, M.WINDOW, 2, 1, M.WINDOW, 0)
    q.seed_row(q.key(s), [1.0, 0, 0, 0], legal=legal, tried=legal)
    path = str(tmp_path / "p.json.gz")
    assert RL.export_policy(q, path, {"alpha": 0.5, "env": "race", "share": 0.6}) == 1
    _, meta = RL.load_policy(path)
    assert meta["key_clip"] == {"d": 128, "p": 48, "d_bin": 2, "p_bin": 2}
    fp = RL.FilePolicy(path)
    assert fp((1, 4, M.WINDOW, 4, 1, M.WINDOW, 0), legal) == (M.HOLD, True)   # same bin, other observation
    assert fp((1, 6, M.WINDOW, 6, 1, M.WINDOW, 0), legal) == (M.REVEAL, False)   # next bin: fallback


def test_cli_train_and_eval_smoke(tmp_path):
    import subprocess
    import sys
    out = tmp_path / "p.json.gz"
    subprocess.run([sys.executable, "scripts/sop_rl.py", "train", "--alpha", "0.45", "--env", "mdp",
                    "--a-max", "3", "--h-max", "3", "--d-max", "40", "--p-max", "12", "--deficit", "12",
                    "--budget", "200000", "--days-eval", "2", "--d-bin", "2", "--p-bin", "2",
                    "--returns", "race", "--n-min", "4", "--lr", "0.1", "--out", str(out)], check=True)
    _, meta = RL.load_policy(str(out))
    assert meta["key_clip"]["p_bin"] == 2 and meta["returns"] == "race" and meta["n_min"] == 4 and meta["lr"] == 0.1
    r = subprocess.run([sys.executable, "scripts/sop_rl.py", "eval", "--policy", str(out), "--alpha", "0.45",
                        "--env", "mdp", "--a-max", "3", "--h-max", "3", "--d-max", "40", "--p-max", "12",
                        "--deficit", "12", "--days", "2", "--seeds", "1"], check=True, capture_output=True, text=True)
    assert "share" in r.stdout and "sim_stubborn" in r.stdout


@pytest.mark.parametrize("race_returns", [False, True])
def test_train_with_stubborn_behaviour_learns_stubborns_own_values(race_returns):
    """Off-policy warm start: with behaviour = sim_stubborn at full weight the
    tried actions are stubborn's, so the greedy policy IS stubborn and scores
    what stubborn scores (the learner's values along deep hold chains are
    then grounded in trajectories that actually reach reveals)."""
    caps = M.Caps(3, 3, 40, 12, 12)
    env = RL.MdpEnv(0.45, caps)
    env.reset(1)
    q = RL.train(env, 0.45, rho=0.3, budget=300_000, seed=1, behaviour=RL.sim_stubborn,
                 beta_start=1.0, beta_end=1.0, eps_start=0.0, eps_end=0.0, race_returns=race_returns)
    for k in list(q.q)[:200]:
        legal = q.legal_of(k)
        if q.visits[k] > 0:
            assert q.greedy_tried(k, legal) == RL.legal_fallback(RL.sim_stubborn(k), legal)
    e1 = RL.MdpEnv(0.45, caps)
    e1.reset(2)
    r_learned = RL.rollout(e1, RL.TablePolicy(q), 500_000)
    e2 = RL.MdpEnv(0.45, caps)
    e2.reset(2)
    r_stub = RL.rollout(e2, RL.stubborn_fn, 500_000)
    assert abs(r_learned["share"] - r_stub["share"]) < 0.01
