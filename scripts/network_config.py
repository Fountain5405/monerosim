#!/usr/bin/env python3
"""
network_config.py - Central configuration module for MoneroSim network settings

This module defines all IP addresses and ports used across the MoneroSim scripts.
It provides the same configuration values as network_config.sh but in a Python-friendly format.
"""

from typing import Dict, Any
import json

# Handle imports for both direct execution and module import
try:
    from error_handling import log_info, log_warning
except ImportError:
    from scripts.error_handling import log_info, log_warning

# Module identification
MODULE_NAME = "NETWORK_CONFIG"

# Daemon Agents Configuration
A0_IP: str = "11.0.0.10"          # Mining node IP
A0_RPC_PORT: str = "28090"       # Mining node RPC port
A0_RPC: str = f"http://{A0_IP}:{A0_RPC_PORT}/json_rpc"

A1_IP: str = "11.0.0.11"          # Sync agent IP
A1_RPC_PORT: str = "28100"       # Sync node RPC port
A1_RPC: str = f"http://{A1_IP}:{A1_RPC_PORT}/json_rpc"

# Wallet Agents Configuration - Updated to match current shadow.yaml configuration
WALLET1_IP: str = "11.0.0.3"     # Mining wallet IP
WALLET1_RPC_PORT: str = "28091"  # Mining wallet RPC port
WALLET1_RPC: str = f"http://{WALLET1_IP}:{WALLET1_RPC_PORT}/json_rpc"

WALLET2_IP: str = "11.0.0.4"     # Recipient wallet IP
WALLET2_RPC_PORT: str = "28092"  # Recipient wallet RPC port
WALLET2_RPC: str = f"http://{WALLET2_IP}:{WALLET2_RPC_PORT}/json_rpc"

# For backward compatibility with scripts using different variable names
DAEMON_IP: str = A0_IP
DAEMON_RPC_PORT: str = A0_RPC_PORT

# Common wallet credentials (used in multiple scripts)
WALLET1_NAME: str = "mining_wallet"
WALLET1_PASSWORD: str = "test123"
WALLET2_NAME: str = "recipient_wallet"
WALLET2_PASSWORD: str = "test456"

# Fallback addresses for error recovery (used if wallet RPC fails to provide addresses)
# These are standard testnet addresses that can be used for mining
WALLET1_ADDRESS_FALLBACK: str = "9tUBnwk5FUXVSKnVbXBjQESkLyS5eWjPHzq2KgQEz3Zcbc1G1oUBHx8Qpc9JnQMNDVQiUBNNopa5qKWuHEJQUW9b2xr2X3K"
WALLET2_ADDRESS_FALLBACK: str = "9tUBnwk5FUXVSKnVbXBjQESkLyS5eWjPHzq2KgQEz3Zcbc1G1oUBHx8Qpc9JnQMNDVQiUBNNopa5qKWuHEJQUW9b2xr2X3K"


