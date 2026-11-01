#!/usr/bin/env python3
"""Summarise an xmrnetscan snapshot (Rucknium's crawler) into the S12 counterpart
of our own crawl's report.json (analysis/mainnet/summarize.py) and the replica
spec's section 6 numbers.

xmrnetscan is Rucknium's Monero network crawler
(https://github.com/Rucknium/xmrnetscan). A daily snapshot is a .tar.xz holding
a dated dir with:
  * crawler-netscan.db  -- SQLite, schema (src/rust/src/main.rs):
      handshake_attempts(connected_node)                         every node probed
      handshake_data(connected_node, rpc_port, pruning_seed,     every node that
                     peer_id, support_flags, core_sync_data,     completed a
                     my_port)                                     handshake (reachable)
      peerlists(connected_node, peerlist)                        peerlist returned
    connected_node is "ip:port"; peerlist is Rust-Debug "[ip:port, ip:port, ...]";
    core_sync_data is Rust-Debug "...CoreSyncData { current_height: N, ...,
    top_version: V, ... }"; support_flags is "PeerSupportFlags(N)".
  * bad_peers.txt  -- peers whose handshake peer_id disagreed with their ping
    peer_id (the ProbeLab/Rucknium spy fingerprint), one "peer: ip:port,
    peer_ids: [...]," per line. This is xmrnetscan's OWN spy detection.
  * good_peers.txt -- the complement.

THE KEY xmrnetscan INSIGHT (vs our own crawl S13): the spy fleet multiplexes
many ports per IP, so the spy share is ~75% by ip:port node-instance but only
~27% by distinct machine (IP). This tool reports BOTH units.

Reuses concentration / top_prefix_share / country_shares / degree_distribution /
top_share_of_edges / hub_coverage / series_stats from summarize.py so S12 is
computed identically to S13, and the ASN cache + Team Cymru lookup from
enrich_asn.py (only IPs not already cached are looked up; --no-network skips even
that and leaves them unresolved).

Usage:
    python3 netscan_summarize.py --snapshot DIR --out report.md
        [--asn-cache PATH] [--ban-list PATH] [--spy-asn 401476] [--no-network]

Writes --out (markdown) and report.json (same stem) next to it.
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize as S            # noqa: E402  (shared metric helpers, reused not copied)
import enrich_asn as E           # noqa: E402  (ASN cache + Team Cymru lookup)

IPPORT_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)")
IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")
SPRUCE_ASN = "401476"            # AS Spruce Creek Networks -- the 2026 spy fleet


def ip_of(s):
    m = IP_RE.search(s or "")
    return m.group(1) if m else None


def ipport_of(s):
    m = IPPORT_RE.search(s or "")
    return m.group(0) if m else None


# ---- loading the SQLite snapshot ------------------------------------------
def load_snapshot(db_path):
    """(attempts_ipport, reachable) where reachable is a list of per-node dicts:
    {ipport, ip, port, peer_id, flags(int|None), pruned(bool), height, top_version}."""
    db = sqlite3.connect(db_path)
    c = db.cursor()
    attempts = set()
    for (node,) in c.execute("SELECT DISTINCT connected_node FROM handshake_attempts"):
        ipp = ipport_of(node)
        if ipp:
            attempts.add(ipp)
    reachable = []
    seen = set()
    for node, _rpc, pruning, peer_id, flags, csd, _myport in c.execute(
            "SELECT connected_node, rpc_port, pruning_seed, peer_id, support_flags, "
            "core_sync_data, my_port FROM handshake_data"):
        ipp = ipport_of(node)
        if not ipp or ipp in seen:
            continue
        seen.add(ipp)
        m = IPPORT_RE.search(node)
        fm = re.search(r"PeerSupportFlags\((\d+)\)", flags or "")
        hm = re.search(r"current_height:\s*(\d+)", csd or "")
        vm = re.search(r"top_version:\s*(\d+)", csd or "")
        reachable.append({
            "ipport": ipp,
            "ip": m.group(1),
            "port": int(m.group(2)),
            "peer_id": peer_id,
            "flags": int(fm.group(1)) if fm else None,
            "pruned": (pruning or "") != "NotPruned",
            "height": int(hm.group(1)) if hm else None,
            "top_version": int(vm.group(1)) if vm else None,
        })
    db.close()
    return attempts, reachable


def load_peerlist_edges(db_path):
    """Directed edges (src_ipport, dst_ipport) from the peerlists table, matching
    summarize.py's crawl-edge convention (src listed dst)."""
    db = sqlite3.connect(db_path)
    edges = []
    for node, pl in db.execute("SELECT connected_node, peerlist FROM peerlists"):
        src = ipport_of(node)
        if not src:
            continue
        for m in IPPORT_RE.finditer(pl or ""):
            dst = m.group(0)
            if dst != src:
                edges.append((src, dst))
    db.close()
    return edges


