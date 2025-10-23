#!/usr/bin/env python3
"""
Simulation Monitor Agent for Monerosim

This agent provides real-time monitoring capabilities for Monerosim simulations.
It periodically polls all Monero nodes via RPC to collect status information
and writes continuously updating status reports to shadow.data/monerosim_monitor.log.
"""

import argparse
import json
import logging
import os
import sys
import time
import atexit
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .base_agent import BaseAgent
from .agent_discovery import AgentDiscovery
from .monero_rpc import MoneroRPC, WalletRPC, RPCError


class SimulationMonitorAgent(BaseAgent):
    """
    Simulation Monitor Agent that provides real-time monitoring of Monerosim simulations.
    
    This agent periodically polls all Monero nodes via RPC to collect status information
    and writes continuously updating status reports to shadow.data/monerosim_monitor.log.
    """
    
    def __init__(self, agent_id: str,
                 shared_dir: Optional[Path] = None,
                 poll_interval: int = 300,
                 status_file: str = "shadow.data/monerosim_monitor.log",
                 enable_alerts: bool = True,
                 detailed_logging: bool = False,
                 log_level: str = "INFO",
                 **kwargs):
        """
        Initialize the Simulation Monitor Agent.
        
        Args:
            agent_id: Unique identifier for this agent
            shared_dir: Directory for shared state files
            poll_interval: Polling interval in seconds (default: 300)
            status_file: Path to the real-time status file
            enable_alerts: Whether to enable alert generation
            detailed_logging: Whether to enable detailed logging
            log_level: Logging level
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(agent_id=agent_id, log_level=log_level, **kwargs)
        
        self.poll_interval = poll_interval
        self.status_file = status_file
        self.enable_alerts = enable_alerts
        self.detailed_logging = detailed_logging
        self.cycle_count = 0
        
        # Initialize agent discovery
        self.discovery = AgentDiscovery(str(self.shared_dir))
        
        # Historical data storage
        self.historical_data = []
        self.max_historical_entries = 1000  # Limit memory usage
        
        # RPC connections cache
        self.rpc_cache = {}
        
        # Transaction tracking
        self.transaction_stats = {
            "total_created": 0,
            "total_in_blocks": 0,
            "total_broadcast": 0,
            "unique_tx_hashes": set(),
            "blocks_mined": 0,
            "last_block_height": 0,
            "node_tx_counts": {},  # Track transactions per node
            "tx_to_block_mapping": {},  # Track which block contains which tx
            "pending_txs": set(),  # Track transactions waiting to be included
            "included_txs": set()  # Track transactions already included in blocks
        }
        
        # Block transaction tracking files
        self.blocks_with_tx_file = self.shared_dir / "blocks_with_transactions.json"
        self.tx_tracking_file = self.shared_dir / "transaction_tracking.json"
        
        # Register cleanup handler to ensure final report is generated
        atexit.register(self._cleanup_agent)
        
        self.logger.info(f"SimulationMonitorAgent initialized with poll_interval={poll_interval}s")
        self.logger.info(f"Status file: {self.status_file}")
    
    def _setup_agent(self):
        """Set up the monitor agent."""
        self.logger.info("Setting up Simulation Monitor Agent")
        
        # Ensure the shadow.data directory exists
        os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
        
        # Initialize status file with header
        self._initialize_status_file()
        
        # Create monitoring directory for historical data
        monitoring_dir = self.shared_dir / "monitoring"
        monitoring_dir.mkdir(exist_ok=True)
        
        self.logger.info("Simulation Monitor Agent setup complete")
    
    def _initialize_status_file(self):
        """Create and initialize the status file with header."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
            
            # Write initial header
            with open(self.status_file, 'w') as f:
                f.write("=== MoneroSim Simulation Monitor Started ===\n")
                f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write(f"Agent ID: {self.agent_id}\n")
                f.write(f"Poll Interval: {self.poll_interval} seconds\n")
                f.write("=== Waiting for first status update ===\n\n")
                f.flush()
                
            self.logger.info(f"Initialized status file: {self.status_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize status file: {e}")
            raise
    
    def run_iteration(self) -> float:
        """
        Main monitoring loop iteration.
        
        Returns:
            float: Time to sleep before next iteration (in seconds)
        """
        self.cycle_count += 1
        self.logger.debug(f"Starting monitoring cycle {self.cycle_count}")
        
        try:
            # Collect data from all nodes
            node_data = self._collect_node_data()
            
            # Analyze network status
            network_metrics = self._analyze_network_health(node_data)
            
            # Track transactions and blocks
            self._track_transactions_and_blocks(node_data)
            
            # Write real-time status to file
            self._write_status_update(node_data, network_metrics)
            
            # Check for alerts
            if self.enable_alerts:
                alerts = self._check_alerts(network_metrics)
                if alerts:
                    self._write_alerts(f, alerts)
            
            # Store detailed data for final report
            self._store_historical_data(node_data, network_metrics)
            
            self.logger.debug(f"Completed monitoring cycle {self.cycle_count}")
            return self.poll_interval
            
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle {self.cycle_count}: {e}", exc_info=True)
            return self.poll_interval  # Return standard interval even on error
    
    def _collect_node_data(self) -> Dict[str, Any]:
        """
        Collect data from all discovered agents via RPC.
        
        Returns:
            Dictionary containing data from all nodes
        """
        node_data = {}
        
        try:
            # Get all agents from the registry
            registry = self.discovery.get_agent_registry(force_refresh=True)
            agents = registry.get("agents", [])
            
            if isinstance(agents, dict):
                agents = list(agents.values())
            
            self.logger.info(f"Collecting data from {len(agents)} agents")
            
            for agent in agents:
                agent_id = agent.get("id", "unknown")
                
                try:
                    # Get RPC connection for this agent
                    rpc_info = self._get_agent_rpc_info(agent)
                    if not rpc_info:
                        self.logger.warning(f"No RPC information for agent {agent_id}")
                        continue
                    
                    # Collect data from daemon
                    daemon_data = self._collect_daemon_data(rpc_info)
                    
                    # Collect data from wallet if available
                    wallet_data = self._collect_wallet_data(rpc_info)
                    
                    # Combine data
                    node_data[agent_id] = {
                        "agent_info": agent,
                        "daemon": daemon_data,
                        "wallet": wallet_data,
                        "timestamp": time.time()
                    }
                    
                except Exception as e:
                    self.logger.warning(f"Failed to collect data from agent {agent_id}: {e}")
                    # Still store basic agent info
                    node_data[agent_id] = {
                        "agent_info": agent,
                        "daemon": {"error": str(e)},
                        "wallet": {"error": str(e)},
                        "timestamp": time.time()
                    }
            
            self.logger.info(f"Successfully collected data from {len(node_data)} nodes")
            return node_data
            
        except Exception as e:
            self.logger.error(f"Failed to collect node data: {e}")
            return {}
    
    def _get_agent_rpc_info(self, agent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract RPC connection information from agent data.
        
        Args:
            agent: Agent dictionary from registry
            
        Returns:
            Dictionary with RPC connection info or None if not available
        """
        try:
            # Try different port field names
            agent_rpc_port = (
                agent.get("agent_rpc_port") or 
                agent.get("daemon_rpc_port") or
                agent.get("rpc_port")
            )
            
            wallet_rpc_port = agent.get("wallet_rpc_port")
            
            if not agent_rpc_port:
                return None
            
            return {
                "host": agent.get("ip_addr", "127.0.0.1"),
                "agent_rpc_port": agent_rpc_port,
                "wallet_rpc_port": wallet_rpc_port,
                "agent_id": agent.get("id", "unknown")
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting RPC info from agent: {e}")
            return None
    
    def _collect_daemon_data(self, rpc_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect data from a Monero daemon via RPC.
        
        Args:
            rpc_info: RPC connection information
            
        Returns:
            Dictionary containing daemon data
        """
        try:
            # Get or create RPC connection
            daemon_rpc = self._get_daemon_rpc(rpc_info)
            if not daemon_rpc:
                return {"error": "Failed to create RPC connection"}
            
            # Collect daemon information
            data = {}
            
            try:
                info = daemon_rpc.get_info()
                data.update({
                    "height": info.get("height", 0),
                    "connections": daemon_rpc.get_connections(),
                    "synced": info.get("synchronized", False),
                    "difficulty": info.get("difficulty", 0),
                    "target_height": info.get("target_height", 0),
                    "incoming_connections": info.get("incoming_connections_count", 0),
                    "outgoing_connections": info.get("outgoing_connections_count", 0),
                    "network_height": info.get("height_without_bootstrap", 0)
                })
            except Exception as e:
                data["info_error"] = str(e)
            
            try:
                # Get mining status
                mining_status = daemon_rpc.mining_status()
                data.update({
                    "mining_active": mining_status.get("active", False),
                    "mining_hashrate": mining_status.get("speed", 0),
                    "mining_threads": mining_status.get("threads_count", 0)
                })
            except Exception as e:
                data["mining_error"] = str(e)
            
            return data
            
        except Exception as e:
            return {"error": str(e)}
    
    def _collect_wallet_data(self, rpc_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect data from a Monero wallet via RPC.
        
        Args:
            rpc_info: RPC connection information
            
        Returns:
            Dictionary containing wallet data
        """
        try:
            wallet_rpc_port = rpc_info.get("wallet_rpc_port")
            if not wallet_rpc_port:
                return {"error": "No wallet RPC port"}
            
            # Get or create wallet RPC connection
            wallet_rpc = self._get_wallet_rpc(rpc_info)
            if not wallet_rpc:
                return {"error": "Failed to create wallet RPC connection"}
            
            # Collect wallet information
            data = {}
            
            try:
                balance = wallet_rpc.get_balance()
                data.update({
                    "balance": balance.get("balance", 0),
                    "unlocked_balance": balance.get("unlocked_balance", 0),
                    "height": balance.get("blocks_to_unlock", 0)
                })
            except Exception as e:
                data["balance_error"] = str(e)
            
            try:
                # Get transaction pool information
                transfers = wallet_rpc.get_transfers(pool=True)
                pool_txs = transfers.get("pool", [])
                data["pool_size"] = len(pool_txs)
            except Exception as e:
                data["pool_error"] = str(e)
            
            return data
            
        except Exception as e:
            return {"error": str(e)}
    
    def _get_daemon_rpc(self, rpc_info: Dict[str, Any]) -> Optional[MoneroRPC]:
        """
        Get or create a daemon RPC connection.
        
        Args:
            rpc_info: RPC connection information
            
        Returns:
            MoneroRPC instance or None if connection fails
        """
        cache_key = f"{rpc_info['host']}:{rpc_info['agent_rpc_port']}"
        
        if cache_key in self.rpc_cache:
            return self.rpc_cache[cache_key]
        
        try:
            daemon_rpc = MoneroRPC(rpc_info["host"], rpc_info["agent_rpc_port"])
            if daemon_rpc.is_ready():
                self.rpc_cache[cache_key] = daemon_rpc
                return daemon_rpc
        except Exception as e:
            self.logger.warning(f"Failed to connect to daemon RPC at {cache_key}: {e}")
        
        return None
    
    def _get_wallet_rpc(self, rpc_info: Dict[str, Any]) -> Optional[WalletRPC]:
        """
        Get or create a wallet RPC connection.
        
        Args:
            rpc_info: RPC connection information
            
        Returns:
            WalletRPC instance or None if connection fails
        """
        wallet_rpc_port = rpc_info.get("wallet_rpc_port")
        if not wallet_rpc_port:
            return None
        
        cache_key = f"{rpc_info['host']}:{wallet_rpc_port}"
        
        if cache_key in self.rpc_cache:
            return self.rpc_cache[cache_key]
        
        try:
            wallet_rpc = WalletRPC(rpc_info["host"], wallet_rpc_port)
            if wallet_rpc.is_ready():
                self.rpc_cache[cache_key] = wallet_rpc
                return wallet_rpc
        except Exception as e:
            self.logger.warning(f"Failed to connect to wallet RPC at {cache_key}: {e}")
        
        return None
    
    def _analyze_network_health(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze network health metrics from collected node data.
        
        Args:
            node_data: Dictionary containing data from all nodes
            
        Returns:
            Dictionary containing network health metrics
        """
        metrics = {
            "total_nodes": len(node_data),
            "synced_nodes": 0,
            "active_miners": 0,
            "total_connections": 0,
            "heights": [],
            "mining_hashrates": [],
            "total_balance": 0,
            "total_unlocked_balance": 0,
            "total_pool_size": 0,
            "errors": []
        }
        
        for node_id, data in node_data.items():
            daemon = data.get("daemon", {})
            wallet = data.get("wallet", {})
            
            # Check synchronization status
            if daemon.get("synced", False):
                metrics["synced_nodes"] += 1
            
            # Check mining status
            if daemon.get("mining_active", False):
                metrics["active_miners"] += 1
                metrics["mining_hashrates"].append(daemon.get("mining_hashrate", 0))
            
            # Collect height information
            height = daemon.get("height", 0)
            if height > 0:
                metrics["heights"].append(height)
            
            # Collect connection information
            connections = daemon.get("connections", 0)
            if connections > 0:
                metrics["total_connections"] += connections
            
            # Collect balance information
            balance = wallet.get("balance", 0)
            unlocked_balance = wallet.get("unlocked_balance", 0)
            if balance > 0:
                metrics["total_balance"] += balance
                metrics["total_unlocked_balance"] += unlocked_balance
            
            # Collect pool size
            pool_size = wallet.get("pool_size", 0)
            if pool_size > 0:
                metrics["total_pool_size"] += pool_size
            
            # Collect errors
            if "error" in daemon:
                metrics["errors"].append(f"{node_id} daemon: {daemon['error']}")
            if "error" in wallet:
                metrics["errors"].append(f"{node_id} wallet: {wallet['error']}")
        
        # Calculate derived metrics
        if metrics["heights"]:
            metrics["avg_height"] = sum(metrics["heights"]) / len(metrics["heights"])
            metrics["max_height"] = max(metrics["heights"])
            metrics["min_height"] = min(metrics["heights"])
            metrics["height_variance"] = sum((h - metrics["avg_height"]) ** 2 for h in metrics["heights"]) / len(metrics["heights"])
        else:
            metrics["avg_height"] = 0
            metrics["max_height"] = 0
            metrics["min_height"] = 0
            metrics["height_variance"] = 0
        
        if metrics["mining_hashrates"]:
            metrics["total_hashrate"] = sum(metrics["mining_hashrates"])
            metrics["avg_hashrate"] = metrics["total_hashrate"] / len(metrics["mining_hashrates"])
        else:
            metrics["total_hashrate"] = 0
            metrics["avg_hashrate"] = 0
        
        metrics["sync_percentage"] = (metrics["synced_nodes"] / metrics["total_nodes"] * 100) if metrics["total_nodes"] > 0 else 0
        
        return metrics
    
    def _track_transactions_and_blocks(self, node_data: Dict[str, Any]):
        """
        Track transactions and blocks across the network by reading the shared state files
        and correlating transactions with blocks.
        
        Args:
            node_data: Dictionary containing data from all nodes
        """
        try:
            # Read actual transaction and block data from shared state files
            self._read_transaction_data()
            self._read_enhanced_block_data()
            
            # Correlate transactions with blocks
            self._correlate_transactions_with_blocks()
            
            # Also track node-level metrics
            current_max_height = 0
            total_nodes_with_txs = 0
            
            for node_id, data in node_data.items():
                daemon = data.get("daemon", {})
                wallet = data.get("wallet", {})
                
                # Track block height
                height = daemon.get("height", 0)
                if height > current_max_height:
                    current_max_height = height
                
                # Track transactions in wallet
                if wallet.get("balance", 0) > 0 or wallet.get("unlocked_balance", 0) > 0:
                    # This node has received transactions
                    if node_id not in self.transaction_stats["node_tx_counts"]:
                        self.transaction_stats["node_tx_counts"][node_id] = 0
                    self.transaction_stats["node_tx_counts"][node_id] += 1
                    total_nodes_with_txs += 1
            
            # Update broadcast count (nodes that have received transactions)
            if total_nodes_with_txs > len(self.transaction_stats["node_tx_counts"]):
                self.transaction_stats["total_broadcast"] = total_nodes_with_txs
            
            # Save enhanced tracking data
            self._save_transaction_tracking_data()
            
        except Exception as e:
            self.logger.error(f"Error tracking transactions and blocks: {e}")
    
    def _read_transaction_data(self):
        """Read transaction data from the shared state file."""
        try:
            transactions_file = self.shared_dir / "transactions.json"
            if transactions_file.exists():
                with open(transactions_file, 'r') as f:
                    transactions = json.load(f)
                
                # Update transaction count
                self.transaction_stats["total_created"] = len(transactions)
                
                # Track unique transaction hashes
                for tx in transactions:
                    if isinstance(tx, dict) and "tx_hash" in tx:
                        tx_hash = tx["tx_hash"]
                        if isinstance(tx_hash, dict) and "tx_hash" in tx_hash:
                            self.transaction_stats["unique_tx_hashes"].add(tx_hash["tx_hash"])
                
                self.logger.debug(f"Read {len(transactions)} transactions from shared state")
            
        except Exception as e:
            self.logger.error(f"Error reading transaction data: {e}")
    
    def _read_enhanced_block_data(self):
        """Read enhanced block data from the shared state file."""
        try:
            blocks_file = self.shared_dir / "blocks_found.json"
            if blocks_file.exists():
                with open(blocks_file, 'r') as f:
                    blocks = json.load(f)
                
                # Update block count
                self.transaction_stats["blocks_mined"] = len(blocks)
                
                # Try to read enhanced blocks with transaction data
                if self.blocks_with_tx_file.exists():
                    try:
                        with open(self.blocks_with_tx_file, 'r') as f:
                            enhanced_blocks = json.load(f)
                        
                        # Count actual transactions in blocks
                        total_tx_in_blocks = sum(len(block.get("transactions", [])) for block in enhanced_blocks)
                        self.transaction_stats["total_in_blocks"] = total_tx_in_blocks
                        
                        self.logger.debug(f"Read {len(enhanced_blocks)} enhanced blocks with {total_tx_in_blocks} transactions")
                        return enhanced_blocks
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to read enhanced block data: {e}")
                
                # Fallback: estimate transactions in blocks (simplified - assumes at least 1 tx per block)
                self.transaction_stats["total_in_blocks"] = len(blocks)
                
                self.logger.debug(f"Read {len(blocks)} basic blocks from shared state")
                return blocks
            
        except Exception as e:
            self.logger.error(f"Error reading block data: {e}")
            return []
    
    def _correlate_transactions_with_blocks(self):
        """
        Correlate transactions with blocks using timing and heuristic analysis.
        This method attempts to determine which transactions are likely included in which blocks
        when direct transaction data is not available in blocks_found.json.
        """
        try:
            # Load existing tracking data if available
            existing_tracking = {}
            if self.tx_tracking_file.exists():
                try:
                    with open(self.tx_tracking_file, 'r') as f:
                        existing_tracking = json.load(f)
                except Exception as e:
                    self.logger.warning(f"Failed to load existing tracking data: {e}")
            
            # Get transaction timestamps
            tx_timestamps = {}
            transactions_file = self.shared_dir / "transactions.json"
            if transactions_file.exists():
                with open(transactions_file, 'r') as f:
                    transactions = json.load(f)
                
                for tx in transactions:
                    tx_hash = None
                    if isinstance(tx, dict) and "tx_hash" in tx:
                        tx_hash_data = tx["tx_hash"]
                        if isinstance(tx_hash_data, dict) and "tx_hash" in tx_hash_data:
                            tx_hash = tx_hash_data["tx_hash"]
                        elif isinstance(tx_hash_data, str):
                            tx_hash = tx_hash_data
                    
                    if tx_hash and "timestamp" in tx:
                        tx_timestamps[tx_hash] = tx["timestamp"]
            
            # Get block timestamps
            blocks_file = self.shared_dir / "blocks_found.json"
            if blocks_file.exists():
                with open(blocks_file, 'r') as f:
                    blocks = json.load(f)
                
                # Sort blocks by timestamp
                blocks.sort(key=lambda x: x.get("timestamp", 0))
                
                # Correlate transactions with blocks based on timing
                for i, block in enumerate(blocks):
                    block_time = block.get("timestamp", 0)
                    block_hash = block.get("block_hash", f"block_{i}")
                    
                    # Find transactions created before this block but after previous block
                    prev_block_time = blocks[i-1].get("timestamp", 0) if i > 0 else 0
                    
                    # Transactions that could be in this block
                    potential_txs = []
                    for tx_hash, tx_time in tx_timestamps.items():
                        if prev_block_time < tx_time <= block_time:
                            potential_txs.append(tx_hash)
                    
                    # Update tracking data
                    if potential_txs:
                        self.transaction_stats["tx_to_block_mapping"][block_hash] = potential_txs
                        self.transaction_stats["included_txs"].update(potential_txs)
                
                # Update the count
                self.transaction_stats["total_in_blocks"] = len(self.transaction_stats["included_txs"])
                
                self.logger.debug(f"Correlated {len(self.transaction_stats['included_txs'])} transactions with {len(blocks)} blocks")
            
        except Exception as e:
            self.logger.error(f"Error correlating transactions with blocks: {e}")
    
    def _save_transaction_tracking_data(self):
        """Save enhanced transaction tracking data to shared files."""
        try:
            # Save transaction tracking data
            tracking_data = {
                "tx_to_block_mapping": dict(self.transaction_stats["tx_to_block_mapping"]),
                "included_txs": list(self.transaction_stats["included_txs"]),
                "pending_txs": list(self.transaction_stats["pending_txs"]),
                "total_in_blocks": self.transaction_stats["total_in_blocks"],
                "last_updated": time.time()
            }
            
            with open(self.tx_tracking_file, 'w') as f:
                json.dump(tracking_data, f, indent=2)
            
            # Always update the enhanced blocks file with current data
            blocks_file = self.shared_dir / "blocks_found.json"
            if blocks_file.exists():
                with open(blocks_file, 'r') as f:
                    blocks = json.load(f)
                
                # Enhance blocks with transaction data
                enhanced_blocks = []
                for i, block in enumerate(blocks):
                    block_hash = block.get("block_hash", f"block_{i}")
                    enhanced_block = block.copy()
                    enhanced_block["transactions"] = self.transaction_stats["tx_to_block_mapping"].get(block_hash, [])
                    enhanced_block["tx_count"] = len(enhanced_block["transactions"])
                    enhanced_block["height"] = i + 1  # Estimate height
                    enhanced_blocks.append(enhanced_block)
                
                with open(self.blocks_with_tx_file, 'w') as f:
                    json.dump(enhanced_blocks, f, indent=2)
                
                self.logger.debug(f"Updated enhanced blocks file with {len(enhanced_blocks)} blocks")
            
        except Exception as e:
            self.logger.error(f"Error saving transaction tracking data: {e}")
    
    def _write_status_update(self, node_data: Dict[str, Any], network_metrics: Dict[str, Any]):
        """
        Write real-time status update to the monitor file.
        
        Args:
            node_data: Dictionary containing data from all nodes
            network_metrics: Dictionary containing network health metrics
        """
        try:
            with open(self.status_file, 'a') as f:
                # Write header with timestamps
                real_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
                sim_time = self._get_simulation_time()
                f.write(f"\n{'='*60}\n")
                f.write(f"=== MoneroSim Simulation Monitor ===\n")
                f.write(f"Real Time: {real_time} | Sim Time: {sim_time} | Cycle: {self.cycle_count}\n\n")
                
                # Write network status
                f.write("NETWORK STATUS:\n")
                f.write(f"- Total Nodes: {network_metrics['total_nodes']}\n")
                f.write(f"- Synchronized: {network_metrics['synced_nodes']}/{network_metrics['total_nodes']} "
                       f"({network_metrics['sync_percentage']:.1f}%)\n")
                f.write(f"- Average Height: {network_metrics['avg_height']:.0f}\n")
                f.write(f"- Height Variance: {network_metrics['height_variance']:.2f}\n")
                f.write(f"- Active Miners: {network_metrics['active_miners']}\n\n")
                
                # Write node details table
                self._write_node_table(f, node_data)
                
                # Write transaction status
                self._write_transaction_status(f, network_metrics)
                
                # Write blockchain status
                self._write_blockchain_status(f, network_metrics)
                
                # Write alerts if any
                alerts = self._check_alerts(network_metrics)
                if alerts:
                    self._write_alerts(f, alerts)
                
                f.write(f"\n=== End Status Update ===\n")
                f.flush()  # Ensure immediate visibility for tail -f
                
        except Exception as e:
            self.logger.error(f"Failed to write status update: {e}")
    
    def _write_node_table(self, f, node_data: Dict[str, Any]):
        """Write formatted node details table."""
        f.write("NODE DETAILS:\n")
        
        # Table header
        f.write("┌─────────────┬───────┬───────┬──────────┬──────────┬─────────┐\n")
        f.write("│ Node        │ Height│ Sync  │ Mining   │ Hashrate │ Conns   │\n")
        f.write("├─────────────┼───────┼───────┼──────────┼──────────┼─────────┤\n")
        
        # Table rows
        for node_id, data in node_data.items():
            agent_info = data.get("agent_info", {})
            daemon = data.get("daemon", {})
            
            # Determine node type
            node_type = "user"
            if agent_info.get("attributes", {}).get("is_miner") == "true":
                node_type = "miner"
            
            # Format values
            height = daemon.get("height", 0)
            sync_status = "✓" if daemon.get("synced", False) else "✗"
            mining_status = "✓ Active" if daemon.get("mining_active", False) else "✗ Inactive"
            hashrate = daemon.get("mining_hashrate", 0)
            hashrate_str = f"{hashrate/1000:.1f} KH/s" if hashrate > 0 else "0 H/s"
            connections = daemon.get("connections", 0)
            
            # Truncate node ID if needed
            node_display = f"{node_id} ({node_type})"
            if len(node_display) > 11:
                node_display = node_display[:11]
            
            f.write(f"│ {node_display:<11} │ {height:>5} │ {sync_status:<5} │ {mining_status:<8} │ {hashrate_str:>8} │ {connections:>7} │\n")
        
        f.write("└─────────────┴───────┴───────┴──────────┴──────────┴─────────┘\n\n")
    
    def _write_transaction_status(self, f, network_metrics: Dict[str, Any]):
        """Write transaction status information."""
        f.write("TRANSACTION STATUS:\n")
        f.write(f"- Total Pool Size: {network_metrics['total_pool_size']}\n")
        
        # Write comprehensive transaction statistics
        f.write(f"- Total Transactions Created: {self.transaction_stats['total_created']}\n")
        f.write(f"- Total Transactions in Blocks: {self.transaction_stats['total_in_blocks']}\n")
        f.write(f"- Total Blocks Mined: {self.transaction_stats['blocks_mined']}\n")
        f.write(f"- Nodes with Transactions: {len(self.transaction_stats['node_tx_counts'])}\n")
        
        # Calculate transaction metrics if we have historical data
        if len(self.historical_data) > 1:
            prev_data = self.historical_data[-2]
            curr_data = self.historical_data[-1] if self.historical_data else network_metrics
            
            prev_pool = prev_data.get("network_metrics", {}).get("total_pool_size", 0)
            curr_pool = curr_data.get("total_pool_size", 0)
            
            # Simple transaction rate calculation
            if prev_pool > curr_pool:
                tx_processed = prev_pool - curr_pool
                f.write(f"- Transactions Processed: {tx_processed}\n")
        
        f.write(f"- Total Balance: {network_metrics['total_balance']/1e12:.6f} XMR\n")
        f.write(f"- Unlocked Balance: {network_metrics['total_unlocked_balance']/1e12:.6f} XMR\n\n")
    
    def _write_blockchain_status(self, f, network_metrics: Dict[str, Any]):
        """Write blockchain status information."""
        f.write("BLOCKCHAIN STATUS:\n")
        f.write(f"- Average Height: {network_metrics['avg_height']:.0f}\n")
        f.write(f"- Height Range: {network_metrics['min_height']:.0f} - {network_metrics['max_height']:.0f}\n")
        
        if network_metrics['total_hashrate'] > 0:
            f.write(f"- Network Hashrate: {network_metrics['total_hashrate']/1000:.1f} KH/s\n")
        
        f.write(f"- Total Connections: {network_metrics['total_connections']}\n\n")
    
    def _check_alerts(self, network_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check for alert conditions in the network metrics.
        
        Args:
            network_metrics: Dictionary containing network health metrics
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        # Check synchronization issues
        if network_metrics['sync_percentage'] < 90:
            alerts.append({
                "type": "sync_issue",
                "severity": "warning",
                "message": f"Low synchronization rate: {network_metrics['sync_percentage']:.1f}%"
            })
        
        # Check height variance
        if network_metrics['height_variance'] > 10:
            alerts.append({
                "type": "height_variance",
                "severity": "warning",
                "message": f"High height variance: {network_metrics['height_variance']:.2f}"
            })
        
        # Check for no miners
        if network_metrics['active_miners'] == 0:
            alerts.append({
                "type": "no_miners",
                "severity": "critical",
                "message": "No active miners detected"
            })
        
        # Check for large transaction pool
        if network_metrics['total_pool_size'] > 50:
            alerts.append({
                "type": "large_pool",
                "severity": "warning",
                "message": f"Large transaction pool: {network_metrics['total_pool_size']} transactions"
            })
        
        # Check for errors
        if network_metrics['errors']:
            alerts.append({
                "type": "node_errors",
                "severity": "warning",
                "message": f"{len(network_metrics['errors'])} nodes reporting errors"
            })
        
        return alerts
    
    def _write_alerts(self, f, alerts: List[Dict[str, Any]]):
        """Write alerts to the status file."""
        f.write("ALERTS:\n")
        for alert in alerts:
            severity_symbol = "⚠️" if alert["severity"] == "warning" else "🚨"
            f.write(f"{severity_symbol} {alert['message']}\n")
        f.write("\n")
    
    def _get_simulation_time(self) -> str:
        """
        Get the current simulation time.
        
        Returns:
            Formatted simulation time string
        """
        # This is a placeholder - in a real implementation, this would
        # get the actual simulation time from Shadow
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.000")
    
    def _store_historical_data(self, node_data: Dict[str, Any], network_metrics: Dict[str, Any]):
        """
        Store historical data for final report generation.
        
        Args:
            node_data: Dictionary containing data from all nodes
            network_metrics: Dictionary containing network health metrics
        """
        try:
            historical_entry = {
                "timestamp": time.time(),
                "cycle": self.cycle_count,
                "simulation_time": self._get_simulation_time(),
                "node_data": node_data,
                "network_metrics": network_metrics
            }
            
            self.historical_data.append(historical_entry)
            
            # Limit memory usage
            if len(self.historical_data) > self.max_historical_entries:
                self.historical_data = self.historical_data[-self.max_historical_entries:]
            
            # Save historical data every cycle
            self._save_historical_data()
            
            # Update final report periodically (every poll_interval)
            if self.cycle_count == 1 or (time.time() - getattr(self, '_last_report_update', 0)) >= self.poll_interval:
                self._update_final_report()
                self._last_report_update = time.time()
                self.logger.info(f"Updated final report at cycle {self.cycle_count}")
                
        except Exception as e:
            self.logger.error(f"Failed to store historical data: {e}")
    
    def _save_historical_data(self):
        """Save historical data to disk."""
        try:
            monitoring_dir = self.shared_dir / "monitoring"
            monitoring_dir.mkdir(exist_ok=True)
            
            historical_file = monitoring_dir / "historical_data.json"
            
            with open(historical_file, 'w') as f:
                json.dump(self.historical_data, f, indent=2)
                
            self.logger.debug(f"Saved historical data with {len(self.historical_data)} entries")
            
        except Exception as e:
            self.logger.error(f"Failed to save historical data: {e}")
    
    def _update_final_report(self):
        """Update the final report with current data."""
        try:
            monitoring_dir = self.shared_dir / "monitoring"
            monitoring_dir.mkdir(exist_ok=True)
            
            # Convert set to list for JSON serialization
            tx_stats_copy = self.transaction_stats.copy()
            tx_stats_copy["unique_tx_hashes"] = list(self.transaction_stats["unique_tx_hashes"])
            
            final_report = {
                "agent_id": self.agent_id,
                "start_time": self.historical_data[0]["timestamp"] if self.historical_data else time.time(),
                "last_update": time.time(),
                "total_cycles": self.cycle_count,
                "historical_data": self.historical_data,
                "transaction_stats": tx_stats_copy,
                "summary": self._generate_summary(),
                "status": "running"
            }
            
            report_file = monitoring_dir / "final_report.json"
            with open(report_file, 'w') as f:
                json.dump(final_report, f, indent=2)
                
            self.logger.debug(f"Updated final report with {len(self.historical_data)} entries")
            
        except Exception as e:
            self.logger.error(f"Failed to update final report: {e}")
    
    def _cleanup_agent(self):
        """Clean up resources before shutdown."""
        self.logger.info("Cleaning up Simulation Monitor Agent")
        
        try:
            # Generate final report
            self._generate_final_report()
            
            # Close RPC connections
            for rpc in self.rpc_cache.values():
                try:
                    # RPC connections don't have explicit close methods in our implementation
                    pass
                except:
                    pass
            
            self.rpc_cache.clear()
            
            # Write shutdown message to status file
            with open(self.status_file, 'a') as f:
                f.write(f"\n=== MoneroSim Simulation Monitor Stopped ===\n")
                f.write(f"Stopped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write(f"Total Cycles: {self.cycle_count}\n")
                f.write("=== End Monitor Session ===\n")
                f.flush()
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def _generate_final_report(self):
        """Generate a comprehensive final report."""
        try:
            monitoring_dir = self.shared_dir / "monitoring"
            monitoring_dir.mkdir(exist_ok=True)
            
            # Convert set to list for JSON serialization
            tx_stats_copy = self.transaction_stats.copy()
            tx_stats_copy["unique_tx_hashes"] = list(self.transaction_stats["unique_tx_hashes"])
            
            final_report = {
                "agent_id": self.agent_id,
                "start_time": self.historical_data[0]["timestamp"] if self.historical_data else time.time(),
                "end_time": time.time(),
                "total_cycles": self.cycle_count,
                "historical_data": self.historical_data,
                "transaction_stats": tx_stats_copy,
                "summary": self._generate_summary(),
                "status": "completed"
            }
            
            report_file = monitoring_dir / "final_report.json"
            with open(report_file, 'w') as f:
                json.dump(final_report, f, indent=2)
                
            self.logger.info(f"Generated final report: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to generate final report: {e}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of the monitoring session."""
        if not self.historical_data:
            return {}
        
        summary = {
            "total_nodes": 0,
            "avg_sync_percentage": 0,
            "max_height": 0,
            "total_transactions_processed": 0,
            "alert_count": 0,
            # Add comprehensive transaction statistics
            "total_blocks_mined": self.transaction_stats["blocks_mined"],
            "total_transactions_created": self.transaction_stats["total_created"],
            "total_transactions_in_blocks": self.transaction_stats["total_in_blocks"],
            "nodes_with_transactions": len(self.transaction_stats["node_tx_counts"]),
            "success_criteria": {
                "blocks_created": self.transaction_stats["blocks_mined"] > 0,
                "blocks_propagated": len(self.transaction_stats["node_tx_counts"]) > 0,
                "transactions_created_broadcast": self.transaction_stats["total_created"] > 0,
                "transactions_in_blocks": self.transaction_stats["total_in_blocks"] > 0
            }
        }
        
        sync_percentages = []
        heights = []
        alert_count = 0
        
        for entry in self.historical_data:
            metrics = entry.get("network_metrics", {})
            
            sync_percentages.append(metrics.get("sync_percentage", 0))
            heights.append(metrics.get("max_height", 0))
            
            # Count alerts (this is a simplified count)
            if metrics.get("sync_percentage", 0) < 90:
                alert_count += 1
            if metrics.get("height_variance", 0) > 10:
                alert_count += 1
            if metrics.get("active_miners", 0) == 0:
                alert_count += 1
        
        if self.historical_data:
            summary["total_nodes"] = self.historical_data[-1].get("network_metrics", {}).get("total_nodes", 0)
            summary["avg_sync_percentage"] = sum(sync_percentages) / len(sync_percentages)
            summary["max_height"] = max(heights) if heights else 0
            summary["alert_count"] = alert_count
        
        return summary
    
    @staticmethod
    def create_argument_parser() -> argparse.ArgumentParser:
        """Create argument parser for the simulation monitor agent."""
        parser = BaseAgent.create_argument_parser(
            description="MoneroSim Simulation Monitor Agent",
            default_shared_dir='/tmp/monerosim_shared'
        )
        
        parser.add_argument('--poll-interval', type=int, default=300,
                          help='Polling interval in seconds (default: 300)')
        parser.add_argument('--status-file', type=str, 
                          default='shadow.data/monerosim_monitor.log',
                          help='Path to the real-time status file')
        parser.add_argument('--enable-alerts', action='store_true', default=True,
                          help='Enable alert generation')
        parser.add_argument('--detailed-logging', action='store_true', default=False,
                          help='Enable detailed logging')
        
        return parser


def main():
    """Main entry point for the simulation monitor agent."""
    parser = SimulationMonitorAgent.create_argument_parser()
    args = parser.parse_args()
    
    try:
        # Create and run the agent
        agent = SimulationMonitorAgent(
            agent_id=args.id,
            shared_dir=args.shared_dir,
            agent_rpc_port=args.agent_rpc_port,
            wallet_rpc_port=args.wallet_rpc_port,
            p2p_port=args.p2p_port,
            rpc_host=args.rpc_host,
            log_level=args.log_level,
            attributes=args.attributes,
            poll_interval=args.poll_interval,
            status_file=args.status_file,
            enable_alerts=args.enable_alerts,
            detailed_logging=args.detailed_logging
        )
        
        agent.run()
        
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
