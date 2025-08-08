#!/usr/bin/env python3
"""
block_controller.py - Central Block Controller Script for MoneroSim

This script controls block generation in the Monero simulation by using the daemon's
generateblocks RPC to generate blocks at regular intervals.

This is a Python port of block_controller.sh, providing the same functionality
with improved error handling and maintainability. It now uses dynamic agent discovery
instead of hardcoded configurations, enabling it to work with any number of agents
and support scalability.

Key Features:
- Dynamic agent discovery using the AgentDiscovery class
- Automatic configuration of daemon and wallet endpoints
- Support for any number of miner agents
- Robust error handling for agent discovery failures
- Scalable architecture that grows with the simulation
"""

import sys
import time
import socket
import argparse
from typing import Optional, Dict, Any
from pathlib import Path

# Handle imports for both direct execution and module import
try:
    from .error_handling import (
        log_info, log_warning, log_error, log_critical,
        verify_daemon_ready, verify_wallet_directory,
        call_daemon_with_retry, call_wallet_with_retry,
        handle_exit, exponential_backoff
    )
    from .agent_discovery import AgentDiscovery, AgentDiscoveryError
except ImportError:
    # Fallback for when running as a script directly
    from error_handling import (
        log_info, log_warning, log_error, log_critical,
        verify_daemon_ready, verify_wallet_directory,
        call_daemon_with_retry, call_wallet_with_retry,
        handle_exit, exponential_backoff
    )
    from agent_discovery import AgentDiscovery, AgentDiscoveryError

# Component name for logging
COMPONENT = "BLOCK_CONTROLLER"

# Configuration
DEFAULT_MAX_ATTEMPTS = 30
DEFAULT_RETRY_DELAY = 2
SHARED_STATE_DIR = "/tmp/monerosim_shared"

