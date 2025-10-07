#!/usr/bin/env python3
"""
enhanced_monitor.py - Live Log Monitoring Script for MoneroSim

This script provides advanced monitoring capabilities for the Monero simulation
by parsing live log files from the Shadow environment. It monitors agent activity
in real-time by reading log files from shadow.data/hosts/[agent]/ directories.

Features:
- Real-time blockchain visualization from logs
- Transaction flow tracking from agent logs
- Network topology visualization
- Performance metrics tracking
- Alerting system for anomalies
- Historical data collection
- Export capabilities for analysis

This version parses live log files instead of using RPC calls, making it suitable
for monitoring simulations where external RPC access is not available.
"""

import sys
import time
import argparse
import json
import csv
import os
import re
import glob
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics
import math
import select
import fcntl

# Import error handling
from error_handling import log_info, log_warning, log_error, log_critical, log_success, handle_exit
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
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

    def __init__(self, name: str, log_dir: str):
        self.name = name
        self.log_dir = log_dir
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
        self.last_mining_time: Optional[str] = None
        self.error: Optional[str] = None

        # Log parsing state
        self.last_log_position: Dict[str, int] = {}  # file -> position
        self.log_files: List[str] = []

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
        
    def find_log_directories(self, base_dir: str = "shadow.data/hosts") -> List[Tuple[str, str]]:
        """Find agent log directories in the Shadow data directory."""
        log_dirs = []

        if not os.path.exists(base_dir):
            log_warning(COMPONENT, f"Shadow data directory not found: {base_dir}")
            return log_dirs

        try:
            for item in os.listdir(base_dir):
                agent_dir = os.path.join(base_dir, item)
                if os.path.isdir(agent_dir):
                    # Check if it contains log files
                    log_files = glob.glob(os.path.join(agent_dir, "*.stdout")) + \
                               glob.glob(os.path.join(agent_dir, "*.stderr")) + \
                               glob.glob(os.path.join(agent_dir, "*.log"))

                    if log_files:
                        log_dirs.append((item, agent_dir))
                        log_info(COMPONENT, f"Found agent logs: {item} -> {agent_dir}")

        except Exception as e:
            log_error(COMPONENT, f"Error scanning log directories: {e}")

        return log_dirs

    def discover_agents(self, base_log_dir: str = "shadow.data/hosts") -> List[AgentStatus]:
        """Discover agents by finding their log directories."""
        agents = []

        # First try to get agent info from registry for network topology
        try:
            registry = self.discovery.get_agent_registry()
            agents_data = registry.get("agents", [])
        except Exception:
            agents_data = []

        # Find log directories
        log_dirs = self.find_log_directories(base_log_dir)

        for agent_name, log_dir in log_dirs:
            agent = AgentStatus(agent_name, log_dir)

            # Find log files for this agent
            agent.log_files = glob.glob(os.path.join(log_dir, "*.stdout")) + \
                             glob.glob(os.path.join(log_dir, "*.stderr")) + \
                             glob.glob(os.path.join(log_dir, "*.log"))

            agents.append(agent)

            # Try to get network topology info from registry
            agent_info = None
            if isinstance(agents_data, list):
                for data in agents_data:
                    if data.get("id") == agent_name or data.get("agent_id") == agent_name:
                        agent_info = data
                        break
            elif isinstance(agents_data, dict):
                agent_info = agents_data.get(agent_name)

            if agent_info:
                ip_addr = agent_info.get("ip_addr", "unknown")
                as_num = agent_info.get("as_num")
                self.network_topology.add_node(agent_name, ip_addr, as_num)

        return agents
        
    def parse_log_line(self, line: str) -> Dict[str, Any]:
        """Parse a single log line for monitoring data."""
        data = {}

        # Height information
        height_match = re.search(r'HEIGHT (\d+)', line)
        if height_match:
            data['height'] = int(height_match.group(1))

        # Difficulty (handle both "difficulty:" and "difficulty:\t")
        diff_match = re.search(r'difficulty[:\s]+(\d+)', line)
        if diff_match:
            data['difficulty'] = int(diff_match.group(1))

        # Transaction count
        tx_match = re.search(r'tx_count[:\s]+(\d+)', line)
        if tx_match:
            data['tx_count'] = int(tx_match.group(1))

        # Transaction pool size
        tx_pool_match = re.search(r'tx_pool_size[:\s]+(\d+)', line)
        if tx_pool_match:
            data['tx_pool_size'] = int(tx_pool_match.group(1))

        # Connections
        incoming_match = re.search(r'incoming_connections_count[:\s]+(\d+)', line)
        if incoming_match:
            data['incoming_connections'] = int(incoming_match.group(1))

        outgoing_match = re.search(r'outgoing_connections_count[:\s]+(\d+)', line)
        if outgoing_match:
            data['outgoing_connections'] = int(outgoing_match.group(1))

        # Peer lists
        white_match = re.search(r'white_peerlist_size[:\s]+(\d+)', line)
        if white_match:
            data['white_peerlist_size'] = int(white_match.group(1))

        grey_match = re.search(r'grey_peerlist_size[:\s]+(\d+)', line)
        if grey_match:
            data['grey_peerlist_size'] = int(grey_match.group(1))

        # Status
        if 'synchronized' in line.lower():
            data['synchronized'] = True

        # Mining status - detect when block controller calls generateblocks on this agent
        if 'Calling RPC method generateblocks' in line:
            data['mining_active'] = True
            # Extract timestamp for recent mining activity
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})', line)
            if timestamp_match:
                data['last_mining_time'] = timestamp_match.group(1)

        # Block reward
        reward_match = re.search(r'block_reward[:\s]+(\d+)', line)
        if reward_match:
            data['block_reward'] = int(reward_match.group(1))

        # Cumulative difficulty
        cum_diff_match = re.search(r'cumulative_difficulty[:\s]+(\d+)', line)
        if cum_diff_match:
            data['cumulative_difficulty'] = int(cum_diff_match.group(1))

        # Top block hash
        hash_match = re.search(r'top_block_hash[:\s]+([0-9a-f]{64})', line)
        if hash_match:
            data['top_block_hash'] = hash_match.group(1)

        # Transaction information
        tx_hash_match = re.search(r'tx_hash[:\s]+([0-9a-f]{64})', line)
        if tx_hash_match:
            data['transaction'] = {
                'hash': tx_hash_match.group(1),
                'timestamp': time.time()
            }

        return data

    def read_new_log_lines(self, agent: AgentStatus) -> List[str]:
        """Read new lines from agent's log files."""
        new_lines = []

        for log_file in agent.log_files:
            if not os.path.exists(log_file):
                continue

            # Get current file size
            try:
                current_size = os.path.getsize(log_file)
                last_pos = agent.last_log_position.get(log_file, 0)

                if current_size > last_pos:
                    with open(log_file, 'r') as f:
                        f.seek(last_pos)
                        lines = f.readlines()
                        new_lines.extend(lines)
                        agent.last_log_position[log_file] = f.tell()

            except Exception as e:
                log_warning(COMPONENT, f"Error reading log file {log_file}: {e}")

        return new_lines

    def update_agent_status(self, agent: AgentStatus) -> None:
        """Update agent status by parsing latest log lines."""
        # Read new log lines
        new_lines = self.read_new_log_lines(agent)

        # Parse each new line
        for line in new_lines:
            parsed_data = self.parse_log_line(line.strip())
            if parsed_data:
                # Update agent status with parsed data
                for key, value in parsed_data.items():
                    if key == 'transaction':
                        # Handle transaction separately
                        tx_data = value
                        self.tx_tracker.add_transaction(
                            tx_data['hash'], agent.name, "unknown",
                            0.0, tx_data['timestamp']
                        )
                    elif hasattr(agent, key):
                        setattr(agent, key, value)

        # Update historical data
        timestamp = time.time()
        agent.height_history.append(agent.height)
        agent.hashrate_history.append(agent.hashrate)
        agent.tx_count_history.append(agent.tx_count)
        agent.connection_history.append(agent.incoming_connections + agent.outgoing_connections)
        agent.timestamp_history.append(timestamp)

        # Determine mining status based on recent activity
        agent.mining_active = self._is_recently_mining(agent)

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
                    
    def _is_recently_mining(self, agent: AgentStatus) -> bool:
        """Check if agent has been mining recently (within last 10 minutes of sim time)."""
        if not agent.last_mining_time:
            return False

        try:
            # Parse the simulation timestamp (format: 2000-01-01 00:42:27.035)
            mining_time = datetime.strptime(agent.last_mining_time, "%Y-%m-%d %H:%M:%S.%f")

            # Get current simulation time from agent's logs
            current_sim_time = self._get_current_simulation_time(agent)
            if not current_sim_time:
                return False

            # Check if mining was within last 10 minutes
            time_diff = current_sim_time - mining_time
            return time_diff.total_seconds() < 600  # 10 minutes

        except (ValueError, AttributeError):
            return False

    def _get_current_simulation_time(self, agent: AgentStatus) -> Optional[datetime]:
        """Extract current simulation time from agent's recent log entries."""
        # Read the last few lines of the agent's log to get current sim time
        for log_file in agent.log_files:
            if not os.path.exists(log_file):
                continue

            try:
                with open(log_file, 'r') as f:
                    # Read last 10 lines
                    lines = f.readlines()[-10:]
                    for line in reversed(lines):
                        # Extract timestamp from log line
                        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})', line)
                        if timestamp_match:
                            return datetime.strptime(timestamp_match.group(1), "%Y-%m-%d %H:%M:%S.%f")
            except Exception:
                continue
        return None

    def _get_simulation_time_status(self) -> str:
        """Get current simulation time status from agents."""
        sim_times = []
        for agent in self.agents:
            sim_time = self._get_current_simulation_time(agent)
            if sim_time:
                sim_times.append(sim_time)

        if sim_times:
            latest_time = max(sim_times)
            return latest_time.strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"

    def _rediscover_agents(self):
        """Re-discover agents to catch any that have started since initial discovery."""
        try:
            current_agent_names = {agent.name for agent in self.agents}
            new_agents = self.discover_agents()

            # Add any new agents we haven't seen before
            for agent in new_agents:
                if agent.name not in current_agent_names:
                    log_info(COMPONENT, f"Discovered new agent: {agent.name}")
                    self.agents.append(agent)

        except Exception as e:
            log_warning(COMPONENT, f"Error during agent rediscovery: {e}")

    def _format_hashrate(self, hashrate: int) -> str:
        """Format hashrate for display."""
        if hashrate >= 1000000:
            return f"{hashrate/1000000:.2f} MH/s"
        elif hashrate >= 1000:
            return f"{hashrate/1000:.2f} KH/s"
        else:
            return f"{hashrate} H/s"

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
            print(f"  Log Directory: {agent.log_dir}")
            print(f"  Cumulative Difficulty: {agent.cumulative_difficulty:,}")
            if agent.top_block_hash:
                print(f"  Top Block Hash: {agent.top_block_hash[:16]}...")
            print(f"  Log Files: {len(agent.log_files)}")

        # Last update
        if agent.last_update:
            print(f"\nLast Update: {agent.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
            
    def print_simulation_summary_table(self):
        """Print a summary ASCII table of all agents."""
        print(f"\n{'='*100}")
        print("Simulation Summary")
        print(f"{'='*100}")

        # Table header
        header = "| {:<15} | {:<8} | {:<6} | {:<10} | {:<12} | {:<8} | {:<12} |".format(
            "Agent", "Height", "Sync", "Mining", "Connections", "TX Count", "Last Update"
        )
        print(header)
        print("|-" + "-"*15 + "-|-" + "-"*8 + "-|-" + "-"*6 + "-|-" + "-"*10 + "-|-" + "-"*12 + "-|-" + "-"*8 + "-|-" + "-"*12 + "-|")

        # Sort agents by name for consistent display
        sorted_agents = sorted(self.agents, key=lambda x: x.name)

        for agent in sorted_agents:
            # Format data
            height = str(agent.height) if agent.height > 0 else "0"
            sync_status = "✓" if agent.synchronized else "✗"
            mining_status = "✓" if agent.mining_active else "✗"
            connections = f"{agent.incoming_connections + agent.outgoing_connections}"
            tx_count = str(agent.tx_count) if agent.tx_count > 0 else "0"
            last_update = agent.last_update.strftime("%H:%M:%S") if agent.last_update else "N/A"

            # Print row
            row = "| {:<15} | {:<8} | {:<6} | {:<10} | {:<12} | {:<8} | {:<12} |".format(
                agent.name[:15], height[:8], sync_status, mining_status,
                connections[:10], tx_count[:8], last_update
            )
            print(row)

        print(f"{'='*100}")

        # Summary statistics
        total_agents = len(self.agents)
        synced_agents = sum(1 for agent in self.agents if agent.synchronized)
        mining_agents = sum(1 for agent in self.agents if agent.mining_active)
        total_height = sum(agent.height for agent in self.agents)
        avg_height = total_height / total_agents if total_agents > 0 else 0

        print(f"Summary: {total_agents} agents | {synced_agents} synced | {mining_agents} mining | Avg height: {avg_height:.1f}")
        print(f"{'='*100}")

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
                    
                sim_time = self._get_simulation_time_status()
                print(f"MoneroSim Enhanced Monitor - Iteration #{iteration}")
                print(f"Real Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Sim Time: {sim_time}")
                
                # Periodically rediscover agents (every 5 iterations)
                if iteration % 5 == 1:
                    self._rediscover_agents()

                # Update all agents
                for agent in self.agents:
                    self.update_agent_status(agent)
                    
                # Print status for each agent
                for agent in self.agents:
                    self.print_enhanced_status(agent, verbose)

                # Print simulation summary table
                self.print_simulation_summary_table()

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
        help="List of agents to monitor (format: name=log_dir). If not specified, agents will be discovered automatically.",
        default=None
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=DEFAULT_REFRESH_INTERVAL,
        help=f"Refresh interval in seconds (default: {DEFAULT_REFRESH_INTERVAL})"
    )
    parser.add_argument(
        "--log-dir",
        default="shadow.data/hosts",
        help="Base directory containing agent log directories (default: shadow.data/hosts)"
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
    monitor = EnhancedMonitor(refresh_interval=args.refresh)

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
                name, log_dir = agent_spec.split("=", 1)
                agent = AgentStatus(name, log_dir)
                # Find log files
                agent.log_files = glob.glob(os.path.join(log_dir, "*.stdout")) + \
                                 glob.glob(os.path.join(log_dir, "*.stderr")) + \
                                 glob.glob(os.path.join(log_dir, "*.log"))
                monitor.agents.append(agent)
            else:
                log_error(COMPONENT, f"Invalid agent specification: {agent_spec}")
                handle_exit(1, COMPONENT, "Invalid agent specification")
    else:
        # Automatic discovery
        monitor.agents = monitor.discover_agents(args.log_dir)

    if not monitor.agents:
        log_error(COMPONENT, "No agents to monitor")
        handle_exit(1, COMPONENT, "No agents to monitor")

    log_info(COMPONENT, f"Monitoring {len(monitor.agents)} agents")
        
    if args.once:
        # Single run mode
        log_info(COMPONENT, "Running single enhanced status check")
        
        # Update all agents
        for agent in monitor.agents:
            monitor.update_agent_status(agent)
            
        # Print status
        for agent in monitor.agents:
            monitor.print_enhanced_status(agent, args.verbose)

        # Print simulation summary table
        monitor.print_simulation_summary_table()

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