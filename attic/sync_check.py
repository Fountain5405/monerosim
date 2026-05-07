#!/usr/bin/env python3
"""
sync_check.py - Synchronization verification script for MoneroSim

This script checks the synchronization status between Monero nodes in the Shadow simulation.
It verifies that nodes have synchronized their blockchains and are at the same height.

This is a Python implementation that replaces the bash sync_check.sh script and has been
refactored to use dynamic agent discovery instead of hardcoded configurations.

The script now automatically discovers miner and regular user nodes from the shared state
directory, eliminating the need for hardcoded IP addresses and ports. This enables the
script to work with any number of agents and supports scalability.

Usage:
  python3 sync_check.py [options]

Options:
  --node1-url URL         URL of the first node (default: discovered automatically)
  --node1-name NAME       Name of the first node (default: discovered automatically)
  --node2-url URL         URL of the second node (default: discovered automatically)
  --node2-name NAME       Name of the second node (default: discovered automatically)
  --shared-state-dir DIR  Path to the shared state directory (default: /tmp/monerosim_shared)
  --sync-threshold N      Maximum allowed height difference (default: 1)
  --max-attempts N        Maximum number of attempts (default: 30)
  --retry-delay SECONDS   Delay between attempts in seconds (default: 2)
  --wait-time SECONDS     Time to wait before checking sync in seconds (default: 10)
  --continuous            Run continuously, checking sync status periodically
  --check-interval SECONDS Interval between checks in continuous mode (default: 30)
  --test-mode             Test mode - only check node discovery, don't attempt RPC calls
"""

import sys
import time
import argparse
from typing import Optional, Tuple, List, Dict, Any

# Import from error_handling and agent_discovery modules
try:
    from agents.base_agent import DEFAULT_SHARED_DIR
    from scripts.error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_network_sync, handle_exit
    )
    from agents.agent_discovery import AgentDiscovery, AgentDiscoveryError
except ImportError:
    # Handle case where script is run from different directory
    sys.path.append('.')
    from agents.base_agent import DEFAULT_SHARED_DIR
    from scripts.error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_network_sync, handle_exit
    )
    from agents.agent_discovery import AgentDiscovery, AgentDiscoveryError

# Component name for logging
COMPONENT = "SYNC_CHECK"

# Default configuration
DEFAULT_MAX_ATTEMPTS = 30
DEFAULT_RETRY_DELAY = 2
DEFAULT_SYNC_THRESHOLD = 1  # Maximum allowed height difference
DEFAULT_SYNC_WAIT_TIME = 10  # Time to wait before checking sync


