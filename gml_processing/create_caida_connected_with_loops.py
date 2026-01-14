#!/usr/bin/env python3
"""
Create a sparse connected GML from raw CAIDA AS-links data with self-loops.
Steps:
1. Parse AS-links to build undirected graph with relationship info.
2. Find largest connected component, limit to max_nodes.
3. Add self-loops to all nodes in component.
4. Renumber nodes to 0-N for Shadow.
5. Generate GML with realistic latency/bandwidth based on geographic regions.

Region-based latencies are derived from well-known Internet measurement studies
and approximate real-world RTT between continents. For more accurate AS-to-AS
latencies, see TODO/ripe-atlas-as-latency.md.

Bandwidth data is derived from Ookla Speedtest Global Index (2025) via
World Population Review. See docs/data-sources.md for full citations.
"""

import argparse
import random
from collections import defaultdict, deque

# Region proportions (must match src/ip/as_manager.rs)
REGION_PROPORTIONS = [
    ("north_america", 16.67),
    ("europe", 25.0),
    ("asia", 25.0),
    ("south_america", 16.67),
    ("africa", 8.33),
    ("oceania", 8.33),
]

# Realistic inter-region latencies in milliseconds (one-way, half of RTT)
# Based on submarine cable distances and speed of light in fiber (~200km/ms)
# Sources: WonderNetwork, Verizon latency maps, submarine cable maps
REGION_LATENCY_MS = {
    # Intra-region (within same continent)
    ("north_america", "north_america"): 25,   # US coast-to-coast ~50ms RTT
    ("europe", "europe"): 15,                  # EU is geographically smaller
    ("asia", "asia"): 40,                      # Asia spans huge distances
    ("south_america", "south_america"): 30,
    ("africa", "africa"): 40,
    ("oceania", "oceania"): 25,

    # Inter-region (between continents) - approximate one-way latency
    ("north_america", "europe"): 45,           # ~90ms RTT transatlantic
    ("north_america", "asia"): 90,             # ~180ms RTT transpacific
    ("north_america", "south_america"): 60,    # ~120ms RTT
    ("north_america", "africa"): 100,          # ~200ms RTT (via EU usually)
    ("north_america", "oceania"): 95,          # ~190ms RTT transpacific

    ("europe", "asia"): 75,                    # ~150ms RTT
    ("europe", "south_america"): 95,           # ~190ms RTT
    ("europe", "africa"): 45,                  # ~90ms RTT (close via Med)
    ("europe", "oceania"): 140,                # ~280ms RTT (longest route)

    ("asia", "south_america"): 150,            # ~300ms RTT (longest)
    ("asia", "africa"): 85,                    # ~170ms RTT
    ("asia", "oceania"): 55,                   # ~110ms RTT (relatively close)

    ("south_america", "africa"): 130,          # ~260ms RTT
    ("south_america", "oceania"): 120,         # ~240ms RTT

    ("africa", "oceania"): 120,                # ~240ms RTT
}

# Regional median bandwidth in Mbps (download speed)
# Source: Ookla Speedtest Global Index via World Population Review (2025)
# https://worldpopulationreview.com/country-rankings/internet-speeds-by-country
#
# Values represent weighted median across major countries in each region.
# Monero nodes are more likely to run on servers (VPS/dedicated) than home connections,
# so we model a mix: ~60% server-like speeds, ~40% home-like speeds.
REGION_BANDWIDTH_MBPS = {
    # North America: US 303, Canada 256, Mexico 92 -> weighted median ~250
    "north_america": {
        "median": 250,
        "std_dev": 80,      # High variance (gigabit vs rural)
        "min": 50,          # Basic broadband floor
        "max": 1000,        # Gigabit cap
    },
    # Europe: Range 38-346, most 100-250 -> median ~170
    "europe": {
        "median": 170,
        "std_dev": 60,
        "min": 30,
        "max": 500,
    },
    # Asia: Huge variance 3-407, bimodal (developed vs developing)
    # Developed (SG, HK, JP, KR): 230-407, Developing (IN, PK, ID): 20-60
    "asia": {
        "median": 130,
        "std_dev": 90,      # Very high variance
        "min": 15,
        "max": 500,
    },
    # South America: Chile 357, Brazil 220, Argentina 110 -> median ~160
    "south_america": {
        "median": 160,
        "std_dev": 70,
        "min": 20,
        "max": 400,
    },
    # Africa: Range 4-92, most 10-50 -> median ~28
    "africa": {
        "median": 28,
        "std_dev": 20,
        "min": 5,
        "max": 100,
    },
    # Oceania: AU 164, NZ 216, islands 5-27 -> bimodal, use ~70
    "oceania": {
        "median": 70,
        "std_dev": 50,
        "min": 10,
        "max": 300,
    },
}

