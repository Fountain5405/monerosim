#!/usr/bin/env python3
"""Decision histograms of param_stubborn in the race model, for the comparison
with a sim cell's attacker log (2026-10-26, the a047 cell: 36 reveals per 72 h
where the model expects ~85). Rolls the policy out and, at every decision
with a branch (a > 0 or h > 0), records the action and the observation, then
prints: actions at (a == 0, h >= 1); the distribution of pa, ph and -D there;
actions at (a >= 1, h >= 1); and the per-72 h rates of reveals, give-ups with
and without blocks, and publishes.

    python scripts/sop_decision_hist.py --alpha 0.47 --days 72h-equivalents ... --knobs "G=6 L=1 M=1 R=1 Z=1"
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sop_attacker_search import parse_grid
from scripts.sop_policy import ACTION_NAMES, GIVE_UP, PUBLISH, REVEAL, param_stubborn
from scripts.sop_rl import legal_fallback, race_env


def histograms(alpha: float, days: float, seed: int, knobs: dict) -> dict:
    env = race_env(alpha, days, seed)
    W = env.window_obs
    acts0, acts1 = Counter(), Counter()
    starts = []          # (pa, ph, honest objects, deficit) at the first decision of a race begun by an honest block
    give_ups_0 = give_ups_b = reveals = publishes = 0
    prev_h = 0
    o = env.obs()
    while not env.done:
        a, D, xa, pa, h, xh, ph = o
        act = legal_fallback(param_stubborn(o, W=W, **knobs), env.legal())
        if a == 0 and h >= 1:
            acts0[ACTION_NAMES[act]] += 1
            if prev_h == 0:
                starts.append((pa, ph, -D, -D + ph - pa))
        elif a >= 1 and h >= 1:
            acts1[ACTION_NAMES[act]] += 1
        if act == GIVE_UP:
            if a == 0:
                give_ups_0 += 1
            else:
                give_ups_b += 1
        elif act == REVEAL:
            reveals += 1
        elif act == PUBLISH:
            publishes += 1
        prev_h = h
        o, _, _ = env.step(act)
    per72 = 3.0 / days

    def q(vals):
        s = sorted(vals)
        return {"n": len(s), "mean": round(sum(s) / len(s), 2) if s else None,
                "p10": s[len(s) // 10] if s else None, "p50": s[len(s) // 2] if s else None,
                "p90": s[9 * len(s) // 10] if s else None}

    return {"acts_a0_h1": dict(acts0), "acts_a1_h1": dict(acts1),
            "race_starts": {"pa": q([s[0] for s in starts]), "ph": q([s[1] for s in starts]),
                            "honest_objects": q([s[2] for s in starts]), "deficit": q([s[3] for s in starts]),
                            "deficit_over_G": sum(1 for s in starts if s[3] > knobs.get("G", 5)) / max(1, len(starts))},
            "per72h": {"reveals": reveals * per72, "give_ups_no_block": give_ups_0 * per72,
                       "give_ups_with_blocks": give_ups_b * per72, "publishes": publishes * per72,
                       "race_starts": len(starts) * per72},
            "share": env.stats.attacker_revenue_share, "days": days}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alpha", type=float, required=True)
    ap.add_argument("--days", type=float, default=300.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--knobs", default="G=6 L=1 M=1 R=1 Z=1")
    args = ap.parse_args(argv)
    knobs = parse_grid(args.knobs)[0]
    h = histograms(args.alpha, args.days, args.seed, knobs)
    import json
    print(json.dumps(h, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
