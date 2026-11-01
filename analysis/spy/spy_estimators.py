#!/usr/bin/env python3
"""Spy-side origin estimators, scored against ground truth (spy plan I3).

docs/20261018_spy_node_defenses.md §5.2. The spies' view is what their own
--sim-log-txrelay logs record (docs/TXRELAY_LOG.md): every `rx` event at a spy
node, i.e. which peer IP sent which tx, when, and with which stem/fluff flag.
Spies must therefore run monerod-sim with the flag (variant R). Ground truth:
transaction_registry/transactions.json (sender), shadow_agents.yaml
(reachability: a non-empty `blocked_inbound_ports` = unreachable), and the
honest nodes' own relay logs (stem peers) and bitmonero.log (connections).

Estimators, one guess or an abstention per tx:
  sp       stem predecessor: the honest peer that first stemmed the tx to any
           spy. Spy-to-spy stems are skipped (the fleet colludes).
  sp_r     sp, kept only when the guessed node is unreachable. Nobody dials an
           unreachable node, so every stem it sends is its own (§2.3 point 1).
           The reachability test stands in for the spy's ping-back.
  fs       first spy: the honest peer that delivered the earliest fluff of the
           tx to any spy.
  combined sp if there is one, else fs.

Per estimator and sender class (unreachable / reachable / busy, where busy =
reachable with >= --busy-min txs), with 95% bootstrap intervals that resample
senders, not txs (a sender's txs share its stem peers):
  recall     correct guesses / txs whose true sender is in the class;
  precision  correct guesses / guesses that name a node in the class.

Ground truth ceiling, per class: the share of txs the origin stemmed straight
to a spy. sp can't do better, and for unreachable senders sp_r should reach it.

Exposure over time, per honest node, split by reachability, over the
activity window (bootstrap end to stop time):
  p_stem(t)  spy share of the node's stem peers, per epoch (relay log `epoch`
             and `stems` events; needs the honest nodes logging too);
  p_out(t)   spy share of its outbound peers, per --window snapshot of the
             bitmonero.log connection tokens (analysis/topology_metrics.py).
p_stem is a slot share, not a per-tx probability: a node's own txs use one of
its two stem peers for a whole epoch, so per-tx exposure is lumpier.

And P(a sender has >= 1 correctly attributed tx) by its tx count, per class.

Spies are the agents whose id starts with `spy` (topology_metrics' class
rule), or those matched by --spies (comma-separated fnmatch globs), which lets
an existing run be re-scored with some honest relays posing as spies.

Usage:
    python3 analysis/spy/spy_estimators.py <archive_dir> [--spies 'relay-00[1-5]']
        [--busy-min 5] [--window 600] [--bootstrap 1000] [--json out.json]
"""

import argparse
import fnmatch
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import txrelay_check  # noqa: E402
import topology_metrics  # noqa: E402

ESTIMATORS = ("sp", "sp_r", "fs", "combined")
CLASSES = ("unreachable", "reachable", "busy")
EXPOSURE_BUCKETS = ((1, 1), (2, 4), (5, 9), (10, 19), (20, None))


def sim_seconds(t_us):
    """Relay-log time (µs since the Unix epoch, simulated) -> seconds into the sim."""
    return t_us / 1e6 - topology_metrics.SIM_EPOCH_UNIX


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_shadow_meta(run_dir):
    """({agent: True if firewalled}, (t_from, t_to) activity window) from
    shadow_agents.yaml. The window is bootstrap end to stop time, as in
    analysis/topology_metrics.py."""
    with open(Path(run_dir, "shadow_agents.yaml")) as f:
        cfg = yaml.safe_load(f)
    unreachable = {name: bool(h.get("blocked_inbound_ports")) for name, h in cfg.get("hosts", {}).items()}
    return unreachable, topology_metrics.default_window_bounds(cfg.get("general", {}))


def spy_set(agents, globs=None):
    if globs:
        pats = [g.strip() for g in globs.split(",") if g.strip()]
        return {a for a in agents if any(fnmatch.fnmatch(a, p) for p in pats)}
    return {a for a in agents if topology_metrics.classify(a) == "spy"}


