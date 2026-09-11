#!/usr/bin/env python3
"""Native-mining DAA (difficulty-adjustment) analysis for a finished run.

Reads every miner's daemon stdout under
`<run_dir>/shadow.data/hosts/<miner>/monerod*.stdout`, builds the accepted
block-by-block chain (height, sim time, miner, difficulty, interval), splits
it into a "pre"/"post" late-joiner regime (derived or given via
--join-time), and checks the result against a set of pre-registered
expectations for monerod's own LWMA difficulty adjustment under native
mining (docs/NATIVE_MINING.md). See the module docstring in
scripts/native_mining_check.py for the underlying log-format assumptions;
this script reuses its FOUND/REJECT regexes.

The end-difficulty and last-2h cadence verdicts (4 and 5) compare the run
against monerod's own get_difficulty_for_next_block window formula (120 x
hashes performed inside that window / window time-span), not a fixed
post-join-equilibrium band, because that window has not converged to
120*sum(hashrate) after only a few hundred blocks. See theory_difficulty_at
/ theory_difficulty_at_time / expected_blocks below.

Usage:
    python3 scripts/native_daa_analysis.py <run_dir> [--join-time 4h]
        [--out <dir>] [--png]

Outputs (default --out <run_dir>/analysis_output/native_daa/):
    blocks.csv    - one row per accepted block
    report.md     - tables (a)-(g) described in the task, also printed
    difficulty_and_intervals.png (only with --png and matplotlib installed)

Exit codes:
    0  all applicable verdicts PASS
    1  at least one applicable verdict FAILed
    2  run_dir / input_config.yaml missing, or zero blocks found
"""
import argparse
import csv
import glob
import math
import os
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

import yaml

# scripts/ package import (matches scripts/smoke_assertions.py's convention).
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.native_mining_check import FOUND, REJECT  # noqa: E402  (do not modify that module)

STALE = re.compile(r"found block at height (\d+) was not added to the main chain")

_SIM_EPOCH = datetime(2000, 1, 1)
_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smh]?)\s*$")
_DURATION_MULT = {"s": 1.0, "m": 60.0, "h": 3600.0}

# monerod's next_difficulty window (src/cryptonote_basic/difficulty.cpp,
# blockchain.cpp get_difficulty_for_next_block).
DIFFICULTY_TARGET = 120.0
DIFFICULTY_WINDOW = 720
DIFFICULTY_CUT = 60
DIFFICULTY_LAG = 15
DIFFICULTY_BLOCKS_COUNT = 735


