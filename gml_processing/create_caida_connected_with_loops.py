#!/usr/bin/env python3
"""
Create a sparse connected GML from raw CAIDA AS-links data with self-loops.
Steps:
1. Parse AS-links to build undirected graph with relationship info.
2. Find largest connected component, limit to max_nodes.
3. Add self-loops to all nodes in component.
4. Renumber nodes to 0-N for Shadow.
5. Generate GML with realistic latency/bandwidth based on relationship types.
"""

import argparse
from collections import defaultdict, deque

RELATIONSHIP_ATTRIBUTES = {
    '-1': {'latency': '50ms', 'bandwidth': '100Mbit'},  # Customer-provider
    '0': {'latency': '10ms', 'bandwidth': '1Gbit'},     # Peer-peer
    '-2': {'latency': '5ms', 'bandwidth': '10Gbit'},    # Sibling
    'default': {'latency': '20ms', 'bandwidth': '500Mbit'}
}

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
    """Add self-loops and prepare attributes for GML."""
    gml_graph = defaultdict(dict)
    
    # Add original edges with attributes
    for source in component:
        for target, rel_type in graph[source].items():
            if target in component:  # Only within component
                attrs = RELATIONSHIP_ATTRIBUTES.get(rel_type, RELATIONSHIP_ATTRIBUTES['default'])
                gml_graph[source][target] = attrs
    
    # Add self-loops for all nodes
    for node in component:
        gml_graph[node][node] = {'latency': '1ms', 'bandwidth': '10Gbit'}  # Local loop
    
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
    """Write renumbered graph to GML."""
    with open(output_file, 'w') as f:
        f.write("graph [\n")
        f.write("  directed 1\n\n")
        
        # Nodes
        for new_id in new_nodes:
            f.write(f"  node [\n")
            f.write(f"    id {new_id}\n")
            f.write(f'    AS "{new_id}"\n')  # Use ID as AS for simplicity
            f.write('    bandwidth "1Gbit"\n')
            f.write("  ]\n\n")
        
        # Edges
        for source in new_graph:
            for target, attrs in new_graph[source].items():
                f.write("  edge [\n")
                f.write(f"    source {source}\n")
                f.write(f"    target {target}\n")
                f.write(f'    latency "{attrs["latency"]}"\n')
                f.write(f'    bandwidth "{attrs["bandwidth"]}"\n')
                f.write("  ]\n")
        
        f.write("]\n")
    
    print(f"GML saved to {output_file}")

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