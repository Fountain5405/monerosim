#!/usr/bin/env python3
"""SoP (MRL #146, 2026-10-20 rule) as a Markov decision process.

The transition rules are those of scripts/sop_race_model.py Model B (rule
"sop", RULE_PRESETS["20261020"]: either_window, count_honest_pending,
attacker_embeds, release_depth 0, no ties, no equal_start, no early honest
shares), restated over a compact state so the states can be counted and the
attacker's policy optimised instead of hand-written.

Objects arrive one at a time; each is the attacker's with probability alpha
and a block with probability 1/w (else a workshare). State, 7 small ints:

  a   attacker blocks since the fork        h   honest blocks since the fork
  D   attacker weight minus honest weight (blocks + embedded shares each side)
  xa  objects past the attacker's FIRST      xh  same for the honest branch;
      block, capped at the window (32)           the either_window test
  pa  attacker shares pending on its tip     ph  honest shares pending

Why this is exact: the race model's rules compare the two weights, never use
them separately, so their difference D suffices; objects since the fork per
side equal weight plus pending, so the give-up counter is derived; the window
test max(xa, xh) >= K - w is monotone within a fork, so x is capped at 32 and,
once the window is passed, both x collapse to 32 (nothing reads them again).
Per-block share lists collapse to sums because the weights are additive.

Network acceptance of a reveal: past the window and attacker weight > honest
weight + honest pending, where the attacker's own pending tip shares do NOT
count (--own-pending ignore, the default; the 12-daemon sims reject reveals
that need them, which the count_own_tip_shares false attacker exploits).
--own-pending count is the race model's 20261020 reading. A reveal the
network rejects costs the attacker its branch (popped, as in the sims).

Actions after every object: hold; publish (h == 0: the attacker's blocks
become final, as honest mining would); reveal (only when accepted); give_up
(adopt the honest branch; honest pending carries on). Truncation caps (a, h,
|D|, p, and the objects deficit) force reveal-if-accepted else give_up, like
SSZ's bounded MDP.

Subcommands:
  enumerate   count the reachable states under the caps (vectorised BFS).
  evaluate    long-run attacker revenue share of the race model's
              window_stubborn policy (give_up_objects G, own or noown) on this
              chain: a check of the transition model against sop_race_model.py
              hunt and the sims.
  solve       optimal policy for the ratio objective att/(att+hon) by relative
              value iteration inside a binary search on rho (Sapirshtein,
              Sompolinsky, Zohar); prints the optimal share and an action
              summary, optionally dumps the policy as JSON.

Examples:
  venv/bin/python scripts/sop_mdp.py enumerate --alpha 0.45
  venv/bin/python scripts/sop_mdp.py evaluate --alpha 0.45 --give-up-objects 5 --test-own-pending count
  venv/bin/python scripts/sop_mdp.py solve --alpha 0.45 --out policy_a045.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from typing import Dict, List, Tuple

import numpy as np

W_SHARES = 16          # objects per block on average (w)
K_OBJECTS = 48         # SoP window in objects (K)
WINDOW = K_OBJECTS - W_SHARES   # either_window: 32 objects past a branch's first block

HOLD, PUBLISH, REVEAL, GIVE_UP = 0, 1, 2, 3
ACTION_NAMES = ["hold", "publish", "reveal", "give_up"]
State = Tuple[int, int, int, int, int, int, int]   # a, D, xa, pa, h, xh, ph
START: State = (0, 0, 0, 0, 0, 0, 0)
EVENTS = [(True, True), (True, False), (False, True), (False, False)]   # (attacker?, block?)
FIELDS = ["a", "D", "xa", "pa", "h", "xh", "ph"]
BITS = [4, 10, 6, 6, 4, 6, 6]        # a<16, D in [-512,511], x<=32, p<64
D_OFF = 512
SHIFTS = np.cumsum([0] + BITS[:-1])


class Caps:
    def __init__(self, a_max=8, h_max=8, d_max=160, p_max=48, deficit=48):
        self.a_max, self.h_max, self.d_max, self.p_max, self.deficit = a_max, h_max, d_max, p_max, deficit

    def __str__(self):
        return f"a<={self.a_max} h<={self.h_max} |D|<={self.d_max} p<={self.p_max} deficit<={self.deficit}"


def event_probs(alpha: float) -> List[float]:
    pb = 1.0 / W_SHARES
    return [alpha * pb, alpha * (1 - pb), (1 - alpha) * pb, (1 - alpha) * (1 - pb)]


# ---------------------------------------------------------------------------
# Scalar reference (the spec; the tests compare the vectorised code to it)
# ---------------------------------------------------------------------------

def _collapse(s: State) -> State:
    a, D, xa, pa, h, xh, ph = s
    if max(xa, xh) >= WINDOW:
        xa = xh = WINDOW
    return (a, D, xa, pa, h, xh, ph)


def past_window(s: State) -> bool:
    return max(s[2], s[5]) >= WINDOW


def deficit(s: State) -> int:
    """Honest objects since the fork minus the attacker's."""
    a, D, xa, pa, h, xh, ph = s
    return -D + ph - pa