def get_agent_registry(shared_dir: str = "/tmp/monerosim_shared") -> Dict[str, Any]:
    """Read the agent registry from the shared directory."""
    registry_path = f"{shared_dir}/agent_registry.json"
    try:
        with open(registry_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Try legacy path for backward compatibility
        legacy_path = f"{shared_dir}/node_registry.json"
        try:
            with open(legacy_path, "r") as f:
                log_warning(MODULE_NAME, f"Using legacy registry at {legacy_path}")
                return json.load(f)
        except FileNotFoundError:
            log_warning(MODULE_NAME, f"Agent registry not found at {registry_path} or {legacy_path}")
            return {"agents": []}
        except json.JSONDecodeError:
            log_warning(MODULE_NAME, f"Could not decode legacy registry at {legacy_path}")
            return {"agents": []}
    except json.JSONDecodeError:
        log_warning(MODULE_NAME, f"Could not decode agent registry at {registry_path}")
        return {"agents": []}

# For backward compatibility
def get_node_registry(shared_dir: str = "/tmp/monerosim_shared") -> Dict[str, Any]:
    """Legacy function for backward compatibility. Use get_agent_registry instead."""
    log_warning(MODULE_NAME, "get_node_registry is deprecated, use get_agent_registry instead")
    return get_agent_registry(shared_dir)

def get_daemon_config(agent_id: str = "user000") -> Dict[str, str]:
    """
    Get daemon configuration for a specific agent from the agent registry.
    
    Args:
        agent_id: Agent identifier (e.g., "user000", "user001")
        
    Returns:
        Dictionary containing IP, port, and RPC URL for the daemon
    """
    registry = get_agent_registry()
    for agent in registry.get("agents", []):
        if agent.get("agent_id") == agent_id or agent.get("id") == agent_id:
            # Handle both formats for backward compatibility
            ip_addr = agent.get("ip_addr")
            rpc_port = agent.get("agent_rpc_port") or agent.get("node_rpc_port")
            
            return {
                "ip": ip_addr,
                "port": rpc_port,
                "rpc_url": f"http://{ip_addr}:{rpc_port}/json_rpc"
            }
    raise ValueError(f"Unknown agent ID: {agent_id}")


def get_wallet_config(wallet_id: int) -> Dict[str, str]:
    """
    Get wallet configuration for a specific wallet.
    
    Args:
        wallet_id: Wallet identifier (1 or 2)
        
    Returns:
        Dictionary containing IP, port, RPC URL, name, password, and fallback address
    """
    if wallet_id == 1:
        return {
            "ip": WALLET1_IP,
            "port": WALLET1_RPC_PORT,
            "rpc_url": WALLET1_RPC,
            "name": WALLET1_NAME,
            "password": WALLET1_PASSWORD,
            "fallback_address": WALLET1_ADDRESS_FALLBACK
        }
    elif wallet_id == 2:
        return {
            "ip": WALLET2_IP,
            "port": WALLET2_RPC_PORT,
            "rpc_url": WALLET2_RPC,
            "name": WALLET2_NAME,
            "password": WALLET2_PASSWORD,
            "fallback_address": WALLET2_ADDRESS_FALLBACK
        }
    else:
        raise ValueError(f"Unknown wallet ID: {wallet_id}")


def get_all_config() -> Dict[str, Any]:
    """
    Get all network configuration as a dictionary.
    
    Returns:
        Dictionary containing all configuration values
    """
    return {
        # Daemon agents
        "A0_IP": A0_IP,
        "A0_RPC_PORT": A0_RPC_PORT,
        "A0_RPC": A0_RPC,
        "A1_IP": A1_IP,
        "A1_RPC_PORT": A1_RPC_PORT,
        "A1_RPC": A1_RPC,
        
        # Wallet agents
        "WALLET1_IP": WALLET1_IP,
        "WALLET1_RPC_PORT": WALLET1_RPC_PORT,
        "WALLET1_RPC": WALLET1_RPC,
        "WALLET2_IP": WALLET2_IP,
        "WALLET2_RPC_PORT": WALLET2_RPC_PORT,
        "WALLET2_RPC": WALLET2_RPC,
        
        # Backward compatibility
        "DAEMON_IP": DAEMON_IP,
        "DAEMON_RPC_PORT": DAEMON_RPC_PORT,
        
        # Wallet credentials
        "WALLET1_NAME": WALLET1_NAME,
        "WALLET1_PASSWORD": WALLET1_PASSWORD,
        "WALLET2_NAME": WALLET2_NAME,
        "WALLET2_PASSWORD": WALLET2_PASSWORD,
        
        # Fallback addresses
        "WALLET1_ADDRESS_FALLBACK": WALLET1_ADDRESS_FALLBACK,
        "WALLET2_ADDRESS_FALLBACK": WALLET2_ADDRESS_FALLBACK
    }


def print_config() -> None:
    """Print all configuration values for debugging purposes."""
    log_info(MODULE_NAME, "Network Configuration:")
    config = get_all_config()
    for key, value in sorted(config.items()):
        log_info(MODULE_NAME, f"  {key}: {value}")


# For direct script execution
if __name__ == "__main__":
    print_config()