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
    node_to_ip: Dict[str, str],
    agents: Dict[str, Agent] = None
) -> Dict:
    """
    Spy Node Analysis: Determine if a spy node could infer transaction originators.

    Methodology (matching Rust implementation):
    1. For each TX, sort observations by timestamp
    2. Look at early observations (first 5)
    3. Find the most common source_ip among early observations
    4. That's the inferred originator
    5. Compare against true sender IP
    6. Count correct inferences per TX (not per observation)

    This models a spy node that analyzes first-seen patterns to guess origins.
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

    # Track per-sender stats
    sender_stats = defaultdict(lambda: {'total': 0, 'correct': 0})

    for tx_hash, tx in transactions.items():
        observations = tx_obs_map.get(tx_hash, [])
        if not observations:
            continue

        results['analyzable_transactions'] += 1
        actual_sender = tx.sender_id
        actual_sender_ip = node_to_ip.get(actual_sender)

        # Calculate timing spread
        first_obs = observations[0]
        last_obs = observations[-1]
        timing_spread_ms = (last_obs['timestamp'] - first_obs['timestamp']) * 1000

        # Classify vulnerability based on timing spread
        if timing_spread_ms < HIGH_VULNERABILITY_THRESHOLD_MS:
            results['timing_distribution']['high_vulnerability_count'] += 1
            vulnerability = 'high'
        elif timing_spread_ms < MODERATE_VULNERABILITY_THRESHOLD_MS:
            results['timing_distribution']['moderate_vulnerability_count'] += 1
            vulnerability = 'moderate'
        else:
            results['timing_distribution']['low_vulnerability_count'] += 1
            vulnerability = 'low'

        # Infer originator: most common source_ip in early observations (first 5)
        early_count = min(5, len(observations))
        early_obs = observations[:early_count]

        source_ip_counts = defaultdict(int)
        for obs in early_obs:
            source_ip = obs.get('source_ip')
            if source_ip:
                source_ip_counts[source_ip] += 1

        # Find most common source_ip
        inferred_originator_ip = None
        if source_ip_counts:
            inferred_originator_ip = max(source_ip_counts.keys(), key=lambda ip: source_ip_counts[ip])

        # Check if inference is correct
        inference_correct = (inferred_originator_ip == actual_sender_ip) if (inferred_originator_ip and actual_sender_ip) else False

        if inference_correct:
            results['correct_inferences'] += 1

        # Track per-sender stats
        sender_stats[actual_sender]['total'] += 1
        if inference_correct:
            sender_stats[actual_sender]['correct'] += 1

        # Build first_seen_by for detailed output
        first_seen_by = []
        for obs in observations[:10]:
            first_seen_by.append({
                'node_id': obs['node_id'],
                'source_ip': obs.get('source_ip'),
                'delta_ms': round((obs['timestamp'] - first_obs['timestamp']) * 1000, 1)
            })

        results['tx_details'].append({
            'tx_hash': tx_hash[:16] + '...',
            'actual_sender': actual_sender,
            'actual_sender_ip': actual_sender_ip,
            'inferred_originator_ip': inferred_originator_ip,
            'inference_correct': inference_correct,
            'timing_spread_ms': round(timing_spread_ms, 1),
            'vulnerability': vulnerability,
            'first_seen_by': first_seen_by
        })

    # Calculate overall accuracy (per-TX, not per-observation)
    if results['analyzable_transactions'] > 0:
        results['inference_accuracy'] = round(
            results['correct_inferences'] / results['analyzable_transactions'], 3
        )

    # Convert sender_stats to list
    vulnerable_list = []
    for sender_id, stats in sender_stats.items():
        if stats['total'] > 0:
            vulnerable_list.append({
                'sender_id': sender_id,
                'total_txs': stats['total'],
                'correct_inferences': stats['correct'],
                'accuracy': round(stats['correct'] / stats['total'], 3)
            })
    vulnerable_list.sort(key=lambda x: x['accuracy'], reverse=True)
    results['vulnerable_senders'] = vulnerable_list

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
    ip_to_node: Dict[str, str],
    tx_observations: List[Dict] = None,
    transactions: Dict[str, Transaction] = None
) -> Dict:
    """
    Network Resilience Analysis: Analyze connectivity and centralization.

    Methodology (matching Rust implementation):
    1. Track connection state by connection_id (add on NEW, remove on CLOSE)
    2. Only count currently-active connections at end of simulation
    3. Calculate first-seen distribution for Gini coefficient
    """
    # Track active connections by (node_id, connection_id) -> peer_ip
    active_connections = {}  # (node_id, connection_id) -> peer_ip

    # Sort events by timestamp
    sorted_events = sorted(connection_events, key=lambda x: x['timestamp'])

    for event in sorted_events:
        node_id = event['node_id']
        conn_id = event.get('connection_id', f"{event['peer_ip']}:{event['peer_port']}")
        conn_key = (node_id, conn_id)

        if event['event_type'] == 'NEW':
            active_connections[conn_key] = event['peer_ip']
        elif event['event_type'] == 'CLOSE':
            active_connections.pop(conn_key, None)

    # Build peer sets from ACTIVE connections only
    node_peers = defaultdict(set)
    for (node_id, conn_id), peer_ip in active_connections.items():
        peer_node = ip_to_node.get(peer_ip)
        if peer_node:
            node_peers[node_id].add(peer_node)

    # Calculate peer counts from active connections
    peer_counts = {node_id: len(peers) for node_id, peers in node_peers.items()}

    # Find isolated nodes (no peers)
    daemon_nodes = {a.id for a in agents.values() if a.daemon}
    connected_nodes = set(node_peers.keys())
    isolated_nodes = list(daemon_nodes - connected_nodes)

    # Calculate Gini coefficient of peer counts
    if peer_counts:
        counts = list(peer_counts.values())
        peer_gini = calculate_gini(counts)
    else:
        peer_gini = 0.0

    # ===== TX First-Seen Distribution Analysis =====
    # Count how often each node is the first to see a TX (excluding originators)
    first_seen_counts = defaultdict(int)
    relay_counts = defaultdict(int)

    if tx_observations and transactions:
        # Group observations by TX hash
        tx_obs_map = defaultdict(list)
        for obs in tx_observations:
            tx_obs_map[obs['tx_hash']].append(obs)

        for tx_hash, obs_list in tx_obs_map.items():
            if not obs_list:
                continue

            # Sort by timestamp
            obs_list.sort(key=lambda x: x['timestamp'])

            # Get originator if known
            originator = None
            if tx_hash in transactions:
                originator = transactions[tx_hash].sender_id

            # First observer (non-originator) that sees this TX
            for obs in obs_list:
                node_id = obs['node_id']
                if node_id != originator:
                    first_seen_counts[node_id] += 1
                    break

            # Count relay participation for each node
            seen_nodes = set()
            for obs in obs_list:
                node_id = obs['node_id']
                if node_id not in seen_nodes:
                    relay_counts[node_id] += 1
                    seen_nodes.add(node_id)

    # Calculate Gini coefficient on first-seen distribution
    if first_seen_counts:
        first_seen_values = list(first_seen_counts.values())
        first_seen_gini = calculate_gini(first_seen_values)
    else:
        first_seen_gini = 0.0

    # Identify critical nodes based on multiple factors
    critical_nodes = []
    for node_id in daemon_nodes:
        peer_count = peer_counts.get(node_id, 0)
        first_seen = first_seen_counts.get(node_id, 0)
        relay_count = relay_counts.get(node_id, 0)

        # Score based on multiple factors
        # Higher score = more critical to network
        score = (
            peer_count * 0.3 +  # More peers = more critical
            first_seen * 2.0 +  # Frequently first to see = well-positioned
            relay_count * 0.5   # High relay participation
        )

        if score > 0:
            critical_nodes.append({
                'node_id': node_id,
                'peer_count': peer_count,
                'first_seen_count': first_seen,
                'relay_count': relay_count,
                'criticality_score': round(score, 1)
            })

    critical_nodes.sort(key=lambda x: x['criticality_score'], reverse=True)

    # First-seen distribution stats
    first_seen_stats = {}
    if first_seen_counts:
        values = list(first_seen_counts.values())
        first_seen_stats = {
            'total_first_seen_events': sum(values),
            'nodes_with_first_seen': len(values),
            'max_first_seen': max(values),
            'avg_first_seen': round(statistics.mean(values), 1),
            'gini_coefficient': round(first_seen_gini, 3)
        }

    results = {
        'total_daemon_nodes': len(daemon_nodes),
        'connected_nodes': len(connected_nodes),
        'isolated_nodes': isolated_nodes,
        'average_peer_count': round(statistics.mean(peer_counts.values()), 1) if peer_counts else 0,
        'median_peer_count': round(statistics.median(peer_counts.values()), 1) if peer_counts else 0,
        'max_peer_count': max(peer_counts.values()) if peer_counts else 0,
        'min_peer_count': min(peer_counts.values()) if peer_counts else 0,
        'peer_gini_coefficient': round(peer_gini, 3),
        'gini_coefficient': round(first_seen_gini, 3) if first_seen_counts else round(peer_gini, 3),
        'first_seen_distribution': first_seen_stats,
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
    node_to_ip: Dict[str, str],
    agents: Dict[str, Agent] = None
) -> Dict:
    """
    Dandelion++ Stem Path Reconstruction.

    Methodology (matching Rust implementation):
    1. Find first observation that came from the originator
    2. Follow chain: next = observation where source_ip matches current node's IP
    3. Fluff detection: if ≥3 nodes received from same sender within 100ms window
    4. Stop when fluff detected or no more observations
    5. Track used observations by index (not by node)
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
        'originator_confirmed_count': 0,
        'avg_stem_length': 0.0,
        'min_stem_length': 0,
        'max_stem_length': 0,
        'avg_stem_duration_ms': 0.0,
        'avg_hop_delay_ms': 0.0,
        'frequent_fluff_points': {},
        'node_stats': defaultdict(lambda: {
            'stem_relay_count': 0,
            'fluff_point_count': 0,
            'originator_count': 0,
            'positions': []
        }),
        'paths': []
    }

    stem_lengths = []
    stem_durations = []
    fluff_point_counts = defaultdict(int)

    for tx_hash, tx in transactions.items():
        observations = tx_obs_map.get(tx_hash, [])
        if not observations:
            continue

        originator = tx.sender_id
        originator_ip = node_to_ip.get(originator)

        # Reconstruct path using Rust methodology
        path_result = reconstruct_single_path(
            tx, observations, ip_to_node, node_to_ip, originator, originator_ip
        )

        if path_result:
            results['paths_reconstructed'] += 1
            stem_lengths.append(path_result['stem_length'])
            if path_result['stem_duration_ms'] > 0:
                stem_durations.append(path_result['stem_duration_ms'])

            if path_result.get('originator_confirmed'):
                results['originator_confirmed_count'] += 1

            # Update node stats
            results['node_stats'][originator]['originator_count'] += 1

            for i, hop in enumerate(path_result['stem_path']):
                node_id = hop['node_id'] if isinstance(hop, dict) else hop
                if i > 0:  # Not the first hop (which is from originator)
                    results['node_stats'][node_id]['stem_relay_count'] += 1
                    results['node_stats'][node_id]['positions'].append(i)

            if path_result.get('fluff_node'):
                fluff_node = path_result['fluff_node']
                results['node_stats'][fluff_node]['fluff_point_count'] += 1
                fluff_point_counts[fluff_node] += 1

            results['paths'].append(path_result)

    # Calculate aggregate statistics
    if stem_lengths:
        results['avg_stem_length'] = round(statistics.mean(stem_lengths), 1)
        results['min_stem_length'] = min(stem_lengths)
        results['max_stem_length'] = max(stem_lengths)

    if stem_durations:
        results['avg_stem_duration_ms'] = round(statistics.mean(stem_durations), 1)
        # Calculate average hop delay
        total_hops = sum(max(0, l - 1) for l in stem_lengths)
        if total_hops > 0:
            results['avg_hop_delay_ms'] = round(sum(stem_durations) / total_hops, 1)

    # Frequent fluff points
    results['frequent_fluff_points'] = dict(sorted(
        [(k, v) for k, v in fluff_point_counts.items() if v >= 2],
        key=lambda x: x[1], reverse=True
    )[:10])

    # Privacy score (based on avg stem length)
    if results['avg_stem_length'] >= 10:
        results['privacy_score'] = 1.0
    elif results['avg_stem_length'] >= 5:
        results['privacy_score'] = round(results['avg_stem_length'] / 10, 2)
    else:
        results['privacy_score'] = round(results['avg_stem_length'] / 10, 2)

    return results


