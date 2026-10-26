#!/usr/bin/env python3
"""Parametric stubborn attackers against Share-or-Perish in the race model.

After the learned attacker's ladder stopped at step 3
(docs/20261026_sop_learned_attacker.md), the next lower bound on what SoP
concedes comes from the strongest HAND-WRITTEN rule we can find:
scripts/sop_policy.py::param_stubborn, the sim's window_stubborn noown rule
with six knobs (G give-up objects, L publish lead, M reveal margin, R reveal
depth, B block deficit, Z hold without blocks), evaluated on the race model
with the sims' settings (sop_rl.race_env: rule 20261020_noown, honest shares,
objects-deficit cap 200).

    python scripts/sop_attacker_search.py --alphas 0.45 0.48 0.50 --days 1000 \\
        --seeds 1 2 --workers 20 --grid "G=3,5,8,12,20,40 Z=0,1" \\
        --out data/sop_search/stage1.jsonl

Appends one JSON line per finished run (resumable: runs already in the file
are skipped), then prints the best combos per alpha and, for every combo run
at three or more alphas, the crossing where its share passes alpha. Each
worker is one race-model rollout (~80 MB); never run this on the control box.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

if __name__ == "__main__":   # run as `python scripts/sop_attacker_search.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sop_policy import param_stubborn
from scripts.sop_rl import legal_fallback, race_env, rollout

KNOBS = ("G", "L", "M", "R", "B", "Z")


def parse_grid(spec: str) -> List[Dict[str, int]]:
    """'G=3,5 Z=0,1' -> every combination as a knob dict; the empty spec is [{}]
    (all defaults, i.e. the sim's own rule)."""
    axes = []
    for item in spec.split():
        name, _, values = item.partition("=")
        if name not in KNOBS:
            raise ValueError(f"unknown knob {name!r}; knobs are {KNOBS}")
        axes.append([(name, int(v)) for v in values.split(",") if v != ""])
    return [dict(c) for c in itertools.product(*axes)] if axes else [{}]


def run_key(knobs: Dict[str, int], alpha: float, seed: int) -> str:
    return json.dumps({"knobs": {k: knobs[k] for k in sorted(knobs)}, "alpha": alpha, "seed": seed}, sort_keys=True)


def evaluate(knobs: Dict[str, int], alpha: float, days: float, seed: int) -> dict:
    """One rollout of param_stubborn(**knobs) on race_env(alpha, days, seed):
    share, reveals, reorg depths and the orphan rates the sims' cell JSONs
    report (attacker_orphan_rate, network_orphan_rate)."""
    env = race_env(alpha, days, seed)
    r = rollout(env, lambda o, legal: legal_fallback(param_stubborn(o, **knobs), legal), env.n_objects)
    st = env.stats
    hon_orphaned = sum(st.reorg_depths)
    found = st.att_final_blocks + st.att_orphaned_blocks + st.hon_final_blocks + hon_orphaned
    return {"knobs": dict(knobs), "alpha": alpha, "seed": seed, "days": days, "share": r["share"],
            "reveals": r["reveals"], "mean_reorg": r["mean_reorg"], "max_reorg": r["max_reorg"],
            "att_final": st.att_final_blocks, "att_orphaned": st.att_orphaned_blocks,
            "hon_final": st.hon_final_blocks, "hon_orphaned": hon_orphaned,
            "att_orphan_rate": st.attacker_orphan_fraction,
            "net_orphan_rate": (st.att_orphaned_blocks + hon_orphaned) / found if found else 0.0}


def crossing(points: Sequence[Tuple[float, float]]) -> Optional[float]:
    """The alpha where share - alpha first crosses zero, by linear interpolation
    between the sorted (alpha, share) points; None if it never does."""
    pts = sorted(points)
    for (a0, s0), (a1, s1) in zip(pts, pts[1:]):
        f0, f1 = s0 - a0, s1 - a1
        if f0 < 0 <= f1:
            return a0 + (a1 - a0) * (-f0) / (f1 - f0)
    return None


def _work(task):
    return evaluate(*task)


def _label(knobs: Dict[str, int]) -> str:
    return " ".join(f"{k}={knobs[k]}" for k in KNOBS if k in knobs) or "defaults"


def report(rows: List[dict], top: int = 5, out=sys.stdout) -> None:
    """Per alpha: the top combos by mean share over seeds (with the mean
    reveals per run and the orphan rates), then every combo's crossing."""
    groups: Dict[Tuple[str, float], List[dict]] = defaultdict(list)
    for r in rows:
        groups[(json.dumps(r["knobs"], sort_keys=True), r["alpha"])].append(r)
    alphas = sorted({a for _, a in groups})
    means: Dict[str, Dict[float, float]] = defaultdict(dict)
    for (kj, a), rs in groups.items():
        means[kj][a] = sum(r["share"] for r in rs) / len(rs)
    for a in alphas:
        print(f"alpha {a:.2f} (honest {a:.4f}):", file=out)
        ranked = sorted(((means[kj][a], kj) for kj in means if a in means[kj]), reverse=True)
        for share, kj in ranked[:top]:
            rs = groups[(kj, a)]
            n = len(rs)
            print(f"  {share:.4f}  {_label(json.loads(kj)):28s} seeds {n}  reveals {sum(r['reveals'] for r in rs) / n:.0f}/run"
                  f"  att_orphan {sum(r['att_orphan_rate'] for r in rs) / n:.3f}"
                  f"  net_orphan {sum(r['net_orphan_rate'] for r in rs) / n:.3f}"
                  f"  reorg {sum(r['mean_reorg'] for r in rs) / n:.2f}/{max(r['max_reorg'] for r in rs)}", file=out)
    xs = []
    for kj, by_alpha in means.items():
        if len(by_alpha) >= 3:
            c = crossing(sorted(by_alpha.items()))
            xs.append((c if c is not None else 9.0, kj))
    if xs:
        print("crossings (share passes alpha; interpolated):", file=out)
        for c, kj in sorted(xs)[:max(top, 10)]:
            print(f"  {('%.4f' % c) if c < 9 else 'none  '}  {_label(json.loads(kj))}", file=out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alphas", type=float, nargs="+", required=True)
    ap.add_argument("--days", type=float, default=1000.0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--grid", default="", help="e.g. 'G=3,5,8 Z=0,1'; knobs not named keep their defaults")
    ap.add_argument("--fixed", default="", help="knobs fixed for every combo, e.g. 'Z=1 L=2'")
    ap.add_argument("--out", required=True, help="JSON lines, appended; existing runs are skipped")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args(argv)
    fixed = parse_grid(args.fixed)
    if len(fixed) != 1:
        raise SystemExit("--fixed takes one value per knob")
    combos = [dict(fixed[0], **c) for c in parse_grid(args.grid)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: List[dict] = []
    done = set()
    if out.exists():
        for line in out.open():
            if line.strip():
                r = json.loads(line)
                rows.append(r)
                done.add(run_key(r["knobs"], r["alpha"], r["seed"]))
    tasks = [(c, a, args.days, s) for c in combos for a in args.alphas for s in args.seeds
             if run_key(c, a, s) not in done]
    print(f"{len(combos)} combos x {len(args.alphas)} alphas x {len(args.seeds)} seeds at {args.days:g} d: "
          f"{len(tasks)} runs to do, {len(done)} already in {out}", file=sys.stderr, flush=True)
    t0 = time.time()
    if tasks:
        with Pool(args.workers) as pool, out.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(_work, tasks), 1):
                f.write(json.dumps(r) + "\n")
                f.flush()
                rows.append(r)
                if i % 10 == 0 or i == len(tasks):
                    print(f"  {i}/{len(tasks)} done [{time.time() - t0:.0f}s]", file=sys.stderr, flush=True)
    report(rows, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