def accepted(s: State, own_pending: bool) -> bool:
    a, D, xa, pa, h, xh, ph = s
    if a == 0 or not past_window(s):
        return False
    return D + (pa if own_pending else 0) > ph


def event(s: State, is_attacker: bool, is_block: bool, caps: Caps) -> State:
    a, D, xa, pa, h, xh, ph = s
    if not is_block:
        if is_attacker:
            pa = min(pa + 1, caps.p_max)
        else:
            ph = min(ph + 1, caps.p_max)
        return (a, D, xa, pa, h, xh, ph)
    if is_attacker:
        if a >= 1:
            xa = min(xa + 1 + pa, WINDOW)
        a, D, pa = a + 1, D + 1 + pa, 0
    else:
        if h >= 1:
            xh = min(xh + 1 + ph, WINDOW)
        h, D, ph = h + 1, D - 1 - ph, 0
    return _collapse((a, D, xa, pa, h, xh, ph))


def do_publish(s: State):
    a, D, xa, pa, h, xh, ph = s
    return (0, 0, 0, pa, 0, 0, ph), a, 0


def do_reveal(s: State):
    a, D, xa, pa, h, xh, ph = s
    return (0, 0, 0, pa, 0, 0, 0), a, 0


def do_give_up(s: State):
    a, D, xa, pa, h, xh, ph = s
    return (0, 0, 0, 0, 0, 0, ph), 0, h


def at_cap(s: State, caps: Caps) -> bool:
    a, D, xa, pa, h, xh, ph = s
    return (a >= caps.a_max or h >= caps.h_max or abs(D) >= caps.d_max or deficit(s) > caps.deficit)


def actions(s: State, caps: Caps, own_pending: bool):
    a, D, xa, pa, h, xh, ph = s
    if a == 0 and h == 0:
        return [(HOLD, s, 0, 0)]
    can_reveal = accepted(s, own_pending)
    if at_cap(s, caps):
        if h == 0:
            return [(PUBLISH, *do_publish(s))]
        if can_reveal:
            return [(REVEAL, *do_reveal(s))]
        return [(GIVE_UP, *do_give_up(s))]
    out = [(HOLD, s, 0, 0)]
    if a >= 1 and h == 0:
        out.append((PUBLISH, *do_publish(s)))
    if can_reveal:
        out.append((REVEAL, *do_reveal(s)))
    out.append((GIVE_UP, *do_give_up(s)))
    return out


def stubborn_action(s: State, caps: Caps, G: int, own_test: bool, own_net: bool):
    """The race model's window_stubborn with the objects give-up: give up once
    honest holds more than G objects more; withhold while h == 0; reveal when
    past the window and the attacker's OWN test (own_test = it counts its
    pending shares) says it wins; a reveal the network rejects pops the branch."""
    a, D, xa, pa, h, xh, ph = s
    if a == 0 and h == 0:
        return (HOLD, s, 0, 0)
    acc = accepted(s, own_net)
    if deficit(s) > G:
        return (GIVE_UP, *do_give_up(s))
    if h == 0:
        # at a cap with no honest block the truncation publishes (as actions()
        # does); checking "cap and not accepted" first here threw the blocks
        # away and cost 2/3 of the revenue at 3-block caps (2026-10-25)
        return (PUBLISH, *do_publish(s)) if at_cap(s, caps) else (HOLD, s, 0, 0)
    if at_cap(s, caps) and not acc:
        return (GIVE_UP, *do_give_up(s))
    if past_window(s) and D + (pa if own_test else 0) > ph:
        return (REVEAL, *do_reveal(s)) if acc else (GIVE_UP, *do_give_up(s))
    if at_cap(s, caps):
        return (REVEAL, *do_reveal(s))      # acc is True here
    return (HOLD, s, 0, 0)


