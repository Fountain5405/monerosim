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
