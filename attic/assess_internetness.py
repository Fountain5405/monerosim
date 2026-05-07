#!/usr/bin/env python3
"""
Assess how closely a MoneroSim simulation resembles the real Internet.

This script analyzes:
1. IP address distribution across geographic regions
2. Network topology latency characteristics
3. Agent placement and inter-agent latencies
4. Bandwidth distribution by region
5. Comparison to ideal global distribution

Usage:
    python scripts/assess_internetness.py [--config CONFIG] [--gml GML_FILE] [--shadow-data DIR]

Examples:
    # Analyze most recent simulation
    python scripts/assess_internetness.py

    # Analyze specific config
    python scripts/assess_internetness.py --config monerosim.expanded.yaml

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

# Real-world bandwidth benchmarks (Mbps) by region
# Source: Ookla Speedtest Global Index (2025) via World Population Review
# https://worldpopulationreview.com/country-rankings/internet-speeds-by-country
REAL_WORLD_BANDWIDTH = {
    # (min, median, max) in Mbps - represents typical range for the region
    "North America": (50, 250, 400),   # US 303, Canada 256, Mexico 92
    "Europe": (30, 170, 350),          # France 346, Germany 102, UK 163
    "Asia": (15, 130, 410),            # Singapore 407, Japan 230, India 62
    "South America": (20, 160, 360),   # Chile 357, Brazil 220, Argentina 110
    "Africa": (5, 28, 100),            # Egypt 92, South Africa 48, Nigeria 31
    "Oceania": (10, 70, 220),          # NZ 216, Australia 164, Fiji 13
}


def get_region_for_node(node_id: int, total_nodes: int = 1200) -> str:
    """Map a node/AS number to its geographic region."""
    boundaries = calculate_region_boundaries(total_nodes)
    for region, (start, end) in boundaries.items():
        if start <= node_id <= end:
            return region
    return "Unknown"


def parse_gml_topology(gml_path: Path) -> Tuple[Dict[int, dict], Dict[int, List[Tuple[int, int, int]]]]:
    """
    Parse GML topology file.

    Returns:
        nodes: Dict mapping node_id -> {as: str, region: str, bandwidth_mbps: int}
        edges: Dict mapping node_id -> [(neighbor, latency_ms, bandwidth_mbps), ...]
    """
    with open(gml_path) as f:
        content = f.read()

    # Parse nodes with all attributes
    nodes = {}
    # Match node blocks more flexibly
    node_pattern = r'node \[\s*id (\d+)\s*AS "(\d+)"\s*region "([^"]+)"\s*bandwidth "([^"]+)"'
    for match in re.finditer(node_pattern, content):
        node_id = int(match.group(1))
        as_num = match.group(2)
        region = match.group(3)
        bandwidth_str = match.group(4)
        bandwidth_mbps = parse_bandwidth(bandwidth_str)
        nodes[node_id] = {
            'as': as_num,
            'region': region,
            'bandwidth_mbps': bandwidth_mbps
        }

    # Fallback: if no nodes found with new pattern, try old pattern
    if not nodes:
        old_pattern = r'node \[\s*id (\d+)\s*AS "(\d+)"'
        for match in re.finditer(old_pattern, content):
            node_id = int(match.group(1))
            as_num = match.group(2)
            nodes[node_id] = {'as': as_num, 'region': 'unknown', 'bandwidth_mbps': 1000}

    # Parse edges with latency and bandwidth
    edges = defaultdict(list)
    edge_pattern = r'edge \[\s*source (\d+)\s*target (\d+)\s*latency "(\d+)ms"\s*bandwidth "([^"]+)"'
    for match in re.finditer(edge_pattern, content):
        src = int(match.group(1))
        tgt = int(match.group(2))
        lat = int(match.group(3))
        bw_str = match.group(4)
        bw_mbps = parse_bandwidth(bw_str)
        edges[src].append((tgt, lat, bw_mbps))

    # Fallback: if no edges found with new pattern, try old pattern
    if not edges:
        old_edge_pattern = r'edge \[\s*source (\d+)\s*target (\d+)\s*latency "(\d+)ms"'
        for match in re.finditer(old_edge_pattern, content):
            src = int(match.group(1))
            tgt = int(match.group(2))
            lat = int(match.group(3))
            edges[src].append((tgt, lat, 1000))  # Default 1Gbit

    return nodes, edges


def parse_bandwidth(bw_str: str) -> int:
    """Parse bandwidth string like '100Mbit' or '1Gbit' to Mbps."""
    bw_str = bw_str.strip().upper()
    if 'GBIT' in bw_str:
        return int(bw_str.replace('GBIT', '')) * 1000
    elif 'MBIT' in bw_str:
        return int(bw_str.replace('MBIT', ''))
    elif 'KBIT' in bw_str:
        return max(1, int(bw_str.replace('KBIT', '')) // 1000)
    else:
        # Try to parse as plain number (assume Mbit)
        try:
            return int(bw_str)
        except ValueError:
            return 1000  # Default 1Gbit


def dijkstra(edges: Dict[int, List[Tuple[int, int, int]]], start: int, num_nodes: int) -> Dict[int, float]:
    """Compute shortest path distances from start to all nodes."""
    dist = {i: float('inf') for i in range(num_nodes)}
    dist[start] = 0
    pq = [(0, start)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for edge in edges.get(u, []):
            v, w = edge[0], edge[1]  # neighbor, latency (ignore bandwidth for dijkstra)
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
        for edge in src_edges:
            latencies.append(edge[1])  # latency is second element

    lat_counter = Counter(latencies)
    print(f"\nEdge Latency Distribution:")
    for lat, count in sorted(lat_counter.items()):
        pct = count / len(latencies) * 100
        edge_type = "self-loop/intra-AS" if lat <= 1 else ("regional" if lat <= 10 else "inter-continental")
        print(f"  {lat}ms: {count:,} edges ({pct:.1f}%) - {edge_type}")

    # Regional distribution of nodes
    print(f"\nNode Distribution by Region:")
    region_counts = Counter(get_region_for_node(int(node_data['as']), num_nodes) for node_data in nodes.values())
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
        "nodes": nodes,  # Pass along for bandwidth analysis
        "edges": edges,
    }


def analyze_gml_bandwidth(gml_path: Path, topology_results: Optional[Dict] = None) -> Dict:
    """Analyze bandwidth distribution in the GML topology."""
    print(f"\n{'='*70}")
    print("BANDWIDTH ANALYSIS")
    print(f"{'='*70}")

    # Use pre-parsed data if available, otherwise parse
    if topology_results and 'nodes' in topology_results:
        nodes = topology_results['nodes']
        edges = topology_results['edges']
    else:
        nodes, edges = parse_gml_topology(gml_path)

    num_nodes = len(nodes)
    if num_nodes == 0:
        print("  ERROR: No nodes found in GML file")
        return {"bandwidth_score": 0}

    # Collect node bandwidths by region
    region_bandwidths = defaultdict(list)
    all_node_bw = []

    for node_id, node_data in nodes.items():
        bw = node_data.get('bandwidth_mbps', 1000)
        region = node_data.get('region', 'unknown')
        # Normalize region name for comparison
        region_normalized = region.replace('_', ' ').title()
        region_bandwidths[region_normalized].append(bw)
        all_node_bw.append(bw)

    # Collect edge bandwidths
    all_edge_bw = []
    for src_edges in edges.values():
        for edge in src_edges:
            if len(edge) >= 3:
                all_edge_bw.append(edge[2])  # bandwidth is third element

    # Print node bandwidth statistics
    print(f"\nNode Bandwidth Statistics:")
    if all_node_bw:
        sorted_bw = sorted(all_node_bw)
        print(f"  Total nodes: {len(all_node_bw)}")
        print(f"  Min: {min(all_node_bw)} Mbit")
        print(f"  Max: {max(all_node_bw)} Mbit")
        print(f"  Median: {sorted_bw[len(sorted_bw)//2]} Mbit")
        print(f"  Mean: {sum(all_node_bw)//len(all_node_bw)} Mbit")

    # Print edge bandwidth statistics
    print(f"\nEdge Bandwidth Statistics:")
    if all_edge_bw:
        sorted_edge_bw = sorted(all_edge_bw)
        non_selfloop = [b for b in all_edge_bw if b < 10000]  # Exclude self-loops
        print(f"  Total edges: {len(all_edge_bw)}")
        if non_selfloop:
            print(f"  Non-self-loop edges: {len(non_selfloop)}")
            print(f"  Min: {min(non_selfloop)} Mbit")
            print(f"  Max: {max(non_selfloop)} Mbit")
            print(f"  Median: {sorted(non_selfloop)[len(non_selfloop)//2]} Mbit")

    # Compare per-region bandwidth to real-world data
    print(f"\nPer-Region Bandwidth Comparison:")
    print(f"  {'Region':<20} {'Sim Median':>12} {'Real-World':>20} {'Assessment':>12}")
    print(f"  {'-'*20} {'-'*12} {'-'*20} {'-'*12}")

    bandwidth_scores = []

    for region in ["North America", "Europe", "Asia", "South America", "Africa", "Oceania"]:
        bw_list = region_bandwidths.get(region, [])
        if not bw_list:
            print(f"  {region:<20} {'N/A':>12} {'N/A':>20} {'NO DATA':>12}")
            continue

        sim_median = sorted(bw_list)[len(bw_list) // 2]
        real_min, real_median, real_max = REAL_WORLD_BANDWIDTH.get(region, (0, 100, 200))
        real_range = f"{real_min}-{real_max} Mbit"

        # Score based on how close to real median, with tolerance
        tolerance = 0.5  # Allow 50% deviation
        deviation = abs(sim_median - real_median) / real_median if real_median > 0 else 1.0

        if deviation <= tolerance * 0.5:
            assessment = "EXCELLENT"
            score = 100
        elif deviation <= tolerance:
            assessment = "GOOD"
            score = 80
        elif real_min <= sim_median <= real_max:
            assessment = "ACCEPTABLE"
            score = 60
        elif sim_median < real_min:
            assessment = "TOO LOW"
            score = max(0, 40 - (real_min - sim_median) / real_min * 40)
        else:
            assessment = "TOO HIGH"
            score = max(0, 40 - (sim_median - real_max) / real_max * 40)

        bandwidth_scores.append(score)
        print(f"  {region:<20} {sim_median:>10} Mbit {real_range:>20} {assessment:>12}")

    # Check bandwidth diversity
    print(f"\nBandwidth Diversity Check:")
    unique_bw = len(set(all_node_bw))
    diversity_pct = unique_bw / len(all_node_bw) * 100 if all_node_bw else 0

    if unique_bw == 1:
        print(f"  WARNING: All nodes have identical bandwidth ({all_node_bw[0]} Mbit)")
        print(f"           This is NOT realistic - real Internet has high variance")
        diversity_score = 0
    elif diversity_pct < 5:
        print(f"  NOTICE: Low bandwidth diversity ({unique_bw} unique values, {diversity_pct:.1f}%)")
        diversity_score = 30
    elif diversity_pct < 20:
        print(f"  OK: Moderate bandwidth diversity ({unique_bw} unique values, {diversity_pct:.1f}%)")
        diversity_score = 60
    else:
        print(f"  GOOD: High bandwidth diversity ({unique_bw} unique values, {diversity_pct:.1f}%)")
        diversity_score = 100

    # Calculate overall bandwidth score
    region_score = sum(bandwidth_scores) / len(bandwidth_scores) if bandwidth_scores else 0
    overall_score = (region_score * 0.7 + diversity_score * 0.3)  # 70% region accuracy, 30% diversity

    print(f"\n  Regional Accuracy Score: {region_score:.1f}/100")
    print(f"  Diversity Score: {diversity_score:.1f}/100")
    print(f"  Overall Bandwidth Score: {overall_score:.1f}/100")

    return {
        "node_bandwidth_min": min(all_node_bw) if all_node_bw else 0,
        "node_bandwidth_max": max(all_node_bw) if all_node_bw else 0,
        "node_bandwidth_median": sorted(all_node_bw)[len(all_node_bw)//2] if all_node_bw else 0,
        "unique_bandwidths": unique_bw,
        "region_bandwidths": {k: sorted(v)[len(v)//2] if v else 0 for k, v in region_bandwidths.items()},
        "bandwidth_score": overall_score,
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


def print_overall_assessment(topology_results: Dict, placement_results: Dict,
                             latency_results: Dict, bandwidth_results: Dict):
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

    if bandwidth_results:
        score = bandwidth_results.get('bandwidth_score', 0)
        scores.append(('Bandwidth Realism', score))
        print(f"  Bandwidth Realism: {score:.1f}/100")

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
        help='Path to monerosim config file (e.g. monerosim.expanded.yaml)'
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
        'bandwidth': {},
    }

    # Analyze GML topology
    if gml_path and gml_path.exists():
        results['topology'] = analyze_gml_topology(gml_path)

        # Analyze bandwidth (uses parsed topology data)
        results['bandwidth'] = analyze_gml_bandwidth(gml_path, results['topology'])
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
        results['latency'],
        results['bandwidth']
    )
    results['overall_score'] = overall_score

    # JSON output (clean up internal data before serializing)
    if args.json:
        # Remove internal data not meant for JSON output
        if 'nodes' in results.get('topology', {}):
            del results['topology']['nodes']
        if 'edges' in results.get('topology', {}):
            del results['topology']['edges']

        print(f"\n{'='*70}")
        print("JSON OUTPUT")
        print("=" * 70)
        print(json.dumps(results, indent=2))

    return 0 if overall_score >= 50 else 1


if __name__ == "__main__":
    sys.exit(main())
