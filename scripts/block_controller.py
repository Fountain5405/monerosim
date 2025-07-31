#!/usr/bin/env python3
"""
block_controller.py - Central Block Controller Script for MoneroSim

This script controls block generation in the Monero simulation by using the daemon's
generateblocks RPC to generate blocks at regular intervals.

This is a Python port of block_controller.sh, providing the same functionality
with improved error handling and maintainability.
"""

import sys
import time
import socket
from typing import Optional, Dict, Any
from pathlib import Path

# Handle imports for both direct execution and module import
from .error_handling import (
    log_info, log_warning, log_error, log_critical,
    verify_daemon_ready, verify_wallet_directory,
    call_daemon_with_retry, call_wallet_with_retry,
    handle_exit, exponential_backoff
)
from .network_config import (
    DAEMON_IP, DAEMON_RPC_PORT, WALLET1_IP, WALLET1_RPC_PORT,
    WALLET1_NAME, WALLET1_PASSWORD, get_wallet_config
)

# Component name for logging
COMPONENT = "BLOCK_CONTROLLER"

# Configuration
MAX_ATTEMPTS = 30
RETRY_DELAY = 2
DAEMON_URL = f"http://{DAEMON_IP}:{DAEMON_RPC_PORT}/json_rpc"
WALLET_URL = f"http://{WALLET1_IP}:{WALLET1_RPC_PORT}/json_rpc"
WALLET_NAME = WALLET1_NAME
WALLET_PASSWORD = WALLET1_PASSWORD
WALLET_DIR = "/tmp/wallet1_data"

# Block generation settings
BLOCK_INTERVAL = 120  # 2 minutes in seconds
BLOCKS_PER_GENERATION = 1  # Number of blocks to generate each time


def verify_wallet_rpc_ready(wallet_url: str, wallet_ip: str, wallet_port: str,
                           max_attempts: int, retry_delay: float, component: str) -> bool:
    """
    Verify wallet RPC service is ready.
    
    Args:
        wallet_url: URL of the wallet RPC endpoint
        wallet_ip: IP address of the wallet
        wallet_port: Port of the wallet RPC
        max_attempts: Maximum number of attempts
        retry_delay: Base delay between attempts
        component: Component name for logging
        
    Returns:
        True if wallet RPC is ready, False otherwise
    """
    log_info(component, "Verifying wallet RPC service readiness...")
    
    for attempt in range(1, max_attempts + 1):
        current_delay = exponential_backoff(attempt, retry_delay, 60)
        
        # Check if port is open
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((wallet_ip, int(wallet_port)))
            sock.close()
            
            if result == 0:
                # Port is open, try to get version
                success, response = call_wallet_with_retry(
                    wallet_url, "get_version", {}, 1, 1, component
                )
                
                if success:
                    log_info(component, "Wallet RPC service is ready")
                    return True
        except Exception as e:
            log_warning(component, f"Error checking wallet RPC: {e}")
        
        log_warning(component, f"Wallet RPC service not ready (attempt {attempt}/{max_attempts})")
        time.sleep(current_delay)
    
    log_critical(component, f"Wallet RPC service not ready after {max_attempts} attempts")
    return False


def create_new_wallet(wallet_url: str, wallet_name: str, wallet_password: str,
                     max_attempts: int, retry_delay: float, component: str) -> bool:
    """
    Create a new wallet.
    
    Args:
        wallet_url: URL of the wallet RPC endpoint
        wallet_name: Name of the wallet to create
        wallet_password: Password for the wallet
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        component: Component name for logging
        
    Returns:
        True if wallet was created successfully, False otherwise
    """
    log_info(component, f"Creating a new wallet: {wallet_name}...")
    
    params = {
        "filename": wallet_name,
        "password": wallet_password,
        "language": "English"
    }
    
    success, response = call_wallet_with_retry(
        wallet_url, "create_wallet", params, max_attempts, retry_delay, component
    )
    
    if success:
        log_info(component, f"Successfully created new wallet: {wallet_name}")
        return True
    else:
        # Check if wallet already exists and try to open it
        error_message = response.get("error", {}).get("message", "")
        if "already exists" in error_message:
            log_info(component, "Wallet already exists, trying to open it...")
            open_params = {
                "filename": wallet_name,
                "password": wallet_password
            }
            success, open_response = call_wallet_with_retry(
                wallet_url, "open_wallet", open_params, max_attempts, retry_delay, component
            )
            if success:
                log_info(component, f"Successfully opened existing wallet: {wallet_name}")
                return True
        
        log_critical(component, f"Failed to create new wallet: {wallet_name}")
        log_error(component, f"Create response: {response}")
        return False


