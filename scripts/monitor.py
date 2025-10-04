#!/usr/bin/env python3
"""
monitor.py - Monitoring Script for MoneroSim

This script monitors the status of the Monero simulation, providing real-time
information about:
- Agent status and synchronization
- Blockchain height and growth
- Peer connections
- Mining status
- Transaction pool status
- System resource usage

This is a Python implementation that replaces the monitor_script.sh functionality.
It uses dynamic agent discovery to automatically find and monitor all agents
in the simulation without requiring hardcoded configurations.
"""

import sys
import time
import argparse
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# Dynamic Agent Discovery
# This script uses the AgentDiscovery class to automatically find and monitor
# all agents in the simulation without requiring hardcoded configurations.
# The discovery system reads agent information from the shared state directory
# (/tmp/monerosim_shared/) where agent registry files are stored.

# Handle imports for both direct execution and module import
try:
    from .error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_daemon_ready, handle_exit
    )
    from agents.agent_discovery import AgentDiscovery
except ImportError:
    # Fallback for when running as a script directly
    from error_handling import (
        log_info, log_warning, log_error, log_critical, log_success,
        call_daemon_with_retry, verify_daemon_ready, handle_exit
    )
    from agents.agent_discovery import AgentDiscovery

# Component name for logging
COMPONENT = "MONITOR"

# Default configuration
DEFAULT_REFRESH_INTERVAL = 10  # seconds
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 2


class AgentStatus:
    """Container for agent status information."""
    
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