def spy_observations(logs, spies, ip_map):
    """{tx: [(t, sender_agent, fluff), ...]} from the spies' rx events, sorted.

    Senders are resolved by IP; receipts from unknown IPs are dropped. A spy
    logs a fluff only on its first receipt (docs/TXRELAY_LOG.md), so the
    earliest fluff across the fleet is still exact.
    """
    obs = defaultdict(list)
    for node in spies:
        for e in logs.get(node, ()):
            if e["ev"] != "rx":
                continue
            sender = ip_map.get(txrelay_check.ip_of(e["addr"]))
            if sender is not None:
                obs[e["tx"]].append((e["t"], sender, bool(e["fluff"])))
    for v in obs.values():
        v.sort()
    return obs


# ---------------------------------------------------------------------------
# Estimators
# ---------------------------------------------------------------------------

def estimate(observations, spies, unreachable):
    """{estimator: guess or None} for one tx's spy observations."""
    honest = [(t, s, fl) for t, s, fl in observations if s not in spies]
    sp = next((s for _, s, fl in honest if not fl), None)
    fs = next((s for _, s, fl in honest if fl), None)
    return {
        "sp": sp,
        "sp_r": sp if sp is not None and unreachable.get(sp, False) else None,
        "fs": fs,
        "combined": sp if sp is not None else fs,
    }


def sender_class(agent, unreachable, tx_count, busy_min):
    if unreachable.get(agent, False):
        return "unreachable"
    return "busy" if tx_count.get(agent, 0) >= busy_min else "reachable"


def score(rows, cls_of):
    """{estimator: {class: {n, guesses, correct, recall, precision}}}.

    rows: [(sender, {estimator: guess})]. Recall is grouped by the true
    sender's class, precision by the guessed node's class.
    """
    out = {}
    for est in ESTIMATORS:
        n, guesses, correct = Counter(), Counter(), Counter()
        for sender, g in rows:
            n[cls_of(sender)] += 1
            guess = g[est]
            if guess is None:
                continue
            guesses[cls_of(guess)] += 1
            if guess == sender:
                correct[cls_of(sender)] += 1
        out[est] = {
            c: {
                "n": n[c], "guesses": guesses[c], "correct": correct[c],
                "recall": correct[c] / n[c] if n[c] else None,
                "precision": correct[c] / guesses[c] if guesses[c] else None,
            }
            for c in CLASSES
        }
    return out


def bootstrap(rows, cls_of, reps, seed=1):
    """95% percentile intervals for recall and precision, resampling senders."""
    by_sender = defaultdict(list)
    for r in rows:
        by_sender[r[0]].append(r)
    senders = sorted(by_sender)
    rng = random.Random(seed)
    samples = defaultdict(list)
    for _ in range(reps):
        pick = [rng.choice(senders) for _ in senders]
        s = score([r for p in pick for r in by_sender[p]], cls_of)
        for est, per in s.items():
            for c, m in per.items():
                for k in ("recall", "precision"):
                    if m[k] is not None:
                        samples[(est, c, k)].append(m[k])
    ci = {}
    for key, vals in samples.items():
        vals.sort()
        ci[key] = (vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))])
    return ci


def exposure(rows, cls_of, est):
    """{class: {bucket: [senders, exposed]}}: a sender is exposed if `est`
    correctly attributes at least one of its txs."""
    sent, hit = Counter(), set()
    for sender, g in rows:
        sent[sender] += 1
        if g[est] == sender:
            hit.add(sender)
    out = {c: {} for c in CLASSES}
    for sender, k in sent.items():
        for lo, hi in EXPOSURE_BUCKETS:
            if k >= lo and (hi is None or k <= hi):
                label = f"{lo}+" if hi is None else (str(lo) if lo == hi else f"{lo}-{hi}")
                b = out[cls_of(sender)].setdefault(label, [0, 0])
                b[0] += 1
                b[1] += sender in hit
    return out


# ---------------------------------------------------------------------------
# Exposure over time
# ---------------------------------------------------------------------------

