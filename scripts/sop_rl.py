#!/usr/bin/env python3
"""A learned attacker for Share-or-Perish (MRL #146, 2026-10-20 rule).

Design: docs/superpowers/specs/2026-10-25-sop-rl-attacker-design.md. The
hand-written window_stubborn attacker is a floor on what SoP concedes; the
exact solver (scripts/sop_mdp.py) cannot reach faithful block caps. This
module trains a tabular policy by reinforcement learning against the race
model (scripts/sop_race_model.py SopEnv, the sims' noown settings) over the
exact-MDP observation (a, D, xa, pa, h, xh, ph), and exports it as a diff
against the sim's own stubborn rule so agents/selfish_strategy.py can run it.

Environments share one small interface: reset(seed) -> obs, step(action) ->
(obs, fa, fh), legal() -> 4 bools, obs(). MdpEnv wraps sop_mdp's scalar
transitions (the game the exact solver solves, for checking the learner);
race_env builds the SopEnv the real policies are trained on.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

if __name__ == "__main__":   # run as `python scripts/sop_rl.py`: make `scripts.` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import sop_mdp as M
from scripts.sop_policy import HOLD, PUBLISH, REVEAL, GIVE_UP, Obs, key_of, load_policy, sim_stubborn  # noqa: F401 (re-exported)
from scripts.sop_race_model import FAR_CAP, RULE_PRESETS, SimConfig, SopEnv

assert (HOLD, PUBLISH, REVEAL, GIVE_UP) == (M.HOLD, M.PUBLISH, M.REVEAL, M.GIVE_UP)


class MdpEnv:
    """The exact solver's game as an environment: the state IS the
    observation; after each object the legal actions are exactly those of
    sop_mdp.actions (so a forced action at a cap is the only legal one)."""

    def __init__(self, alpha: float, caps: M.Caps, own_pending: bool = False):
        self.alpha, self.caps, self.own = alpha, caps, own_pending
        self.rng = random.Random(0)
        self.s: Obs = M.START
        self._choices: Dict[int, Tuple[Obs, int, int]] = {}
        self.objects = 0
        self.att_final = self.hon_final = self.reveals = 0
        self.reorg_depths: List[int] = []
        self.done = False

    def reset(self, seed: int) -> Obs:
        self.rng = random.Random(seed)
        self.s = M.START
        self.objects = 0
        self.att_final = self.hon_final = self.reveals = 0
        self.reorg_depths = []
        self.done = False
        self._draw()
        return self.s

    def _draw(self) -> None:
        is_att = self.rng.random() < self.alpha
        is_blk = self.rng.random() < 1.0 / M.W_SHARES
        self.s = M.event(self.s, is_att, is_blk, self.caps)
        self.objects += 1
        self._choices = {act: (s2, fa, fh) for act, s2, fa, fh in M.actions(self.s, self.caps, self.own)}

    def obs(self) -> Obs:
        return self.s

    def legal(self) -> Tuple[bool, bool, bool, bool]:
        c = self._choices
        return (HOLD in c, PUBLISH in c, REVEAL in c, GIVE_UP in c)

    def step(self, action: int) -> Tuple[Obs, int, int]:
        if action not in self._choices:
            raise ValueError(f"illegal action {M.ACTION_NAMES[action]} at {self.s}")
        s2, fa, fh = self._choices[action]
        if action == REVEAL:
            self.reveals += 1
            self.reorg_depths.append(self.s[4])
        self.att_final += fa
        self.hon_final += fh
        self.s = s2
        self._draw()
        return self.s, fa, fh


def race_env(alpha: float, days: float, seed: int, cap_blocks: int = 0) -> SopEnv:
    """The training environment: the sims' noown attacker settings
    (rule 20261020_noown, honest shares via the slot rule, o5 give-up for
    stubborn_policy only), far-capped on the objects deficit. The |D| cap is
    left off: equal_start copies a long honest share gap into the attacker's
    pending and the stubborn baseline then exceeds |D| 200 within 2000 d;
    the Q-table key clips D instead. Returned already reset with `seed`."""
    cfg = SimConfig(alpha=alpha, d=1, rule="sop", attacker_embeds=True, days=days, seed=seed,
                    give_up_objects=5, equal_start=True, early_honest_shares=True,
                    positional_shares=True, cap_blocks=cap_blocks, deficit_cap=FAR_CAP,
                    **RULE_PRESETS["20261020_noown"])
    env = SopEnv(cfg)
    env.reset(seed)
    return env


Policy = Callable[[Obs, Tuple[bool, bool, bool, bool]], object]


def rollout(env, policy: Policy, n_objects: int) -> dict:
    """Drive `env` with `policy` for n_objects decisions (or until the env
    is done). A policy returns an action, or (action, stored) where stored
    says its key was in the table (TablePolicy / FilePolicy)."""
    att = hon = decisions = stored_hits = 0
    o = env.obs()
    for _ in range(n_objects):
        if env.done:
            break
        r = policy(o, env.legal())
        if isinstance(r, tuple):
            a, st = r
        else:
            a, st = r, False
        o, fa, fh = env.step(a)
        att += fa
        hon += fh
        decisions += 1
        stored_hits += bool(st)
    src = getattr(env, "stats", env)
    depths = src.reorg_depths
    return {"share": att / (att + hon) if att + hon else 0.0, "att": att, "hon": hon,
            "reveals": src.reveals, "mean_reorg": sum(depths) / len(depths) if depths else 0.0,
            "max_reorg": max(depths) if depths else 0, "decisions": decisions,
            "stored_hits": stored_hits}


# ---------------------------------------------------------------------------
# Tabular relative-value Q-learning
# ---------------------------------------------------------------------------

class QTable:
    """Q rows (4 floats, Python lists: the inner loop is per object) keyed by
    key_of(obs), created on first visit; `visits` counts updates per key."""

    def __init__(self, d_clip: int = 128, p_clip: int = 48, d_bin: int = 1, p_bin: int = 1, n_min: int = 1):
        self.d_clip, self.p_clip, self.d_bin, self.p_bin = d_clip, p_clip, d_bin, p_bin
        self.n_min = n_min                   # updates an action needs at a key before it can be the greedy one
        self.q: Dict[Obs, List[float]] = {}
        self.n: Dict[Obs, List[int]] = {}    # updates per action
        self.visits: Dict[Obs, int] = {}
        self.legal: Dict[Obs, int] = {}      # bits 0-3: legal actions as first seen; bits 4-7: actions tried

    def key(self, obs: Obs) -> Obs:
        return key_of(obs, self.d_clip, self.p_clip, self.d_bin, self.p_bin)

    def row(self, k: Obs, legal=None) -> List[float]:
        r = self.q.get(k)
        if r is None:
            r = [0.0, 0.0, 0.0, 0.0]
            self.q[k] = r
            self.n[k] = [0, 0, 0, 0]
            self.visits[k] = 0
            if legal is not None:
                self.legal[k] = sum(1 << i for i in range(4) if legal[i])
        return r

    def seed_row(self, k: Obs, row: List[float], legal, tried, n=None) -> None:
        """Install a row with its legal and tried masks and per-action update
        counts (tests, warm starts); tried actions count as updated once."""
        self.q[k] = list(row)
        self.n[k] = list(n) if n is not None else [1 if t else 0 for t in tried]
        self.visits[k] = max(self.visits.get(k, 0), 1)
        self.legal[k] = sum(1 << i for i in range(4) if legal[i]) | sum(1 << (4 + i) for i in range(4) if tried[i])

    def legal_of(self, k: Obs):
        m = self.legal.get(k, 0b1111)
        return tuple(bool(m >> i & 1) for i in range(4))

    def tried_of(self, k: Obs):
        m = self.legal.get(k, 0) >> 4
        return tuple(bool(m >> i & 1) for i in range(4))

    def value(self, k: Obs) -> float:
        """max over the key's tried legal actions (0 for an unknown key)."""
        a = self.greedy_tried(k, self.legal_of(k))
        return self.q[k][a] if a >= 0 else 0.0

    def greedy_tried(self, k: Obs, legal) -> int:
        """Greedy among the legal actions updated at least n_min times; -1 if
        none. An untried action's 0.0 must not outrank a tried action's value,
        and (n_min > 1, 2026-10-25) one lucky sample must not outrank a
        well-estimated one: the greedy policies were patchworks of such
        samples (one-step targets drifted to honest, race returns collapsed
        to 0.129 at alpha 0.50)."""
        r = self.q.get(k)
        if r is None:
            return -1
        cnt, m = self.n[k], self.n_min
        mask = tuple(legal[i] and cnt[i] >= m for i in range(4))
        return self.argmax(r, mask) if any(mask) else -1

    def value_tried(self, k: Obs, legal, default: float, fallback: int = -1) -> float:
        """Bootstrap value of a successor: max over its confident legal
        actions; else the `fallback` action's value if that was updated at
        least once (the behaviour policy's action there, which is what the
        greedy policy plays where nothing is confident); else `default` (the
        reference value). Maximising over untried zeros instead made every
        hold chain look like 0 at its frontier (2026-10-25: Q(hold) -0.17
        where the Monte Carlo return was -0.76)."""
        a = self.greedy_tried(k, legal)
        if a >= 0:
            return self.q[k][a]
        if fallback >= 0 and legal[fallback]:
            cnt = self.n.get(k)
            if cnt is not None and cnt[fallback] > 0:
                return self.q[k][fallback]
        return default

    @staticmethod
    def argmax(row: List[float], legal) -> int:
        """Greedy action among the legal ones; ties go to the lowest index."""
        best, best_v = -1, None
        for i in range(4):
            if legal[i] and (best_v is None or row[i] > best_v):
                best, best_v = i, row[i]
        return best

    def greedy(self, obs: Obs, legal) -> int:
        return self.argmax(self.q.get(self.key(obs)) or [0.0, 0.0, 0.0, 0.0], legal)

    def __len__(self) -> int:
        return len(self.q)