def reconstruct_single_path(
    tx: Transaction,
    observations: List[Dict],
    ip_to_node: Dict[str, str],
    node_to_ip: Dict[str, str],
    originator: str,
    originator_ip: Optional[str]
) -> Optional[Dict]:
    """
    Reconstruct stem path for a single transaction (matching Rust methodology).

    The stem path is a chain: originator -> A -> B -> C -> fluff
    Each node receives from the previous, then relays to exactly one next node.
    Fluff point is where a node broadcasts to multiple peers simultaneously.
    """
    if not observations:
        return None

    # Sorted observations (already sorted by caller, but ensure)
    sorted_obs = sorted(observations, key=lambda x: x['timestamp'])

    stem_path = []
    used_observations = set()  # Track by index like Rust
    fluff_node = None
    fluff_recipients = 0
    current_sender_ip = originator_ip

    # Find first observation that came from the originator
    first_hop_idx = None
    for i, obs in enumerate(sorted_obs):
        if originator_ip and obs.get('source_ip') == originator_ip:
            first_hop_idx = i
            break

    if first_hop_idx is not None:
        # Start from first hop (received from originator)
        first_obs = sorted_obs[first_hop_idx]
        stem_path.append({
            'node_id': first_obs['node_id'],
            'from_node_id': originator,
            'from_ip': first_obs.get('source_ip'),
            'timestamp': first_obs['timestamp'],
            'delta_ms': 0.0
        })
        used_observations.add(first_hop_idx)
        current_sender_ip = node_to_ip.get(first_obs['node_id'])
    else:
        # Originator not found, start from first observation
        first_obs = sorted_obs[0]
        from_node = ip_to_node.get(first_obs.get('source_ip', ''))
        stem_path.append({
            'node_id': first_obs['node_id'],
            'from_node_id': from_node,
            'from_ip': first_obs.get('source_ip'),
            'timestamp': first_obs['timestamp'],
            'delta_ms': 0.0
        })
        used_observations.add(0)
        current_sender_ip = node_to_ip.get(first_obs['node_id'])

    first_timestamp = stem_path[0]['timestamp']

    # Follow the chain
    max_iterations = 100
    for _ in range(max_iterations):
        if not current_sender_ip:
            break

        # Find all observations from current sender that haven't been used
        from_current = [
            (i, obs) for i, obs in enumerate(sorted_obs)
            if i not in used_observations and obs.get('source_ip') == current_sender_ip
        ]

        if not from_current:
            break

        # Check for fluff: multiple nodes received from same sender within time window
        if len(from_current) >= FLUFF_MIN_RECEIVERS:
            first_time = from_current[0][1]['timestamp']
            recipients_in_window = sum(
                1 for (_, obs) in from_current
                if (obs['timestamp'] - first_time) * 1000 <= FLUFF_DETECTION_THRESHOLD_MS
            )

            if recipients_in_window >= FLUFF_MIN_RECEIVERS:
                # This is the fluff point
                fluff_node = stem_path[-1]['node_id'] if stem_path else None
                fluff_recipients = len(from_current)
                break

        # Single relay (stem phase) - take the earliest
        next_idx, next_obs = from_current[0]
        prev_timestamp = stem_path[-1]['timestamp'] if stem_path else next_obs['timestamp']

        stem_path.append({
            'node_id': next_obs['node_id'],
            'from_node_id': ip_to_node.get(current_sender_ip),
            'from_ip': current_sender_ip,
            'timestamp': next_obs['timestamp'],
            'delta_ms': round((next_obs['timestamp'] - first_timestamp) * 1000, 1)
        })

        used_observations.add(next_idx)
        current_sender_ip = node_to_ip.get(next_obs['node_id'])

    # If no fluff detected, last node in stem is likely the fluff point
    if fluff_node is None and stem_path:
        fluff_node = stem_path[-1]['node_id']
        fluff_recipients = len(sorted_obs) - len(used_observations)

    # Check if originator is confirmed
    originator_confirmed = False
    if stem_path and stem_path[0].get('from_node_id') == originator:
        originator_confirmed = True

    stem_length = len(stem_path)
    stem_duration_ms = 0.0
    if len(stem_path) >= 2:
        stem_duration_ms = (stem_path[-1]['timestamp'] - stem_path[0]['timestamp']) * 1000

    return {
        'tx_hash': tx.tx_hash,
        'originator': originator,
        'originator_ip': originator_ip,
        'stem_path': stem_path,
        'fluff_node': fluff_node,
        'stem_length': stem_length,
        'stem_duration_ms': round(stem_duration_ms, 1),
        'fluff_recipients': fluff_recipients,
        'originator_confirmed': originator_confirmed
    }