# ----------------------------------------------------------------------
# Time parsing
# ----------------------------------------------------------------------
def parse_duration(value) -> float:
    """Parse a YAML duration like '0s', '4s', '14400s', '4h', '10m' to seconds.

    Bare numbers (int/float, or a numeric string with no unit) are treated
    as seconds. Raises ValueError on anything else.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return 0.0
    m = _DURATION_RE.match(str(value))
    if not m:
        raise ValueError(f"cannot parse duration: {value!r}")
    n = float(m.group(1))
    unit = m.group(2) or "s"
    return n * _DURATION_MULT[unit]


def parse_sim_ts(ts_str: str) -> float:
    """Parse a '2000-01-01 HH:MM:SS.mmm'-style sim timestamp to seconds since
    the sim epoch (2000-01-01 00:00:00). datetime handles day rollover
    ('2000-01-02 ...') transparently since the date is part of the parse.
    """
    dt_obj = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    return (dt_obj - _SIM_EPOCH).total_seconds()


# ----------------------------------------------------------------------
# input_config.yaml
# ----------------------------------------------------------------------
def load_config(cfg_path: Path) -> dict:
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f) or {}
    general = cfg.get("general", {}) or {}
    mining_mode = ((general.get("mining") or {}).get("mode"))
    stop_time_raw = general.get("stop_time")
    stop_time_s = None
    if stop_time_raw is not None:
        try:
            stop_time_s = parse_duration(stop_time_raw)
        except ValueError:
            stop_time_s = None

    miners = {}
    for aid, adef in (cfg.get("agents") or {}).items():
        if not isinstance(adef, dict) or "hashrate" not in adef:
            continue
        try:
            hashrate = float(adef["hashrate"])
        except (TypeError, ValueError):
            continue
        try:
            start_s = parse_duration(adef.get("start_time", "0s"))
        except ValueError:
            start_s = 0.0
        miners[aid] = {"hashrate": hashrate, "start_s": start_s}

    return {"mining_mode": mining_mode, "stop_time_s": stop_time_s, "miners": miners}


# ----------------------------------------------------------------------
# Block-log parsing
# ----------------------------------------------------------------------
def parse_one_file(path: str, miner_id: str) -> list:
    """Return raw (unmerged, undeduped) FOUND entries for one stdout file,
    with entries that a subsequent STALE line marks as a lost race/stale
    template flagged stale=True. Never raises on a malformed line.
    """
    entries = []
    try:
        fh = open(path, errors="replace")
    except OSError:
        return entries
    with fh:
        for line in fh:
            m = None
            try:
                m = FOUND.match(line)
            except Exception:
                m = None
            if m:
                try:
                    entries.append({
                        "miner": miner_id,
                        "height": int(m.group(3)),
                        "sim_time_s": parse_sim_ts(m.group(1)),
                        "difficulty": int(m.group(4)),
                        "stale": False,
                    })
                except (ValueError, IndexError):
                    pass
                continue
            sm = STALE.search(line)
            if sm:
                try:
                    h = int(sm.group(1))
                except ValueError:
                    continue
                for e in reversed(entries):
                    if e["height"] == h and not e["stale"]:
                        e["stale"] = True
                        break
    return entries


def parse_all_miners(run_dir: Path, miner_ids) -> list:
    raw = []
    missing = []
    for mid in miner_ids:
        pattern = str(run_dir / "shadow.data" / "hosts" / mid / "monerod*.stdout")
        files = sorted(glob.glob(pattern))
        if not files:
            missing.append(mid)
            continue
        for f in files:
            raw.extend(parse_one_file(f, mid))
    if missing:
        print(f"warning: no monerod stdout found for miner(s): {', '.join(missing)}",
              file=sys.stderr)
    return raw


def build_accepted(raw_entries: list) -> list:
    """Drop stale-flagged finds, then dedupe same-height races (a handful of
    early trivial-difficulty blocks each miner briefly "successfully adds"
    to its own local view before losing the race - no STALE line is ever
    logged for those) by keeping the earliest-timestamped entry per height.
    This mirrors block_time_analysis.py's dedupe-by-height convention and is
    verified against both fixture archives: unique-height counts after
    dedupe match summary.txt's "Blocks mined" exactly.
    """
    non_stale = [e for e in raw_entries if not e["stale"]]
    non_stale.sort(key=lambda e: (e["height"], e["sim_time_s"]))
    accepted = []
    seen = set()
    for e in non_stale:
        if e["height"] in seen:
            continue
        seen.add(e["height"])
        accepted.append({
            "height": e["height"],
            "sim_time_s": e["sim_time_s"],
            "miner": e["miner"],
            "difficulty": e["difficulty"],
        })
    accepted.sort(key=lambda r: r["height"])
    return accepted


def attach_intervals(accepted: list) -> None:
    prev = None
    for r in accepted:
        r["interval_s"] = None if prev is None else r["sim_time_s"] - prev["sim_time_s"]
        prev = r


def derive_join_time(miners: dict):
    """Earliest start_time among miners starting after 60s, else None."""
    late = sorted(info["start_s"] for info in miners.values() if info["start_s"] > 60.0)
    return late[0] if late else None


def assign_regimes(accepted: list, join_time) -> None:
    for r in accepted:
        if join_time is None:
            r["regime"] = "n/a"
        else:
            r["regime"] = "pre" if r["sim_time_s"] < join_time else "post"


def count_relay_rejections(run_dir: Path) -> int:
    count = 0
    pattern = str(run_dir / "shadow.data" / "hosts" / "relay-*" / "monerod*.stdout")
    for f in glob.glob(pattern):
        try:
            with open(f, errors="replace") as fh:
                for line in fh:
                    if REJECT.search(line):
                        count += 1
        except OSError:
            continue
    return count


def parse_summary_fields(path: Path) -> dict:
    if not path.is_file():
        return {}
    text = path.read_text(errors="replace")
    out = {}
    for label, key in [
        ("Wall time", "wall_time"),
        ("Sync", "sync"),
        ("Nodes online", "nodes_online"),
        ("Blocks mined", "blocks_mined"),
        ("Created", "tx_created"),
        ("In blocks", "tx_in_blocks"),
    ]:
        m = re.search(rf"{re.escape(label)}:\s+(\S.*)$", text, re.MULTILINE)
        if m:
            out[key] = m.group(1).strip()
    return out


# ----------------------------------------------------------------------
# Statistics / tables
# ----------------------------------------------------------------------
def per_hour_table(accepted: list) -> list:
    if not accepted:
        return []
    max_hour = int(accepted[-1]["sim_time_s"] // 3600)
    rows = []
    last_diff = None
    for h in range(max_hour + 1):
        lo, hi = h * 3600, (h + 1) * 3600
        in_hour = [r for r in accepted if lo <= r["sim_time_s"] < hi]
        intervals = [r["interval_s"] for r in in_hour if r["interval_s"] is not None]
        if in_hour:
            last_diff = in_hour[-1]["difficulty"]
        rows.append({
            "hour": h + 1,  # 1-indexed for display
            "blocks": len(in_hour),
            "mean_interval": statistics.mean(intervals) if intervals else None,
            "median_interval": statistics.median(intervals) if intervals else None,
            "mean_difficulty": statistics.mean(r["difficulty"] for r in in_hour) if in_hour else None,
            "difficulty_at_hour_end": last_diff,
        })
    return rows


def per_regime_miner_table(accepted: list, miners: dict, join_time) -> dict:
    """share/expected-share/sigma/verdict per miner, per applicable regime.

    "Active" miners for a regime: for 'pre' (or 'n/a', the whole-run
    stand-in when there is no late joiner), miners that started before the
    join; for 'post', all miners (by the time the post regime starts,
    everyone declared in the config has joined - see derive_join_time).
    """
    if join_time is None:
        regimes = {"n/a": dict(miners)}
    else:
        pre_active = {m: info for m, info in miners.items() if info["start_s"] < join_time}
        post_active = dict(miners)
        regimes = {"pre": pre_active, "post": post_active}

    table = {}
    for regime, active in regimes.items():
        rows_r = [r for r in accepted if r["regime"] == regime]
        n = len(rows_r)
        total_hr = sum(info["hashrate"] for info in active.values())
        out_rows = []
        for m, info in active.items():
            found = sum(1 for r in rows_r if r["miner"] == m)
            expected = 100.0 * info["hashrate"] / total_hr if total_hr else None
            if n > 0 and expected is not None:
                share = 100.0 * found / n
                p = info["hashrate"] / total_hr
                sigma = 100.0 * math.sqrt(p * (1 - p) / n)
                if sigma > 0:
                    verdict = "PASS" if abs(share - expected) <= 2.5 * sigma else "FAIL"
                else:
                    verdict = "PASS" if abs(share - expected) < 1e-9 else "FAIL"
            else:
                share, sigma, verdict = None, None, "N/A"
            out_rows.append({
                "miner": m, "n_regime": n, "found": found, "share": share,
                "expected": expected, "sigma": sigma, "verdict": verdict,
            })
        table[regime] = out_rows
    return table


def difficulty_value_at(accepted: list, t: float):
    candidates = [r for r in accepted if r["sim_time_s"] <= t]
    return candidates[-1]["difficulty"] if candidates else None


# ----------------------------------------------------------------------
# monerod difficulty-window theory
#
# In expectation, the sum of the difficulties of the blocks found inside a
# time interval equals the number of hashes performed in that interval
# (each hash succeeds with probability 1/D and contributes D). Modelling
# monerod's own next_difficulty window (see DIFFICULTY_* above) this way
# gives a difficulty prediction that tracks a not-yet-converged run
# (join-time hashrate steps, still-growing window) instead of assuming the
# fixed post-join equilibrium 120 * sum(all hashrate).
# ----------------------------------------------------------------------
def hashes_in(miners: dict, a: float, b: float) -> float:
    """Expected number of hashes performed by `miners` during [a, b)."""
    if b <= a:
        return 0.0
    total = 0.0
    for info in miners.values():
        total += info["hashrate"] * max(0.0, b - max(a, info["start_s"]))
    return total


def active_hashrate(miners: dict, t: float) -> float:
    """Sum of hashrate of miners already started (start_s <= t) at time t."""
    return sum(info["hashrate"] for info in miners.values() if info["start_s"] <= t)


def monerod_window(accepted: list, h: int):
    """(index_begin, index_end_exclusive) into `accepted` for the blocks
    monerod's next_difficulty would use to compute the difficulty of height
    h, applying the 735 / 720 / 600 rules (see module docstring). Returns
    None if fewer than 2 blocks are available for the window.

    accepted[i] is assumed to hold height i+1 (genesis, height 0, is never
    in the accepted list - verified against build_accepted's FOUND-based
    heights, which start at 1).
    """
    n = len(accepted)
    if n < 2 or h < 2:
        return None
    lo_h = max(1, h - DIFFICULTY_BLOCKS_COUNT)
    hi_h = h - 1
    if hi_h < lo_h:
        return None
    hi_h = min(hi_h, n)  # can't use blocks that don't exist yet
    begin = lo_h - 1  # index of height lo_h
    end = hi_h  # exclusive end index (index of height hi_h is hi_h - 1)
    if end - begin > DIFFICULTY_WINDOW:
        end = begin + DIFFICULTY_WINDOW  # keep the oldest 720, drop the DIFFICULTY_LAG=15 newest
    length = end - begin
    if length < 2:
        return None
    cut = DIFFICULTY_WINDOW - 2 * DIFFICULTY_CUT  # 600
    if length <= cut:
        cut_begin, cut_end = 0, length
    else:
        cut_begin = (length - cut + 1) // 2
        cut_end = cut_begin + cut
    idx_begin, idx_end = begin + cut_begin, begin + cut_end
    if idx_end - idx_begin < 2:
        return None
    return (idx_begin, idx_end)


def theory_difficulty_at(accepted: list, miners: dict, h: int):
    """D_theory(h) = 120 * hashes_in(window) / window span, using monerod's
    own difficulty window for height h. None if the window is unavailable
    or its span is 0.
    """
    window = monerod_window(accepted, h)
    if window is None:
        return None
    idx_begin, idx_end = window
    a = accepted[idx_begin]["sim_time_s"]
    b = accepted[idx_end - 1]["sim_time_s"]
    span = b - a
    if span <= 0:
        return None
    return DIFFICULTY_TARGET * hashes_in(miners, a, b) / span


def theory_difficulty_at_time(accepted: list, miners: dict, t: float):
    """D_theory for the next block after the last accepted block with
    sim_time_s <= t. None if there is no such block or the theory window
    is unavailable.
    """
    candidates = [r for r in accepted if r["sim_time_s"] <= t]
    if not candidates:
        return None
    h = candidates[-1]["height"] + 1
    return theory_difficulty_at(accepted, miners, h)


def expected_blocks(accepted: list, miners: dict, t0: float, t1: float, step_s: float = 60.0) -> float:
    """Numerical integral of active_hashrate(t) / theory_difficulty_at_time(t)
    over [t0, t1] (a step's contribution is skipped where the theory is
    unavailable). Each step is sampled at its midpoint.
    """
    if t1 <= t0:
        return 0.0
    total = 0.0
    t = t0
    while t < t1:
        seg_end = min(t + step_s, t1)
        mid = (t + seg_end) / 2.0
        theory = theory_difficulty_at_time(accepted, miners, mid)
        if theory:
            total += active_hashrate(miners, mid) / theory * (seg_end - t)
        t = seg_end
    return total


def difficulty_checkpoints(accepted: list, join_time, miners: dict) -> dict:
    if join_time is None:
        pre_hashrate = sum(info["hashrate"] for info in miners.values())
    else:
        pre_hashrate = sum(info["hashrate"] for info in miners.values() if info["start_s"] < join_time)
    post_hashrate = sum(info["hashrate"] for info in miners.values())
    checkpoints = {}
    if join_time is not None:
        for name, t in (
            ("at_join", join_time),
            ("join+1h", join_time + 3600),
            ("join+2h", join_time + 2 * 3600),
            ("join+3h", join_time + 3 * 3600),
        ):
            checkpoints[name] = difficulty_value_at(accepted, t)
            checkpoints[f"{name}_theory"] = theory_difficulty_at_time(accepted, miners, t)
    checkpoints["at_end"] = accepted[-1]["difficulty"] if accepted else None
    checkpoints["at_end_theory"] = (
        theory_difficulty_at_time(accepted, miners, accepted[-1]["sim_time_s"]) if accepted else None
    )
    return {
        "checkpoints": checkpoints,
        "d_pre_eq": 120.0 * pre_hashrate,
        "d_post_eq": 120.0 * post_hashrate,
    }


def interval_windows(accepted: list, join_time, stop_time_s) -> dict:
    pre_end = join_time if join_time is not None else float("inf")
    window_end = min(4 * 3600, pre_end)
    pre_h1_4 = [r["interval_s"] for r in accepted
                if r["interval_s"] is not None and r["sim_time_s"] < window_end]

    first20 = None
    if join_time is not None:
        post_rows = [r for r in accepted if r["sim_time_s"] >= join_time]
        first20 = [r["interval_s"] for r in post_rows[:20] if r["interval_s"] is not None]

    if stop_time_s is not None:
        run_end = stop_time_s
    elif accepted:
        run_end = accepted[-1]["sim_time_s"]
    else:
        run_end = 0.0
    last2h_start = max(0.0, run_end - 2 * 3600)
    last2h = [r["interval_s"] for r in accepted
              if r["interval_s"] is not None and r["sim_time_s"] >= last2h_start]

    return {"pre_h1_4": pre_h1_4, "first20": first20, "last2h": last2h, "run_end": run_end}


# ----------------------------------------------------------------------
# Verdicts
# ----------------------------------------------------------------------
def make_verdicts(accepted, miners, join_time, diffcp, windows, regime_table, reject_count) -> list:
    v = []

    # 1. pre-join plateau
    d_pre_eq = diffcp["d_pre_eq"]
    d_actual = None
    if accepted:
        if join_time is not None:
            pre_rows = [r for r in accepted if r["regime"] == "pre"]
            d_actual = pre_rows[-1]["difficulty"] if pre_rows else None
        else:
            d_actual = accepted[-1]["difficulty"]
    if d_actual is not None and d_pre_eq > 0:
        tol = 0.25 * d_pre_eq
        status = "PASS" if abs(d_actual - d_pre_eq) <= tol else "FAIL"
        detail = f"D={d_actual} target={d_pre_eq:.0f} (tol ±{tol:.0f})"
    else:
        status, detail = "N/A", "insufficient data"
    v.append(("pre-join plateau: |D - 120*sum(pre hashrate)| <= 25%", status, detail))

    # 2. pre-join hours 1-4 mean interval
    k = len(windows["pre_h1_4"])
    if k >= 3:
        mean_i = statistics.mean(windows["pre_h1_4"])
        tol = max(0.15 * 120.0, 2.5 * 120.0 / math.sqrt(k))
        status = "PASS" if abs(mean_i - 120.0) <= tol else "FAIL"
        detail = f"mean={mean_i:.1f}s n={k} (tol ±{tol:.1f}s)"
    else:
        status, detail = "N/A", f"only {k} interval(s)"
    v.append(("pre-join hours 1-4 mean interval within tol of 120s", status, detail))

    # 3. post-join burst
    if join_time is None:
        v.append(("post-join burst: mean of first 20 post-join intervals < 90s",
                   "N/A", "no late joiner"))
    else:
        f20 = windows["first20"]
        if f20:
            mean_f20 = statistics.mean(f20)
            status = "PASS" if mean_f20 < 90.0 else "FAIL"
            detail = f"mean={mean_f20:.1f}s n={len(f20)}"
        else:
            status, detail = "N/A", "no post-join blocks"
        v.append(("post-join burst: mean of first 20 post-join intervals < 90s", status, detail))

    # 4. end difficulty vs monerod's own difficulty-window theory (LWMA
    # legitimately overshoots its target by a few percent in either
    # direction, so this keeps the same +/-25% tolerance as the pre-join
    # plateau rule rather than a hard 1.0x ceiling - just centred on the
    # theory value instead of the fixed post-join equilibrium, since the
    # window has not converged to that equilibrium within this run).
    d_post_eq = diffcp["d_post_eq"]
    theory_end = diffcp["checkpoints"].get("at_end_theory")
    if accepted and theory_end:
        d_end = accepted[-1]["difficulty"]
        lo, hi = 0.75 * theory_end, 1.25 * theory_end
        status = "PASS" if lo <= d_end <= hi else "FAIL"
        ratio = d_end / theory_end
        detail = (f"D_end={d_end} theory={theory_end:.0f} ratio={ratio:.2f} "
                  f"(asymptote D_post_eq={d_post_eq:.0f})")
    else:
        status, detail = "N/A", "no blocks" if not accepted else "theory unavailable"
    v.append(("end difficulty within [0.75, 1.25] x theory", status, detail))

    # 5. last-2h block count vs monerod's own difficulty-window theory (a
    # Poisson count test, since the expected block interval is not 120s
    # while the window is still filling from a hashrate step).
    run_end = windows["run_end"]
    if run_end < 7200:
        status, detail = "N/A", "run shorter than 2h"
    else:
        lo2h = run_end - 7200
        n2h = len([r for r in accepted if lo2h <= r["sim_time_s"] <= run_end])
        expected = expected_blocks(accepted, miners, lo2h, run_end)
        if not expected:
            status, detail = "N/A", "theory unavailable"
        else:
            sigma = math.sqrt(expected)
            tol2 = max(3, 2.5 * sigma)
            status = "PASS" if abs(n2h - expected) <= tol2 else "FAIL"
            mean_l2 = statistics.mean(windows["last2h"]) if windows["last2h"] else None
            theory_mean = 7200.0 / expected
            detail = (f"n={n2h} expected={expected:.1f} "
                      f"(mean interval {fmt(mean_l2, 1)}s, theory mean {theory_mean:.1f}s)")
    v.append(("last-2h block count within 2.5 sigma of theory", status, detail))

    # 6. late miner share
    if join_time is None:
        v.append(("late miner share within 2.5 sigma of expected", "N/A", "no late joiner"))
    else:
        late_miners = [m for m, info in miners.items() if info["start_s"] >= join_time]
        post_rows = regime_table.get("post", [])
        found_any = False
        ok_all = True
        bits = []
        for m in late_miners:
            row = next((r for r in post_rows if r["miner"] == m), None)
            if row is None or row["verdict"] == "N/A":
                continue
            found_any = True
            ok_all &= (row["verdict"] == "PASS")
            bits.append(f"{m}: share={row['share']:.1f}% exp={row['expected']:.1f}% sigma={row['sigma']:.2f}")
        if not found_any:
            v.append(("late miner share within 2.5 sigma of expected", "N/A",
                      "no post-join blocks for late miner"))
        else:
            v.append(("late miner share within 2.5 sigma of expected",
                      "PASS" if ok_all else "FAIL", "; ".join(bits)))

    # 7. relay PoW rejections
    status = "PASS" if reject_count == 0 else "FAIL"
    v.append(("relay PoW rejections == 0", status, f"count={reject_count}"))

    return v


# ----------------------------------------------------------------------
# Output: CSV
# ----------------------------------------------------------------------
def write_csv(accepted: list, path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["height", "sim_time_s", "miner", "difficulty", "interval_s", "regime"])
        for r in accepted:
            w.writerow([
                r["height"],
                f"{r['sim_time_s']:.3f}",
                r["miner"],
                r["difficulty"],
                "" if r["interval_s"] is None else f"{r['interval_s']:.3f}",
                r["regime"],
            ])


# ----------------------------------------------------------------------
# Output: report.md / stdout
# ----------------------------------------------------------------------
def fmt(v, nd=1, suffix=""):
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.{nd}f}{suffix}"
    return f"{v}{suffix}"


def fmt_dur(s):
    if s is None:
        return "N/A"
    if s < 60:
        return f"{s:.1f}s"
    if s < 3600:
        return f"{s / 60:.1f}m"
    return f"{s / 3600:.2f}h"


def md_table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def render_report(run_id, cfg, join_time, join_source, hour_rows, regime_table,
                   diffcp, windows, verdicts, reject_count, summary_facts, accepted) -> str:
    lines = [f"# Native DAA analysis — {run_id}", ""]

    if cfg["mining_mode"] != "native":
        lines.append(f"**WARNING**: general.mining.mode = {cfg['mining_mode']!r}, expected 'native'.")
        lines.append("")

    miners = cfg["miners"]
    lines.append("## Miners (from input_config.yaml)")
    lines.append(md_table(["miner", "hashrate (h/s)", "start_time"],
                           [[m, fmt(info["hashrate"]), fmt_dur(info["start_s"])]
                            for m, info in sorted(miners.items())]))
    lines.append("")
    if join_time is None:
        lines.append("Join time / regime split: **N/A** (no miner starts after 60s; treated as a single regime).")
    else:
        lines.append(f"Join time: **{fmt_dur(join_time)}** ({join_time:.1f}s), source: {join_source}.")
    lines.append("")

    # (a) per-hour table
    lines.append("## (a) Per-hour block production")
    lines.append(md_table(
        ["hour", "blocks", "mean interval", "median interval", "mean difficulty", "difficulty at hour end"],
        [[r["hour"], r["blocks"], fmt(r["mean_interval"], 1, "s"), fmt(r["median_interval"], 1, "s"),
          fmt(r["mean_difficulty"], 0), fmt(r["difficulty_at_hour_end"], 0)]
         for r in hour_rows]))
    lines.append("")

    # (b) per-regime per-miner share
    lines.append("## (b) Per-regime per-miner share")
    for regime in ("pre", "post", "n/a"):
        rows = regime_table.get(regime)
        if rows is None:
            continue
        label = "all (no late joiner)" if regime == "n/a" else regime
        lines.append(f"### regime: {label}")
        lines.append(md_table(
            ["miner", "blocks found", "share %", "expected share %", "sigma", "verdict (2.5 sigma)"],
            [[r["miner"], r["found"], fmt(r["share"], 1), fmt(r["expected"], 1),
              fmt(r["sigma"], 2), r["verdict"]] for r in rows]))
        lines.append("")

    # (c) difficulty checkpoints
    lines.append("## (c) Difficulty checkpoints")
    cp = diffcp["checkpoints"]

    def _cp_row(label, name):
        measured, theory = cp.get(name), cp.get(f"{name}_theory")
        ratio = measured / theory if measured is not None and theory else None
        return [label, fmt(measured, 0), fmt(theory, 0), fmt(ratio, 2)]

    cp_rows = []
    if join_time is not None:
        cp_rows.append(_cp_row("at join", "at_join"))
        cp_rows.append(_cp_row("join +1h", "join+1h"))
        cp_rows.append(_cp_row("join +2h", "join+2h"))
        cp_rows.append(_cp_row("join +3h", "join+3h"))
    cp_rows.append(_cp_row("at end", "at_end"))
    lines.append(md_table(["checkpoint", "difficulty", "theory", "measured/theory"], cp_rows))
    lines.append("")
    lines.append("Theory = 120 x hashes in monerod's difficulty window / window span (window = "
                 "whole history until 600 blocks); D_post_eq = 36000-style asymptote once the "
                 "window holds only post-join blocks.")
    lines.append(f"Expected pre-join equilibrium (120 x sum(pre hashrate)): {diffcp['d_pre_eq']:.0f}")
    lines.append(f"Expected post-join equilibrium (120 x sum(all hashrate)): {diffcp['d_post_eq']:.0f}")
    lines.append("")

    # (d) block intervals
    lines.append("## (d) Block interval windows")
    run_end = windows["run_end"]
    theory_last2h_mean = None
    if run_end >= 7200:
        exp_blocks = expected_blocks(accepted, miners, run_end - 7200, run_end)
        if exp_blocks:
            theory_last2h_mean = 7200.0 / exp_blocks
    d_rows = [
        ["pre-join hours 1-4", fmt(statistics.mean(windows["pre_h1_4"]) if windows["pre_h1_4"] else None, 1, "s"),
         str(len(windows["pre_h1_4"])), "N/A"],
        ["first 20 post-join", fmt(statistics.mean(windows["first20"]) if windows["first20"] else None, 1, "s"),
         str(len(windows["first20"])) if windows["first20"] is not None else "N/A", "N/A"],
        ["last 2h", fmt(statistics.mean(windows["last2h"]) if windows["last2h"] else None, 1, "s"),
         str(len(windows["last2h"])), fmt(theory_last2h_mean, 1, "s")],
    ]
    lines.append(md_table(["window", "mean interval", "n", "theory mean interval"], d_rows))
    lines.append("")

    # (e) relay PoW rejections
    lines.append("## (e) Relay PoW rejections")
    lines.append(f"Total 'does not have enough proof of work' / 'verification failed' lines on relay-* stdout: {reject_count}")
    lines.append("")

    # (f) summary.txt facts
    lines.append("## (f) summary.txt facts")
    if summary_facts:
        lines.append(md_table(["field", "value"], [[k, v] for k, v in summary_facts.items()]))
    else:
        lines.append("(summary.txt not found or unparseable)")
    lines.append("")

    # (g) verdicts
    lines.append("## Verdicts")
    lines.append(md_table(["check", "verdict", "detail"], [[name, status, detail] for name, status, detail in verdicts]))
    lines.append("")

    return "\n".join(lines)


# ----------------------------------------------------------------------
# Output: PNG (optional, matplotlib)
# ----------------------------------------------------------------------
def rolling_mean(values, window):
    out = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        chunk = values[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def make_plot(accepted, join_time, diffcp, out_path, run_id, miners) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hours = [r["sim_time_s"] / 3600.0 for r in accepted]
    diffs = [r["difficulty"] for r in accepted]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax1.step(hours, diffs, where="post", color="tab:blue", label="difficulty")

    theory_hours, theory_vals = [], []
    if accepted:
        t, t_end = accepted[0]["sim_time_s"], accepted[-1]["sim_time_s"]
        while t <= t_end:
            val = theory_difficulty_at_time(accepted, miners, t)
            if val is not None:
                theory_hours.append(t / 3600.0)
                theory_vals.append(val)
            t += 60.0
    if theory_vals:
        ax1.plot(theory_hours, theory_vals, color="tab:green", linestyle="--",
                 label="theory (monerod window)")

    d_pre_eq, d_post_eq = diffcp["d_pre_eq"], diffcp["d_post_eq"]
    if d_pre_eq:
        ax1.axhline(d_pre_eq, color="gray", linestyle="--", label=f"pre eq ({d_pre_eq:.0f})")
    if d_post_eq and abs(d_post_eq - d_pre_eq) > 1e-6:
        ax1.axhline(d_post_eq, color="black", linestyle="--", label=f"post eq ({d_post_eq:.0f})")
    if join_time is not None:
        ax1.axvline(join_time / 3600.0, color="red", linestyle=":", label="join")
    ax1.set_ylabel("difficulty")
    ax1.set_title(f"Native DAA analysis — {run_id}")
    ax1.legend(loc="best", fontsize="small")

    int_hours = [r["sim_time_s"] / 3600.0 for r in accepted if r["interval_s"] is not None]
    intervals = [r["interval_s"] for r in accepted if r["interval_s"] is not None]
    ax2.scatter(int_hours, intervals, s=8, color="tab:blue", label="interval")
    if intervals:
        ax2.plot(int_hours, rolling_mean(intervals, 10), color="tab:orange", label="10-block rolling mean")
    ax2.axhline(120.0, color="gray", linestyle="--", label="120s target")
    if join_time is not None:
        ax2.axvline(join_time / 3600.0, color="red", linestyle=":")
    ax2.set_xlabel("sim time (hours)")
    ax2.set_ylabel("block interval (s)")
    ax2.legend(loc="best", fontsize="small")

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--join-time", default=None,
                     help="Override the derived late-joiner regime split (e.g. '4h').")
    ap.add_argument("--out", default=None, help="Output directory (default: <run_dir>/analysis_output/native_daa/)")
    ap.add_argument("--png", action="store_true", help="Also write difficulty_and_intervals.png")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"error: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    cfg_path = run_dir / "input_config.yaml"
    if not cfg_path.is_file():
        print(f"error: missing input_config.yaml in {run_dir}", file=sys.stderr)
        return 2
    try:
        cfg = load_config(cfg_path)
    except Exception as exc:
        print(f"error: could not parse {cfg_path}: {exc}", file=sys.stderr)
        return 2

    miners = cfg["miners"]
    if not miners:
        print(f"error: no agents with a 'hashrate' key found in {cfg_path}", file=sys.stderr)
        return 2
    if cfg["mining_mode"] != "native":
        print(f"warning: general.mining.mode = {cfg['mining_mode']!r}, expected 'native'", file=sys.stderr)

    raw = parse_all_miners(run_dir, miners.keys())
    accepted = build_accepted(raw)
    if not accepted:
        print(f"error: zero accepted blocks found under {run_dir}/shadow.data/hosts/*/monerod*.stdout",
              file=sys.stderr)
        return 2
    attach_intervals(accepted)

    if args.join_time is not None:
        try:
            join_time = parse_duration(args.join_time)
        except ValueError as exc:
            print(f"error: --join-time: {exc}", file=sys.stderr)
            return 2
        join_source = "--join-time"
    else:
        join_time = derive_join_time(miners)
        join_source = "derived (earliest start_time > 60s)"

    assign_regimes(accepted, join_time)

    reject_count = count_relay_rejections(run_dir)
    summary_facts = parse_summary_fields(run_dir / "summary.txt")

    hour_rows = per_hour_table(accepted)
    regime_table = per_regime_miner_table(accepted, miners, join_time)
    diffcp = difficulty_checkpoints(accepted, join_time, miners)
    windows = interval_windows(accepted, join_time, cfg["stop_time_s"])
    verdicts = make_verdicts(accepted, miners, join_time, diffcp, windows, regime_table, reject_count)

    out_dir = Path(args.out) if args.out else run_dir / "analysis_output" / "native_daa"
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(accepted, out_dir / "blocks.csv")

    report_text = render_report(run_dir.name, cfg, join_time, join_source, hour_rows, regime_table,
                                 diffcp, windows, verdicts, reject_count, summary_facts, accepted)
    (out_dir / "report.md").write_text(report_text)
    print(report_text)

    if args.png:
        try:
            make_plot(accepted, join_time, diffcp, out_dir / "difficulty_and_intervals.png", run_dir.name, miners)
        except ImportError:
            print("warning: matplotlib not available; skipping difficulty_and_intervals.png", file=sys.stderr)

    ok = all(status in ("PASS", "N/A") for _, status, _ in verdicts)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
