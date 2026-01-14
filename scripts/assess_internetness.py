#!/usr/bin/env python3
"""
Assess how closely a MoneroSim simulation resembles the real Internet.

This script analyzes:
1. IP address distribution across geographic regions
2. Network topology latency characteristics
3. Agent placement and inter-agent latencies
4. Comparison to ideal global distribution

Usage:
    python scripts/assess_internetness.py [--config CONFIG] [--gml GML_FILE] [--shadow-data DIR]

Examples:
    # Analyze most recent simulation
    python scripts/assess_internetness.py

    # Analyze specific config
    python scripts/assess_internetness.py --config monerosim.yaml

    # Analyze GML topology only
    python scripts/assess_internetness.py --gml gml_processing/1200_nodes_caida_with_loops.gml
"""

import argparse
import heapq
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Default region proportions (matches src/ip/as_manager.rs)
# These are applied proportionally to any topology size
REGION_PROPORTIONS = [
    ("North America", 16.67),
    ("Europe", 25.0),
    ("Asia", 25.0),
    ("South America", 16.67),
    ("Africa", 8.33),
    ("Oceania", 8.33),
]


def calculate_region_boundaries(total_nodes: int) -> Dict[str, Tuple[int, int]]:
    """
    Calculate region boundaries proportionally for any topology size.
    Matches the logic in src/ip/as_manager.rs:calculate_region_boundaries().
    """
    if total_nodes == 0:
        return {region: (0, 0) for region, _ in REGION_PROPORTIONS}

    boundaries = {}
    start = 0

    for i, (region, proportion) in enumerate(REGION_PROPORTIONS):
        count = round(total_nodes * proportion / 100.0)
        if i == 5:  # Last region gets remaining nodes
            end = total_nodes - 1
        else:
            end = min(start + count - 1, total_nodes - 1)
        boundaries[region] = (start, end)
        start = end + 1

    return boundaries


# Legacy static mapping for backward compatibility (1200-node topology)
REGION_MAPPING = calculate_region_boundaries(1200)

# Real-world Internet latency benchmarks (approximate RTT in ms)
REAL_WORLD_LATENCIES = {
    ("North America", "North America"): (10, 50),
    ("North America", "Europe"): (70, 120),
    ("North America", "Asia"): (150, 250),
    ("North America", "South America"): (100, 180),
    ("North America", "Africa"): (180, 280),
    ("North America", "Oceania"): (150, 220),
    ("Europe", "Europe"): (10, 40),
    ("Europe", "Asia"): (100, 200),
    ("Europe", "South America"): (180, 280),
    ("Europe", "Africa"): (80, 150),
    ("Europe", "Oceania"): (250, 350),
    ("Asia", "Asia"): (20, 80),
    ("Asia", "South America"): (250, 350),
    ("Asia", "Africa"): (150, 250),
    ("Asia", "Oceania"): (80, 150),
    ("South America", "South America"): (30, 80),
    ("South America", "Africa"): (250, 350),
    ("South America", "Oceania"): (200, 300),
    ("Africa", "Africa"): (30, 100),
    ("Africa", "Oceania"): (200, 300),
    ("Oceania", "Oceania"): (20, 60),
}


def get_region_for_node(node_id: int, total_nodes: int = 1200) -> str:
    """Map a node/AS number to its geographic region."""
    boundaries = calculate_region_boundaries(total_nodes)
    for region, (start, end) in boundaries.items():
        if start <= node_id <= end:
            return region
    return "Unknown"


def parse_gml_topology(gml_path: Path) -> Tuple[Dict[int, str], Dict[int, List[Tuple[int, int]]]]:
    """
    Parse GML topology file.

    Returns:
        nodes: Dict mapping node_id -> AS number string
        edges: Dict mapping node_id -> [(neighbor, latency_ms), ...]
    """
    with open(gml_path) as f:
        content = f.read()

    # Parse nodes
    nodes = {}
    node_pattern = r'node \[\s*id (\d+)\s*AS "(\d+)"'
    for match in re.finditer(node_pattern, content):
        node_id = int(match.group(1))
        as_num = match.group(2)
        nodes[node_id] = as_num

    # Parse edges with latency
    edges = defaultdict(list)
    edge_pattern = r'edge \[\s*source (\d+)\s*target (\d+)\s*latency "(\d+)ms"'
    for match in re.finditer(edge_pattern, content):
        src = int(match.group(1))
        tgt = int(match.group(2))
        lat = int(match.group(3))
        edges[src].append((tgt, lat))

    return nodes, edges