def enumerate_states(caps: Caps, own_pending: bool, policy=None):
    index: Dict[State, int] = {START: 0}
    order: List[State] = [START]
    q = deque([START])
    while q:
        s = q.popleft()
        for is_att, is_blk in EVENTS:
            s1 = event(s, is_att, is_blk, caps)
            choices = [policy(s1)] if policy else actions(s1, caps, own_pending)
            for _, s2, _, _ in choices:
                if s2 not in index:
                    index[s2] = len(order)
                    order.append(s2)
                    q.append(s2)
    return index, order


def build_tables(order, index, caps, own_pending, policy=None):
    N = len(order)
    nxt = -np.ones((N, 4, 4), dtype=np.int64)
    ra = np.zeros((N, 4, 4), dtype=np.int8)
    rh = np.zeros((N, 4, 4), dtype=np.int8)
    for i, s in enumerate(order):
        for e, (is_att, is_blk) in enumerate(EVENTS):
            s1 = event(s, is_att, is_blk, caps)
            choices = [policy(s1)] if policy else actions(s1, caps, own_pending)
            for act, s2, fa, fh in choices:
                nxt[i, e, act] = index[s2]
                ra[i, e, act] = fa
                rh[i, e, act] = fh
    return nxt, ra, rh


def make_stubborn(caps, G, own_test, own_net):
    return lambda s: stubborn_action(s, caps, G, own_test, own_net)


# ---------------------------------------------------------------------------
# Vectorised enumeration: states as int64 keys, frontier expansion in numpy
# ---------------------------------------------------------------------------

def encode(cols) -> np.ndarray:
    key = np.zeros(len(cols[0]), dtype=np.int64)
    for i, (c, sh) in enumerate(zip(cols, SHIFTS)):
        v = c.astype(np.int64) + (D_OFF if FIELDS[i] == "D" else 0)
        key |= v << int(sh)
    return key


def decode(key: np.ndarray):
    out = []
    for i, (sh, b) in enumerate(zip(SHIFTS, BITS)):
        v = ((key >> int(sh)) & ((1 << b) - 1)).astype(np.int64)
        out.append(v - (D_OFF if FIELDS[i] == "D" else 0))
    return out


def key_of(s: State) -> int:
    return int(encode([np.array([v]) for v in s])[0])


def v_event(cols, is_att: bool, is_blk: bool, caps: Caps):
    a, D, xa, pa, h, xh, ph = [c.copy() for c in cols]
    if not is_blk:
        if is_att:
            pa = np.minimum(pa + 1, caps.p_max)
        else:
            ph = np.minimum(ph + 1, caps.p_max)
        return [a, D, xa, pa, h, xh, ph]
    if is_att:
        xa = np.where(a >= 1, np.minimum(xa + 1 + pa, WINDOW), xa)
        D = D + 1 + pa
        a = a + 1
        pa = np.zeros_like(pa)
    else:
        xh = np.where(h >= 1, np.minimum(xh + 1 + ph, WINDOW), xh)
        D = D - 1 - ph
        h = h + 1
        ph = np.zeros_like(ph)
    past = np.maximum(xa, xh) >= WINDOW
    xa = np.where(past, WINDOW, xa)
    xh = np.where(past, WINDOW, xh)
    return [a, D, xa, pa, h, xh, ph]


