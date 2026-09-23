#!/usr/bin/env python3
"""Stage-2 validation metrics: compare an archived run's connection graph
against the mainnet-topology literature targets (S1-S11).

Spec: docs/superpowers/specs/2026-09-23-mainnet-replica-design.md #6
Numbers: docs/20260923_mainnet_topology_literature.md

Reads monitor-level daemon logs (net.p2p.msg lines, the same bracketed
`[<ip>:<port> INC|OUT]` tokens analysis/conn_matrix.py parses -- this module
imports conn_matrix's regex and host loader rather than re-deriving them) and
the generated `shadow_agents.yaml` for node -> IP -> class mapping and
firewall state (`blocked_inbound_ports`). Peerlist dumps
(`daemon_logs/<observer>/peerlist_dump.jsonl`, written by the patched
`--peerlist-dump-file` build; format shared with
analysis/eclipse/analyze_peerlist_dumps.py) feed the spy-peerlist-share
metric.

Node class comes from the agent-id prefix: `spy` > `monero-seed` > `miner` >
`medium` > `observer` > `relay` > `user`, else `other`. "Honest" = every class
but `spy`. "Reachable" = `blocked_inbound_ports` unset/empty in
shadow_agents.yaml.

Metrics (one line each; this is also `--help`'s output):
  1. outbound-degree class shares, absolute thresholds        light<=12 / 12<medium<=250 / heavy>250      (S1)
  1b. outbound-degree class shares, N-scaled thresholds        light<=12 / medium<=0.07N / heavy>0.25N     (S1)
  2. connection share held by the top 13.2% of nodes by total (in+out) degree                              (S1)
  3. hub coverage: share of non-hub nodes adjacent to >=1 hub (hubs: --hubs, --top-k, or miner/monero-seed) (S2)
  3b. hub neighbour overlap: median share of a hub's neighbours also adjacent to another hub                (S2)
  4. degree assortativity: Pearson correlation of total degree across edge endpoints                        (S3)
  5. modularity: greedy-modularity communities (networkx; N/A if unavailable)                                (S11)
  6. inbound connections per reachable honest node (median across such nodes)                                (S10)
  7. spy share of honest nodes' inbound slots, and outbound slots                                            (S4)
  7c. spy share of peerlist entries, from observer peerlist_dump.jsonl                                       (S4)
  (connection-duration / >6h-tail is out of scope here -- see analysis/ruck_analysis_turnover.r)

Every metric is computed on connection-graph snapshots sampled every
`--window` seconds over `[--from, --to]` (default: the run's post-bootstrap
"activity window", read from shadow_agents.yaml's
general.bootstrap_end_time..general.stop_time). The reported "measured" value
is the median across snapshots; the spread is the (min, max) across
snapshots.

Usage:
    python3 analysis/topology_metrics.py <archive_dir> [--window 300]
        [--from SECONDS] [--to SECONDS] [--hubs id1,id2,...] [--top-k N]
        [--json out.json]
"""
import argparse
import json
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conn_matrix  # noqa: E402  (MONEROD_TOKEN regex + load_hosts: reused, not copied)

# Shadow's simulated wall clock starts at 2000-01-01T00:00:00 UTC (see
# conn_matrix.py's --window docstring; peerlist_dump.jsonl's "t" field is the
# same epoch as a raw Unix timestamp: 946684800 == 2000-01-01T00:00:00Z).
SIM_EPOCH = datetime(2000, 1, 1)
SIM_EPOCH_UNIX = 946684800

CLASS_PREFIXES = [
    ("spy", "spy"),
    ("monero-seed", "monero-seed"),
    ("miner", "miner"),
    ("medium", "medium"),
    ("observer", "observer"),
    ("relay", "relay"),
    ("user", "user"),
]