def get_agent_info(agent_url: str, max_attempts: int, retry_delay: float) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive agent information.
    
    Args:
        agent_url: URL of the agent RPC endpoint
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        Dictionary with agent information or None if failed
    """
    success, response = call_daemon_with_retry(
        agent_url, "get_info", {}, max_attempts, retry_delay, COMPONENT
    )
    
    if success:
        return response.get("result", {})
    return None


def get_mining_status(agent_url: str, max_attempts: int, retry_delay: float) -> Optional[Dict[str, Any]]:
    """
    Get mining status from agent.
    
    Args:
        agent_url: URL of the agent RPC endpoint
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        Dictionary with mining status or None if failed
    """
    success, response = call_daemon_with_retry(
        agent_url, "mining_status", {}, max_attempts, retry_delay, COMPONENT
    )
    
    if success:
        return response.get("result", {})
    return None


def get_connections(agent_url: str, max_attempts: int, retry_delay: float) -> Optional[List[Dict[str, Any]]]:
    """
    Get peer connections from agent.
    
    Args:
        agent_url: URL of the agent RPC endpoint
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
        
    Returns:
        List of connections or None if failed
    """
    success, response = call_daemon_with_retry(
        agent_url, "get_connections", {}, max_attempts, retry_delay, COMPONENT
    )
    
    if success:
        return response.get("result", {}).get("connections", [])
    return None


def update_agent_status(agent: AgentStatus, max_attempts: int, retry_delay: float) -> None:
    """
    Update agent status with latest information.
    
    Args:
        agent: AgentStatus object to update
        max_attempts: Maximum number of attempts
        retry_delay: Delay between attempts
    """
    # Get basic agent info
    info = get_agent_info(agent.url, max_attempts, retry_delay)
    if info:
        agent.height = info.get("height", 0)
        agent.target_height = info.get("target_height", 0)
        agent.difficulty = info.get("difficulty", 0)
        agent.tx_count = info.get("tx_count", 0)
        agent.tx_pool_size = info.get("tx_pool_size", 0)
        agent.incoming_connections = info.get("incoming_connections_count", 0)
        agent.outgoing_connections = info.get("outgoing_connections_count", 0)
        agent.white_peerlist_size = info.get("white_peerlist_size", 0)
        agent.grey_peerlist_size = info.get("grey_peerlist_size", 0)
        agent.status = info.get("status", "unknown")
        agent.synchronized = info.get("synchronized", False)
        agent.cumulative_difficulty = info.get("cumulative_difficulty", 0)
        agent.top_block_hash = info.get("top_block_hash", "")
        agent.block_reward = info.get("block_reward", 0)
        agent.error = None
    else:
        agent.error = "Failed to get agent info"
    
    # Get mining status (may not be available in regtest mode)
    mining_status = get_mining_status(agent.url, max_attempts, retry_delay)
    if mining_status:
        agent.mining_active = mining_status.get("active", False)
        agent.hashrate = mining_status.get("speed", 0)
    else:
        # Mining status might not be available (e.g., in regtest mode)
        # This is not an error, just unavailable information
        log_info(COMPONENT, f"Mining status not available for {agent.name} (this is normal in regtest mode)")
    
    agent.last_update = datetime.now()


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


def print_agent_status(agent: AgentStatus, verbose: bool = False) -> None:
    """
    Print formatted agent status.
    
    Args:
        agent: AgentStatus object to print
        verbose: Whether to print verbose output
    """
    print(f"\n{'='*60}")
    print(f"Agent: {agent.name}")
    print(f"{'='*60}")
    
    if agent.error:
        print(f"ERROR: {agent.error}")
        return
    
    # Basic info
    print(f"Status: {agent.status}")
    print(f"Synchronized: {'Yes' if agent.synchronized else 'No'}")
    print(f"Height: {agent.height:,} / {agent.target_height:,}")
    if agent.target_height > 0:
        sync_percent = (agent.height / agent.target_height) * 100
        print(f"Sync Progress: {sync_percent:.1f}%")
    
    # Mining info
    if agent.mining_active:
        print(f"Mining: Active ({format_hashrate(agent.hashrate)})")
    else:
        print(f"Mining: Inactive")
    
    # Network info
    print(f"Connections: {agent.incoming_connections} in / {agent.outgoing_connections} out")
    print(f"Peer Lists: {agent.white_peerlist_size} white / {agent.grey_peerlist_size} grey")
    
    # Transaction pool
    print(f"TX Pool: {agent.tx_pool_size} transactions")
    print(f"Total TXs: {agent.tx_count:,}")
    
    # Blockchain info
    print(f"Difficulty: {agent.difficulty:,}")
    if agent.block_reward > 0:
        reward_xmr = agent.block_reward / 1e12
        print(f"Block Reward: {reward_xmr:.12f} XMR")
    
    # Verbose information
    if verbose:
        print(f"\nVerbose Details:")
        print(f"URL: {agent.url}")
        print(f"Cumulative Difficulty: {agent.cumulative_difficulty:,}")
        if agent.top_block_hash:
            print(f"Top Block Hash: {agent.top_block_hash[:16]}...")
    
    # Last update
    if agent.last_update:
        print(f"Last Update: {agent.last_update.strftime('%Y-%m-%d %H:%M:%S')}")


def print_comparison(agents: List[AgentStatus]) -> None:
    """
    Print comparison between agents.
    
    Args:
        agents: List of AgentStatus objects to compare
    """
    if len(agents) < 2:
        return
    
    print(f"\n{'='*60}")
    print("Agent Comparison")
    print(f"{'='*60}")
    
    # Height comparison
    heights = [(n.name, n.height) for n in agents if not n.error]
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
    for agent in agents:
        if not agent.error:
            total_conn = agent.incoming_connections + agent.outgoing_connections
            print(f"  {agent.name}: {total_conn} total ({agent.incoming_connections} in / {agent.outgoing_connections} out)")
    
    # Mining status
    print("\nMining Status:")
    for agent in agents:
        if not agent.error:
            if agent.mining_active:
                print(f"  {agent.name}: Active ({format_hashrate(agent.hashrate)})")
            else:
                print(f"  {agent.name}: Inactive")


def monitor_loop(agents: List[AgentStatus], refresh_interval: int,
                max_attempts: int, retry_delay: float,
                clear_screen: bool = True, verbose: bool = False) -> None:
    """
    Main monitoring loop.
    
    Args:
        agents: List of AgentStatus objects to monitor
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
            
            # Update all agents
            for agent in agents:
                update_agent_status(agent, max_attempts, retry_delay)
            
            # Print status for each agent
            for agent in agents:
                print_agent_status(agent, verbose)
            
            # Print comparison
            print_comparison(agents)
            
            print(f"\nRefreshing in {refresh_interval} seconds... (Press Ctrl+C to stop)")
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        log_info(COMPONENT, "Monitoring stopped by user")


