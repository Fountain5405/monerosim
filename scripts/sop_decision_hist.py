#!/usr/bin/env python3
"""Decision histograms of param_stubborn in the race model, for the comparison
with a sim cell's attacker log (2026-10-26, the first-round a047 cell: 15
reveals per 1,000 found blocks where the model expects 40). Rolls the policy out and, at every decision
with a branch (a > 0 or h > 0), records the action and the observation, then
prints: actions at (a == 0, h >= 1); the distribution of pa, ph and -D there;
actions at (a >= 1, h >= 1); and the rates of reveals, give-ups with and
without blocks, publishes and race starts, per 72 h and per 1,000 found
blocks. Compare the model with a sim per found block only: the model's 72 h
is 2,160 found blocks, a sim's 72 h holds 1.4-1.6x that.

    python scripts/sop_decision_hist.py --alpha 0.47 --days 72h-equivalents ... --knobs "G=6 L=1 M=1 R=1 Z=1"
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))



def q(vals):
    s = sorted(vals)
    return {"n": len(s), "mean": round(sum(s) / len(s), 2) if s else None,
            "p10": s[len(s) // 10] if s else None, "p50": s[len(s) // 2] if s else None,
            "p90": s[9 * len(s) // 10] if s else None}


def histograms(alpha: float, days: float, seed: int, knobs: dict, perish: bool = False,
               K: int | None = None, w: int | None = None) -> dict:
    from scripts.sop_policy import ACTION_NAMES, GIVE_UP, PUBLISH, REVEAL, param_stubborn
    from scripts.sop_rl import legal_fallback, race_env   # numpy: the model side only
    env = race_env(alpha, days, seed, K=K, w=w, perish=perish)   # K, w: race_env's defaults 3, 16
    W = env.window_obs
    acts0, acts1 = Counter(), Counter()
    starts = []          # (pa, ph, honest objects, deficit) at the first decision of a race begun by an honest block
    give_ups_0 = give_ups_b = reveals = publishes = 0
    reveal_ah = Counter()
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
            reveal_ah[str((a, h))] += 1
        elif act == PUBLISH:
            publishes += 1
        prev_h = h
        o, _, _ = env.step(act)
    per72 = 3.0 / days
    st = env.stats
    found = st.att_final_blocks + st.att_orphaned_blocks + st.hon_final_blocks + sum(st.reorg_depths)
    counts = {"reveals": reveals, "give_ups_no_block": give_ups_0, "give_ups_with_blocks": give_ups_b,
              "publishes": publishes, "race_starts": len(starts)}
    return {"acts_a0_h1": dict(acts0), "acts_a1_h1": dict(acts1),
            "race_starts": {"pa": q([s[0] for s in starts]), "ph": q([s[1] for s in starts]),
                            "honest_objects": q([s[2] for s in starts]), "deficit": q([s[3] for s in starts]),
                            "deficit_over_G": sum(1 for s in starts if s[3] > knobs.get("G", 5)) / max(1, len(starts))},
            "per72h": {"reveals": reveals * per72, "give_ups_no_block": give_ups_0 * per72,
                       "give_ups_with_blocks": give_ups_b * per72, "publishes": publishes * per72,
                       "race_starts": len(starts) * per72},
            "reveal_ah": dict(reveal_ah.most_common(12)),
            "found": found, "per_1000_found": {k: v / found * 1000 for k, v in counts.items()} if found else {},
            "share": env.stats.attacker_revenue_share, "days": days, "window_obs": W}


LEARNED = re.compile(r"^((2000-\d\d-\d\d \d\d:\d\d:\d\d),\d+) - attacker-miner - SelfishMinerAgent\[attacker-miner\] - "
                     r"DEBUG - learned: obs=\(([-\d, ]+)\) key=.* action=(\w+)")
RELEASE = re.compile(r"^(2000-\d\d-\d\d \d\d:\d\d:\d\d,\d+) - attacker-miner - SelfishMinerAgent\[attacker-miner\] - "
                     r"INFO - \w+: reveal fork=")
TERMINAL = ("give_up", "publish", "reveal")


def sim_histograms(lines, G: int = 6, found: float = 0.0) -> dict:
    """The same tallies from a sim run's attacker log (the "learned: obs=... action=..."
    DEBUG lines, one handler's copy, exact duplicates dropped). The sim decides per
    poll, not per object, and logs no decision at a == h == 0, so a race start is a
    line with a == 0 and h >= 1 right after a race-ending action or an h == 0 line;
    rates are per 72 h of the logged span and, given the run's found blocks
    (canonical / (1 - network orphan rate)), per 1,000 found blocks: the only
    basis comparable with the model (whose 72 h is 2,160 found blocks). A reveal
    counts only when the agent released it (an INFO '<strategy>: reveal fork='
    line at the decision's timestamp); a reveal decision the agent's own
    acceptance test held back (suppressed_reveals) is counted apart. With no
    release lines in the input every reveal decision counts."""
    import datetime as dt
    seen, ev, released = set(), [], set()
    for ln in lines:
        r = RELEASE.match(ln)
        if r:
            released.add(r.group(1))
            continue
        m = LEARNED.match(ln)
        if not m or m.group(0) in seen:
            continue
        seen.add(m.group(0))
        t = dt.datetime.strptime(m.group(2), "%Y-%m-%d %H:%M:%S")
        ev.append((t, tuple(int(x) for x in m.group(3).split(",")), m.group(4), m.group(1)))
    if not ev:
        return {"hours": 0.0}
    hours = (ev[-1][0] - ev[0][0]).total_seconds() / 3600.0
    per = 72.0 / hours if hours else 0.0
    starts, reveal_ah = [], Counter()
    n = Counter()
    prev_h, prev_act = 0, "publish"
    for _, (a, D, xa, pa, h, xh, ph), act, ts in ev:
        if act == "reveal":
            n["reveal_decisions"] += 1
            if released and ts not in released:
                act = "hold"            # suppressed by the agent's acceptance test: the race goes on
        if a == 0 and h >= 1 and (prev_h == 0 or prev_act in TERMINAL):
            starts.append((pa, ph, -D, -D + ph - pa))
        if act == "give_up":
            n["give_ups_no_block" if a == 0 else "give_ups_with_blocks"] += 1
        elif act == "reveal":
            n["reveals"] += 1
            reveal_ah[str((a, h))] += 1
        elif act == "publish":
            n["publishes"] += 1
        prev_h, prev_act = h, act
    return {"hours": hours,
            "race_starts": {"pa": q([s[0] for s in starts]), "ph": q([s[1] for s in starts]),
                            "honest_objects": q([s[2] for s in starts]), "deficit": q([s[3] for s in starts]),
                            "deficit_over_G": sum(1 for s in starts if s[3] > G) / max(1, len(starts))},
            "per72h": {k: n[k] * per for k in ("reveals", "reveal_decisions", "give_ups_no_block",
                                               "give_ups_with_blocks", "publishes")}
                      | {"race_starts": len(starts) * per},
            "found": found,
            "per_1000_found": ({k: n[k] / found * 1000 for k in ("reveals", "reveal_decisions", "give_ups_no_block",
                                                                 "give_ups_with_blocks", "publishes")}
                               | {"race_starts": len(starts) / found * 1000}) if found else {},
            "reveal_ah": dict(reveal_ah.most_common(12))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alpha", type=float)
    ap.add_argument("--sim-log", nargs="+", help="tally sim attacker logs instead of the model")
    ap.add_argument("--cell-json", help="the sim run's cell JSON (canonical_blocks, network_orphan_rate): "
                                        "rates per 1,000 found blocks")
    ap.add_argument("--days", type=float, default=300.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--knobs", default="G=6 L=1 M=1 R=1 Z=1")
    ap.add_argument("--perish", action="store_true", help="honest pending shares perish on an attacker publish")
    ap.add_argument("--K", type=int, help="window depth in blocks (default 3)")
    ap.add_argument("--w", type=int, help="shares per block (default 16); the window is (K - 1) * w objects")
    args = ap.parse_args(argv)
    knobs = {k: int(v) for k, v in (kv.split("=") for kv in args.knobs.split())}
    if args.sim_log:
        lines = []
        for f in args.sim_log:
            with open(f, errors="replace") as fh:
                lines += [ln for ln in fh if "learned: obs=" in ln or ": reveal fork=" in ln]
        found = 0.0
        if args.cell_json:
            import json as _json
            c = _json.load(open(args.cell_json))
            found = c["canonical_blocks"] / (1.0 - c["network_orphan_rate"])
        h = sim_histograms(lines, G=knobs.get("G", 6), found=found)
    else:
        h = histograms(args.alpha, args.days, args.seed, knobs, perish=args.perish, K=args.K, w=args.w)
    import json
    print(json.dumps(h, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