def legal_fallback(a: int, legal) -> int:
    """A fallback action forced into the legal set: hold if allowed, else the
    first legal action (at a cap only the forced ones are)."""
    if legal[a]:
        return a
    return HOLD if legal[HOLD] else next(i for i in range(4) if legal[i])



REF_REFRESH = 50_000   # steps between re-picking the reference key (the most visited one)
MAX_RACE = 4096        # race_returns: a race longer than this (objects) is flushed with a bootstrap


def train(env, alpha: float, rho: float, budget: int, q: Optional[QTable] = None,
          lr: float = 0.02, eps_start: float = 0.3, eps_end: float = 0.02, seed: int = 1,
          lr_min: float = 0.002, behaviour: Optional[Callable[[Obs], int]] = None,
          beta_start: float = 1.0, beta_end: float = 0.0, race_returns: bool = False,
          n_min: int = 1) -> QTable:
    """Relative-value (RVI) Q-learning for the average reward
    r = fa - rho * (fa + fh):  Q(s,a) += a_n * (r - V(ref) + max_legal Q(s') - Q(s,a)),
    V(ref) = max_legal Q(ref). The step size decays per key with its visit
    count n: a_n = max(lr_min, 1 / (1 + lr * n)) (the first update takes the
    full target, so a new row's zeros never linger). The reference key is
    the most visited one so far, re-picked every REF_REFRESH steps (START
    itself is almost never visited: a settled fork leaves pending shares on
    one side, so a fixed START anchor let the values drift). Epsilon decays
    linearly over the budget; illegal actions are never chosen nor maximised
    over; the greedy choice is over actions already tried. Warm-startable
    through `q`.

    `behaviour` (2026-10-25): an off-policy warm start. With probability
    beta (linear from beta_start to beta_end over the budget) the step takes
    behaviour(obs) (legality-guarded) instead of the eps-greedy choice.
    Pure eps-greedy converged to honest mining even at alpha 0.50, where
    sim_stubborn earns 0.57: it never holds a branch long enough to see a
    deep reveal pay. Q-learning is off-policy, so learning along stubborn's
    trajectories grounds those values; the greedy policy can then deviate.

    `race_returns` (2026-10-25): the steps of a race (any state with a
    branch: a > 0 or h > 0) are buffered until the fork settles (a == h == 0)
    and then updated backward with the race's full return, cut at
    exploratory actions as in Watkins' Q(lambda): a step whose action was
    not its key's greedy one makes the earlier steps bootstrap from that
    key's max instead of the sampled return. One-step targets valued every
    hold of a race off its (untried) successor, i.e. off the reference
    value, so a reveal's payoff reached the race's first hold only after as
    many revisits as the race is long; over millions of keys seen a few
    times each, the first warm-started trainings (20:45Z) still ended at
    honest mining at every alpha. Settled steps flush at once (one-step).

    `n_min` (2026-10-25, the table's confidence gate): an action is greedy
    at a key only after n_min updates there; where nothing is confident the
    training step and the bootstrap use the behaviour policy's action, so
    the learned policy is the behaviour policy plus the deviations the data
    supports (with n_min 1 this is the plain tried-only rule)."""
    q = q if q is not None else QTable(n_min=n_min)
    rng = random.Random(seed)
    o = env.obs()
    legal = env.legal()
    k = q.key(o)
    row = q.row(k, legal)
    kref = max(q.visits, key=q.visits.get) if q.visits else k
    de = (eps_end - eps_start) / max(budget, 1)
    eps = eps_start
    dbeta = (beta_end - beta_start) / max(budget, 1)
    beta = beta_start if behaviour is not None else 0.0
    buf: List[tuple] = []   # race_returns: (row, k, a, r, k2, legal2, exploratory, fb2) since the last settled state

    def flush() -> None:
        vref = q.value(kref)
        G = 0.0
        cut = True            # the race's last step bootstraps from its settled successor
        for row_t, k_t, a_t, r_t, k2_t, legal2_t, expl_t, fb_t in reversed(buf):
            if cut:
                G = q.value_tried(k2_t, legal2_t, vref, fb_t)
            G = r_t - vref + G
            n = q.visits[k_t]
            st = 1.0 / (1.0 + lr * n)
            if st < lr_min:
                st = lr_min
            row_t[a_t] += st * (G - row_t[a_t])
            q.visits[k_t] = n + 1
            q.n[k_t][a_t] += 1
            q.legal[k_t] |= 1 << (4 + a_t)
            cut = expl_t
        buf.clear()

    for t in range(budget):
        if env.done:
            break
        g = -2    # the greedy action at k, when computed (race_returns cuts the return at a deviation)
        if behaviour is not None and rng.random() < beta:
            a = legal_fallback(behaviour(o), legal)
        elif rng.random() < eps:
            choices = [i for i in range(4) if legal[i]]
            a = choices[int(rng.random() * len(choices))]
        else:
            g = a = q.greedy_tried(k, legal)
            if a < 0:
                if behaviour is not None:    # nothing confident here: play the behaviour policy
                    a = legal_fallback(behaviour(o), legal)
                else:
                    choices = [i for i in range(4) if legal[i]]
                    a = choices[int(rng.random() * len(choices))]
        o2, fa, fh = env.step(a)
        r = fa - rho * (fa + fh)
        legal2 = env.legal()
        k2 = q.key(o2)
        row2 = q.row(k2, legal2)
        fb2 = legal_fallback(behaviour(o2), legal2) if behaviour is not None else -1
        if race_returns:
            if g == -2:
                g = q.greedy_tried(k, legal)
            buf.append((row, k, a, r, k2, legal2, g >= 0 and a != g, fb2))
            if (o2[0] == 0 and o2[4] == 0) or len(buf) >= MAX_RACE:
                flush()
        else:
            vref = q.value(kref)
            m2 = q.value_tried(k2, legal2, vref, fb2)
            n = q.visits[k]
            step = 1.0 / (1.0 + lr * n)
            if step < lr_min:
                step = lr_min
            row[a] += step * (r - vref + m2 - row[a])
            q.visits[k] = n + 1
            q.n[k][a] += 1
            q.legal[k] |= 1 << (4 + a)
        o, legal, k, row = o2, legal2, k2, row2
        eps += de
        beta += dbeta
        if t % REF_REFRESH == REF_REFRESH - 1:
            kref = max(q.visits, key=q.visits.get)
    if buf:
        flush()
    return q


