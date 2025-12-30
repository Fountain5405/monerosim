#!/usr/bin/env python3
"""
Public Node Discovery for Wallet-Only Agents

Provides daemon selection strategies for wallet-only agents
connecting to remote public nodes.
"""

import json
import random
import time
import fcntl
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum


class DaemonSelectionStrategy(Enum):
    """Strategies for selecting a daemon from available public nodes."""
    RANDOM = "random"
    FIRST = "first"
    ROUND_ROBIN = "round_robin"


class PublicNodeDiscovery:
    """Discover and select public nodes for wallet-only agents."""

    def __init__(self, shared_dir: Path = Path("/tmp/monerosim_shared")):
        """
        Initialize the public node discovery service.

        Args:
            shared_dir: Path to the shared directory containing public_nodes.json
        """
        self.shared_dir = shared_dir
        self.logger = logging.getLogger(f"PublicNodeDiscovery")
        self._round_robin_index = 0
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_time: float = 0
        self._cache_ttl: int = 5  # seconds

    def get_public_nodes(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of available public nodes.

        Args:
            force_refresh: If True, bypass cache and reload from disk

        Returns:
            List of public node dictionaries with agent_id, ip_addr, rpc_port, etc.
        """
        # Check cache validity
        if not force_refresh and self._cache is not None:
            if (time.time() - self._cache_time) < self._cache_ttl:
                return self._cache

        registry_path = self.shared_dir / "public_nodes.json"

        if not registry_path.exists():
            self.logger.warning("Public nodes registry not found at %s", registry_path)
            return []

        try:
            with open(registry_path, 'r') as f:
                registry = json.load(f)

            # Filter to available nodes
            nodes = registry.get("nodes", [])
            available_nodes = [
                node for node in nodes
                if node.get("status") == "available"
            ]

            # Update cache
            self._cache = available_nodes
            self._cache_time = time.time()

            self.logger.debug("Found %d available public nodes", len(available_nodes))
            return available_nodes

        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse public nodes registry: %s", e)
            return []
        except Exception as e:
            self.logger.error("Failed to read public nodes registry: %s", e)
            return []

    def select_daemon(
        self,
        strategy: DaemonSelectionStrategy = DaemonSelectionStrategy.RANDOM,
        exclude_ids: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Select a daemon address based on the specified strategy.

        Args:
            strategy: The selection strategy to use
            exclude_ids: List of agent IDs to exclude from selection

        Returns:
            Daemon address in "ip:port" format, or None if no nodes available
        """
        nodes = self.get_public_nodes()

        # Filter out excluded nodes
        if exclude_ids:
            nodes = [n for n in nodes if n["agent_id"] not in exclude_ids]

        if not nodes:
            self.logger.warning("No public nodes available for selection")
            return None

        selected_node = None

        if strategy == DaemonSelectionStrategy.RANDOM:
            selected_node = random.choice(nodes)

        elif strategy == DaemonSelectionStrategy.FIRST:
            selected_node = nodes[0]

        elif strategy == DaemonSelectionStrategy.ROUND_ROBIN:
            selected_node = nodes[self._round_robin_index % len(nodes)]
            self._round_robin_index += 1

        if selected_node:
            address = f"{selected_node['ip_addr']}:{selected_node['rpc_port']}"
            self.logger.info(
                "Selected daemon: %s (agent: %s, strategy: %s)",
                address, selected_node['agent_id'], strategy.value
            )
            return address

        return None

    def update_node_status(
        self,
        agent_id: str,
        status: str = "available",
        registered_at: Optional[float] = None
    ) -> bool:
        """
        Update the status of a public node in the registry.

        This is called by daemon agents to register themselves or update their status.

        Args:
            agent_id: The ID of the agent to update
            status: New status ("available", "busy", "offline")
            registered_at: Timestamp of registration (defaults to current time)

        Returns:
            True if update was successful, False otherwise
        """
        registry_path = self.shared_dir / "public_nodes.json"
        lock_path = self.shared_dir / "public_nodes.lock"

        if registered_at is None:
            registered_at = time.time()

        try:
            # Create lock file if it doesn't exist
            lock_path.touch(exist_ok=True)

            with open(lock_path, "w") as lock_f:
                fcntl.flock(lock_f, fcntl.LOCK_EX)
                try:
                    # Read existing registry
                    if registry_path.exists():
                        with open(registry_path, 'r') as f:
                            registry = json.load(f)
                    else:
                        registry = {"nodes": [], "version": 1}

                    # Find and update the node
                    found = False
                    for node in registry["nodes"]:
                        if node["agent_id"] == agent_id:
                            node["status"] = status
                            node["registered_at"] = registered_at
                            found = True
                            break

                    if not found:
                        self.logger.warning(
                            "Agent %s not found in public nodes registry", agent_id
                        )
                        return False

                    # Write back atomically
                    temp_path = registry_path.with_suffix('.tmp')
                    with open(temp_path, 'w') as f:
                        json.dump(registry, f, indent=2)
                    temp_path.rename(registry_path)

                    self.logger.info(
                        "Updated public node %s status to %s", agent_id, status
                    )
                    return True

                finally:
                    fcntl.flock(lock_f, fcntl.LOCK_UN)

        except Exception as e:
            self.logger.error("Failed to update public node status: %s", e)
            return False

    def invalidate_cache(self):
        """Invalidate the internal cache, forcing a refresh on next access."""
        self._cache = None
        self._cache_time = 0


def get_daemon_address(
    strategy: str = "random",
    shared_dir: str = "/tmp/monerosim_shared",
    exclude_self: Optional[str] = None
) -> Optional[str]:
    """
    Convenience function to get a daemon address for wallet-only agents.

    Args:
        strategy: Selection strategy ("random", "first", "round_robin")
        shared_dir: Path to shared directory
        exclude_self: Agent ID to exclude (typically the calling agent's ID)

    Returns:
        Daemon address in "ip:port" format, or None if unavailable
    """
    discovery = PublicNodeDiscovery(Path(shared_dir))

    try:
        strategy_enum = DaemonSelectionStrategy(strategy.lower())
    except ValueError:
        logging.warning("Unknown strategy '%s', defaulting to random", strategy)
        strategy_enum = DaemonSelectionStrategy.RANDOM

    exclude_ids = [exclude_self] if exclude_self else None
    return discovery.select_daemon(strategy_enum, exclude_ids)


def parse_selection_strategy(strategy_str: Optional[str]) -> DaemonSelectionStrategy:
    """
    Parse a strategy string into a DaemonSelectionStrategy enum.

    Args:
        strategy_str: Strategy string (e.g., "random", "first", "round_robin")

    Returns:
        Corresponding DaemonSelectionStrategy enum value
    """
    if not strategy_str:
        return DaemonSelectionStrategy.RANDOM

    try:
        return DaemonSelectionStrategy(strategy_str.lower())
    except ValueError:
        logging.warning(
            "Unknown daemon selection strategy '%s', defaulting to random",
            strategy_str
        )
        return DaemonSelectionStrategy.RANDOM
