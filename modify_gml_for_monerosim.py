#!/usr/bin/env python3
"""
Modify the intermediate GML file to add Monerosim-compatible attributes.
- Nodes: Update bandwidth based on degree tiers, add label
- Edges: Add packet_loss attribute with random values
"""

import networkx as nx
import random

def load_gml(file_path):
    """Load GML file using NetworkX."""
    print(f"Loading GML file: {file_path}")
    G = nx.read_gml(file_path, label=None)
    print(f"Loaded graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    return G

def modify_nodes(G):
    """Modify node attributes based on degree."""
    degrees = dict(G.degree())
    sorted_degrees = sorted(degrees.values())
    n = len(sorted_degrees)

    # Define tiers: low, medium, high
    low_threshold = sorted_degrees[n // 3]
    high_threshold = sorted_degrees[2 * n // 3]

    bandwidth_map = {
        'low': '500Mbit',
        'medium': '1000Mbit',
        'high': '10000Mbit'
    }

    for node in G.nodes():
        deg = degrees[node]
        if deg <= low_threshold:
            tier = 'low'
        elif deg <= high_threshold:
            tier = 'medium'
        else:
            tier = 'high'

        G.nodes[node]['bandwidth'] = bandwidth_map[tier]

        # Add label if AS exists
        if 'AS' in G.nodes[node]:
            as_num = G.nodes[node]['AS']
            G.nodes[node]['label'] = f"AS{as_num}"

    print("Modified node attributes")

def modify_edges(G):
    """Add packet_loss to edges with random values."""
    for u, v in G.edges():
        packet_loss = round(random.uniform(0.01, 0.3), 2)
        G.edges[u, v]['packet_loss'] = f"{packet_loss}%"

    print("Added packet_loss to edges")

def save_gml(G, output_path):
    """Save the modified graph to GML."""
    print(f"Saving modified GML to: {output_path}")
    nx.write_gml(G, output_path)
    print("Saved successfully")

def main():
    input_file = 'gml_processing/intermediate_global_caida.gml'
    output_file = 'global_caida_internet.gml'

    G = load_gml(input_file)
    modify_nodes(G)
    modify_edges(G)
    save_gml(G, output_file)

if __name__ == "__main__":
    main()