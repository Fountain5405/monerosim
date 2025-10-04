#!/usr/bin/env python3
"""
enhanced_monitor.py - Enhanced Monitoring Script for MoneroSim

This script provides advanced monitoring capabilities for the Monero simulation,
building upon the original monitor.py with additional features:
- Real-time blockchain visualization
- Transaction flow tracking
- Network topology visualization
- Performance metrics tracking
- Alerting system for anomalies
- Historical data collection
- Export capabilities for analysis

This enhanced version uses dynamic agent discovery to automatically find and 
monitor all agents in the simulation without requiring hardcoded configurations.
"""

import sys
import time
import argparse
import json
import csv
import os
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics
import math

# Handle imports for both direct execution and module import
try:
    from .error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_daemon_ready, handle_exit
    )
    from agents.agent_discovery import AgentDiscovery
except ImportError:
    # Fallback for when running as a script directly
    from error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_daemon_ready, handle_exit
    )
    from agents.agent_discovery import AgentDiscovery

# Component name for logging
COMPONENT = "ENHANCED_MONITOR"

# Default configuration
DEFAULT_REFRESH_INTERVAL = 10  # seconds
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 2
DEFAULT_HISTORY_SIZE = 100  # Number of data points to keep
DEFAULT_ALERT_THRESHOLD = 2.0  # Standard deviations for anomaly detection


class AgentStatus:
    """Enhanced container for agent status information with historical tracking."""
    
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.height: int = 0
        self.target_height: int = 0
        self.difficulty: int = 0
        self.tx_count: int = 0
        self.tx_pool_size: int = 0
        self.incoming_connections: int = 0
        self.outgoing_connections: int = 0
        self.white_peerlist_size: int = 0
        self.grey_peerlist_size: int = 0
        self.status: str = "unknown"
        self.synchronized: bool = False
        self.mining_active: bool = False
        self.hashrate: int = 0
        self.block_reward: int = 0
        self.cumulative_difficulty: int = 0
        self.top_block_hash: str = ""
        self.last_update: Optional[datetime] = None
        self.error: Optional[str] = None
        
        # Historical data tracking
        self.height_history: deque = deque(maxlen=DEFAULT_HISTORY_SIZE)
        self.hashrate_history: deque = deque(maxlen=DEFAULT_HISTORY_SIZE)
        self.tx_count_history: deque = deque(maxlen=DEFAULT_HISTORY_SIZE)
        self.connection_history: deque = deque(maxlen=DEFAULT_HISTORY_SIZE)
        self.timestamp_history: deque = deque(maxlen=DEFAULT_HISTORY_SIZE)
        
        # Performance metrics
        self.avg_height_rate: float = 0.0
        self.avg_hashrate: float = 0.0
        self.avg_tx_rate: float = 0.0
        self.connection_stability: float = 0.0
        
        # Alert tracking
        self.alerts: List[Dict[str, Any]] = []


class TransactionTracker:
    """Track transactions across the network."""
    
    def __init__(self):
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.tx_flow: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        self.total_tx_count: int = 0
        self.total_volume: float = 0.0
        
    def add_transaction(self, tx_hash: str, sender: str, recipient: str, 
                       amount: float, timestamp: float):
        """Add a transaction to the tracker."""
        self.transactions[tx_hash] = {
            "sender": sender,
            "recipient": recipient,
            "amount": amount,
            "timestamp": timestamp,
            "confirmed": False
        }
        
        # Track flow
        self.tx_flow[sender].append((recipient, timestamp))
        self.total_tx_count += 1
        self.total_volume += amount
        
    def confirm_transaction(self, tx_hash: str):
        """Mark a transaction as confirmed."""
        if tx_hash in self.transactions:
            self.transactions[tx_hash]["confirmed"] = True