def dijkstra(edges: Dict[int, List[Tuple[int, int]]], start: int, num_nodes: int) -> Dict[int, float]:
    """Compute shortest path distances from start to all nodes."""
    dist = {i: float('inf') for i in range(num_nodes)}
    dist[start] = 0
    pq = [(0, start)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in edges.get(u, []):
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(pq, (dist[v], v))
    return dist


def analyze_gml_topology(gml_path: Path) -> Dict:
    """Analyze the GML topology file."""
    print(f"\n{'='*70}")
    print("GML TOPOLOGY ANALYSIS")
    print(f"{'='*70}")
    print(f"File: {gml_path}")

    nodes, edges = parse_gml_topology(gml_path)

    # Basic stats
    num_nodes = len(nodes)
    num_edges = sum(len(e) for e in edges.values())

    print(f"\nBasic Statistics:")
    print(f"  Total nodes: {num_nodes}")
    print(f"  Total edges: {num_edges}")
    print(f"  Average degree: {num_edges / num_nodes:.1f}")

    # Edge latency distribution
    latencies = []
    for src_edges in edges.values():
        for _, lat in src_edges:
            latencies.append(lat)

    lat_counter = Counter(latencies)
    print(f"\nEdge Latency Distribution:")
    for lat, count in sorted(lat_counter.items()):
        pct = count / len(latencies) * 100
        edge_type = "self-loop/intra-AS" if lat <= 1 else ("regional" if lat <= 10 else "inter-continental")
        print(f"  {lat}ms: {count:,} edges ({pct:.1f}%) - {edge_type}")

    # Regional distribution of nodes
    print(f"\nNode Distribution by Region:")
    region_counts = Counter(get_region_for_node(int(as_num), num_nodes) for as_num in nodes.values())
    for region, count in sorted(region_counts.items(), key=lambda x: -x[1]):
        pct = count / num_nodes * 100
        print(f"  {region}: {count} nodes ({pct:.1f}%)")

    # Compute sample shortest-path latencies
    print(f"\nShortest-Path Latency Analysis (sampled):")

    # Sample one node from each region
    sample_nodes = {}
    for region, (start, end) in REGION_MAPPING.items():
        # Pick middle node in range
        mid = (start + end) // 2
        if mid < num_nodes:
            sample_nodes[region] = mid

    # Compute distances from sample nodes
    sample_distances = {}
    for region, node in sample_nodes.items():
        sample_distances[region] = dijkstra(edges, node, num_nodes)

    # Print inter-region latencies
    print(f"\n  Inter-Region Latencies (simulated vs real-world):")
    print(f"  {'Route':<40} {'Simulated':>12} {'Real-World':>15} {'Assessment':>12}")
    print(f"  {'-'*40} {'-'*12} {'-'*15} {'-'*12}")

    assessment_scores = []
    for region1 in sample_nodes:
        for region2 in sample_nodes:
            if region1 >= region2:
                continue

            node1 = sample_nodes[region1]
            node2 = sample_nodes[region2]
            sim_lat = sample_distances[region1].get(node2, float('inf'))

            # Get real-world benchmark
            key = (region1, region2) if (region1, region2) in REAL_WORLD_LATENCIES else (region2, region1)
            real_min, real_max = REAL_WORLD_LATENCIES.get(key, (0, 0))

            if sim_lat == float('inf'):
                assessment = "UNREACHABLE"
                score = 0
            elif real_min <= sim_lat <= real_max:
                assessment = "REALISTIC"
                score = 100
            elif sim_lat < real_min:
                assessment = "TOO FAST"
                score = max(0, 100 - (real_min - sim_lat) / real_min * 100)
            else:
                assessment = "TOO SLOW"
                score = max(0, 100 - (sim_lat - real_max) / real_max * 100)

            assessment_scores.append(score)
            route = f"{region1} <-> {region2}"
            real_range = f"{real_min}-{real_max}ms"
            print(f"  {route:<40} {sim_lat:>10.0f}ms {real_range:>15} {assessment:>12}")

    avg_score = sum(assessment_scores) / len(assessment_scores) if assessment_scores else 0
    print(f"\n  Latency Realism Score: {avg_score:.1f}/100")

    return {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "latency_distribution": dict(lat_counter),
        "region_distribution": dict(region_counts),
        "latency_realism_score": avg_score,
    }


def analyze_shadow_config(config_path: Path, total_nodes: int = 1200) -> Dict:
    """Analyze Shadow processed config for agent placement."""
    print(f"\n{'='*70}")
    print("AGENT PLACEMENT ANALYSIS")
    print(f"{'='*70}")
    print(f"Config: {config_path}")

    if not HAS_YAML:
        print("  ERROR: PyYAML not installed. Run: pip install pyyaml")
        return {}

    with open(config_path) as f:
        config = yaml.safe_load(f)

    hosts = config.get('hosts', {})

    agents = []
    for host_name, host_data in hosts.items():
        ip = host_data.get('ip_addr', 'unknown')
        node_id = host_data.get('network_node_id', -1)
        region = get_region_for_node(node_id, total_nodes)
        agents.append({
            'name': host_name,
            'ip': ip,
            'node_id': node_id,
            'region': region
        })

    # Sort by node_id
    agents.sort(key=lambda x: (x['node_id'], x['name']))

    print(f"\nAgent Distribution:")
    print(f"  {'Agent':<25} {'IP Address':<18} {'Network Node':<12} {'Region'}")
    print(f"  {'-'*25} {'-'*18} {'-'*12} {'-'*20}")

    for agent in agents[:20]:  # Show first 20
        print(f"  {agent['name']:<25} {agent['ip']:<18} {agent['node_id']:<12} {agent['region']}")

    if len(agents) > 20:
        print(f"  ... and {len(agents) - 20} more agents")

    # Regional summary
    print(f"\n{'='*70}")
    print("REGIONAL DISTRIBUTION SUMMARY")
    print(f"{'='*70}")

    region_counts = Counter(a['region'] for a in agents)
    total = len(agents)

    print(f"\n  {'Region':<20} {'Agents':>10} {'Percentage':>12} {'Assessment'}")
    print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*20}")

    # Expected distribution for "global" internet
    expected_pct = {
        "North America": 16.7,
        "Europe": 25.0,
        "Asia": 25.0,
        "South America": 16.7,
        "Africa": 8.3,
        "Oceania": 8.3,
    }

    distribution_score = 0
    for region in ["North America", "Europe", "Asia", "South America", "Africa", "Oceania", "Unknown"]:
        count = region_counts.get(region, 0)
        pct = count / total * 100 if total > 0 else 0
        expected = expected_pct.get(region, 0)

        if region == "Unknown":
            assessment = "" if count == 0 else "UNEXPECTED"
        elif count == 0:
            assessment = "MISSING"
        elif abs(pct - expected) < 5:
            assessment = "GOOD"
            distribution_score += 100 / 6
        elif abs(pct - expected) < 15:
            assessment = "ACCEPTABLE"
            distribution_score += 50 / 6
        else:
            assessment = "SKEWED"

        print(f"  {region:<20} {count:>10} {pct:>11.1f}% {assessment}")

    print(f"\n  Distribution Score: {distribution_score:.1f}/100")

    # Unique nodes used
    unique_nodes = set(a['node_id'] for a in agents)
    print(f"\n  Total agents: {total}")
    print(f"  Unique network nodes: {len(unique_nodes)}")
    print(f"  Node range: {min(unique_nodes)} - {max(unique_nodes)}")

    # Check for clustering
    if max(unique_nodes) - min(unique_nodes) < total * 2:
        print(f"\n  WARNING: Agents are clustered in a narrow node range!")
        print(f"           This does NOT simulate a global Internet.")

    return {
        "total_agents": total,
        "unique_nodes": len(unique_nodes),
        "region_distribution": dict(region_counts),
        "distribution_score": distribution_score,
    }


