#!/usr/bin/env python3
"""Turn a crawl.py + poll_node.py dataset into the mainnet counterparts of
the replica spec's §6 table and the literature's §4/§4a numbers.

Usage:
    python3 summarize.py --crawl CRAWL_DIR --poll POLL_DIR \\
        --ban-list ban_list.txt --asn asn.jsonl --out report.md

Writes both --out (markdown) and a report.json with the same data, next to
it (same stem, .json extension).
"""
import argparse
import gzip
import ipaddress
import json
import math
import statistics
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BAN_LIST_URL = ("https://raw.githubusercontent.com/Boog900/monero-ban-list/"
               "refs/heads/main/ban_list.txt")
SIX_HOURS = 6 * 3600


# ---- loading ---------------------------------------------------------------
def _open_maybe_gz(path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt")
    return open(path)


def load_jsonl(path):
    out = []
    with _open_maybe_gz(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_nodes(crawl_dir):
    path = Path(crawl_dir) / "nodes.jsonl"
    return load_jsonl(path) if path.exists() else []


def load_edges(crawl_dir):
    path = Path(crawl_dir) / "edges.jsonl.gz"
    if not path.exists():
        path = Path(crawl_dir) / "edges.jsonl"
    if not path.exists():
        return []
    return [(e["src"], e["dst"]) for e in load_jsonl(path)]


def load_asn_map(asn_path):
    if not asn_path or not Path(asn_path).exists():
        return {}
    return {rec["ip"]: rec for rec in load_jsonl(asn_path)}


def _poll_files(poll_dir, prefix):
    poll_dir = Path(poll_dir)
    files = sorted(poll_dir.glob("%s-*.jsonl" % prefix)) + \
        sorted(poll_dir.glob("%s-*.jsonl.gz" % prefix))
    # de-dupe by date stamp (prefer the plain file if both exist), sort by date
    by_date = {}
    for f in files:
        stem = f.name[len(prefix) + 1:].split(".")[0]
        by_date.setdefault(stem, f)
    return [by_date[d] for d in sorted(by_date)]


def load_poll_connections(poll_dir):
    ticks = []
    for f in _poll_files(poll_dir, "connections"):
        ticks.extend(load_jsonl(f))
    ticks.sort(key=lambda t: t.get("ts", 0))
    return ticks


def load_poll_peerlist(poll_dir):
    ticks = []
    for f in _poll_files(poll_dir, "peerlist"):
        ticks.extend(load_jsonl(f))
    ticks.sort(key=lambda t: t.get("ts", 0))
    return ticks


def fetch_ban_list(dest_dir):
    """Download the ban list into dest_dir with a date stamp; return its path."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    dest = dest_dir / ("ban_list-%s.txt" % stamp)
    with urllib.request.urlopen(BAN_LIST_URL, timeout=30) as resp:
        dest.write_bytes(resp.read())
    return dest


def load_ban_list(path):
    nets = []
    with open(path) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            try:
                nets.append(ipaddress.ip_network(line, strict=False))
            except ValueError:
                continue
    return nets


def ip_in_networks(ip_str, networks):
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in net for net in networks)


# ---- small stats helpers ----------------------------------------------
def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def series_stats(values):
    if not values:
        return {"n": 0, "mean": None, "median": None, "p10": None, "p90": None}
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p10": percentile(values, 0.10),
        "p90": percentile(values, 0.90),
    }


def cidr24(ip):
    parts = ip.split(".")
    if len(parts) != 4:
        return None
    return ".".join(parts[:3]) + ".0/24"


def connection_counts(connections):
    inc = sum(1 for c in connections or [] if c.get("incoming"))
    out = sum(1 for c in connections or [] if not c.get("incoming"))
    return inc, out


# ---- §4/§6 metrics -----------------------------------------------------
def reachable_count(nodes):
    return sum(1 for n in nodes if n.get("reachable"))


def compute_spy_labels(nodes, ban_networks):
    """One label-dict per reachable node: ban / mismatch / flags_absent."""
    out = []
    for n in nodes:
        if not n.get("reachable"):
            continue
        out.append({
            "ip": n["ip"],
            "ban": ip_in_networks(n["ip"], ban_networks),
            "mismatch": bool(n.get("peer_id_mismatch")),
            "flags_absent": not (n.get("support_flags") or {}).get("present", True),
        })
    return out


def spy_label_summary(labels):
    total = len(labels)

    def share(pred):
        return (sum(1 for l in labels if pred(l)) / total) if total else 0.0

    return {
        "total_reachable": total,
        "ban_share": share(lambda l: l["ban"]),
        "mismatch_share": share(lambda l: l["mismatch"]),
        "flags_absent_share": share(lambda l: l["flags_absent"]),
        "ban_and_mismatch_share": share(lambda l: l["ban"] and l["mismatch"]),
        "ban_and_flags_absent_share": share(lambda l: l["ban"] and l["flags_absent"]),
        "mismatch_and_flags_absent_share": share(lambda l: l["mismatch"] and l["flags_absent"]),
        "all_three_share": share(lambda l: l["ban"] and l["mismatch"] and l["flags_absent"]),
        "any_share": share(lambda l: l["ban"] or l["mismatch"] or l["flags_absent"]),
    }


def concentration(ips, asn_map, top_n=10):
    ips = list(ips)
    slash24 = Counter(cidr24(ip) for ip in ips if cidr24(ip))
    asn_counter = Counter()
    for ip in ips:
        rec = asn_map.get(ip)
        if rec and rec.get("asn"):
            asn_counter[rec["asn"]] += 1
    total = len(ips)
    top_asns = [{"asn": asn, "as_name": next((asn_map[ip]["as_name"] for ip in ips
                                              if asn_map.get(ip, {}).get("asn") == asn), None),
                "count": c, "share": c / total if total else 0.0}
               for asn, c in asn_counter.most_common(top_n)]
    return {"total": total, "distinct_24s": len(slash24), "top_asns": top_asns}


def top_prefix_share(ips, top_fraction=0.12):
    counts = Counter(cidr24(ip) for ip in ips if cidr24(ip))
    if not counts:
        return {"distinct_24s": 0, "top_fraction": top_fraction, "n_top_24s": 0, "top_share": 0.0}
    n_top = max(1, math.ceil(len(counts) * top_fraction))
    top_counts = sorted(counts.values(), reverse=True)[:n_top]
    total = sum(counts.values())
    return {
        "distinct_24s": len(counts),
        "top_fraction": top_fraction,
        "n_top_24s": n_top,
        "top_share": sum(top_counts) / total if total else 0.0,
    }


def country_shares(ips, asn_map, top_n=10):
    c = Counter()
    for ip in ips:
        rec = asn_map.get(ip)
        cc = rec.get("cc") if rec else None
        if cc:
            c[cc] += 1
    total = sum(c.values())
    return [{"cc": cc, "count": n, "share": n / total} for cc, n in c.most_common(top_n)] if total else []


def in_out_series(conn_ticks):
    ins, outs = [], []
    for tick in conn_ticks:
        conns = tick.get("connections")
        if conns is None:
            continue
        i, o = connection_counts(conns)
        ins.append(i)
        outs.append(o)
    return ins, outs


def spy_slot_share_series(conn_ticks, ban_networks):
    in_shares, out_shares = [], []
    for tick in conn_ticks:
        conns = tick.get("connections")
        if not conns:
            continue
        inc = [c for c in conns if c.get("incoming")]
        out = [c for c in conns if not c.get("incoming")]
        if inc:
            in_shares.append(sum(1 for c in inc if ip_in_networks(c.get("ip", ""), ban_networks)) / len(inc))
        if out:
            out_shares.append(sum(1 for c in out if ip_in_networks(c.get("ip", ""), ban_networks)) / len(out))
    return in_shares, out_shares


def peerlist_spy_share_series(peerlist_ticks, ban_networks):
    white_shares, gray_shares = [], []
    for tick in peerlist_ticks:
        wl, gl = tick.get("white_list"), tick.get("gray_list")
        if wl:
            white_shares.append(
                sum(1 for e in wl if ip_in_networks(e.get("host") or e.get("ip", ""), ban_networks)) / len(wl))
        if gl:
            gray_shares.append(
                sum(1 for e in gl if ip_in_networks(e.get("host") or e.get("ip", ""), ban_networks)) / len(gl))
    return white_shares, gray_shares


def derive_connection_durations(conn_ticks):
    """A connection present at tick t (by connection_id) and absent at t+1 is
    counted as completed, with duration = its live_time at tick t. A tick
    with a null/errored connections list breaks the pairing (can't tell if a
    connection ended or we just missed a sample). Returns (out_durations,
    in_durations) in seconds."""
    out_durations, in_durations = [], []
    prev = None
    for tick in conn_ticks:
        conns = tick.get("connections")
        if conns is None:
            prev = None
            continue
        cur = {c.get("connection_id"): c for c in conns if c.get("connection_id")}
        if prev is not None:
            for cid, c in prev.items():
                if cid not in cur:
                    lt = c.get("live_time")
                    if lt is None:
                        continue
                    (in_durations if c.get("incoming") else out_durations).append(lt)
        prev = cur
    return out_durations, in_durations


def duration_stats(durations):
    if not durations:
        return {"n": 0, "median": None, "over_6h_share": 0.0}
    return {
        "n": len(durations),
        "median": statistics.median(durations),
        "over_6h_share": sum(1 for d in durations if d > SIX_HOURS) / len(durations),
    }


def live_time_snapshot(conn_ticks):
    """Pooled live_time across all ticks (a long-lived connection is sampled
    many times; this is the raw snapshot distribution, not de-duplicated
    per-connection)."""
    in_vals, out_vals = [], []
    for tick in conn_ticks:
        for c in tick.get("connections") or []:
            lt = c.get("live_time")
            if lt is None:
                continue
            (in_vals if c.get("incoming") else out_vals).append(lt)
    return series_stats(in_vals), series_stats(out_vals)


def degree_distribution(edges):
    out_deg, in_deg, nodes = Counter(), Counter(), set()
    for src, dst in edges:
        out_deg[src] += 1
        in_deg[dst] += 1
        nodes.add(src)
        nodes.add(dst)
    return {n: out_deg.get(n, 0) + in_deg.get(n, 0) for n in nodes}


def top_share_of_edges(degree, top_fraction=0.132):
    if not degree:
        return {"n_nodes": 0, "top_fraction": top_fraction, "n_top": 0, "top_share": 0.0}
    vals = sorted(degree.values(), reverse=True)
    n_top = max(1, math.ceil(len(vals) * top_fraction))
    total = sum(vals)
    return {
        "n_nodes": len(vals),
        "top_fraction": top_fraction,
        "n_top": n_top,
        "top_share": sum(vals[:n_top]) / total if total else 0.0,
    }


def hub_coverage(edges, degree, top_n=14):
    """Share of non-hub nodes with a direct edge (either direction) to one of
    the top-`top_n` nodes by degree -- a like-for-like with S2's "14 hubs
    linked to 82.1% of the giant component"."""
    if not degree:
        return {"top_n": top_n, "covered": 0, "total_nodes": 0, "coverage": 0.0}
    hubs = set(sorted(degree, key=lambda n: degree[n], reverse=True)[:top_n])
    adjacent = set()
    for src, dst in edges:
        if src in hubs and dst not in hubs:
            adjacent.add(dst)
        if dst in hubs and src not in hubs:
            adjacent.add(src)
    denom = len(degree) - len(hubs & set(degree))
    return {
        "top_n": top_n,
        "covered": len(adjacent),
        "total_nodes": denom,
        "coverage": len(adjacent) / denom if denom else 0.0,
    }


# ---- report assembly ----------------------------------------------------
def build_report(nodes, edges, conn_ticks, peerlist_ticks, ban_networks, asn_map):
    labels = compute_spy_labels(nodes, ban_networks)
    ban_ips = [l["ip"] for l in labels if l["ban"]]
    honest_ips = [l["ip"] for l in labels if not l["ban"]]

    ins, outs = in_out_series(conn_ticks)
    in_slot, out_slot = spy_slot_share_series(conn_ticks, ban_networks)
    white_share, gray_share = peerlist_spy_share_series(peerlist_ticks, ban_networks)
    out_durs, in_durs = derive_connection_durations(conn_ticks)
    live_in_snap, live_out_snap = live_time_snapshot(conn_ticks)
    degree = degree_distribution(edges)

    dates = sorted({datetime.fromtimestamp(t["ts"], timezone.utc).date().isoformat()
                    for t in conn_ticks if t.get("ts")})

    return {
        "dates": dates,
        "reachable_nodes": reachable_count(nodes),
        "total_probed": len(nodes),
        "spy_label_overlap": spy_label_summary(labels),
        "spy_concentration": concentration(ban_ips, asn_map),
        "honest_concentration": {
            "prefix_share": top_prefix_share(honest_ips),
            "top_asns": concentration(honest_ips, asn_map)["top_asns"],
            "country_shares": country_shares(honest_ips, asn_map),
        },
        "our_node_connections": {"inbound": series_stats(ins), "outbound": series_stats(outs)},
        "our_node_spy_slot_share": {
            "inbound_median": statistics.median(in_slot) if in_slot else None,
            "outbound_median": statistics.median(out_slot) if out_slot else None,
            "n_ticks_inbound": len(in_slot),
            "n_ticks_outbound": len(out_slot),
        },
        "peerlist_spy_share": {
            "white_median": statistics.median(white_share) if white_share else None,
            "gray_median": statistics.median(gray_share) if gray_share else None,
            "n_ticks": len(peerlist_ticks),
        },
        "connection_duration": {
            "outbound": duration_stats(out_durs),
            "inbound": duration_stats(in_durs),
            "live_time_snapshot": {"inbound": live_in_snap, "outbound": live_out_snap},
        },
        "peerlist_adjacency_degree": {
            "stats": series_stats(list(degree.values())),
            "top_13_2pct_edge_share": top_share_of_edges(degree),
            "hub_coverage_top14": hub_coverage(edges, degree),
        },
    }


def _fmt(x, fmt="%.3f"):
    return fmt % x if isinstance(x, (int, float)) else ("n/a" if x is None else str(x))


def render_markdown(report):
    lines = ["# Mainnet observation report", ""]
    lines.append("Measurement dates: %s" % (", ".join(report["dates"]) or "n/a"))
    lines.append("")
    lines.append("## Reachability")
    lines.append("- Reachable nodes (handshake ok): **%d** of %d probed" %
                 (report["reachable_nodes"], report["total_probed"]))
    lines.append("")

    sl = report["spy_label_overlap"]
    lines.append("## Spy share of reachable IPs")
    lines.append("| Label | Share |")
    lines.append("|---|---|")
    for key, label in [("ban_share", "Ban list"), ("mismatch_share", "Peer-ID mismatch"),
                       ("flags_absent_share", "Support flags absent"),
                       ("ban_and_mismatch_share", "Ban ∩ mismatch"),
                       ("ban_and_flags_absent_share", "Ban ∩ flags-absent"),
                       ("mismatch_and_flags_absent_share", "Mismatch ∩ flags-absent"),
                       ("all_three_share", "All three"), ("any_share", "Any label")]:
        lines.append("| %s | %s |" % (label, _fmt(sl.get(key))))
    lines.append("(of %d reachable nodes)" % sl.get("total_reachable", 0))
    lines.append("")

    sc = report["spy_concentration"]
    lines.append("## Spy /24 and ASN concentration (ban-list-labelled)")
    lines.append("- %d spy IPs in %d distinct /24s" % (sc["total"], sc["distinct_24s"]))
    for a in sc["top_asns"]:
        lines.append("  - AS%s (%s): %d nodes (%s)" % (a["asn"], a["as_name"], a["count"], _fmt(a["share"])))
    lines.append("")

    hc = report["honest_concentration"]
    lines.append("## Honest ASN/prefix concentration")
    lines.append("- Top %s%% of /24s (%d of %d) hold %s of honest nodes" %
                 (_fmt(hc["prefix_share"]["top_fraction"] * 100, "%.0f"),
                  hc["prefix_share"]["n_top_24s"], hc["prefix_share"]["distinct_24s"],
                  _fmt(hc["prefix_share"]["top_share"])))
    for a in hc["top_asns"]:
        lines.append("  - AS%s (%s): %d nodes (%s)" % (a["asn"], a["as_name"], a["count"], _fmt(a["share"])))
    for c in hc["country_shares"]:
        lines.append("  - %s: %d nodes (%s)" % (c["cc"], c["count"], _fmt(c["share"])))
    lines.append("")

    oc = report["our_node_connections"]
    lines.append("## Our node's connection counts over time")
    for direction in ("inbound", "outbound"):
        s = oc[direction]
        lines.append("- %s: median %s, p10 %s, p90 %s (n=%d ticks)" %
                     (direction, _fmt(s["median"], "%.1f"), _fmt(s["p10"], "%.1f"),
                      _fmt(s["p90"], "%.1f"), s["n"]))
    lines.append("")

    ss = report["our_node_spy_slot_share"]
    lines.append("## Spy share of our node's slots (ban list)")
    lines.append("- Inbound median: %s (n=%d ticks)" % (_fmt(ss["inbound_median"]), ss["n_ticks_inbound"]))
    lines.append("- Outbound median: %s (n=%d ticks)" % (_fmt(ss["outbound_median"]), ss["n_ticks_outbound"]))
    lines.append("")

    ps = report["peerlist_spy_share"]
    lines.append("## Spy share of white/gray peerlist entries")
    lines.append("- White-list median: %s" % _fmt(ps["white_median"]))
    lines.append("- Gray-list median: %s (n=%d ticks)" % (_fmt(ps["gray_median"]), ps["n_ticks"]))
    lines.append("")

    cd = report["connection_duration"]
    lines.append("## Connection-duration distribution (derived, poll)")
    for direction in ("outbound", "inbound"):
        d = cd[direction]
        lines.append("- %s: median %ss, >6h share %s (n=%d completed connections)" %
                     (direction, _fmt(d["median"], "%.0f"), _fmt(d["over_6h_share"]), d["n"]))
    lines.append("Live-time snapshot (pooled across ticks, not de-duplicated):")
    for direction, s in zip(("inbound", "outbound"), cd["live_time_snapshot"].values()):
        lines.append("- %s: median %ss, p10 %ss, p90 %ss (n=%d samples)" %
                     (direction, _fmt(s["median"], "%.0f"), _fmt(s["p10"], "%.0f"),
                      _fmt(s["p90"], "%.0f"), s["n"]))
    lines.append("")

    da = report["peerlist_adjacency_degree"]
    lines.append("## Peerlist-adjacency degree distribution (crawl)")
    st = da["stats"]
    lines.append("- mean %s, median %s, p90 %s (n=%d nodes)" %
                 (_fmt(st["mean"], "%.1f"), _fmt(st["median"], "%.1f"), _fmt(st["p90"], "%.1f"), st["n"]))
    te = da["top_13_2pct_edge_share"]
    lines.append("- Top %s%% of nodes by degree (%d of %d) hold %s of edges" %
                 (_fmt(te["top_fraction"] * 100, "%.1f"), te["n_top"], te["n_nodes"], _fmt(te["top_share"])))
    hcv = da["hub_coverage_top14"]
    lines.append("- Top %d nodes by degree are adjacent to %s of the other %d nodes (%d covered)" %
                 (hcv["top_n"], _fmt(hcv["coverage"]), hcv["total_nodes"], hcv["covered"]))
    lines.append("")

    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--crawl", required=True)
    p.add_argument("--poll", required=True)
    p.add_argument("--ban-list", default=None, help="path to an already-fetched ban list")
    p.add_argument("--fetch-ban-list", default=None, metavar="DIR",
                  help="download a fresh, date-stamped ban list into DIR instead of --ban-list")
    p.add_argument("--asn", default=None)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    ban_list_path = args.ban_list
    if args.fetch_ban_list:
        ban_list_path = fetch_ban_list(args.fetch_ban_list)
    if not ban_list_path:
        raise SystemExit("one of --ban-list or --fetch-ban-list is required")

    nodes = load_nodes(args.crawl)
    edges = load_edges(args.crawl)
    conn_ticks = load_poll_connections(args.poll)
    peerlist_ticks = load_poll_peerlist(args.poll)
    ban_networks = load_ban_list(ban_list_path)
    asn_map = load_asn_map(args.asn)

    report = build_report(nodes, edges, conn_ticks, peerlist_ticks, ban_networks, asn_map)

    out_path = Path(args.out)
    out_path.write_text(render_markdown(report))
    out_path.with_suffix(".json").write_text(json.dumps(report, indent=2, default=str))
    print("wrote %s and %s" % (out_path, out_path.with_suffix(".json")))


if __name__ == "__main__":
    main()
