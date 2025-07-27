#!/usr/bin/env python3
"""
monitor.py - Monitoring Script for MoneroSim

This script monitors the status of the Monero simulation, providing real-time
information about:
- Node status and synchronization
- Blockchain height and growth
- Peer connections
- Mining status
- Transaction pool status
- System resource usage

This is a Python implementation that replaces the monitor_script.sh functionality.
"""

import sys
import time
import argparse
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# Handle imports for both direct execution and module import
try:
    from error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_daemon_ready, handle_exit
    )
    from network_config import (
        A0_RPC, A1_RPC, get_daemon_config
    )
except ImportError:
    sys.path.append('..')
    from scripts.error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_daemon_ready, handle_exit
    )
    from scripts.network_config import (
        A0_RPC, A1_RPC, get_daemon_config
    )

# Component name for logging
COMPONENT = "MONITOR"

# Default configuration
DEFAULT_REFRESH_INTERVAL = 10  # seconds
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 2


class NodeStatus:
    """Container for node status information."""
    
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


def get_node_info(node_url: str, max_attempts: int, retry_delay: float) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive node information.
    
    Args:
        node_url: URL of the node RPC endpoint
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        Dictionary with node information or None if failed
    """
    success, response = call_daemon_with_retry(
        node_url, "get_info", {}, max_attempts, retry_delay, COMPONENT
    )
    
    if success:
        return response.get("result", {})
    return None


def get_mining_status(node_url: str, max_attempts: int, retry_delay: float) -> Optional[Dict[str, Any]]:
    """
    Get mining status from node.
    
    Args:
        node_url: URL of the node RPC endpoint
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        Dictionary with mining status or None if failed
    """
    success, response = call_daemon_with_retry(
        node_url, "mining_status", {}, max_attempts, retry_delay, COMPONENT
    )
    
    if success:
        return response.get("result", {})
    return None


def get_connections(node_url: str, max_attempts: int, retry_delay: float) -> Optional[List[Dict[str, Any]]]:
    """
    Get peer connections from node.
    
    Args:
        node_url: URL of the node RPC endpoint
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        List of connections or None if failed
    """
    success, response = call_daemon_with_retry(
        node_url, "get_connections", {}, max_attempts, retry_delay, COMPONENT
    )
    
    if success:
        return response.get("result", {}).get("connections", [])
    return None


def update_node_status(node: NodeStatus, max_attempts: int, retry_delay: float) -> None:
    """
    Update node status with latest information.
    
    Args:
        node: NodeStatus object to update
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
    """
    # Get basic node info
    info = get_node_info(node.url, max_attempts, retry_delay)
    if info:
        node.height = info.get("height", 0)
        node.target_height = info.get("target_height", 0)
        node.difficulty = info.get("difficulty", 0)
        node.tx_count = info.get("tx_count", 0)
        node.tx_pool_size = info.get("tx_pool_size", 0)
        node.incoming_connections = info.get("incoming_connections_count", 0)
        node.outgoing_connections = info.get("outgoing_connections_count", 0)
        node.white_peerlist_size = info.get("white_peerlist_size", 0)
        node.grey_peerlist_size = info.get("grey_peerlist_size", 0)
        node.status = info.get("status", "unknown")
        node.synchronized = info.get("synchronized", False)
        node.cumulative_difficulty = info.get("cumulative_difficulty", 0)
        node.top_block_hash = info.get("top_block_hash", "")
        node.block_reward = info.get("block_reward", 0)
        node.error = None
    else:
        node.error = "Failed to get node info"
    
    # Get mining status (may not be available in regtest mode)
    mining_status = get_mining_status(node.url, max_attempts, retry_delay)
    if mining_status:
        node.mining_active = mining_status.get("active", False)
        node.hashrate = mining_status.get("speed", 0)
    else:
        # Mining status might not be available (e.g., in regtest mode)
        # This is not an error, just unavailable information
        log_info(COMPONENT, f"Mining status not available for {node.name} (this is normal in regtest mode)")
    
    node.last_update = datetime.now()


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_hashrate(hashrate: int) -> str:
    """Format hashrate to human readable format."""
    if hashrate < 1000:
        return f"{hashrate} H/s"
    elif hashrate < 1000000:
        return f"{hashrate/1000:.2f} KH/s"
    else:
        return f"{hashrate/1000000:.2f} MH/s"


def print_node_status(node: NodeStatus, verbose: bool = False) -> None:
    """
    Print formatted node status.
    
    Args:
        node: NodeStatus object to print
        verbose: Whether to print verbose output
    """
    print(f"\n{'='*60}")
    print(f"Node: {node.name}")
    print(f"{'='*60}")
    
    if node.error:
        print(f"ERROR: {node.error}")
        return
    
    # Basic info
    print(f"Status: {node.status}")
    print(f"Synchronized: {'Yes' if node.synchronized else 'No'}")
    print(f"Height: {node.height:,} / {node.target_height:,}")
    if node.target_height > 0:
        sync_percent = (node.height / node.target_height) * 100
        print(f"Sync Progress: {sync_percent:.1f}%")
    
    # Mining info
    if node.mining_active:
        print(f"Mining: Active ({format_hashrate(node.hashrate)})")
    else:
        print(f"Mining: Inactive")
    
    # Network info
    print(f"Connections: {node.incoming_connections} in / {node.outgoing_connections} out")
    print(f"Peer Lists: {node.white_peerlist_size} white / {node.grey_peerlist_size} grey")
    
    # Transaction pool
    print(f"TX Pool: {node.tx_pool_size} transactions")
    print(f"Total TXs: {node.tx_count:,}")
    
    # Blockchain info
    print(f"Difficulty: {node.difficulty:,}")
    if node.block_reward > 0:
        reward_xmr = node.block_reward / 1e12
        print(f"Block Reward: {reward_xmr:.12f} XMR")
    
    # Verbose information
    if verbose:
        print(f"\nVerbose Details:")
        print(f"URL: {node.url}")
        print(f"Cumulative Difficulty: {node.cumulative_difficulty:,}")
        if node.top_block_hash:
            print(f"Top Block Hash: {node.top_block_hash[:16]}...")
    
    # Last update
    if node.last_update:
        print(f"Last Update: {node.last_update.strftime('%Y-%m-%d %H:%M:%S')}")


def print_comparison(nodes: List[NodeStatus]) -> None:
    """
    Print comparison between nodes.
    
    Args:
        nodes: List of NodeStatus objects to compare
    """
    if len(nodes) < 2:
        return
    
    print(f"\n{'='*60}")
    print("Node Comparison")
    print(f"{'='*60}")
    
    # Height comparison
    heights = [(n.name, n.height) for n in nodes if not n.error]
    if heights:
        max_height = max(h[1] for h in heights)
        min_height = min(h[1] for h in heights)
        
        print("Blockchain Heights:")
        for name, height in heights:
            diff = height - min_height
            status = "✓" if height == max_height else f"-{max_height - height}"
            print(f"  {name}: {height:,} ({status})")
        
        if max_height != min_height:
            print(f"  Height Difference: {max_height - min_height} blocks")
    
    # Connection comparison
    print("\nConnections:")
    for node in nodes:
        if not node.error:
            total_conn = node.incoming_connections + node.outgoing_connections
            print(f"  {node.name}: {total_conn} total ({node.incoming_connections} in / {node.outgoing_connections} out)")
    
    # Mining status
    print("\nMining Status:")
    for node in nodes:
        if not node.error:
            if node.mining_active:
                print(f"  {node.name}: Active ({format_hashrate(node.hashrate)})")
            else:
                print(f"  {node.name}: Inactive")


def monitor_loop(nodes: List[NodeStatus], refresh_interval: int,
                max_attempts: int, retry_delay: float,
                clear_screen: bool = True, verbose: bool = False) -> None:
    """
    Main monitoring loop.
    
    Args:
        nodes: List of NodeStatus objects to monitor
        refresh_interval: Time between updates in seconds
        max_attempts: Maximum number of attempts for RPC calls
        retry_delay: Delay between RPC attempts
        clear_screen: Whether to clear screen between updates
        verbose: Whether to print verbose output
    """
    iteration = 0
    
    try:
        while True:
            iteration += 1
            
            # Clear screen if requested
            if clear_screen:
                print("\033[2J\033[H")  # ANSI escape codes to clear screen
            
            print(f"MoneroSim Monitor - Iteration #{iteration}")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Update all nodes
            for node in nodes:
                update_node_status(node, max_attempts, retry_delay)
            
            # Print status for each node
            for node in nodes:
                print_node_status(node, verbose)
            
            # Print comparison
            print_comparison(nodes)
            
            print(f"\nRefreshing in {refresh_interval} seconds... (Press Ctrl+C to stop)")
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        log_info(COMPONENT, "Monitoring stopped by user")


def main():
    """Main function for monitor script."""
    parser = argparse.ArgumentParser(
        description="Monitor Monero nodes in Shadow simulation"
    )
    
    # Add command line arguments
    parser.add_argument(
        "--nodes",
        nargs="+",
        help="List of nodes to monitor (format: name=url)",
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
        "--continuous",
        action="store_true",
        help="Run in continuous mode (default unless --once is specified)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="Alias for --refresh, sets refresh interval in seconds"
    )
    
    args = parser.parse_args()
    
    # Handle interval alias
    if args.interval is not None:
        args.refresh = args.interval
    
    log_info(COMPONENT, "=== MoneroSim Monitor ===")
    log_info(COMPONENT, f"Starting monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Parse nodes
    nodes = []
    if args.nodes:
        for node_spec in args.nodes:
            if "=" in node_spec:
                name, url = node_spec.split("=", 1)
                nodes.append(NodeStatus(name, url))
            else:
                log_error(COMPONENT, f"Invalid node specification: {node_spec}")
                log_error(COMPONENT, "Use format: name=url")
                handle_exit(1, COMPONENT, "Invalid node specification")
    else:
        # Default nodes
        nodes = [
            NodeStatus("A0", A0_RPC),
            NodeStatus("A1", A1_RPC)
        ]
    
    log_info(COMPONENT, f"Monitoring {len(nodes)} nodes")
    
    # Verify all nodes are reachable
    all_ready = True
    for node in nodes:
        if not verify_daemon_ready(node.url, node.name, args.max_attempts, 
                                 args.retry_delay, COMPONENT):
            log_error(COMPONENT, f"Node {node.name} is not ready")
            all_ready = False
    
    if not all_ready:
        handle_exit(1, COMPONENT, "Not all nodes are ready")
    
    if args.once:
        # Single run mode
        log_info(COMPONENT, "Running single status check")
        
        # Update all nodes
        for node in nodes:
            update_node_status(node, args.max_attempts, args.retry_delay)
        
        # Print status
        for node in nodes:
            print_node_status(node, args.verbose)
        
        # Print comparison
        print_comparison(nodes)
        
        log_info(COMPONENT, "Monitor check completed")
        handle_exit(0, COMPONENT, "Single run completed successfully")
    else:
        # Continuous monitoring mode
        log_info(COMPONENT, f"Starting continuous monitoring (refresh every {args.refresh} seconds)")
        monitor_loop(nodes, args.refresh, args.max_attempts, args.retry_delay,
                    not args.no_clear, args.verbose)
        
        handle_exit(0, COMPONENT, "Monitoring stopped")


if __name__ == "__main__":
    main()