def stubborn_fn(obs: Obs, legal) -> Tuple[int, bool]:
    """sim_stubborn as a rollout policy (never stored)."""
    return legal_fallback(sim_stubborn(obs), legal), False


class TablePolicy:
    """Greedy over a QTable where the key was visited; `fallback(obs)`
    (sim_stubborn by default) elsewhere. Returns (action, stored)."""

    def __init__(self, q: QTable, fallback: Callable[[Obs], int] = sim_stubborn):
        self.q, self.fallback = q, fallback

    def __call__(self, obs: Obs, legal) -> Tuple[int, bool]:
        k = self.q.key(obs)
        a = self.q.greedy_tried(k, legal)
        if a >= 0:
            return a, True
        return legal_fallback(self.fallback(obs), legal), False


# ---------------------------------------------------------------------------
# Share bisection, policy files, CLI
# ---------------------------------------------------------------------------

def _copy_table(q: QTable) -> QTable:
    c = QTable(q.d_clip, q.p_clip, q.d_bin, q.p_bin, q.n_min)
    c.q = {k: list(v) for k, v in q.q.items()}
    c.n = {k: list(v) for k, v in q.n.items()}
    c.visits = dict(q.visits)
    c.legal = dict(q.legal)
    return c


def share_search(make_env: Callable[[int], object], alpha: float, budget: int, lo: float = 0.05,
                 hi: float = 0.80, tol: float = 1e-3, eval_objects: int = 23_040_000,
                 seeds: Tuple[int, ...] = (11, 12, 13), log=None,
                 make_train_env: Optional[Callable[[int], object]] = None, max_steps: int = 12,
                 behaviour: Optional[Callable[[Obs], int]] = None, beta_start: float = 1.0,
                 beta_end: float = 0.0, race_returns: bool = False, d_bin: int = 1, p_bin: int = 1,
                 n_min: int = 1, lr: float = 0.02) -> dict:
    """Bisection on rho (Sapirshtein-Sompolinsky-Zohar): train at mid
    (warm-started from the BEST table so far), roll the greedy policy out on
    `eval_objects` objects per seed with fresh envs from make_env(seed), and
    move lo up if the mean share exceeds mid (gain > 0), else hi down. Stops
    at hi - lo <= tol or after max_steps. Returns rho, the best rollout share
    seen with its table, converged, and the (rho, share, states) history.
    A probe at a rho above the optimum degenerates (every settlement loses,
    holding scores 0, so the greedy policy holds until forced: 0.311 at rho
    0.575, alpha 0.50, 2026-10-25); its table is dropped, not carried."""
    make_train_env = make_train_env or make_env
    q: Optional[QTable] = QTable(d_bin=d_bin, p_bin=p_bin, n_min=n_min)
    best_share, best_q = -1.0, None
    history: List[Tuple[float, float, int]] = []
    step = 0
    while hi - lo > tol and step < max_steps:
        mid = 0.5 * (lo + hi)
        t = time.time()
        env = make_train_env(1000 + step)
        env.reset(1000 + step)
        q = train(env, alpha, mid, budget, q=q, seed=1000 + step, behaviour=behaviour,
                  beta_start=beta_start, beta_end=beta_end, race_returns=race_returns, n_min=n_min, lr=lr)
        rows = []
        for sd in seeds:
            e = make_env(sd)
            e.reset(sd)
            rows.append(rollout(e, TablePolicy(q), eval_objects))
        n = len(rows)
        share = sum(r["share"] for r in rows) / n
        history.append((mid, share, len(q)))
        if log:   # what the greedy rollout did, not only its share (per seed means; stored = table hits)
            print(f"  rho={mid:.5f} share={share:.5f} states={len(q):,} "
                  f"reveals={sum(r.get('reveals', 0) for r in rows) / n:.0f} "
                  f"reorg={sum(r.get('mean_reorg', 0.0) for r in rows) / n:.2f}/{max(r.get('max_reorg', 0) for r in rows)} "
                  f"stored={sum(r.get('stored_hits', 0) for r in rows) / max(1, sum(r.get('decisions', 0) for r in rows)):.3f} "
                  f"[{time.time() - t:.0f}s]", file=log, flush=True)
        if share > best_share:
            best_share, best_q = share, _copy_table(q)
        else:
            q = None                   # drop the failed probe's table before copying (peak: two tables)
            q = _copy_table(best_q)
        if share > mid:
            lo = mid
        else:
            hi = mid
        step += 1
    if best_q is None:   # budget 0 and no step: nothing learned
        best_q = q if q is not None else QTable()
    return {"rho": 0.5 * (lo + hi), "share": max(best_share, 0.0), "q": best_q,
            "converged": hi - lo <= tol, "history": history}