class NetworkTopology:
    """Track and visualize network topology."""
    
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.connections: Set[Tuple[str, str]] = set()
        self.as_mapping: Dict[str, str] = {}
        
    def add_node(self, node_id: str, ip_addr: str, as_num: Optional[str] = None):
        """Add a node to the topology."""
        self.nodes[node_id] = {
            "ip_addr": ip_addr,
            "as_num": as_num,
            "connections": set()
        }
        if as_num:
            self.as_mapping[node_id] = as_num
            
    def add_connection(self, node1: str, node2: str):
        """Add a connection between two nodes."""
        self.connections.add((node1, node2))
        self.connections.add((node2, node1))
        self.nodes[node1]["connections"].add(node2)
        self.nodes[node2]["connections"].add(node1)


class AlertManager:
    """Manage alerts for anomalies."""
    
    def __init__(self, threshold: float = DEFAULT_ALERT_THRESHOLD):
        self.threshold = threshold
        self.alerts: List[Dict[str, Any]] = []
        
    def check_anomaly(self, metric_name: str, current_value: float, 
                     history: deque, agent_name: str) -> Optional[Dict[str, Any]]:
        """Check if a metric value is anomalous based on historical data."""
        if len(history) < 10:  # Need sufficient history
            return None
            
        try:
            mean = statistics.mean(history)
            stdev = statistics.stdev(history)
            
            if stdev == 0:  # No variation
                return None
                
            z_score = abs((current_value - mean) / stdev)
            
            if z_score > self.threshold:
                return {
                    "type": "anomaly",
                    "metric": metric_name,
                    "agent": agent_name,
                    "current_value": current_value,
                    "mean": mean,
                    "z_score": z_score,
                    "timestamp": datetime.now().isoformat(),
                    "severity": "high" if z_score > self.threshold * 2 else "medium"
                }
        except (statistics.StatisticsError, ZeroDivisionError):
            pass
            
        return None
        
    def add_alert(self, alert: Dict[str, Any]):
        """Add an alert."""
        self.alerts.append(alert)
        
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get alerts that are still active (within last hour)."""
        cutoff_time = datetime.now() - timedelta(hours=1)
        return [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert["timestamp"]) > cutoff_time
        ]


class EnhancedMonitor:
    """Enhanced monitor with advanced monitoring capabilities."""
    
    def __init__(self, refresh_interval: int = DEFAULT_REFRESH_INTERVAL,
                 max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                 retry_delay: float = DEFAULT_RETRY_DELAY):
        self.refresh_interval = refresh_interval
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        
        # Initialize components
        self.agents: List[AgentStatus] = []
        self.tx_tracker = TransactionTracker()
        self.network_topology = NetworkTopology()
        self.alert_manager = AlertManager()
        self.discovery = AgentDiscovery()
        
        # Export settings
        self.export_enabled = False
        self.export_format = "json"  # json, csv
        self.export_file = None
        
    def discover_agents(self) -> List[AgentStatus]:
        """Discover agents using the agent discovery system."""
        agents = []
        
        try:
            registry = self.discovery.get_agent_registry()
            agents_data = registry.get("agents", [])
            
            # Handle both list and dictionary formats
            if isinstance(agents_data, list):
                for agent_data in agents_data:
                    agent_id = agent_data.get("agent_id") or agent_data.get("id")
                    ip_addr = agent_data.get("ip_addr")
                    rpc_port = agent_data.get("agent_rpc_port") or agent_data.get("node_rpc_port")
                    
                    if agent_id and ip_addr and rpc_port:
                        agents.append(AgentStatus(agent_id, f"http://{ip_addr}:{rpc_port}/json_rpc"))
                        
                        # Add to network topology
                        as_num = agent_data.get("as_num")
                        self.network_topology.add_node(agent_id, ip_addr, as_num)
            elif isinstance(agents_data, dict):
                for agent_id, agent_data in agents_data.items():
                    ip_addr = agent_data.get("ip_addr")
                    rpc_port = agent_data.get("agent_rpc_port") or agent_data.get("node_rpc_port")
                    
                    if ip_addr and rpc_port:
                        agents.append(AgentStatus(agent_id, f"http://{ip_addr}:{rpc_port}/json_rpc"))
                        
                        # Add to network topology
                        as_num = agent_data.get("as_num")
                        self.network_topology.add_node(agent_id, ip_addr, as_num)
            
        except Exception as e:
            log_error(COMPONENT, f"Failed to discover agents: {e}")
            
        return agents
        
    def update_agent_status(self, agent: AgentStatus) -> None:
        """Update agent status with latest information."""
        # Get basic agent info
        info = self.get_agent_info(agent.url)
        if info:
            agent.height = info.get("height", 0)
            agent.target_height = info.get("target_height", 0)
            agent.difficulty = info.get("difficulty", 0)
            agent.tx_count = info.get("tx_count", 0)
            agent.tx_pool_size = info.get("tx_pool_size", 0)
            agent.incoming_connections = info.get("incoming_connections_count", 0)
            agent.outgoing_connections = info.get("outgoing_connections_count", 0)
            agent.white_peerlist_size = info.get("white_peerlist_size", 0)
            agent.grey_peerlist_size = info.get("grey_peerlist_size", 0)
            agent.status = info.get("status", "unknown")
            agent.synchronized = info.get("synchronized", False)
            agent.cumulative_difficulty = info.get("cumulative_difficulty", 0)
            agent.top_block_hash = info.get("top_block_hash", "")
            agent.block_reward = info.get("block_reward", 0)
            agent.error = None
        else:
            agent.error = "Failed to get agent info"
        
        # Get mining status
        mining_status = self.get_mining_status(agent.url)
        if mining_status:
            agent.mining_active = mining_status.get("active", False)
            agent.hashrate = mining_status.get("speed", 0)
        
        # Update historical data
        timestamp = time.time()
        agent.height_history.append(agent.height)
        agent.hashrate_history.append(agent.hashrate)
        agent.tx_count_history.append(agent.tx_count)
        agent.connection_history.append(agent.incoming_connections + agent.outgoing_connections)
        agent.timestamp_history.append(timestamp)
        
        # Calculate performance metrics
        self._calculate_performance_metrics(agent)
        
        # Check for anomalies
        self._check_anomalies(agent)
        
        agent.last_update = datetime.now()
        
    def _calculate_performance_metrics(self, agent: AgentStatus):
        """Calculate performance metrics for an agent."""
        if len(agent.height_history) >= 2:
            # Calculate height rate (blocks per second)
            time_diff = agent.timestamp_history[-1] - agent.timestamp_history[-2]
            if time_diff > 0:
                height_rate = (agent.height_history[-1] - agent.height_history[-2]) / time_diff
                agent.avg_height_rate = height_rate
                
        # Calculate averages
        if agent.hashrate_history:
            agent.avg_hashrate = statistics.mean(agent.hashrate_history)
            
        if len(agent.tx_count_history) >= 2:
            time_diff = agent.timestamp_history[-1] - agent.timestamp_history[-2]
            if time_diff > 0:
                tx_rate = (agent.tx_count_history[-1] - agent.tx_count_history[-2]) / time_diff
                agent.avg_tx_rate = tx_rate
                
        # Calculate connection stability
        if agent.connection_history:
            connections = list(agent.connection_history)
            if len(connections) >= 2:
                # Calculate coefficient of variation
                mean_conn = statistics.mean(connections)
                stdev_conn = statistics.stdev(connections) if len(connections) > 1 else 0
                if mean_conn > 0:
                    agent.connection_stability = 1 - (stdev_conn / mean_conn)
                    
    def _check_anomalies(self, agent: AgentStatus):
        """Check for anomalies in agent metrics."""
        # Check height anomaly
        alert = self.alert_manager.check_anomaly(
            "height", agent.height, agent.height_history, agent.name
        )
        if alert:
            self.alert_manager.add_alert(alert)
            agent.alerts.append(alert)
            
        # Check hashrate anomaly
        alert = self.alert_manager.check_anomaly(
            "hashrate", agent.hashrate, agent.hashrate_history, agent.name
        )
        if alert:
            self.alert_manager.add_alert(alert)
            agent.alerts.append(alert)
            
        # Check connection anomaly
        total_connections = agent.incoming_connections + agent.outgoing_connections
        alert = self.alert_manager.check_anomaly(
            "connections", total_connections, agent.connection_history, agent.name
        )
        if alert:
            self.alert_manager.add_alert(alert)
            agent.alerts.append(alert)
            
    def get_agent_info(self, agent_url: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive agent information."""
        success, response = call_daemon_with_retry(
            agent_url, "get_info", {}, self.max_attempts, self.retry_delay, COMPONENT
        )
        
        if success:
            return response.get("result", {})
        return None
        
    def get_mining_status(self, agent_url: str) -> Optional[Dict[str, Any]]:
        """Get mining status from agent."""
        success, response = call_daemon_with_retry(
            agent_url, "mining_status", {}, self.max_attempts, self.retry_delay, COMPONENT
        )
        
        if success:
            return response.get("result", {})
        return None
        
    def get_connections(self, agent_url: str) -> Optional[List[Dict[str, Any]]]:
        """Get peer connections from agent."""
        success, response = call_daemon_with_retry(
            agent_url, "get_connections", {}, self.max_attempts, self.retry_delay, COMPONENT
        )
        
        if success:
            return response.get("result", {}).get("connections", [])
        return None
        
    def print_enhanced_status(self, agent: AgentStatus, verbose: bool = False):
        """Print enhanced agent status with additional metrics."""
        print(f"\n{'='*60}")
        print(f"Agent: {agent.name}")
        print(f"{'='*60}")
        
        if agent.error:
            print(f"ERROR: {agent.error}")
            return
            
        # Basic info
        print(f"Status: {agent.status}")
        print(f"Synchronized: {'Yes' if agent.synchronized else 'No'}")
        print(f"Height: {agent.height:,} / {agent.target_height:,}")
        if agent.target_height > 0:
            sync_percent = (agent.height / agent.target_height) * 100
            print(f"Sync Progress: {sync_percent:.1f}%")
            
        # Performance metrics
        print(f"\nPerformance Metrics:")
        print(f"  Height Rate: {agent.avg_height_rate:.4f} blocks/sec")
        print(f"  Avg Hashrate: {self._format_hashrate(agent.avg_hashrate)}")
        print(f"  TX Rate: {agent.avg_tx_rate:.4f} tx/sec")
        print(f"  Connection Stability: {agent.connection_stability:.2%}")
        
        # Mining info
        if agent.mining_active:
            print(f"\nMining: Active ({self._format_hashrate(agent.hashrate)})")
        else:
            print(f"\nMining: Inactive")
            
        # Network info
        print(f"\nNetwork:")
        print(f"  Connections: {agent.incoming_connections} in / {agent.outgoing_connections} out")
        print(f"  Peer Lists: {agent.white_peerlist_size} white / {agent.grey_peerlist_size} grey")
        
        # Transaction pool
        print(f"\nTransactions:")
        print(f"  TX Pool: {agent.tx_pool_size} transactions")
        print(f"  Total TXs: {agent.tx_count:,}")
        
        # Blockchain info
        print(f"\nBlockchain:")
        print(f"  Difficulty: {agent.difficulty:,}")
        if agent.block_reward > 0:
            reward_xmr = agent.block_reward / 1e12
            print(f"  Block Reward: {reward_xmr:.12f} XMR")
            
        # Alerts
        if agent.alerts:
            print(f"\n⚠️  Active Alerts:")
            for alert in agent.alerts[-3:]:  # Show last 3 alerts
                print(f"  - {alert['metric']}: {alert['severity']} severity (Z-score: {alert['z_score']:.2f})")
                
        # Verbose information
        if verbose:
            print(f"\nVerbose Details:")
            print(f"  URL: {agent.url}")
            print(f"  Cumulative Difficulty: {agent.cumulative_difficulty:,}")
            if agent.top_block_hash:
                print(f"  Top Block Hash: {agent.top_block_hash[:16]}...")
                
        # Last update
        if agent.last_update:
            print(f"\nLast Update: {agent.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
            
    def print_network_topology(self):
        """Print network topology visualization."""
        print(f"\n{'='*60}")
        print("Network Topology")
        print(f"{'='*60}")
        
        # Group by AS
        as_groups = defaultdict(list)
        for node_id, node_info in self.network_topology.nodes.items():
            as_num = node_info.get("as_num", "Unknown")
            as_groups[as_num].append(node_id)
            
        print(f"Autonomous Systems:")
        for as_num, nodes in as_groups.items():
            print(f"  AS {as_num}: {', '.join(nodes)}")
            
        # Print connections
        print(f"\nConnections:")
        for node1, node2 in self.network_topology.connections:
            if (node1, node2) not in self.network_topology.connections:
                continue  # Avoid duplicates
            print(f"  {node1} <-> {node2}")
            
    def print_alerts(self):
        """Print active alerts."""
        alerts = self.alert_manager.get_active_alerts()
        if alerts:
            print(f"\n{'='*60}")
            print("Active Alerts")
            print(f"{'='*60}")
            
            for alert in alerts:
                print(f"⚠️  {alert['agent']} - {alert['metric']}: {alert['severity']}")
                print(f"   Current: {alert['current_value']:.2f}, Mean: {alert['mean']:.2f}")
                print(f"   Z-score: {alert['z_score']:.2f}, Time: {alert['timestamp']}")
                
    def export_data(self, filename: str = None):
        """Export monitoring data."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"monerosim_monitor_{timestamp}.{self.export_format}"
            
        try:
            if self.export_format == "json":
                with open(filename, 'w') as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "agents": [
                            {
                                "name": agent.name,
                                "height": agent.height,
                                "hashrate": agent.hashrate,
                                "tx_count": agent.tx_count,
                                "connections": agent.incoming_connections + agent.outgoing_connections,
                                "status": agent.status,
                                "alerts": agent.alerts
                            }
                            for agent in self.agents
                        ],
                        "alerts": self.alert_manager.get_active_alerts()
                    }, f, indent=2)
                    
            elif self.export_format == "csv":
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Agent", "Height", "Hashrate", "TX Count", "Connections", "Status"])
                    
                    for agent in self.agents:
                        writer.writerow([
                            agent.name,
                            agent.height,
                            agent.hashrate,
                            agent.tx_count,
                            agent.incoming_connections + agent.outgoing_connections,
                            agent.status
                        ])
                        
            log_success(COMPONENT, f"Data exported to {filename}")
            
        except Exception as e:
            log_error(COMPONENT, f"Failed to export data: {e}")
            
    def run_monitoring(self, clear_screen: bool = True, verbose: bool = False,
                      export_format: str = None, export_file: str = None):
        """Run the enhanced monitoring loop."""
        iteration = 0
        
        if export_format:
            self.export_format = export_format
        if export_file:
            self.export_file = export_file
            
        try:
            while True:
                iteration += 1
                
                # Clear screen if requested
                if clear_screen:
                    print("\033[2J\033[H")  # ANSI escape codes to clear screen
                    
                print(f"MoneroSim Enhanced Monitor - Iteration #{iteration}")
                print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Update all agents
                for agent in self.agents:
                    self.update_agent_status(agent)
                    
                # Print status for each agent
                for agent in self.agents:
                    self.print_enhanced_status(agent, verbose)
                    
                # Print network topology
                self.print_network_topology()
                
                # Print alerts
                self.print_alerts()
                
                # Export data if enabled
                if self.export_enabled:
                    self.export_data(self.export_file)
                    
                print(f"\nRefreshing in {self.refresh_interval} seconds... (Press Ctrl+C to stop)")
                time.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            log_info(COMPONENT, "Monitoring stopped by user")
            if self.export_enabled:
                self.export_data(self.export_file)


def main():
    """Main function for enhanced monitor script."""
    parser = argparse.ArgumentParser(
        description="Enhanced monitor for Monero agents in Shadow simulation with advanced features"
    )
    
    # Add command line arguments
    parser.add_argument(
        "--agents",
        nargs="+",
        help="List of agents to monitor (format: name=url). If not specified, agents will be discovered automatically.",
        default=None
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=DEFAULT_REFRESH_INTERVAL,
        help=f"Refresh interval in seconds (default: {DEFAULT_REFRESH_INTERVAL})"
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Maximum RPC attempts (default: {DEFAULT_MAX_ATTEMPTS})"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY,
        help=f"Delay between RPC attempts (default: {DEFAULT_RETRY_DELAY})"
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear screen between updates"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (no continuous monitoring)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with additional details"
    )
    parser.add_argument(
        "--export-format",
        choices=["json", "csv"],
        help="Export format for monitoring data"
    )
    parser.add_argument(
        "--export-file",
        help="Export file path (default: auto-generated)"
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Disable data export"
    )
    parser.add_argument(
        "--alert-threshold",
        type=float,
        default=DEFAULT_ALERT_THRESHOLD,
        help=f"Alert threshold in standard deviations (default: {DEFAULT_ALERT_THRESHOLD})"
    )
    
    args, _ = parser.parse_known_args()
    
    log_info(COMPONENT, "=== MoneroSim Enhanced Monitor ===")
    log_info(COMPONENT, f"Starting enhanced monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize enhanced monitor
    monitor = EnhancedMonitor(
        refresh_interval=args.refresh,
        max_attempts=args.max_attempts,
        retry_delay=args.retry_delay
    )
    
    # Configure alert threshold
    monitor.alert_manager.threshold = args.alert_threshold
    
    # Configure export
    monitor.export_enabled = not args.no_export
    if args.export_format:
        monitor.export_format = args.export_format
    if args.export_file:
        monitor.export_file = args.export_file
    
    # Discover agents
    if args.agents:
        # Manual agent specification
        for agent_spec in args.agents:
            if "=" in agent_spec:
                name, url = agent_spec.split("=", 1)
                monitor.agents.append(AgentStatus(name, url))
            else:
                log_error(COMPONENT, f"Invalid agent specification: {agent_spec}")
                handle_exit(1, COMPONENT, "Invalid agent specification")
    else:
        # Automatic discovery
        monitor.agents = monitor.discover_agents()
        
    if not monitor.agents:
        log_error(COMPONENT, "No agents to monitor")
        handle_exit(1, COMPONENT, "No agents to monitor")
        
    log_info(COMPONENT, f"Monitoring {len(monitor.agents)} agents")
    
    # Verify all agents are reachable
    all_ready = True
    unreachable_agents = []
    
    for agent in monitor.agents:
        if not verify_daemon_ready(agent.url, agent.name, args.max_attempts,
                                  args.retry_delay, COMPONENT):
            log_error(COMPONENT, f"Agent {agent.name} is not ready")
            unreachable_agents.append(agent.name)
            all_ready = False
            
    if not all_ready:
        log_error(COMPONENT, f"Unreachable agents: {', '.join(unreachable_agents)}")
        handle_exit(1, COMPONENT, "Not all agents are ready")
        
    if args.once:
        # Single run mode
        log_info(COMPONENT, "Running single enhanced status check")
        
        # Update all agents
        for agent in monitor.agents:
            monitor.update_agent_status(agent)
            
        # Print status
        for agent in monitor.agents:
            monitor.print_enhanced_status(agent, args.verbose)
            
        # Print network topology
        monitor.print_network_topology()
        
        # Print alerts
        monitor.print_alerts()
        
        # Export data
        if monitor.export_enabled:
            monitor.export_data(monitor.export_file)
            
        log_info(COMPONENT, "Enhanced monitor check completed")
        handle_exit(0, COMPONENT, "Single run completed successfully")
    else:
        # Continuous monitoring mode
        log_info(COMPONENT, f"Starting enhanced continuous monitoring (refresh every {args.refresh} seconds)")
        monitor.run_monitoring(
            not args.no_clear, 
            args.verbose,
            args.export_format,
            args.export_file
        )
        
        handle_exit(0, COMPONENT, "Enhanced monitoring stopped")


if __name__ == "__main__":
    main()