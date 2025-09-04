#!/usr/bin/env python3
"""
Comprehensive Internet Topology End-to-End Test

This test validates the complete realistic internet topology simulation system including:
1. GML parsing functionality
2. Hierarchical IP assignment across Autonomous Systems
3. Multi-layered network structure validation
4. Agent distribution across network nodes
5. Shadow configuration generation
6. Inter-network communication validation

Usage:
    python3 scripts/comprehensive_internet_topology_test.py

Requirements:
    - Python 3.6+
    - Access to monerosim binary
    - GML topology file: comprehensive_internet_topology_test.gml
    - Configuration file: config_comprehensive_internet_test.yaml
"""

import os
import sys
import json
import time
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('comprehensive_internet_topology_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Represents the result of a test case"""
    name: str
    passed: bool
    message: str
    details: Optional[Dict] = None

@dataclass
class NetworkTopology:
    """Represents the parsed network topology"""
    nodes: Dict[int, Dict]
    edges: List[Tuple[int, int, Dict]]
    autonomous_systems: Dict[str, List[int]]
    node_ips: Dict[int, str]

class ComprehensiveInternetTopologyTest:
    """Main test class for comprehensive internet topology validation"""

    def __init__(self):
        self.test_results: List[TestResult] = []
        self.gml_file = "comprehensive_internet_topology_test.gml"
        self.config_file = "config_comprehensive_internet_test.yaml"
        self.shadow_output_dir = "comprehensive_internet_test_output"
        self.shared_dir = "/tmp/monerosim_shared"

        # Expected AS configurations
        self.expected_ases = {
            "65001": {"subnet": "10.0.0", "nodes": [0, 1, 2, 3], "description": "Large ISP Network"},
            "65002": {"subnet": "192.168.0", "nodes": [4, 5, 6, 7], "description": "Regional ISP Network"},
            "65003": {"subnet": "172.16.0", "nodes": [8, 9, 10], "description": "Data Center Network"},
            "65004": {"subnet": "203.0.113", "nodes": [11, 12], "description": "International Network"},
            "65005": {"subnet": "198.51.100", "nodes": [13, 14], "description": "University Network"}
        }

    def run_all_tests(self) -> bool:
        """Run all test cases and return overall success"""
        logger.info("Starting Comprehensive Internet Topology End-to-End Test")

        test_methods = [
            self.test_gml_parsing,
            self.test_network_topology_validation,
            self.test_autonomous_system_grouping,
            self.test_hierarchical_ip_assignment,
            self.test_agent_distribution,
            self.test_shadow_configuration_generation,
            self.test_agent_registry_creation,
            self.test_miner_registry_creation,
            self.test_inter_network_communication_paths
        ]

        for test_method in test_methods:
            try:
                logger.info(f"Running test: {test_method.__name__}")
                result = test_method()
                self.test_results.append(result)
                logger.info(f"Test {test_method.__name__}: {'PASSED' if result.passed else 'FAILED'}")
                if not result.passed:
                    logger.error(f"Test failed: {result.message}")
            except Exception as e:
                error_result = TestResult(
                    name=test_method.__name__,
                    passed=False,
                    message=f"Test execution failed: {str(e)}"
                )
                self.test_results.append(error_result)
                logger.error(f"Test {test_method.__name__} execution failed: {str(e)}")

        return self.generate_test_report()

    def test_gml_parsing(self) -> TestResult:
        """Test GML file parsing functionality"""
        try:
            # Import the GML parser (this would need to be accessible from Python)
            # For now, we'll test file existence and basic structure
            if not os.path.exists(self.gml_file):
                return TestResult(
                    name="test_gml_parsing",
                    passed=False,
                    message=f"GML file not found: {self.gml_file}"
                )

            with open(self.gml_file, 'r') as f:
                content = f.read()

            # Basic validation
            if 'graph [' not in content:
                return TestResult(
                    name="test_gml_parsing",
                    passed=False,
                    message="Invalid GML format: missing 'graph [' declaration"
                )

            # Count nodes and edges
            node_count = content.count('node [')
            edge_count = content.count('edge [')

            if node_count < 10:
                return TestResult(
                    name="test_gml_parsing",
                    passed=False,
                    message=f"Insufficient nodes in GML: found {node_count}, expected at least 10"
                )

            if edge_count < 15:
                return TestResult(
                    name="test_gml_parsing",
                    passed=False,
                    message=f"Insufficient edges in GML: found {edge_count}, expected at least 15"
                )

            return TestResult(
                name="test_gml_parsing",
                passed=True,
                message="GML parsing validation passed",
                details={"nodes": node_count, "edges": edge_count}
            )

        except Exception as e:
            return TestResult(
                name="test_gml_parsing",
                passed=False,
                message=f"GML parsing test failed: {str(e)}"
            )

    def test_network_topology_validation(self) -> TestResult:
        """Test network topology connectivity and structure"""
        try:
            # Read and parse GML content to extract topology
            topology = self._parse_gml_topology()

            # Validate connectivity
            if not self._is_topology_connected(topology):
                return TestResult(
                    name="test_network_topology_validation",
                    passed=False,
                    message="Network topology is not fully connected"
                )

            # Validate AS distribution
            as_node_counts = {}
            for node_id, node_data in topology.nodes.items():
                as_num = node_data.get('AS')
                if as_num:
                    as_node_counts[as_num] = as_node_counts.get(as_num, 0) + 1

            # Check minimum nodes per AS
            min_nodes_per_as = 2
            small_ases = [as_num for as_num, count in as_node_counts.items() if count < min_nodes_per_as]

            if small_ases:
                return TestResult(
                    name="test_network_topology_validation",
                    passed=False,
                    message=f"ASes with insufficient nodes: {small_ases}"
                )

            return TestResult(
                name="test_network_topology_validation",
                passed=True,
                message="Network topology validation passed",
                details={"as_distribution": as_node_counts}
            )

        except Exception as e:
            return TestResult(
                name="test_network_topology_validation",
                passed=False,
                message=f"Network topology validation failed: {str(e)}"
            )

    def test_autonomous_system_grouping(self) -> TestResult:
        """Test AS-aware node grouping"""
        try:
            topology = self._parse_gml_topology()

            # Validate expected ASes exist
            found_ases = set()
            for node_data in topology.nodes.values():
                if 'AS' in node_data:
                    found_ases.add(node_data['AS'])

            missing_ases = set(self.expected_ases.keys()) - found_ases
            if missing_ases:
                return TestResult(
                    name="test_autonomous_system_grouping",
                    passed=False,
                    message=f"Missing expected ASes: {missing_ases}"
                )

            # Validate AS node assignments
            for as_num, expected_data in self.expected_ases.items():
                as_nodes = [node_id for node_id, node_data in topology.nodes.items()
                           if node_data.get('AS') == as_num]

                if len(as_nodes) != len(expected_data['nodes']):
                    return TestResult(
                        name="test_autonomous_system_grouping",
                        passed=False,
                        message=f"AS {as_num}: expected {len(expected_data['nodes'])} nodes, found {len(as_nodes)}"
                    )

            return TestResult(
                name="test_autonomous_system_grouping",
                passed=True,
                message="Autonomous system grouping validation passed",
                details={"found_ases": list(found_ases)}
            )

        except Exception as e:
            return TestResult(
                name="test_autonomous_system_grouping",
                passed=False,
                message=f"AS grouping test failed: {str(e)}"
            )

    def test_hierarchical_ip_assignment(self) -> TestResult:
        """Test hierarchical IP assignment across ASes"""
        try:
            topology = self._parse_gml_topology()

            # Validate IP assignments follow AS subnet patterns
            ip_assignments = {}
            for node_id, node_data in topology.nodes.items():
                if 'ip' in node_data:
                    ip = node_data['ip']
                    as_num = node_data.get('AS')
                    if as_num and as_num in self.expected_ases:
                        expected_subnet = self.expected_ases[as_num]['subnet']
                        if not ip.startswith(expected_subnet + '.'):
                            return TestResult(
                                name="test_hierarchical_ip_assignment",
                                passed=False,
                                message=f"Node {node_id} IP {ip} doesn't match AS {as_num} subnet {expected_subnet}"
                            )
                        ip_assignments[as_num] = ip_assignments.get(as_num, []) + [ip]

            # Validate IP uniqueness within each AS
            for as_num, ips in ip_assignments.items():
                if len(ips) != len(set(ips)):
                    return TestResult(
                        name="test_hierarchical_ip_assignment",
                        passed=False,
                        message=f"Duplicate IPs found in AS {as_num}: {ips}"
                    )

            return TestResult(
                name="test_hierarchical_ip_assignment",
                passed=True,
                message="Hierarchical IP assignment validation passed",
                details={"ip_assignments": ip_assignments}
            )

        except Exception as e:
            return TestResult(
                name="test_hierarchical_ip_assignment",
                passed=False,
                message=f"Hierarchical IP assignment test failed: {str(e)}"
            )

    def test_agent_distribution(self) -> TestResult:
        """Test agent distribution across network nodes"""
        try:
            # This would require running the monerosim binary to generate configuration
            # For now, we'll validate the configuration file structure
            if not os.path.exists(self.config_file):
                return TestResult(
                    name="test_agent_distribution",
                    passed=False,
                    message=f"Configuration file not found: {self.config_file}"
                )

            # Parse configuration to validate agent definitions
            agent_count = self._count_agents_in_config()

            if agent_count < 10:
                return TestResult(
                    name="test_agent_distribution",
                    passed=False,
                    message=f"Insufficient agents defined: {agent_count}, expected at least 10"
                )

            # Validate miner distribution
            miner_count = self._count_miners_in_config()
            if miner_count < 3:
                return TestResult(
                    name="test_agent_distribution",
                    passed=False,
                    message=f"Insufficient miners defined: {miner_count}, expected at least 3"
                )

            return TestResult(
                name="test_agent_distribution",
                passed=True,
                message="Agent distribution validation passed",
                details={"total_agents": agent_count, "miners": miner_count}
            )

        except Exception as e:
            return TestResult(
                name="test_agent_distribution",
                passed=False,
                message=f"Agent distribution test failed: {str(e)}"
            )

    def test_shadow_configuration_generation(self) -> TestResult:
        """Test Shadow configuration generation from GML topology"""
        try:
            # Create output directory
            os.makedirs(self.shadow_output_dir, exist_ok=True)

            # Run monerosim to generate Shadow configuration
            cmd = [
                "./target/release/monerosim",
                "--config", self.config_file,
                "--output", f"{self.shadow_output_dir}/shadow_agents.yaml"
            ]

            logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                return TestResult(
                    name="test_shadow_configuration_generation",
                    passed=False,
                    message=f"Shadow configuration generation failed: {result.stderr}"
                )

            # Validate generated configuration
            shadow_config_path = f"{self.shadow_output_dir}/shadow_agents.yaml"
            if not os.path.exists(shadow_config_path):
                return TestResult(
                    name="test_shadow_configuration_generation",
                    passed=False,
                    message="Shadow configuration file not generated"
                )

            # Parse and validate Shadow configuration
            validation_result = self._validate_shadow_config(shadow_config_path)
            if not validation_result['valid']:
                return TestResult(
                    name="test_shadow_configuration_generation",
                    passed=False,
                    message=f"Shadow configuration validation failed: {validation_result['error']}"
                )

            return TestResult(
                name="test_shadow_configuration_generation",
                passed=True,
                message="Shadow configuration generation passed",
                details=validation_result
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                name="test_shadow_configuration_generation",
                passed=False,
                message="Shadow configuration generation timed out"
            )
        except Exception as e:
            return TestResult(
                name="test_shadow_configuration_generation",
                passed=False,
                message=f"Shadow configuration generation test failed: {str(e)}"
            )

    def test_agent_registry_creation(self) -> TestResult:
        """Test agent registry creation and validation"""
        try:
            registry_path = f"{self.shadow_output_dir}/../{self.shared_dir}/agent_registry.json"
            if not os.path.exists(registry_path):
                return TestResult(
                    name="test_agent_registry_creation",
                    passed=False,
                    message="Agent registry file not found"
                )

            with open(registry_path, 'r') as f:
                registry = json.load(f)

            if 'agents' not in registry:
                return TestResult(
                    name="test_agent_registry_creation",
                    passed=False,
                    message="Agent registry missing 'agents' field"
                )

            agents = registry['agents']
            if len(agents) < 10:
                return TestResult(
                    name="test_agent_registry_creation",
                    passed=False,
                    message=f"Insufficient agents in registry: {len(agents)}"
                )

            # Validate agent data structure
            required_fields = ['id', 'ip_addr', 'daemon', 'wallet']
            for agent in agents:
                missing_fields = [field for field in required_fields if field not in agent]
                if missing_fields:
                    return TestResult(
                        name="test_agent_registry_creation",
                        passed=False,
                        message=f"Agent {agent.get('id', 'unknown')} missing fields: {missing_fields}"
                    )

            return TestResult(
                name="test_agent_registry_creation",
                passed=True,
                message="Agent registry validation passed",
                details={"agent_count": len(agents)}
            )

        except Exception as e:
            return TestResult(
                name="test_agent_registry_creation",
                passed=False,
                message=f"Agent registry test failed: {str(e)}"
            )

    def test_miner_registry_creation(self) -> TestResult:
        """Test miner registry creation and hashrate distribution"""
        try:
            registry_path = f"{self.shadow_output_dir}/../{self.shared_dir}/miners.json"
            if not os.path.exists(registry_path):
                return TestResult(
                    name="test_miner_registry_creation",
                    passed=False,
                    message="Miner registry file not found"
                )

            with open(registry_path, 'r') as f:
                registry = json.load(f)

            if 'miners' not in registry:
                return TestResult(
                    name="test_miner_registry_creation",
                    passed=False,
                    message="Miner registry missing 'miners' field"
                )

            miners = registry['miners']
            if len(miners) < 3:
                return TestResult(
                    name="test_miner_registry_creation",
                    passed=False,
                    message=f"Insufficient miners in registry: {len(miners)}"
                )

            # Validate hashrate distribution
            total_hashrate = sum(miner.get('weight', 0) for miner in miners)
            if total_hashrate == 0:
                return TestResult(
                    name="test_miner_registry_creation",
                    passed=False,
                    message="Total hashrate is zero"
                )

            # Check for unique IP addresses
            ips = [miner.get('ip_addr') for miner in miners]
            if len(ips) != len(set(ips)):
                return TestResult(
                    name="test_miner_registry_creation",
                    passed=False,
                    message="Duplicate IP addresses in miner registry"
                )

            return TestResult(
                name="test_miner_registry_creation",
                passed=True,
                message="Miner registry validation passed",
                details={"miner_count": len(miners), "total_hashrate": total_hashrate}
            )

        except Exception as e:
            return TestResult(
                name="test_miner_registry_creation",
                passed=False,
                message=f"Miner registry test failed: {str(e)}"
            )

    def test_inter_network_communication_paths(self) -> TestResult:
        """Test inter-network communication path validation"""
        try:
            topology = self._parse_gml_topology()

            # Validate that all ASes are interconnected
            connected_components = self._find_connected_components(topology)

            if len(connected_components) > 1:
                return TestResult(
                    name="test_inter_network_communication_paths",
                    passed=False,
                    message=f"Network has {len(connected_components)} disconnected components"
                )

            # Validate minimum connectivity requirements
            min_connections_per_as = 2
            as_connections = self._count_as_connections(topology)

            poorly_connected = [as_num for as_num, count in as_connections.items()
                              if count < min_connections_per_as]

            if poorly_connected:
                return TestResult(
                    name="test_inter_network_communication_paths",
                    passed=False,
                    message=f"ASes with insufficient connections: {poorly_connected}"
                )

            return TestResult(
                name="test_inter_network_communication_paths",
                passed=True,
                message="Inter-network communication validation passed",
                details={"as_connections": as_connections}
            )

        except Exception as e:
            return TestResult(
                name="test_inter_network_communication_paths",
                passed=False,
                message=f"Inter-network communication test failed: {str(e)}"
            )

    def _parse_gml_topology(self) -> NetworkTopology:
        """Parse GML file to extract network topology"""
        nodes = {}
        edges = []
        autonomous_systems = {}

        with open(self.gml_file, 'r') as f:
            content = f.read()

        # Simple parsing - extract node and edge information
        lines = content.split('\n')
        current_section = None
        current_data = {}

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line == 'node [':
                current_section = 'node'
                current_data = {}
            elif line == 'edge [':
                current_section = 'edge'
                current_data = {}
            elif line == ']' and current_section:
                if current_section == 'node' and 'id' in current_data:
                    node_id = int(current_data['id'])
                    nodes[node_id] = current_data.copy()
                    # Add to AS grouping
                    if 'AS' in current_data:
                        as_num = current_data['AS']
                        if as_num not in autonomous_systems:
                            autonomous_systems[as_num] = []
                        autonomous_systems[as_num].append(node_id)
                elif current_section == 'edge' and 'source' in current_data and 'target' in current_data:
                    edges.append((
                        int(current_data['source']),
                        int(current_data['target']),
                        current_data.copy()
                    ))
                current_section = None
            elif current_section:
                # Parse key-value pairs (GML format: key "value" or key value)
                parts = line.split(None, 1)  # Split on whitespace
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().strip('"')  # Remove quotes if present
                    current_data[key] = value

        return NetworkTopology(
            nodes=nodes,
            edges=edges,
            autonomous_systems=autonomous_systems,
            node_ips={node_id: data.get('ip', '') for node_id, data in nodes.items()}
        )

    def _is_topology_connected(self, topology: NetworkTopology) -> bool:
        """Check if the network topology is fully connected"""
        if not topology.nodes:
            return True

        # Simple connectivity check using DFS
        visited = set()
        stack = [next(iter(topology.nodes.keys()))]

        while stack:
            node = stack.pop()
            if node not in visited:
                visited.add(node)
                # Add neighbors
                for source, target, _ in topology.edges:
                    if source == node and target not in visited:
                        stack.append(target)
                    elif target == node and source not in visited:
                        stack.append(source)

        return len(visited) == len(topology.nodes)

    def _find_connected_components(self, topology: NetworkTopology) -> List[Set[int]]:
        """Find connected components in the network"""
        components = []
        visited = set()

        for node in topology.nodes.keys():
            if node not in visited:
                component = set()
                stack = [node]

                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)

                        # Add neighbors
                        for source, target, _ in topology.edges:
                            if source == current and target not in visited:
                                stack.append(target)
                            elif target == current and source not in visited:
                                stack.append(source)

                components.append(component)

        return components

    def _count_as_connections(self, topology: NetworkTopology) -> Dict[str, int]:
        """Count inter-AS connections for each AS"""
        as_connections = {}

        for source, target, _ in topology.edges:
            source_as = topology.nodes.get(source, {}).get('AS')
            target_as = topology.nodes.get(target, {}).get('AS')

            if source_as and target_as and source_as != target_as:
                # Inter-AS connection
                as_connections[source_as] = as_connections.get(source_as, 0) + 1
                as_connections[target_as] = as_connections.get(target_as, 0) + 1

        return as_connections

    def _count_agents_in_config(self) -> int:
        """Count total agents in configuration file"""
        try:
            import yaml
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)

            agents = config.get('agents', {})
            user_agents = agents.get('user_agents', [])
            return len(user_agents)
        except:
            return 0

    def _count_miners_in_config(self) -> int:
        """Count miners in configuration file"""
        try:
            import yaml
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)

            agents = config.get('agents', {})
            user_agents = agents.get('user_agents', [])
            return sum(1 for agent in user_agents if agent.get('is_miner'))
        except:
            return 0

    def _validate_shadow_config(self, config_path: str) -> Dict:
        """Validate generated Shadow configuration"""
        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Basic validation
            if 'general' not in config:
                return {'valid': False, 'error': 'Missing general section'}

            if 'hosts' not in config:
                return {'valid': False, 'error': 'Missing hosts section'}

            hosts = config['hosts']
            if len(hosts) < 10:
                return {'valid': False, 'error': f'Insufficient hosts: {len(hosts)}'}

            # Validate host structure
            for host_name, host_data in hosts.items():
                if 'network_node_id' not in host_data:
                    return {'valid': False, 'error': f'Host {host_name} missing network_node_id'}

                if 'processes' not in host_data:
                    return {'valid': False, 'error': f'Host {host_name} missing processes'}

            return {
                'valid': True,
                'host_count': len(hosts),
                'network_type': config.get('network', {}).get('graph', {}).get('type', 'unknown')
            }

        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def generate_test_report(self) -> bool:
        """Generate comprehensive test report and return overall success"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.passed)
        failed_tests = total_tests - passed_tests

        # Generate report
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            'results': [
                {
                    'test': result.name,
                    'passed': result.passed,
                    'message': result.message,
                    'details': result.details
                }
                for result in self.test_results
            ]
        }

        # Save report to file
        with open('comprehensive_internet_topology_test_report.json', 'w') as f:
            json.dump(report, f, indent=2)

        # Print summary
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE INTERNET TOPOLOGY TEST REPORT")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(".1f")
        logger.info("")

        if failed_tests > 0:
            logger.info("FAILED TESTS:")
            for result in self.test_results:
                if not result.passed:
                    logger.info(f"  - {result.name}: {result.message}")
        else:
            logger.info("ALL TESTS PASSED! 🎉")

        logger.info("=" * 80)

        return failed_tests == 0


def main():
    """Main entry point"""
    test = ComprehensiveInternetTopologyTest()
    success = test.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()