LIGHT_MAX = 12
MEDIUM_MAX_ABS = 250
TOP_SHARE_FRACTION = 0.132       # S1: top 13.2% of nodes hold 82.86% of connections
MEDIUM_MAX_SCALED_FRAC = 0.07    # S1-derived scaled band
HEAVY_MIN_SCALED_FRAC = 0.25     # S2-derived scaled band


def classify(name):
    """Agent class from its id prefix. See module docstring for priority order."""
    for prefix, cls in CLASS_PREFIXES:
        if name.startswith(prefix):
            return cls
    return "other"


def parse_duration(value, default=0):
    """'10m' / '1h' / '300s' / plain seconds / 'auto' -> int seconds."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    v = str(value).strip()
    if not v or v == "auto":
        return default
    units = {"s": 1, "m": 60, "h": 3600}
    if v[-1] in units:
        try:
            return int(float(v[:-1]) * units[v[-1]])
        except ValueError:
            return default
    try:
        return int(v)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Loading run metadata
# ---------------------------------------------------------------------------

def load_run_meta(archive):
    """(by_ip, by_name, firewalled, node_class, general) for one archived run.

    by_ip / by_name come from conn_matrix.load_hosts (reused). firewalled and
    node_class are the small bits conn_matrix doesn't need: a host is
    firewalled if shadow_agents.yaml sets a non-empty `blocked_inbound_ports`.
    """
    archive = Path(archive)
    by_ip, by_name = conn_matrix.load_hosts(archive)
    cfg = yaml.safe_load(open(archive / "shadow_agents.yaml"))
    firewalled = {}
    for name, host in cfg.get("hosts", {}).items():
        firewalled[name] = bool(host.get("blocked_inbound_ports"))
    node_class = {name: classify(name) for name in by_name}
    general = cfg.get("general", {})
    return by_ip, by_name, firewalled, node_class, general


def default_window_bounds(general):
    t_from = parse_duration(general.get("bootstrap_end_time"), default=0)
    t_to = parse_duration(general.get("stop_time"), default=t_from + 3600)
    if t_to <= t_from:
        t_to = t_from + 3600
    return t_from, t_to


# ---------------------------------------------------------------------------
# Log parsing: per-node timestamped connection events
# ---------------------------------------------------------------------------

def parse_timestamped_peers(log_path):
    """[(t_seconds_since_sim_epoch, peer_ip, 'IN'|'OUT'), ...] from a monerod
    log, using conn_matrix's MONEROD_TOKEN regex (reused, not copied).

    Reads the file directly (not conn_matrix's grep-window trick) because we
    need each event's own timestamp to bucket it into arbitrary snapshots
    later; fine at this repo's archived-run log sizes (single-digit MB/node).
    """
    events = []
    with open(log_path, "r", errors="replace") as fh:
        for line in fh:
            m = conn_matrix.MONEROD_TOKEN.search(line)
            if not m:
                continue
            try:
                dt = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                continue
            t = (dt - SIM_EPOCH).total_seconds()
            events.append((t, m.group(1), "IN" if m.group(2) == "INC" else "OUT"))
    events.sort(key=lambda e: e[0])
    return events


def load_node_events(archive):
    """{agent_name: sorted [(t, peer_ip, dir), ...]} for every monerod node.

    Non-monerod (e.g. cuprate) node logs are skipped: this tool's targets are
    all measured on monerod's connection model (S1-S10 predate cuprate).
    """
    archive = Path(archive)
    logs_dir = archive / "daemon_logs"
    out = {}
    if not logs_dir.is_dir():
        return out
    for node_dir in sorted(d for d in logs_dir.iterdir() if d.is_dir()):
        impl, log_path = conn_matrix.detect_impl_and_log(node_dir)
        if impl != "monerod":
            continue
        name = (node_dir.name[len("monero-"):] if node_dir.name.startswith("monero-")
                else node_dir.name)
        out[name] = parse_timestamped_peers(log_path)
    return out


# ---------------------------------------------------------------------------
# Windowing and per-snapshot graph construction
# ---------------------------------------------------------------------------

def make_windows(t_from, t_to, window):
    if window <= 0:
        window = max(t_to - t_from, 1)
    if t_to <= t_from:
        return [(t_from, t_from + window)]
    windows = []
    t = t_from
    while t < t_to:
        windows.append((t, min(t + window, t_to)))
        t += window
    return windows


def snapshot_peer_sets(node_events, by_ip, w_start, w_end):
    """(out_peers, in_peers): {name: set(peer_name)} for one time window,
    from each node's own log (peer identity resolved via by_ip, same identity
    assumption as conn_matrix.py: one IP per host)."""
    out_peers, in_peers = defaultdict(set), defaultdict(set)
    for name, events in node_events.items():
        ts = [e[0] for e in events]
        lo, hi = bisect_left(ts, w_start), bisect_left(ts, w_end)  # window is [w_start, w_end)
        for t, ip, d in events[lo:hi]:
            peer = by_ip.get(ip)
            if not peer:
                continue
            peer_name = peer[0]
            if peer_name == name:
                continue
            (out_peers if d == "OUT" else in_peers)[name].add(peer_name)
    return out_peers, in_peers


# ---------------------------------------------------------------------------
# Per-snapshot metrics (also the unit under test: callable with a hand-built
# graph, bypassing log parsing entirely)
# ---------------------------------------------------------------------------

def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / (sxx * syy) ** 0.5


def compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled,
                              hubs=None, top_k=None):
    """All #6-metric-table numbers for ONE connection-graph snapshot.

    nodes: iterable of every agent name in the (fixed) population.
    out_peers / in_peers: {name: set(peer_name)}, this node's own view.
    node_class: {name: class_str}; firewalled: {name: bool}.
    hubs: explicit hub-name set (default: miner/monero-seed classes present).
    top_k: if given, overrides hubs with the top-K nodes by total degree.
    """
    nodes = list(nodes)
    n = len(nodes)
    out_peers = {k: set(v) for k, v in out_peers.items()}
    in_peers = {k: set(v) for k, v in in_peers.items()}
    neighbors = {name: out_peers.get(name, set()) | in_peers.get(name, set()) for name in nodes}
    out_deg = {name: len(out_peers.get(name, set())) for name in nodes}
    in_deg = {name: len(in_peers.get(name, set())) for name in nodes}
    total_deg = {name: len(neighbors[name]) for name in nodes}

    m = {}

    # 1. outbound-degree class shares (absolute thresholds)
    def class_shares(heavy_min_raw):
        # heavy_min is floored at LIGHT_MAX so the light (<=12) and heavy bands
        # never overlap at small N (where 0.25*N or 250 could otherwise fall
        # below 12, which would double-count a node into both bands).
        heavy_min = max(LIGHT_MAX, heavy_min_raw)
        light = sum(1 for name in nodes if out_deg[name] <= LIGHT_MAX)
        heavy = sum(1 for name in nodes if out_deg[name] > heavy_min)
        medium = n - light - heavy
        return {"light_pct": 100 * light / n if n else None,
                "medium_pct": 100 * medium / n if n else None,
                "heavy_pct": 100 * heavy / n if n else None}

    m["degree_class_shares_absolute"] = class_shares(MEDIUM_MAX_ABS)
    m["degree_class_shares_scaled"] = class_shares(HEAVY_MIN_SCALED_FRAC * n)
    m["scaled_medium_threshold"] = MEDIUM_MAX_SCALED_FRAC * n
    m["scaled_heavy_threshold"] = HEAVY_MIN_SCALED_FRAC * n

    # 2. connection share of the top 13.2% of nodes by total degree
    ranked = sorted(nodes, key=lambda name: total_deg[name], reverse=True)
    k = max(1, round(TOP_SHARE_FRACTION * n)) if n else 0
    top = ranked[:k]
    deg_sum = sum(total_deg.values())
    m["top_k_count"] = k
    m["top_k_connection_share_pct"] = (
        100 * sum(total_deg[name] for name in top) / deg_sum if deg_sum else None)

    # 3. hub coverage + 3b. hub neighbour overlap
    if hubs is not None:
        hub_set = set(hubs) & set(nodes)
    elif top_k:
        hub_set = set(ranked[:top_k])
    else:
        hub_set = {name for name in nodes if node_class.get(name) in ("miner", "monero-seed")}
    non_hub = [name for name in nodes if name not in hub_set]
    covered = [name for name in non_hub if neighbors[name] & hub_set]
    m["hub_set"] = sorted(hub_set)
    m["hub_coverage_pct"] = 100 * len(covered) / len(non_hub) if non_hub else None

    overlaps = []
    for h in hub_set:
        h_neighbors = neighbors[h]
        if not h_neighbors:
            continue
        other_hub_neighbors = set()
        for h2 in hub_set:
            if h2 != h:
                other_hub_neighbors |= neighbors[h2]
        overlaps.append(100 * len(h_neighbors & other_hub_neighbors) / len(h_neighbors))
    m["hub_neighbour_overlap_pct"] = median(overlaps) if overlaps else None

    # 4. degree assortativity (Pearson over edge-endpoint total degree, symmetrized)
    edges = set()
    for name in nodes:
        for peer in neighbors[name]:
            edges.add(frozenset((name, peer)))
    xs, ys = [], []
    for e in edges:
        pair = tuple(e) if len(e) == 2 else (next(iter(e)),) * 2
        a, b = pair
        da, db = total_deg.get(a, 0), total_deg.get(b, 0)
        xs += [da, db]
        ys += [db, da]
    m["edge_count"] = len(edges)
    m["degree_assortativity"] = pearson(xs, ys)

    # 5. modularity (greedy, networkx if importable)
    try:
        import networkx as nx
        if edges:
            g = nx.Graph()
            g.add_nodes_from(nodes)
            g.add_edges_from(tuple(e) if len(e) == 2 else (next(iter(e)),) * 2 for e in edges)
            communities = nx.algorithms.community.greedy_modularity_communities(g)
            m["modularity_greedy"] = nx.algorithms.community.modularity(g, communities)
        else:
            m["modularity_greedy"] = None
        m["modularity_note"] = None
    except ImportError as exc:
        m["modularity_greedy"] = None
        m["modularity_note"] = "networkx not importable: %s" % exc

    # 6. inbound connections per reachable honest node
    reachable_honest = [name for name in nodes
                         if node_class.get(name) not in ("spy", "other")
                         and not firewalled.get(name, False)]
    m["reachable_honest_count"] = len(reachable_honest)
    m["inbound_per_reachable_honest"] = (
        median(in_deg[name] for name in reachable_honest) if reachable_honest else None)

    # 7. spy share of honest inbound/outbound slots
    honest = [name for name in nodes if node_class.get(name) not in ("spy", "other")]
    total_in = sum(in_deg[name] for name in honest)
    total_out = sum(out_deg[name] for name in honest)
    spy_in = sum(1 for name in honest for p in in_peers.get(name, ()) if node_class.get(p) == "spy")
    spy_out = sum(1 for name in honest for p in out_peers.get(name, ()) if node_class.get(p) == "spy")
    m["spy_share_inbound_pct"] = 100 * spy_in / total_in if total_in else None
    m["spy_share_outbound_pct"] = 100 * spy_out / total_out if total_out else None

    return m


def peerlist_entry_spy_share(ip_ports, node_class, by_ip):
    """Spy share (%) of one peerlist snapshot's entries (white+gray combined)."""
    ips = [ip_port.rsplit(":", 1)[0] for ip_port in ip_ports]
    total = len(ips)
    if not total:
        return None
    spies = sum(1 for ip in ips
                if by_ip.get(ip) and node_class.get(by_ip[ip][0]) == "spy")
    return 100 * spies / total


