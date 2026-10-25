#!/usr/bin/env python3
"""Churn-cost scorer (journal open question 11).

For every monerod node in an archived run: its daemon sessions (one per start-up banner in
bitmonero.log; peer turnover restarts the daemon on its data dir), the time from each session's
start to a full outbound set, and the dial-related failure lines in its log. The point is to price
a peer-selection rule where peers churn: a rule that draws stale entries shows up as failed dials
and slower slot filling, not as spy share.

Usage:
    venv/bin/python -I analysis/spy/churn_cost.py <archive> [--slots 12] [--window 300] [--json out.json]

"Full outbound set": the first time after a session's start when the distinct OUT peers seen in
the trailing --window seconds of log lines reach --slots (the same connection tokens
x0_calibration.py snapshots; a quiet connection is invisible, so this is an upper bound on the
fill time). Failure patterns are counted per node and reported per class as a rate per node-hour
of session time; `back ping connect failed` is the ping-back to an inbound peer and is reported
separately from outbound dial failures.
"""
import argparse
import json
import re
import statistics
import sys
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import topology_metrics  # noqa: E402

BANNER = re.compile(r"Monero '[^']+' \(v[0-9.]+")
PATTERNS = {
    "connect_failed": re.compile(r"Connect failed|Failed to connect|connect error", re.I),
    "handshake_failed": re.compile(r"COMMAND_HANDSHAKE F", re.I),
    "timed_out": re.compile(r"timed out|timeout", re.I),
    "back_ping_failed": re.compile(r"back ping connect failed", re.I),
    "handshake_ok": re.compile(r"CONNECTION HANDSHAKED OK", re.I),
}


def parse_log(log_path):
    """(session_starts_s, pattern_counts, last_t) from one bitmonero.log."""
    starts, counts, last_t = [], {k: 0 for k in PATTERNS}, None
    with open(log_path, "r", errors="replace") as fh:
        for line in fh:
            try:
                t = (datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f") - topology_metrics.SIM_EPOCH).total_seconds()
            except ValueError:
                continue
            last_t = t
            if BANNER.search(line):
                starts.append(t)
            for key, rx in PATTERNS.items():
                if rx.search(line):
                    counts[key] += 1
    return starts, counts, last_t


def fill_times(events, starts, end_t, slots, window):
    """Per session: seconds from start to the first trailing-window with >= slots distinct OUT peers (None if never)."""
    out = [(t, ip) for t, ip, d in events if d == "OUT"]
    res = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else (end_t if end_t is not None else float("inf"))
        win, seen, fill = deque(), defaultdict(int), None
        for t, ip in out:
            if t < s:
                continue
            if t >= e:
                break
            win.append((t, ip)); seen[ip] += 1
            while win and win[0][0] < t - window:
                t0, ip0 = win.popleft(); seen[ip0] -= 1
                if seen[ip0] == 0:
                    del seen[ip0]
            if len(seen) >= slots:
                fill = t - s
                break
        res.append({"start": s, "end": e if e != float("inf") else None, "fill": fill})
    return res


def q(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = max(0, min(len(vals) - 1, int(round(p * (len(vals) - 1)))))
    return vals[k]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive")
    ap.add_argument("--slots", type=int, default=12)
    ap.add_argument("--window", type=int, default=300)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    archive = Path(a.archive)
    by_ip, by_name, firewalled, node_class, general = topology_metrics.load_run_meta(archive)
    events = topology_metrics.load_node_events(archive)
    per_class = defaultdict(lambda: {"nodes": 0, "sessions": 0, "restarts": 0, "hours": 0.0,
                                     "fill_first": [], "fill_restart": [], "unfilled": 0,
                                     "counts": {k: 0 for k in PATTERNS}})
    per_node = {}
    for node_dir in sorted(d for d in (archive / "daemon_logs").iterdir() if d.is_dir()):
        name = node_dir.name[len("monero-"):] if node_dir.name.startswith("monero-") else node_dir.name
        log = node_dir / "bitmonero.log"
        if not log.is_file() or name not in events:
            continue
        starts, counts, last_t = parse_log(log)
        if not starts:
            continue
        cls = node_class.get(name, topology_metrics.classify(name))
        ft = fill_times(events[name], starts, last_t, a.slots, a.window)
        hours = sum(((s["end"] if s["end"] is not None else last_t) - s["start"]) for s in ft) / 3600.0
        c = per_class[cls]
        c["nodes"] += 1; c["sessions"] += len(ft); c["restarts"] += max(0, len(ft) - 1); c["hours"] += hours
        for i, s in enumerate(ft):
            if s["fill"] is None:
                c["unfilled"] += 1
            elif i == 0:
                c["fill_first"].append(s["fill"])
            else:
                c["fill_restart"].append(s["fill"])
        for k in PATTERNS:
            c["counts"][k] += counts[k]
        per_node[name] = {"class": cls, "sessions": ft, "counts": counts, "hours": hours}
    print(f"churn cost  {archive.name}  slots={a.slots} window={a.window}s")
    print(f"{'class':10s} {'nodes':>5s} {'sess':>5s} {'restarts':>8s} {'hours':>7s} | fill first med/p90 | fill restart med/p90 | unfilled | per node-hour: connect_failed handshake_failed timed_out back_ping_failed handshake_ok")
    report = {}
    for cls in sorted(per_class):
        c = per_class[cls]
        h = max(c["hours"], 1e-9)
        rates = {k: c["counts"][k] / h for k in PATTERNS}
        ff = (q(c["fill_first"], 0.5), q(c["fill_first"], 0.9)); fr = (q(c["fill_restart"], 0.5), q(c["fill_restart"], 0.9))
        fmt = lambda v: "-" if v is None else f"{v/60:.1f}m"
        print(f"{cls:10s} {c['nodes']:5d} {c['sessions']:5d} {c['restarts']:8d} {c['hours']:7.1f} | {fmt(ff[0]):>7s} {fmt(ff[1]):>7s} | {fmt(fr[0]):>7s} {fmt(fr[1]):>7s} | {c['unfilled']:8d} | "
              + " ".join(f"{rates[k]:.2f}" for k in PATTERNS))
        report[cls] = {"nodes": c["nodes"], "sessions": c["sessions"], "restarts": c["restarts"], "hours": c["hours"],
                       "fill_first_med_s": ff[0], "fill_first_p90_s": ff[1], "fill_restart_med_s": fr[0], "fill_restart_p90_s": fr[1],
                       "unfilled": c["unfilled"], "counts": c["counts"], "per_node_hour": rates}
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"archive": archive.name, "slots": a.slots, "window": a.window, "classes": report, "nodes": per_node}, fh, indent=1)
        print("json:", a.json)


if __name__ == "__main__":
    main()