# Upload/download ratio by connection type
# Asymmetric (cable/DSL): 10-20% of download
# Symmetric (fiber/server): 100% of download
# We model a mix assuming Monero nodes often run on servers
UPLOAD_RATIO = 0.4  # 40% of download on average (mix of symmetric and asymmetric)

# Edge bandwidth based on relationship type and regional capacity
# These represent AS interconnection capacity, not end-user speeds
RELATIONSHIP_BANDWIDTH_MULT = {
    '-1': 0.5,      # Customer-provider (bottlenecked by customer)
    '0': 1.0,       # Peer-peer (full capacity)
    '-2': 2.0,      # Sibling (intra-org, high capacity)
    'self': 10.0,   # Self-loop (local, very fast)
    'default': 0.75
}

def get_region_for_node(node_id: int, total_nodes: int) -> str:
    """Map a node ID to its geographic region based on proportional boundaries."""
    if total_nodes == 0:
        return "north_america"

    start = 0
    for region, proportion in REGION_PROPORTIONS:
        count = round(total_nodes * proportion / 100.0)
        end = start + count - 1
        if node_id <= end:
            return region
        start = end + 1

    # Last region gets any remaining nodes
    return REGION_PROPORTIONS[-1][0]


def get_latency_between_nodes(source: int, target: int, total_nodes: int) -> int:
    """Get realistic latency in ms between two nodes based on their regions."""
    if source == target:
        return 1  # Self-loop

    src_region = get_region_for_node(source, total_nodes)
    tgt_region = get_region_for_node(target, total_nodes)

    # Look up latency (order-independent)
    key = (src_region, tgt_region)
    if key in REGION_LATENCY_MS:
        return REGION_LATENCY_MS[key]

    key_rev = (tgt_region, src_region)
    if key_rev in REGION_LATENCY_MS:
        return REGION_LATENCY_MS[key_rev]

    # Fallback for same region
    if src_region == tgt_region:
        return 20

    # Fallback for cross-region
    return 100


def get_node_bandwidth(node_id: int, total_nodes: int, rng: random.Random) -> tuple:
    """Get realistic download/upload bandwidth for a node based on its region.

    Returns (download_mbps, upload_mbps) as integers.
    Uses a truncated normal distribution centered on regional median.
    """
    region = get_region_for_node(node_id, total_nodes)
    stats = REGION_BANDWIDTH_MBPS.get(region, REGION_BANDWIDTH_MBPS["north_america"])

    # Sample from normal distribution
    download = rng.gauss(stats["median"], stats["std_dev"])

    # Clamp to min/max
    download = max(stats["min"], min(stats["max"], download))
    download = int(round(download))

    # Upload is a fraction of download (models mix of symmetric/asymmetric)
    # Add some variance to the ratio too
    upload_ratio = rng.uniform(0.2, 0.8)  # 20-80% of download
    upload = int(round(download * upload_ratio))
    upload = max(5, upload)  # Minimum 5 Mbps upload

    return download, upload


def get_edge_bandwidth(source: int, target: int, rel_type: str,
                       total_nodes: int, node_bandwidths: dict) -> int:
    """Get edge bandwidth based on relationship type and endpoint capacities.

    Edge bandwidth is limited by the slower endpoint and modified by relationship type.
    Returns bandwidth in Mbps.
    """
    if source == target:
        # Self-loop: local communication, very fast
        return 10000  # 10 Gbit

    # Get endpoint download speeds
    src_bw = node_bandwidths.get(source, (100, 50))[0]
    tgt_bw = node_bandwidths.get(target, (100, 50))[0]

    # Edge is limited by slower endpoint
    min_bw = min(src_bw, tgt_bw)

    # Apply relationship multiplier
    mult = RELATIONSHIP_BANDWIDTH_MULT.get(rel_type, RELATIONSHIP_BANDWIDTH_MULT['default'])

    # For AS interconnections, scale up from end-user speeds
    # (ASes aggregate many users, so peering capacity is higher)
    edge_bw = int(min_bw * mult * 5)  # 5x multiplier for aggregation

    # Clamp to reasonable AS peering range
    edge_bw = max(50, min(10000, edge_bw))  # 50 Mbit to 10 Gbit

    return edge_bw


