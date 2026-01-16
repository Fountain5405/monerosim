#!/usr/bin/env python3
"""
tx_analyzer.py - Transaction Routing Analysis Tool for MoneroSim

Analyzes transaction propagation patterns, spy node vulnerabilities,
network resilience, and Dandelion++ stem paths from simulation logs.
"""

import os
import sys
import argparse
import json
import re
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import statistics

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_SHARED_DIR = "/tmp/monerosim_shared"
DEFAULT_SHADOW_DATA = "shadow.data"
DEFAULT_OUTPUT_DIR = "analysis_output"

# Timing thresholds for vulnerability assessment (milliseconds)
HIGH_VULNERABILITY_THRESHOLD_MS = 100  # < 100ms spread = high vulnerability
MODERATE_VULNERABILITY_THRESHOLD_MS = 500  # < 500ms spread = moderate

# Dandelion++ fluff detection threshold (milliseconds)
FLUFF_DETECTION_THRESHOLD_MS = 100
FLUFF_MIN_RECEIVERS = 3

# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TxObservation:
    """A single observation of a transaction at a node."""
    timestamp: float  # Unix timestamp with milliseconds
    node_id: str  # Node that observed the TX
    source_ip: str  # IP address of the peer that sent the TX
    source_port: int  # Port of the peer
    direction: str  # INC or OUT
    tx_hash: str

@dataclass
class Transaction:
    """Ground truth transaction data."""
    tx_hash: str
    sender_id: str
    recipient_id: str
    amount: float
    timestamp: float

@dataclass
class BlockInfo:
    """Block information with included transactions."""
    height: int
    transactions: List[str]
    tx_count: int

@dataclass
class Agent:
    """Agent/node information."""
    id: str
    ip_addr: str
    daemon: bool = False
    wallet: bool = False
    daemon_rpc_port: int = 18081

@dataclass
class ConnectionEvent:
    """Network connection event."""
    timestamp: float
    node_id: str
    peer_ip: str
    peer_port: int
    event_type: str  # NEW or CLOSE
    direction: str  # INC or OUT
    uuid: Optional[str] = None

# ============================================================================
# Log Parsing
# ============================================================================

# Regex patterns for log parsing
TIMESTAMP_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})'

# TX received pattern: [IP:PORT INC/OUT] Received NOTIFY_NEW_TRANSACTIONS (N txes)
TX_RECEIVED_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\]\s+Received NOTIFY_NEW_TRANSACTIONS\s+\((\d+)\s+txes?\)'
)

# Including transaction pattern: Including transaction <hash>
TX_INCLUDE_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+Including transaction\s+<([0-9a-f]{64})>'
)

# TX hash announcement (V2): [IP:PORT INC/OUT] Received NOTIFY_TX_POOL_HASH (N txes)
TX_HASH_ANNOUNCE_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\]\s+Received NOTIFY_TX_POOL_HASH\s+\((\d+)\s+txes?\)'
)

# TX request (V2): [IP:PORT INC/OUT] Received NOTIFY_REQUEST_TX_POOL_TXS (N txes)
TX_REQUEST_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\]\s+Received NOTIFY_REQUEST_TX_POOL_TXS\s+\((\d+)\s+txes?\)'
)

# Connection events: [IP:PORT UUID INC/OUT] NEW CONNECTION / CLOSE CONNECTION
CONNECTION_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+([0-9a-f-]+)\s+(INC|OUT)\]\s+(NEW|CLOSE)\s+CONNECTION'
)

# Block received: [IP:PORT INC/OUT] Received NOTIFY_NEW_FLUFFY_BLOCK <hash> (height N, N txes)
BLOCK_RECEIVED_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+\[(\d+\.\d+\.\d+\.\d+):(\d+)\s+(INC|OUT)\].*Received NOTIFY_NEW_FLUFFY_BLOCK\s+<([0-9a-f]+)>\s+\(height\s+(\d+)'
)

# Block mined locally: +++++ BLOCK SUCCESSFULLY ADDED followed by HEIGHT N
BLOCK_MINED_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+\+\+\+\+\+\s+BLOCK SUCCESSFULLY ADDED'
)

BLOCK_HEIGHT_PATTERN = re.compile(
    TIMESTAMP_PATTERN + r'\s+I\s+HEIGHT\s+(\d+),\s+difficulty:\s+(\d+)'
)


def parse_timestamp(ts_str: str) -> float:
    """Parse timestamp string to Unix timestamp with milliseconds."""
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    return dt.timestamp()