# ============================================================================
# Time Windowing and Upgrade Analysis
# ============================================================================

@dataclass
class TimeWindow:
    """A time window for segmented analysis."""
    start: float
    end: float
    label: Optional[str] = None

    def contains(self, timestamp: float) -> bool:
        """Check if timestamp falls within this window."""
        return self.start <= timestamp < self.end

    def duration(self) -> float:
        """Return duration of window in seconds."""
        return self.end - self.start


@dataclass
class WindowedMetrics:
    """Metrics calculated for a single time window."""
    window: TimeWindow
    tx_count: int = 0
    observation_count: int = 0
    spy_accuracy: Optional[float] = None
    avg_propagation_ms: Optional[float] = None
    median_propagation_ms: Optional[float] = None
    avg_peer_count: Optional[float] = None
    gini_coefficient: Optional[float] = None
    avg_stem_length: Optional[float] = None


def create_time_windows(start: float, end: float, window_size_sec: float) -> List[TimeWindow]:
    """Create time windows spanning the simulation duration."""
    windows = []
    current = start
    index = 0

    while current < end:
        window_end = min(current + window_size_sec, end)
        windows.append(TimeWindow(
            start=current,
            end=window_end,
            label=f"window_{index}"
        ))
        current = window_end
        index += 1

    return windows


