"""Solve a countermeasure MDP and report the policy's revenue and reorg profile.

One JSON line per run on stdout. Run on a lane box with the BLAS threads
capped (OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4); the solver needs scipy,
networkx and pymdptoolbox-roi, which the repo venv lacks.

  python -m studies.sop.countermeasures.solve nakamoto --alpha 0.35 --gamma 0 --max-fork 40
  python -m studies.sop.countermeasures.solve nakamoto --alpha 0.35 --gamma 0.5 --max-fork 60 \
      --objective disruption --min-depth 11
  python -m studies.sop.countermeasures.solve nakamoto --alpha 0.35 --gamma 0 --policy sm1 --mc-steps 2000000
  python -m studies.sop.countermeasures.solve sop --alpha 0.40 --objective disruption --exact-objects 20000000

`sop` is the SoP walk model (sop_walk.py): disruption only, rates per block
interval; --exact-objects also runs the optimal policy through the exact SoP
game (sop_mdp.py's rules) for a rate that is legal there.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time

import numpy as np

from .nakamoto import NakamotoModel
from .reorgs import OBJECTIVES, WEIGHTS, reorg_profile, simulate_profile
from .sop_walk import SoPWalkModel, exact_rate

PROTOCOLS = {"nakamoto": NakamotoModel, "sop": SoPWalkModel}


def build_model(args: argparse.Namespace):
    if args.protocol == "nakamoto":
        return NakamotoModel(args.alpha, args.gamma, args.max_fork, objective=args.objective,
                             min_depth=args.min_depth, weight=args.weight, normalization=args.normalization)
    if args.protocol == "sop":
        return SoPWalkModel(args.alpha, w=args.w, min_depth=args.min_depth, x_min=args.x_min, x_max=args.x_max,
                            p_max=args.p_max, objective=args.objective)
    raise ValueError(f"unknown protocol {args.protocol}")


def solve(model, solver: str, horizon: int, epsilon: float, max_iter: int):
    from .vendor.blockchain_mdps import OSMSolver, PTOSolver

    if solver == "pto":
        s = PTOSolver(model, expected_horizon=horizon)
    elif solver == "osm":
        if model.objective != "revenue":
            raise ValueError("OSM bisects the revenue share; use PTO for disruption")
        s = OSMSolver(model)
    else:
        raise ValueError(f"unknown solver {solver}")
    # mdptoolbox prints its convergence warning on stdout, which carries the JSON
    with contextlib.redirect_stdout(sys.stderr):
        policy, value, iterations, _ = s.calc_opt_policy(epsilon=epsilon, max_iter=max_iter)
    return tuple(int(x) for x in policy), float(value), int(iterations)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("protocol", choices=sorted(PROTOCOLS))
    p.add_argument("--alpha", type=float, required=True)
    p.add_argument("--gamma", type=float, default=0.0)
    p.add_argument("--max-fork", type=int, default=40)
    p.add_argument("--objective", choices=OBJECTIVES, default="revenue")
    p.add_argument("--min-depth", type=int, default=11,
                   help="shallowest reorg the disruption objective counts (default 11: deeper than the 10-block lock)")
    p.add_argument("--weight", choices=WEIGHTS, default="count")
    p.add_argument("--normalization", choices=("main_chain", "time"), default="main_chain",
                   help="nakamoto: rates per main-chain block or per block interval")
    p.add_argument("--w", type=int, default=16, help="sop: objects per block")
    p.add_argument("--x-min", type=int, default=-80, help="sop: walk floor")
    p.add_argument("--x-max", type=int, default=80, help="sop: walk ceiling")
    p.add_argument("--p-max", type=int, default=64, help="sop: attacker pending-share cap")
    p.add_argument("--exact-objects", type=int, default=0,
                   help="sop: simulate the optimal policy in the exact SoP game for this many objects")
    p.add_argument("--policy", choices=("optimal", "honest", "sm1"), default="optimal")
    p.add_argument("--solver", choices=("pto", "osm"), default="pto")
    p.add_argument("--horizon", type=int, default=10 ** 5, help="PTO expected horizon in blocks")
    p.add_argument("--epsilon", type=float, default=1e-6)
    p.add_argument("--max-iter", type=int, default=200000)
    p.add_argument("--mc-steps", type=int, default=0, help="also estimate the profile by Monte Carlo")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--max-report-depth", type=int, default=40)
    p.add_argument("--stationary", choices=("direct", "eigs"), default="direct",
                   help="how the reorg profile computes the stationary distribution")
    p.add_argument("--save-policy", help="write the policy (and the arguments) to this .npz")
    p.add_argument("--load-policy", help="skip the solve: read the policy from this .npz")
    args = p.parse_args(argv)

    model = build_model(args)
    out = {"protocol": args.protocol, "model": repr(model), "alpha": args.alpha, "gamma": args.gamma,
           "max_fork": args.max_fork, "objective": args.objective, "min_depth": args.min_depth,
           "weight": args.weight, "policy": args.policy, "states": model.state_space.size,
           "unit": "block interval" if args.protocol == "sop" or args.normalization == "time"
           else "main-chain block"}
    t0 = time.time()
    if args.load_policy:
        policy = tuple(int(x) for x in np.load(args.load_policy)["policy"])
        if len(policy) != model.state_space.size:
            raise ValueError("the saved policy does not fit this model")
        out["loaded_policy"] = args.load_policy
    elif args.policy == "optimal":
        policy, value, iterations = solve(model, args.solver, args.horizon, args.epsilon, args.max_iter)
        out.update({"solver": args.solver, "horizon": args.horizon, "value": value,
                    "iterations": iterations})
    elif args.protocol != "nakamoto":
        raise ValueError("only the optimal policy is defined for this protocol")
    elif args.policy == "honest":
        policy = model.build_honest_policy()
    else:
        policy = model.build_sm1_policy()
    out["solve_s"] = round(time.time() - t0, 1)
    if args.save_policy:
        np.savez_compressed(args.save_policy, policy=np.array(policy, dtype=np.int8), args=json.dumps(vars(args)))
        out["saved_policy"] = args.save_policy

    t0 = time.time()
    out["profile"] = reorg_profile(model, policy, max_report_depth=args.max_report_depth,
                                   method=args.stationary)
    out["stationary"] = args.stationary
    out["profile_s"] = round(time.time() - t0, 1)
    if args.mc_steps:
        t0 = time.time()
        out["mc"] = simulate_profile(model, policy, args.mc_steps, seed=args.seed,
                                     max_report_depth=args.max_report_depth)
        out["mc_s"] = round(time.time() - t0, 1)
    if args.exact_objects:
        if args.protocol != "sop":
            raise ValueError("--exact-objects applies to sop")
        t0 = time.time()
        out["exact"] = exact_rate(model, policy, args.exact_objects, seed=args.seed)
        out["exact_s"] = round(time.time() - t0, 1)
    out["honest_value"] = model.get_honest_revenue()
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