def analyze_agent_latencies(gml_path: Path, config_path: Path) -> Dict:
    """Compute actual latencies between agents in the simulation."""
    print(f"\n{'='*70}")
    print("INTER-AGENT LATENCY ANALYSIS")
    print(f"{'='*70}")

    if not HAS_YAML:
        print("  ERROR: PyYAML not installed")
        return {}

    # Load topology
    nodes, edges = parse_gml_topology(gml_path)
    num_nodes = len(nodes)

    # Load agent placements
    with open(config_path) as f:
        config = yaml.safe_load(f)

    hosts = config.get('hosts', {})
    agent_nodes = {}
    for host_name, host_data in hosts.items():
        node_id = host_data.get('network_node_id', 0)
        agent_nodes[host_name] = node_id

    if len(agent_nodes) < 2:
        print("  Not enough agents for latency analysis")
        return {}

    # Compute all-pairs shortest paths for agent nodes
    unique_agent_nodes = set(agent_nodes.values())
    node_distances = {}

    print(f"  Computing shortest paths for {len(unique_agent_nodes)} unique agent nodes...")
    for node in unique_agent_nodes:
        node_distances[node] = dijkstra(edges, node, num_nodes)

    # Compute pairwise latencies
    agent_names = sorted(agent_nodes.keys())
    latencies = []

    for i, agent1 in enumerate(agent_names):
        for agent2 in agent_names[i+1:]:
            node1 = agent_nodes[agent1]
            node2 = agent_nodes[agent2]
            lat = node_distances[node1].get(node2, float('inf'))
            if lat != float('inf'):
                latencies.append(lat)

    if not latencies:
        print("  No valid latencies computed (agents may be unreachable)")
        return {}

    print(f"\n  Pairwise Latency Statistics:")
    print(f"    Total pairs: {len(latencies)}")
    print(f"    Min latency: {min(latencies):.0f}ms")
    print(f"    Max latency: {max(latencies):.0f}ms")
    print(f"    Mean latency: {sum(latencies)/len(latencies):.1f}ms")
    print(f"    Median latency: {sorted(latencies)[len(latencies)//2]:.0f}ms")

    # Latency buckets
    buckets = {
        '0-20ms (local)': 0,
        '20-50ms (regional)': 0,
        '50-100ms (continental)': 0,
        '100-200ms (inter-continental)': 0,
        '200+ms (global)': 0,
    }

    for lat in latencies:
        if lat <= 20:
            buckets['0-20ms (local)'] += 1
        elif lat <= 50:
            buckets['20-50ms (regional)'] += 1
        elif lat <= 100:
            buckets['50-100ms (continental)'] += 1
        elif lat <= 200:
            buckets['100-200ms (inter-continental)'] += 1
        else:
            buckets['200+ms (global)'] += 1

    print(f"\n  Latency Distribution:")
    for bucket, count in buckets.items():
        pct = count / len(latencies) * 100
        bar = '#' * int(pct / 2)
        print(f"    {bucket:<30} {count:>5} ({pct:>5.1f}%) {bar}")

    # Assessment
    print(f"\n  Assessment:")
    if max(latencies) < 60:
        print("    WARNING: All latencies < 60ms - agents are too close together!")
        print("             Real Internet has 100-300ms latencies between continents.")
        latency_score = 20
    elif max(latencies) < 100:
        print("    NOTICE: Max latency < 100ms - limited geographic diversity")
        latency_score = 50
    else:
        print("    GOOD: Latency range suggests reasonable geographic distribution")
        latency_score = 80

    return {
        "min_latency": min(latencies),
        "max_latency": max(latencies),
        "mean_latency": sum(latencies) / len(latencies),
        "latency_buckets": buckets,
        "latency_score": latency_score,
    }