def find_simulation_time_range(tx_observations: List[Dict], connection_events: List[Dict]) -> Tuple[float, float]:
    """Find the time range of all observations."""
    all_timestamps = []

    for obs in tx_observations:
        all_timestamps.append(obs['timestamp'])

    for event in connection_events:
        all_timestamps.append(event['timestamp'])

    if not all_timestamps:
        return (0.0, 0.0)

    return (min(all_timestamps), max(all_timestamps))


def filter_observations_by_window(observations: List[Dict], window: TimeWindow) -> List[Dict]:
    """Filter observations to those within a time window."""
    return [obs for obs in observations if window.contains(obs['timestamp'])]


def filter_transactions_by_window(transactions: Dict[str, Transaction], window: TimeWindow) -> Dict[str, Transaction]:
    """Filter transactions to those created within a time window."""
    return {
        tx_hash: tx for tx_hash, tx in transactions.items()
        if window.contains(tx.timestamp)
    }


def load_upgrade_manifest(manifest_path: str) -> Optional[Dict]:
    """Load upgrade manifest from JSON file."""
    try:
        with open(manifest_path, 'r') as f:
            data = json.load(f)

        manifest = {
            'pre_upgrade_version': data.get('pre_upgrade_version'),
            'post_upgrade_version': data.get('post_upgrade_version'),
            'node_upgrades': [],
            'upgrade_start': None,
            'upgrade_end': None,
        }

        for upgrade in data.get('upgrades', []):
            manifest['node_upgrades'].append({
                'node_id': upgrade.get('node_id'),
                'timestamp': upgrade.get('timestamp'),
                'version': upgrade.get('version', 'unknown'),
            })

        if manifest['node_upgrades']:
            timestamps = [u['timestamp'] for u in manifest['node_upgrades']]
            manifest['upgrade_start'] = min(timestamps)
            manifest['upgrade_end'] = max(timestamps)

        return manifest
    except Exception as e:
        print(f"Warning: Could not load upgrade manifest: {e}", file=sys.stderr)
        return None


def label_windows_by_upgrade(windows: List[TimeWindow], manifest: Optional[Dict]) -> None:
    """Label windows based on upgrade manifest timing."""
    if not manifest:
        return

    upgrade_start = manifest.get('upgrade_start', float('inf'))
    upgrade_end = manifest.get('upgrade_end', float('inf'))

    for window in windows:
        if window.end <= upgrade_start:
            window.label = 'pre-upgrade'
        elif window.start >= upgrade_end:
            window.label = 'post-upgrade'
        else:
            window.label = 'transition'