def main():
    """Main function for monitor script."""
    parser = argparse.ArgumentParser(
        description="Monitor Monero agents in Shadow simulation using dynamic agent discovery"
    )
    
    # Add command line arguments
    parser.add_argument(
        "--agents",
        nargs="+",
        help="List of agents to monitor (format: name=url). If not specified, agents will be discovered automatically.",
        default=None
    )
    # For backward compatibility
    parser.add_argument(
        "--nodes",
        nargs="+",
        help="[DEPRECATED] Use --agents instead. List of nodes to monitor (format: name=url)",
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
    
    args, _ = parser.parse_known_args()
    
    # Handle interval alias
    if args.interval is not None:
        args.refresh = args.interval
    
    log_info(COMPONENT, "=== MoneroSim Monitor ===")
    log_info(COMPONENT, f"Starting monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Parse agents
    agents = []
    
    # Handle both --agents and --nodes (for backward compatibility)
    agent_specs = args.agents or args.nodes
    
    if agent_specs:
        if args.nodes and not args.agents:
            log_warning(COMPONENT, "The --nodes parameter is deprecated. Please use --agents instead.")
            
        for agent_spec in agent_specs:
            if "=" in agent_spec:
                name, url = agent_spec.split("=", 1)
                agents.append(AgentStatus(name, url))
            else:
                log_error(COMPONENT, f"Invalid agent specification: {agent_spec}")
                log_error(COMPONENT, "Use format: name=url")
                handle_exit(1, COMPONENT, "Invalid agent specification")
    else:
        # Default agents from dynamic discovery
        try:
            discovery = AgentDiscovery()
            registry = discovery.get_agent_registry()
            
            # Get all agents from the registry
            agents_data = registry.get("agents", [])
            
            # Handle both list and dictionary formats
            if isinstance(agents_data, list):
                for agent_data in agents_data:
                    # Handle both formats for backward compatibility
                    agent_id = agent_data.get("agent_id") or agent_data.get("id")
                    ip_addr = agent_data.get("ip_addr")
                    rpc_port = agent_data.get("agent_rpc_port") or agent_data.get("node_rpc_port")
                    
                    if agent_id and ip_addr and rpc_port:
                        agents.append(AgentStatus(agent_id, f"http://{ip_addr}:{rpc_port}/json_rpc"))
            elif isinstance(agents_data, dict):
                for agent_id, agent_data in agents_data.items():
                    ip_addr = agent_data.get("ip_addr")
                    rpc_port = agent_data.get("agent_rpc_port") or agent_data.get("node_rpc_port")
                    
                    if ip_addr and rpc_port:
                        agents.append(AgentStatus(agent_id, f"http://{ip_addr}:{rpc_port}/json_rpc"))
            
            if not agents:
                log_warning(COMPONENT, "No agents found in registry. The simulation may not be running.")
                log_info(COMPONENT, "Use --agents parameter to specify agents manually.")
                
        except Exception as e:
            log_error(COMPONENT, f"Failed to discover agents: {e}")
            log_info(COMPONENT, "Use --agents parameter to specify agents manually.")
    
    log_info(COMPONENT, f"Monitoring {len(agents)} agents")
    
    # If no agents were discovered and none were specified manually, exit with error
    if not agents:
        log_error(COMPONENT, "No agents to monitor")
        log_info(COMPONENT, "Please specify agents with --agents parameter or ensure the simulation is running")
        handle_exit(1, COMPONENT, "No agents to monitor")
    
    # Verify all agents are reachable
    all_ready = True
    unreachable_agents = []
    
    for agent in agents:
        if not verify_daemon_ready(agent.url, agent.name, args.max_attempts,
                                  args.retry_delay, COMPONENT):
            log_error(COMPONENT, f"Agent {agent.name} is not ready")
            unreachable_agents.append(agent.name)
            all_ready = False
    
    if not all_ready:
        log_error(COMPONENT, f"Unreachable agents: {', '.join(unreachable_agents)}")
        if len(unreachable_agents) == len(agents):
            log_error(COMPONENT, "All agents are unreachable. The simulation may not be running.")
            log_info(COMPONENT, "Please check if the Shadow simulation is active and agents are properly configured.")
        handle_exit(1, COMPONENT, "Not all agents are ready")
    
    if args.once:
        # Single run mode
        log_info(COMPONENT, "Running single status check")
        
        # Update all agents
        for agent in agents:
            update_agent_status(agent, args.max_attempts, args.retry_delay)
        
        # Print status
        for agent in agents:
            print_agent_status(agent, args.verbose)
        
        # Print comparison
        print_comparison(agents)
        
        log_info(COMPONENT, "Monitor check completed")
        handle_exit(0, COMPONENT, "Single run completed successfully")
    else:
        # Continuous monitoring mode
        log_info(COMPONENT, f"Starting continuous monitoring (refresh every {args.refresh} seconds)")
        monitor_loop(agents, args.refresh, args.max_attempts, args.retry_delay,
                    not args.no_clear, args.verbose)
        
        handle_exit(0, COMPONENT, "Monitoring stopped")


if __name__ == "__main__":
    main()