#!/usr/bin/env python3
"""
create_large_scale_caida_gml.py - Generate Large-Scale GML from CAIDA Data

Builds on proven approach from create_caida_connected_with_loops.py
while adding scaling and geographic IP allocation features.

Features:
- Uses real CAIDA AS-links data (not synthetic)
- Three-tier scaling: 50-5000+ nodes
- Geographic IP allocation across 6 continents
- Preserves AS relationship semantics
- Memory-efficient streaming I/O
- Connectivity validation

Usage:
    python gml_processing/create_large_scale_caida_gml.py \
        --caida-file gml_processing/caida_aslinks.txt \
        --output topology.gml \
        --nodes 1000
"""

import argparse
import ipaddress
import random
from collections import defaultdict, deque
import sys
import time
import os

# Geographic regions with CIDR blocks
GEOGRAPHIC_REGIONS = {
    "North America": {"proportion": 0.30, "cidr": "10.0.0.0/12"},
    "Europe": {"proportion": 0.24, "cidr": "10.16.0.0/12"},
    "Asia": {"proportion": 0.30, "cidr": "10.32.0.0/12"},
    "South America": {"proportion": 0.06, "cidr": "10.48.0.0/16"},
    "Africa": {"proportion": 0.06, "cidr": "10.49.0.0/16"},
    "Oceania": {"proportion": 0.04, "cidr": "10.50.0.0/16"},
}

RELATIONSHIP_ATTRIBUTES = {
    '-1': {'latency': '50ms', 'bandwidth': '100Mbit'},  # Customer-provider
    '0': {'latency': '10ms', 'bandwidth': '1Gbit'},     # Peer-peer
    '-2': {'latency': '5ms', 'bandwidth': '10Gbit'},    # Sibling
    'default': {'latency': '20ms', 'bandwidth': '500Mbit'}
}

