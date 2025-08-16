#!/usr/bin/env python3
"""
Agent Discovery Module for Monerosim

This module provides a comprehensive agent discovery system that replaces the legacy 
hardcoded network configuration approach. It enables dynamic agent discovery and 
supports scaling to hundreds of agents.

The module reads agent information from the shared state directory 
(/tmp/monerosim_shared/) where agent registry files are stored.
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import time

try:
    from .error_handling import ErrorHandler, LogLevel
except ImportError:
    # Fallback for when running as a script directly
    from error_handling import ErrorHandler, LogLevel


class AgentDiscoveryError(Exception):
    """Exception raised for agent discovery related errors."""
    pass


class AgentDiscovery:
    """
    A comprehensive agent discovery system for Monerosim that enables dynamic 
    agent discovery and supports scaling to hundreds of agents.
    
    This class provides methods to discover and filter agents based on various 
    criteria such as type, attributes, and capabilities.
    """
    
    def __init__(self, shared_state_dir: str = "/tmp/monerosim_shared"):
        """
        Initialize the AgentDiscovery with the shared state directory.
        
        Args:
            shared_state_dir: Path to the directory containing agent registry files.
                            Defaults to "/tmp/monerosim_shared".
        """
        self.shared_state_dir = Path(shared_state_dir)
        self.logger = self._setup_logger()
        self._registry_cache: Optional[Dict[str, Any]] = None
        self._registry_cache_time: float = 0
        self.cache_ttl = 5  # Cache TTL in seconds
        
        # Ensure the shared state directory exists
        try:
            self.shared_state_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"AgentDiscovery initialized with shared state directory: {self.shared_state_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create shared state directory: {e}")
            raise AgentDiscoveryError(f"Failed to create shared state directory: {e}")
    
    def _setup_logger(self) -> logging.Logger:
        """
        Set up a logger for the AgentDiscovery class.
        
        Returns:
            Configured logger instance.
        """
        logger = logging.getLogger("AgentDiscovery")
        
        # Set default level if not already configured
        if not logger.handlers:
            logger.setLevel(logging.DEBUG)
            
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            
            # Add handler to logger
            logger.addHandler(console_handler)
        
        return logger
    
    def _is_cache_valid(self) -> bool:
        """
        Check if the registry cache is still valid based on TTL.
        
        Returns:
            True if cache is valid, False otherwise.
        """
        return (time.time() - self._registry_cache_time) < self.cache_ttl
    
    def _load_registry_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Load and parse a registry file with error handling.
        
        Args:
            file_path: Path to the registry file.
            
        Returns:
            Parsed registry data.
            
        Raises:
            AgentDiscoveryError: If the file cannot be loaded or parsed.
        """
        try:
            if not file_path.exists():
                self.logger.warning(f"Registry file not found: {file_path}")
                return {}
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.logger.debug(f"Successfully loaded registry file: {file_path}")
            return data
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in registry file {file_path}: {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to load registry file {file_path}: {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def get_agent_registry(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Load and return the agent registry from the shared state directory.
        
        This method aggregates information from all registry files in the shared
        state directory and provides a unified view of all agents.
        
        Args:
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            Dictionary containing agent registry information.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        # Return cached data if valid and not forcing refresh
        if not force_refresh and self._registry_cache is not None and self._is_cache_valid():
            self.logger.debug("Returning cached agent registry")
            return self._registry_cache
        
        self.logger.info("Loading agent registry from shared state directory")
        
        try:
            registry = {
                "agents": {},
                "miners": {},
                "wallets": {},
                "block_controllers": {},
                "last_updated": time.time()
            }
            
            # Load all JSON files in the shared state directory
            for file_path in self.shared_state_dir.glob("*.json"):
                try:
                    data = self._load_registry_file(file_path)
                    filename = file_path.stem
                    
                    # Categorize registry files based on naming conventions
                    if filename == "agent_registry":
                        # Extract the agents list from the registry data
                        if isinstance(data, dict) and "agents" in data:
                            registry["agents"] = data["agents"]
                            self.logger.debug(f"Loaded agent_registry agents as {type(data['agents'])} with {len(data['agents']) if isinstance(data['agents'], (list, dict)) else 0} items")
                        else:
                            registry["agents"] = data
                            self.logger.debug(f"Loaded agent_registry as {type(data)} with {len(data) if isinstance(data, (list, dict)) else 0} items")
                    elif filename == "miners":
                        # Handle both dictionary and list formats
                        if isinstance(data, dict):
                            registry["miners"] = data
                        elif isinstance(data, list):
                            # Convert list to dictionary with indices as keys
                            registry["miners"] = {str(i): miner for i, miner in enumerate(data)}
                        else:
                            self.logger.warning(f"Unexpected data format in miners: {type(data)}")
                            registry["miners"] = {}
                    elif filename == "wallets":
                        # Handle both dictionary and list formats
                        if isinstance(data, dict):
                            registry["wallets"] = data
                        elif isinstance(data, list):
                            # Convert list to dictionary with indices as keys
                            registry["wallets"] = {str(i): wallet for i, wallet in enumerate(data)}
                        else:
                            self.logger.warning(f"Unexpected data format in wallets: {type(data)}")
                            registry["wallets"] = {}
                    elif filename == "block_controller":
                        # Handle both dictionary and list formats
                        if isinstance(data, dict):
                            registry["block_controllers"] = data
                        elif isinstance(data, list):
                            # Convert list to dictionary with indices as keys
                            registry["block_controllers"] = {str(i): controller for i, controller in enumerate(data)}
                        else:
                            self.logger.warning(f"Unexpected data format in block_controller: {type(data)}")
                            registry["block_controllers"] = {}
                    else:
                        # Handle other registry files
                        if filename not in registry:
                            registry[filename] = data
                        else:
                            registry[filename].update(data)
                            
                except AgentDiscoveryError:
                    # Log the error but continue processing other files
                    continue
            
            # Update cache
            self._registry_cache = registry
            self._registry_cache_time = time.time()
            
            self.logger.info(f"Successfully loaded agent registry with {len(registry['agents'])} agents")
            return registry
            
        except Exception as e:
            error_msg = f"Failed to load agent registry: {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def find_agents_by_type(self, agent_type: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Return all agents of a specific type.
        
        Args:
            agent_type: The type of agents to find (e.g., "miner", "user", "wallet").
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            List of agent dictionaries matching the specified type.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.debug(f"Finding agents by type: {agent_type}")
        
        try:
            registry = self.get_agent_registry(force_refresh)
            agents = registry.get("agents", [])
            
            self.logger.debug(f"Agents type: {type(agents)}")
            self.logger.debug(f"Registry keys: {list(registry.keys())}")
            
            matching_agents = []
            
            # Handle both list and dictionary formats
            if isinstance(agents, list):
                self.logger.debug(f"Processing agents as list with {len(agents)} items")
                for agent_data in agents:
                    if agent_data.get("type") == agent_type:
                        agent_copy = agent_data.copy()
                        # Ensure ID is present
                        if "id" not in agent_copy and "agent_id" in agent_copy:
                            agent_copy["id"] = agent_copy["agent_id"]
                        matching_agents.append(agent_copy)
            elif isinstance(agents, dict):
                self.logger.debug(f"Processing agents as dict with {len(agents)} items")
                for agent_id, agent_data in agents.items():
                    if agent_data.get("type") == agent_type:
                        agent_copy = agent_data.copy()
                        agent_copy["id"] = agent_id
                        matching_agents.append(agent_copy)
            
            self.logger.info(f"Found {len(matching_agents)} agents of type '{agent_type}'")
            return matching_agents
            
        except Exception as e:
            error_msg = f"Failed to find agents by type '{agent_type}': {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def find_agents_by_attribute(
        self,
        attribute_name: str,
        attribute_value: Any,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Return agents matching a specific attribute value.
        
        Args:
            attribute_name: The name of the attribute to match.
            attribute_value: The value of the attribute to match.
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            List of agent dictionaries matching the specified attribute.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.debug(f"Finding agents by attribute: {attribute_name}={attribute_value}")
        
        try:
            registry = self.get_agent_registry(force_refresh)
            agents = registry.get("agents", [])
            
            matching_agents = []
            
            # Handle both list and dictionary formats
            if isinstance(agents, list):
                for agent_data in agents:
                    attributes = agent_data.get("attributes", {})
                    if attributes.get(attribute_name) == attribute_value:
                        agent_copy = agent_data.copy()
                        # Ensure ID is present
                        if "id" not in agent_copy and "agent_id" in agent_copy:
                            agent_copy["id"] = agent_copy["agent_id"]
                        matching_agents.append(agent_copy)
            elif isinstance(agents, dict):
                for agent_id, agent_data in agents.items():
                    attributes = agent_data.get("attributes", {})
                    if attributes.get(attribute_name) == attribute_value:
                        agent_copy = agent_data.copy()
                        agent_copy["id"] = agent_id
                        matching_agents.append(agent_copy)
            
            self.logger.info(f"Found {len(matching_agents)} agents with {attribute_name}={attribute_value}")
            return matching_agents
            
        except Exception as e:
            error_msg = f"Failed to find agents by attribute '{attribute_name}': {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def get_miner_agents(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Return all agents that are miners.
        
        Args:
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            List of miner agent dictionaries.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.debug("Getting miner agents")
        
        try:
            # Try to find miners by type first
            miners = self.find_agents_by_type("miner", force_refresh)
            
            # If no miners found by type, try to find by attribute
            if not miners:
                miners = self.find_agents_by_attribute("is_miner", True, force_refresh=force_refresh)
            
            # Also check the dedicated miners registry
            if not miners:
                registry = self.get_agent_registry(force_refresh)
                miners_data = registry.get("miners", {})
                
                self.logger.debug(f"Miners data type: {type(miners_data)}")
                
                # Handle the case where miners_data is a dict with a 'miners' key
                if isinstance(miners_data, dict) and "miners" in miners_data:
                    miners_list = miners_data["miners"]
                    self.logger.debug(f"Processing miners list with {len(miners_list)} items")
                    if isinstance(miners_list, list):
                        for i, miner_data in enumerate(miners_list):
                            if isinstance(miner_data, dict):
                                miner_copy = miner_data.copy()
                                # Ensure ID is present
                                if "id" not in miner_copy and "agent_id" in miner_copy:
                                    miner_copy["id"] = miner_copy["agent_id"]
                                elif "id" not in miner_copy:
                                    miner_copy["id"] = f"miner_{i}"
                                miners.append(miner_copy)
                # Handle both list and dictionary formats
                elif isinstance(miners_data, list):
                    self.logger.debug(f"Processing miners as list with {len(miners_data)} items")
                    for i, miner_data in enumerate(miners_data):
                        miner_copy = miner_data.copy()
                        # Ensure ID is present
                        if "id" not in miner_copy and "agent_id" in miner_copy:
                            miner_copy["id"] = miner_copy["agent_id"]
                        elif "id" not in miner_copy:
                            miner_copy["id"] = f"miner_{i}"
                        miners.append(miner_copy)
                elif isinstance(miners_data, dict):
                    self.logger.debug(f"Processing miners as dict with {len(miners_data)} items")
                    for miner_id, miner_data in miners_data.items():
                        miner_copy = miner_data.copy()
                        miner_copy["id"] = miner_id
                        miners.append(miner_copy)
                else:
                    self.logger.warning(f"Unexpected miners data type: {type(miners_data)}")
            
            # If we still don't have miners, look for agents with is_miner attribute in the main agents list
            if not miners:
                registry = self.get_agent_registry(force_refresh)
                agents = registry.get("agents", [])
                
                if isinstance(agents, list):
                    for agent_data in agents:
                        attributes = agent_data.get("attributes", {})
                        if str(attributes.get("is_miner", "")).lower() == "true":
                            miner_copy = agent_data.copy()
                            # Ensure ID is present
                            if "id" not in miner_copy and "agent_id" in miner_copy:
                                miner_copy["id"] = miner_copy["agent_id"]
                            miners.append(miner_copy)
            
            # If we have miners from the miners registry but they lack port information,
            # try to enrich them with data from the main agents list
            if miners:
                registry = self.get_agent_registry(force_refresh)
                agents = registry.get("agents", [])
                
                # Log the structure of the agents data
                self.logger.debug(f"Agents data type: {type(agents)}")
                if isinstance(agents, dict):
                    self.logger.debug(f"Agents dict keys: {list(agents.keys())}")
                    if agents:
                        first_key = next(iter(agents))
                        self.logger.debug(f"First agent keys: {list(agents[first_key].keys())}")
                elif isinstance(agents, list) and agents:
                    self.logger.debug(f"First agent keys: {list(agents[0].keys())}")
                
                # Create a mapping of agent IP addresses to agent data for quick lookup
                # since miners.json uses IP addresses as identifiers
                agent_ip_map = {}
                
                if isinstance(agents, list):
                    for agent_data in agents:
                        ip_addr = agent_data.get("ip_addr")
                        if ip_addr:
                            agent_ip_map[ip_addr] = agent_data
                            self.logger.debug(f"Added agent with IP {ip_addr} to map")
                elif isinstance(agents, dict):
                    for agent_id, agent_data in agents.items():
                        ip_addr = agent_data.get("ip_addr")
                        if ip_addr:
                            agent_ip_map[ip_addr] = agent_data
                            self.logger.debug(f"Added agent with IP {ip_addr} to map")
                
                self.logger.debug(f"Created agent IP map with {len(agent_ip_map)} entries")
                self.logger.debug(f"Agent IP map keys: {list(agent_ip_map.keys())}")
                
                # Enrich miner data with port information from the main agents list
                for miner in miners:
                    miner_ip = miner.get("ip_addr")
                    miner_id = miner.get("id")
                    self.logger.debug(f"Processing miner {miner_id} with IP {miner_ip} and keys: {list(miner.keys())}")
                    
                    if miner_ip and miner_ip in agent_ip_map:
                        agent_data = agent_ip_map[miner_ip]
                        self.logger.debug(f"Found matching agent with keys: {list(agent_data.keys())}")
                        
                        # Copy port information if not already present
                        if "daemon_rpc_port" not in miner and "daemon_rpc_port" in agent_data:
                            miner["daemon_rpc_port"] = agent_data["daemon_rpc_port"]
                            self.logger.debug(f"Added daemon_rpc_port: {agent_data['daemon_rpc_port']}")
                        if "agent_rpc_port" not in miner and "agent_rpc_port" in agent_data:
                            miner["agent_rpc_port"] = agent_data["agent_rpc_port"]
                            self.logger.debug(f"Added agent_rpc_port: {agent_data['agent_rpc_port']}")
                        if "wallet_rpc_port" not in miner and "wallet_rpc_port" in agent_data:
                            miner["wallet_rpc_port"] = agent_data["wallet_rpc_port"]
                            self.logger.debug(f"Added wallet_rpc_port: {agent_data['wallet_rpc_port']}")
                        # Also add the agent_id for future reference
                        if "agent_id" not in miner and "id" in agent_data:
                            miner["agent_id"] = agent_data["id"]
                            self.logger.debug(f"Added agent_id: {agent_data['id']}")
                    else:
                        self.logger.debug(f"No matching agent found for miner with IP {miner_ip}")
                        self.logger.debug(f"Available IPs in map: {list(agent_ip_map.keys())}")
            
            self.logger.info(f"Found {len(miners)} miner agents")
            return miners
            
        except Exception as e:
            error_msg = f"Failed to get miner agents: {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def get_wallet_agents(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Return all agents that have wallets.
        
        Args:
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            List of wallet agent dictionaries.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.debug("Getting wallet agents")
        
        try:
            # Try to find wallets by type first
            wallets = self.find_agents_by_type("wallet", force_refresh)
            
            # If no wallets found by type, try to find by attribute
            if not wallets:
                wallets = self.find_agents_by_attribute("has_wallet", True, force_refresh)
            
            # Also check the dedicated wallets registry
            if not wallets:
                registry = self.get_agent_registry(force_refresh)
                wallets_data = registry.get("wallets", {})
                
                # Handle both dictionary and list formats
                if isinstance(wallets_data, dict):
                    for wallet_id, wallet_data in wallets_data.items():
                        if isinstance(wallet_data, dict):
                            wallet_copy = wallet_data.copy()
                            wallet_copy["id"] = wallet_id
                            wallets.append(wallet_copy)
                elif isinstance(wallets_data, list):
                    for i, wallet_data in enumerate(wallets_data):
                        if isinstance(wallet_data, dict):
                            wallet_copy = wallet_data.copy()
                            # Ensure ID is present
                            if "id" not in wallet_copy and "wallet_id" in wallet_copy:
                                wallet_copy["id"] = wallet_copy["wallet_id"]
                            elif "id" not in wallet_copy:
                                wallet_copy["id"] = f"wallet_{i}"
                            wallets.append(wallet_copy)
            
            # Also check agents that have wallet information
            if not wallets:
                registry = self.get_agent_registry(force_refresh)
                agents = registry.get("agents", [])
                
                # Handle both list and dictionary formats
                if isinstance(agents, list):
                    for agent_data in agents:
                        if "wallet" in agent_data or "wallet_rpc" in agent_data:
                            agent_copy = agent_data.copy()
                            # Ensure ID is present
                            if "id" not in agent_copy and "agent_id" in agent_copy:
                                agent_copy["id"] = agent_copy["agent_id"]
                            wallets.append(agent_copy)
                elif isinstance(agents, dict):
                    for agent_id, agent_data in agents.items():
                        if "wallet" in agent_data or "wallet_rpc" in agent_data:
                            agent_copy = agent_data.copy()
                            agent_copy["id"] = agent_id
                            wallets.append(agent_copy)
            
            self.logger.info(f"Found {len(wallets)} wallet agents")
            return wallets
            
        except Exception as e:
            error_msg = f"Failed to get wallet agents: {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def get_block_controllers(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Return all block controller agents.
        
        Args:
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            List of block controller agent dictionaries.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.debug("Getting block controller agents")
        
        try:
            # Try to find block controllers by type first
            controllers = self.find_agents_by_type("block_controller", force_refresh)
            
            # If no controllers found by type, check the dedicated registry
            if not controllers:
                registry = self.get_agent_registry(force_refresh)
                controllers_data = registry.get("block_controllers", {})
                
                for controller_id, controller_data in controllers_data.items():
                    controller_copy = controller_data.copy()
                    controller_copy["id"] = controller_id
                    controllers.append(controller_copy)
            
            self.logger.info(f"Found {len(controllers)} block controller agents")
            return controllers
            
        except Exception as e:
            error_msg = f"Failed to get block controller agents: {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def get_agent_by_id(self, agent_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a specific agent by its ID.
        
        Args:
            agent_id: The ID of the agent to retrieve.
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            Agent dictionary if found, None otherwise.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.debug(f"Getting agent by ID: {agent_id}")
        
        try:
            registry = self.get_agent_registry(force_refresh)
            agents = registry.get("agents", [])
            
            # Handle both list and dictionary formats
            if isinstance(agents, list):
                for agent_data in agents:
                    if agent_data.get("id") == agent_id:
                        return agent_data.copy()
            elif isinstance(agents, dict):
                if agent_id in agents:
                    agent_data = agents[agent_id].copy()
                    agent_data["id"] = agent_id
                    return agent_data
            
            # Check other registries if not found in main agents registry
            for registry_name, registry_data in registry.items():
                if registry_name != "agents":
                    if isinstance(registry_data, dict):
                        if agent_id in registry_data:
                            agent_data = registry_data[agent_id].copy()
                            agent_data["id"] = agent_id
                            return agent_data
                    elif isinstance(registry_data, list):
                        for agent_data in registry_data:
                            if agent_data.get("id") == agent_id:
                                return agent_data.copy()
            
            self.logger.warning(f"Agent with ID '{agent_id}' not found")
            return None
            
        except Exception as e:
            error_msg = f"Failed to get agent by ID '{agent_id}': {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)
    
    def refresh_cache(self) -> Dict[str, Any]:
        """
        Force refresh the agent registry cache.
        
        Returns:
            Updated agent registry.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.info("Forcing cache refresh")
        return self.get_agent_registry(force_refresh=True)
    
    def get_registry_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get statistics about the agent registry.
        
        Args:
            force_refresh: If True, bypass the cache and reload from disk.
            
        Returns:
            Dictionary containing registry statistics.
            
        Raises:
            AgentDiscoveryError: If the registry cannot be loaded.
        """
        self.logger.debug("Getting registry statistics")
        
        try:
            registry = self.get_agent_registry(force_refresh)
            
            # Get agents and handle both list and dictionary formats
            agents = registry.get("agents", [])
            if isinstance(agents, dict):
                agents = list(agents.values())
            
            # Get miners and handle both list and dictionary formats
            miners = registry.get("miners", [])
            if isinstance(miners, dict):
                miners = list(miners.values())
            
            # Get wallets and handle both list and dictionary formats
            wallets = registry.get("wallets", [])
            if isinstance(wallets, dict):
                wallets = list(wallets.values())
            
            # Get block controllers and handle both list and dictionary formats
            block_controllers = registry.get("block_controllers", [])
            if isinstance(block_controllers, dict):
                block_controllers = list(block_controllers.values())
            
            stats = {
                "total_agents": len(agents),
                "total_miners": len(miners),
                "total_wallets": len(wallets),
                "total_block_controllers": len(block_controllers),
                "last_updated": registry.get("last_updated", 0),
                "cache_time": self._registry_cache_time,
                "cache_valid": self._is_cache_valid()
            }
            
            # Count agents by type
            agent_types = {}
            for agent_data in agents:
                agent_type = agent_data.get("type", "unknown")
                agent_types[agent_type] = agent_types.get(agent_type, 0) + 1
            
            stats["agent_types"] = agent_types
            
            self.logger.info(f"Registry stats: {stats}")
            return stats
            
        except Exception as e:
            error_msg = f"Failed to get registry stats: {e}"
            self.logger.error(error_msg)
            raise AgentDiscoveryError(error_msg)


# Convenience functions for direct usage
def get_agent_registry(shared_state_dir: str = "/tmp/monerosim_shared") -> Dict[str, Any]:
    """
    Convenience function to get the agent registry.
    
    Args:
        shared_state_dir: Path to the shared state directory.
        
    Returns:
        Agent registry dictionary.
    """
    discovery = AgentDiscovery(shared_state_dir)
    return discovery.get_agent_registry()


def find_agents_by_type(
    agent_type: str, 
    shared_state_dir: str = "/tmp/monerosim_shared"
) -> List[Dict[str, Any]]:
    """
    Convenience function to find agents by type.
    
    Args:
        agent_type: The type of agents to find.
        shared_state_dir: Path to the shared state directory.
        
    Returns:
        List of matching agent dictionaries.
    """
    discovery = AgentDiscovery(shared_state_dir)
    return discovery.find_agents_by_type(agent_type)


def find_agents_by_attribute(
    attribute_name: str, 
    attribute_value: Any, 
    shared_state_dir: str = "/tmp/monerosim_shared"
) -> List[Dict[str, Any]]:
    """
    Convenience function to find agents by attribute.
    
    Args:
        attribute_name: The name of the attribute to match.
        attribute_value: The value of the attribute to match.
        shared_state_dir: Path to the shared state directory.
        
    Returns:
        List of matching agent dictionaries.
    """
    discovery = AgentDiscovery(shared_state_dir)
    return discovery.find_agents_by_attribute(attribute_name, attribute_value)


def get_miner_agents(shared_state_dir: str = "/tmp/monerosim_shared") -> List[Dict[str, Any]]:
    """
    Convenience function to get miner agents.
    
    Args:
        shared_state_dir: Path to the shared state directory.
        
    Returns:
        List of miner agent dictionaries.
    """
    discovery = AgentDiscovery(shared_state_dir)
    return discovery.get_miner_agents()


def get_wallet_agents(shared_state_dir: str = "/tmp/monerosim_shared") -> List[Dict[str, Any]]:
    """
    Convenience function to get wallet agents.
    
    Args:
        shared_state_dir: Path to the shared state directory.
        
    Returns:
        List of wallet agent dictionaries.
    """
    discovery = AgentDiscovery(shared_state_dir)
    return discovery.get_wallet_agents()


if __name__ == "__main__":
    # Example usage
    try:
        discovery = AgentDiscovery()
        
        # Get all agents
        registry = discovery.get_agent_registry()
        print(f"Registry: {json.dumps(registry, indent=2)}")
        
        # Get miner agents
        miners = discovery.get_miner_agents()
        print(f"Miners: {json.dumps(miners, indent=2)}")
        
        # Get wallet agents
        wallets = discovery.get_wallet_agents()
        print(f"Wallets: {json.dumps(wallets, indent=2)}")
        
        # Get registry stats
        stats = discovery.get_registry_stats()
        print(f"Stats: {json.dumps(stats, indent=2)}")
        
    except Exception as e:
        print(f"Error: {e}")