def export_policy(q: QTable, path: str, meta: dict) -> int:
    """Write the greedy policy as gzip JSON, keeping only visited keys whose
    greedy action (over tried, legal actions) differs from sim_stubborn(key);
    the sim falls back to sim_stubborn elsewhere. Returns the entry count."""
    entries = {}
    for k in q.q:
        a = q.greedy_tried(k, q.legal_of(k))
        if a >= 0 and a != sim_stubborn(k):
            entries[",".join(str(x) for x in k)] = M.ACTION_NAMES[a]
    doc = {"meta": meta, "key_clip": {"d": q.d_clip, "p": q.p_clip, "d_bin": q.d_bin, "p_bin": q.p_bin},
           "fallback": "sim_stubborn", "policy": entries}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with gzip.open(path, "wt") as f:
        json.dump(doc, f)
    return len(entries)


class FilePolicy:
    """A policy file as a callable (obs, legal) -> (action, stored)."""

    def __init__(self, path: str, fallback: Callable[[Obs], int] = sim_stubborn):
        self.policy, self.meta = load_policy(path)
        c = self.meta["key_clip"]
        self.d_clip, self.p_clip = int(c["d"]), int(c["p"])
        self.d_bin, self.p_bin = int(c.get("d_bin", 1)), int(c.get("p_bin", 1))
        self.fallback = fallback

    def key(self, obs: Obs) -> Obs:
        return key_of(obs, self.d_clip, self.p_clip, self.d_bin, self.p_bin)

    def __call__(self, obs: Obs, legal) -> Tuple[int, bool]:
        a = self.policy.get(self.key(obs))
        if a is not None and legal[a]:
            return a, True
        return legal_fallback(self.fallback(obs), legal), False