def calculate_window_metrics(
    window: TimeWindow,
    tx_observations: List[Dict],
    transactions: Dict[str, Transaction],
    connection_events: List[Dict],
    agents: Dict[str, Agent],
    ip_to_node: Dict[str, str],
    node_to_ip: Dict[str, str]
) -> WindowedMetrics:
    """Calculate all metrics for a single time window."""
    # Filter data to window
    window_obs = filter_observations_by_window(tx_observations, window)
    window_txs = filter_transactions_by_window(transactions, window)
    window_connections = filter_observations_by_window(connection_events, window)

    metrics = WindowedMetrics(
        window=window,
        tx_count=len(window_txs),
        observation_count=len(window_obs)
    )

    if not window_txs or not window_obs:
        return metrics

    # Spy accuracy
    spy_result = analyze_spy_node(window_obs, window_txs, ip_to_node, node_to_ip, agents)
    if spy_result.get('analyzable_transactions', 0) > 0:
        metrics.spy_accuracy = spy_result.get('inference_accuracy')

    # Propagation
    prop_result = analyze_propagation(window_obs, window_txs, [])
    if prop_result.get('average_propagation_ms', 0) > 0:
        metrics.avg_propagation_ms = prop_result.get('average_propagation_ms')
        metrics.median_propagation_ms = prop_result.get('median_propagation_ms')

    # Resilience (peer count and Gini)
    if connection_events:
        resilience_result = analyze_network_resilience(
            connection_events, agents, ip_to_node, window_obs, window_txs
        )
        metrics.avg_peer_count = resilience_result.get('average_peer_count')
        metrics.gini_coefficient = resilience_result.get('gini_coefficient')

    # Dandelion stem length
    dandelion_result = analyze_dandelion_paths(window_obs, window_txs, ip_to_node, node_to_ip, agents)
    if dandelion_result.get('paths_reconstructed', 0) > 0:
        metrics.avg_stem_length = dandelion_result.get('avg_stem_length')

    return metrics


def welch_t_test(sample1: List[float], sample2: List[float]) -> Optional[float]:
    """
    Perform Welch's t-test to compare two samples.
    Returns approximate p-value (using normal approximation for large samples).
    """
    if len(sample1) < 2 or len(sample2) < 2:
        return None

    n1 = len(sample1)
    n2 = len(sample2)

    mean1 = statistics.mean(sample1)
    mean2 = statistics.mean(sample2)

    var1 = statistics.variance(sample1)
    var2 = statistics.variance(sample2)

    se = (var1 / n1 + var2 / n2) ** 0.5
    if se == 0:
        return None

    t = abs(mean1 - mean2) / se

    # Welch-Satterthwaite degrees of freedom
    df_num = (var1 / n1 + var2 / n2) ** 2
    df_denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
    if df_denom == 0:
        return None
    df = df_num / df_denom

    # Use normal approximation for p-value (conservative for small df)
    import math
    p = 2.0 * (1.0 - standard_normal_cdf(t * (0.9 if df <= 30 else 1.0)))

    return p


def standard_normal_cdf(x: float) -> float:
    """Approximate standard normal CDF (Abramowitz and Stegun)."""
    import math
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = -1.0 if x < 0 else 1.0
    x = abs(x) / math.sqrt(2)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 0.5 * (1.0 + sign * y)


def create_period_summary(windows: List[WindowedMetrics], label: str) -> Dict:
    """Create aggregated summary for a period."""
    filtered = [w for w in windows if w.window.label == label]

    if not filtered:
        return None

    def extract_values(attr: str) -> List[float]:
        return [getattr(w, attr) for w in filtered if getattr(w, attr) is not None]

    spy_values = extract_values('spy_accuracy')
    prop_values = extract_values('avg_propagation_ms')
    peer_values = extract_values('avg_peer_count')
    gini_values = extract_values('gini_coefficient')
    stem_values = extract_values('avg_stem_length')

    return {
        'period_label': label,
        'start': min(w.window.start for w in filtered),
        'end': max(w.window.end for w in filtered),
        'window_count': len(filtered),
        'total_txs': sum(w.tx_count for w in filtered),
        'mean_spy_accuracy': statistics.mean(spy_values) if spy_values else None,
        'mean_propagation_ms': statistics.mean(prop_values) if prop_values else None,
        'mean_peer_count': statistics.mean(peer_values) if peer_values else None,
        'mean_gini': statistics.mean(gini_values) if gini_values else None,
        'mean_stem_length': statistics.mean(stem_values) if stem_values else None,
    }


def compare_periods(pre_summary: Dict, post_summary: Dict, windowed_metrics: List[WindowedMetrics]) -> List[Dict]:
    """Compare pre-upgrade and post-upgrade metrics."""
    if not pre_summary or not post_summary:
        return []

    changes = []

    metric_pairs = [
        ('mean_spy_accuracy', 'Spy Node Accuracy'),
        ('mean_propagation_ms', 'Avg Propagation (ms)'),
        ('mean_peer_count', 'Avg Peer Count'),
        ('mean_gini', 'Gini Coefficient'),
        ('mean_stem_length', 'Avg Stem Length'),
    ]

    for attr, name in metric_pairs:
        pre_val = pre_summary.get(attr)
        post_val = post_summary.get(attr)

        if pre_val is None or post_val is None:
            continue

        # Calculate percent change
        if pre_val != 0:
            pct_change = ((post_val - pre_val) / abs(pre_val)) * 100
        else:
            pct_change = 0 if post_val == 0 else 100

        # Get samples for statistical test
        pre_windows = [w for w in windowed_metrics if w.window.label == 'pre-upgrade']
        post_windows = [w for w in windowed_metrics if w.window.label == 'post-upgrade']

        pre_samples = [getattr(w, attr.replace('mean_', '')) for w in pre_windows
                       if getattr(w, attr.replace('mean_', ''), None) is not None]
        post_samples = [getattr(w, attr.replace('mean_', '')) for w in post_windows
                        if getattr(w, attr.replace('mean_', ''), None) is not None]

        p_value = welch_t_test(pre_samples, post_samples)
        significant = p_value is not None and p_value < 0.05

        # Generate interpretation
        interpretation = generate_interpretation(name, pct_change, significant)

        changes.append({
            'metric_name': name,
            'pre_value': round(pre_val, 4),
            'post_value': round(post_val, 4),
            'percent_change': round(pct_change, 2),
            'p_value': round(p_value, 4) if p_value else None,
            'statistically_significant': significant,
            'interpretation': interpretation,
        })

    return changes