def first_hop_spy(stems, rows, spies, ip_map, cls_of):
    """{class: {txs, to_spy, share}}: ground truth for how many txs the origin
    stemmed straight to a spy. It caps sp's recall: a spy can name the origin
    as stem predecessor only for these. `stems` is txrelay_check.index's."""
    n, hit = Counter(), Counter()
    for tx, sender in rows:
        hop = stems.get(tx, {}).get(sender)
        if hop is None:
            continue
        c = cls_of(sender)
        n[c] += 1
        hit[c] += ip_map.get(txrelay_check.ip_of(hop[1])) in spies
    return {c: {"txs": n[c], "to_spy": hit[c],
                "share": round(hit[c] / n[c], 3) if n[c] else None} for c in CLASSES}


def p_stem_series(logs, spies, ip_map, t_from=0, t_to=float("inf")):
    """{node: [(t_sim, spy share of stem peers)]} from epoch/stems events in
    [t_from, t_to), plus each node's stem set at t_from (the epoch in force).

    Epochs with no stem peer are skipped (the node fluffs; no stem to expose).
    """
    series = {}
    for node, events in logs.items():
        if node in spies:
            continue
        pts, before = [], None
        for e in events:
            if e["ev"] not in ("epoch", "stems") or not e["stems"]:
                continue
            t = sim_seconds(e["t"])
            if t >= t_to:
                break
            peers = [ip_map.get(txrelay_check.ip_of(s["addr"])) for s in e["stems"]]
            share = sum(p in spies for p in peers) / len(peers)
            if t < t_from:
                before = (t_from, share)
            else:
                pts.append((t, share))
        if before:
            pts.insert(0, before)
        if pts:
            series[node] = pts
    return series


def p_out_series(run_dir, spies, window):
    """{node: [(window start, spy share of outbound peers)]}, honest nodes only."""
    by_ip, _, _, _, general = topology_metrics.load_run_meta(run_dir)
    events = topology_metrics.load_node_events(run_dir)
    t_from, t_to = topology_metrics.default_window_bounds(general)
    series = defaultdict(list)
    for w0, w1 in topology_metrics.make_windows(t_from, t_to, window):
        out_peers, _ = topology_metrics.snapshot_peer_sets(events, by_ip, w0, w1)
        for node, peers in out_peers.items():
            if node not in spies and peers:
                series[node].append((w0, sum(p in spies for p in peers) / len(peers)))
    return dict(series)


def summarize_series(series, unreachable):
    """Per reachability group: median over nodes of each node's mean share,
    and the share of nodes that ever had a spy (share > 0)."""
    out = {}
    for group, want in (("unreachable", True), ("reachable", False)):
        means = [statistics.mean(v for _, v in pts) for n, pts in series.items()
                 if unreachable.get(n, False) == want]
        ever = [any(v > 0 for _, v in pts) for n, pts in series.items()
                if unreachable.get(n, False) == want]
        out[group] = {
            "nodes": len(means),
            "median_of_means": round(statistics.median(means), 3) if means else None,
            "ever_spy": round(sum(ever) / len(ever), 3) if ever else None,
        }
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def analyze(run_dir, spies_glob=None, busy_min=5, window=600, reps=1000, with_p_out=True):
    logs = txrelay_check.load_logs(run_dir)
    ip_map = txrelay_check.load_ip_map(run_dir)
    senders = txrelay_check.load_senders(run_dir)
    unreachable, (t_from, t_to) = load_shadow_meta(run_dir)
    spies = spy_set(set(ip_map.values()), spies_glob)

    obs = spy_observations(logs, spies, ip_map)
    tx_count = Counter(s for s in senders.values() if s not in spies)
    cls_of = lambda a: sender_class(a, unreachable, tx_count, busy_min)  # noqa: E731
    tx_rows = [(tx, s) for tx, s in sorted(senders.items()) if s and s not in spies]
    rows = [(s, estimate(obs.get(tx, ()), spies, unreachable)) for tx, s in tx_rows]
    stems = txrelay_check.index(logs)[1]

    report = {
        "spies": sorted(spies),
        "spies_logging": sorted(spies & set(logs)),
        "txs": len(rows),
        "txs_seen_by_spies": sum(1 for tx, s in senders.items() if s not in spies and obs.get(tx)),
        "senders": {c: sum(1 for a in tx_count if cls_of(a) == c) for c in CLASSES},
        "busy_min": busy_min,
        "scores": score(rows, cls_of),
        "first_hop_spy": first_hop_spy(stems, tx_rows, spies, ip_map, cls_of),
        "exposure": {est: exposure(rows, cls_of, est) for est in ("sp_r", "combined")},
        "window": [t_from, t_to],
        "p_stem": summarize_series(p_stem_series(logs, spies, ip_map, t_from, t_to), unreachable),
    }
    if reps:
        ci = bootstrap(rows, cls_of, reps)
        for (est, c, k), lohi in ci.items():
            report["scores"][est][c][k + "_ci"] = lohi
    if with_p_out:
        report["p_out"] = summarize_series(p_out_series(run_dir, spies, window), unreachable)
    return report