def _add_env_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--alpha", type=float, required=True)
    p.add_argument("--env", choices=["race", "mdp"], default="race")
    p.add_argument("--a-max", type=int, default=4)
    p.add_argument("--h-max", type=int, default=4)
    p.add_argument("--d-max", type=int, default=64)
    p.add_argument("--p-max", type=int, default=24)
    p.add_argument("--deficit", type=int, default=24)
    p.add_argument("--own-pending", choices=["ignore", "count"], default="ignore")
    p.add_argument("--cap-blocks", type=int, default=0)


def _env_factory(args, days: float):
    if args.env == "mdp":
        caps = M.Caps(args.a_max, args.h_max, args.d_max, args.p_max, args.deficit)
        return lambda seed: MdpEnv(args.alpha, caps, args.own_pending == "count")
    return lambda seed: race_env(args.alpha, days, seed, args.cap_blocks)


def _report(name: str, policy, make_env, days: float, seeds: List[int]) -> float:
    n = int(days * 720 * M.W_SHARES)
    rows = []
    for sd in seeds:
        e = make_env(sd)
        e.reset(sd)
        rows.append(rollout(e, policy, n))
    mean = sum(r["share"] for r in rows) / len(rows)
    print(f"{name}: share " + " ".join(f"{r['share']:.4f}" for r in rows) + f"  mean {mean:.4f}  "
          f"reveals {sum(r['reveals'] for r in rows) / len(rows):.0f}/run  mean reorg "
          f"{sum(r['mean_reorg'] for r in rows) / len(rows):.2f}  max reorg {max(r['max_reorg'] for r in rows)}  "
          f"stored {sum(r['stored_hits'] for r in rows) / max(1, sum(r['decisions'] for r in rows)):.3f}")
    return mean


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("train", help="bisection on the share with Q-learning at each rho; writes a policy file")
    _add_env_args(p)
    p.add_argument("--budget", type=int, default=200_000_000, help="Q-learning steps per rho")
    p.add_argument("--out", required=True)
    p.add_argument("--lo", type=float, default=0.05)
    p.add_argument("--hi", type=float, default=0.80)
    p.add_argument("--tol", type=float, default=1e-3)
    p.add_argument("--days-eval", type=float, default=2000.0, help="rollout length per seed at each rho")
    p.add_argument("--eval-seeds", type=int, nargs="+", default=[11, 12, 13])
    p.add_argument("--behaviour", choices=["none", "stubborn"], default="stubborn",
                   help="off-policy warm start: follow sim_stubborn with weight beta (default on)")
    p.add_argument("--beta-start", type=float, default=1.0)
    p.add_argument("--beta-end", type=float, default=0.0)
    p.add_argument("--returns", choices=["step", "race"], default="step",
                   help="one-step targets, or each race's full return applied backward when it settles")
    p.add_argument("--d-bin", type=int, default=1, help="bin D (objects) in the table key")
    p.add_argument("--p-bin", type=int, default=1, help="bin the pending counts in the table key")
    p.add_argument("--n-min", type=int, default=1,
                   help="updates an action needs at a key before it can be the greedy one (else sim_stubborn)")
    p.add_argument("--lr", type=float, default=0.02, help="step size 1/(1 + lr * n) per key, floor 0.002")
    p = sub.add_parser("eval", help="score a policy file (or 'none' for sim_stubborn alone)")
    _add_env_args(p)
    p.add_argument("--policy", required=True)
    p.add_argument("--days", type=float, default=2000.0)
    p.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    args = ap.parse_args(argv)

    if args.cmd == "train":
        t = time.time()
        make_eval = _env_factory(args, args.days_eval)
        make_train = _env_factory(args, args.budget / (720 * M.W_SHARES) + 1)
        out = share_search(make_eval, args.alpha, args.budget, lo=args.lo, hi=args.hi, tol=args.tol,
                           eval_objects=int(args.days_eval * 720 * M.W_SHARES), seeds=tuple(args.eval_seeds),
                           log=sys.stderr, make_train_env=make_train,
                           behaviour=sim_stubborn if args.behaviour == "stubborn" else None,
                           beta_start=args.beta_start, beta_end=args.beta_end,
                           race_returns=args.returns == "race", d_bin=args.d_bin, p_bin=args.p_bin,
                           n_min=args.n_min, lr=args.lr)
        meta = {"alpha": args.alpha, "env": args.env, "share": out["share"], "rho": out["rho"],
                "converged": out["converged"], "history": out["history"], "budget": args.budget,
                "behaviour": args.behaviour, "beta": [args.beta_start, args.beta_end],
                "returns": args.returns, "bins": [args.d_bin, args.p_bin], "n_min": args.n_min, "lr": args.lr,
                "caps": vars(args) if args.env == "mdp" else {"cap_blocks": args.cap_blocks},
                "trained": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds": round(time.time() - t)}
        n = export_policy(out["q"], args.out, meta)
        print(f"alpha={args.alpha} env={args.env}: share {out['share']:.4f} (rho {out['rho']:.4f}, "
              f"converged={out['converged']}); {len(out['q']):,} states, {n:,} entries differ from "
              f"sim_stubborn -> {args.out}  [{time.time() - t:.0f}s]")
        return 0

    make_env = _env_factory(args, args.days)
    if args.policy != "none":
        _report(f"policy {os.path.basename(args.policy)}", FilePolicy(args.policy), make_env, args.days, args.seeds)
    _report("sim_stubborn", stubborn_fn, make_env, args.days, args.seeds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
