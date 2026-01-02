import os
import re
from collections import defaultdict
from pathlib import Path
import json
from typing import Dict, Set, Tuple, List
from glob import glob
import concurrent.futures
import threading
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.error_handling import log_info

# Define data structures
Block = Tuple[int, str]  # (height, hash)

# Constants
DEFAULT_MAX_WORKERS = 4
TIMESTAMP_PATTERN = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{3}\s*'


def parse_log_file(file_path: str) -> Dict[str, List]:
    """
    Parse a single log file for Monero events.
    Normalizes lines by stripping timestamp and normalizing spaces.
    Returns dict with keys: 'blocks_received', 'blocks_mined', 'tx_created', 'tx_received', 'tx_included', 'tx_in_pool'
    Each value is a list of relevant tuples or dicts.
    """
    events = defaultdict(list)

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        log_info("analyze_success_criteria", f"Error reading file {file_path}: {e}")
        return dict(events)

    normalized_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip timestamp prefix
        line = re.sub(TIMESTAMP_PATTERN, '', line)
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

        # Transaction created by this agent (from Python agent logs)
        # Pattern 1: regular_user - "Sent transaction: {...'tx_hash': 'abc123'...} to None for X XMR"
        # Pattern 2: miner_distributor - "Transaction sent successfully: abc123 from X to Y"
        tx_sent_match = re.search(r"Sent transaction:.*'tx_hash':\s*'([0-9a-f]{64})'", line, re.IGNORECASE)
        if not tx_sent_match:
            tx_sent_match = re.search(r"Transaction sent successfully:\s*([0-9a-f]{64})", line, re.IGNORECASE)
        if tx_sent_match:
            tx_hash = tx_sent_match.group(1)
            events['tx_created'].append(tx_hash)
            continue

        # Transaction added to pool (could be local or received - used for pool tracking)
        tx_pool_match = re.search(r'Transaction added to pool: txid <([0-9a-f]{64})>', line, re.IGNORECASE)
        if tx_pool_match:
            tx_hash = tx_pool_match.group(1)
            events['tx_in_pool'].append(tx_hash)
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