def load_bad_peers(path):
    """{spy ip:port} from bad_peers.txt (xmrnetscan's peer-id-mismatch list)."""
    out = set()
    if not path or not Path(path).exists():
        return out
    with open(path) as f:
        for line in f:
            ipp = ipport_of(line)
            if ipp:
                out.add(ipp)
    return out


# ---- ASN enrichment (cache first, look up only the residual) --------------
def enrich_ips(ips, cache_path, allow_network):
    """{ip: {asn, as_name, cc, prefix}} for ips, plus a small provenance dict.
    Uses enrich_asn's on-disk cache; residual IPs are looked up via Team Cymru
    unless allow_network is False."""
    cache = E.load_cache(cache_path) if cache_path else {}
    residual = [ip for ip in ips if ip not in cache]
    looked_up = 0
    if residual and allow_network:
        cache.update(E.bulk_lookup(residual))
        looked_up = len(residual)
        if cache_path:
            E.save_cache(cache_path, cache)
        residual = [ip for ip in ips if ip not in cache]
    return cache, {"ips": len(ips), "cache_hits": len(ips) - len(residual) - looked_up,
                   "looked_up": looked_up, "residual_unresolved": len(residual)}


def asn_of(asn_map, ip):
    rec = asn_map.get(ip)
    return (rec or {}).get("asn")


# ---- report assembly -------------------------------------------------------
def dual_unit_spy(spy_ipport, reachable):
    """Spy share by ip:port node-instance AND by distinct machine (IP)."""
    r_ipport = {n["ipport"] for n in reachable}
    r_ip = {n["ip"] for n in reachable}
    spy_ip = {ip_of(x) for x in spy_ipport if ip_of(x)}
    spy_ip &= r_ip
    hit_ipport = spy_ipport & r_ipport
    s24 = Counter(S.cidr24(ip) for ip in spy_ip if S.cidr24(ip))
    ports_per_ip = (len(hit_ipport) / len(spy_ip)) if spy_ip else None
    return {
        "by_ipport": {"count": len(hit_ipport),
                      "share": len(hit_ipport) / len(r_ipport) if r_ipport else 0.0},
        "by_ip": {"count": len(spy_ip),
                  "share": len(spy_ip) / len(r_ip) if r_ip else 0.0,
                  "distinct_24s": len(s24)},
        "mean_ports_per_spy_ip": ports_per_ip,
    }


