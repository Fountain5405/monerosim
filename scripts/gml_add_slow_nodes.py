#!/usr/bin/env python3
"""Derive a Shadow GML graph with slow-link nodes for latency experiments.

Latency in monerosim lives only on graph edges (no per-host knob), so a
"miner on a slow link" is a host pinned (`topology_node`) to a node that
reaches the rest of the graph through one high-latency edge. This script
appends such nodes to an existing GML: each new node copies the anchor's
region and bandwidth (AS = its own id), gets the standard 1 ms self-loop,
and is joined to the anchor by one edge in each direction at the requested
latency (the directed graph needs both). Everything else is left byte for
byte as it was, so the base cells and the slow cells share the topology.

    python3 scripts/gml_add_slow_nodes.py \
        gml_processing/1200_nodes_caida_with_loops.gml \
        gml_processing/1200_nodes_caida_slow_links.gml --anchor 0 \
        --latency-ms 3000 10000 30000

prints the id of each node added (first = max existing id + 1).
"""
import argparse
import re
import sys

_REC = re.compile(r"^  (node|edge) \[\n(.*?)^  \]\n", re.M | re.S)


def parse_records(text: str):
    """(nodes, edges): each a list of {key: raw value string} in file order."""
    nodes, edges = [], []
    for m in _REC.finditer(text):
        rec = {}
        for line in m.group(2).splitlines():
            line = line.strip()
            if not line:
                continue
            k, _, v = line.partition(" ")
            rec[k] = v.strip()
        (nodes if m.group(1) == "node" else edges).append(rec)
    return nodes, edges


def _node(nid: int, region: str, bandwidth: str) -> str:
    return (f"  node [\n    id {nid}\n    AS \"{nid}\"\n"
            f"    region {region}\n    bandwidth {bandwidth}\n  ]\n")


def _edge(s: int, t: int, latency: str, bandwidth: str) -> str:
    return (f"  edge [\n    source {s}\n    target {t}\n"
            f"    latency {latency}\n    bandwidth {bandwidth}\n  ]\n")


def add_slow_nodes(text: str, anchor: int, latencies_ms, loop_latency="1ms",
                   loop_bandwidth='"10Gbit"') -> str:
    nodes, _ = parse_records(text)
    by_id = {int(n["id"]): n for n in nodes}
    if anchor not in by_id:
        raise ValueError(f"anchor {anchor} is not a node of the graph")
    a = by_id[anchor]
    region, bandwidth = a["region"], a["bandwidth"]
    first_edge = text.index("  edge [\n")
    close = text.rstrip().rfind("]")
    nid = max(by_id) + 1
    new_nodes, new_edges = [], []
    for lat in latencies_ms:
        lat_s = f'"{int(lat)}ms"'
        new_nodes.append(_node(nid, region, bandwidth))
        new_edges.append(_edge(nid, nid, f'"{loop_latency}"', loop_bandwidth))
        new_edges.append(_edge(anchor, nid, lat_s, bandwidth))
        new_edges.append(_edge(nid, anchor, lat_s, bandwidth))
        nid += 1
    return (text[:first_edge] + "".join(new_nodes) + text[first_edge:close]
            + "".join(new_edges) + text[close:])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--anchor", type=int, required=True,
                    help="existing node id the slow nodes hang off")
    ap.add_argument("--latency-ms", type=int, nargs="+", required=True,
                    help="one new node per value, one-way latency to the anchor")
    args = ap.parse_args(argv)
    with open(args.src) as f:
        text = f.read()
    nodes, _ = parse_records(text)
    first = max(int(n["id"]) for n in nodes) + 1
    out = add_slow_nodes(text, args.anchor, args.latency_ms)
    with open(args.dst, "w") as f:
        f.write(out)
    for i, lat in enumerate(args.latency_ms):
        print(f"node {first + i}: {lat} ms to node {args.anchor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
