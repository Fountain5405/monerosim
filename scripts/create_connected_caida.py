#!/usr/bin/env python3
"""
Create a connected subgraph from CAIDA AS-links data for Shadow compatibility.

This script:
1. Loads CAIDA AS-links data
2. Builds the graph
3. Extracts the largest connected component
4. Limits to a manageable size
5. Converts to GML format
"""

import argparse
from collections import defaultdict, deque
import sys

# Constants
DEFAULT_MAX_NODES = 800


def build_graph_from_aslinks(input_file: str) -> defaultdict:
    """Build undirected graph from CAIDA AS-links."""
    graph = defaultdict(set)

    with open(input_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] in ['I', 'D']:
                try:
                    source = int(parts[1])
                    target = int(parts[2])
                    graph[source].add(target)
                    graph[target].add(source)  # Undirected for connectivity
                except ValueError:
                    continue

    return graph


def find_connected_components(graph: defaultdict) -> list:
    """Find all connected components using BFS."""
    visited = set()
    components = []

    # Get all nodes
    all_nodes = set(graph.keys())
    for neighbors in graph.values():
        all_nodes.update(neighbors)

    for start_node in all_nodes:
        if start_node in visited:
            continue

        # BFS to find component
        component = set()
        queue = deque([start_node])
        visited.add(start_node)

        while queue:
            node = queue.popleft()
            component.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        components.append(component)

    return components


def extract_largest_component(graph: defaultdict, max_nodes: int = DEFAULT_MAX_NODES) -> set:
    """Extract and limit the largest connected component."""
    components = find_connected_components(graph)
    largest_component = max(components, key=len) if components else set()

    print(f"Found {len(components)} components")
    print(f"Largest component has {len(largest_component)} nodes")

    # Limit size for Shadow compatibility
    if len(largest_component) > max_nodes:
        limited_component = set(list(largest_component)[:max_nodes])
        print(f"Limited to {max_nodes} nodes for Shadow compatibility")
    else:
        limited_component = largest_component

    return limited_component


def create_subgraph_aslinks(input_file: str, output_file: str, component_nodes: set) -> None:
    """Create AS-links file for the component."""
    with open(input_file, 'r') as f, open(output_file, 'w') as out:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] in ['I', 'D']:
                try:
                    source = int(parts[1])
                    target = int(parts[2])
                    if source in component_nodes and target in component_nodes:
                        out.write(line)
                except ValueError:
                    continue

    print(f"Created subgraph with {len(component_nodes)} nodes")


def convert_aslinks_to_gml(input_file: str, output_file: str, component_nodes: set) -> None:
    """Convert component AS-links to GML."""
    as_nodes = {}  # Map AS number to node ID
    edges = []
    node_id = 0

    # Build node mapping
    for as_num in sorted(component_nodes):
        as_nodes[as_num] = node_id
        node_id += 1

    # Read edges
    with open(input_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] in ['I', 'D']:
                try:
                    source = int(parts[1])
                    target = int(parts[2])
                    rel_type = parts[2]  # Relationship type
                    if source in component_nodes and target in component_nodes:
                        edges.append((as_nodes[source], as_nodes[target], rel_type))
                except ValueError:
                    continue

    # Write GML
    with open(output_file, 'w') as f:
        f.write("graph [\n")
        f.write("  directed 1\n")  # Required for Shadow

        # Write nodes
        for as_num, node_id in as_nodes.items():
            f.write("  node [\n")
            f.write(f"    id {node_id}\n")
            f.write(f'    AS "{as_num}"\n')
            f.write('    label "AS{as_num}"\n')
            f.write('    bandwidth "1Gbit"\n')
            f.write("  ]\n")

        # Write edges
        for source_id, target_id, rel_type in edges:
            f.write("  edge [\n")
            f.write(f"    source {source_id}\n")
            f.write(f"    target {target_id}\n")
            # Estimate latency/bandwidth based on relationship
            if rel_type == "-2":
                f.write('    latency "10ms"\n')
                f.write('    bandwidth "1Gbit"\n')
            elif rel_type == "-1":
                f.write('    latency "50ms"\n')
                f.write('    bandwidth "500Mbit"\n')
            else:
                f.write('    latency "100ms"\n')
                f.write('    bandwidth "100Mbit"\n')
            f.write("  ]\n")

        f.write("]\n")

    print(f"Converted to GML: {len(as_nodes)} nodes, {len(edges)} edges")


def main():
    parser = argparse.ArgumentParser(description="Create connected CAIDA subgraph for Shadow")
    parser.add_argument("input_file", help="CAIDA AS-links file")
    parser.add_argument("output_gml", help="Output GML file")
    parser.add_argument("--max_nodes", type=int, default=DEFAULT_MAX_NODES,
                        help=f"Maximum nodes in subgraph (default: {DEFAULT_MAX_NODES})")

    args = parser.parse_args()

    print("Building graph from CAIDA AS-links...")
    graph = build_graph_from_aslinks(args.input_file)

    print("Finding largest connected component...")
    component = extract_largest_component(graph, args.max_nodes)

    print("Creating subgraph AS-links...")
    subgraph_file = args.output_gml.replace('.gml', '_aslinks.txt')
    create_subgraph_aslinks(args.input_file, subgraph_file, component)

    print("Converting to GML...")
    convert_aslinks_to_gml(subgraph_file, args.output_gml, component)

    print(f"Success! Created connected CAIDA subgraph: {args.output_gml}")


if __name__ == "__main__":
    main()