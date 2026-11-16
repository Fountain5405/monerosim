"""Exact average-reward policy iteration (Howard) for the ratio objective.

Maximises g = (long-run reward) / (long-run difficulty) over stationary
policies, on pto's matrices. Each evaluation solves, by sparse LU,

    (I - P_pi) h + g d_pi = r_pi,   h(start) = 0

(the start state's column of I - P_pi is replaced by d_pi, whose unknown is
g), and the improvement step picks argmax_a r(s,a) - g d(s,a) + (P_a h)(s),
keeping the current action on ties. It stops only when the policy stops
changing.

Why not pto's PTOSolver here: mdptoolbox-roi evaluates sparse policies with
Krylov solvers at rtol 1e-7 and stops policy iteration once
span(V - Vprev) < epsilon. With tiny rewards (the disruption objective at low
alpha) both trigger: on the SoP walk model at alpha 0.25 PTO reported
3.4e-13 deep reorgs per block interval for a policy whose exact rate is
1.34e-8 (2026-11-16).

Assumes the policies visited are unichain (every state leads back to the
start state), which holds for the models here: give-up and adopt return to it.
Illegal actions (pto's error transitions into the final state) are never
chosen, except in states that have no legal action (unreachable corners);
the final state is dropped.
"""
from __future__ import annotations

import time
from typing import Optional, Tuple

import numpy as np
from scipy.sparse import csr_matrix, diags, identity
from scipy.sparse.linalg import splu

from .vendor.blockchain_mdps.base.blockchain_mdps.sparse_blockchain_mdp import SparseBlockchainMDP


def _tables(model):
    mdp = SparseBlockchainMDP(model)
    mdp.build_mdp()
    final = mdp.final_state_index
    n, na = mdp.num_of_states, mdp.num_of_actions
    keep = np.array([i for i in range(n) if i != final])
    P, r, d, legal = [], np.zeros((na, len(keep))), np.zeros((na, len(keep))), np.zeros((na, len(keep)), bool)
    for a in range(na):
        pa = csr_matrix(mdp.P.get_data()[a])
        ra = pa.multiply(csr_matrix(mdp.R.get_data()[a])).sum(axis=1).A.ravel()
        da = pa.multiply(csr_matrix(mdp.D.get_data()[a])).sum(axis=1).A.ravel()
        to_final = pa[:, final].toarray().ravel()
        ok = (to_final < 1e-12) & (ra > model.error_penalty / 10)
        P.append(pa[keep][:, keep].tocsr())
        r[a], d[a], legal[a] = ra[keep], da[keep], ok[keep]
    # states with no legal action (pto's unreachable corners, e.g. Nakamoto's
    # (0, 0, Active)) keep their error action: its only successor, the final
    # state, is dropped, so h there is the penalty and nothing leads in
    dead = ~legal.any(axis=0)
    legal[0, dead] = True
    start = int(np.searchsorted(keep, mdp.initial_state_index))
    return mdp, keep, P, r, d, legal, start


def evaluate(P_pi, r_pi, d_pi, start) -> Tuple[float, np.ndarray]:
    n = P_pi.shape[0]
    A = (identity(n, format="csr") - P_pi).tolil()
    A[:, start] = d_pi.reshape(-1, 1)
    z = splu(A.tocsc()).solve(r_pi)
    g = float(z[start])
    h = z.copy()
    h[start] = 0.0
    return g, h


def solve_tables(P, r, d, legal, start, cur=None, max_iter: int = 200, verbose: bool = False):
    """Howard on explicit tables: P[a] (n x n csr), r[a], d[a], legal[a] (length n), start index.

    Returns (policy as an int array over the n states, g, iterations). `cur`
    is the initial policy (an int array); default the first legal action.
    Every policy visited must be unichain.
    """
    t0 = time.time()
    na, n = r.shape
    cur = np.argmax(legal, axis=0) if cur is None else np.asarray(cur).copy()
    if not legal[cur, np.arange(n)].all():
        raise ValueError("the initial policy takes an illegal action")
    rows = np.arange(n)
    g = None
    for it in range(1, max_iter + 1):
        P_pi = sum(diags((cur == a).astype(float)) @ P[a] for a in range(na)).tocsr()
        g, h = evaluate(P_pi, r[cur, rows], d[cur, rows], start)
        Q = np.full((na, n), -np.inf)
        for a in range(na):
            q = r[a] - g * d[a] + P[a] @ h
            Q[a] = np.where(legal[a], q, -np.inf)
        best = Q.max(axis=0)
        cur_q = Q[cur, rows]
        # change only where strictly better (relative tolerance), so the loop ends
        improve = best > cur_q + 1e-12 * np.maximum(1.0, np.abs(cur_q))
        if verbose:
            print(f"  howard it {it}: g={g:.10e} changes={int(improve.sum())} ({time.time() - t0:.0f} s)", flush=True)
        if not improve.any():
            break
        cur = np.where(improve, Q.argmax(axis=0), cur)
    return cur, g, it


def solve_average(model, policy0: Optional[tuple] = None, max_iter: int = 200, verbose: bool = False):
    """Optimal policy of a pto model (a tuple over all states, final included), its g, and the iterations."""
    mdp, keep, P, r, d, legal, start = _tables(model)
    cur = None if policy0 is None else np.asarray(policy0)[keep]
    cur, g, it = solve_tables(P, r, d, legal, start, cur=cur, max_iter=max_iter, verbose=verbose)
    full = np.zeros(mdp.num_of_states, dtype=int)
    full[keep] = cur
    full[mdp.final_state_index] = 0
    return tuple(int(x) for x in full), g, it
