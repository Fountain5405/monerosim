#!/usr/bin/env python3
"""X0 calibration report: does the lab reproduce measured spy exposure?

docs/20261018_spy_node_defenses.md §5.3 X0; cells from
test_configs/x0/make_cells.sh. For one archived run, over the activity window:

  - spy share of honest outbound and inbound slots, per --window snapshot of
    the bitmonero.log connection tokens (analysis/topology_metrics.py), split
    by class, by always-on (observer) nodes, and by ban-list adopters
    (`--ban-list` in the host's args) versus non-adopters;
  - stem length and how stems ended, from the relay logs
    (analysis/spy/txrelay_check.py), and the embargo-timer rate: the share of
    txs whose stem ended because a holder's timer fired.

Targets (pass: within 1.5x): outbound share ~0.15 with legacy selection and no
list (Rucknium 2024, Kopyciok 15.26%), ~0.07 with the list (7.13%), ~70% lower
with /24 dedup (#9939's simulation); stem hops geometric with mean ~5. Compare
cells with --compare, which prints one row per run.

Usage:
    python3 analysis/spy/x0_calibration.py <archive_dir> [--window 300]
    python3 analysis/spy/x0_calibration.py --compare <archive_dir> ... [--json out.json]
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import txrelay_check  # noqa: E402
import topology_metrics  # noqa: E402

TARGETS = {"legacy/none": 0.15, "legacy/half": 0.07}


def host_flags(run_dir):
    """({host: True if --ban-list}, dedup mode) from shadow_agents.yaml."""
    with open(Path(run_dir, "shadow_agents.yaml")) as f:
        hosts = yaml.safe_load(f).get("hosts", {})
    adopter, modes = {}, Counter()
    for name, h in hosts.items():
        args = [str(a) for p in h.get("processes", []) for a in p.get("args", [])]
        adopter[name] = any(a.startswith("--ban-list") for a in args)
        for a in args:
            if a.startswith("--sim-subnet-dedup="):
                modes[a.split("=", 1)[1]] += 1
    mode = modes.most_common(1)[0][0] if modes else "24"
    return adopter, mode


def slot_shares(run_dir, window=300):
    """{group: {"out": share, "in": share, "nodes": n}} over the activity window.

    A slot is one (node, peer) pair seen in a snapshot window; shares are spy
    slots / all slots, pooled over windows and nodes (slot-weighted).
    """
    by_ip, _, _, node_class, general = topology_metrics.load_run_meta(run_dir)
    adopter, _ = host_flags(run_dir)
    events = topology_metrics.load_node_events(run_dir)
    t_from, t_to = topology_metrics.default_window_bounds(general)
    tot = defaultdict(lambda: Counter())
    nodes = defaultdict(set)
    for w0, w1 in topology_metrics.make_windows(t_from, t_to, window):
        out_peers, in_peers = topology_metrics.snapshot_peer_sets(events, by_ip, w0, w1)
        for direction, peer_sets in (("out", out_peers), ("in", in_peers)):
            for node, peers in peer_sets.items():
                cls = node_class.get(node)
                if cls == "spy" or not peers:
                    continue
                spies = sum(node_class.get(p) == "spy" for p in peers)
                groups = ["honest", cls, "ban-list" if adopter.get(node) else "no-list"]
                if cls in ("user", "relay", "observer"):
                    groups.append("light")
                for g in groups:
                    tot[g][direction] += len(peers)
                    tot[g][direction + "_spy"] += spies
                    nodes[g].add(node)
    return {
        g: {"out": round(c["out_spy"] / c["out"], 4) if c["out"] else None,
            "in": round(c["in_spy"] / c["in"], 4) if c["in"] else None,
            "nodes": len(nodes[g])}
        for g, c in tot.items()
    }


def stem_metrics(run_dir):
    r = txrelay_check.check(run_dir)
    if not r["logs"]:
        return None
    ends = r["stem_end"]
    n = sum(ends.values())
    return {
        "txs": r["txs"],
        "stem_hops_mean": r["stem_hops_mean"],
        # Paths that ended in a fluff epoch are the geometric part; loops and
        # missing logs cut paths short, more so in small networks.
        "stem_hops_mean_epoch": r["stem_hops_mean_by_end"].get("epoch"),
        "fluff_per_hop": r["fluff_per_hop"],
        "stem_hops_implied": round(1 / r["fluff_per_hop"], 2) if r["fluff_per_hop"] else None,
        "stem_hops_hist": r["stem_hops_hist"],
        "stem_end": ends,
        "embargo_rate": round(ends.get("embargo", 0) / n, 4) if n else None,
        "loop_rate": round(ends.get("loop", 0) / n, 4) if n else None,
        "fluff_epoch_share": r["fluff_epoch_share"],
        "stem_hops_without_rx": r["stem_hops_without_rx"],
    }


def analyze(run_dir, window=300):
    adopter, mode = host_flags(run_dir)
    lists = "half" if any(adopter.values()) else "none"
    return {
        "run": str(run_dir),
        "cell": f"{mode}/{lists}",
        "slots": slot_shares(run_dir, window),
        "stems": stem_metrics(run_dir),
    }


def verdict(value, target):
    if value is None or target is None:
        return ""
    lo, hi = target / 1.5, target * 1.5
    return "PASS" if lo <= value <= hi else "FAIL"


def render(r):
    lines = [f"cell {r['cell']}   {r['run']}", "",
             f"{'group':10} {'nodes':>5} {'spy share out':>13} {'spy share in':>12}"]
    order = ["honest", "light", "observer", "user", "relay", "medium", "miner", "monero-seed",
             "no-list", "ban-list"]
    for g in order:
        m = r["slots"].get(g)
        if m:
            lines.append(f"{g:10} {m['nodes']:5} {m['out']!s:>13} {m['in']!s:>12}")
    t = TARGETS.get(r["cell"])
    if t:
        v = r["slots"].get("light", {}).get("out")
        lines.append(f"\ntarget: light-node outbound share ~{t}; measured {v}: {verdict(v, t)}")
    s = r["stems"]
    if s:
        lines += ["", f"stems: {s['txs']} txs, mean hops {s['stem_hops_mean']}, "
                  f"{s['stem_hops_mean_epoch']} on paths ended by a fluff epoch",
                  f"  fluff per hop {s['fluff_per_hop']} (stock 0.2): implied uncensored mean "
                  f"{s['stem_hops_implied']} hops (target ~5)",
                  f"  ended "
                  f"{s['stem_end']}", f"  embargo rate {s['embargo_rate']}, loop rate "
                  f"{s['loop_rate']}, fluff epochs {s['fluff_epoch_share']}, "
                  f"hops without rx {s['stem_hops_without_rx']}",
                  f"  hops histogram {s['stem_hops_hist']}"]
    return "\n".join(lines)


def render_compare(rows):
    lines = [f"{'cell':12} {'light out':>9} {'obs out':>8} {'no-list out':>11} {'list out':>8} "
             f"{'hops':>5} {'embargo':>7}  run"]
    for r in rows:
        sl, st = r["slots"], r["stems"] or {}
        g = lambda k: (sl.get(k) or {}).get("out")  # noqa: E731
        lines.append(f"{r['cell']:12} {g('light')!s:>9} {g('observer')!s:>8} {g('no-list')!s:>11} "
                     f"{g('ban-list')!s:>8} {st.get('stem_hops_mean')!s:>5} "
                     f"{st.get('embargo_rate')!s:>7}  {r['run']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--compare", action="store_true", help="one row per run")
    ap.add_argument("--window", type=int, default=300)
    ap.add_argument("--json", help="also write the report(s) to this file")
    args = ap.parse_args(argv)
    rows = [analyze(r, args.window) for r in args.run_dirs]
    print(render_compare(rows) if args.compare else "\n\n".join(render(r) for r in rows))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
