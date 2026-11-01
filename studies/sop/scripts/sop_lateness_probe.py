#!/usr/bin/env python3
"""Can a Share-or-Perish pair say SWITCH in both directions?

MRL #146 times lateness against "the main chain block of the same height".
If that means the CURRENT main block, after a switch it is a different one,
so a pair's weights can depend on which branch the node is on, even under
the symmetric n_f rule ("either" in sop_oracle.decide). The issue's
2026-10-15 revision fixes the reference per height (the first block there
to join the node's main chain), which removes the dependence; records that
log it ("ref", log v2) replay with it.

  example   the hand-worked honest race below, under both n_f rules
  replay    every logged SIM-SoP-DEC decision that switched: recompute it
            forward, then from the other side (the node's view right after
            the switch), under both n_f rules, and count reverse SWITCHes

Usage:
  python -m scripts.sop_lateness_probe example
  python -m scripts.sop_lateness_probe replay RUN_DIR [RUN_DIR ...]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from scripts.sop_oracle import decide, parse_log_line

RULES = ("alt", "either")


def reverse(rec: dict) -> dict:
    """The same pair as seen by the node right after it switched: the old
    alt branch is now main, the displaced main branch is the alt one."""
    alt = rec.get("alt") or []
    main = rec.get("main") or []
    r = dict(rec)
    r["alt"], r["main"] = main, alt
    if alt:
        r["top"] = max(b["h"] for b in alt)
    r["reinsert"] = False
    return r


def example_race(d_ms: int = 5000, fixed_ref: bool = False) -> dict:
    """Two honest blocks at one height, seen 4 s apart, both far under k*w.

    X (main) is seen at t = 0 with 3 shares seen 2-4 s before it.
    Y (alt) is seen at t = 4 s with 2 shares seen 9-10 s before X.

    fixed_ref: log the v2 reference the revised #146 (2026-10-15) uses, X's
    seen time (X joined the main chain first), on both blocks; a switch no
    longer moves it.
    """
    def blk(seen, shares):
        b = {"h": 1000, "id": "x" if seen == 0 else "y", "diff": "1216",
             "seen": seen, "n_sh": len(shares),
             "shares": [{"id": "s", "seen": t} for t in shares]}
        if fixed_ref:
            b["ref"] = 0
        return b
    x = blk(0, [-4000, -3000, -2000])
    y = blk(4000, [-10000, -9000])
    return {"mode": "whole_branch", "reinsert": False, "h0": 994, "hf": 1000,
            "top": 1000, "w": 16, "k": 3, "d_ms": d_ms, "alt": [y], "main": [x]}


def both_ways(rec: dict, nf_rule: str) -> tuple[dict, dict]:
    return decide(rec, nf_rule), decide(reverse(rec), nf_rule)


def _cmd_example() -> int:
    for label, fixed in (("moving reference", False), ("fixed reference", True)):
        rec = example_race(fixed_ref=fixed)
        for rule in RULES:
            fwd, rev = both_ways(rec, rule)
            print(f"{label}, n_f rule {rule}: on X: Y {fwd['w_alt']} vs X {fwd['w_main']} -> "
                  f"{fwd['expected']} ({fwd['regime']}); on Y: X {rev['w_alt']} vs "
                  f"Y {rev['w_main']} -> {rev['expected']} ({rev['regime']})")
    return 0


def iter_records(run_dir: Path):
    for log in sorted(run_dir.glob("daemon_logs/*/bitmonero.log")):
        node = log.parent.name
        with open(log, errors="replace") as fh:
            for line in fh:
                if "SIM-SoP-DEC " not in line:
                    continue
                rec = parse_log_line(line)
                if rec is not None:
                    yield node, rec


def replay(run_dirs: list[Path]) -> Counter:
    """Count, per n_f rule, logged switches that would switch straight back."""
    c: Counter = Counter()
    for run_dir in run_dirs:
        for node, rec in iter_records(run_dir):
            if rec.get("skipped") or (rec.get("mode") == "whole_branch"
                                      and rec.get("reinsert")):
                continue
            c["decisions"] += 1
            for rule in RULES:
                fwd, rev = both_ways(rec, rule)
                if fwd["expected"] != "SWITCH":
                    continue
                c[f"{rule}:switch"] += 1
                c[f"{rule}:switch:{fwd['regime']}"] += 1
                if rev["expected"] == "SWITCH":
                    c[f"{rule}:back"] += 1
                    c[f"{rule}:back:fwd_{fwd['regime']}:rev_{rev['regime']}"] += 1
                elif rev["expected"] == "TIE":
                    c[f"{rule}:back_tie"] += 1
    return c


def _cmd_replay(paths: list[str]) -> int:
    run_dirs = [Path(p) for p in paths]
    c = replay(run_dirs)
    print(f"runs={len(run_dirs)} decisions={c['decisions']}")
    for rule in RULES:
        sw = c[f"{rule}:switch"]
        back = c[f"{rule}:back"]
        print(f"n_f rule {rule}: switch={sw} "
              f"(subjective {c[f'{rule}:switch:subjective']}, "
              f"objective {c[f'{rule}:switch:objective']}); "
              f"would switch straight back={back}; tie on the way back="
              f"{c[f'{rule}:back_tie']}")
        for key in sorted(k for k in c if k.startswith(f"{rule}:back:")):
            print(f"    {key.split(':', 2)[2]}: {c[key]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("example")
    p = sub.add_parser("replay")
    p.add_argument("run_dirs", nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "example":
        return _cmd_example()
    return _cmd_replay(args.run_dirs)


if __name__ == "__main__":
    sys.exit(main())
