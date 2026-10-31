#!/usr/bin/env python3
"""Check sop_mdp.py's hand-written solver against off-the-shelf solvers and a
published table (2026-10-31: the MRL review asked why the solver uses no MDP
library).

  sop   export sop_mdp.Compact's tables (the model every solve runs on: lower
        or upper bound, or a fixed window_stubborn policy) as a standard MDP
        and solve it three ways: the hand-written Compact relative VI inside
        its bisection on rho; pymdptoolbox's RelativeValueIteration inside the
        same bisection; and scipy's HiGHS on the occupation-measure linear
        program of the ratio objective (Charnes-Cooper), which needs neither
        the bisection nor value iteration.
  btc   the Bitcoin selfish-mining MDP of Sapirshtein, Sompolinsky and Zohar
        (FC 2016, Table 1; truncated at max(a, h) = T, under- or over-paying
        as in their section 4.2) in sop_mdp's (state, event, action) table
        form, solved by sop_mdp.relative_vi (the hand-written dense relative
        VI) in the bisection and by the two library solvers, beside the
        paper's Table 2 (gamma 0, T 95); and SSZ's SM1 policy beside
        Eyal-Sirer's closed form, and honest mining beside alpha.

Decision nodes are (post-decision state i, event e) pairs: event e (prob p_e)
takes i to a post-event state, the attacker picks an action, and the next node
is (successor j, e') with prob p_e'. The toolbox needs every action at every
node, so an illegal action gets the node's first legal action's transition and
reward (a duplicate cannot change the optimum); the LP uses legal actions only.

Runs on a lane box with its own venv (numpy, scipy, pymdptoolbox), never on
the control box:
  venv/bin/python scripts/sop_mdp_crosscheck.py sop --alpha 0.45 --a-max 3 --h-max 3 --p-max 16 --d-max 40 --deficit 12 --bound upper
  venv/bin/python scripts/sop_mdp_crosscheck.py btc --alpha 0.35 --gamma 0 --T 95
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

import sop_mdp as M


# ---------------------------------------------------------------------------
# Generic tables -> library solvers
# ---------------------------------------------------------------------------

def fill_illegal(succ, att, hon):
    """(N, E, A) tables -> per-node (N*E, A) arrays, node = i*E + e, with every
    illegal action replaced by the node's first legal one; also the legal mask."""
    N, E, A = succ.shape
    s = succ.reshape(N * E, A).copy()
    ra = att.reshape(N * E, A).astype(np.float64)
    rh = hon.reshape(N * E, A).astype(np.float64)
    legal = s >= 0
    assert legal.any(axis=1).all(), "a decision node with no legal action"
    first = legal.argmax(axis=1)
    r, c = np.nonzero(~legal)
    s[r, c] = s[r, first[r]]
    ra[r, c] = ra[r, first[r]]
    rh[r, c] = rh[r, first[r]]
    return s, ra, rh, legal


def toolbox_P(s, probs, tau=1.0):
    """One scipy CSR matrix per action over the decision nodes; tau < 1 mixes in
    a self-loop (P' = tau P + (1 - tau) I: same stationary laws, same gain) for
    a periodic chain."""
    from scipy.sparse import csr_matrix, identity
    n, A = s.shape
    E = len(probs)
    ev = np.nonzero(probs > 0)[0]
    rows = np.repeat(np.arange(n), len(ev))
    data = np.tile(probs[ev], n)
    out = []
    for a in range(A):
        P = csr_matrix((data, (rows, (s[:, a][:, None] * E + ev[None, :]).ravel())), shape=(n, n))
        out.append(P if tau == 1.0 else (tau * P + (1.0 - tau) * identity(n, format="csr")).tocsr())
    return out


