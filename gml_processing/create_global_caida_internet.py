#!/usr/bin/env python3
"""
Create a global CAIDA internet GML with ~2000 nodes from raw CAIDA cycle-aslinks data.
Steps:
1. Parse AS-links to build directed NetworkX graph with relationship info.
2. Clean: remove self-loops and duplicates (handled by DiGraph).
3. Subsample to ~2000 high-degree nodes for global core coverage.
4. Ensure weakly connected by adding minimal bridge edges if needed.
5. Renumber nodes to 0-N for Shadow compatibility.
6. Generate GML with realistic latency/bandwidth based on relationship types.
"""

import argparse
import networkx as nx
from collections import defaultdict

RELATIONSHIP_ATTRIBUTES = {
    '1': {'latency': '50ms', 'bandwidth': '100Mbit'},  # provider-to-customer
    '2': {'latency': '50ms', 'bandwidth': '100Mbit'},  # customer-to-provider
    '3': {'latency': '10ms', 'bandwidth': '1Gbit'},    # peer-peer
    '4': {'latency': '5ms', 'bandwidth': '10Gbit'},    # sibling-sibling
    'default': {'latency': '20ms', 'bandwidth': '500Mbit'}
}

def parse_caida_file(filepath):
    """Parse CAIDA cycle-aslinks file into directed NetworkX graph."""
    G = nx.DiGraph()
    line_count = 0
    edge_count = 0

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            line_count += 1
            if not line or line.startswith('#') or line.startswith('#INFO'):
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            link_type = parts[0]
            try:
                source = int(parts[1])
                target = int(parts[2])
                if source == target:
                    continue  # Skip self-loops

                if link_type in ['I', 'D'] and len(parts) >= 4:
                    rel = parts[3]
                else:
                    rel = 'default'

                G.add_edge(source, target, relation=rel)
                edge_count += 1
            except ValueError:
                continue

    # DiGraph automatically handles no duplicates/multi-edges
    print(f"Parsed {line_count} lines, loaded {G.number_of_nodes()} nodes, {edge_count} edges (after cleaning)")
    return G

def subsample_high_degree(G, target_nodes=2000):
    """Subsample prioritizing high-degree nodes."""
    if G.number_of_nodes() <= target_nodes:
        return G

    degrees = dict(G.degree())  # total degree (in + out)
    sorted_nodes = sorted(degrees, key=degrees.get, reverse=True)
    selected_nodes = sorted_nodes[:target_nodes]

    H = G.subgraph(selected_nodes).copy()
    print(f"Subsampled to {H.number_of_nodes()} high-degree nodes, {H.number_of_edges()} edges")
    return H

def ensure_weakly_connected(G):
    """Ensure the graph is weakly connected by adding minimal bridges."""
    U = G.to_undirected()
    if nx.is_connected(U):
        print("Graph is already weakly connected.")
        return G

    components = list(nx.connected_components(U))
    print(f"Found {len(components)} weakly connected components")

    # Select representatives (highest degree node in each component)
    reps = []
    for comp in components:
        comp_nodes = list(comp)
        rep = max(comp_nodes, key=lambda n: G.degree(n))
        reps.append(rep)

    # Choose central rep (highest degree overall among reps)
    central_idx = max(range(len(reps)), key=lambda i: G.degree(reps[i]))
    central = reps[central_idx]

    added_count = 0
    for i, rep in enumerate(reps):
        if i == central_idx:
            continue
        # Add bidirectional bridge edges (peer-peer relationship)
        if not G.has_edge(central, rep):
            G.add_edge(central, rep, relation='3')  # peer
            added_count += 1
        if not G.has_edge(rep, central):
            G.add_edge(rep, central, relation='3')  # peer
            added_count += 1

    print(f"Added {added_count} bridge edges to ensure weak connectivity.")
    return G

def renumber_graph(G):
    """Renumber nodes to 0-N and add original AS to node attributes."""
    nodes = sorted(G.nodes())
    old_to_new = {old: new for new, old in enumerate(nodes)}
    H = nx.relabel_nodes(G, old_to_new, copy=True)

    for old_id, new_id in old_to_new.items():
        H.nodes[new_id]['AS'] = str(old_id)

    return H, list(range(len(nodes)))

def write_gml(H, new_nodes, output_file):
    """Write the renumbered graph to GML format."""
    with open(output_file, 'w') as f:
        f.write("graph [\n")
        f.write("  directed 1\n\n")

        # Nodes
        for new_id in new_nodes:
            f.write("  node [\n")
            f.write(f"    id {new_id}\n")
            as_num = H.nodes[new_id].get('AS', str(new_id))
            f.write(f'    AS "{as_num}"\n')
            f.write('    bandwidth "1Gbit"\n')
            f.write("  ]\n\n")

        # Edges
        for source, target, data in H.edges(data=True):
            rel = data.get('relation', 'default')
            attrs = RELATIONSHIP_ATTRIBUTES.get(rel, RELATIONSHIP_ATTRIBUTES['default'])
            f.write("  edge [\n")
            f.write(f"    source {source}\n")
            f.write(f"    target {target}\n")
            f.write(f'    latency "{attrs["latency"]}"\n')
            f.write(f'    bandwidth "{attrs["bandwidth"]}"\n')
            f.write("  ]\n")

        f.write("]\n")

    print(f"Intermediate cleaned GML saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Create global CAIDA internet GML with ~2000 cleaned nodes")
    parser.add_argument("caida_file", help="Path to raw CAIDA cycle-aslinks file")
    parser.add_argument("output_gml", help="Path to output intermediate GML file")
    parser.add_argument("--target_nodes", type=int, default=2000, help="Target number of nodes (~2000)")

    args = parser.parse_args()

    # Parse and clean
    print("Step 1: Parsing and cleaning CAIDA file...")
    G = parse_caida_file(args.caida_file)

    # Subsample
    print("Step 2: Subsampling high-degree nodes...")
    H = subsample_high_degree(G, args.target_nodes)

    # Ensure connectivity
    print("Step 3: Ensuring weak connectivity...")
    H = ensure_weakly_connected(H)

    # Renumber
    print("Step 4: Renumbering nodes...")
    renumbered_H, new_nodes = renumber_graph(H)

    # Output
    print("Step 5: Writing intermediate GML...")
    write_gml(renumbered_H, new_nodes, args.output_gml)

    final_edges = renumbered_H.number_of_edges()
    print(f"Completed: {len(new_nodes)} nodes, {final_edges} edges in intermediate graph.")

if __name__ == "__main__":
    main()