def generate_interpretation(metric_name: str, pct_change: float, significant: bool) -> str:
    """Generate human-readable interpretation of a metric change."""
    if not significant:
        return f"No significant change in {metric_name.lower()}"

    direction = "increased" if pct_change > 0 else "decreased"
    magnitude = abs(pct_change)

    if 'propagation' in metric_name.lower():
        if pct_change < 0:
            return f"Transaction propagation improved by {magnitude:.1f}% (faster)"
        else:
            return f"Transaction propagation degraded by {magnitude:.1f}% (slower)"

    elif 'spy' in metric_name.lower() or 'accuracy' in metric_name.lower():
        if pct_change < 0:
            return f"Privacy improved: spy accuracy decreased by {magnitude:.1f}%"
        else:
            return f"Privacy concern: spy accuracy increased by {magnitude:.1f}%"

    elif 'peer' in metric_name.lower():
        return f"Network connectivity {direction} by {magnitude:.1f}%"

    elif 'gini' in metric_name.lower():
        if pct_change < 0:
            return f"Network decentralization improved (Gini decreased by {magnitude:.1f}%)"
        else:
            return f"Network more centralized (Gini increased by {magnitude:.1f}%)"

    elif 'stem' in metric_name.lower():
        return f"Average stem length {direction} by {magnitude:.1f}%"

    return f"{metric_name} {direction} by {magnitude:.1f}%"


def generate_assessment(changes: List[Dict], pre_summary: Dict, post_summary: Dict) -> Dict:
    """Generate overall assessment of upgrade impact."""
    improved = sum(1 for c in changes if c['statistically_significant'] and
                   (('propagation' in c['metric_name'].lower() and c['percent_change'] < 0) or
                    ('spy' in c['metric_name'].lower() and c['percent_change'] < 0) or
                    ('peer' in c['metric_name'].lower() and c['percent_change'] > 0) or
                    ('gini' in c['metric_name'].lower() and c['percent_change'] < 0)))

    degraded = sum(1 for c in changes if c['statistically_significant'] and
                   (('propagation' in c['metric_name'].lower() and c['percent_change'] > 0) or
                    ('spy' in c['metric_name'].lower() and c['percent_change'] > 0) or
                    ('gini' in c['metric_name'].lower() and c['percent_change'] > 0)))

    unchanged = len(changes) - improved - degraded

    # Determine verdict
    if improved > 0 and degraded == 0:
        verdict = 'Positive'
    elif degraded > 0 and improved == 0:
        verdict = 'Negative'
    elif improved > 0 and degraded > 0:
        verdict = 'Mixed'
    elif not pre_summary or not post_summary:
        verdict = 'Inconclusive'
    else:
        verdict = 'Neutral'

    # Generate findings
    findings = []
    for c in changes:
        if c['statistically_significant']:
            findings.append(c['interpretation'])

    # Identify concerns
    concerns = []
    for c in changes:
        if c['statistically_significant']:
            if 'spy' in c['metric_name'].lower() and c['percent_change'] > 0:
                concerns.append(f"Spy node accuracy increased by {abs(c['percent_change']):.1f}%")
            if 'propagation' in c['metric_name'].lower() and c['percent_change'] > 20:
                concerns.append(f"Propagation time increased significantly")
            if 'gini' in c['metric_name'].lower() and c['percent_change'] > 10:
                concerns.append(f"Network centralization increased")

    # Generate recommendations
    recommendations = []
    if degraded > 0:
        recommendations.append("Review upgrade changes that may have caused degradation")
    if not findings:
        recommendations.append("Consider longer simulation for more data points")
    if verdict == 'Positive':
        recommendations.append("Upgrade appears safe to deploy")

    return {
        'verdict': verdict,
        'metrics_improved': improved,
        'metrics_degraded': degraded,
        'metrics_unchanged': unchanged,
        'findings': findings,
        'concerns': concerns,
        'recommendations': recommendations,
    }