def print_overall_assessment(topology_results: Dict, placement_results: Dict, latency_results: Dict):
    """Print overall internetness assessment."""
    print(f"\n{'='*70}")
    print("OVERALL INTERNETNESS ASSESSMENT")
    print(f"{'='*70}")

    scores = []

    if topology_results:
        score = topology_results.get('latency_realism_score', 0)
        scores.append(('Topology Realism', score))
        print(f"\n  Topology Latency Realism: {score:.1f}/100")

    if placement_results:
        score = placement_results.get('distribution_score', 0)
        scores.append(('Agent Distribution', score))
        print(f"  Agent Regional Distribution: {score:.1f}/100")

    if latency_results:
        score = latency_results.get('latency_score', 0)
        scores.append(('Inter-Agent Latency', score))
        print(f"  Inter-Agent Latency Diversity: {score:.1f}/100")

    if scores:
        overall = sum(s for _, s in scores) / len(scores)
        print(f"\n  {'='*40}")
        print(f"  OVERALL INTERNETNESS SCORE: {overall:.1f}/100")
        print(f"  {'='*40}")

        if overall >= 80:
            print("\n  Assessment: EXCELLENT - Network closely resembles global Internet")
        elif overall >= 60:
            print("\n  Assessment: GOOD - Network has reasonable Internet characteristics")
        elif overall >= 40:
            print("\n  Assessment: FAIR - Network has some Internet-like properties")
        else:
            print("\n  Assessment: POOR - Network does NOT resemble global Internet")
            print("              Consider enabling global agent distribution.")

    return overall if scores else 0