def get_wallet_address(wallet_url: str, component: str) -> Optional[str]:
    """
    Get wallet address.
    
    Args:
        wallet_url: URL of the wallet RPC endpoint
        component: Component name for logging
        
    Returns:
        Wallet address if successful, None otherwise
    """
    log_info(component, "Getting wallet address...")
    
    success, response = call_wallet_with_retry(
        wallet_url, "get_address", {"account_index": 0}, 3, 2, component
    )
    
    if success:
        wallet_address = response.get("result", {}).get("address")
        if wallet_address:
            log_info(component, f"Successfully retrieved wallet address: {wallet_address}")
            return wallet_address
    
    log_critical(component, "Failed to get wallet address")
    log_error(component, f"Address response: {response}")
    return None


def generate_blocks_continuously(daemon_url: str, wallet_address: str,
                               block_interval: int, blocks_per_generation: int,
                               component: str) -> None:
    """
    Generate blocks continuously at specified intervals.
    
    Args:
        daemon_url: URL of the daemon RPC endpoint
        wallet_address: Address to receive mining rewards
        block_interval: Time between block generations in seconds
        blocks_per_generation: Number of blocks to generate each time
        component: Component name for logging
    """
    block_count = 0
    
    log_info(component, f"Starting block generation with address: {wallet_address}")
    log_info(component, f"Generating {blocks_per_generation} block(s) every {block_interval} seconds")
    
    while True:
        try:
            log_info(component, f"Generating {blocks_per_generation} block(s)...")
            
            # Get initial height
            success, info_response = call_daemon_with_retry(
                daemon_url, "get_info", {}, 3, 2, component
            )
            
            if not success:
                log_warning(component, "Failed to get initial block height. Retrying...")
                time.sleep(block_interval)
                continue
            
            initial_height = info_response.get("result", {}).get("height", 0)
            log_info(component, f"Initial block height: {initial_height}")
            
            # Generate blocks
            gen_params = {
                "amount_of_blocks": blocks_per_generation,
                "wallet_address": wallet_address
            }
            
            success, gen_response = call_daemon_with_retry(
                daemon_url, "generateblocks", gen_params, 3, 5, component
            )
            
            if success:
                result = gen_response.get("result", {})
                blocks_generated = len(result.get("blocks", []))
                final_height = result.get("height", initial_height)
                
                log_info(component, f"Block generation successful! Generated {blocks_generated} blocks")
                log_info(component, f"New height: {final_height}")
                block_count += blocks_generated
            else:
                log_warning(component, "Block generation failed.")
                log_warning(component, f"Response: {gen_response}")
            
            log_info(component, f"Total blocks generated in this session: {block_count}")
            log_info(component, f"Waiting {block_interval} seconds for the next block...")
            time.sleep(block_interval)
            
        except KeyboardInterrupt:
            log_info(component, "Block generation interrupted by user")
            break
        except Exception as e:
            log_error(component, f"Unexpected error during block generation: {e}")
            log_info(component, f"Waiting {block_interval} seconds before retry...")
            time.sleep(block_interval)


def main() -> None:
    """Main execution function."""
    log_info(COMPONENT, "Starting block controller script")
    
    # Verify daemon is ready
    if not verify_daemon_ready(DAEMON_URL, "Daemon", MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        handle_exit(1, COMPONENT, "Daemon verification failed")
    
    # Verify wallet directory
    if not verify_wallet_directory(WALLET_DIR, COMPONENT):
        handle_exit(1, COMPONENT, "Wallet directory verification failed")
    
    # Verify wallet RPC is ready
    if not verify_wallet_rpc_ready(WALLET_URL, WALLET1_IP, WALLET1_RPC_PORT,
                                  MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        handle_exit(1, COMPONENT, "Wallet RPC service verification failed")
    
    # Create or open wallet
    if not create_new_wallet(WALLET_URL, WALLET_NAME, WALLET_PASSWORD,
                           MAX_ATTEMPTS, RETRY_DELAY, COMPONENT):
        handle_exit(1, COMPONENT, "Wallet creation failed")
    
    # Get wallet address
    wallet_address = get_wallet_address(WALLET_URL, COMPONENT)
    if not wallet_address:
        handle_exit(1, COMPONENT, "Failed to get wallet address")
    
    log_info(COMPONENT, f"Using wallet address: {wallet_address}")
    
    # Start continuous block generation
    try:
        generate_blocks_continuously(DAEMON_URL, wallet_address,
                                   BLOCK_INTERVAL, BLOCKS_PER_GENERATION, COMPONENT)
    except KeyboardInterrupt:
        log_info(COMPONENT, "Block controller stopped by user")
        handle_exit(0, COMPONENT, "Script completed successfully")
    except Exception as e:
        log_critical(COMPONENT, f"Unexpected error: {e}")
        handle_exit(1, COMPONENT, f"Script failed with error: {e}")


if __name__ == "__main__":
    main()