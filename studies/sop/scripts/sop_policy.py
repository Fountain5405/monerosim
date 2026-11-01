"""The numpy-free part of the learned SoP attacker (scripts/sop_rl.py):
what agents/selfish_strategy.py needs at decision time inside a Shadow run,
where the lane boxes' venvs have no numpy. sop_rl re-exports these.

Observation (scripts/sop_mdp.py State): (a, D, xa, pa, h, xh, ph).
Policy file: gzip JSON {"meta": {...}, "key_clip": {"d", "p", "d_bin", "p_bin"},
"fallback": "sim_stubborn", "policy": {"a,D,xa,pa,h,xh,ph": action name}},
holding only the keys where the learned action differs from sim_stubborn.
"""
from __future__ import annotations

import gzip
import json
import os
from typing import Dict, Tuple

Obs = Tuple[int, int, int, int, int, int, int]
HOLD, PUBLISH, REVEAL, GIVE_UP = 0, 1, 2, 3
ACTION_NAMES = ["hold", "publish", "reveal", "give_up"]
WINDOW = 32   # either_window: K - w objects past a branch's first block (scripts/sop_mdp.py)


def key_of(obs: Obs, d_clip: int = 128, p_clip: int = 48, d_bin: int = 1, p_bin: int = 1) -> Obs:
    """The Q-table key: the observation with |D| clipped (then binned,
    truncating toward zero) and the pending counts clipped (then binned).
    The game itself is never clipped; only the table's view of it."""
    a, D, xa, pa, h, xh, ph = obs
    D = max(-d_clip, min(d_clip, D))
    if d_bin > 1:
        D = int(D / d_bin)
    pa, ph = min(pa, p_clip), min(ph, p_clip)
    if p_bin > 1:
        pa, ph = pa // p_bin, ph // p_bin
    return (a, D, min(xa, WINDOW), pa, h, min(xh, WINDOW), ph)


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
    if max(xa, xh) >= WINDOW and D > ph:
        return REVEAL
    return HOLD


def param_stubborn(obs: Obs, G: int = 5, L: int = 0, M: int = 1, R: int = 1, B: int = 0, Z: int = 0,
                   W: int = WINDOW) -> int:
    """sim_stubborn with knobs (2026-10-26, scripts/sop_attacker_search.py):
    G the objects give-up; L publish an unopposed lead of L blocks (0: never,
    hold as the sim's rule does); M reveal only with a margin of M objects
    over the honest branch (1: as soon as the network accepts); R reveal only
    once the honest branch holds R blocks; B give up when behind by B blocks
    (0: off); Z hold a pending-shares-only branch against an honest block
    instead of giving up (the race model's own rule, +0.025 at alpha 0.45
    over the sim's). W is the network's window in objects past a branch's
    first block ((K - 1) * w; 32 by default), which the observation's x
    counters are capped at. The defaults are exactly sim_stubborn."""
    a, D, xa, pa, h, xh, ph = obs
    if a == 0 and h > 0 and not Z:
        return GIVE_UP
    if h == 0:
        return PUBLISH if (L > 0 and a >= L) else HOLD
    if -D + ph - pa > G:
        return GIVE_UP
    if B > 0 and h - a >= B:
        return GIVE_UP
    if max(xa, xh) >= W and D - ph >= M and h >= R:
        return REVEAL
    return HOLD


def load_policy(path: str) -> Tuple[Dict[Obs, int], dict]:
    """(policy keyed by observation tuple -> action, meta with key_clip and
    fallback merged in). Raises FileNotFoundError / ValueError on a bad file."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    try:
        with gzip.open(path, "rt") as f:
            doc = json.load(f)
        names = {n: i for i, n in enumerate(ACTION_NAMES)}
        policy = {tuple(int(x) for x in k.split(",")): names[v] for k, v in doc["policy"].items()}
        meta = dict(doc["meta"])
        meta["key_clip"] = doc["key_clip"]
        meta["fallback"] = doc.get("fallback", "sim_stubborn")
    except (OSError, KeyError, ValueError, TypeError) as e:
        raise ValueError(f"not a policy file: {path}: {e}") from e
    return policy, meta
