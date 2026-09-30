#!/usr/bin/env python3
"""Share-or-Perish conformance oracle (docs/20260930_sop_conformance.md).

Recomputes every `SIM-SoP-DEC` fork-choice decision from its logged inputs
only (never from the daemon's own result fields) and flags disagreement.
Written from MRL #146 and the conventions in the doc above; independent of
`patches/monero-sim-pop.patch`.

Usage:
  python scripts/sop_oracle.py check RUN_DIR [RUN_DIR ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MARKER = "SIM-SoP-DEC "


def parse_log_line(line: str) -> dict | None:
    """The JSON object following the SIM-SoP-DEC marker, or None."""
    line = line.rstrip()
    idx = line.find(MARKER)
    if idx == -1:
        return None
    text = line[idx + len(MARKER):].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def decide(rec: dict) -> dict:
    """Recompute nf, regime, suffix weights and the expected outcome from
    the logged inputs (mode, reinsert, h0, hf, top, w, k, d_ms, alt, main)
    only. Never reads the daemon's own result fields."""
    mode = rec.get("mode")
    reinsert = bool(rec.get("reinsert"))
    h0, hf, top = rec["h0"], rec["hf"], rec["top"]
    w, k, d_ms = rec["w"], rec["k"], rec["d_ms"]
    alt = rec.get("alt") or []
    main = rec.get("main") or []
    main_by_h = {b["h"]: b for b in main}

    nf = sum(1 + b.get("n_sh", 0) for b in alt)

    # Convention 9: sim-only guard, the first alt block's difficulty below w
    # forces the objective regime.
    diff_alt0 = int(alt[0]["diff"]) if alt else 0
    window_open = h0 < hf and nf < k * w and diff_alt0 >= w
    regime = "subjective" if window_open else "objective"

    old_cutoff = top - 10 * w

    def block_weight(b: dict, self_is_main: bool) -> int:
        h = b["h"]
        diff = int(b["diff"])
        if h <= old_cutoff:
            return diff  # Table 3: old blocks weigh diff(h); shares weigh 0.
        unit = max(1, diff // w)
        if self_is_main:
            # The main chain block of height h is itself: trivially on time.
            main_seen = b.get("seen")
            block_seen = main_seen
        else:
            main_b = main_by_h.get(h)
            main_seen = main_b.get("seen") if main_b is not None else b.get("seen")
            block_seen = b.get("seen")
        l_b = 1
        if window_open and block_seen is not None and main_seen is not None \
                and block_seen - main_seen > d_ms:
            l_b = 0
        counted = 0
        for sh in b.get("shares") or []:
            share_seen = sh.get("seen")
            if share_seen is None:
                # Convention 4: a never-gossiped share is first seen inside
                # its containing block.
                share_seen = block_seen
            l_w = 1
            if window_open and main_seen is not None and share_seen is not None \
                    and main_seen - share_seen <= d_ms:
                l_w = 0
            if l_w:
                counted += 1
        return unit * l_b * (1 + counted)

    w_alt = sum(block_weight(b, False) for b in alt)
    w_main = sum(block_weight(b, True) for b in main)

    if w_alt > w_main:
        expected = "SWITCH"
    elif w_alt < w_main:
        expected = "KEEP"
    else:
        expected = "TIE"

    skip = mode == "whole_branch" and reinsert

    return {"nf": nf, "regime": regime, "w_alt": w_alt, "w_main": w_main,
            "expected": expected, "skip": skip}


def compare(rec: dict) -> list[str]:
    """Human-readable mismatches between the daemon's logged record and the
    oracle's recomputation; empty if they agree."""
    d = decide(rec)
    msgs: list[str] = []
    daemon_skipped = bool(rec.get("skipped"))

    if daemon_skipped and not d["skip"]:
        msgs.append("skipped=true outside a whole_branch reinsert")
        return msgs

    if d["skip"]:
        if not daemon_skipped:
            msgs.append("whole_branch reinsert was not skipped")
        if rec.get("result") != "KEEP":
            msgs.append(f"skipped record result {rec.get('result')!r} != KEEP")
        return msgs  # skipped records are not recomputed further.

    daemon_nf = int(rec["nf"])
    if daemon_nf != d["nf"]:
        msgs.append(f"nf {daemon_nf} != expected {d['nf']}")
    if rec.get("regime") != d["regime"]:
        msgs.append(f"regime {rec.get('regime')!r} != expected {d['regime']!r}")
    daemon_w_alt = int(rec["w_alt"])
    daemon_w_main = int(rec["w_main"])
    if daemon_w_alt != d["w_alt"]:
        msgs.append(f"w_alt {daemon_w_alt} != expected {d['w_alt']}")
    if daemon_w_main != d["w_main"]:
        msgs.append(f"w_main {daemon_w_main} != expected {d['w_main']}")

    if d["expected"] == "TIE":
        if not rec.get("tie") or rec.get("tie_draw") is None:
            msgs.append("expected a tie (equal weights) but tie/tie_draw not set")
    else:
        if rec.get("tie"):
            msgs.append(f"tie=true but weights differ (w_alt={d['w_alt']}, w_main={d['w_main']})")
        if rec.get("result") != d["expected"]:
            msgs.append(f"result {rec.get('result')!r} != expected {d['expected']!r}")

    return msgs


def check_log(path) -> dict:
    """Scan one daemon log; counts plus mismatch details."""
    path = Path(path)
    decisions = skipped = ties = mismatches = 0
    details = []
    with open(path, errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            rec = parse_log_line(line)
            if rec is None:
                continue
            decisions += 1
            d = decide(rec)
            if d["skip"]:
                skipped += 1
            elif d["expected"] == "TIE":
                ties += 1
            msgs = compare(rec)
            if msgs:
                mismatches += 1
                details.append({"file": str(path), "line": lineno, "messages": msgs})
    return {"decisions": decisions, "skipped": skipped, "ties": ties,
            "mismatches": mismatches, "details": details}


def _cmd_check(run_dirs: list[str]) -> int:
    any_empty = False
    total_mismatches = 0
    all_details = []
    for rd in run_dirs:
        rd = Path(rd)
        run_decisions = 0
        for log in sorted(rd.glob("daemon_logs/*/bitmonero.log")):
            node = log.parent.name
            rep = check_log(log)
            run_decisions += rep["decisions"]
            total_mismatches += rep["mismatches"]
            print(f"{node:30s} decisions={rep['decisions']} skipped={rep['skipped']} "
                  f"ties={rep['ties']} mismatches={rep['mismatches']}")
            all_details.extend(rep["details"])
        if run_decisions == 0:
            any_empty = True
    for d in all_details[:20]:
        print(f"  ! {d['file']}:{d['line']} {'; '.join(d['messages'])}")
    if any_empty:
        return 2
    if total_mismatches:
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("check")
    pc.add_argument("run_dirs", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return _cmd_check(a.run_dirs)
    return 2


if __name__ == "__main__":
    sys.exit(main())
