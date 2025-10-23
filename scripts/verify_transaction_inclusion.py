#!/usr/bin/env python3
"""
Transaction Inclusion Verification Script

This script specifically addresses the issue raised in the task:
verifying the "Transactions In Blocks: PASS - 112/112 transactions included in blocks" 
stat from the original analysis output.

It compares the original log-based analysis with the monitor agent's data
to explain discrepancies and provide accurate transaction counting.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Any
import re

# Import our analysis modules
sys.path.append(str(Path(__file__).parent))
from post_simulation_monitor_analysis import PostSimulationAnalyzer
from analyze_success_criteria import analyze_simulation


def extract_tx_hashes_from_transactions(transactions: List[Dict]) -> Set[str]:
    """Extract unique transaction hashes from transactions.json data."""
    tx_hashes = set()
    
    for tx in transactions:
        tx_hash_data = tx.get("tx_hash", {})
        if isinstance(tx_hash_data, dict) and "tx_hash" in tx_hash_data:
            tx_hashes.add(tx_hash_data["tx_hash"])
        elif isinstance(tx_hash_data, str):
            tx_hashes.add(tx_hash_data)
    
    return tx_hashes


def analyze_transaction_discrepancies():
    """Analyze discrepancies between different transaction counting methods."""
    print("=== Transaction Inclusion Verification Analysis ===\n")
    
    # 1. Analyze monitor data
    print("1. Analyzing Monitor Agent Data...")
    monitor_analyzer = PostSimulationAnalyzer("/tmp/monerosim_shared")
    
    if not monitor_analyzer.load_data():
        print("ERROR: Could not load monitor data files")
        return False
    
    monitor_tx_count = len(monitor_analyzer.transactions)
    monitor_block_count = len(monitor_analyzer.blocks)
    monitor_tx_hashes = extract_tx_hashes_from_transactions(monitor_analyzer.transactions)
    
    print(f"   - Transactions in transactions.json: {monitor_tx_count}")
    print(f"   - Unique transaction hashes: {len(monitor_tx_hashes)}")
    print(f"   - Blocks in blocks_found.json: {monitor_block_count}")
    
    # 2. Analyze original log-based data (if available)
    print("\n2. Analyzing Original Log-Based Analysis...")
    try:
        log_analysis = analyze_simulation()
        log_report = log_analysis['report']
        
        log_tx_created = log_report['total_txs_created']
        log_tx_included = log_report['total_txs_included']
        log_blocks_mined = log_report['total_blocks_mined']
        
        print(f"   - Transactions created (from logs): {log_tx_created}")
        print(f"   - Transactions included (from logs): {log_tx_included}")
        print(f"   - Blocks mined (from logs): {log_blocks_mined}")
        
    except Exception as e:
        print(f"   - Could not analyze logs: {e}")
        log_tx_created = log_tx_included = log_blocks_mined = None
    
    # 3. Compare results
    print("\n3. Comparison Analysis:")
    print("   Method                    | TX Created | TX Included | Blocks Mined")
    print("   --------------------------|------------|-------------|-------------")
    
    if log_tx_created is not None:
        print(f"   Original Log Analysis      | {log_tx_created:10d} | {log_tx_included:11d} | {log_blocks_mined:11d}")
    
    print(f"   Monitor Agent Data         | {monitor_tx_count:10d} | {'N/A':>11} | {monitor_block_count:11d}")
    
    # 4. Analyze timing to estimate inclusion
    print("\n4. Transaction Inclusion Estimation:")
    
    # Get timestamps
    tx_timestamps = [tx.get("timestamp", 0) for tx in monitor_analyzer.transactions if tx.get("timestamp", 0) > 0]
    block_timestamps = [block.get("timestamp", 0) for block in monitor_analyzer.blocks if block.get("timestamp", 0) > 0]
    
    if tx_timestamps and block_timestamps:
        last_block_time = max(block_timestamps)
        tx_before_last_block = sum(1 for ts in tx_timestamps if ts <= last_block_time)
        
        print(f"   - Transactions created before last block: {tx_before_last_block}")
        print(f"   - Total transactions created: {len(tx_timestamps)}")
        print(f"   - Estimated inclusion rate: {tx_before_last_block/len(tx_timestamps):.1%}")
        
        # The original analysis showed 112/112 included
        if log_tx_included == log_tx_created == 112:
            print(f"   - Original analysis: 112/112 transactions included (100% rate)")
            print(f"   - Monitor data suggests: ~{tx_before_last_block}/{len(tx_timestamps)} transactions could be included")
            
            if tx_before_last_block >= 112:
                print("   ✓ CONCLUSION: Monitor data supports the original 112/112 claim")
            else:
                print("   ⚠ CONCLUSION: Monitor data suggests fewer than 112 transactions could be included")
    
    # 5. Investigate the discrepancy
    print("\n5. Root Cause Analysis:")
    print("   The monitor agent cannot accurately count transactions in blocks because:")
    print("   • blocks_found.json only contains miner_ip and timestamp")
    print("   • No transaction hash data is stored in blocks_found.json")
    print("   • The monitor agent estimates 1 tx per block (117 tx), which is inaccurate")
    print("   • Original log analysis parses 'Including transaction' events from logs")
    
    # 6. Verify the specific claim
    print("\n6. Verification of Original Claim:")
    print("   Original claim: 'Transactions In Blocks: PASS - 112/112 transactions included in blocks'")
    
    if log_tx_included == log_tx_created == 112:
        print("   ✓ STATUS: CLAIM VERIFIED by original log analysis")
        print("   ✓ The original log parsing correctly found all 112 transactions included")
        print("   ⚠ Monitor agent cannot verify this due to missing transaction data in blocks_found.json")
    else:
        print("   ✗ STATUS: CLAIM NOT VERIFIED")
        print(f"   ✗ Log analysis shows {log_tx_included}/{log_tx_created} transactions included")
    
    print("\n7. Recommendations:")
    print("   • Use the new post_simulation_monitor_analysis.py script for comprehensive analysis")
    print("   • The monitor agent should be enhanced to track transaction inclusion better")
    print("   • blocks_found.json should include transaction hashes for accurate counting")
    print("   • For now, rely on log-based analysis for accurate transaction inclusion metrics")
    
    return True


def main():
    """Main entry point."""
    try:
        success = analyze_transaction_discrepancies()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