def load_peerlist_dump_snapshots(path):
    """[(t_sim_seconds, [ "ip:port", ... ]), ...] from one peerlist_dump.jsonl."""
    snaps = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("t", 0) - SIM_EPOCH_UNIX
            entries = [e[0] if isinstance(e, (list, tuple)) else e
                       for e in (rec.get("white") or []) + (rec.get("gray") or [])]
            snaps.append((t, entries))
    return snaps


def nearest_snapshot_at_or_before(snaps, t):
    best = None
    for st, entries in snaps:
        if st <= t and (best is None or st > best[0]):
            best = (st, entries)
    return best


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def analyze(archive, window, t_from=None, t_to=None, hubs=None, top_k=None):
    by_ip, by_name, firewalled, node_class, general = load_run_meta(archive)
    node_events = load_node_events(archive)
    nodes = sorted(node_events)  # population = daemon nodes we have logs for

    if t_from is None or t_to is None:
        d_from, d_to = default_window_bounds(general)
        t_from = d_from if t_from is None else t_from
        t_to = d_to if t_to is None else t_to

    windows = make_windows(t_from, t_to, window)
    per_snapshot = []
    for w_start, w_end in windows:
        out_peers, in_peers = snapshot_peer_sets(node_events, by_ip, w_start, w_end)
        per_snapshot.append(
            compute_snapshot_metrics(nodes, out_peers, in_peers, node_class, firewalled,
                                      hubs=hubs, top_k=top_k))

    # peerlist-dump spy share, sampled at the same window edges
    archive_path = Path(archive)
    dump_paths = sorted((archive_path / "daemon_logs").glob("*/peerlist_dump.jsonl"))
    dump_snaps = {p: load_peerlist_dump_snapshots(p) for p in dump_paths}
    peerlist_shares = []
    for w_start, w_end in windows:
        shares_this_window = []
        for snaps in dump_snaps.values():
            snap = nearest_snapshot_at_or_before(snaps, w_end)
            if snap is None:
                continue
            share = peerlist_entry_spy_share(snap[1], node_class, by_ip)
            if share is not None:
                shares_this_window.append(share)
        if shares_this_window:
            peerlist_shares.append(median(shares_this_window))

    return {
        "archive": str(archive),
        "params": {"window": window, "from": t_from, "to": t_to,
                   "n_snapshots": len(windows), "n_nodes": len(nodes),
                   "n_peerlist_dumps": len(dump_paths)},
        "per_snapshot": per_snapshot,
        "peerlist_spy_share_pct_per_snapshot": peerlist_shares,
    }