# Block generation settings
DEFAULT_BLOCK_INTERVAL = 120  # 2 minutes in seconds
DEFAULT_BLOCKS_PER_GENERATION = 1  # Number of blocks to generate each time


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Block controller for Monero simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 block_controller.py --help
  python3 block_controller.py --block-interval 60 --blocks-per-generation 2
  python3 block_controller.py --max-attempts 20 --retry-delay 1
        """
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Maximum number of attempts for connection and operations (default: {DEFAULT_MAX_ATTEMPTS})"
    )
    
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=DEFAULT_RETRY_DELAY,
        help=f"Base delay in seconds between retries (default: {DEFAULT_RETRY_DELAY})"
    )
    
    parser.add_argument(
        "--block-interval",
        type=int,
        default=DEFAULT_BLOCK_INTERVAL,
        help=f"Time in seconds between block generations (default: {DEFAULT_BLOCK_INTERVAL})"
    )
    
    parser.add_argument(
        "--blocks-per-generation",
        type=int,
        default=DEFAULT_BLOCKS_PER_GENERATION,
        help=f"Number of blocks to generate each time (default: {DEFAULT_BLOCKS_PER_GENERATION})"
    )
    
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run in test mode (discover agents but don't start block generation)"
    )
    
    return parser.parse_args()


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


def discover_and_configure_agents() -> Dict[str, Any]:
    """
    Discover and configure agents using dynamic agent discovery.
    
    This function replaces the legacy hardcoded configuration approach by dynamically
    discovering miner agents and their associated daemon and wallet configurations.
    It automatically selects the first available miner agent and extracts all necessary
    configuration parameters for block generation.
    
    Returns:
        Dictionary containing daemon and wallet configuration with keys:
        - daemon_url: RPC URL for the daemon
        - daemon_ip: IP address of the daemon
        - daemon_port: RPC port of the daemon
        - wallet_url: RPC URL for the wallet
        - wallet_ip: IP address of the wallet
        - wallet_port: RPC port of the wallet
        - wallet_name: Name of the wallet
        - wallet_password: Password for the wallet
        - wallet_dir: Directory for wallet data
        
    Raises:
        AgentDiscoveryError: If agent discovery fails or no miners are found.
    """
    log_info(COMPONENT, "Initializing agent discovery")
    
    try:
        # Initialize agent discovery
        discovery = AgentDiscovery(SHARED_STATE_DIR)
        
        # Get all agents from the registry
        registry = discovery.get_agent_registry()
        agents = registry.get("agents", [])
        
        # Find agents that have both daemon and wallet capabilities
        miner_agents = []
        
        # Handle both list and dictionary formats
        if isinstance(agents, list):
            for agent_data in agents:
                # Check if agent has both daemon and wallet capabilities
                if (agent_data.get("daemon") is True and
                    agent_data.get("wallet") is True and
                    agent_data.get("daemon_rpc_port") and
                    agent_data.get("wallet_rpc_port") and
                    agent_data.get("attributes", {}).get("is_miner") == "true"):
                    
                    # Ensure ID is present
                    agent_copy = agent_data.copy()
                    if "id" not in agent_copy and "agent_id" in agent_copy:
                        agent_copy["id"] = agent_copy["agent_id"]
                    miner_agents.append(agent_copy)
        elif isinstance(agents, dict):
            for agent_id, agent_data in agents.items():
                # Check if agent has both daemon and wallet capabilities
                if (agent_data.get("daemon") is True and
                    agent_data.get("wallet") is True and
                    agent_data.get("daemon_rpc_port") and
                    agent_data.get("wallet_rpc_port") and
                    agent_data.get("attributes", {}).get("is_miner") == "true"):
                    
                    agent_copy = agent_data.copy()
                    agent_copy["id"] = agent_id
                    miner_agents.append(agent_copy)
        
        if not miner_agents:
            raise AgentDiscoveryError("No miner agents with both daemon and wallet found")
        
        # Use the first miner for block generation
        miner = miner_agents[0]
        log_info(COMPONENT, f"Using miner agent: {miner.get('id', 'unknown')}")
        
        # Extract daemon configuration
        daemon_ip = miner.get("ip_addr")
        daemon_port = miner.get("daemon_rpc_port")
        
        if not daemon_ip or not daemon_port:
            raise AgentDiscoveryError(f"Miner agent missing daemon configuration: {miner}")
        
        daemon_url = f"http://{daemon_ip}:{daemon_port}/json_rpc"
        
        # Extract wallet configuration
        wallet_ip = miner.get("ip_addr")  # Wallet is on the same host as the miner
        wallet_port = miner.get("wallet_rpc_port")
        wallet_name = miner.get("wallet_name", "mining_wallet")
        wallet_password = miner.get("wallet_password", "test123")
        
        if not wallet_ip or not wallet_port:
            raise AgentDiscoveryError(f"Miner agent missing wallet configuration: {miner}")
        
        wallet_url = f"http://{wallet_ip}:{wallet_port}/json_rpc"
        wallet_dir = f"/tmp/{miner.get('id', 'miner')}_wallet_data"
        
        log_info(COMPONENT, f"Discovered daemon at: {daemon_url}")
        log_info(COMPONENT, f"Discovered wallet at: {wallet_url}")
        
        return {
            "daemon_url": daemon_url,
            "daemon_ip": daemon_ip,
            "daemon_port": daemon_port,
            "wallet_url": wallet_url,
            "wallet_ip": wallet_ip,
            "wallet_port": wallet_port,
            "wallet_name": wallet_name,
            "wallet_password": wallet_password,
            "wallet_dir": wallet_dir
        }
        
    except Exception as e:
        log_error(COMPONENT, f"Agent discovery failed: {e}")
        raise AgentDiscoveryError(f"Failed to discover agents: {e}")


def main() -> None:
    """
    Main execution function for the block controller.
    
    This function orchestrates the block generation process by:
    1. Parsing command line arguments
    2. Dynamically discovering miner agents and their configurations
    3. Verifying that both daemon and wallet services are ready
    4. Creating or opening the wallet for mining rewards
    5. Starting continuous block generation at regular intervals
    
    The function uses dynamic agent discovery instead of hardcoded configurations,
    enabling it to work with any number of agents and support scalability.
    """
    # Parse command line arguments
    args = parse_arguments()
    
    log_info(COMPONENT, "Starting block controller script")
    
    try:
        # Discover and configure agents dynamically
        agent_config = discover_and_configure_agents()
        
        # If in test mode, just report success and exit
        if args.test_mode:
            log_info(COMPONENT, "Test mode: Agent discovery successful")
            log_info(COMPONENT, f"Found daemon at: {agent_config['daemon_url']}")
            log_info(COMPONENT, f"Found wallet at: {agent_config['wallet_url']}")
            handle_exit(0, COMPONENT, "Test mode completed successfully")
        
        # Verify daemon is ready
        if not verify_daemon_ready(agent_config["daemon_url"], "Daemon", args.max_attempts, args.retry_delay, COMPONENT):
            handle_exit(1, COMPONENT, "Daemon verification failed")
        
        # Verify wallet directory
        if not verify_wallet_directory(agent_config["wallet_dir"], COMPONENT):
            handle_exit(1, COMPONENT, "Wallet directory verification failed")
        
        # Verify wallet RPC is ready
        if not verify_wallet_rpc_ready(
            agent_config["wallet_url"],
            agent_config["wallet_ip"],
            agent_config["wallet_port"],
            args.max_attempts, args.retry_delay, COMPONENT
        ):
            handle_exit(1, COMPONENT, "Wallet RPC service verification failed")
        
        # Create or open wallet
        if not create_new_wallet(
            agent_config["wallet_url"],
            agent_config["wallet_name"],
            agent_config["wallet_password"],
            args.max_attempts, args.retry_delay, COMPONENT
        ):
            handle_exit(1, COMPONENT, "Wallet creation failed")
        
        # Get wallet address
        wallet_address = get_wallet_address(agent_config["wallet_url"], COMPONENT)
        if not wallet_address:
            handle_exit(1, COMPONENT, "Failed to get wallet address")
        
        log_info(COMPONENT, f"Using wallet address: {wallet_address}")
        
        # Start continuous block generation
        try:
            generate_blocks_continuously(
                agent_config["daemon_url"],
                wallet_address,
                args.block_interval, args.blocks_per_generation, COMPONENT
            )
        except KeyboardInterrupt:
            log_info(COMPONENT, "Block controller stopped by user")
            handle_exit(0, COMPONENT, "Script completed successfully")
        except Exception as e:
            log_critical(COMPONENT, f"Unexpected error: {e}")
            handle_exit(1, COMPONENT, f"Script failed with error: {e}")
            
    except AgentDiscoveryError as e:
        log_critical(COMPONENT, f"Agent discovery failed: {e}")
        handle_exit(1, COMPONENT, "Agent discovery failed")
    except Exception as e:
        log_critical(COMPONENT, f"Unexpected error: {e}")
        handle_exit(1, COMPONENT, f"Script failed with error: {e}")


if __name__ == "__main__":
    main()