def _common(cols, caps: Caps, own_net: bool):
    a, D, xa, pa, h, xh, ph = cols
    idle = (a == 0) & (h == 0)
    past = np.maximum(xa, xh) >= WINDOW
    acc = (a >= 1) & past & ((D + (pa if own_net else 0)) > ph)
    dfc = -D + ph - pa
    cap = ((a >= caps.a_max) | (h >= caps.h_max) | (np.abs(D) >= caps.d_max) | (dfc > caps.deficit)) & ~idle
    return idle, past, acc, dfc, cap


def v_masks(cols, caps: Caps, own_pending: bool):
    a, D, xa, pa, h, xh, ph = cols
    idle, past, acc, dfc, cap = _common(cols, caps, own_pending)
    free = ~cap & ~idle
    return {
        HOLD: idle | free,
        PUBLISH: (free & (a >= 1) & (h == 0)) | (cap & (h == 0)),
        REVEAL: (free & acc) | (cap & (h >= 1) & acc),
        GIVE_UP: free | (cap & (h >= 1) & ~acc),
    }


def v_stubborn_masks(cols, caps: Caps, G: int, own_test: bool, own_net: bool):
    a, D, xa, pa, h, xh, ph = cols
    idle, past, acc, dfc, cap = _common(cols, caps, own_net)
    test_wins = past & ((D + (pa if own_test else 0)) > ph)
    act = np.full(len(a), HOLD, dtype=np.int64)
    give = ~idle & ((dfc > G) | (cap & ~acc & (h >= 1)))   # h == 0 at a cap publishes
    act[give] = GIVE_UP
    rest = ~idle & ~give
    act[rest & (h == 0) & cap] = PUBLISH
    h1 = rest & (h >= 1)
    act[h1 & test_wins & acc] = REVEAL
    act[h1 & test_wins & ~acc] = GIVE_UP
    act[h1 & ~test_wins & cap] = REVEAL          # cap & ~acc already went to give
    return {k: act == k for k in (HOLD, PUBLISH, REVEAL, GIVE_UP)}


def v_apply(cols, act: int):
    a, D, xa, pa, h, xh, ph = cols
    z = np.zeros_like(a)
    if act == HOLD:
        return cols, z, z
    if act == PUBLISH:
        return [z, z, z, pa, z, z, ph], a, z
    if act == REVEAL:
        return [z, z, z, pa, z, z, z], a, z
    return [z, z, z, z, z, z, ph], z, h


def enumerate_keys(caps: Caps, own_pending: bool, stubborn=None, verbose=False) -> np.ndarray:
    """Reachable post-decision states as a sorted int64 key array."""
    visited = encode([np.zeros(1, dtype=np.int64)] * 7)
    frontier = visited.copy()
    rounds = 0
    t = time.time()
    while len(frontier):
        cand = []
        cols = decode(frontier)
        for is_att, is_blk in EVENTS:
            post = v_event(cols, is_att, is_blk, caps)
            masks = (v_stubborn_masks(post, caps, *stubborn) if stubborn
                     else v_masks(post, caps, own_pending))
            for act, m in masks.items():
                if not m.any():
                    continue
                sub = [c[m] for c in post]
                nxt_cols, _, _ = v_apply(sub, act)
                cand.append(encode(nxt_cols))
        cand = np.unique(np.concatenate(cand))
        new = cand[~np.isin(cand, visited, assume_unique=True)]
        visited = np.union1d(visited, new)
        frontier = new
        rounds += 1
        if verbose and rounds % 25 == 0:
            print(f"  round {rounds}: {len(visited):,} states, frontier {len(new):,}  [{time.time() - t:.0f}s]",
                  file=sys.stderr, flush=True)
    return visited