def analyze_simulation(log_dir: str = None, max_workers: int = DEFAULT_MAX_WORKERS) -> Dict:
    """
    Analyze all host logs in the directory using multi-threading.
    Returns aggregated data and success report.
    If log_dir is None, finds the most recent shadow.data/hosts directory.
    """
    if log_dir is None:
        workspace = Path('.')
        current_shadow_path = workspace / 'shadow.data' / 'hosts'
        if current_shadow_path.exists():
            log_path = current_shadow_path
        else:
            # Find the most recent dated shadow.data directory
            shadow_dirs = []
            for d in workspace.iterdir():
                if d.is_dir() and re.match(r'\d{8}', d.name):
                    shadow_path = d / 'shadow.data' / 'hosts'
                    if shadow_path.exists():
                        shadow_dirs.append((d.stat().st_mtime, shadow_path))
            if not shadow_dirs:
                raise ValueError("No shadow.data/hosts directory found in current workspace or dated subdirectories.")
            # Sort by modification time, take the most recent
            shadow_dirs.sort(reverse=True)
            log_path = shadow_dirs[0][1]
    else:
        log_path = Path(log_dir)
        # Handle case where user passes shadow.data instead of shadow.data/hosts
        if log_path.name == 'shadow.data' and (log_path / 'hosts').exists():
            log_path = log_path / 'hosts'
        if not log_path.exists():
            raise ValueError(f"Log directory {log_dir} not found.")

    log_info("analyze_simulation", f"Using log directory: {log_path}")

    node_data = {}
    all_blocks_mined = set()
    all_blocks_received = defaultdict(set)
    all_txs_created = set()
    all_txs_received = defaultdict(set)
    all_txs_included = defaultdict(set)  # tx_hash -> set of heights

    # Collect all log files to process
    log_files_to_process = []
    for host_dir in log_path.iterdir():
        if not host_dir.is_dir():
            continue
        host_name = host_dir.name

        # Find all bash.*.stdout files
        log_files = glob(str(host_dir / 'bash.*.stdout'))
        for log_file in log_files:
            log_files_to_process.append((host_name, log_file))

    # Process log files in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(parse_log_file, log_file): (host_name, log_file)
            for host_name, log_file in log_files_to_process
        }

        # Process results as they complete
        host_events = defaultdict(lambda: {'blocks_mined': set(), 'blocks_received': set(),
                                        'tx_created': set(), 'tx_received': set(), 'tx_included': {}})

        for future in concurrent.futures.as_completed(future_to_file):
            host_name, log_file = future_to_file[future]
            try:
                events = future.result()

                # Aggregate for this host
                host_events[host_name]['blocks_mined'].update(events.get('blocks_mined', []))
                host_events[host_name]['blocks_received'].update(events.get('blocks_received', []))
                host_events[host_name]['tx_created'].update(events.get('tx_created', []))
                host_events[host_name]['tx_received'].update(events.get('tx_received', []))
                for tx_h, height in events.get('tx_included', []):
                    if tx_h not in host_events[host_name]['tx_included']:
                        host_events[host_name]['tx_included'][tx_h] = set()
                    host_events[host_name]['tx_included'][tx_h].add(height)

            except Exception as exc:
                print(f'Error processing {log_file}: {exc}')

    # Global aggregation
    for host_name, events in host_events.items():
        all_blocks_mined.update(events['blocks_mined'])
        all_blocks_received[host_name] = events['blocks_received']
        all_txs_created.update(events['tx_created'])
        all_txs_received[host_name] = events['tx_received']
        for tx_h, heights in events['tx_included'].items():
            all_txs_included[tx_h].update(heights)

        node_data[host_name] = events

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
        'details': f"{len(all_blocks_mined)} blocks mined" if blocks_created else "No blocks mined"
    }

    # 2. Blocks propagated: Blocks are propagated to all user nodes
    user_blocks_received = {node: received for node, received in all_blocks_received.items() if node.startswith('user')}
    blocks_propagated = blocks_created and all(len(received) > 0 for received in user_blocks_received.values())
    report['criteria']['blocks_propagated'] = {
        'success': blocks_propagated,
        'details': f"{len(user_blocks_received)} user nodes received blocks" if blocks_propagated else "Not all user nodes received blocks"
    }

    # 3. Transactions created and broadcast: Transactions are created and broadcast to all user nodes
    txs_created_broadcast = len(all_txs_created) > 0
    user_txs_received = {node: received for node, received in all_txs_received.items() if node.startswith('user')}
    txs_propagated = txs_created_broadcast and all(len(received) > 0 for received in user_txs_received.values())
    report['criteria']['transactions_created_broadcast'] = {
        'success': txs_created_broadcast and txs_propagated,
        'details': f"{len(all_txs_created)} transactions created and propagated to {len(user_txs_received)} user nodes" if txs_created_broadcast and txs_propagated else "Transactions not properly created or propagated"
    }

    # 4. Transactions in blocks: All created txs are included in some block
    included_txs = set(all_txs_included.keys())
    txs_in_blocks = True  # True if no txs created
    if txs_created_broadcast:
        if not all_txs_created.issubset(included_txs):
            txs_in_blocks = False
    report['criteria']['transactions_in_blocks'] = {
        'success': txs_in_blocks,
        'details': f"{len(included_txs)}/{len(all_txs_created)} transactions included in blocks" if txs_created_broadcast else "No transactions created"
    }

    # Overall success
    overall_success = all(crit['success'] for crit in report['criteria'].values())
    report['overall_success'] = overall_success

    return {'node_data': node_data, 'report': report}


def generate_determinism_fingerprint(node_data: Dict, report: Dict) -> Dict:
    """
    Generate a determinism fingerprint that captures structural simulation behavior
    while ignoring non-deterministic elements like block/transaction hashes.

    This fingerprint can be compared across runs to verify determinism.
    """
    fingerprint = {
        'version': 1,  # Fingerprint format version
        'summary': {
            'num_nodes': report['num_nodes'],
            'total_blocks_mined': report['total_blocks_mined'],
            'total_txs_created': report['total_txs_created'],
            'total_txs_included': report['total_txs_included'],
        },
        'block_heights': {
            'mined': [],      # List of heights where blocks were mined
            'max_height': 0,  # Maximum block height achieved
        },
        'per_node_counts': {},  # Per-node event counts (sorted by node name)
        'propagation': {
            'blocks_propagated_to_all_users': report['criteria']['blocks_propagated']['success'],
            'txs_propagated_to_all_users': report['criteria']['transactions_created_broadcast']['success'],
        },
        'success_criteria': {
            criterion: data['success']
            for criterion, data in report['criteria'].items()
        },
        'overall_success': report['overall_success'],
    }

    # Extract block heights (ignoring hashes)
    all_heights_mined = set()
    all_heights_received = set()

    for node_name, events in sorted(node_data.items()):
        # Count events per node
        blocks_mined = events.get('blocks_mined', set())
        blocks_received = events.get('blocks_received', set())
        txs_created = events.get('tx_created', set())
        txs_received = events.get('tx_received', set())
        txs_included = events.get('tx_included', {})

        # Extract heights from block tuples (height, hash)
        mined_heights = [h for h, _ in blocks_mined] if blocks_mined else []
        received_heights = [h for h, _ in blocks_received] if blocks_received else []

        all_heights_mined.update(mined_heights)
        all_heights_received.update(received_heights)

        fingerprint['per_node_counts'][node_name] = {
            'blocks_mined': len(blocks_mined),
            'blocks_received': len(blocks_received),
            'txs_created': len(txs_created),
            'txs_received': len(txs_received),
            'txs_included': len(txs_included),
            'mined_heights': sorted(mined_heights),
            'max_height_seen': max(mined_heights + received_heights) if (mined_heights or received_heights) else 0,
        }

    # Aggregate block height info
    fingerprint['block_heights']['mined'] = sorted(all_heights_mined)
    fingerprint['block_heights']['max_height'] = max(all_heights_mined | all_heights_received) if (all_heights_mined or all_heights_received) else 0

    return fingerprint


