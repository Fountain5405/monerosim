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
    # Prefer miner-001 → miner-002 → first miner-* in lexical order.
    candidates = sorted(daemon_logs.glob("monero-miner-*"))
    for c in candidates:
        log = c / "bitmonero.log"
        if log.is_file() and log.stat().st_size > 0:
            return log
    return None


def parse_block_events(log_path: Path) -> list[tuple[float, int, int]]:
    """Return list of (sim_offset_seconds, height, difficulty) per block-add."""
    events: list[tuple[dt.datetime, int, int]] = []
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
                    events.append((pending_ts, int(mh.group(1)), int(mh.group(2))))
                    pending_ts = None
    if not events:
        return []
    sim_start = events[0][0]
    return [((t - sim_start).total_seconds(), h, d) for (t, h, d) in events]


def histogram_buckets(intervals: list[float]) -> str:
    edges = [0, 30, 60, 120, 180, 300, 600, 900, 1800, 3600, float("inf")]
    labels = ["0-30s", "30-60s", "1-2m", "2-3m", "3-5m", "5-10m",
              "10-15m", "15-30m", "30-60m", ">60m"]
    counts = [0] * len(labels)
    for d in intervals:
        for i, top in enumerate(edges[1:]):
            if d < top:
                counts[i] += 1
                break
    if not counts or max(counts) == 0:
        return "  (no data)"
    width = 28
    maxc = max(counts)
    out = []
    for lbl, c in zip(labels, counts):
        bar = "█" * int(width * c / maxc)
        out.append(f"  {lbl:>9}: {c:>4}  {bar}")
    return "\n".join(out)


def fmt_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    if s < 3600:
        return f"{s/60:.1f}m"
    return f"{s/3600:.2f}h"


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

    sim_end = events[-1][0]
    n_blocks = len(events) - 1  # genesis is height 0; chain growth = #intervals
    intervals = [events[i][0] - events[i - 1][0] for i in range(1, len(events))]
    final_height = events[-1][1]
    final_diff = events[-1][2]

    print()
    print(f"  {_BOLD}Block production{_RESET}  (parsed from {log.parent.name})")
    print(f"  Chain reached height:    {final_height} ({n_blocks} blocks in {fmt_seconds(sim_end)})")
    print(f"  Final difficulty:        {final_diff}")
    print()
    print(f"  {_BOLD}Block intervals{_RESET}  (n={len(intervals)})")
    print(f"    mean:    {fmt_seconds(statistics.mean(intervals)):>8}"
          f"   target = 2m (mainnet)")
    print(f"    median:  {fmt_seconds(statistics.median(intervals)):>8}")
    if len(intervals) > 1:
        print(f"    stdev:   {fmt_seconds(statistics.stdev(intervals)):>8}")
    print(f"    min:     {fmt_seconds(min(intervals)):>8}")
    print(f"    max:     {fmt_seconds(max(intervals)):>8}")
    print()
    print(f"  {_BOLD}Interval distribution{_RESET}")
    print(histogram_buckets(intervals))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