def analyze_upgrade_impact(
    tx_observations: List[Dict],
    transactions: Dict[str, Transaction],
    connection_events: List[Dict],
    agents: Dict[str, Agent],
    ip_to_node: Dict[str, str],
    node_to_ip: Dict[str, str],
    window_size_sec: float = 60.0,
    manifest_path: Optional[str] = None,
    pre_upgrade_end: Optional[float] = None,
    post_upgrade_start: Optional[float] = None
) -> Dict:
    """
    Analyze upgrade impact by comparing metrics across time windows.

    This divides the simulation into time windows, calculates metrics for each,
    and compares pre-upgrade vs post-upgrade periods.
    """
    # Find simulation time range
    sim_start, sim_end = find_simulation_time_range(tx_observations, connection_events)

    if sim_start == sim_end:
        return {'error': 'No data found'}

    # Create time windows
    windows = create_time_windows(sim_start, sim_end, window_size_sec)

    # Load upgrade manifest if provided
    manifest = None
    if manifest_path:
        manifest = load_upgrade_manifest(manifest_path)

    # Apply manual overrides
    if manifest is None and (pre_upgrade_end or post_upgrade_start):
        manifest = {
            'upgrade_start': pre_upgrade_end,
            'upgrade_end': post_upgrade_start,
            'node_upgrades': [],
        }
    elif manifest:
        if pre_upgrade_end:
            manifest['upgrade_start'] = pre_upgrade_end
        if post_upgrade_start:
            manifest['upgrade_end'] = post_upgrade_start

    # Label windows if manifest exists
    if manifest:
        label_windows_by_upgrade(windows, manifest)
    else:
        # Without manifest, use simple time-based split
        mid_point = (sim_start + sim_end) / 2
        for window in windows:
            if window.end <= mid_point:
                window.label = 'pre-upgrade'
            else:
                window.label = 'post-upgrade'

    # Calculate metrics for each window
    print(f"Calculating metrics for {len(windows)} time windows...")
    windowed_metrics = []
    for i, window in enumerate(windows):
        metrics = calculate_window_metrics(
            window, tx_observations, transactions, connection_events,
            agents, ip_to_node, node_to_ip
        )
        windowed_metrics.append(metrics)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(windows)} windows")

    # Create period summaries
    pre_summary = create_period_summary(windowed_metrics, 'pre-upgrade')
    post_summary = create_period_summary(windowed_metrics, 'post-upgrade')
    transition_summary = create_period_summary(windowed_metrics, 'transition')

    # Compare periods
    changes = compare_periods(pre_summary, post_summary, windowed_metrics)

    # Generate assessment
    assessment = generate_assessment(changes, pre_summary, post_summary)

    # Build time series for output
    time_series = []
    for m in windowed_metrics:
        time_series.append({
            'window': {
                'start': m.window.start,
                'end': m.window.end,
                'label': m.window.label,
            },
            'tx_count': m.tx_count,
            'observation_count': m.observation_count,
            'spy_accuracy': m.spy_accuracy,
            'avg_propagation_ms': m.avg_propagation_ms,
            'median_propagation_ms': m.median_propagation_ms,
            'avg_peer_count': m.avg_peer_count,
            'gini_coefficient': m.gini_coefficient,
            'avg_stem_length': m.avg_stem_length,
        })

    return {
        'metadata': {
            'analysis_timestamp': datetime.now().isoformat(),
            'simulation_start': sim_start,
            'simulation_end': sim_end,
            'window_size_sec': window_size_sec,
            'total_windows': len(windows),
            'total_transactions': len(transactions),
        },
        'upgrade_info': manifest,
        'time_series': time_series,
        'pre_upgrade_summary': pre_summary,
        'transition_summary': transition_summary,
        'post_upgrade_summary': post_summary,
        'changes': changes,
        'assessment': assessment,
    }