def toolbox_share(P, ra, rh, lo=0.0, hi=1.0, tol=1e-6, eps=1e-10, max_iter=200000):
    """pymdptoolbox RelativeValueIteration (average reward of att - rho (att + hon))
    inside a bisection on rho for zero gain. pymdptoolbox 4.0b3's input check
    broadcasts a sparse matrix's (n, 1) row sums against an (n,) vector and
    compares the matrix with 0 densely, allocating n x n arrays (9.4 GiB at
    35,588 nodes, 2026-10-31); it is replaced by the same checks done sparsely
    here (later releases have skip_check for this)."""
    import mdptoolbox.mdp as mdp
    for Pa in P:
        assert Pa.shape == (len(ra), len(ra)) and (Pa.data >= 0).all(), "transition matrix shape or sign"
        assert np.abs(np.asarray(Pa.sum(axis=1)).ravel() - 1.0).max() < 1e-12, "transition rows must sum to 1"
    assert ra.shape == (len(ra), len(P)) and rh.shape == ra.shape
    mdp._util.check = lambda *a, **k: None
    steps = []
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        m = mdp.RelativeValueIteration(P, ra - mid * (ra + rh), epsilon=eps, max_iter=max_iter)
        m.run()
        steps.append((mid, float(m.average_reward), int(m.iter)))
        if m.iter >= max_iter:
            raise RuntimeError(f"toolbox RVI hit max_iter {max_iter} at rho {mid} (periodic chain? try --tau 0.5)")
        if m.average_reward > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), steps


def lp_share(s, ra, rh, legal, probs):
    """max sum y att  s.t.  y >= 0 a flow over (node, legal action) pairs
    (out of each node = into it) and sum y (att + hon) = 1: the occupation-
    measure LP of the ratio objective after Charnes-Cooper, solved by HiGHS.
    The flow rows always sum to zero, so node 0's is dropped: with all of them
    HiGHS called a fixed-policy chain infeasible (2026-10-31) although its
    stationary law satisfies every row to 2e-16."""
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix, csr_matrix, vstack
    n, A = s.shape
    E = len(probs)
    ev = np.nonzero(probs > 0)[0]
    ni, ai = np.nonzero(legal)
    K = len(ni)
    j = s[ni, ai]
    rows = np.concatenate([ni, (j[:, None] * E + ev[None, :]).ravel()])
    cols = np.concatenate([np.arange(K), np.repeat(np.arange(K), len(ev))])
    data = np.concatenate([np.ones(K), -np.tile(probs[ev], K)])
    flow = coo_matrix((data, (rows, cols)), shape=(n, K)).tocsr()
    tot = csr_matrix((ra + rh)[ni, ai][None, :])
    b = np.zeros(n + 1)
    b[-1] = 1.0
    A_eq = vstack([flow[1:], tot]).tocsr()
    # HiGHS returned status 15 (unknown, primal infeasible) at tight tolerances on
    # the slow-mixing Bitcoin chains at alpha >= 0.4, T 95 (2026-10-31): retry looser
    tried = []
    for opts in ({"primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9}, {},
                 {"presolve": False}):
        res = linprog(-ra[ni, ai], A_eq=A_eq, b_eq=b[1:], bounds=(0, None), method="highs", options=opts)
        if res.status == 0:
            return float(-res.fun), K
        tried.append(f"{opts or 'defaults'}: {res.message[:60]}")
    raise RuntimeError("LP failed: " + " | ".join(tried))


def library_checks(succ, att, hon, probs, tol, tau):
    s, ra, rh, legal = fill_illegal(succ, att, hon)
    out = {"nodes": int(s.shape[0])}
    t = time.time()
    rho, steps = toolbox_share(toolbox_P(s, probs, tau), ra, rh, tol=tol)
    out.update(toolbox_rvi=rho, toolbox_max_iter=max(it for _, _, it in steps), toolbox_s=round(time.time() - t, 1))
    t = time.time()
    try:
        rho, K = lp_share(s, ra, rh, legal, probs)
        out.update(highs_lp=rho, lp_vars=K, lp_s=round(time.time() - t, 1))
    except (RuntimeError, MemoryError) as exc:      # keep the other two solvers' results
        out.update(highs_lp=None, lp_error=str(exc)[:300])
    return out


# ---------------------------------------------------------------------------
# sop: Compact's own tables
# ---------------------------------------------------------------------------

def compact_tables(C, alpha):
    """(succ, att, hon) of shape (N, 4, 4) and the event probabilities: the
    transitions and rewards Compact.sweep uses (upper bound: the award replaces
    every action at a cap, paid as fractional blocks with successor START)."""
    N = len(C.keys)
    C.alpha = alpha
    if C.upper:
        C._award_tables()
    succ = -np.ones((N, 4, 4), dtype=np.int64)
    att = np.zeros((N, 4, 4))
    hon = np.zeros((N, 4, 4))
    for e, (is_att, is_blk) in enumerate(M.EVENTS):
        post = M.v_event(C.cols, is_att, is_blk, C.caps)
        a_p, pa_p, h_p, ph_p = (post[k].astype(np.int64) for k in (0, 3, 4, 6))
        zero = np.zeros(N, dtype=np.int64)
        lg = C.legal[:, e]
        for act, bit, nxt, ra, rh in ((M.HOLD, M.B_HOLD, C.hold[:, e], zero, zero),
                                      (M.PUBLISH, M.B_PUB, C.r_pub[pa_p, ph_p], a_p, zero),
                                      (M.REVEAL, M.B_REV, C.r_rev[pa_p], a_p, zero),
                                      (M.GIVE_UP, M.B_GIV, C.r_giv[ph_p], zero, h_p)):
            m = (lg & bit) > 0
            assert (nxt[m] >= 0).all(), f"legal {M.ACTION_NAMES[act]} with no enumerated successor"
            succ[m, e, act] = nxt[m]
            att[m, e, act] = ra[m]
            hon[m, e, act] = rh[m]
        if C.upper:
            m = C.award[:, e]
            xi = C.award_x[:, e] - C.x_lo
            pr, g = C.p_ret[xi], C.g[xi]
            succ[m, e, :] = -1
            att[m, e, :] = 0.0
            hon[m, e, :] = 0.0
            succ[m, e, 0] = C.i_start
            att[m, e, 0] = (pr * a_p + g / M.W_SHARES)[m]
            hon[m, e, 0] = ((1.0 - pr) * h_p)[m]
    return succ, att, hon, np.asarray(M.event_probs(alpha))


def compact_share(C, alpha, optimise, tol):
    """Compact.share's loop (warm-started bisection over Compact.gain), keeping
    the sweep count of each step so a hit of gain()'s 5000-sweep cap shows."""
    C.alpha = alpha
    lo, hi, V, its = 0.0, 1.0, None, []
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        g, V, it = C.gain(mid, optimise, V0=V)
        its.append(it)
        if g > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), max(its)


