#!/usr/bin/env python3
"""Block-time analysis for a finished monerosim run.

Walks one miner's bitmonero.log, extracts the (sim_time, height) of every
"BLOCK SUCCESSFULLY ADDED" event, computes interval statistics over the
chain, and emits a terse summary suitable for the post-run printout in
run_sim.sh.

Usage:
    python3 scripts/block_time_analysis.py <archive_dir>

The archive layout we expect:
    <archive_dir>/daemon_logs/monero-miner-001/bitmonero.log
    <archive_dir>/daemon_logs/monero-miner-002/bitmonero.log   (fallback)
    ...

Exits 0 with the summary on stdout, or 0 with a short "no data" line
if the log can't be found / has no block events (so the caller can pipe
output unconditionally).
"""

import argparse
import datetime as dt
import math
import re
import statistics
import sys
from pathlib import Path

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
HEIGHT_RE = re.compile(r"HEIGHT (\d+), difficulty:\s+(\d+)")

# ANSI bold; turn off when stdout isn't a TTY (e.g. piped into summary.txt).
_BOLD = "\033[1m" if sys.stdout.isatty() else ""
_RESET = "\033[0m" if sys.stdout.isatty() else ""


def find_miner_log(archive_dir: Path) -> Path | None:
    daemon_logs = archive_dir / "daemon_logs"
    if not daemon_logs.is_dir():
        return None
    # Prefer miner-001 → miner-002 → first miner-* in lexical order, then any
    # other daemon (selfish-mining configs name miners honest-001, ...).
    candidates = (sorted(daemon_logs.glob("monero-miner-*")) + sorted(daemon_logs.glob("monero-honest-*"))
                  + sorted(daemon_logs.glob("monero-*")))
    for c in candidates:
        log = c / "bitmonero.log"
        if log.is_file() and log.stat().st_size > 0:
            return log
    return None


def parse_block_events(log_path: Path) -> list[tuple[float, int, int]]:
    """Return list of (sim_offset_seconds, height, difficulty) per block-add.

    Dedupes by height: monerod logs "BLOCK SUCCESSFULLY ADDED" once when a
    block is added to the main chain, and again every time it replays
    `handle_block_to_main_chain` during a reorg (walking onto a longer
    competing chain) or batch catch-up. We want one entry per main-chain
    height — the earliest timestamp — so sort by (height, timestamp) and
    keep the first occurrence per height.
    """
    raw: list[tuple[dt.datetime, int, int]] = []
    pending_ts: dt.datetime | None = None
    with log_path.open() as f:
        for line in f:
            if "BLOCK SUCCESSFULLY ADDED" in line:
                m = TS_RE.match(line)
                if m:
                    pending_ts = dt.datetime.strptime(m.group(1)[:23],
                                                     "%Y-%m-%d %H:%M:%S.%f")
            elif pending_ts is not None and "HEIGHT" in line and "difficulty:" in line:
                mh = HEIGHT_RE.search(line)
                if mh:
                    raw.append((pending_ts, int(mh.group(1)), int(mh.group(2))))
                    pending_ts = None
    if not raw:
        return []
    raw.sort(key=lambda e: (e[1], e[0]))
    deduped: list[tuple[dt.datetime, int, int]] = []
    seen: set[int] = set()
    for ts, h, d in raw:
        if h in seen:
            continue
        seen.add(h)
        deduped.append((ts, h, d))
    sim_start = deduped[0][0]
    return [((t - sim_start).total_seconds(), h, d) for (t, h, d) in deduped]


def fmt_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    if s < 3600:
        return f"{s/60:.1f}m"
    return f"{s/3600:.2f}h"


# Monero's block-time target (DIFFICULTY_TARGET_V2).
TARGET_S = 120.0
# Warm-up ends at the first block whose difficulty is within this fraction of
# the late-run level (median difficulty over the second half of the run).
WARMUP_FRACTION = 0.75
# Equal-width 30 s bins up to 5 min, then one overflow bin (~8 % of intervals).
BIN_EDGES = [30.0 * i for i in range(11)] + [math.inf]