def build_tables_v(keys: np.ndarray, caps: Caps, own_pending: bool, stubborn=None):
    N = len(keys)
    nxt = -np.ones((N, 4, 4), dtype=np.int32)
    ra = np.zeros((N, 4, 4), dtype=np.int8)
    rh = np.zeros((N, 4, 4), dtype=np.int8)
    cols = decode(keys)
    for e, (is_att, is_blk) in enumerate(EVENTS):
        post = v_event(cols, is_att, is_blk, caps)
        masks = (v_stubborn_masks(post, caps, *stubborn) if stubborn
                 else v_masks(post, caps, own_pending))
        for act, m in masks.items():
            if not m.any():
                continue
            sub = [c[m] for c in post]
            nxt_cols, fa, fh = v_apply(sub, act)
            k = encode(nxt_cols)
            idx = np.searchsorted(keys, k)
            assert np.all(keys[np.minimum(idx, N - 1)] == k), "successor not in the enumerated set"
            rows = np.nonzero(m)[0]
            nxt[rows, e, act] = idx
            ra[rows, e, act] = fa
            rh[rows, e, act] = fh
    return nxt, ra, rh


# ---------------------------------------------------------------------------
# Compact tables: ~35 B/state. publish/reveal/give_up all reset to one of a
# few hundred states keyed by the pending counts, so per (state, event) only
# the hold successor and a legality bitmask are stored; rewards (a or h of the
# post-event state) are recomputed from the decoded columns each sweep.
# ---------------------------------------------------------------------------

B_HOLD, B_PUB, B_REV, B_GIV = 1, 2, 4, 8