def format_bandwidth(mbps: int) -> str:
    """Format bandwidth in Mbps to Shadow-compatible string."""
    if mbps >= 1000:
        return f"{mbps // 1000}Gbit"
    else:
        return f"{mbps}Mbit"


def load_caida_graph(aslinks_file):
    """Load CAIDA AS-links into undirected graph with relationship info."""
    graph = defaultdict(dict)  # source -> {target: rel_type}
    as_set = set()
    
    with open(aslinks_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4 or parts[0] not in ['I', 'D']:
                continue  # Skip metadata and non-links
            
            try:
                source = int(parts[1])
                target = int(parts[2])
                rel_type = parts[3]
            except ValueError:
                continue
            
            # Undirected for connectivity, store rel_type
            graph[source][target] = rel_type
            graph[target][source] = rel_type  # Symmetric for undirected connectivity
            as_set.add(source)
            as_set.add(target)
    
    return graph, sorted(as_set)

def find_connected_subgraph(graph, as_list, max_nodes=50):
    """Find a connected subgraph of size max_nodes from the largest component using BFS expansion."""
    # First, find the start node from the largest component
    visited = set()
    components = []
    
    for start in as_list:
        if start in visited:
            continue
        
        component = set()
        queue = deque([start])
        visited.add(start)
        
        while queue:
            node = queue.popleft()
            component.add(node)
            
            for neighbor in graph[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        if len(component) > 0:
            components.append((start, sorted(list(component))))
    
    if not components:
        return []
    
    # Start from the start node of the largest component
    largest_start, _ = max(components, key=lambda x: len(x[1]))
    
    # BFS expansion to build connected subgraph of size max_nodes
    subgraph = set()
    queue = deque([largest_start])
    subgraph.add(largest_start)
    
    while queue and len(subgraph) < max_nodes:
        node = queue.popleft()
        
        for neighbor in graph[node]:
            if neighbor not in subgraph and len(subgraph) < max_nodes:
                subgraph.add(neighbor)
                queue.append(neighbor)
    
    print(f"Connected subgraph: {len(subgraph)} nodes")
    return sorted(list(subgraph))

def add_self_loops_and_attributes(graph, component):
    """Add self-loops and prepare attributes for GML.

    Note: Latency and bandwidth are calculated later based on renumbered node
    regions. Here we just store the relationship type.
    """
    gml_graph = defaultdict(dict)

    # Add original edges with relationship type
    for source in component:
        for target, rel_type in graph[source].items():
            if target in component:  # Only within component
                gml_graph[source][target] = {'rel_type': rel_type}

    # Add self-loops for all nodes
    for node in component:
        gml_graph[node][node] = {'rel_type': 'self'}

    return gml_graph

def renumber_nodes(gml_graph, component):
    """Renumber nodes to 0-N and update edges."""
    old_to_new = {old: new for new, old in enumerate(sorted(component))}
    new_graph = {}
    
    for old_source in gml_graph:
        new_source = old_to_new[old_source]
        new_graph[new_source] = {}
        for old_target, attrs in gml_graph[old_source].items():
            new_target = old_to_new[old_target]
            new_graph[new_source][new_target] = attrs
    
    return new_graph, sorted(old_to_new.values())

def write_gml(new_graph, new_nodes, output_file, seed=42):
    """Write renumbered graph to GML with region-based latencies and bandwidth."""
    total_nodes = len(new_nodes)
    rng = random.Random(seed)  # Reproducible randomness

    # Pre-compute node bandwidths for all nodes
    node_bandwidths = {}
    for node_id in new_nodes:
        node_bandwidths[node_id] = get_node_bandwidth(node_id, total_nodes, rng)

    # Track statistics for reporting
    latency_stats = defaultdict(list)
    bandwidth_stats = {"node_download": [], "node_upload": [], "edge": []}

    with open(output_file, 'w') as f:
        f.write("graph [\n")
        f.write("  directed 1\n\n")

        # Nodes with region-based bandwidth
        for new_id in new_nodes:
            region = get_region_for_node(new_id, total_nodes)
            download, upload = node_bandwidths[new_id]
            # Node bandwidth is the download speed (what the node can receive)
            bandwidth_str = format_bandwidth(download)

            f.write(f"  node [\n")
            f.write(f"    id {new_id}\n")
            f.write(f'    AS "{new_id}"\n')
            f.write(f'    region "{region}"\n')
            f.write(f'    bandwidth "{bandwidth_str}"\n')
            f.write("  ]\n\n")

            bandwidth_stats["node_download"].append(download)
            bandwidth_stats["node_upload"].append(upload)

        # Edges with region-based latency and bandwidth
        for source in new_graph:
            for target, attrs in new_graph[source].items():
                latency = get_latency_between_nodes(source, target, total_nodes)
                rel_type = attrs.get("rel_type", "default")
                edge_bw = get_edge_bandwidth(source, target, rel_type, total_nodes, node_bandwidths)
                bandwidth_str = format_bandwidth(edge_bw)

                f.write("  edge [\n")
                f.write(f"    source {source}\n")
                f.write(f"    target {target}\n")
                f.write(f'    latency "{latency}ms"\n')
                f.write(f'    bandwidth "{bandwidth_str}"\n')
                f.write("  ]\n")

                # Track stats
                src_region = get_region_for_node(source, total_nodes)
                tgt_region = get_region_for_node(target, total_nodes)
                if source != target:
                    key = tuple(sorted([src_region, tgt_region]))
                    latency_stats[key].append(latency)
                    bandwidth_stats["edge"].append(edge_bw)

        f.write("]\n")

    print(f"GML saved to {output_file}")

    # Print latency summary
    print("\nRegion-to-Region Latency Summary:")
    for (r1, r2), latencies in sorted(latency_stats.items()):
        avg = sum(latencies) / len(latencies)
        print(f"  {r1} <-> {r2}: {avg:.0f}ms ({len(latencies)} edges)")

    # Print bandwidth summary
    print("\nBandwidth Summary:")
    dl = bandwidth_stats["node_download"]
    ul = bandwidth_stats["node_upload"]
    edge = bandwidth_stats["edge"]
    print(f"  Node download: min={min(dl)}Mbit, median={sorted(dl)[len(dl)//2]}Mbit, max={max(dl)}Mbit")
    print(f"  Node upload:   min={min(ul)}Mbit, median={sorted(ul)[len(ul)//2]}Mbit, max={max(ul)}Mbit")
    if edge:
        print(f"  Edge:          min={min(edge)}Mbit, median={sorted(edge)[len(edge)//2]}Mbit, max={max(edge)}Mbit")

    # Print per-region bandwidth stats
    print("\nPer-Region Node Bandwidth (median download):")
    for region, _ in REGION_PROPORTIONS:
        region_bw = [node_bandwidths[n][0] for n in new_nodes
                     if get_region_for_node(n, total_nodes) == region]
        if region_bw:
            median = sorted(region_bw)[len(region_bw)//2]
            print(f"  {region}: {median}Mbit (n={len(region_bw)} nodes)")

def main():
    parser = argparse.ArgumentParser(description="Create connected CAIDA GML with self-loops")
    parser.add_argument("aslinks_file", help="Raw CAIDA AS-links file")
    parser.add_argument("output_gml", help="Output GML file")
    parser.add_argument("--max_nodes", type=int, default=50, help="Max nodes in component")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for bandwidth generation")

    args = parser.parse_args()

    # Load graph
    print("Loading CAIDA data...")
    graph, as_list = load_caida_graph(args.aslinks_file)

    # Find connected subgraph
    component = find_connected_subgraph(graph, as_list, args.max_nodes)

    if len(component) < 2:
        print("Error: Component too small for simulation")
        return

    # Add self-loops and attributes
    print("Adding self-loops and attributes...")
    gml_graph = add_self_loops_and_attributes(graph, component)

    # Renumber
    print("Renumbering nodes...")
    new_graph, new_nodes = renumber_nodes(gml_graph, component)

    # Write GML with bandwidth based on seed
    write_gml(new_graph, new_nodes, args.output_gml, seed=args.seed)

    # Validation
    num_edges = sum(len(neighbors) for neighbors in new_graph.values())
    print(f"\nGenerated GML: {len(new_nodes)} nodes, {num_edges} edges (including {len(new_nodes)} self-loops)")

if __name__ == "__main__":
    main()