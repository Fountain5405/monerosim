#!/usr/bin/env python3
"""
Network Connectivity Analysis Script for Monerosim

This script analyzes Shadow simulation logs to determine the actual Monero P2P network topology.
It parses connection logs, builds network graphs, analyzes IP address usage with geolocation,
and provides insights into connectivity issues.

Usage:
    python analyze_network_connectivity.py --config CONFIG_FILE [--logs LOG_DIR] [--output OUTPUT_DIR]

Arguments:
    --config: Path to the simulation config file (required)
    --logs: Path to shadow.data/hosts directory (default: /home/lever65/monerosim_dev/monerosim/shadow.data/hosts)
    --output: Output directory for analysis results (default: analysis_results subfolder in /home/lever65/monerosim_dev/monerosim)

Output Files:
    - network_graph.json: Network topology data
    - network_summary.txt: Human-readable analysis summary
    - network_topology.graphml: GraphML format for visualization
    - connection_details.json: Detailed connection events
    - ip_analysis.json: Comprehensive IP address analysis
    - ip_analysis_summary.txt: IP usage summary with geolocation data
"""

import argparse
import json
import os
import re
import sys
import requests
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

import networkx as nx
from networkx.readwrite import graphml

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.error_handling import log_error, log_info, log_warning
from agents.agent_discovery import AgentDiscovery

# Constants
DEFAULT_BASE_DIR = "/home/lever65/monerosim_dev/monerosim"
DEFAULT_LOGS_DIR = f"{DEFAULT_BASE_DIR}/shadow.data/hosts"
DEFAULT_OUTPUT_DIR = f"{DEFAULT_BASE_DIR}/analysis_results"
IPAPI_TIMEOUT = 5
MAX_RETRIES = 3


def find_latest_shadow_data(base_dir: str = DEFAULT_BASE_DIR) -> Path:
    """Find the most recent shadow.data directory, prioritizing current workspace."""
    workspace = Path(base_dir)
    current_shadow_path = workspace / 'shadow.data'
    if current_shadow_path.exists():
        return current_shadow_path

    # Fallback to dated subdirectories
    shadow_dirs = []
    for d in workspace.iterdir():
        if d.is_dir() and re.match(r'\d{8}', d.name):
            shadow_path = d / 'shadow.data'
            if shadow_path.exists():
                shadow_dirs.append((d.stat().st_mtime, shadow_path))

    if not shadow_dirs:
        return Path(f'{base_dir}/shadow.data')  # Fallback to default

    shadow_dirs.sort(reverse=True)
    return shadow_dirs[0][1]


def find_latest_shadow_config(base_dir: str = DEFAULT_BASE_DIR) -> Path:
    """Find the most recent shadow_agents.yaml in shadow_agents_output directories."""
    workspace = Path(base_dir)
    config_files = []
    for d in workspace.iterdir():
        if d.is_dir() and d.name.startswith('shadow_agents_output'):
            config_path = d / 'shadow_agents.yaml'
            if config_path.exists():
                config_files.append((d.stat().st_mtime, config_path))

    if not config_files:
        return Path(f'{base_dir}/shadow_agents_output/shadow_agents.yaml')  # Fallback

    config_files.sort(reverse=True)
    return config_files[0][1]