def print_upgrade_report(report: Dict):
    """Print upgrade analysis report to stdout."""
    print("\n" + "=" * 70)
    print("UPGRADE IMPACT ANALYSIS")
    print("=" * 70 + "\n")

    meta = report.get('metadata', {})
    print(f"Simulation Duration: {meta.get('simulation_start', 0):.1f}s - {meta.get('simulation_end', 0):.1f}s")
    print(f"Window Size: {meta.get('window_size_sec', 0):.0f}s ({meta.get('total_windows', 0)} windows)")
    print()

    # Upgrade info
    upgrade_info = report.get('upgrade_info')
    if upgrade_info:
        if upgrade_info.get('upgrade_start') and upgrade_info.get('upgrade_end'):
            print(f"Upgrade Period: {upgrade_info['upgrade_start']:.1f}s - {upgrade_info['upgrade_end']:.1f}s")
            print(f"Nodes Upgraded: {len(upgrade_info.get('node_upgrades', []))}")

    # Period summaries
    pre = report.get('pre_upgrade_summary')
    post = report.get('post_upgrade_summary')
    if pre and post:
        print()
        print(f"Pre-Upgrade Period: {pre['start']:.1f}s - {pre['end']:.1f}s ({pre['window_count']} windows)")
        print(f"Post-Upgrade Period: {post['start']:.1f}s - {post['end']:.1f}s ({post['window_count']} windows)")

    # Metric comparison
    changes = report.get('changes', [])
    if changes:
        print("\n" + "-" * 70)
        print("METRIC COMPARISON")
        print("-" * 70 + "\n")

        print(f"{'Metric':<25} | {'Pre-Upgrade':>12} | {'Post-Upgrade':>12} | {'Change':>10} | {'Sig?':>6}")
        print("-" * 25 + "-+-" + "-" * 12 + "-+-" + "-" * 12 + "-+-" + "-" * 10 + "-+-" + "-" * 6)

        for change in changes:
            sig = "YES *" if change['statistically_significant'] else "NO"

            if 'accuracy' in change['metric_name'].lower():
                pre_str = f"{change['pre_value'] * 100:.1f}%"
                post_str = f"{change['post_value'] * 100:.1f}%"
            elif 'propagation' in change['metric_name'].lower() or 'ms' in change['metric_name'].lower():
                pre_str = f"{change['pre_value']:.0f}ms"
                post_str = f"{change['post_value']:.0f}ms"
            elif 'gini' in change['metric_name'].lower():
                pre_str = f"{change['pre_value']:.3f}"
                post_str = f"{change['post_value']:.3f}"
            else:
                pre_str = f"{change['pre_value']:.1f}"
                post_str = f"{change['post_value']:.1f}"

            change_str = f"{change['percent_change']:+.1f}%"

            print(f"{change['metric_name']:<25} | {pre_str:>12} | {post_str:>12} | {change_str:>10} | {sig:>6}")

        print()
        print("* Statistically significant at p < 0.05")

    # Assessment
    assessment = report.get('assessment', {})
    print("\n" + "-" * 70)
    print("ASSESSMENT")
    print("-" * 70 + "\n")

    verdict_labels = {
        'Positive': 'POSITIVE - Upgrade improved network behavior',
        'Negative': 'NEGATIVE - Upgrade degraded network behavior',
        'Mixed': 'MIXED - Upgrade had mixed effects',
        'Neutral': 'NEUTRAL - No significant changes detected',
        'Inconclusive': 'INCONCLUSIVE - Insufficient data for assessment',
    }
    print(f"Verdict: {verdict_labels.get(assessment.get('verdict'), assessment.get('verdict', 'Unknown'))}")
    print()

    if assessment.get('findings'):
        print("Findings:")
        for finding in assessment['findings']:
            print(f"  - {finding}")
        print()

    if assessment.get('concerns'):
        print("Concerns:")
        for concern in assessment['concerns']:
            print(f"  - {concern}")
        print()

    if assessment.get('recommendations'):
        print("Recommendations:")
        for rec in assessment['recommendations']:
            print(f"  - {rec}")
        print()

    print("(See upgrade_analysis.json for full time-series data)")
    print()


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
  python tx_analyzer.py upgrade-analysis       # Compare pre/post upgrade metrics
  python tx_analyzer.py upgrade-analysis --window-size 30 --manifest upgrade.json
  python tx_analyzer.py upgrade-analysis --pre-upgrade-end 300 --post-upgrade-start 600
        """
    )

    parser.add_argument(
        'command',
        choices=['full', 'spy-node', 'propagation', 'resilience', 'relay-v2', 'dandelion', 'summary', 'upgrade-analysis'],
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

    # Upgrade analysis specific options
    parser.add_argument(
        '--window-size',
        type=int,
        default=60,
        help="Size of each time window in seconds (default: 60)"
    )

    parser.add_argument(
        '--manifest',
        type=str,
        default=None,
        help="Path to upgrade manifest JSON file"
    )

    parser.add_argument(
        '--pre-upgrade-end',
        type=float,
        default=None,
        help="Manual override: end of pre-upgrade period (simulation time in seconds)"
    )

    parser.add_argument(
        '--post-upgrade-start',
        type=float,
        default=None,
        help="Manual override: start of post-upgrade period (simulation time in seconds)"
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
        spy_analysis = analyze_spy_node(tx_observations, transactions, ip_to_node, node_to_ip, agents)
        if not args.detailed:
            spy_analysis.pop('tx_details', None)

    if args.command in ('full', 'propagation', 'summary'):
        print("Running propagation analysis...")
        propagation_analysis = analyze_propagation(tx_observations, transactions, blocks)
        if not args.detailed:
            propagation_analysis.pop('tx_propagation_details', None)

    if args.command in ('full', 'resilience', 'summary'):
        print("Running network resilience analysis...")
        resilience_analysis = analyze_network_resilience(
            connection_events, agents, ip_to_node, tx_observations, transactions
        )

    if args.command in ('full', 'relay-v2', 'summary'):
        print("Running TX Relay V2 analysis...")
        relay_v2_analysis = analyze_tx_relay_v2(log_stats)

    if args.command in ('full', 'dandelion', 'summary'):
        print("Running Dandelion++ analysis...")
        dandelion_analysis = analyze_dandelion_paths(tx_observations, transactions, ip_to_node, node_to_ip, agents)
        if not args.detailed:
            # Simplify paths for non-detailed output
            simplified_paths = []
            for path in dandelion_analysis.get('paths', [])[:5]:  # Only show first 5
                simplified_paths.append({
                    'tx_hash': path['tx_hash'][:16] + '...',
                    'originator': path['originator'],
                    'stem_path': [hop['node_id'] if isinstance(hop, dict) else hop for hop in path.get('stem_path', [])],
                    'fluff_node': path.get('fluff_node'),
                    'stem_length': path['stem_length'],
                    'stem_duration_ms': path['stem_duration_ms']
                })
            dandelion_analysis['paths'] = simplified_paths

    # Handle upgrade-analysis command separately
    if args.command == 'upgrade-analysis':
        print("Running upgrade impact analysis...")
        upgrade_report = analyze_upgrade_impact(
            tx_observations,
            transactions,
            connection_events,
            agents,
            ip_to_node,
            node_to_ip,
            window_size_sec=float(args.window_size),
            manifest_path=args.manifest,
            pre_upgrade_end=args.pre_upgrade_end,
            post_upgrade_start=args.post_upgrade_start
        )

        if args.json:
            print(json.dumps(upgrade_report, indent=2))
        else:
            print_upgrade_report(upgrade_report)

            # Save JSON report
            output_path = args.output
            if not output_path:
                os.makedirs(args.output_dir, exist_ok=True)
                output_path = os.path.join(args.output_dir, "upgrade_analysis.json")

            with open(output_path, 'w') as f:
                json.dump(upgrade_report, f, indent=2)
            print(f"Full report saved to: {output_path}")

        return  # Exit after upgrade analysis

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
