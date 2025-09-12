import os
import re
from collections import defaultdict
from pathlib import Path
import json
from typing import Dict, Set, Tuple, List
from glob import glob

# Define data structures
Block = Tuple[int, str]  # (height, hash)

def parse_log_file(file_path: str) -> Dict[str, List]:
    """
    Parse a single log file for Monero events.
    Normalizes lines by stripping timestamp and normalizing spaces.
    Returns dict with keys: 'blocks_received', 'blocks_mined', 'tx_created', 'tx_received', 'tx_included'
    Each value is a list of relevant tuples or dicts.
    """
    events = defaultdict(list)
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    normalized_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip timestamp prefix
        line = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{3}\s*', '', line)
        # Normalize multiple spaces/tabs to single space
        line = re.sub(r'\s+', ' ', line).strip()
        normalized_lines.append(line)

    last_height = 0
    for i, line in enumerate(normalized_lines):
        # Block mined
        mined_match = re.search(r'mined new block.*height=(\d+).*hash=([0-9a-f]{64})', line, re.IGNORECASE)
        if mined_match:
            height, block_hash = int(mined_match.group(1)), mined_match.group(2)
            events['blocks_mined'].append((height, block_hash))
            last_height = height
            continue

        # Block received/propagated
        received_match = re.search(r'Received NOTIFY_NEW_FLUFFY_BLOCK <([0-9a-f]{64})> \(height (\d+),', line, re.IGNORECASE)
        if received_match:
            block_hash, height = received_match.group(1), int(received_match.group(2))
            events['blocks_received'].append((height, block_hash))
            last_height = height
            continue

        # Block added (+++++ BLOCK SUCCESSFULLY ADDED)
        if '+++++ BLOCK SUCCESSFULLY ADDED' in line:
            if i + 1 < len(normalized_lines):
                next_line = normalized_lines[i + 1]
                id_match = re.search(r'id: <([0-9a-f]{64})>', next_line, re.IGNORECASE)
                if id_match:
                    block_hash = id_match.group(1)
                    # Extract height from nearby lines
                    height = last_height
                    for j in range(i, min(i + 5, len(normalized_lines))):
                        height_match = re.search(r'HEIGHT (\d+)', normalized_lines[j], re.IGNORECASE)
                        if height_match:
                            height = int(height_match.group(1))
                            break
                    # Check for PoW in the current line or next 2 lines to determine if mined
                    pow_found = False
                    for j in range(i, min(i + 3, len(normalized_lines))):
                        if re.search(r'PoW: <([0-9a-f]{64})>', normalized_lines[j], re.IGNORECASE):
                            pow_found = True
                            break
                    if pow_found:
                        events['blocks_mined'].append((height, block_hash))
                    else:
                        events['blocks_received'].append((height, block_hash))
                    last_height = height
            continue

        # Transaction added to pool (created/received/broadcast)
        tx_pool_match = re.search(r'Transaction added to pool: txid <([0-9a-f]{64})>', line, re.IGNORECASE)
        if tx_pool_match:
            tx_hash = tx_pool_match.group(1)
            events['tx_created'].append(tx_hash)
            continue

        # Transaction received (NOTIFY_NEW_TRANSACTIONS)
        tx_notify_match = re.search(r'Received NOTIFY_NEW_TRANSACTIONS \((\d+) txes\)', line, re.IGNORECASE)
        if tx_notify_match:
            # Look for txid in nearby lines (within 5 lines before/after)
            for j in range(max(0, i-5), min(len(normalized_lines), i+6)):
                if j != i:
                    nearby_match = re.search(r'txid <([0-9a-f]{64})>', normalized_lines[j], re.IGNORECASE)
                    if nearby_match:
                        tx_hash = nearby_match.group(1)
                        events['tx_received'].append(tx_hash)
                        break
            continue

        # Transaction inclusion
        include_match = re.search(r'Including transaction <([0-9a-f]{64})>', line, re.IGNORECASE)
        if include_match:
            tx_hash = include_match.group(1)
            events['tx_included'].append((tx_hash, last_height))
            continue

    return dict(events)