def parse_log_file(log_path: str, node_id: str) -> Dict:
    """
    Parse a single node's log file and extract relevant events.

    Returns dict with:
        - tx_observations: List of (timestamp, source_ip, source_port, direction, tx_hash)
        - v1_messages: Count of V1 protocol messages
        - v2_hash_announces: Count of V2 hash announcements
        - v2_requests: Count of V2 TX requests
        - connection_events: List of connection events
        - blocks_received: List of block receive events
        - blocks_mined: List of locally mined blocks
    """
    result = {
        'tx_observations': [],
        'v1_messages': 0,
        'v2_hash_announces': 0,
        'v2_requests': 0,
        'connection_events': [],
        'blocks_received': [],
        'blocks_mined': []
    }

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: Could not read {log_path}: {e}", file=sys.stderr)
        return result

    # Track the last TX received event for associating with Including transaction lines
    last_tx_received = None
    pending_block_mined = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for TX received (V1)
        match = TX_RECEIVED_PATTERN.match(line)
        if match:
            ts_str, source_ip, source_port, direction, tx_count = match.groups()
            if int(tx_count) > 0:
                last_tx_received = {
                    'timestamp': parse_timestamp(ts_str),
                    'source_ip': source_ip,
                    'source_port': int(source_port),
                    'direction': direction
                }
                result['v1_messages'] += 1
            continue

        # Check for Including transaction
        match = TX_INCLUDE_PATTERN.match(line)
        if match:
            ts_str, tx_hash = match.groups()
            timestamp = parse_timestamp(ts_str)

            # Use the last TX received info if available and recent (within 1 second)
            if last_tx_received and abs(timestamp - last_tx_received['timestamp']) < 1.0:
                result['tx_observations'].append({
                    'timestamp': timestamp,
                    'source_ip': last_tx_received['source_ip'],
                    'source_port': last_tx_received['source_port'],
                    'direction': last_tx_received['direction'],
                    'tx_hash': tx_hash,
                    'node_id': node_id
                })
            else:
                # No associated TX received event
                result['tx_observations'].append({
                    'timestamp': timestamp,
                    'source_ip': None,
                    'source_port': None,
                    'direction': None,
                    'tx_hash': tx_hash,
                    'node_id': node_id
                })
            continue

        # Check for V2 hash announcement
        match = TX_HASH_ANNOUNCE_PATTERN.match(line)
        if match:
            result['v2_hash_announces'] += 1
            continue

        # Check for V2 TX request
        match = TX_REQUEST_PATTERN.match(line)
        if match:
            result['v2_requests'] += 1
            continue

        # Check for connection events
        match = CONNECTION_PATTERN.match(line)
        if match:
            ts_str, peer_ip, peer_port, uuid, direction, event_type = match.groups()
            result['connection_events'].append({
                'timestamp': parse_timestamp(ts_str),
                'peer_ip': peer_ip,
                'peer_port': int(peer_port),
                'uuid': uuid,
                'direction': direction,
                'event_type': event_type,
                'node_id': node_id
            })
            continue

        # Check for block received
        match = BLOCK_RECEIVED_PATTERN.match(line)
        if match:
            ts_str, source_ip, source_port, direction, block_hash, height = match.groups()
            result['blocks_received'].append({
                'timestamp': parse_timestamp(ts_str),
                'source_ip': source_ip,
                'source_port': int(source_port),
                'direction': direction,
                'block_hash': block_hash,
                'height': int(height),
                'node_id': node_id
            })
            continue

        # Check for block mined
        match = BLOCK_MINED_PATTERN.match(line)
        if match:
            ts_str = match.group(1)
            pending_block_mined = parse_timestamp(ts_str)
            continue

        # Check for block height (follows BLOCK SUCCESSFULLY ADDED)
        if pending_block_mined:
            match = BLOCK_HEIGHT_PATTERN.match(line)
            if match:
                ts_str, height, difficulty = match.groups()
                result['blocks_mined'].append({
                    'timestamp': pending_block_mined,
                    'height': int(height),
                    'difficulty': int(difficulty),
                    'node_id': node_id
                })
                pending_block_mined = None

    return result


def parse_all_logs(shadow_data_dir: str, max_workers: int = None) -> Dict:
    """
    Parse all node logs in parallel.

    Returns aggregated results from all nodes.
    """
    hosts_dir = Path(shadow_data_dir) / "hosts"
    if not hosts_dir.exists():
        print(f"Error: Hosts directory not found: {hosts_dir}", file=sys.stderr)
        return {}

    # Find all log files
    log_files = []
    for node_dir in hosts_dir.iterdir():
        if node_dir.is_dir():
            log_file = node_dir / "bash.1000.stdout"
            if log_file.exists():
                log_files.append((str(log_file), node_dir.name))

    if not log_files:
        print("Warning: No log files found", file=sys.stderr)
        return {}

    if max_workers is None:
        max_workers = min(len(log_files), multiprocessing.cpu_count())

    # Parse logs in parallel
    all_results = {
        'tx_observations': [],
        'v1_messages': 0,
        'v2_hash_announces': 0,
        'v2_requests': 0,
        'connection_events': [],
        'blocks_received': [],
        'blocks_mined': []
    }

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(parse_log_file, log_path, node_id): node_id
            for log_path, node_id in log_files
        }

        for future in as_completed(futures):
            node_id = futures[future]
            try:
                result = future.result()
                all_results['tx_observations'].extend(result['tx_observations'])
                all_results['v1_messages'] += result['v1_messages']
                all_results['v2_hash_announces'] += result['v2_hash_announces']
                all_results['v2_requests'] += result['v2_requests']
                all_results['connection_events'].extend(result['connection_events'])
                all_results['blocks_received'].extend(result['blocks_received'])
                all_results['blocks_mined'].extend(result['blocks_mined'])
            except Exception as e:
                print(f"Error parsing logs for {node_id}: {e}", file=sys.stderr)

    return all_results


