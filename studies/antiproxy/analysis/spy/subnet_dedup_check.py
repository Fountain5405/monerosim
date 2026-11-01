#!/usr/bin/env python3
"""Spies per honest node's outbound set, for checking --sim-subnet-dedup.

Reads an archived run's connection tokens (analysis/topology_metrics.py) and,
per --window snapshot over the activity window, counts each honest node's
outbound peers that are spies (agent ids starting with `spy`). Reports the
spy share of outbound slots, the share of node-snapshots with at least one
spy, and the histogram of spies per node-snapshot.
test_configs/subnet_dedup_check.scenario.yaml is the matching run.

Usage:
    python3 analysis/spy/subnet_dedup_check.py <archive_dir> [<archive_dir> ...] [--window 600]
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import topology_metrics  # noqa: E402


def dedup_mode(run_dir):
    """The --sim-subnet-dedup value the run's honest daemons were given."""
    path = Path(run_dir, "input_config.yaml")
    if path.exists():
        for line in path.read_text().splitlines():
            if "sim-subnet-dedup:" in line:
                return line.split(":", 1)[1].strip().strip("'\"")
    return "24"


def check(run_dir, window=600):
    by_ip, _, _, node_class, general = topology_metrics.load_run_meta(run_dir)
    events = topology_metrics.load_node_events(run_dir)
    t_from, t_to = topology_metrics.default_window_bounds(general)
    hist, slots, spy_slots = Counter(), 0, 0
    for w0, w1 in topology_metrics.make_windows(t_from, t_to, window):
        out_peers, _ = topology_metrics.snapshot_peer_sets(events, by_ip, w0, w1)
        for node, peers in out_peers.items():
            if node_class.get(node) == "spy" or not peers:
                continue
            k = sum(node_class.get(p) == "spy" for p in peers)
            hist[k] += 1
            slots += len(peers)
            spy_slots += k
    snaps = sum(hist.values())
    return {
        "mode": dedup_mode(run_dir),
        "node_snapshots": snaps,
        "spy_share_of_outbound": round(spy_slots / slots, 3) if slots else None,
        "with_a_spy": round(1 - hist[0] / snaps, 3) if snaps else None,
        "spies_per_node": dict(sorted(hist.items())),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--window", type=int, default=600)
    args = ap.parse_args(argv)
    print(f"{'mode':8} {'snapshots':>9} {'spy share':>9} {'>=1 spy':>8}  spies per node: snapshots")
    for run in args.run_dirs:
        r = check(run, args.window)
        hist = "  ".join(f"{k}: {v}" for k, v in r["spies_per_node"].items())
        print(f"{r['mode']:8} {r['node_snapshots']:9} {r['spy_share_of_outbound']!s:>9} "
              f"{r['with_a_spy']!s:>8}  {hist}   {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