def set_window(w, K):
    """Rescale the share rule (w objects per block, window K objects); every
    sop_mdp function reads these module constants at call time, so small caps
    can reach the window. The production model is w 16, K 48."""
    M.W_SHARES, M.K_OBJECTS, M.WINDOW = w, K, K - w
    assert 0 < M.WINDOW <= 32, "x is stored in 6 bits and collapsed at the window"


def cmd_sop(args):
    set_window(args.w_shares, args.k_objects)
    caps = M.Caps(args.a_max, args.h_max, args.d_max, args.p_max, args.deficit)
    own = args.own_pending == "count"
    stub = (args.give_up_objects, args.test_own_pending == "count", own) if args.stubborn else None
    t = time.time()
    keys = M.enumerate_keys(caps, own, stubborn=stub)
    C = M.Compact(keys, caps, own, stubborn=stub, bound=args.bound)
    out = {"model": "sop", "alpha": args.alpha, "w": M.W_SHARES, "K": M.K_OBJECTS, "caps": str(caps),
           "own_pending": args.own_pending,
           "bound": args.bound, "policy": f"window_stubborn G={args.give_up_objects} test_own={args.test_own_pending}"
           if stub else "optimised", "states": int(len(keys))}
    rho, sweeps = compact_share(C, args.alpha, optimise=stub is None, tol=args.tol)
    out.update(hand_written=rho, hand_max_sweeps=sweeps, hand_s=round(time.time() - t, 1))
    succ, att, hon, probs = compact_tables(C, args.alpha)
    out.update(library_checks(succ, att, hon, probs, args.tol, args.tau))
    print(json.dumps(out), flush=True)
    return 0


# ---------------------------------------------------------------------------
# btc: the Sapirshtein-Sompolinsky-Zohar Bitcoin MDP
# ---------------------------------------------------------------------------

ADOPT, OVERRIDE, MATCH, WAIT = 0, 1, 2, 3
IRRELEVANT, RELEVANT, ACTIVE = 0, 1, 2