class Compact:
    def __init__(self, keys, caps: Caps, own_pending: bool, stubborn=None):
        self.keys, self.caps, self.own, self.stubborn = keys, caps, own_pending, stubborn
        N = len(keys)
        self.cols = [c.astype(np.int16) for c in decode(keys)]
        self.hold = -np.ones((N, 4), dtype=np.int32)
        self.legal = np.zeros((N, 4), dtype=np.uint8)
        P = caps.p_max + 1
        z = np.zeros(P * P, dtype=np.int64)
        pa = np.repeat(np.arange(P), P); ph = np.tile(np.arange(P), P)
        self.r_pub = self._lookup(encode([z, z, z, pa, z, z, ph])).reshape(P, P)
        self.r_rev = self._lookup(encode([z[:P], z[:P], z[:P], np.arange(P), z[:P], z[:P], z[:P]]))
        self.r_giv = self._lookup(encode([z[:P], z[:P], z[:P], z[:P], z[:P], z[:P], np.arange(P)]))
        for e, (is_att, is_blk) in enumerate(EVENTS):
            post = v_event(self.cols, is_att, is_blk, caps)
            masks = (v_stubborn_masks(post, caps, *stubborn) if stubborn else v_masks(post, caps, own_pending))
            bits = (masks[HOLD].astype(np.uint8) * B_HOLD | masks[PUBLISH].astype(np.uint8) * B_PUB
                    | masks[REVEAL].astype(np.uint8) * B_REV | masks[GIVE_UP].astype(np.uint8) * B_GIV)
            self.legal[:, e] = bits
            m = masks[HOLD]
            if m.any():
                k = encode([c[m] for c in post])
                self.hold[m, e] = self._lookup(k, strict=True)

    def _lookup(self, k, strict=False):
        idx = np.searchsorted(self.keys, k)
        ok = (idx < len(self.keys))
        ok[ok] = self.keys[idx[ok]] == k[ok]
        if strict:
            assert ok.all(), "successor not in the enumerated set"
        return np.where(ok, idx, -1).astype(np.int32)

    def sweep(self, V, rho, optimise: bool):
        """One relative-VI sweep: returns Vn (unnormalised) and, if asked, the argmax."""
        N = len(self.keys)
        p = event_probs(self.alpha)
        Vn = np.zeros(N)
        for e, (is_att, is_blk) in enumerate(EVENTS):
            post = v_event(self.cols, is_att, is_blk, self.caps)
            a_p, pa_p, h_p, ph_p = post[0].astype(np.int64), post[3].astype(np.int64), post[4].astype(np.int64), post[6].astype(np.int64)
            lg = self.legal[:, e]
            best = np.full(N, -np.inf) if optimise else np.zeros(N)
            # hold
            m = (lg & B_HOLD) > 0
            q = V[np.where(m, self.hold[:, e], 0)]
            self._fold(best, q, m, optimise)
            # publish / reveal: reward a (1 - rho)
            for bit, nxt in ((B_PUB, self.r_pub[pa_p, ph_p]), (B_REV, self.r_rev[pa_p])):
                m = (lg & bit) > 0
                q = a_p * (1.0 - rho) + V[np.where(m, nxt, 0)]
                self._fold(best, q, m, optimise)
            # give up: reward -rho h
            m = (lg & B_GIV) > 0
            q = -rho * h_p + V[np.where(m, self.r_giv[ph_p], 0)]
            self._fold(best, q, m, optimise)
            Vn += p[e] * best
        return Vn

    @staticmethod
    def _fold(best, q, m, optimise):
        if optimise:
            np.maximum(best, np.where(m, q, -np.inf), out=best)
        else:
            best += np.where(m, q, 0.0)

    def gain(self, rho, optimise, iters=5000, tol=1e-7, V0=None):
        N = len(self.keys)
        V = np.zeros(N) if V0 is None else V0.copy()   # warm start: the gain is V0-independent
        g = 0.0
        for it in range(iters):
            Vn = self.sweep(V, rho, optimise)
            g = Vn[0]
            Vn -= g
            span = np.max(np.abs(Vn - V))
            V = Vn
            if span < tol:
                break
        return g, V, it + 1

    def share(self, alpha, optimise, verbose=False, lo=0.0, hi=1.0, tol=1e-5):
        """Binary search on rho for zero gain; each step's VI starts from the
        previous step's V (2026-10-25: 320 cold sweeps per step at mid caps)."""
        self.alpha = alpha
        V = None
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            g, V, it = self.gain(mid, optimise, V0=V)
            if verbose:
                print(f"  rho={mid:.5f} gain={g:+.3e} ({it} sweeps)", file=sys.stderr, flush=True)
            if g > 0:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi), V

    def policy(self, V, rho):
        """Chosen action per (state, event) where more than one is legal; -1 elsewhere."""
        N = len(self.keys)
        pol = -np.ones((N, 4), dtype=np.int8)
        for e, (is_att, is_blk) in enumerate(EVENTS):
            post = v_event(self.cols, is_att, is_blk, self.caps)
            a_p, pa_p, h_p, ph_p = post[0].astype(np.int64), post[3].astype(np.int64), post[4].astype(np.int64), post[6].astype(np.int64)
            lg = self.legal[:, e]
            multi = np.array([bin(x).count("1") for x in range(16)], dtype=np.int8)[lg] > 1
            best = np.full(N, -np.inf)
            cands = [(HOLD, B_HOLD, V[np.where(lg & B_HOLD, self.hold[:, e], 0)]),
                     (PUBLISH, B_PUB, a_p * (1 - rho) + V[np.where(lg & B_PUB, self.r_pub[pa_p, ph_p], 0)]),
                     (REVEAL, B_REV, a_p * (1 - rho) + V[np.where(lg & B_REV, self.r_rev[pa_p], 0)]),
                     (GIVE_UP, B_GIV, -rho * h_p + V[np.where(lg & B_GIV, self.r_giv[ph_p], 0)])]
            for act, bit, q in cands:
                q = np.where((lg & bit) > 0, q, -np.inf)
                better = q > best + 1e-12
                pol[better & multi, e] = act
                np.maximum(best, q, out=best)
        return pol


# ---------------------------------------------------------------------------
# Average reward (ratio objective via rho): dense-table reference versions
# ---------------------------------------------------------------------------

def _q_event(nxt, ra, rh, rho, V, e, act):
    """Q for one (event, action) column: reward r = att - rho*(att+hon) plus V(next)."""
    n = nxt[:, e, act]
    valid = n >= 0
    r = ra[:, e, act].astype(np.float64) - rho * (ra[:, e, act].astype(np.float64) + rh[:, e, act].astype(np.float64))
    return np.where(valid, r + V[np.where(valid, n, 0)], -np.inf), valid


