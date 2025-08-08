#!/usr/bin/env python3
"""
Simple MoneroSim Test Script

This script tests basic mining and synchronization functionality in the MoneroSim
Shadow network simulation. It verifies that:
1. Both daemon nodes (A0 and A1) are ready and responsive
2. The mining node (A0) can generate blocks
3. The sync node (A1) synchronizes with the mining node

This script uses the agent_discovery module to dynamically discover and connect
to daemon nodes in the simulation environment, replacing the previous hardcoded
network configuration approach.

This is a Python equivalent of simple_test.sh with the same test flow and checks.
"""

import sys
import time
import argparse
from typing import Optional, Tuple

# Add the parent directory to the Python path to import our modules
sys.path.insert(0, '.')

from scripts.error_handling import (
    log_info, log_error, log_critical,
    verify_daemon_ready, call_daemon_with_retry,
    verify_block_generation, verify_network_sync,
    handle_exit
)
from scripts.agent_discovery import AgentDiscovery, AgentDiscoveryError

# Component name for logging
COMPONENT = "SIMPLE_TEST"

# Configuration
MAX_ATTEMPTS = 30
RETRY_DELAY = 2
SYNC_WAIT_TIME = 30
SYNC_THRESHOLD = 0  # Exact match required for this simple test
MINING_ADDRESS = "48S1ZANZRDGTqF7rdxCh8R4jvBELF63u9MieHNwGNYrRZWka84mN9ttV88eq2QScJRHJsdHJMNg3LDu3Z21hmaE61SWymvv"
NUM_BLOCKS = 3

# Agent discovery
agent_discovery = None
A0_RPC = None
A1_RPC = None


def get_height(daemon_url: str, daemon_name: str) -> Optional[int]:
    """
    Get blockchain height from a daemon with retry logic.
    
    Args:
        daemon_url: The RPC URL of the daemon
        daemon_name: The name of the daemon (for logging)
        
    Returns:
        The blockchain height as an integer, or None if failed
    """
    log_info(COMPONENT, f"Getting {daemon_name} height...")
    
    success, response = call_daemon_with_retry(
        daemon_url, "get_info", {}, MAX_ATTEMPTS, RETRY_DELAY, COMPONENT
    )
    
    if not success:
        log_error(COMPONENT, f"Failed to get {daemon_name} height")
        return None
    
    # Extract height from response
    try:
        height = response.get("result", {}).get("height")
        if height is None:
            log_error(COMPONENT, f"Failed to extract height from response: {response}")
            return None
        
        log_info(COMPONENT, f"{daemon_name} height: {height}")
        return height
    except Exception as e:
        log_error(COMPONENT, f"Error parsing height from response: {e}")
        return None


def initialize_agent_discovery():
    """Initialize agent discovery and get daemon RPC URLs."""
    global agent_discovery, A0_RPC, A1_RPC
    
    try:
        agent_discovery = AgentDiscovery()
        
        # Get daemon agents - look for agents with daemon_rpc_port field
        registry = agent_discovery.get_agent_registry()
        agents = registry.get('agents', [])
        
        daemon_agents = []
        if isinstance(agents, list):
            for agent in agents:
                if 'daemon_rpc_port' in agent and agent.get('daemon', False):
                    daemon_agents.append(agent)
        elif isinstance(agents, dict):
            for agent_id, agent_data in agents.items():
                if 'daemon_rpc_port' in agent_data and agent_data.get('daemon', False):
                    daemon_agents.append(agent_data)
        
        if len(daemon_agents) < 2:
            log_error(COMPONENT, f"Insufficient daemon agents found: {len(daemon_agents)}")
            return False
            
        # Extract RPC URLs from daemon agents
        # Sort by ID to ensure consistent ordering
        daemon_agents.sort(key=lambda x: x.get("id", ""))
        
        A0_RPC = f"http://{daemon_agents[0]['ip_addr']}:{daemon_agents[0]['daemon_rpc_port']}/json_rpc"
        A1_RPC = f"http://{daemon_agents[1]['ip_addr']}:{daemon_agents[1]['daemon_rpc_port']}/json_rpc"
        
        log_info(COMPONENT, f"Discovered daemon agents:")
        log_info(COMPONENT, f"  A0: {A0_RPC}")
        log_info(COMPONENT, f"  A1: {A1_RPC}")
        
        return True
        
    except AgentDiscoveryError as e:
        log_error(COMPONENT, f"Agent discovery failed: {e}")
        return False
    except Exception as e:
        log_error(COMPONENT, f"Unexpected error during agent discovery: {e}")
        return False


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MoneroSim Simple Test - Tests basic mining and synchronization functionality"
    )
    parser.add_argument(
        "--max-attempts", type=int, default=MAX_ATTEMPTS,
        help=f"Maximum number of attempts for RPC calls (default: {MAX_ATTEMPTS})"
    )
    parser.add_argument(
        "--retry-delay", type=int, default=RETRY_DELAY,
        help=f"Delay between retries in seconds (default: {RETRY_DELAY})"
    )
    parser.add_argument(
        "--sync-wait", type=int, default=SYNC_WAIT_TIME,
        help=f"Time to wait for synchronization in seconds (default: {SYNC_WAIT_TIME})"
    )
    parser.add_argument(
        "--num-blocks", type=int, default=NUM_BLOCKS,
        help=f"Number of blocks to generate (default: {NUM_BLOCKS})"
    )
    parser.add_argument(
        "--mining-address", type=str, default=MINING_ADDRESS,
        help="Mining address for block generation"
    )
    return parser.parse_args()


