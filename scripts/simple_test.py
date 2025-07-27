#!/usr/bin/env python3
"""
Simple MoneroSim Test Script

This script tests basic mining and synchronization functionality in the MoneroSim
Shadow network simulation. It verifies that:
1. Both daemon nodes (A0 and A1) are ready and responsive
2. The mining node (A0) can generate blocks
3. The sync node (A1) synchronizes with the mining node

This is a Python equivalent of simple_test.sh with the same test flow and checks.
"""

import sys
import time
from typing import Optional, Tuple

# Add the parent directory to the Python path to import our modules
sys.path.insert(0, '.')

from scripts.error_handling import (
    log_info, log_error, log_critical,
    verify_daemon_ready, call_daemon_with_retry,
    verify_block_generation, verify_network_sync,
    handle_exit
)
from scripts.network_config import A0_RPC, A1_RPC

# Component name for logging
COMPONENT = "SIMPLE_TEST"

# Configuration
MAX_ATTEMPTS = 30
RETRY_DELAY = 2
SYNC_WAIT_TIME = 30
SYNC_THRESHOLD = 0  # Exact match required for this simple test
MINING_ADDRESS = "48S1ZANZRDGTqF7rdxCh8R4jvBELF63u9MieHNwGNYrRZWka84mN9ttV88eq2QScJRHJsdHJMNg3LDu3Z21hmaE61SWymvv"
NUM_BLOCKS = 3


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


def main() -> int:
    """
    Main test execution function.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    log_info(COMPONENT, "=== MoneroSim Simple Test ===")
    log_info(COMPONENT, f"Starting simple test at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Verify daemon readiness
    log_info(COMPONENT, "Step 1: Verifying daemon readiness")
    
    if not verify_daemon_ready(A0_RPC, "A0", MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        handle_exit(1, COMPONENT, "A0 daemon verification failed")
        return 1
    
    if not verify_daemon_ready(A1_RPC, "A1", MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        handle_exit(1, COMPONENT, "A1 daemon verification failed")
        return 1
    
    # Step 2: Get initial daemon info
    log_info(COMPONENT, "Step 2: Getting initial daemon info")
    
    success, a0_info = call_daemon_with_retry(A0_RPC, "get_info", {}, MAX_ATTEMPTS, RETRY_DELAY, COMPONENT)
    if not success:
        log_critical(COMPONENT, "Failed to get A0 info")
        handle_exit(1, COMPONENT, "A0 info retrieval failed")
        return 1
    
    success, a1_info = call_daemon_with_retry(A1_RPC, "get_info", {}, MAX_ATTEMPTS, RETRY_DELAY, COMPONENT)
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
    
    if not verify_block_generation(A0_RPC, MINING_ADDRESS, NUM_BLOCKS, MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        log_critical(COMPONENT, "Block generation failed")
        handle_exit(1, COMPONENT, "Block generation verification failed")
        return 1
    
    # Step 5: Wait for synchronization
    log_info(COMPONENT, f"Step 5: Waiting {SYNC_WAIT_TIME} seconds for synchronization")
    time.sleep(SYNC_WAIT_TIME)
    
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