def relative_vi(nxt, ra, rh, probs, rho, optimise: bool, iters=5000, tol=1e-7):
    """Relative value iteration, per-event loop to keep temporaries at N floats."""
    N = nxt.shape[0]
    V = np.zeros(N)
    p = np.asarray(probs)
    gain = 0.0
    for it in range(iters):
        Vn = np.zeros(N)
        for e in range(4):
            best = np.full(N, -np.inf) if optimise else np.zeros(N)
            for act in range(4):
                q, valid = _q_event(nxt, ra, rh, rho, V, e, act)
                if optimise:
                    np.maximum(best, q, out=best)
                else:
                    best += np.where(valid, q, 0.0)
            Vn += p[e] * best
        gain = Vn[0]
        Vn -= gain
        span = np.max(np.abs(Vn - V))
        V = Vn
        if span < tol:
            break
    return gain, V, it + 1


def policy_from_V(nxt, ra, rh, probs, rho, V):
    N = nxt.shape[0]
    pol = np.zeros((N, 4), dtype=np.int8)
    for e in range(4):
        best = np.full(N, -np.inf)
        for act in range(4):
            q, _ = _q_event(nxt, ra, rh, rho, V, e, act)
            better = q > best
            pol[better, e] = act
            np.maximum(best, q, out=best)
    return pol


def share_for(nxt, ra, rh, probs, optimise, lo=0.0, hi=1.0, verbose=False):
    V = None
    while hi - lo > 1e-5:
        mid = 0.5 * (lo + hi)
        g, V, it = relative_vi(nxt, ra, rh, probs, mid, optimise)
        if verbose:
            print(f"  rho={mid:.5f} gain={g:+.3e} ({it} sweeps)", file=sys.stderr, flush=True)
        if g > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), V


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def add_common(p):
    p.add_argument("--alpha", type=float, default=0.45)
    p.add_argument("--own-pending", choices=["ignore", "count"], default="ignore",
                   help="does the network count the attacker's pending tip shares at a reveal")
    p.add_argument("--a-max", type=int, default=8)
    p.add_argument("--h-max", type=int, default=8)
    p.add_argument("--d-max", type=int, default=160, help="cap on |attacker weight - honest weight|")
    p.add_argument("--p-max", type=int, default=48)
    p.add_argument("--deficit", type=int, default=48, help="forced give-up once honest leads by this many objects")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--rho-lo", type=float, default=0.0, help="bisection bracket for the share")
    p.add_argument("--rho-hi", type=float, default=1.0)
    p.add_argument("--rho-tol", type=float, default=1e-5)


def window_reach(caps: Caps) -> Tuple[int, int]:
    """Most window progress each branch can make under the caps. x advances only
    on that branch's own blocks after its first, by 1 + the pending shares the
    block embeds (race model: sum(1 + n for n in blocks[1:])), so with a_max
    blocks and p_max pending shares it is (a_max - 1) * (1 + p_max)."""
    return (caps.a_max - 1) * (1 + caps.p_max), (caps.h_max - 1) * (1 + caps.p_max)


def caps_of(args):
    caps = Caps(args.a_max, args.h_max, args.d_max, args.p_max, args.deficit)
    ra, rh = window_reach(caps)
    if max(ra, rh) < WINDOW:
        print(f"WARNING: under these caps neither branch can reach the {WINDOW}-object window "
              f"(attacker at most {ra}, honest {rh}): no reveal is ever accepted, every withheld "
              f"block is lost, so the stubborn chain scores ~0 and the optimum is honest mining. "
              f"Raise --a-max/--h-max or --p-max so (blocks - 1) * (1 + p_max) >= {WINDOW}.",
              file=sys.stderr, flush=True)
    return caps


def cmd_enumerate(args):
    caps, own = caps_of(args), args.own_pending == "count"
    t = time.time()
    keys = enumerate_keys(caps, own, verbose=args.verbose)
    N = len(keys)
    cols = decode(keys)
    choice = np.zeros(N, dtype=bool)
    for is_att, is_blk in EVENTS:
        m = v_masks(v_event(cols, is_att, is_blk, caps), caps, own)
        choice |= (sum(mm.astype(np.int64) for mm in m.values()) > 1)
    a, h = cols[0], cols[4]
    past = np.maximum(cols[2], cols[5]) >= WINDOW
    print(f"caps: {caps}  own_pending={args.own_pending}")
    print(f"reachable states: {N:,}  (with a real choice after some event: {int(choice.sum()):,}; "
          f"inside the window: {int((~past).sum()):,}, past it: {int(past.sum()):,})  [{time.time() - t:.1f}s]")
    print("states by (attacker blocks a, honest blocks h):")
    amax, hmax = int(a.max()), int(h.max())
    hist = np.zeros((amax + 1, hmax + 1), dtype=np.int64)
    np.add.at(hist, (a, h), 1)
    print("  a\\h " + " ".join(f"{hh:>9d}" for hh in range(hmax + 1)))
    for aa in range(amax + 1):
        print(f"  {aa:>3d} " + " ".join(f"{hist[aa, hh]:>9d}" for hh in range(hmax + 1)))
    return 0