def main() -> int:
    """
    Main test execution function.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    args = parse_arguments()
    
    log_info(COMPONENT, "=== MoneroSim Simple Test ===")
    log_info(COMPONENT, f"Starting simple test at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize agent discovery
    log_info(COMPONENT, "Initializing agent discovery...")
    if not initialize_agent_discovery():
        handle_exit(1, COMPONENT, "Agent discovery initialization failed")
        return 1
    
    # Step 1: Verify daemon readiness
    log_info(COMPONENT, "Step 1: Verifying daemon readiness")
    
    if not verify_daemon_ready(A0_RPC, "A0", args.max_attempts, args.retry_delay, COMPONENT):
        handle_exit(1, COMPONENT, "A0 daemon verification failed")
        return 1
    
    if not verify_daemon_ready(A1_RPC, "A1", args.max_attempts, args.retry_delay, COMPONENT):
        handle_exit(1, COMPONENT, "A1 daemon verification failed")
        return 1
    
    # Step 2: Get initial daemon info
    log_info(COMPONENT, "Step 2: Getting initial daemon info")
    
    success, a0_info = call_daemon_with_retry(A0_RPC, "get_info", {}, args.max_attempts, args.retry_delay, COMPONENT)
    if not success:
        log_critical(COMPONENT, "Failed to get A0 info")
        handle_exit(1, COMPONENT, "A0 info retrieval failed")
        return 1
    
    success, a1_info = call_daemon_with_retry(A1_RPC, "get_info", {}, args.max_attempts, args.retry_delay, COMPONENT)
    if not success:
        log_critical(COMPONENT, "Failed to get A1 info")
        handle_exit(1, COMPONENT, "A1 info retrieval failed")
        return 1
    
    # Step 3: Get initial blockchain heights
    log_info(COMPONENT, "Step 3: Getting initial blockchain heights")
    
    a0_height = get_height(A0_RPC, "A0")
    if a0_height is None:
        log_critical(COMPONENT, "Failed to get A0 height")
        handle_exit(1, COMPONENT, "A0 height retrieval failed")
        return 1
    
    a1_height = get_height(A1_RPC, "A1")
    if a1_height is None:
        log_critical(COMPONENT, "Failed to get A1 height")
        handle_exit(1, COMPONENT, "A1 height retrieval failed")
        return 1
    
    log_info(COMPONENT, f"Initial heights - A0: {a0_height}, A1: {a1_height}")
    
    # Step 4: Generate blocks on A0
    log_info(COMPONENT, "Step 4: Generating blocks on A0")
    
    if not verify_block_generation(A0_RPC, args.mining_address, args.num_blocks, args.max_attempts, args.retry_delay, COMPONENT):
        log_critical(COMPONENT, "Block generation failed")
        handle_exit(1, COMPONENT, "Block generation verification failed")
        return 1
    
    # Step 5: Wait for synchronization
    log_info(COMPONENT, f"Step 5: Waiting {args.sync_wait} seconds for synchronization")
    time.sleep(args.sync_wait)
    
    # Step 6: Verify network synchronization
    log_info(COMPONENT, "Step 6: Verifying network synchronization")
    
    if verify_network_sync(A0_RPC, A1_RPC, SYNC_THRESHOLD, 1, 1, COMPONENT):
        log_info(COMPONENT, "✅ SUCCESS: Nodes are synchronized")
    else:
        # Get final heights for diagnostic information
        log_info(COMPONENT, "Getting final blockchain heights")
        a0_final_height = get_height(A0_RPC, "A0")
        a1_final_height = get_height(A1_RPC, "A1")
        
        log_critical(COMPONENT, "❌ FAILURE: Nodes have different blockchain heights")
        log_critical(COMPONENT, f"❌ A0: {a0_final_height}, A1: {a1_final_height}")
        handle_exit(1, COMPONENT, "Synchronization verification failed")
        return 1
    
    log_info(COMPONENT, "✅ Basic mining and synchronization test PASSED")
    log_info(COMPONENT, "=== Simple test completed ===")
    
    handle_exit(0, COMPONENT, "Simple test completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())