# SSZ (FC 2016) Table 2, gamma 0, T 95, epsilon 1e-5: (SM1, epsilon-OPT, upper bound)
SSZ_TABLE2 = {1 / 3: (1 / 3, 0.33705, 0.33707), 0.35: (0.36650, 0.37077, 0.37079),
              0.375: (0.42118, 0.42600, 0.42604), 0.4: (0.48372, 0.48866, 0.48904),
              0.425: (0.55801, 0.56808, 0.57226), 0.45: (0.65177, 0.66891, 0.70109),
              0.475: (0.78254, 0.80172, 0.90476)}


def btc_event(st, e):
    """Post-decision (a, h, m) -> post-event (a, h, fork) and the attacker blocks
    the event itself makes final. e: 0 attacker block; 1 honest block on the
    attacker's matched branch (its h published blocks win); 2 honest block on
    the honest branch; 3 unused (probability 0)."""
    a, h, m = st
    if e == 0:
        return (a + 1, h, ACTIVE if m else IRRELEVANT), 0
    if e == 1 and m:
        return (a - h, 1, RELEVANT), h
    return (a, h + 1, RELEVANT), 0


def btc_award(a, h, alpha):
    """SSZ's over-paying reward at max(a, h) = T (section 4.2, eq. 7 and the
    h >= a case) as (attacker, honest) blocks, so that the rho-weighted reward
    att - rho (att + hon) is the paper's expression."""
    c = alpha * (1 - alpha) / (1 - 2 * alpha) ** 2
    if a >= h:
        return c + 0.5 * ((a - h) / (1 - 2 * alpha) + a + h), 0.0
    q = (alpha / (1 - alpha)) ** (h - a)
    return q * (c + (h - a) / (1 - 2 * alpha)), (1 - q) * h


def btc_actions(s1, T, alpha=None, upper=False):
    """(action, post-decision state, attacker blocks, honest blocks) at a
    post-event state. At max(a, h) = T only adopt (SSZ: the under-paying MDP),
    or with upper the over-paying award in its place."""
    a, h, f = s1
    if a >= T or h >= T:
        return [(ADOPT, (0, 0, 0), *btc_award(a, h, alpha))] if upper else [(ADOPT, (0, 0, 0), 0, h)]
    out = [(ADOPT, (0, 0, 0), 0, h)]
    if a > h:
        out.append((OVERRIDE, (a - h - 1, 0, 0), h + 1, 0))
    if f == RELEVANT and a >= h:
        out.append((MATCH, (a, h, 1), 0, 0))
    out.append((WAIT, (a, h, 1 if f == ACTIVE else 0), 0, 0))
    return out


def sm1_action(s1):
    """SM1 as SSZ define it (section 3, eq. 3): adopt if h > a, match if
    h = a = 1, override if h = a - 1 >= 1, wait otherwise."""
    a, h, f = s1
    if h > a:
        return ADOPT
    if h == a == 1:
        return MATCH
    if h == a - 1 >= 1:
        return OVERRIDE
    return WAIT


def honest_action(s1):
    """SSZ eq. 2: adopt if h > a, override if a > h, wait otherwise."""
    a, h, f = s1
    return ADOPT if h > a else OVERRIDE if a > h else WAIT


def btc_tables(alpha, gamma, T, policy=None, upper=False):
    probs = np.array([alpha, gamma * (1 - alpha), (1 - gamma) * (1 - alpha), 0.0])
    start = (0, 0, 0)
    index, order, q = {start: 0}, [start], [start]
    rows = []
    while q:
        st = q.pop()
        i = index[st]
        for e in range(4):
            s1, ev_att = btc_event(st, e if e < 3 else 2)
            acts = btc_actions(s1, T, alpha, upper)
            if policy is not None:
                want = ADOPT if max(s1[0], s1[1]) >= T else policy(s1)
                acts = [x for x in acts if x[0] == want]
                assert len(acts) == 1, f"policy action {want} not legal at {s1}"
            for act, s2, fa, fh in acts:
                if s2 not in index:
                    index[s2] = len(order)
                    order.append(s2)
                    q.append(s2)
                rows.append((i, e, act, index[s2], ev_att + fa, fh))
    N = len(order)
    succ = -np.ones((N, 4, 4), dtype=np.int64)
    att = np.zeros((N, 4, 4))
    hon = np.zeros((N, 4, 4))
    for i, e, act, j, fa, fh in rows:
        succ[i, e, act], att[i, e, act], hon[i, e, act] = j, fa, fh
    return succ, att, hon, probs