def cmd_evaluate(args):
    caps, own_net = caps_of(args), args.own_pending == "count"
    own_test = args.test_own_pending == "count"
    stub = (args.give_up_objects, own_test, own_net)
    t = time.time()
    keys = enumerate_keys(caps, own_net, stubborn=stub, verbose=args.verbose)
    print(f"chain states: {len(keys):,}  [enumerated in {time.time() - t:.0f}s]", file=sys.stderr, flush=True)
    C = Compact(keys, caps, own_net, stubborn=stub)
    rho, _ = C.share(args.alpha, optimise=False, verbose=args.verbose,
                     lo=args.rho_lo, hi=args.rho_hi, tol=args.rho_tol)
    print(f"window_stubborn give_up_objects={args.give_up_objects} test_own_pending={args.test_own_pending} "
          f"network_own_pending={args.own_pending} alpha={args.alpha}")
    print(f"chain states: {len(keys):,}  attacker revenue share: {rho:.4f}  [{time.time() - t:.1f}s]")
    return 0


def cmd_solve(args):
    caps, own_net = caps_of(args), args.own_pending == "count"
    t = time.time()
    keys = enumerate_keys(caps, own_net, verbose=args.verbose)
    print(f"alpha={args.alpha} own_pending={args.own_pending} caps: {caps}  states: {len(keys):,}  "
          f"[enumerated in {time.time() - t:.0f}s]", file=sys.stderr, flush=True)
    C = Compact(keys, caps, own_net)
    rho, V = C.share(args.alpha, optimise=True, verbose=args.verbose,
                     lo=args.rho_lo, hi=args.rho_hi, tol=args.rho_tol)
    pol = C.policy(V, rho)
    multi = pol >= 0
    counts = {n: int(((pol == i) & multi).sum()) for i, n in enumerate(ACTION_NAMES)}
    print(f"optimal attacker revenue share at alpha={args.alpha}: {rho:.4f}  "
          f"(honest mining {args.alpha:.2f}; states {len(keys):,}; {time.time() - t:.0f}s)")
    print("action counts over decision (state, event) pairs: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if args.out:
        table = {}
        for e, (is_att, is_blk) in enumerate(EVENTS):
            post = v_event(C.cols, is_att, is_blk, caps)
            rows = np.nonzero(multi[:, e])[0]
            pk = encode([c[rows].astype(np.int64) for c in post])
            for r, k in zip(rows, pk):
                table[str(int(k))] = ACTION_NAMES[pol[r, e]]
        with open(args.out, "w") as fh:
            json.dump({"alpha": args.alpha, "own_pending": args.own_pending, "caps": str(caps), "share": rho,
                       "key": f"int64 of fields {FIELDS} with bits {BITS}; D stored + {D_OFF}",
                       "policy": table}, fh)
        print(f"policy table ({len(table):,} post-event states) -> {args.out}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("enumerate"); add_common(p); p.set_defaults(fn=cmd_enumerate)
    p = sub.add_parser("evaluate"); add_common(p)
    p.add_argument("--give-up-objects", type=int, default=5)
    p.add_argument("--test-own-pending", choices=["ignore", "count"], default="count",
                   help="does the ATTACKER's reveal test count its own pending shares (count = o5 attacker, ignore = noown)")
    p.set_defaults(fn=cmd_evaluate)
    p = sub.add_parser("solve"); add_common(p); p.add_argument("--out"); p.set_defaults(fn=cmd_solve)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