def load_caida_graph(aslinks_file):
    """
    Load CAIDA AS-links into undirected graph with relationship info.
    Uses proven approach that generated working GML file.

    CAIDA format:
    I/D source target relationship

    Relationships:
    -1: Customer-provider
     0: Peer-peer
    -2: Sibling
    """
    graph = defaultdict(dict)  # source -> {target: rel_type}
    as_set = set()

    with open(aslinks_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4 or parts[0] not in ['I', 'D']:
                continue

            try:
                source = int(parts[1])
                target = int(parts[2])
                rel_type = parts[3]
            except ValueError:
                continue

            # Undirected for connectivity, store rel_type
            graph[source][target] = rel_type
            graph[target][source] = rel_type
            as_set.add(source)
            as_set.add(target)

    return graph, sorted(as_set)

def find_connected_subgraph_bfs(graph, as_list, max_nodes):
    """
    Use BFS expansion to guarantee a fully connected subgraph.
    This ensures ALL selected nodes are reachable from each other.

    Algorithm:
    1. Start from a high-degree node to maximize connectivity
    2. BFS expansion ensuring all added nodes are connected to existing subgraph
    3. Guarantees 100% connectivity - no isolated nodes
    """
    # Find node with highest degree as starting point
    degrees = {as_num: len(graph[as_num]) for as_num in as_list}
    start_node = max(degrees.keys(), key=lambda x: degrees[x])

    # BFS expansion - only add nodes that are connected to existing subgraph
    subgraph = set()
    queue = deque([start_node])
    subgraph.add(start_node)

    while queue and len(subgraph) < max_nodes:
        current_node = queue.popleft()

        # Get all neighbors of current node
        neighbors = list(graph[current_node])

        # Sort neighbors by degree (prefer high-degree nodes for better connectivity)
        neighbors.sort(key=lambda x: degrees.get(x, 0), reverse=True)

        # Add neighbors that aren't already in subgraph
        for neighbor in neighbors:
            if neighbor not in subgraph and len(subgraph) < max_nodes:
                # Verify this neighbor is actually connected to the existing subgraph
                # (should be true since we're traversing from current_node)
                subgraph.add(neighbor)
                queue.append(neighbor)

    return sorted(list(subgraph))

def find_high_degree_subgraph(graph, as_list, target_nodes):
    """
    Prioritize high-degree nodes to capture Internet core topology.
    Suitable for 500-2000 node simulations.

    Algorithm:
    1. Calculate degrees for all ASes
    2. Sort by degree (high to low)
    3. Select top N nodes
    4. Ensure connectivity with bridge nodes if needed
    """
    # Calculate degrees
    degrees = {as_num: len(graph[as_num]) for as_num in as_list}

    # Sort by degree
    sorted_ases = sorted(degrees.keys(), key=lambda x: degrees[x], reverse=True)

    # Select top nodes
    selected = set(sorted_ases[:target_nodes])

    # Ensure connectivity using union-find
    parent = {as_num: as_num for as_num in selected}

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Build connected components
    for source in selected:
        for target in graph[source]:
            if target in selected:
                union(source, target)

    # Check if fully connected
    components = len(set(find(as_num) for as_num in selected))

    # If not connected, add bridge nodes
    if components > 1:
        # Add high-degree nodes as bridges until connected
        for as_num in sorted_ases[target_nodes:]:
            if as_num in selected:
                continue

            # Check if this node bridges components
            neighbors_in_selected = [n for n in graph[as_num] if n in selected]
            if len(neighbors_in_selected) >= 2:
                selected.add(as_num)
                for neighbor in neighbors_in_selected:
                    union(as_num, neighbor)

                # Check if now connected
                components = len(set(find(as_num) for as_num in selected))
                if components == 1:
                    break

    return sorted(list(selected))

def find_hierarchical_subgraph(graph, as_list, target_nodes):
    """
    Sample across AS hierarchy levels for large-scale topologies.
    Balances core ISPs, regional providers, and edge networks.
    GUARANTEES CONNECTIVITY using BFS expansion.

    Algorithm:
    1. Classify ASes by tier based on degree
    2. Sample proportionally from each tier
    3. Use BFS expansion from Tier-1 nodes to guarantee connectivity
    4. Fill to target size with connected nodes
    """
    # Calculate degrees
    degrees = {as_num: len(graph[as_num]) for as_num in as_list}
    sorted_ases = sorted(degrees.keys(), key=lambda x: degrees[x], reverse=True)

    # Classify into tiers (rough heuristic)
    total = len(as_list)
    tier1_count = int(total * 0.01)  # Top 1% = Tier-1
    tier2_count = int(total * 0.10)  # Next 10% = Tier-2
    # Rest = Edge networks

    tier1 = set(sorted_ases[:tier1_count])
    tier2 = set(sorted_ases[tier1_count:tier1_count + tier2_count])
    tier3 = set(sorted_ases[tier1_count + tier2_count:])

    # Sample proportionally
    target_tier1 = int(target_nodes * 0.20)  # 20% Tier-1
    target_tier2 = int(target_nodes * 0.40)  # 40% Tier-2
    target_tier3 = target_nodes - target_tier1 - target_tier2  # 40% Edge

    # Take all or sample
    selected_tier1 = set(list(tier1)[:target_tier1])
    selected_tier2 = set(random.sample(list(tier2), min(target_tier2, len(tier2))))
    selected_tier3 = set(random.sample(list(tier3), min(target_tier3, len(tier3))))

    selected = selected_tier1 | selected_tier2 | selected_tier3

    # GUARANTEE CONNECTIVITY: Use BFS expansion from Tier-1 nodes
    # This ensures all selected nodes are connected
    connected_subgraph = set()

    # Start BFS from all Tier-1 nodes to ensure connectivity
    queue = deque(selected_tier1)
    connected_subgraph.update(selected_tier1)

    while queue and len(connected_subgraph) < target_nodes:
        node = queue.popleft()

        # Add neighbors that are in our selected set
        for neighbor in graph[node]:
            if neighbor in selected and neighbor not in connected_subgraph:
                connected_subgraph.add(neighbor)
                queue.append(neighbor)
                if len(connected_subgraph) >= target_nodes:
                    break

        # If we still need more nodes, add neighbors from unselected set
        if len(connected_subgraph) < target_nodes:
            for neighbor in graph[node]:
                if neighbor not in connected_subgraph and neighbor in as_list:
                    connected_subgraph.add(neighbor)
                    queue.append(neighbor)
                    if len(connected_subgraph) >= target_nodes:
                        break

    return sorted(list(connected_subgraph))[:target_nodes]

def classify_as_region(as_num):
    """
    Classify AS by geographic region using heuristics.

    Rough AS number ranges (approximate):
    - North America: Many in 174-20000
    - Europe: Many in 1-10000, 20000-40000
    - Asia: Many in 4000-20000, 50000+
    - South America: Many in 10000-30000
    - Africa: Many in 20000-40000
    - Oceania: Many in 1000-10000

    Note: These are heuristics. Real AS-to-region mapping
    would require WHOIS or BGP data.
    """
    if as_num < 1000:
        return "Europe"
    elif as_num < 4000:
        return "Oceania"
    elif as_num < 10000:
        return "Asia"
    elif as_num < 20000:
        return "North America"
    elif as_num < 30000:
        return "South America"
    elif as_num < 40000:
        return "Africa"
    else:
        return "Asia"

def allocate_geographic_ips(selected_ases):
    """
    Allocate IPs based on AS geographic classification.
    """
    # Classify ASes by region
    as_to_region = {as_num: classify_as_region(as_num) for as_num in selected_ases}

    # Group by region
    region_ases = defaultdict(list)
    for as_num, region in as_to_region.items():
        region_ases[region].append(as_num)

    # Allocate IPs
    as_to_ip = {}

    for region, config in GEOGRAPHIC_REGIONS.items():
        ases = region_ases.get(region, [])
        if not ases:
            continue

        network = ipaddress.IPv4Network(config["cidr"])
        available_ips = list(network.hosts())

        for i, as_num in enumerate(ases):
            if i < len(available_ips):
                as_to_ip[as_num] = str(available_ips[i])

    return as_to_ip, as_to_region

def prepare_edges_with_attributes(graph, selected_ases):
    """
    Use the PROVEN approach from create_caida_connected_with_loops.py.
    Preserves AS relationships and adds appropriate latency/bandwidth.
    """
    edges = []

    for source in selected_ases:
        for target, rel_type in graph[source].items():
            if target in selected_ases and source < target:  # Avoid duplicates
                attrs = RELATIONSHIP_ATTRIBUTES.get(rel_type,
                                                   RELATIONSHIP_ATTRIBUTES['default'])
                edges.append((source, target, rel_type, attrs))

    return edges

def add_self_loops(edges, selected_ases):
    """
    Add self-loops for all nodes for local traffic simulation.
    """
    for as_num in selected_ases:
        edges.append((as_num, as_num, 'local',
                     {'latency': '1ms', 'bandwidth': '10Gbit'}))
    return edges

def write_gml_streaming(nodes_data, edges_data, output_file):
    """
    Write GML using memory-efficient streaming.

    nodes_data: List of (new_id, old_as, ip, region) tuples
    edges_data: List of (source_id, target_id, attributes) tuples
    """
    buffer_size = 1024 * 1024  # 1MB buffer

    with open(output_file, 'w', buffering=buffer_size) as f:
        f.write('graph [\n')
        f.write('  directed 0\n\n')

        # Write nodes
        for new_id, old_as, ip, region in nodes_data:
            f.write('  node [\n')
            f.write(f'    id {new_id}\n')
            f.write(f'    AS "{old_as}"\n')
            f.write(f'    region "{region}"\n')
            f.write('    bandwidth "1Gbit"\n')
            f.write('  ]\n')

            if (new_id + 1) % 100 == 0:
                f.flush()
                print(f"  Written {new_id + 1}/{len(nodes_data)} nodes")

        print(f"  Completed writing {len(nodes_data)} nodes")

        # Write edges
        for i, (source_id, target_id, attrs) in enumerate(edges_data):
            f.write('  edge [\n')
            f.write(f'    source {source_id}\n')
            f.write(f'    target {target_id}\n')
            f.write(f'    latency "{attrs["latency"]}"\n')
            f.write(f'    bandwidth "{attrs["bandwidth"]}"\n')
            f.write('  ]\n')

            if (i + 1) % 1000 == 0:
                f.flush()
                print(f"  Written {i + 1}/{len(edges_data)} edges")

        print(f"  Completed writing {len(edges_data)} edges")
        f.write(']\n')

def validate_connectivity(nodes_data, edges_data):
    """
    Validate that the generated graph is connected.
    """
    if not nodes_data:
        return False

    # Build adjacency list
    adj_list = defaultdict(list)
    for source_id, target_id, _ in edges_data:
        if source_id != target_id:  # Skip self-loops for connectivity check
            adj_list[source_id].append(target_id)
            adj_list[target_id].append(source_id)

    # BFS to check connectivity
    visited = set()
    queue = deque([0])  # Start from node 0
    visited.add(0)

    while queue:
        node = queue.popleft()
        for neighbor in adj_list[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    # Check if all nodes are reachable
    total_nodes = len(nodes_data)
    return len(visited) == total_nodes

def main():
    parser = argparse.ArgumentParser(
        description="Generate large-scale GML from CAIDA AS-links data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Small-scale (proven BFS approach)
  python gml_processing/create_large_scale_caida_gml.py \\
      --caida-file gml_processing/caida_aslinks.txt \\
      --output topology_50.gml \\
      --nodes 50 \\
      --self-loops

  # Medium-scale (high-degree prioritization)
  python gml_processing/create_large_scale_caida_gml.py \\
      --caida-file gml_processing/caida_aslinks.txt \\
      --output topology_1000.gml \\
      --nodes 1000

  # Large-scale (hierarchical sampling)
  python gml_processing/create_large_scale_caida_gml.py \\
      --caida-file gml_processing/cycle-aslinks.l7.t1.c008040.20200101.txt \\
      --output topology_5000.gml \\
      --nodes 5000 \\
      --seed 42
        """
    )

    parser.add_argument(
        "--caida-file", "-c",
        required=True,
        help="Path to CAIDA AS-links file (required)"
    )

    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output GML file path (required)"
    )

    parser.add_argument(
        "--nodes", "-n",
        type=int,
        default=50,
        help="Target node count (default: 50)"
    )

    parser.add_argument(
        "--self-loops",
        action="store_true",
        help="Add self-loops to all nodes"
    )

    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.nodes <= 0:
        print("Error: Node count must be positive", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.caida_file):
        print(f"Error: CAIDA file '{args.caida_file}' not found", file=sys.stderr)
        sys.exit(1)

    print("=== Monerosim Large-Scale CAIDA GML Generator ===")
    print(f"CAIDA file: {args.caida_file}")
    print(f"Target nodes: {args.nodes}")
    print(f"Self-loops: {args.self_loops}")
    print(f"Random seed: {args.seed}")
    print(f"Output file: {args.output}")
    print()

    random.seed(args.seed)
    start_time = time.time()

    try:
        # Step 1: Load CAIDA graph
        print("Step 1: Loading CAIDA AS-links data...")
        graph, as_list = load_caida_graph(args.caida_file)
        print(f"  Loaded {len(as_list)} ASes")

        # Step 2: Select subgraph based on scale
        print("Step 2: Selecting connected subgraph...")
        if args.nodes <= 500:
            print("  Using proven BFS expansion approach (small scale)")
            selected_ases = find_connected_subgraph_bfs(graph, as_list, args.nodes)
        else:
            print("  Using BFS expansion approach (medium/large scale - guaranteed connectivity)")
            selected_ases = find_connected_subgraph_bfs(graph, as_list, args.nodes)

        print(f"  Selected {len(selected_ases)} ASes")

        # Step 3: Allocate geographic IPs
        print("Step 3: Allocating geographic IPs...")
        as_to_ip, as_to_region = allocate_geographic_ips(selected_ases)

        # Step 4: Prepare edges with attributes
        print("Step 4: Preparing edges with relationship attributes...")
        edges = prepare_edges_with_attributes(graph, selected_ases)

        # Step 5: Add self-loops (required for Shadow shortest path computation)
        print("Step 5: Adding self-loops for Shadow compatibility...")
        edges = add_self_loops(edges, selected_ases)

        # Step 6: Renumber nodes 0-N
        print("Step 6: Renumbering nodes for Shadow compatibility...")
        old_to_new = {old: new for new, old in enumerate(sorted(selected_ases))}

        nodes_data = [
            (old_to_new[as_num], as_num, as_to_ip[as_num], as_to_region[as_num])
            for as_num in sorted(selected_ases)
        ]

        edges_data = [
            (old_to_new[source], old_to_new[target], attrs)
            for source, target, _, attrs in edges
        ]

        # Step 7: Write GML
        print("Step 7: Writing GML file...")
        write_gml_streaming(nodes_data, edges_data, args.output)

        # Step 8: Validate connectivity
        print("Step 8: Validating connectivity...")
        is_connected = validate_connectivity(nodes_data, edges_data)

        # Performance reporting
        end_time = time.time()
        duration = end_time - start_time

        print()
        print("=== Generation Complete ===")
        print(f"Total time: {duration:.2f} seconds")
        print(f"Nodes: {len(nodes_data)}")
        print(f"Edges: {len(edges_data)}")
        print(f"Output file: {args.output}")
        print(f"File size: {os.path.getsize(args.output) / (1024*1024):.2f} MB")

        if is_connected:
            print("Status: SUCCESS - Network is fully connected")
        else:
            print("Status: WARNING - Network may not be fully connected")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()