def aggregate(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"median": median(vals), "min": min(vals), "max": max(vals), "n": len(vals)}


def fmt(agg, pct=True, digits=1):
    if agg is None:
        return "n/a"
    suffix = "%" if pct else ""
    return "%.*f%s (%.*f-%.*f)" % (digits, agg["median"], suffix, digits, agg["min"], digits, agg["max"])


# (label, extractor, target, source, is_percentage)
TABLE_ROWS = [
    ("Outbound-degree share, light (<=12), absolute thresholds",
     lambda r: aggregate(s["degree_class_shares_absolute"]["light_pct"] for s in r["per_snapshot"]),
     "86.8%", "S1", True),
    ("Outbound-degree share, medium, absolute thresholds",
     lambda r: aggregate(s["degree_class_shares_absolute"]["medium_pct"] for s in r["per_snapshot"]),
     "12.5%", "S1", True),
    ("Outbound-degree share, heavy, absolute thresholds",
     lambda r: aggregate(s["degree_class_shares_absolute"]["heavy_pct"] for s in r["per_snapshot"]),
     "0.7%", "S1", True),
    ("Outbound-degree share, light (<=12), N-scaled thresholds",
     lambda r: aggregate(s["degree_class_shares_scaled"]["light_pct"] for s in r["per_snapshot"]),
     "86.8%", "S1", True),
    ("Outbound-degree share, medium (<=0.07N), N-scaled thresholds",
     lambda r: aggregate(s["degree_class_shares_scaled"]["medium_pct"] for s in r["per_snapshot"]),
     "12.5%", "S1", True),
    ("Outbound-degree share, heavy (>0.25N), N-scaled thresholds",
     lambda r: aggregate(s["degree_class_shares_scaled"]["heavy_pct"] for s in r["per_snapshot"]),
     "0.7%", "S1", True),
    ("Connection share held by top 13.2% of nodes (total degree)",
     lambda r: aggregate(s["top_k_connection_share_pct"] for s in r["per_snapshot"]),
     "~83%", "S1", True),
    ("Hub coverage (share of non-hub nodes adjacent to a hub)",
     lambda r: aggregate(s["hub_coverage_pct"] for s in r["per_snapshot"]),
     "~82%", "S2", True),
    ("Hub neighbour overlap (median across hubs)",
     lambda r: aggregate(s["hub_neighbour_overlap_pct"] for s in r["per_snapshot"]),
     ">91%", "S2", True),
    ("Degree assortativity",
     lambda r: aggregate(s["degree_assortativity"] for s in r["per_snapshot"]),
     "~-0.28", "S3", False),
    ("Modularity (greedy)",
     lambda r: aggregate(s["modularity_greedy"] for s in r["per_snapshot"]),
     "~0.09", "S11", False),
    ("Inbound connections per reachable honest node",
     lambda r: aggregate(s["inbound_per_reachable_honest"] for s in r["per_snapshot"]),
     "50-100", "S10", False),
    ("Spy share of honest inbound slots",
     lambda r: aggregate(s["spy_share_inbound_pct"] for s in r["per_snapshot"]),
     "~20%", "S4", True),
    ("Spy share of honest outbound slots",
     lambda r: aggregate(s["spy_share_outbound_pct"] for s in r["per_snapshot"]),
     "<=15%", "S4", True),
    ("Spy share of peerlist entries (observer dumps)",
     lambda r: aggregate(r["peerlist_spy_share_pct_per_snapshot"]),
     "~17%", "S4", True),
]


