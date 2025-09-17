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

def parse_log_file_threaded(file_path: str) -> Dict[str, List]:
    """
    Thread-safe wrapper for parse_log_file.
    """
    return parse_log_file(file_path)

def analyze_simulation(log_dir: str = 'shadow.data/hosts', max_workers: int = 4) -> Dict:
    """
    Analyze all host logs in the directory using multi-threading.
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
            executor.submit(parse_log_file_threaded, log_file): (host_name, log_file)
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

    # 3. Transactions created and broadcast: Transactions are created and broadcast to all nodes
    txs_created_broadcast = len(all_txs_created) > 0
    txs_propagated = txs_created_broadcast and all(len(received) > 0 for received in all_txs_received.values())
    report['criteria']['transactions_created_broadcast'] = {
        'success': txs_created_broadcast and txs_propagated,
        'details': f"{len(all_txs_created)} transactions created and propagated" if txs_created_broadcast and txs_propagated else "Transactions not properly created or propagated"
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
    try:
        print("Starting simulation analysis with multi-threading support...")
        analysis = analyze_simulation(max_workers=4)
        report = analysis['report']
        
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
            'overall_success': report['overall_success']
        }
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    main()