def main():
    parser = argparse.ArgumentParser(
        description="Assess how closely a MoneroSim simulation resembles the real Internet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to monerosim.yaml config file'
    )
    parser.add_argument(
        '--gml', '-g',
        type=Path,
        help='Path to GML topology file'
    )
    parser.add_argument(
        '--shadow-data', '-s',
        type=Path,
        help='Path to shadow.data directory'
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    # Find files
    base_dir = Path(__file__).parent.parent

    # GML file
    gml_path = args.gml
    if not gml_path:
        # Try to find from config or default location
        default_gml = base_dir / 'gml_processing' / '1200_nodes_caida_with_loops.gml'
        if default_gml.exists():
            gml_path = default_gml

    # Shadow data directory
    shadow_data = args.shadow_data
    if not shadow_data:
        default_shadow = base_dir / 'shadow.data'
        if default_shadow.exists():
            shadow_data = default_shadow

    # Processed config - try multiple possible names
    processed_config = None
    if shadow_data:
        # Try different config file names
        config_names = ['shadow_agents.yaml', 'processed-config.yaml', 'shadow.yaml']
        for name in config_names:
            candidate = shadow_data / name
            if candidate.exists():
                processed_config = candidate
                break

    print("=" * 70)
    print("MONEROSIM INTERNETNESS ASSESSMENT")
    print("=" * 70)
    print(f"\nAnalyzing simulation network characteristics...")

    results = {
        'topology': {},
        'placement': {},
        'latency': {},
    }

    # Analyze GML topology
    if gml_path and gml_path.exists():
        results['topology'] = analyze_gml_topology(gml_path)
    else:
        print(f"\nWARNING: No GML topology file found")
        if args.gml:
            print(f"         Specified file does not exist: {args.gml}")

    # Analyze agent placement
    if processed_config and processed_config.exists():
        total_nodes = results['topology'].get('num_nodes', 1200)
        results['placement'] = analyze_shadow_config(processed_config, total_nodes)

        # Analyze inter-agent latencies
        if gml_path and gml_path.exists():
            results['latency'] = analyze_agent_latencies(gml_path, processed_config)
    else:
        print(f"\nWARNING: No processed Shadow config found")
        print(f"         Run a simulation first to generate shadow.data/processed-config.yaml")

    # Overall assessment
    overall_score = print_overall_assessment(
        results['topology'],
        results['placement'],
        results['latency']
    )
    results['overall_score'] = overall_score

    # JSON output
    if args.json:
        print(f"\n{'='*70}")
        print("JSON OUTPUT")
        print("=" * 70)
        print(json.dumps(results, indent=2))

    return 0 if overall_score >= 50 else 1


if __name__ == "__main__":
    sys.exit(main())
