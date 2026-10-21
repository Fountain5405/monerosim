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


def pool_count(entries: list, major: int, rule: str = "slot") -> int:
    """Pool shares that count for a chain tip (convention 11): PoW-valid
    entries; rule "slot" keeps the first seen per slot and counts the
    contiguous run from `major`; rule "all" counts every valid entry."""
    ok = [e for e in entries if e.get("pow_ok")]
    if rule == "all":
        return len(ok)
    if rule != "slot":
        raise ValueError(f"unknown pool rule {rule!r}")
    slots = {e["slot"] for e in ok}
    n = 0
    while major + n in slots:
        n += 1
    return n


def _lateness_weight(b: dict, window_open: bool, w: int, d_ms: int) -> int:
    """One block's weight under a v2+ reference (`ref`), Tables 3-5."""
    diff = int(b["diff"])
    unit = max(1, diff // w)
    block_seen = b.get("seen")
    main_seen = b["ref"] if b.get("ref") is not None else block_seen
    l_b = 1
    if window_open and block_seen is not None and main_seen is not None \
            and block_seen - main_seen > d_ms:
        l_b = 0
    counted = 0
    for s in b.get("shares") or []:
        share_seen = s.get("seen") if s.get("seen") is not None else block_seen
        late = (window_open and main_seen is not None and share_seen is not None
                and main_seen - share_seen <= d_ms)
        counted += 0 if late else 1
    return unit * l_b * (1 + counted)


def decide_v4(rec: dict, pool_rule: str = "slot") -> dict:
    """The rule as edited 2026-10-16 and 2026-10-20 (conformance doc,
    "Revised 2026-10-16 and 2026-10-20"), from logged inputs only."""
    h0, hf, top = rec["h0"], rec["hf"], rec["top"]
    w, k, d_ms = rec["w"], rec["k"], rec["d_ms"]
    alt = rec.get("alt") or []
    main = rec.get("main") or []
    n_alt = sum(1 + b.get("n_sh", 0) for b in alt[1:])
    n_main = sum(1 + b.get("n_sh", 0) for b in main if b["h"] != hf)
    h_max = max(top, alt[-1]["h"] if alt else top)
    nakamoto = h_max - (hf - 1) >= 10 * w
    diff_alt0 = int(alt[0]["diff"]) if alt else 0
    window_open = (not nakamoto and rec["online"] and h0 < hf - 1
                   and max(n_alt, n_main) < (k - 1) * w and diff_alt0 >= w)
    regime = "nakamoto" if nakamoto else ("subjective" if window_open else "objective")

    pa = pm = 0
    if regime == "nakamoto":
        w_alt = sum(int(b["diff"]) for b in alt)
        w_main = sum(int(b["diff"]) for b in main)
    else:
        w_alt = sum(_lateness_weight(b, window_open, w, d_ms) for b in alt)
        w_main = sum(_lateness_weight(b, window_open, w, d_ms) for b in main)
        if regime == "objective":
            major = rec["major"]
            pa = pool_count(rec.get("pool_alt") or [], major, pool_rule)
            pm = pool_count(rec.get("pool_main") or [], major, pool_rule)
            w_alt += pa * max(1, int(rec["pool_diff_alt"]) // w)
            w_main += pm * max(1, int(rec["pool_diff_main"]) // w)
    expected = "SWITCH" if w_alt > w_main else ("KEEP" if w_alt < w_main else "TIE")
    skip = rec.get("mode") == "whole_branch" and bool(rec.get("reinsert"))
    return {"n_alt": n_alt, "n_main": n_main, "regime": regime, "w_alt": w_alt,
            "w_main": w_main, "pool_alt_counted": pa, "pool_main_counted": pm,
            "expected": expected, "skip": skip}


def decide(rec: dict, nf_rule: str | None = None) -> dict:
    """Recompute nf, regime, suffix weights and the expected outcome from
    the logged inputs (mode, reinsert, h0, online, hf, top, w, k, d_ms, alt,
    main) only. Never reads the daemon's own result fields.

    Lateness reference: a block entry carrying "ref" (log v2) is timed
    against it on both branches; older records time an alt block against
    the current main block at its height and a main block against itself.

    nf_rule "either" is the issue's rule since its 2026-10-15 revision
    (n_f = max(n_main, n_alt)): the regime is objective once either branch
    holds k*w work objects past the fork, and the only rule the daemon
    implements once its --sim-sop-nf-rule option is gone. "alt" is the
    earlier formal definition (the alt branch only), for older logs."""
    # Without an explicit rule, use the one the daemon logged
    # (--sim-sop-nf-rule); records from before that flag mean "alt".
    if rec.get("v", 1) >= 4:
        return decide_v4(rec)
    if nf_rule is None:
        nf_rule = rec.get("nf_rule", "alt")

    mode = rec.get("mode")
    reinsert = bool(rec.get("reinsert"))
    h0, hf, top = rec["h0"], rec["hf"], rec["top"]
    w, k, d_ms = rec["w"], rec["k"], rec["d_ms"]
    alt = rec.get("alt") or []
    main = rec.get("main") or []
    main_by_h = {b["h"]: b for b in main}

    nf = sum(1 + b.get("n_sh", 0) for b in alt)
    nf_main = sum(1 + b.get("n_sh", 0) for b in main)
    if nf_rule == "alt":
        under_kw = nf < k * w
    elif nf_rule == "either":
        under_kw = nf < k * w and nf_main < k * w
    else:
        raise ValueError(f"unknown nf_rule {nf_rule!r}")

    # Convention 9: sim-only guard, the first alt block's difficulty below w
    # forces the objective regime.
    diff_alt0 = int(alt[0]["diff"]) if alt else 0
    # Log v3 follows the revised #146: its h_f is the last common block, hf - 1
    # in the log (hf = the first alt block), and a node that has not come
    # online yet ("online": false) judges objectively. Older logs tested
    # h0 < hf.
    if rec.get("v", 1) >= 3:
        online_before_fork = rec["online"] and h0 < hf - 1
    else:
        online_before_fork = h0 < hf
    window_open = online_before_fork and under_kw and diff_alt0 >= w
    regime = "subjective" if window_open else "objective"

    old_cutoff = top - 10 * w

    def block_weight(b: dict, self_is_main: bool) -> int:
        h = b["h"]
        diff = int(b["diff"])
        if h <= old_cutoff:
            return diff  # Table 3: old blocks weigh diff(h); shares weigh 0.
        unit = max(1, diff // w)
        if "ref" in b:
            # Log v2 (#146 revised 2026-10-15): main_seen is fixed per height,
            # the seen time of the first block there to join the node's main
            # chain, the same on both branches; null when none has (alt
            # ahead, or heights loaded from disk): main_seen = block_seen.
            block_seen = b.get("seen")
            main_seen = b["ref"] if b["ref"] is not None else block_seen
        elif self_is_main:
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

    return {"nf": nf, "nf_main": nf_main, "regime": regime, "w_alt": w_alt,
            "w_main": w_main, "expected": expected, "skip": skip}


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

    if rec.get("v", 1) >= 4:
        for key in ("n_alt", "n_main", "pool_alt_counted", "pool_main_counted"):
            if int(rec.get(key, -1)) != d[key]:
                msgs.append(f"{key} {rec.get(key)} != expected {d[key]}")
    else:
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


def _pool_rule_changes(path) -> int:
    n = 0
    with open(path, errors="replace") as f:
        for line in f:
            rec = parse_log_line(line)
            if rec and rec.get("v", 1) >= 4 \
                    and decide_v4(rec, "all")["expected"] != decide_v4(rec)["expected"]:
                n += 1
    return n


def _cmd_check(run_dirs: list[str], pool_rule: str = "slot") -> int:
    changed = 0
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
            if pool_rule == "all":
                changed += _pool_rule_changes(log)
        if run_decisions == 0:
            any_empty = True
    if pool_rule == "all":
        print(f"pool-rule all changes {changed} outcomes")
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
    pc.add_argument("--pool-rule", choices=("slot", "all"), default="slot")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return _cmd_check(a.run_dirs, a.pool_rule)
    return 2


if __name__ == "__main__":
    sys.exit(main())
