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
"""

import argparse
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

# Bandwidth based on relationship type
RELATIONSHIP_BANDWIDTH = {
    '-1': '100Mbit',   # Customer-provider
    '0': '1Gbit',      # Peer-peer
    '-2': '10Gbit',    # Sibling
    'default': '500Mbit'
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

    Note: Latency will be calculated later based on renumbered node regions.
    Here we just store the relationship type for bandwidth calculation.
    """
    gml_graph = defaultdict(dict)

    # Add original edges with relationship type (latency calculated after renumbering)
    for source in component:
        for target, rel_type in graph[source].items():
            if target in component:  # Only within component
                bandwidth = RELATIONSHIP_BANDWIDTH.get(rel_type, RELATIONSHIP_BANDWIDTH['default'])
                gml_graph[source][target] = {'rel_type': rel_type, 'bandwidth': bandwidth}

    # Add self-loops for all nodes
    for node in component:
        gml_graph[node][node] = {'rel_type': 'self', 'bandwidth': '10Gbit'}

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

def write_gml(new_graph, new_nodes, output_file):
    """Write renumbered graph to GML with region-based latencies."""
    total_nodes = len(new_nodes)

    # Track latency statistics for reporting
    latency_stats = defaultdict(list)

    with open(output_file, 'w') as f:
        f.write("graph [\n")
        f.write("  directed 1\n\n")

        # Nodes
        for new_id in new_nodes:
            region = get_region_for_node(new_id, total_nodes)
            f.write(f"  node [\n")
            f.write(f"    id {new_id}\n")
            f.write(f'    AS "{new_id}"\n')
            f.write(f'    region "{region}"\n')
            f.write('    bandwidth "1Gbit"\n')
            f.write("  ]\n\n")

        # Edges with region-based latency
        for source in new_graph:
            for target, attrs in new_graph[source].items():
                latency = get_latency_between_nodes(source, target, total_nodes)
                bandwidth = attrs["bandwidth"]

                f.write("  edge [\n")
                f.write(f"    source {source}\n")
                f.write(f"    target {target}\n")
                f.write(f'    latency "{latency}ms"\n')
                f.write(f'    bandwidth "{bandwidth}"\n')
                f.write("  ]\n")

                # Track stats
                src_region = get_region_for_node(source, total_nodes)
                tgt_region = get_region_for_node(target, total_nodes)
                if source != target:
                    key = tuple(sorted([src_region, tgt_region]))
                    latency_stats[key].append(latency)

        f.write("]\n")

    print(f"GML saved to {output_file}")

    # Print latency summary
    print("\nRegion-to-Region Latency Summary:")
    for (r1, r2), latencies in sorted(latency_stats.items()):
        avg = sum(latencies) / len(latencies)
        print(f"  {r1} <-> {r2}: {avg:.0f}ms ({len(latencies)} edges)")

def main():
    parser = argparse.ArgumentParser(description="Create connected CAIDA GML with self-loops")
    parser.add_argument("aslinks_file", help="Raw CAIDA AS-links file")
    parser.add_argument("output_gml", help="Output GML file")
    parser.add_argument("--max_nodes", type=int, default=50, help="Max nodes in component")
    
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
    
    # Write GML
    write_gml(new_graph, new_nodes, args.output_gml)
    
    # Validation
    num_edges = sum(len(neighbors) for neighbors in new_graph.values())
    print(f"Generated GML: {len(new_nodes)} nodes, {num_edges} edges (including {len(new_nodes)} self-loops)")

if __name__ == "__main__":
    main()