class NetworkConnectivityAnalyzer:
    """Analyzes Monero P2P network connectivity from Shadow logs."""

    def __init__(self, config_file: str, logs_dir: str, output_dir: str):
        self.config_file = Path(config_file)
        self.logs_dir = Path(logs_dir)
        # Create output directory in monerosim root
        monerosim_root = Path(DEFAULT_BASE_DIR)
        self.output_dir = monerosim_root / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_config()
        self.gml_file = self._get_gml_file()

        # Initialize agent discovery
        self.agent_discovery = AgentDiscovery()

        # Data structures
        self.connections = defaultdict(set)  # node -> set of connected nodes
        self.connection_events = []  # List of connection events
        self.node_info = {}  # node -> info dict
        self.ip_to_node = {}  # ip -> node_name
        self.ip_analysis = defaultdict(lambda: {'count': 0, 'ports': set(), 'geolocation': None})

        # Log patterns - only successful connections
        self.successful_connection_pattern = re.compile(
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\s+I\s+\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+[^\]]*\]\s+New connection handshaked'
        )

    def _load_config(self) -> dict:
        """Load the simulation configuration file."""
        try:
            import yaml
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            log_error("NetworkConnectivityAnalyzer", f"Failed to load config file {self.config_file}: {e}")
            return {}

    def _get_gml_file(self) -> Optional[Path]:
        """Get the GML topology file from config."""
        network_config = self.config.get('network', {})
        gml_path = network_config.get('path')
        if gml_path:
            return Path(gml_path)
        return None

    def _parse_log_file(self, log_file: Path) -> None:
        """Parse a single log file for successful connection events."""
        node_name = log_file.parent.name  # Extract node name from path

        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    # Extract timestamp if available
                    timestamp_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
                    timestamp = timestamp_match.group(0) if timestamp_match else f"line_{line_num}"

                    # Check for successful connections
                    successful_conn = self.successful_connection_pattern.search(line)
                    if successful_conn:
                        ip, port = successful_conn.groups()
                        self._handle_successful_connection(node_name, ip, port, timestamp)

        except Exception as e:
            log_warning("NetworkConnectivityAnalyzer", f"Error parsing log file {log_file}: {e}")

    def _handle_successful_connection(self, node_name: str, ip: str, port: str, timestamp: str) -> None:
        """Handle a successful connection event."""
        # Track IP analysis data
        self.ip_analysis[ip]['count'] += 1
        self.ip_analysis[ip]['ports'].add(port)

        # Map IP to node name
        target_node = self.ip_to_node.get(ip)
        if not target_node:
            target_node = self._find_node_by_ip(ip)
            if target_node:
                self.ip_to_node[ip] = target_node

        if target_node and target_node != node_name:
            # Record directed connection
            self.connections[node_name].add(target_node)

            self.connection_events.append({
                'timestamp': timestamp,
                'event_type': 'successful_connection',
                'source_node': node_name,
                'target_node': target_node,
                'ip': ip,
                'port': port
            })

    def _find_node_by_ip(self, ip: str) -> Optional[str]:
        """Find node name by IP address."""
        # Try agent registry first
        try:
            registry = self.agent_discovery.get_agent_registry()
            for agent in registry:
                if isinstance(agent, dict) and agent.get('ip_addr') == ip:
                    return agent.get('name', agent.get('id'))
        except:
            pass

        # Fallback: parse shadow config
        shadow_config = self._load_shadow_config()
        if shadow_config:
            hosts = shadow_config.get('hosts', {})
            for host_name, host_data in hosts.items():
                if host_data.get('ip_addr') == ip:
                    return host_name

        # If not found, create a synthetic node name
        synthetic_name = f"node_{ip.replace('.', '_').replace(':', '_')}"
        if synthetic_name not in self.node_info:
            self.node_info[synthetic_name] = {
                'ip': ip,
                'type': 'unknown_node',
                'name': synthetic_name
            }
        return synthetic_name

    def _load_shadow_config(self) -> dict:
        """Load the Shadow configuration file."""
        shadow_config_path = find_latest_shadow_config()
        try:
            import yaml
            with open(shadow_config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            log_warning("NetworkConnectivityAnalyzer", f"Could not load shadow config {shadow_config_path}: {e}")
            return {}

    def _build_node_info(self) -> None:
        """Build node information mapping - only for Monero daemons."""
        # Get Monero daemon nodes from agent registry
        try:
            registry_data = self.agent_discovery.get_agent_registry()
            registry = registry_data.get('agents', []) if isinstance(registry_data, dict) else registry_data

            if isinstance(registry, list):
                for agent in registry:
                    if isinstance(agent, dict) and agent.get('daemon', False):
                        node_name = agent.get('id', 'unknown')
                        ip = agent.get('ip_addr', 'unknown')
                        is_miner = agent.get('attributes', {}).get('is_miner', False)

                        self.node_info[node_name] = {
                            'ip': ip,
                            'type': 'miner' if is_miner else 'user',
                            'name': node_name
                        }

                        if ip and ip != 'unknown':
                            self.ip_to_node[ip] = node_name

            log_info("NetworkConnectivityAnalyzer", f"Found {len(self.node_info)} Monero daemon nodes from registry")

        except Exception as e:
            log_warning("NetworkConnectivityAnalyzer", f"Could not load agent registry: {e}")

        # Verify nodes have corresponding log directories
        hosts_dir = self.logs_dir
        if hosts_dir.exists():
            existing_nodes = set()
            for host_dir in hosts_dir.iterdir():
                if host_dir.is_dir() and host_dir.name in self.node_info:
                    existing_nodes.add(host_dir.name)

            # Remove nodes without log directories
            nodes_to_remove = set(self.node_info.keys()) - existing_nodes
            for node in nodes_to_remove:
                del self.node_info[node]
                if node in self.ip_to_node.values():
                    ips_to_remove = [ip for ip, name in self.ip_to_node.items() if name == node]
                    for ip in ips_to_remove:
                        del self.ip_to_node[ip]

            if nodes_to_remove:
                log_warning("NetworkConnectivityAnalyzer", f"Removed {len(nodes_to_remove)} nodes without log directories: {nodes_to_remove}")

    def analyze_logs(self) -> None:
        """Analyze all log files."""
        log_info("NetworkConnectivityAnalyzer", "Starting log analysis...")

        # Find all log files
        log_files = list(self.logs_dir.glob("*/bash.*.stdout"))

        if not log_files:
            log_warning("NetworkConnectivityAnalyzer", f"No log files found in {self.logs_dir}")
            return

        log_info("NetworkConnectivityAnalyzer", f"Found {len(log_files)} log files to analyze")

        # Build node info first
        self._build_node_info()

        # Parse each log file
        for i, log_file in enumerate(log_files, 1):
            if i % 10 == 0:
                log_info("NetworkConnectivityAnalyzer", f"Processed {i}/{len(log_files)} log files")
            self._parse_log_file(log_file)

        log_info("NetworkConnectivityAnalyzer", "Log analysis complete")

    def build_network_graph(self) -> nx.Graph:
        """Build NetworkX graph from connections."""
        G = nx.Graph()

        # Add nodes
        log_info("NetworkConnectivityAnalyzer", f"Adding {len(self.node_info)} nodes to graph")
        for node, info in self.node_info.items():
            G.add_node(node, **info)

        # Add edges
        edge_count = 0
        for node1, connected_nodes in self.connections.items():
            for node2 in connected_nodes:
                if node1 < node2:  # Avoid duplicate edges
                    G.add_edge(node1, node2)
                    edge_count += 1

        log_info("NetworkConnectivityAnalyzer", f"Added {edge_count} edges to graph")
        return G

    def analyze_topology(self, G: nx.Graph) -> dict:
        """Analyze network topology."""
        analysis = {
            'num_nodes': len(G.nodes()),
            'num_edges': len(G.edges()),
            'connected_components': [],
            'isolated_nodes': [],
            'degree_distribution': dict(Counter(dict(G.degree()).values())),
            'average_degree': sum(dict(G.degree()).values()) / len(G.nodes()) if G.nodes() else 0,
            'clustering_coefficient': nx.average_clustering(G) if G.nodes() else 0,
            'network_density': nx.density(G) if G.nodes() else 0
        }

        # Connected components
        components = list(nx.connected_components(G))
        analysis['connected_components'] = [list(comp) for comp in components]

        # Isolated nodes
        analysis['isolated_nodes'] = [node for node in G.nodes() if G.degree(node) == 0]

        # Compare with intended topology if GML available
        if self.gml_file and self.gml_file.exists():
            intended_G = self._load_gml_graph()
            if intended_G:
                analysis['topology_comparison'] = self._compare_topologies(G, intended_G)
            else:
                log_warning("NetworkConnectivityAnalyzer", f"Could not load GML file {self.gml_file} for topology comparison")

        return analysis

    def _load_gml_graph(self) -> Optional[nx.Graph]:
        """Load GML topology as NetworkX graph with robust parsing."""
        try:
            # First try standard NetworkX loading
            return nx.read_gml(str(self.gml_file))
        except Exception as e:
            log_warning("NetworkConnectivityAnalyzer", f"Standard GML loading failed: {e}")
            # Try to fix common issues and retry
            return self._load_gml_with_fixes()

    def _load_gml_with_fixes(self) -> Optional[nx.Graph]:
        """Load GML with fixes for common issues."""
        try:
            import tempfile

            # Read the file and add missing labels
            with open(self.gml_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Add label attribute to nodes that don't have it
            import re

            def add_label(match):
                node_content = match.group(1)
                # Check if label already exists
                if 'label' in node_content:
                    return match.group(0)

                # Extract id value and ensure it's a string
                id_match = re.search(r'id\s+("?\d+"?)', node_content)
                if id_match:
                    node_id = id_match.group(1).strip('"')
                    # Insert label after id
                    return node_content.replace(f'id {id_match.group(1)}', f'id "{node_id}"\n    label "{node_id}"', 1)
                return match.group(0)

            # Apply the fix for nodes
            fixed_content = re.sub(r'node\s*\[\s*(.*?)\s*\]', add_label, content, flags=re.DOTALL)

            # Also fix edges to use string IDs
            def fix_edge_ids(match):
                edge_content = match.group(1)
                # Replace source and target IDs with quoted versions
                edge_content = re.sub(r'source\s+(\d+)', r'source "\1"', edge_content)
                edge_content = re.sub(r'target\s+(\d+)', r'target "\1"', edge_content)
                return f'edge [\n    {edge_content}\n  ]'

            fixed_content = re.sub(r'edge\s*\[\s*(.*?)\s*\]', fix_edge_ids, fixed_content, flags=re.DOTALL)

            # Write to temporary file and load
            with tempfile.NamedTemporaryFile(mode='w', suffix='.gml', delete=False) as tmp:
                tmp.write(fixed_content)
                tmp_path = tmp.name

            try:
                return nx.read_gml(tmp_path)
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            log_error("NetworkConnectivityAnalyzer", f"GML parsing with fixes failed: {e}")
            return None

    def _compare_topologies(self, actual: nx.Graph, intended: nx.Graph) -> dict:
        """Compare actual vs intended topology."""
        comparison = {
            'intended_nodes': len(intended.nodes()),
            'intended_edges': len(intended.edges()),
            'actual_nodes': len(actual.nodes()),
            'actual_edges': len(actual.edges()),
            'missing_connections': [],
            'extra_connections': []
        }

        # Find missing connections (in intended but not actual)
        intended_edges = set((min(u,v), max(u,v)) for u,v in intended.edges())
        actual_edges = set((min(u,v), max(u,v)) for u,v in actual.edges())

        comparison['missing_connections'] = list(intended_edges - actual_edges)
        comparison['extra_connections'] = list(actual_edges - intended_edges)

        return comparison

    def _get_ip_geolocation(self, ip: str) -> Optional[dict]:
        """Get geolocation data for an IP address."""
        # Skip private IPs
        if ip.startswith(('10.', '192.168.', '172.', '127.', '169.254.')):
            return {'type': 'private', 'note': 'Private IP address - no public geolocation available'}

        try:
            # Use ipapi.co for geolocation
            response = requests.get(f'http://ipapi.co/{ip}/json/', timeout=IPAPI_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('error'):
                    return {'error': data['error']}
                return {
                    'country': data.get('country_name'),
                    'region': data.get('region'),
                    'city': data.get('city'),
                    'org': data.get('org'),
                    'asn': data.get('asn'),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude')
                }
        except Exception as e:
            log_warning("NetworkConnectivityAnalyzer", f"Could not get geolocation for {ip}: {e}")

        return None

    def analyze_ip_usage(self) -> dict:
        """Analyze IP address usage in the simulation."""
        log_info("NetworkConnectivityAnalyzer", "Analyzing IP address usage...")

        ip_analysis_results = {}

        for ip, data in self.ip_analysis.items():
            analysis = {
                'frequency': data['count'],
                'ports': sorted(list(data['ports'])),
                'associated_nodes': []
            }

            # Find nodes associated with this IP
            for node_name, node_data in self.node_info.items():
                if node_data.get('ip') == ip:
                    analysis['associated_nodes'].append({
                        'name': node_name,
                        'type': node_data.get('type')
                    })

            # Get geolocation if not already cached
            if data['geolocation'] is None:
                data['geolocation'] = self._get_ip_geolocation(ip)
            analysis['geolocation'] = data['geolocation']

            ip_analysis_results[ip] = analysis

        # Sort by frequency (most used first)
        sorted_ips = sorted(ip_analysis_results.items(), key=lambda x: x[1]['frequency'], reverse=True)

        return {
            'total_unique_ips': len(ip_analysis_results),
            'total_ip_mentions': sum(data['count'] for data in self.ip_analysis.values()),
            'ip_details': dict(sorted_ips),
            'ip_frequency_distribution': dict(Counter([data['count'] for data in self.ip_analysis.values()]))
        }

    def generate_outputs(self, G: nx.Graph, analysis: dict, ip_analysis: dict) -> None:
        """Generate all output files."""
        log_info("NetworkConnectivityAnalyzer", "Generating output files...")

        # 1. JSON graph data
        graph_data = {
            'nodes': [{'id': node, **info} for node, info in self.node_info.items()],
            'edges': [{'source': u, 'target': v} for u, v in G.edges()],
            'connection_events': self.connection_events
        }

        with open(self.output_dir / 'network_graph.json', 'w') as f:
            json.dump(graph_data, f, indent=2)

        # 2. Text summary
        summary = f"""
Network Connectivity Analysis Summary
====================================

Simulation Configuration:
- Config file: {self.config_file}
- GML topology: {self.gml_file or 'None'}

Network Statistics:
- Total Monero nodes: {analysis['num_nodes']}
- Total successful connections: {analysis['num_edges']}
- Connected components: {len(analysis['connected_components'])}
- Isolated nodes: {len(analysis['isolated_nodes'])}
- Average degree: {analysis['average_degree']:.2f}
- Clustering coefficient: {analysis['clustering_coefficient']:.3f}
- Network density: {analysis['network_density']:.3f}

Connection Events:
- Total successful connections: {len(self.connection_events)}

Isolated Nodes:
{chr(10).join(f"- {node}" for node in analysis['isolated_nodes'])}

Connected Components:
"""

        for i, comp in enumerate(analysis['connected_components'], 1):
            summary += f"\nComponent {i} ({len(comp)} nodes): {', '.join(sorted(comp))}"

        if 'topology_comparison' in analysis:
            comp = analysis['topology_comparison']
            summary += f"""

Topology Comparison (Actual vs Intended):
- Intended: {comp['intended_nodes']} nodes, {comp['intended_edges']} edges
- Actual: {comp['actual_nodes']} nodes, {comp['actual_edges']} edges
- Missing connections: {len(comp['missing_connections'])}
- Extra connections: {len(comp['extra_connections'])}
"""

        with open(self.output_dir / 'network_summary.txt', 'w') as f:
            f.write(summary)

        # 3. GraphML for visualization
        nx.write_graphml(G, self.output_dir / 'network_topology.graphml')

        # 4. Detailed connection log
        with open(self.output_dir / 'connection_details.json', 'w') as f:
            json.dump({
                'connections': {k: list(v) for k, v in self.connections.items()},
                'events': self.connection_events,
                'analysis': analysis
            }, f, indent=2)

        # 5. IP analysis results
        with open(self.output_dir / 'ip_analysis.json', 'w') as f:
            json.dump(ip_analysis, f, indent=2)

        # 6. IP analysis summary text
        ip_summary = f"""
IP Address Analysis Summary
===========================

Total Unique IP Addresses: {ip_analysis['total_unique_ips']}
Total IP Mentions: {ip_analysis['total_ip_mentions']}

IP Frequency Distribution:
{chr(10).join(f"- {count} mentions: {freq} IPs" for count, freq in sorted(ip_analysis['ip_frequency_distribution'].items()))}

Top 10 Most Used IP Addresses:
"""

        for i, (ip, data) in enumerate(list(ip_analysis['ip_details'].items())[:10], 1):
            ip_summary += f"\n{i}. {ip}\n"
            ip_summary += f"   Frequency: {data['frequency']} mentions\n"
            ip_summary += f"   Ports: {', '.join(data['ports'])}\n"
            if data['associated_nodes']:
                node_list = [f"{n['name']} ({n['type']})" for n in data['associated_nodes']]
                ip_summary += f"   Associated Nodes: {', '.join(node_list)}\n"
            if data['geolocation']:
                if 'type' in data['geolocation'] and data['geolocation']['type'] == 'private':
                    ip_summary += f"   Geolocation: {data['geolocation']['note']}\n"
                elif 'country' in data['geolocation']:
                    loc = data['geolocation']
                    ip_summary += f"   Location: {loc.get('city', 'Unknown')}, {loc.get('region', 'Unknown')}, {loc.get('country', 'Unknown')}\n"
                    if loc.get('org'):
                        ip_summary += f"   Organization: {loc['org']}\n"
            ip_summary += "\n"

        with open(self.output_dir / 'ip_analysis_summary.txt', 'w') as f:
            f.write(ip_summary)

        log_info("NetworkConnectivityAnalyzer", f"Output files generated in {self.output_dir}")

    def run_analysis(self) -> None:
        """Run the complete analysis."""
        try:
            log_info("NetworkConnectivityAnalyzer", "Starting network connectivity analysis")

            # Analyze logs
            self.analyze_logs()

            # Build and analyze graph
            G = self.build_network_graph()
            analysis = self.analyze_topology(G)

            # Analyze IP usage
            ip_analysis = self.analyze_ip_usage()

            # Generate outputs
            self.generate_outputs(G, analysis, ip_analysis)

            log_info("NetworkConnectivityAnalyzer", "Analysis complete")

        except Exception as e:
            log_error("NetworkConnectivityAnalyzer", f"Analysis failed: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Analyze Monero P2P network connectivity from Shadow logs")
    parser.add_argument('--config', required=True, help='Path to simulation config file')
    parser.add_argument('--logs', default=DEFAULT_LOGS_DIR, help='Path to shadow.data/hosts directory')
    parser.add_argument('--output', help='Output directory (default: analysis_results subfolder)')

    args = parser.parse_args()

    # Use provided output dir or default to analysis_results
    output_dir = args.output if args.output else 'analysis_results'
    analyzer = NetworkConnectivityAnalyzer(args.config, args.logs, output_dir)
    analyzer.run_analysis()


if __name__ == '__main__':
    main()