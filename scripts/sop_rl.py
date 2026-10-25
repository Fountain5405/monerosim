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

import random
from typing import Callable, Dict, List, Optional, Tuple

from scripts import sop_mdp as M
from scripts.sop_race_model import FAR_CAP, RULE_PRESETS, SimConfig, SopEnv

Obs = Tuple[int, int, int, int, int, int, int]
HOLD, PUBLISH, REVEAL, GIVE_UP = M.HOLD, M.PUBLISH, M.REVEAL, M.GIVE_UP


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


def sim_stubborn(obs: Obs, G: int = 5) -> int:
    """agents/selfish_strategy.py::_window_stubborn_decision (noown, objects
    give-up G) restated over the observation. It is the fallback for unseen
    states and the reference a policy file is a diff against. It differs
    from sop_race_model.stubborn_policy: it gives up at a == 0 with any
    honest block, and never gives up on objects while h == 0."""
    a, D, xa, pa, h, xh, ph = obs
    if a == 0 and h > 0:
        return GIVE_UP
    if h == 0:
        return HOLD
    if -D + ph - pa > G:
        return GIVE_UP
    if max(xa, xh) >= M.WINDOW and D > ph:
        return REVEAL
    return HOLD


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

def key_of(obs: Obs, d_clip: int = 128, p_clip: int = 48, d_bin: int = 1) -> Obs:
    """The Q-table key: the observation with |D| clipped (then binned,
    truncating toward zero) and the pending counts clipped. The game itself
    is never clipped; only the table's view of it."""
    a, D, xa, pa, h, xh, ph = obs
    D = max(-d_clip, min(d_clip, D))
    if d_bin > 1:
        D = int(D / d_bin)
    return (a, D, xa, min(pa, p_clip), h, min(xh, M.WINDOW), min(ph, p_clip))


class QTable:
    """Q rows (4 floats, Python lists: the inner loop is per object) keyed by
    key_of(obs), created on first visit; `visits` counts updates per key."""

    def __init__(self, d_clip: int = 128, p_clip: int = 48, d_bin: int = 1):
        self.d_clip, self.p_clip, self.d_bin = d_clip, p_clip, d_bin
        self.q: Dict[Obs, List[float]] = {}
        self.visits: Dict[Obs, int] = {}
        self.legal: Dict[Obs, int] = {}      # bits 0-3: legal actions as first seen; bits 4-7: actions tried

    def key(self, obs: Obs) -> Obs:
        return key_of(obs, self.d_clip, self.p_clip, self.d_bin)

    def row(self, k: Obs, legal=None) -> List[float]:
        r = self.q.get(k)
        if r is None:
            r = [0.0, 0.0, 0.0, 0.0]
            self.q[k] = r
            self.visits[k] = 0
            if legal is not None:
                self.legal[k] = sum(1 << i for i in range(4) if legal[i])
        return r

    def seed_row(self, k: Obs, row: List[float], legal, tried) -> None:
        """Install a row with its legal and tried masks (tests, warm starts)."""
        self.q[k] = list(row)
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
        """Greedy among the legal actions that were actually updated; -1 if none
        (an untried action's 0.0 must not outrank a tried action's value)."""
        r = self.q.get(k)
        if r is None:
            return -1
        t = self.legal.get(k, 0) >> 4
        mask = tuple(legal[i] and bool(t >> i & 1) for i in range(4))
        return self.argmax(r, mask) if any(mask) else -1

    def value_tried(self, k: Obs, legal, default: float) -> float:
        """Bootstrap value of a successor: max over its tried legal actions,
        or `default` (the reference value) when nothing was tried there yet.
        Maximising over untried zeros instead made every hold chain look
        like 0 at its frontier (2026-10-25: Q(hold) -0.17 where the Monte
        Carlo return was -0.76)."""
        a = self.greedy_tried(k, legal)
        return self.q[k][a] if a >= 0 else default

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


REF_REFRESH = 50_000   # steps between re-picking the reference key (the most visited one)


def train(env, alpha: float, rho: float, budget: int, q: Optional[QTable] = None,
          lr: float = 0.02, eps_start: float = 0.3, eps_end: float = 0.02, seed: int = 1,
          lr_min: float = 0.002) -> QTable:
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
    through `q`."""
    q = q if q is not None else QTable()
    rng = random.Random(seed)
    o = env.obs()
    legal = env.legal()
    k = q.key(o)
    row = q.row(k, legal)
    kref = max(q.visits, key=q.visits.get) if q.visits else k
    de = (eps_end - eps_start) / max(budget, 1)
    eps = eps_start
    for t in range(budget):
        if env.done:
            break
        if rng.random() < eps:
            choices = [i for i in range(4) if legal[i]]
            a = choices[int(rng.random() * len(choices))]
        else:
            a = q.greedy_tried(k, legal)
            if a < 0:
                choices = [i for i in range(4) if legal[i]]
                a = choices[int(rng.random() * len(choices))]
        o2, fa, fh = env.step(a)
        r = fa - rho * (fa + fh)
        legal2 = env.legal()
        k2 = q.key(o2)
        row2 = q.row(k2, legal2)
        vref = q.value(kref)
        m2 = q.value_tried(k2, legal2, vref)
        n = q.visits[k]
        step = 1.0 / (1.0 + lr * n)
        if step < lr_min:
            step = lr_min
        row[a] += step * (r - vref + m2 - row[a])
        q.visits[k] = n + 1
        q.legal[k] |= 1 << (4 + a)
        o, legal, k, row = o2, legal2, k2, row2
        eps += de
        if t % REF_REFRESH == REF_REFRESH - 1:
            kref = max(q.visits, key=q.visits.get)
    return q


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
        a = self.fallback(obs)
        if not legal[a]:
            a = HOLD if legal[HOLD] else next(i for i in range(4) if legal[i])
        return a, False
