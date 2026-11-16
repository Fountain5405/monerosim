"""SoP (MRL #146, 2026-10-20 rule) for the disruption objective, with the honest pending shares.

The walk model (sop_walk.py) drops the honest pending shares ph when a race
restarts; the exact game (sop_mdp.py) starts the next race at x = -ph after
give_up and x = pa - ph after publish, and an attacker can time its restarts
by ph. This model keeps ph:

  h   honest blocks since the fork, saturating at min_depth;
  a1  whether the attacker has a block since the fork;
  x   the attacker's object lead D + pa - ph (+1 per attacker object, -1 per
      honest object);
  pa  the attacker's pending shares; ph the honest pending shares.

A reveal is accepted iff x - pa > 0 (sop_mdp's D > ph). The only departures
from the exact game left:
- the window (no reveal before 32 objects past a branch's first block) is
  ignored: in the attacker's favour;
- pa and ph stop counting at their caps while x keeps counting: acceptance
  then reads a smaller pa (in the attacker's favour) and a restart a smaller
  ph (in its favour), but a reveal carries a smaller pa into the next race
  (against it, by the shares above the cap);
- x is clamped to [x_min, x_max]: honest objects below x_min are ignored (in
  its favour), attacker objects above x_max are lost (against it).

Tables are built with numpy over the full product space (no pto: a few
million states) and solved with howard.solve_tables. Time is counted in block
intervals (1/w per object); the reward is 1 per accepted reveal with
h >= min_depth.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

HOLD, REVEAL, GIVE_UP, PUBLISH = 0, 1, 2, 3
ACTION_NAMES = ["hold", "reveal", "give_up", "publish"]


@dataclass
class TightSoP:
    alpha: float
    w: int = 16
    min_depth: int = 11
    x_min: int = -64
    x_max: int = 64
    p_max: int = 32
    q_max: int = 32

    def __post_init__(self):
        self.dims = (self.min_depth + 1, 2, self.x_max - self.x_min + 1, self.p_max + 1, self.q_max + 1)
        self.n = int(np.prod(self.dims))

    def index(self, h, a1, x, pa, ph):
        H, A1, NX, NP, NQ = self.dims
        return (((h * A1 + a1) * NX + (x - self.x_min)) * NP + pa) * NQ + ph

    def decode(self, idx):
        H, A1, NX, NP, NQ = self.dims
        idx = np.asarray(idx)
        ph = idx % NQ; idx = idx // NQ
        pa = idx % NP; idx = idx // NP
        x = idx % NX + self.x_min; idx = idx // NX
        a1 = idx % A1; h = idx // A1
        return h, a1, x, pa, ph

    @property
    def start(self) -> int:
        return int(self.index(0, 0, 0, 0, 0))

    def from_exact(self, s) -> int:
        """Index of an exact sop_mdp state (a, D, xa, pa, h, xh, ph)."""
        a, D, xa, pa, h, xh, ph = s
        x = max(self.x_min, min(self.x_max, D + pa - ph))
        return int(self.index(min(h, self.min_depth), 1 if a >= 1 else 0, x,
                              min(pa, self.p_max), min(ph, self.q_max)))

    def tables(self):
        """P (list of csr, one per action), r, d, legal (arrays actions x n)."""
        t0 = time.time()
        n = self.n
        h, a1, x, pa, ph = self.decode(np.arange(n))
        clamp = lambda v: np.clip(v, self.x_min, self.x_max)
        al, pb = self.alpha, 1.0 / self.w
        # hold: four events per object
        nxt = [
            (self.index(h, a1, clamp(x + 1), np.minimum(pa + 1, self.p_max), ph), al * (1 - pb)),   # attacker share
            (self.index(h, 1, clamp(x + 1), 0, ph), al * pb),                                        # attacker block
            (self.index(h, a1, clamp(x - 1), pa, np.minimum(ph + 1, self.q_max)), (1 - al) * (1 - pb)),  # honest share
            (self.index(np.minimum(h + 1, self.min_depth), a1, clamp(x - 1), pa, 0), (1 - al) * pb),  # honest block
        ]
        rows = np.concatenate([np.arange(n)] * 4)
        cols = np.concatenate([c for c, _ in nxt])
        vals = np.concatenate([np.full(n, p) for _, p in nxt])
        P_hold = csr_matrix((vals, (rows, cols)), shape=(n, n))
        P_hold.sum_duplicates()
        zeros = np.zeros(n, dtype=int)
        reveal_to = self.index(zeros, zeros, clamp(pa), pa, zeros)
        publish_to = self.index(zeros, zeros, clamp(pa - ph), pa, ph)
        give_up_to = self.index(zeros, zeros, clamp(-ph), zeros, ph)
        one = lambda to: csr_matrix((np.ones(n), (np.arange(n), to)), shape=(n, n))
        P = [P_hold, one(reveal_to), one(give_up_to), one(publish_to)]
        legal = np.zeros((4, n), bool)
        legal[HOLD] = True
        legal[REVEAL] = (a1 == 1) & (h >= 1) & (x - pa > 0)
        legal[GIVE_UP] = (h >= 1) | (a1 == 1)
        legal[PUBLISH] = (a1 == 1) & (h == 0)
        r = np.zeros((4, n))
        r[REVEAL] = ((h >= self.min_depth) & legal[REVEAL]).astype(float)
        d = np.zeros((4, n))
        d[HOLD] = pb
        self.build_s = time.time() - t0
        return P, r, d, legal

    def initial_policy(self):
        """Give up far behind, reveal when deep and accepted, publish with no fork, else hold."""
        h, a1, x, pa, ph = self.decode(np.arange(self.n))
        pol = np.full(self.n, HOLD)
        pol[(a1 == 1) & (h == 0)] = PUBLISH
        pol[((h >= 1) | (a1 == 1)) & (x < -10)] = GIVE_UP
        pol[(a1 == 1) & (h >= self.min_depth) & (x - pa > 0)] = REVEAL
        return pol


def profile(P, r, d, policy, start):
    """Rate (reward per block interval) of a policy from its stationary distribution.

    pi(start) is pinned to 1 and the other balance equations are solved by
    sparse LU (no dense normalisation row: that one filled in past 13 GB at
    1.2 M states, 2026-11-16), then pi is normalised.
    """
    from scipy.sparse import diags, identity
    from scipy.sparse.csgraph import breadth_first_order
    from scipy.sparse.linalg import splu

    n = P[0].shape[0]
    rows = np.arange(n)
    P_pi = sum(diags((policy == a).astype(float)) @ P[a] for a in range(len(P))).tocsr()
    reach = np.sort(breadth_first_order(P_pi, start, directed=True, return_predecessors=False))
    sub = P_pi[reach][:, reach].tocsr()
    m = len(reach)
    s0 = int(np.searchsorted(reach, start))
    keep = np.r_[0:s0, s0 + 1:m]
    # pi_j = sum_i pi_i P_ij for j != start, with pi_start = 1
    A = (identity(m, format="csr") - sub).T.tocsr()[keep][:, keep]
    b = sub[s0, :].toarray().ravel()[keep]
    rest = splu(A.tocsc()).solve(b)
    pi = np.zeros(m)
    pi[s0] = 1.0
    pi[keep] = rest
    pi = np.clip(pi, 0.0, None)
    pi /= pi.sum()
    rr, dd = r[policy, rows][reach], d[policy, rows][reach]
    return {"rate": float(pi @ rr / (pi @ dd)), "reachable": int(m),
            "give_up_share": float(pi[policy[reach] == GIVE_UP].sum())}


def exact_rate(model: TightSoP, policy, objects: int, seed: int = 1, window: bool = True) -> dict:
    """Deep-reorg rate of `policy` in the exact SoP game (sop_mdp's rules), by simulation.

    Actions the exact game forbids (a reveal before the window or one the
    network rejects) become hold. window=False drops the window test (the
    only rule the tight model leaves out), for a like-for-like check.
    """
    from studies.sop.scripts import sop_mdp as M

    if model.w != M.W_SHARES:
        raise ValueError(f"exact_rate needs w = {M.W_SHARES}")
    caps = M.Caps(a_max=10 ** 9, h_max=10 ** 9, d_max=10 ** 9, p_max=10 ** 9, deficit=10 ** 9)
    events = np.random.default_rng(seed).choice(4, size=objects, p=np.array(M.event_probs(model.alpha)))
    s = M.START
    deep = 0
    for e in events:
        is_att, is_blk = M.EVENTS[e]
        s = M.event(s, is_att, is_blk, caps)
        a, D, xa, pa, h, xh, ph = s
        if a == 0 and h == 0:
            continue
        act = int(policy[model.from_exact(s)])
        accepted = a >= 1 and (M.past_window(s) or not window) and D > ph
        if act == REVEAL and not accepted:
            act = HOLD
        if act == PUBLISH and not (a >= 1 and h == 0):
            act = HOLD
        if act == REVEAL:
            deep += h >= model.min_depth
            s = M.do_reveal(s)[0]
        elif act == PUBLISH:
            s = M.do_publish(s)[0]
        elif act == GIVE_UP:
            s = M.do_give_up(s)[0]
    block_times = objects / model.w
    return {"objects": objects, "deep": deep, "rate": deep / block_times}


def main(argv=None) -> int:
    import argparse
    import json
    import sys

    from .howard import solve_tables

    p = argparse.ArgumentParser(description="Solve the tight SoP disruption model (one JSON line on stdout).")
    p.add_argument("--alpha", type=float, required=True)
    p.add_argument("--min-depth", type=int, default=11)
    p.add_argument("--x-min", type=int, default=-64)
    p.add_argument("--x-max", type=int, default=64)
    p.add_argument("--p-max", type=int, default=32)
    p.add_argument("--q-max", type=int, default=32)
    p.add_argument("--save-policy")
    p.add_argument("--no-profile", action="store_true", help="skip the stationary-distribution check of g")
    p.add_argument("--exact-objects", type=int, default=0, help="also run the policy in the exact game")
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args(argv)

    m = TightSoP(args.alpha, min_depth=args.min_depth, x_min=args.x_min, x_max=args.x_max,
                 p_max=args.p_max, q_max=args.q_max)
    P, r, d, legal = m.tables()
    out = {"model": "sop_tight", **vars(args), "states": m.n, "build_s": round(m.build_s, 1)}
    t0 = time.time()
    policy, g, it = solve_tables(P, r, d, legal, m.start, cur=m.initial_policy(), verbose=True)
    out.update({"g": g, "iterations": it, "solve_s": round(time.time() - t0, 1)})
    if args.save_policy:
        np.savez_compressed(args.save_policy, policy=policy.astype(np.int8), args=json.dumps(vars(args)))
    if not args.no_profile:
        t0 = time.time()
        out["profile"] = profile(P, r, d, policy, m.start)
        out["profile_s"] = round(time.time() - t0, 1)
    if args.exact_objects:
        for window in (False, True):
            t0 = time.time()
            res = exact_rate(m, policy, args.exact_objects, seed=args.seed, window=window)
            res["s"] = round(time.time() - t0, 1)
            out["exact_window" if window else "exact_no_window"] = res
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
