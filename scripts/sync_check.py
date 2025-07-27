#!/usr/bin/env python3
"""
sync_check.py - Synchronization verification script for MoneroSim

This script checks the synchronization status between Monero nodes in the Shadow simulation.
It verifies that nodes have synchronized their blockchains and are at the same height.

This is a Python implementation that replaces the bash sync_check.sh script.
"""

import sys
import time
import argparse
from typing import Optional, Tuple

# Import from error_handling and network_config modules
try:
    from error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_network_sync, handle_exit
    )
    from network_config import (
        A0_RPC, A1_RPC, get_daemon_config
    )
except ImportError:
    # Handle case where script is run from different directory
    sys.path.append('..')
    from scripts.error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_network_sync, handle_exit
    )
    from scripts.network_config import (
        A0_RPC, A1_RPC, get_daemon_config
    )

# Component name for logging
COMPONENT = "SYNC_CHECK"

# Default configuration
DEFAULT_MAX_ATTEMPTS = 30
DEFAULT_RETRY_DELAY = 2
DEFAULT_SYNC_THRESHOLD = 1  # Maximum allowed height difference
DEFAULT_SYNC_WAIT_TIME = 10  # Time to wait before checking sync


def get_node_info(daemon_url: str, daemon_name: str, max_attempts: int, 
                  retry_delay: float) -> Optional[Tuple[int, str, str]]:
    """
    Get node information including height, hash, and status.
    
    Args:
        daemon_url: URL of the daemon RPC endpoint
        daemon_name: Name of the daemon for logging
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        Tuple of (height, top_block_hash, status) or None if failed
    """
    log_info(COMPONENT, f"Getting {daemon_name} node information...")
    
    success, response = call_daemon_with_retry(
        daemon_url, "get_info", {}, max_attempts, retry_delay, COMPONENT
    )
    
    if not success:
        log_error(COMPONENT, f"Failed to get {daemon_name} node information")
        return None
    
    result = response.get("result", {})
    height = result.get("height", 0)
    top_block_hash = result.get("top_block_hash", "")
    status = result.get("status", "unknown")
    
    return height, top_block_hash, status


def check_synchronization(node1_url: str, node1_name: str,
                         node2_url: str, node2_name: str,
                         sync_threshold: int, max_attempts: int,
                         retry_delay: float) -> bool:
    """
    Check synchronization between two nodes.
    
    Args:
        node1_url: URL of the first node
        node1_name: Name of the first node
        node2_url: URL of the second node
        node2_name: Name of the second node
        sync_threshold: Maximum allowed height difference
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        True if nodes are synchronized, False otherwise
    """
    log_info(COMPONENT, f"Checking synchronization between {node1_name} and {node2_name}")
    log_info(COMPONENT, f"Maximum allowed height difference: {sync_threshold} blocks")
    
    # Get initial node information
    node1_info = get_node_info(node1_url, node1_name, max_attempts, retry_delay)
    node2_info = get_node_info(node2_url, node2_name, max_attempts, retry_delay)
    
    if not node1_info or not node2_info:
        log_critical(COMPONENT, "Failed to get initial node information")
        return False
    
    height1, hash1, status1 = node1_info
    height2, hash2, status2 = node2_info
    
    log_info(COMPONENT, f"{node1_name} - Height: {height1}, Hash: {hash1}, Status: {status1}")
    log_info(COMPONENT, f"{node2_name} - Height: {height2}, Hash: {hash2}, Status: {status2}")
    
    # Calculate initial height difference
    height_diff = abs(height1 - height2)
    log_info(COMPONENT, f"Initial height difference: {height_diff} blocks")
    
    # Use the verify_network_sync function from error_handling
    if verify_network_sync(node1_url, node2_url, sync_threshold, 
                          max_attempts, retry_delay, COMPONENT):
        log_success(COMPONENT, f"Nodes {node1_name} and {node2_name} are synchronized")
        
        # Get final state for reporting
        final_node1_info = get_node_info(node1_url, node1_name, 3, 2)
        final_node2_info = get_node_info(node2_url, node2_name, 3, 2)
        
        if final_node1_info and final_node2_info:
            final_height1, final_hash1, _ = final_node1_info
            final_height2, final_hash2, _ = final_node2_info
            
            log_info(COMPONENT, "Final synchronization state:")
            log_info(COMPONENT, f"  {node1_name}: Height={final_height1}, Hash={final_hash1}")
            log_info(COMPONENT, f"  {node2_name}: Height={final_height2}, Hash={final_hash2}")
            
            if final_hash1 == final_hash2:
                log_success(COMPONENT, "Nodes have identical blockchain tips")
            else:
                log_warning(COMPONENT, "Nodes are at same height but have different top block hashes")
        
        return True
    else:
        log_error(COMPONENT, f"Nodes {node1_name} and {node2_name} failed to synchronize")
        
        # Get final state for diagnostics
        final_node1_info = get_node_info(node1_url, node1_name, 3, 2)
        final_node2_info = get_node_info(node2_url, node2_name, 3, 2)
        
        if final_node1_info and final_node2_info:
            final_height1, final_hash1, _ = final_node1_info
            final_height2, final_hash2, _ = final_node2_info
            final_diff = abs(final_height1 - final_height2)
            
            log_error(COMPONENT, "Final synchronization state:")
            log_error(COMPONENT, f"  {node1_name}: Height={final_height1}, Hash={final_hash1}")
            log_error(COMPONENT, f"  {node2_name}: Height={final_height2}, Hash={final_hash2}")
            log_error(COMPONENT, f"  Height difference: {final_diff} blocks")
        
        return False