def render_markdown(result):
    lines = ["| metric | measured (median, range) | target | source |",
             "|---|---|---|---|"]
    for label, fn, target, source, pct in TABLE_ROWS:
        lines.append("| %s | %s | %s | %s |" % (label, fmt(fn(result), pct=pct), target, source))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archive", help="archived run directory (archived_runs/<run_id>/)")
    parser.add_argument("--window", type=int, default=300,
                         help="snapshot window length in simulated seconds (default 300)")
    parser.add_argument("--from", dest="t_from", type=int, default=None,
                         help="window start, simulated seconds (default: bootstrap_end_time)")
    parser.add_argument("--to", dest="t_to", type=int, default=None,
                         help="window end, simulated seconds (default: stop_time)")
    parser.add_argument("--hubs", default=None,
                         help="comma-separated hub agent ids (default: miner-*/monero-seed-*)")
    parser.add_argument("--top-k", type=int, default=None,
                         help="use the top-K nodes by total degree as hubs instead of --hubs")
    parser.add_argument("--json", default=None, help="write full metrics + params to this path")
    args = parser.parse_args(argv)

    hubs = args.hubs.split(",") if args.hubs else None
    result = analyze(args.archive, args.window, t_from=args.t_from, t_to=args.t_to,
                      hubs=hubs, top_k=args.top_k)

    print("archive: %s" % result["archive"])
    print("window params: %s" % result["params"])
    print()
    print(render_markdown(result))

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2, default=str)
        print("\nwrote %s" % args.json)


if __name__ == "__main__":
    main()