def save_determinism_fingerprint(fingerprint: Dict, filename: str = None) -> str:
    """
    Save the determinism fingerprint to a JSON file.
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"determinism_fingerprint_{timestamp}.json"

    with open(filename, 'w') as f:
        json.dump(fingerprint, f, indent=2, sort_keys=True)

    print(f"Determinism fingerprint saved to: {filename}")
    return filename


def generate_summary_report(report: Dict) -> str:
    """
    Generate a clean summary report with less granular data.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary = []
    summary.append("Monerosim Simulation Success Analysis Report")
    summary.append("=" * 50)
    summary.append(f"Generated: {timestamp}")
    summary.append("")

    # Basic statistics
    summary.append("Simulation Overview:")
    summary.append(f"  Number of nodes analyzed: {report['num_nodes']}")
    summary.append(f"  Total blocks mined: {report['total_blocks_mined']}")
    summary.append(f"  Total unique transactions created: {report['total_txs_created']}")
    summary.append(f"  Total transactions included in blocks: {report['total_txs_included']}")
    summary.append("")

    # Success criteria
    summary.append("Success Criteria Results:")
    summary.append("")

    for criterion, data in report['criteria'].items():
        status = "PASS" if data['success'] else "FAIL"
        summary.append(f"  • {criterion.replace('_', ' ').title()}: {status}")
        summary.append(f"    {data['details']}")
        summary.append("")

    # Overall success
    summary.append("Overall Result:")
    overall_status = "SUCCESS" if report['overall_success'] else "FAILURE"
    summary.append(f"  {overall_status}")
    summary.append("")

    # Recommendations
    if not report['overall_success']:
        summary.append("Recommendations:")
        summary.append("  • Check network connectivity between nodes")
        summary.append("  • Verify mining configuration")
        summary.append("  • Ensure transaction broadcasting is working")
        summary.append("  • Check block propagation timing")

    return "\n".join(summary)


def save_summary_report(report: Dict, filename: str = None):
    """
    Save the summary report to a file.
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"simulation_summary_report_{timestamp}.txt"

    summary = generate_summary_report(report)

    with open(filename, 'w') as f:
        f.write(summary)

    print(f"Summary report saved to: {filename}")
    return filename


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Analyze Monerosim simulation results')
    parser.add_argument('--fingerprint-only', action='store_true',
                       help='Only generate determinism fingerprint (for comparison)')
    parser.add_argument('--fingerprint-file', type=str, default=None,
                       help='Output filename for determinism fingerprint')
    parser.add_argument('--log-dir', type=str, default=None,
                       help='Path to shadow.data/hosts directory')
    args = parser.parse_args()

    try:
        print("Starting simulation analysis with multi-threading support...")
        analysis = analyze_simulation(log_dir=args.log_dir, max_workers=DEFAULT_MAX_WORKERS)
        report = analysis['report']
        node_data = analysis['node_data']

        # Always generate determinism fingerprint
        fingerprint = generate_determinism_fingerprint(node_data, report)
        fingerprint_file = save_determinism_fingerprint(fingerprint, args.fingerprint_file)

        if args.fingerprint_only:
            # Only output fingerprint for determinism comparison
            return {
                'success': True,
                'fingerprint_file': fingerprint_file,
                'overall_success': report['overall_success']
            }

        # Print clean summary to console
        summary = generate_summary_report(report)
        print("\n" + summary)

        # Save summary report to file
        summary_file = save_summary_report(report)

        # Save detailed report to JSON (maintain existing functionality)
        with open('success_analysis_report.json', 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"\nDetailed report saved to success_analysis_report.json")

        return {
            'success': True,
            'summary_file': summary_file,
            'detailed_file': 'success_analysis_report.json',
            'fingerprint_file': fingerprint_file,
            'overall_success': report['overall_success']
        }

    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    main()