# ============================================================================
# Data Loading
# ============================================================================

def load_agent_registry(shared_dir: str) -> Tuple[Dict[str, Agent], Dict[str, str], Dict[str, str]]:
    """
    Load agent registry and build IP mappings.

    Returns:
        - agents: Dict[id, Agent]
        - ip_to_node: Dict[ip, node_id]
        - node_to_ip: Dict[node_id, ip]
    """
    registry_path = Path(shared_dir) / "agent_registry.json"

    agents = {}
    ip_to_node = {}
    node_to_ip = {}

    try:
        with open(registry_path, 'r') as f:
            data = json.load(f)

        for agent_data in data.get('agents', []):
            agent = Agent(
                id=agent_data['id'],
                ip_addr=agent_data.get('ip_addr', ''),
                daemon=agent_data.get('daemon', False),
                wallet=agent_data.get('wallet', False),
                daemon_rpc_port=agent_data.get('daemon_rpc_port', 18081)
            )
            agents[agent.id] = agent
            if agent.ip_addr:
                ip_to_node[agent.ip_addr] = agent.id
                node_to_ip[agent.id] = agent.ip_addr

    except FileNotFoundError:
        print(f"Warning: Agent registry not found at {registry_path}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"Error parsing agent registry: {e}", file=sys.stderr)

    return agents, ip_to_node, node_to_ip


def load_transactions(shared_dir: str) -> Dict[str, Transaction]:
    """Load ground truth transaction data."""
    tx_path = Path(shared_dir) / "transactions.json"
    result = {}

    try:
        with open(tx_path, 'r') as f:
            data = json.load(f)

        for tx_data in data:
            # Handle case where tx_hash might be a nested dict with full TX info
            tx_hash_raw = tx_data['tx_hash']
            if isinstance(tx_hash_raw, dict):
                tx_hash = tx_hash_raw.get('tx_hash', '')
            else:
                tx_hash = tx_hash_raw

            if not tx_hash or not isinstance(tx_hash, str):
                continue  # Skip malformed entries

            tx_obj = Transaction(
                tx_hash=tx_hash,
                sender_id=tx_data.get('sender_id', ''),
                recipient_id=tx_data.get('recipient_id', ''),
                amount=tx_data.get('amount', 0.0),
                timestamp=tx_data.get('timestamp', 0.0)
            )
            result[tx_obj.tx_hash] = tx_obj

    except FileNotFoundError:
        print(f"Warning: Transactions file not found at {tx_path}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"Error parsing transactions: {e}", file=sys.stderr)
    except KeyError as e:
        print(f"Error: Missing field in transaction data: {e}", file=sys.stderr)

    return result


def load_blocks(shared_dir: str) -> List[BlockInfo]:
    """Load block information with included transactions."""
    blocks_path = Path(shared_dir) / "blocks_with_transactions.json"
    blocks = []

    try:
        with open(blocks_path, 'r') as f:
            data = json.load(f)

        for block_data in data:
            block = BlockInfo(
                height=block_data['height'],
                transactions=block_data.get('transactions', []),
                tx_count=block_data.get('tx_count', 0)
            )
            blocks.append(block)

    except FileNotFoundError:
        print(f"Warning: Blocks file not found at {blocks_path}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"Error parsing blocks: {e}", file=sys.stderr)

    return blocks


# ============================================================================
# Analysis Modules
# ============================================================================

def analyze_spy_node(
    tx_observations: List[Dict],
    transactions: Dict[str, Transaction],
    ip_to_node: Dict[str, str],
    node_to_ip: Dict[str, str]
) -> Dict:
    """
    Spy Node Analysis: For each TX, determine if the originator can be inferred.

    Returns analysis results including inference accuracy and vulnerability distribution.
    """
    # Group observations by TX hash
    tx_obs_map = defaultdict(list)
    for obs in tx_observations:
        tx_obs_map[obs['tx_hash']].append(obs)

    # Sort observations by timestamp for each TX
    for tx_hash in tx_obs_map:
        tx_obs_map[tx_hash].sort(key=lambda x: x['timestamp'])

    results = {
        'inference_accuracy': 0.0,
        'total_transactions': len(transactions),
        'analyzable_transactions': 0,
        'correct_inferences': 0,
        'timing_distribution': {
            'high_vulnerability_count': 0,
            'moderate_vulnerability_count': 0,
            'low_vulnerability_count': 0
        },
        'vulnerable_senders': [],
        'tx_details': []
    }

    for tx_hash, tx in transactions.items():
        observations = tx_obs_map.get(tx_hash, [])
        if not observations:
            continue

        results['analyzable_transactions'] += 1

        # Find first observation
        first_obs = observations[0]
        last_obs = observations[-1]

        # Calculate timing spread
        timing_spread_ms = (last_obs['timestamp'] - first_obs['timestamp']) * 1000

        # Classify vulnerability
        if timing_spread_ms < HIGH_VULNERABILITY_THRESHOLD_MS:
            results['timing_distribution']['high_vulnerability_count'] += 1
            vulnerability = 'high'
        elif timing_spread_ms < MODERATE_VULNERABILITY_THRESHOLD_MS:
            results['timing_distribution']['moderate_vulnerability_count'] += 1
            vulnerability = 'moderate'
        else:
            results['timing_distribution']['low_vulnerability_count'] += 1
            vulnerability = 'low'

        # Infer originator from first-seen source IP
        inferred_originator = None
        if first_obs.get('source_ip'):
            inferred_originator = ip_to_node.get(first_obs['source_ip'])

        # Compare with actual sender
        actual_sender = tx.sender_id
        correct = inferred_originator == actual_sender

        if correct:
            results['correct_inferences'] += 1

        # Track vulnerable senders
        if vulnerability in ('high', 'moderate') and actual_sender not in results['vulnerable_senders']:
            results['vulnerable_senders'].append(actual_sender)

        results['tx_details'].append({
            'tx_hash': tx_hash[:16] + '...',
            'actual_sender': actual_sender,
            'inferred_originator': inferred_originator,
            'correct': correct,
            'timing_spread_ms': round(timing_spread_ms, 1),
            'vulnerability': vulnerability,
            'first_observer': first_obs['node_id'],
            'observation_count': len(observations)
        })

    # Calculate accuracy
    if results['analyzable_transactions'] > 0:
        results['inference_accuracy'] = round(
            results['correct_inferences'] / results['analyzable_transactions'], 3
        )

    return results


def analyze_propagation(
    tx_observations: List[Dict],
    transactions: Dict[str, Transaction],
    blocks: List[BlockInfo]
) -> Dict:
    """
    Propagation Timing Analysis: Measure TX propagation times across the network.
    """
    # Group observations by TX hash
    tx_obs_map = defaultdict(list)
    for obs in tx_observations:
        tx_obs_map[obs['tx_hash']].append(obs)

    # Sort observations by timestamp
    for tx_hash in tx_obs_map:
        tx_obs_map[tx_hash].sort(key=lambda x: x['timestamp'])

    # Build TX to block mapping
    tx_to_block = {}
    for block in blocks:
        for tx_hash in block.transactions:
            tx_to_block[tx_hash] = block.height

    propagation_times = []
    confirmation_delays = []
    node_receive_times = defaultdict(list)

    results = {
        'average_propagation_ms': 0.0,
        'median_propagation_ms': 0.0,
        'p95_propagation_ms': 0.0,
        'min_propagation_ms': 0.0,
        'max_propagation_ms': 0.0,
        'average_confirmation_delay_s': 0.0,
        'bottleneck_nodes': [],
        'tx_propagation_details': []
    }

    for tx_hash, tx in transactions.items():
        observations = tx_obs_map.get(tx_hash, [])
        if len(observations) < 2:
            continue

        first_obs = observations[0]
        last_obs = observations[-1]

        # Propagation time (first to last observation)
        prop_time_ms = (last_obs['timestamp'] - first_obs['timestamp']) * 1000
        propagation_times.append(prop_time_ms)

        # Track per-node receive times relative to first observation
        for obs in observations:
            relative_time = (obs['timestamp'] - first_obs['timestamp']) * 1000
            node_receive_times[obs['node_id']].append(relative_time)

        # Confirmation delay
        if tx_hash in tx_to_block:
            # We'd need block timestamps to calculate this properly
            # For now, skip this calculation
            pass

        results['tx_propagation_details'].append({
            'tx_hash': tx_hash[:16] + '...',
            'propagation_ms': round(prop_time_ms, 1),
            'nodes_reached': len(set(o['node_id'] for o in observations)),
            'first_observer': first_obs['node_id'],
            'last_observer': last_obs['node_id']
        })

    if propagation_times:
        propagation_times.sort()
        results['average_propagation_ms'] = round(statistics.mean(propagation_times), 1)
        results['median_propagation_ms'] = round(statistics.median(propagation_times), 1)
        results['min_propagation_ms'] = round(min(propagation_times), 1)
        results['max_propagation_ms'] = round(max(propagation_times), 1)

        # P95
        p95_idx = int(len(propagation_times) * 0.95)
        results['p95_propagation_ms'] = round(propagation_times[min(p95_idx, len(propagation_times)-1)], 1)

    # Identify bottleneck nodes (consistently slow to receive)
    avg_node_delays = {}
    for node_id, times in node_receive_times.items():
        if times:
            avg_node_delays[node_id] = statistics.mean(times)

    if avg_node_delays:
        overall_avg = statistics.mean(avg_node_delays.values())
        # Nodes with average delay > 2x overall average are bottlenecks
        bottlenecks = [
            {'node_id': node_id, 'avg_delay_ms': round(delay, 1)}
            for node_id, delay in avg_node_delays.items()
            if delay > overall_avg * 2
        ]
        bottlenecks.sort(key=lambda x: x['avg_delay_ms'], reverse=True)
        results['bottleneck_nodes'] = bottlenecks[:10]  # Top 10

    return results


def analyze_network_resilience(
    connection_events: List[Dict],
    agents: Dict[str, Agent],
    ip_to_node: Dict[str, str]
) -> Dict:
    """
    Network Resilience Analysis: Analyze connectivity and centralization.
    """
    # Build current peer connections per node
    node_peers = defaultdict(set)
    connection_state = {}  # (node_id, peer_ip, peer_port) -> bool

    # Sort events by timestamp
    sorted_events = sorted(connection_events, key=lambda x: x['timestamp'])

    for event in sorted_events:
        node_id = event['node_id']
        peer_key = (node_id, event['peer_ip'], event['peer_port'])

        if event['event_type'] == 'NEW':
            connection_state[peer_key] = True
            peer_node = ip_to_node.get(event['peer_ip'])
            if peer_node:
                node_peers[node_id].add(peer_node)
                node_peers[peer_node].add(node_id)
        elif event['event_type'] == 'CLOSE':
            connection_state[peer_key] = False

    # Calculate peer counts
    peer_counts = {node_id: len(peers) for node_id, peers in node_peers.items()}

    # Find isolated nodes (no peers)
    daemon_nodes = {a.id for a in agents.values() if a.daemon}
    connected_nodes = set(node_peers.keys())
    isolated_nodes = list(daemon_nodes - connected_nodes)

    # Calculate Gini coefficient of peer counts
    if peer_counts:
        counts = list(peer_counts.values())
        gini = calculate_gini(counts)
    else:
        gini = 0.0

    # Identify critical nodes (high betweenness - simplified)
    # Nodes whose removal would most affect connectivity
    critical_nodes = []
    for node_id in peer_counts:
        # Simple heuristic: nodes with many peers are more critical
        if peer_counts[node_id] > statistics.mean(peer_counts.values()) * 1.5:
            critical_nodes.append({
                'node_id': node_id,
                'peer_count': peer_counts[node_id]
            })
    critical_nodes.sort(key=lambda x: x['peer_count'], reverse=True)

    results = {
        'total_daemon_nodes': len(daemon_nodes),
        'connected_nodes': len(connected_nodes),
        'isolated_nodes': isolated_nodes,
        'average_peer_count': round(statistics.mean(peer_counts.values()), 1) if peer_counts else 0,
        'median_peer_count': round(statistics.median(peer_counts.values()), 1) if peer_counts else 0,
        'max_peer_count': max(peer_counts.values()) if peer_counts else 0,
        'min_peer_count': min(peer_counts.values()) if peer_counts else 0,
        'gini_coefficient': round(gini, 3),
        'critical_nodes': critical_nodes[:5],
        'peer_distribution': dict(sorted(peer_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    }

    return results


def calculate_gini(values: List[float]) -> float:
    """Calculate Gini coefficient for a list of values."""
    if not values or len(values) == 0:
        return 0.0

    n = len(values)
    if n == 1:
        return 0.0

    sorted_values = sorted(values)
    cumulative = sum((i + 1) * v for i, v in enumerate(sorted_values))
    total = sum(sorted_values)

    if total == 0:
        return 0.0

    return (2 * cumulative) / (n * total) - (n + 1) / n


def analyze_tx_relay_v2(log_stats: Dict) -> Dict:
    """
    TX Relay V2 Analysis: Compare V1 vs V2 protocol usage.
    """
    v1_count = log_stats.get('v1_messages', 0)
    v2_hash_count = log_stats.get('v2_hash_announces', 0)
    v2_request_count = log_stats.get('v2_requests', 0)

    total_messages = v1_count + v2_hash_count + v2_request_count

    results = {
        'v1_message_count': v1_count,
        'v2_hash_announcement_count': v2_hash_count,
        'v2_request_count': v2_request_count,
        'total_messages': total_messages,
        'v1_percentage': round(v1_count / total_messages * 100, 1) if total_messages > 0 else 0,
        'v2_percentage': round((v2_hash_count + v2_request_count) / total_messages * 100, 1) if total_messages > 0 else 0,
        'health_assessment': 'good' if v1_count > 0 else 'no_data'
    }

    # Health assessment based on message patterns
    if total_messages == 0:
        results['health_assessment'] = 'no_data'
    elif v2_hash_count > 0 and v2_request_count > 0:
        # V2 is being used
        if v2_request_count / v2_hash_count > 0.5:
            results['health_assessment'] = 'excellent'
        else:
            results['health_assessment'] = 'good'
    elif v1_count > 0:
        results['health_assessment'] = 'v1_only'

    return results


def analyze_dandelion_paths(
    tx_observations: List[Dict],
    transactions: Dict[str, Transaction],
    ip_to_node: Dict[str, str],
    node_to_ip: Dict[str, str]
) -> Dict:
    """
    Dandelion++ Stem Path Reconstruction.

    Reconstructs the stem path for each transaction by following the chain
    of observations where each receiver's IP becomes the next sender.
    """
    # Group observations by TX hash
    tx_obs_map = defaultdict(list)
    for obs in tx_observations:
        tx_obs_map[obs['tx_hash']].append(obs)

    # Sort observations by timestamp
    for tx_hash in tx_obs_map:
        tx_obs_map[tx_hash].sort(key=lambda x: x['timestamp'])

    results = {
        'paths_reconstructed': 0,
        'avg_stem_length': 0.0,
        'min_stem_length': 0,
        'max_stem_length': 0,
        'frequent_fluff_points': {},
        'privacy_score': 0.0,
        'paths': []
    }

    stem_lengths = []
    fluff_point_counts = defaultdict(int)

    for tx_hash, tx in transactions.items():
        observations = tx_obs_map.get(tx_hash, [])
        if not observations:
            continue

        originator_ip = node_to_ip.get(tx.sender_id)
        if not originator_ip:
            continue

        # Reconstruct stem path
        stem_path = []
        current_ip = originator_ip
        used_nodes = {tx.sender_id}
        fluff_node = None
        stem_start_time = None
        stem_end_time = None

        # Build a map of observations by source IP
        obs_by_source = defaultdict(list)
        for obs in observations:
            if obs.get('source_ip'):
                obs_by_source[obs['source_ip']].append(obs)

        # Follow the chain
        iteration = 0
        max_iterations = 100  # Prevent infinite loops

        while iteration < max_iterations:
            iteration += 1

            # Find observations where source_ip == current_ip
            matching_obs = obs_by_source.get(current_ip, [])

            if not matching_obs:
                break

            # Check for fluff point: multiple nodes receiving from same source within threshold
            if len(matching_obs) >= FLUFF_MIN_RECEIVERS:
                # Check timing spread
                times = [o['timestamp'] for o in matching_obs]
                time_spread = (max(times) - min(times)) * 1000

                if time_spread <= FLUFF_DETECTION_THRESHOLD_MS:
                    # Fluff detected
                    fluff_node = ip_to_node.get(current_ip)
                    if stem_start_time is None and matching_obs:
                        stem_start_time = matching_obs[0]['timestamp']
                    stem_end_time = max(times)
                    break

            # Take the first observation as the next hop
            next_obs = matching_obs[0]
            next_node = next_obs['node_id']

            if next_node in used_nodes:
                # Cycle detected, stop
                break

            stem_path.append(next_node)
            used_nodes.add(next_node)

            if stem_start_time is None:
                stem_start_time = next_obs['timestamp']
            stem_end_time = next_obs['timestamp']

            # Move to next hop
            next_node_ip = node_to_ip.get(next_node)
            if not next_node_ip:
                break
            current_ip = next_node_ip

        # Calculate stem duration
        stem_duration_ms = 0.0
        if stem_start_time and stem_end_time:
            stem_duration_ms = (stem_end_time - stem_start_time) * 1000

        if stem_path:
            results['paths_reconstructed'] += 1
            stem_lengths.append(len(stem_path))

            if fluff_node:
                fluff_point_counts[fluff_node] += 1

            results['paths'].append({
                'tx_hash': tx_hash[:16] + '...',
                'originator': tx.sender_id,
                'stem_path': stem_path,
                'fluff_node': fluff_node,
                'stem_length': len(stem_path),
                'stem_duration_ms': round(stem_duration_ms, 1)
            })

    if stem_lengths:
        results['avg_stem_length'] = round(statistics.mean(stem_lengths), 1)
        results['min_stem_length'] = min(stem_lengths)
        results['max_stem_length'] = max(stem_lengths)

        # Privacy score: higher stem lengths = better privacy
        # Score from 0-1, based on average stem length (target: 10+ hops)
        results['privacy_score'] = round(min(1.0, results['avg_stem_length'] / 10), 2)

    # Top fluff points
    results['frequent_fluff_points'] = dict(
        sorted(fluff_point_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    )

    return results


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(
    spy_analysis: Dict,
    propagation_analysis: Dict,
    resilience_analysis: Dict,
    relay_v2_analysis: Dict,
    dandelion_analysis: Dict,
    metadata: Dict
) -> Dict:
    """Generate the full analysis report."""
    return {
        'metadata': metadata,
        'spy_node_analysis': {
            'inference_accuracy': spy_analysis.get('inference_accuracy', 0),
            'total_transactions': spy_analysis.get('total_transactions', 0),
            'analyzable_transactions': spy_analysis.get('analyzable_transactions', 0),
            'correct_inferences': spy_analysis.get('correct_inferences', 0),
            'timing_distribution': spy_analysis.get('timing_distribution', {}),
            'vulnerable_senders': spy_analysis.get('vulnerable_senders', [])
        },
        'propagation_analysis': {
            'average_propagation_ms': propagation_analysis.get('average_propagation_ms', 0),
            'median_propagation_ms': propagation_analysis.get('median_propagation_ms', 0),
            'p95_propagation_ms': propagation_analysis.get('p95_propagation_ms', 0),
            'min_propagation_ms': propagation_analysis.get('min_propagation_ms', 0),
            'max_propagation_ms': propagation_analysis.get('max_propagation_ms', 0),
            'bottleneck_nodes': propagation_analysis.get('bottleneck_nodes', [])
        },
        'network_resilience': {
            'total_daemon_nodes': resilience_analysis.get('total_daemon_nodes', 0),
            'connected_nodes': resilience_analysis.get('connected_nodes', 0),
            'isolated_nodes': resilience_analysis.get('isolated_nodes', []),
            'average_peer_count': resilience_analysis.get('average_peer_count', 0),
            'gini_coefficient': resilience_analysis.get('gini_coefficient', 0),
            'critical_nodes': resilience_analysis.get('critical_nodes', [])
        },
        'tx_relay_v2_analysis': relay_v2_analysis,
        'dandelion_analysis': {
            'paths_reconstructed': dandelion_analysis.get('paths_reconstructed', 0),
            'avg_stem_length': dandelion_analysis.get('avg_stem_length', 0),
            'min_stem_length': dandelion_analysis.get('min_stem_length', 0),
            'max_stem_length': dandelion_analysis.get('max_stem_length', 0),
            'privacy_score': dandelion_analysis.get('privacy_score', 0),
            'frequent_fluff_points': dandelion_analysis.get('frequent_fluff_points', {}),
            'paths': dandelion_analysis.get('paths', [])
        }
    }


def print_summary(report: Dict):
    """Print a human-readable summary of the analysis."""
    print("\n" + "=" * 70)
    print("TRANSACTION ROUTING ANALYSIS SUMMARY")
    print("=" * 70)

    meta = report.get('metadata', {})
    print(f"\nAnalysis timestamp: {meta.get('analysis_timestamp', 'N/A')}")
    print(f"Total nodes: {meta.get('total_nodes', 0)}")
    print(f"Total transactions: {meta.get('total_transactions', 0)}")
    print(f"Total blocks: {meta.get('total_blocks', 0)}")

    # Spy Node Analysis
    spy = report.get('spy_node_analysis', {})
    print("\n--- SPY NODE ANALYSIS ---")
    print(f"Inference accuracy: {spy.get('inference_accuracy', 0) * 100:.1f}%")
    print(f"Analyzable transactions: {spy.get('analyzable_transactions', 0)}")
    timing = spy.get('timing_distribution', {})
    print(f"Vulnerability distribution:")
    print(f"  High risk:     {timing.get('high_vulnerability_count', 0)}")
    print(f"  Moderate risk: {timing.get('moderate_vulnerability_count', 0)}")
    print(f"  Low risk:      {timing.get('low_vulnerability_count', 0)}")

    # Propagation Analysis
    prop = report.get('propagation_analysis', {})
    print("\n--- PROPAGATION TIMING ---")
    print(f"Average propagation: {prop.get('average_propagation_ms', 0):.1f} ms")
    print(f"Median propagation:  {prop.get('median_propagation_ms', 0):.1f} ms")
    print(f"P95 propagation:     {prop.get('p95_propagation_ms', 0):.1f} ms")

    # Network Resilience
    res = report.get('network_resilience', {})
    print("\n--- NETWORK RESILIENCE ---")
    print(f"Connected nodes: {res.get('connected_nodes', 0)} / {res.get('total_daemon_nodes', 0)}")
    print(f"Average peers:   {res.get('average_peer_count', 0):.1f}")
    print(f"Gini coefficient: {res.get('gini_coefficient', 0):.3f}")
    if res.get('isolated_nodes'):
        print(f"Isolated nodes:  {', '.join(res['isolated_nodes'][:5])}")

    # TX Relay V2
    v2 = report.get('tx_relay_v2_analysis', {})
    print("\n--- TX RELAY V2 ---")
    print(f"V1 messages: {v2.get('v1_message_count', 0)}")
    print(f"V2 hash announcements: {v2.get('v2_hash_announcement_count', 0)}")
    print(f"Health assessment: {v2.get('health_assessment', 'N/A')}")

    # Dandelion Analysis
    dan = report.get('dandelion_analysis', {})
    print("\n--- DANDELION++ ANALYSIS ---")
    print(f"Paths reconstructed: {dan.get('paths_reconstructed', 0)}")
    print(f"Average stem length: {dan.get('avg_stem_length', 0):.1f}")
    print(f"Stem length range:   {dan.get('min_stem_length', 0)} - {dan.get('max_stem_length', 0)}")
    print(f"Privacy score:       {dan.get('privacy_score', 0):.2f}")

    print("\n" + "=" * 70)


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Transaction Routing Analysis Tool for MoneroSim",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tx_analyzer.py full                    # Run all analyses
  python tx_analyzer.py spy-node               # Spy node analysis only
  python tx_analyzer.py propagation            # Propagation timing only
  python tx_analyzer.py dandelion --detailed   # Dandelion++ with all paths
  python tx_analyzer.py summary                # Quick summary stats
        """
    )

    parser.add_argument(
        'command',
        choices=['full', 'spy-node', 'propagation', 'resilience', 'relay-v2', 'dandelion', 'summary'],
        help="Analysis command to run"
    )

    parser.add_argument(
        '--shared-dir',
        default=DEFAULT_SHARED_DIR,
        help=f"Path to shared data directory (default: {DEFAULT_SHARED_DIR})"
    )

    parser.add_argument(
        '--shadow-data',
        default=DEFAULT_SHADOW_DATA,
        help=f"Path to Shadow data directory (default: {DEFAULT_SHADOW_DATA})"
    )

    parser.add_argument(
        '--output',
        '-o',
        help="Output file path for JSON report"
    )

    parser.add_argument(
        '--output-dir',
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for reports (default: {DEFAULT_OUTPUT_DIR})"
    )

    parser.add_argument(
        '--detailed',
        action='store_true',
        help="Include detailed per-transaction data in output"
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=None,
        help="Maximum parallel workers for log parsing"
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help="Output results as JSON only (no summary)"
    )

    args = parser.parse_args()

    # Load data
    print("Loading data...")
    agents, ip_to_node, node_to_ip = load_agent_registry(args.shared_dir)
    transactions = load_transactions(args.shared_dir)
    blocks = load_blocks(args.shared_dir)

    print(f"Loaded {len(agents)} agents, {len(transactions)} transactions, {len(blocks)} blocks")

    # Parse logs
    print("Parsing log files...")
    log_stats = parse_all_logs(args.shadow_data, args.max_workers)

    tx_observations = log_stats.get('tx_observations', [])
    connection_events = log_stats.get('connection_events', [])

    print(f"Found {len(tx_observations)} TX observations, {len(connection_events)} connection events")

    # Build metadata
    metadata = {
        'analysis_timestamp': datetime.now().isoformat(),
        'data_dir': args.shadow_data,
        'shared_dir': args.shared_dir,
        'total_nodes': len([a for a in agents.values() if a.daemon]),
        'total_transactions': len(transactions),
        'total_blocks': len(blocks)
    }

    # Run requested analyses
    spy_analysis = {}
    propagation_analysis = {}
    resilience_analysis = {}
    relay_v2_analysis = {}
    dandelion_analysis = {}

    if args.command in ('full', 'spy-node', 'summary'):
        print("Running spy node analysis...")
        spy_analysis = analyze_spy_node(tx_observations, transactions, ip_to_node, node_to_ip)
        if not args.detailed:
            spy_analysis.pop('tx_details', None)

    if args.command in ('full', 'propagation', 'summary'):
        print("Running propagation analysis...")
        propagation_analysis = analyze_propagation(tx_observations, transactions, blocks)
        if not args.detailed:
            propagation_analysis.pop('tx_propagation_details', None)

    if args.command in ('full', 'resilience', 'summary'):
        print("Running network resilience analysis...")
        resilience_analysis = analyze_network_resilience(connection_events, agents, ip_to_node)

    if args.command in ('full', 'relay-v2', 'summary'):
        print("Running TX Relay V2 analysis...")
        relay_v2_analysis = analyze_tx_relay_v2(log_stats)

    if args.command in ('full', 'dandelion', 'summary'):
        print("Running Dandelion++ analysis...")
        dandelion_analysis = analyze_dandelion_paths(tx_observations, transactions, ip_to_node, node_to_ip)
        if not args.detailed:
            dandelion_analysis['paths'] = dandelion_analysis.get('paths', [])[:5]  # Only show first 5

    # Generate report
    report = generate_report(
        spy_analysis,
        propagation_analysis,
        resilience_analysis,
        relay_v2_analysis,
        dandelion_analysis,
        metadata
    )

    # Output results
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_summary(report)

        # Save to file if requested
        output_path = args.output
        if not output_path:
            os.makedirs(args.output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(args.output_dir, f"tx_analysis_{timestamp}.json")

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report saved to: {output_path}")


if __name__ == "__main__":
    main()