def fmt(v, ci=None):
    if v is None:
        return "    -          "
    s = f"{v:5.3f}"
    return s + (f" [{ci[0]:.2f},{ci[1]:.2f}]" if ci else " " * 12)


def render(r):
    lines = [
        f"spies: {len(r['spies'])} ({len(r['spies_logging'])} logging)   "
        f"txs: {r['txs']} ({r['txs_seen_by_spies']} seen by a spy)   "
        f"senders: " + ", ".join(f"{c} {n}" for c, n in r["senders"].items())
        + f"   (busy = reachable with >= {r['busy_min']} txs)",
        "",
        f"{'estimator':9} {'class':12} {'n':>5} {'guesses':>8} {'correct':>8}  "
        f"{'recall [95% CI]':24} {'precision [95% CI]':24}",
    ]
    for est in ESTIMATORS:
        for c in CLASSES:
            m = r["scores"][est][c]
            lines.append(f"{est:9} {c:12} {m['n']:5} {m['guesses']:8} {m['correct']:8}  "
                         f"{fmt(m['recall'], m.get('recall_ci')):24} "
                         f"{fmt(m['precision'], m.get('precision_ci')):24}")
    lines += ["", "Ground truth: txs the origin stemmed straight to a spy (caps sp recall)"]
    for c, m in r["first_hop_spy"].items():
        if m["txs"]:
            lines.append(f"  {c:12} {m['to_spy']}/{m['txs']} = {m['share']}")
    for est, per in r["exposure"].items():
        lines += ["", f"P(sender has >= 1 tx attributed by {est}), by tx count: exposed/senders"]
        for c, buckets in per.items():
            if buckets:
                lines.append(f"  {c:12} " + "  ".join(f"{b}: {e}/{n}" for b, (n, e) in buckets.items()))
    lines += ["", f"Exposure over the activity window, sim {r['window'][0]}-{r['window'][1]} s"]
    for key, label in (("p_stem", "p_stem (spy share of stem peers, per epoch)"),
                       ("p_out", "p_out (spy share of outbound peers, per window)")):
        if key in r:
            lines += ["", label]
            for g, m in r[key].items():
                lines.append(f"  {g:12} nodes {m['nodes']:4}   median of node means "
                             f"{m['median_of_means']}   ever had a spy {m['ever_spy']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--spies", help="comma-separated agent-id globs (default: ids starting with 'spy')")
    ap.add_argument("--busy-min", type=int, default=5, help="txs for a reachable sender to count as busy")
    ap.add_argument("--window", type=int, default=600, help="p_out snapshot window, seconds")
    ap.add_argument("--bootstrap", type=int, default=1000, help="bootstrap replicates (0: none)")
    ap.add_argument("--no-p-out", action="store_true", help="skip the bitmonero.log connection scan")
    ap.add_argument("--json", help="also write the report to this file")
    args = ap.parse_args(argv)
    r = analyze(args.run_dir, args.spies, args.busy_min, args.window, args.bootstrap, not args.no_p_out)
    if not r["spies"]:
        print("No spy agents (ids starting with 'spy'); pass --spies", file=sys.stderr)
        return 1
    if not r["spies_logging"]:
        print("No spy has a txrelay.jsonl: run spies on monerod-sim with "
              "sim-log-txrelay (docs/TXRELAY_LOG.md)", file=sys.stderr)
        return 1
    print(render(r))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(r, f, indent=2, default=list)
    return 0


if __name__ == "__main__":
    sys.exit(main())