def discover_nodes(shared_state_dir: str = DEFAULT_SHARED_DIR) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Discover nodes dynamically using agent discovery.

    This function replaces the hardcoded A0/A1 node configuration with dynamic discovery
    from the shared state directory. It finds the first miner agent and the first regular
    user agent to use for synchronization checking.

    Args:
        shared_state_dir: Path to the shared state directory containing agent registry files

    Returns:
        Tuple of (miner_node, regular_node) dictionaries or (None, None) if discovery fails

    Raises:
        Logs errors but does not raise exceptions to allow graceful fallback
    """
    try:
        discovery = AgentDiscovery(shared_state_dir)

        # Get all agents from the registry
        registry = discovery.get_agent_registry()
        all_agents = registry.get("agents", [])

        if not all_agents:
            log_error(COMPONENT, "No agents found in registry")
            return None, None

        log_info(COMPONENT, f"Found {len(all_agents)} agents in registry")

        # Find miner agents directly from the main agents list
        miners = []
        for agent in all_agents:
            # Check if agent has is_miner attribute set to true
            attributes = agent.get("attributes", {})
            if str(attributes.get("is_miner", "")).lower() == "true":
                miners.append(agent)

        if not miners:
            log_error(COMPONENT, "No miner agents found")
            return None, None

        miner_node = miners[0]  # Use the first miner
        log_info(COMPONENT, f"Discovered miner node: {miner_node.get('id', 'unknown')}")

        # Find regular user agents (agents without is_miner attribute)
        regular_users = []
        for agent in all_agents:
            agent_id = agent.get("id") or agent.get("agent_id", "unknown")
            agent_type = agent.get("type", "unknown")
            attributes = agent.get("attributes", {})
            is_miner = str(attributes.get("is_miner", "")).lower() == "true"
            has_daemon = agent.get("daemon", False)

            log_info(COMPONENT, f"Checking agent {agent_id}: type={agent_type}, is_miner={is_miner}, has_daemon={has_daemon}")

            # Check for regularuser type or agents without is_miner attribute
            if (agent_type == "regularuser") or (
                not is_miner and has_daemon
            ):
                regular_users.append(agent)
                log_info(COMPONENT, f"Added {agent_id} as regular user")

        if not regular_users:
            log_error(COMPONENT, "No regular user agents found")
            return None, None

        regular_node = regular_users[0]  # Use the first regular user
        log_info(COMPONENT, f"Discovered regular node: {regular_node.get('id', 'unknown')}")

        return miner_node, regular_node

    except AgentDiscoveryError as e:
        log_error(COMPONENT, f"Agent discovery failed: {e}")
        return None, None
    except Exception as e:
        log_error(COMPONENT, f"Unexpected error during node discovery: {e}")
        return None, None


def get_node_rpc_url(node: Dict[str, Any]) -> Optional[str]:
    """
    Extract RPC URL from node information.

    This function handles multiple possible formats for RPC URLs in the agent data,
    providing flexibility for different agent registry formats. It first checks
    for direct RPC URL fields, then constructs the URL from IP and port if needed.

    Args:
        node: Node dictionary from agent discovery containing RPC connection details

    Returns:
        RPC URL string in format "http://ip:port/json_rpc" or None if not found

    Note:
        Supports multiple field names for backward compatibility:
        - daemon_rpc, rpc_url, monerod_rpc (direct URL)
        - ip_addr/ip + rpc_port/monerod_port (constructed URL)
    """
    if not node:
        return None

    # Debug logging
    log_info(COMPONENT, f"Node data keys: {list(node.keys())}")
    if "attributes" in node:
        log_info(COMPONENT, f"Node attributes: {node['attributes']}")

    # Try different possible keys for RPC URL
    rpc_url = node.get("daemon_rpc") or node.get("rpc_url") or node.get("monerod_rpc")

    if rpc_url:
        log_info(COMPONENT, f"Found direct RPC URL: {rpc_url}")
        return rpc_url

    # If RPC URL not found directly, try to construct from IP and port
    ip = node.get("ip_addr") or node.get("ip")
    port = node.get("rpc_port") or node.get("monerod_port") or node.get("daemon_rpc_port") or node.get("agent_rpc_port")

    log_info(COMPONENT, f"IP: {ip}, Port: {port}")

    if ip and port:
        constructed_url = f"http://{ip}:{port}/json_rpc"
        log_info(COMPONENT, f"Constructed RPC URL: {constructed_url}")
        return constructed_url

    log_warning(COMPONENT, "Could not determine RPC URL from node data")
    return None


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
    """
    Main function for sync check script.

    This function handles command-line argument parsing and orchestrates the
    synchronization checking process. It now supports both automatic node
    discovery and manual node specification via command-line arguments.

    The function first attempts to discover nodes dynamically if URLs are not
    provided, then proceeds with the synchronization check in either single
    or continuous mode based on the provided arguments.
    """
    parser = argparse.ArgumentParser(
        description="Check synchronization between Monero nodes in Shadow simulation"
    )

    # Add command line arguments
    parser.add_argument(
        "--node1-url",
        default="",
        help="URL of the first node (default: discovered automatically)"
    )
    parser.add_argument(
        "--node1-name",
        default="",
        help="Name of the first node (default: discovered automatically)"
    )
    parser.add_argument(
        "--node2-url",
        default="",
        help="URL of the second node (default: discovered automatically)"
    )
    parser.add_argument(
        "--node2-name",
        default="",
        help="Name of the second node (default: discovered automatically)"
    )
    parser.add_argument(
        "--shared-state-dir",
        default=DEFAULT_SHARED_DIR,
        help="Path to the shared state directory"
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
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Test mode - only check node discovery, don't attempt RPC calls"
    )

    args, _ = parser.parse_known_args()

    log_info(COMPONENT, "=== MoneroSim Synchronization Check ===")
    log_info(COMPONENT, f"Starting sync check at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Use dynamic node discovery if node URLs are not provided
    node1_url = args.node1_url
    node1_name = args.node1_name
    node2_url = args.node2_url
    node2_name = args.node2_name

    if not node1_url or not node2_url:
        log_info(COMPONENT, "Using dynamic agent discovery to find nodes...")
        miner_node, regular_node = discover_nodes(args.shared_state_dir)

        if not miner_node or not regular_node:
            log_critical(COMPONENT, "Failed to discover nodes for synchronization check")
            handle_exit(1, COMPONENT, "Node discovery failed")

        # Set node URLs and names if not provided via command line
        if not node1_url:
            node1_url = get_node_rpc_url(miner_node)
            node1_name = miner_node.get("id", "miner")

        if not node2_url:
            node2_url = get_node_rpc_url(regular_node)
            node2_name = regular_node.get("id", "regular_user")

    # Verify we have valid URLs
    if not node1_url or not node2_url:
        log_critical(COMPONENT, "Invalid node URLs for synchronization check")
        handle_exit(1, COMPONENT, "Invalid node URLs")

    log_info(COMPONENT, f"Node 1: {node1_name} at {node1_url}")
    log_info(COMPONENT, f"Node 2: {node2_name} at {node2_url}")

    # Test mode - only check node discovery, don't attempt RPC calls
    if args.test_mode:
        log_info(COMPONENT, "Test mode enabled - node discovery completed successfully")
        log_info(COMPONENT, "Skipping RPC calls as requested")
        log_success(COMPONENT, "✅ Node discovery test PASSED")
        log_info(COMPONENT, "=== Test mode completed successfully ===")
        handle_exit(0, COMPONENT, "Node discovery test completed successfully")

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
                    node1_url, node1_name,
                    node2_url, node2_name,
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
            node1_url, node1_name,
            node2_url, node2_name,
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