def build_report(snapshot_dir, asn_cache_path, ban_list_path, spy_asn, allow_network):
    snapshot_dir = Path(snapshot_dir)
    db = str(snapshot_dir / "crawler-netscan.db")
    attempts, reachable = load_snapshot(db)
    edges = load_peerlist_edges(db)
    bad_peers = load_bad_peers(snapshot_dir / "bad_peers.txt")

    r_ip = sorted({n["ip"] for n in reachable})
    asn_map, asn_prov = enrich_ips(r_ip, asn_cache_path, allow_network)

    # spy sets: mismatch (bad_peers, primary), ASN fleet, optional ban list
    spy_mismatch = bad_peers
    spy_asn_ipport = {n["ipport"] for n in reachable if asn_of(asn_map, n["ip"]) == spy_asn}
    ban_networks = S.load_ban_list(ban_list_path) if ban_list_path else []
    spy_ban_ipport = ({n["ipport"] for n in reachable
                       if S.ip_in_networks(n["ip"], ban_networks)} if ban_networks else set())

    # honest = reachable minus any spy label; IPs feed the concentration metrics
    spy_all_ipport = spy_mismatch | spy_asn_ipport | spy_ban_ipport
    spy_all_ip = {ip_of(x) for x in spy_all_ipport if ip_of(x)}
    honest_ips = [n["ip"] for n in reachable if n["ip"] not in spy_all_ip]

    degree = S.degree_distribution(edges)
    heights = [n["height"] for n in reachable if n["height"] is not None]
    versions = Counter(n["top_version"] for n in reachable if n["top_version"] is not None)
    flags = Counter(n["flags"] for n in reachable)
    n_reach = len(reachable)
    pruned = sum(1 for n in reachable if n["pruned"])
    peer_ids = [n["peer_id"] for n in reachable]

    r_ipport = {n["ipport"] for n in reachable}
    return {
        "source": "xmrnetscan",
        "snapshot": snapshot_dir.name,
        "reachability": {
            "reachable_ipport": len(r_ipport), "probed_ipport": len(attempts),
            "reachable_ip": len(r_ip),
            "probed_ip": len({ip_of(x) for x in attempts if ip_of(x)}),
            "reachable_share_ipport": len(r_ipport) / len(attempts) if attempts else None,
        },
        "port_multiplexing": {
            "reachable_ipport": len(r_ipport), "reachable_ip": len(r_ip),
            "mean_ports_per_ip": len(r_ipport) / len(r_ip) if r_ip else None,
        },
        "spy": {
            "primary_method": "peer_id_mismatch (bad_peers.txt)",
            "spy_asn": spy_asn,
            "mismatch": dual_unit_spy(spy_mismatch, reachable),
            "asn_fleet": dual_unit_spy(spy_asn_ipport, reachable),
            "ban_list": dual_unit_spy(spy_ban_ipport, reachable) if ban_networks else None,
        },
        "honest_concentration": {
            "prefix_share": S.top_prefix_share(honest_ips),
            "top_asns": S.concentration(honest_ips, asn_map)["top_asns"],
            "country_shares": S.country_shares(honest_ips, asn_map),
        },
        "handshake": {
            "support_flags_dist": {str(k): v for k, v in flags.items()},
            "flags_absent_share": flags.get(0, 0) / n_reach if n_reach else None,
            "pruned_share": pruned / n_reach if n_reach else None,
            "peer_id": {"total": len(peer_ids), "distinct": len(set(peer_ids)),
                        "zero": sum(1 for p in peer_ids if p == 0)},
        },
        "chain": {
            "height": S.series_stats(heights),
            "height_spread_p10_p90": (
                S.percentile(heights, 0.90) - S.percentile(heights, 0.10)
                if heights else None),
            "top_version_dist": {str(k): v for k, v in versions.most_common()},
        },
        "peerlist_adjacency_degree": {
            "stats": S.series_stats(list(degree.values())),
            "top_13_2pct_edge_share": S.top_share_of_edges(degree),
            "hub_coverage_top14": S.hub_coverage(edges, degree),
        },
        "asn_enrichment": asn_prov,
    }