def main():
    """Main function for sync check script."""
    parser = argparse.ArgumentParser(
        description="Check synchronization between Monero nodes in Shadow simulation"
    )
    
    # Add command line arguments
    parser.add_argument(
        "--node1-url", 
        default=A0_RPC,
        help=f"URL of the first node (default: {A0_RPC})"
    )
    parser.add_argument(
        "--node1-name",
        default="A0",
        help="Name of the first node (default: A0)"
    )
    parser.add_argument(
        "--node2-url",
        default=A1_RPC,
        help=f"URL of the second node (default: {A1_RPC})"
    )
    parser.add_argument(
        "--node2-name",
        default="A1",
        help="Name of the second node (default: A1)"
    )
    parser.add_argument(
        "--sync-threshold",
        type=int,
        default=DEFAULT_SYNC_THRESHOLD,
        help=f"Maximum allowed height difference (default: {DEFAULT_SYNC_THRESHOLD})"
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Maximum number of attempts (default: {DEFAULT_MAX_ATTEMPTS})"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY,
        help=f"Delay between attempts in seconds (default: {DEFAULT_RETRY_DELAY})"
    )
    parser.add_argument(
        "--wait-time",
        type=int,
        default=DEFAULT_SYNC_WAIT_TIME,
        help=f"Time to wait before checking sync in seconds (default: {DEFAULT_SYNC_WAIT_TIME})"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously, checking sync status periodically"
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=30,
        help="Interval between checks in continuous mode (default: 30 seconds)"
    )
    
    args = parser.parse_args()
    
    log_info(COMPONENT, "=== MoneroSim Synchronization Check ===")
    log_info(COMPONENT, f"Starting sync check at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Wait before checking if requested
    if args.wait_time > 0:
        log_info(COMPONENT, f"Waiting {args.wait_time} seconds before checking synchronization...")
        time.sleep(args.wait_time)
    
    if args.continuous:
        # Continuous mode - keep checking sync status
        log_info(COMPONENT, "Running in continuous mode")
        check_count = 0
        
        try:
            while True:
                check_count += 1
                log_info(COMPONENT, f"--- Sync check #{check_count} ---")
                
                sync_ok = check_synchronization(
                    args.node1_url, args.node1_name,
                    args.node2_url, args.node2_name,
                    args.sync_threshold, args.max_attempts,
                    args.retry_delay
                )
                
                if sync_ok:
                    log_success(COMPONENT, f"✅ Sync check #{check_count} PASSED")
                else:
                    log_error(COMPONENT, f"❌ Sync check #{check_count} FAILED")
                
                log_info(COMPONENT, f"Next check in {args.check_interval} seconds...")
                time.sleep(args.check_interval)
                
        except KeyboardInterrupt:
            log_info(COMPONENT, "Continuous sync check interrupted by user")
            handle_exit(0, COMPONENT, "Sync check stopped by user")
    else:
        # Single check mode
        sync_ok = check_synchronization(
            args.node1_url, args.node1_name,
            args.node2_url, args.node2_name,
            args.sync_threshold, args.max_attempts,
            args.retry_delay
        )
        
        if sync_ok:
            log_success(COMPONENT, "✅ Synchronization check PASSED")
            log_info(COMPONENT, "=== Sync check completed successfully ===")
            handle_exit(0, COMPONENT, "Sync check completed successfully")
        else:
            log_critical(COMPONENT, "❌ Synchronization check FAILED")
            log_info(COMPONENT, "=== Sync check failed ===")
            handle_exit(1, COMPONENT, "Sync check failed")


if __name__ == "__main__":
    main()