def hand_share(succ, att, hon, probs, optimise, tol, iters=200000):
    """sop_mdp.relative_vi (the hand-written dense relative VI) in the bisection."""
    lo, hi, its = 0.0, 1.0, []
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        g, _, it = M.relative_vi(succ, att, hon, probs, mid, optimise, iters=iters, tol=1e-11)
        its.append(it)
        if g > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), max(its)


def es_sm1(alpha, gamma):
    a = alpha
    return (a * (1 - a) ** 2 * (4 * a + gamma * (1 - 2 * a)) - a ** 3) / (1 - a * (1 + (2 - a) * a))


def cmd_btc(args):
    t = time.time()
    upper = args.bound == "upper"
    succ, att, hon, probs = btc_tables(args.alpha, args.gamma, args.T, upper=upper)
    out = {"model": "btc", "alpha": args.alpha, "gamma": args.gamma, "T": args.T, "bound": args.bound,
           "states": int(succ.shape[0])}
    if not args.policies_only:
        rho, sweeps = hand_share(succ, att, hon, probs, True, args.tol)
        out.update(hand_written=rho, hand_max_sweeps=sweeps, hand_s=round(time.time() - t, 1))
        if not args.no_library:
            out.update(library_checks(succ, att, hon, probs, args.tol, args.tau))
    if not upper and args.T_policy:
        out["T_policy"] = args.T_policy
        for name, pol in (("sm1", sm1_action), ("honest", honest_action)):
            tabs = btc_tables(args.alpha, args.gamma, args.T_policy, policy=pol)
            out[f"{name}_hand_written"] = hand_share(*tabs, False, args.tol)[0]
            try:
                out[f"{name}_lp"] = lp_share(*fill_illegal(*tabs[:3]), tabs[3])[0]
            except (RuntimeError, MemoryError) as exc:
                out[f"{name}_lp"], out[f"{name}_lp_error"] = None, str(exc)[:300]
        out["sm1_eyal_sirer"] = es_sm1(args.alpha, args.gamma)
    ref = [v for k, v in SSZ_TABLE2.items() if abs(k - args.alpha) < 1e-9]
    if args.gamma == 0 and ref:
        out.update(ssz_sm1=ref[0][0], ssz_opt=ref[0][1], ssz_upper=ref[0][2])
    print(json.dumps(out), flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sop")
    for name, default in (("--a-max", 3), ("--h-max", 3), ("--d-max", 40), ("--p-max", 16), ("--deficit", 12)):
        p.add_argument(name, type=int, default=default)
    p.add_argument("--alpha", type=float, default=0.45)
    p.add_argument("--w-shares", type=int, default=16, help="objects per block (production 16)")
    p.add_argument("--k-objects", type=int, default=48, help="SoP window in objects (production 48)")
    p.add_argument("--own-pending", choices=["ignore", "count"], default="ignore")
    p.add_argument("--bound", choices=["lower", "upper"], default="lower")
    p.add_argument("--stubborn", action="store_true", help="evaluate window_stubborn instead of optimising")
    p.add_argument("--give-up-objects", type=int, default=5)
    p.add_argument("--test-own-pending", choices=["ignore", "count"], default="count")
    p.set_defaults(fn=cmd_sop)
    p = sub.add_parser("btc")
    p.add_argument("--alpha", type=float, default=0.35)
    p.add_argument("--gamma", type=float, default=0.0)
    p.add_argument("--T", type=int, default=95)
    p.add_argument("--bound", choices=["lower", "upper"], default="lower",
                   help="lower: adopt only at max(a, h) = T; upper: SSZ's over-paying award there")
    p.add_argument("--T-policy", type=int, default=400,
                   help="truncation for the SM1 / honest evaluations (SM1's lead walk is near-balanced: "
                        "at T 30 the cap costs it 0.0035 at alpha 0.35)")
    p.add_argument("--policies-only", action="store_true", help="skip the optimisation")
    p.add_argument("--no-library", action="store_true", help="hand-written solver only (large T)")
    p.set_defaults(fn=cmd_btc)
    for p in sub.choices.values():
        p.add_argument("--tol", type=float, default=1e-6, help="bisection tolerance on the share")
        p.add_argument("--tau", type=float, default=1.0, help="aperiodicity mix for the toolbox (1 = none)")
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