def render_markdown(r):
    L = ["# xmrnetscan (S12) summary", "", "Snapshot: %s" % r["snapshot"], ""]
    rc = r["reachability"]
    L += ["## Reachability",
          "- **%d** reachable / %d probed ip:port = %s" % (
              rc["reachable_ipport"], rc["probed_ipport"],
              S._fmt(rc["reachable_share_ipport"])),
          "- %d distinct reachable IPs (%d probed IPs)" % (rc["reachable_ip"], rc["probed_ip"]),
          ""]
    pm = r["port_multiplexing"]
    L += ["## Port multiplexing",
          "- %d ip:port on %d IPs = **%s ports/IP** mean" % (
              pm["reachable_ipport"], pm["reachable_ip"], S._fmt(pm["mean_ports_per_ip"], "%.1f")),
          ""]
    L += ["## Spy share (both units)", "| method | by ip:port | by IP | spy /24s | ports/spy-IP |",
          "|---|---|---|---|---|"]
    for key, name in [("mismatch", "peer-id mismatch"), ("asn_fleet", "ASN fleet"),
                      ("ban_list", "ban list")]:
        s = r["spy"].get(key)
        if not s:
            continue
        L.append("| %s | %s (%d) | %s (%d) | %d | %s |" % (
            name, S._fmt(s["by_ipport"]["share"]), s["by_ipport"]["count"],
            S._fmt(s["by_ip"]["share"]), s["by_ip"]["count"], s["by_ip"]["distinct_24s"],
            S._fmt(s["mean_ports_per_spy_ip"], "%.1f")))
    L.append("")
    hc = r["honest_concentration"]
    ps = hc["prefix_share"]
    L += ["## Honest ASN/prefix concentration",
          "- Densest %s%% of /24s (%d of %d) hold %s of honest nodes" % (
              S._fmt(ps["top_fraction"] * 100, "%.0f"), ps["n_top_24s"], ps["distinct_24s"],
              S._fmt(ps["top_share"]))]
    for a in hc["top_asns"]:
        L.append("  - AS%s (%s): %d (%s)" % (a["asn"], a["as_name"], a["count"], S._fmt(a["share"])))
    for cc in hc["country_shares"]:
        L.append("  - %s: %d (%s)" % (cc["cc"], cc["count"], S._fmt(cc["share"])))
    L.append("")
    hs = r["handshake"]
    L += ["## Handshake",
          "- support-flags-absent share: %s (%s)" % (
              S._fmt(hs["flags_absent_share"]), hs["support_flags_dist"]),
          "- pruned share: %s" % S._fmt(hs["pruned_share"]),
          "- peer_id: %d distinct / %d, %d zero" % (
              hs["peer_id"]["distinct"], hs["peer_id"]["total"], hs["peer_id"]["zero"]),
          ""]
    ch = r["chain"]
    L += ["## Chain consensus",
          "- height median %s, spread p10-p90 = %s blocks" % (
              S._fmt(ch["height"]["median"], "%.0f"), S._fmt(ch["height_spread_p10_p90"], "%.0f")),
          "- top_version (HF) dist: %s" % ch["top_version_dist"], ""]
    da = r["peerlist_adjacency_degree"]
    te, hcv = da["top_13_2pct_edge_share"], da["hub_coverage_top14"]
    L += ["## Peerlist-adjacency graph (not the connection graph)",
          "- degree mean %s median %s (n=%d)" % (
              S._fmt(da["stats"]["mean"], "%.1f"), S._fmt(da["stats"]["median"], "%.1f"),
              da["stats"]["n"]),
          "- top 13.2%% of nodes hold %s of edges" % S._fmt(te["top_share"]),
          "- top 14 hubs adjacent to %s of nodes" % S._fmt(hcv["coverage"]), ""]
    ae = r["asn_enrichment"]
    L += ["_ASN: %d IPs, %d cache hits, %d looked up, %d unresolved_" % (
        ae["ips"], ae["cache_hits"], ae["looked_up"], ae["residual_unresolved"]), ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--snapshot", required=True,
                   help="extracted snapshot dir (holds crawler-netscan.db + bad_peers.txt)")
    p.add_argument("--out", required=True)
    p.add_argument("--asn-cache", default=None,
                   help="enrich_asn.py .asn_cache.json (residual IPs looked up unless --no-network)")
    p.add_argument("--ban-list", default=None, help="optional ban list for a 3rd spy label")
    p.add_argument("--spy-asn", default=SPRUCE_ASN, help="spy fleet ASN (default %s)" % SPRUCE_ASN)
    p.add_argument("--no-network", action="store_true", help="never query Team Cymru")
    args = p.parse_args()

    report = build_report(args.snapshot, args.asn_cache, args.ban_list,
                          args.spy_asn, allow_network=not args.no_network)
    out = Path(args.out)
    out.write_text(render_markdown(report))
    out.with_suffix(".json").write_text(json.dumps(report, indent=2, default=str))
    print("wrote %s and %s" % (out, out.with_suffix(".json")))


if __name__ == "__main__":
    main()