def steady_state_start(events: list[tuple[float, int, int]]) -> int:
    """Index of the first event past the difficulty warm-up.

    A run that starts from genesis spends its first blocks with difficulty
    ramping up from 1, so those blocks come far faster than 2 minutes. A run
    booted on a chain snapshot starts near equilibrium and has no warm-up."""
    diffs = [d for _, _, d in events]
    late = sorted(diffs[len(diffs) // 2:])
    level = late[len(late) // 2]
    for i, d in enumerate(diffs):
        if d >= WARMUP_FRACTION * level:
            return i
    return 0


def expected_counts(n: int, edges: list[float]) -> list[float]:
    """Counts per bin if n intervals were exponential with mean TARGET_S (what
    proof-of-work produces at the target block time)."""
    cdf = lambda x: 1.0 if math.isinf(x) else 1.0 - math.exp(-x / TARGET_S)
    return [n * (cdf(b) - cdf(a)) for a, b in zip(edges, edges[1:])]


def verdict(mean_s: float, n: int) -> tuple[bool, str]:
    """Is the mean interval consistent with TARGET_S? The standard error of the
    mean of n exponential intervals is TARGET_S / sqrt(n); allow 2.5 of them."""
    band = 2.5 * TARGET_S / math.sqrt(n)
    diff = mean_s - TARGET_S
    if abs(diff) <= band:
        return True, (f"consistent with the 2-minute target "
                      f"(mean {fmt_seconds(mean_s)}, expected {fmt_seconds(TARGET_S)} ± {band:.0f}s for n={n})")
    way = "faster" if diff < 0 else "slower"
    return False, (f"{way} than the 2-minute target: mean {fmt_seconds(mean_s)} vs "
                   f"{fmt_seconds(TARGET_S)} ± {band:.0f}s for n={n}")


def _label(a: float, b: float) -> str:
    def f(x: float) -> str:
        return f"{int(x)}s" if x < 60 else (f"{x / 60:g}m")
    return f">{f(a)}" if math.isinf(b) else f"{f(a)}-{f(b)}"


def render_summary(events: list[tuple[float, int, int]], source: str) -> str:
    out: list[str] = []
    sim_end = events[-1][0]
    out.append("")
    out.append(f"  {_BOLD}Block production{_RESET}  (parsed from {source})")
    out.append(f"  Chain reached height:    {events[-1][1]} ({len(events) - 1} blocks in {fmt_seconds(sim_end)})")
    out.append(f"  Final difficulty:        {events[-1][2]}")

    start = steady_state_start(events)
    if start > 0:
        warm = [events[i][0] - events[i - 1][0] for i in range(1, start + 1)]
        out.append("")
        out.append(f"  {_BOLD}Warm-up{_RESET} (difficulty ramp from genesis, {events[0][2]} -> {events[start][2]}): "
                   f"heights {events[0][1]}-{events[start][1]}, {len(warm)} blocks, mean {fmt_seconds(statistics.mean(warm))}")
        out.append("    Blocks come fast until difficulty catches up with the hashrate;")
        out.append("    they are left out of the statistics below.")

    iv = [events[i][0] - events[i - 1][0] for i in range(start + 1, len(events))]
    out.append("")
    if len(iv) < 2:
        out.append(f"  {_BOLD}Steady state{_RESET}: only {len(iv)} interval(s) after warm-up; too few to judge.")
        out.append("")
        return "\n".join(out)
    ok, text = verdict(statistics.mean(iv), len(iv))
    out.append(f"  {_BOLD}Steady state{_RESET}  (n={len(iv)} intervals)  {'PASS' if ok else 'CHECK'}: {text}")
    out.append(f"    mean {fmt_seconds(statistics.mean(iv))}   median {fmt_seconds(statistics.median(iv))} "
               f"(expected ~{fmt_seconds(TARGET_S * math.log(2))})   min {fmt_seconds(min(iv))}   max {fmt_seconds(max(iv))}")
    out.append("")
    out.append(f"  {_BOLD}Interval distribution{_RESET}  (observed vs expected at a 2-minute target)")
    out.append("    Mining is a random process: gaps between blocks are exponential, so")
    out.append("    short gaps are the most common and the median is ~0.69 x the mean.")
    obs = [0] * (len(BIN_EDGES) - 1)
    for d in iv:
        for i, b in enumerate(BIN_EDGES[1:]):
            if d < b:
                obs[i] += 1
                break
    exp = expected_counts(len(iv), BIN_EDGES)
    width = 30
    top = max(max(obs), max(exp)) or 1
    out.append(f"    {'interval':>9}  {'obs':>4}  {'expected':>8}")
    for i, (a, b) in enumerate(zip(BIN_EDGES, BIN_EDGES[1:])):
        filled = int(round(width * obs[i] / top))
        mark = int(round(width * exp[i] / top))
        bar = ["█"] * filled + [" "] * (width + 1 - filled)
        bar[mark] = "┃" if mark < filled else "|"    # expected, inside or past the bar
        out.append(f"    {_label(a, b):>9}  {obs[i]:>4}  {exp[i]:>8.1f}  {''.join(bar).rstrip()}")
    out.append("    (bars: observed; | or ┃: expected)")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive_dir", type=Path,
                    help="Path to archived_runs/<TS>_<name>/")
    args = ap.parse_args()

    if not args.archive_dir.is_dir():
        print(f"  (block-time analysis: archive dir not found: {args.archive_dir})")
        return 0

    log = find_miner_log(args.archive_dir)
    if log is None:
        print("  (block-time analysis: no miner log found)")
        return 0

    events = parse_block_events(log)
    if len(events) < 2:
        print(f"  (block-time analysis: only {len(events)} block event(s); need ≥2)")
        return 0

    print(render_summary(events, source=log.parent.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