def analyze_simulation(log_dir: str = 'shadow.data/hosts') -> Dict:
    """
    Analyze all host logs in the directory.
    Returns aggregated data and success report.
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        raise ValueError(f"Log directory {log_dir} not found.")

    node_data = {}
    all_blocks_mined = set()
    all_blocks_received = defaultdict(set)
    all_txs_created = set()
    all_txs_received = defaultdict(set)
    all_txs_included = defaultdict(set)  # tx_hash -> set of heights

    # Iterate over hosts
    for host_dir in log_path.iterdir():
        if not host_dir.is_dir():
            continue
        host_name = host_dir.name

        # Find all bash.*.stdout files
        log_files = glob(str(host_dir / 'bash.*.stdout'))

        node_events = {'blocks_mined': set(), 'blocks_received': set(), 'tx_created': set(), 'tx_received': set(), 'tx_included': {}}

        for log_file in log_files:
            events = parse_log_file(log_file)

            # Aggregate for this node
            node_events['blocks_mined'].update(events.get('blocks_mined', []))
            node_events['blocks_received'].update(events.get('blocks_received', []))
            node_events['tx_created'].update(events.get('tx_created', []))
            node_events['tx_received'].update(events.get('tx_received', []))
            for tx_h, height in events.get('tx_included', []):
                if tx_h not in node_events['tx_included']:
                    node_events['tx_included'][tx_h] = set()
                node_events['tx_included'][tx_h].add(height)

        # Global aggregation
        all_blocks_mined.update(node_events['blocks_mined'])
        all_blocks_received[host_name] = node_events['blocks_received']
        all_txs_created.update(node_events['tx_created'])
        all_txs_received[host_name] = node_events['tx_received']
        for tx_h, heights in node_events['tx_included'].items():
            all_txs_included[tx_h].update(heights)

        node_data[host_name] = node_events

    # Verify success criteria
    report = {
        'num_nodes': len(node_data),
        'total_blocks_mined': len(all_blocks_mined),
        'total_txs_created': len(all_txs_created),
        'total_txs_included': len(all_txs_included),
        'criteria': {}
    }

    # 1. Blocks created: At least one block mined
    blocks_created = len(all_blocks_mined) > 0
    report['criteria']['blocks_created'] = {
        'success': blocks_created,
        'details': list(all_blocks_mined) if blocks_created else 'No blocks mined'
    }

    # 2. Blocks propagated: Blocks are propagated to all user nodes
    user_blocks_received = {node: received for node, received in all_blocks_received.items() if node.startswith('user')}
    blocks_propagated = blocks_created and all(len(received) > 0 for received in user_blocks_received.values())
    report['criteria']['blocks_propagated'] = {
        'success': blocks_propagated,
        'details': {node: len(received) for node, received in user_blocks_received.items()}
    }

    # 3. Transactions created and broadcast: Transactions are created and broadcast to all nodes
    txs_created_broadcast = len(all_txs_created) > 0
    txs_propagated = txs_created_broadcast and all(len(received) > 0 for received in all_txs_received.values())
    report['criteria']['transactions_created_broadcast'] = {
        'success': txs_created_broadcast and txs_propagated,
        'details': {'total_created': len(all_txs_created), 'nodes_received': {node: len(recvd) for node, recvd in all_txs_received.items()}}
    }

    # 4. Transactions in blocks: All created txs are included in some block
    included_txs = set(all_txs_included.keys())
    txs_in_blocks = True  # True if no txs created
    if txs_created_broadcast:
        if not all_txs_created.issubset(included_txs):
            txs_in_blocks = False
    report['criteria']['transactions_in_blocks'] = {
        'success': txs_in_blocks,
        'details': {
            'included_txs': len(included_txs),
            'missing_txs': list(all_txs_created - included_txs) if txs_created_broadcast and not txs_in_blocks else []
        }
    }

    # Overall success
    overall_success = all(crit['success'] for crit in report['criteria'].values())
    report['overall_success'] = overall_success

    return {'node_data': node_data, 'report': report}

def main():
    try:
        analysis = analyze_simulation()
        print("Simulation Success Analysis Report")
        print("=" * 50)
        report = analysis['report']
        print(f"Number of nodes analyzed: {report['num_nodes']}")
        print(f"Total blocks mined: {report['total_blocks_mined']}")
        print(f"Total unique txs created: {report['total_txs_created']}")
        print(f"Total txs included in blocks: {report['total_txs_included']}")
        print(f"\nOverall Success: {'YES' if report['overall_success'] else 'NO'}")
        print("\nDetailed Criteria:")
        for criterion, data in report['criteria'].items():
            status = "PASS" if data['success'] else "FAIL"
            print(f"\n{criterion.replace('_', ' ').title()}: {status}")
            print(f"Details: {data['details']}")

        # Save report to JSON
        with open('success_analysis_report.json', 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print("\nFull report saved to success_analysis_report.json")

    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    main()