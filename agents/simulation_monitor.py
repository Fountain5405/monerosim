#!/usr/bin/env python3
"""
Simulation Monitor Agent for Monerosim

This agent provides real-time monitoring capabilities for Monerosim simulations.
It periodically polls all Monero nodes via RPC to collect status information
and writes continuously updating status reports to shadow.data/monerosim_monitor.log.
"""

import argparse
import glob
import json
import logging
import os
import re
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
                 output_dir: Optional[str] = None,
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
            output_dir: Shadow output directory for daemon log discovery
            status_file: Path to the real-time status file
            enable_alerts: Whether to enable alert generation
            detailed_logging: Whether to enable detailed logging
            log_level: Logging level
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(agent_id=agent_id, log_level=log_level, **kwargs)

        self.poll_interval = poll_interval
        self.output_dir = Path(output_dir) if output_dir else None
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
            "last_processed_height": 0,  # Track last block we've processed for tx extraction
            "node_tx_counts": {},  # Track transactions per node (received)
            "tx_created_by_node": {},  # Track transactions created per sender node
            "tx_to_block_mapping": {},  # Track which block contains which tx (height -> tx_hashes)
            "pending_txs": set(),  # Track transactions waiting to be included
            "included_txs": set()  # Track transactions already included in blocks
        }

        # Block transaction tracking files
        self.blocks_with_tx_file = self.shared_dir / "blocks_with_transactions.json"
        self.tx_tracking_file = self.shared_dir / "transaction_tracking.json"

        # Reference daemon for block queries (will be set to first available daemon)
        self.reference_daemon = None

        # Mining tracking
        self.miner_registry = {}  # agent_id -> miner info (weight, ip_addr, etc.)
        self.miner_block_counts = {}  # agent_id -> blocks mined (from log parsing)
        self.last_heights = {}  # agent_id -> last seen height
        self.network_difficulty = 0

        # Real-time log parsing for mining detection
        self.log_file_positions = {}  # file_path -> last read position
        self.daemon_log_files = {}  # agent_id -> log file path
        self.recent_blocks_mined = {}  # agent_id -> list of (height, timestamp) tuples
        self.total_blocks_mined_by_agent = {}  # agent_id -> total count
        self.blocks_mined_by_height = {}  # height -> agent_id (first miner to log this height)
        self.last_daemon_discovery_time = 0  # Track when we last discovered daemon logs
        self.daemon_discovery_interval = 60  # Re-discover daemon logs every 60 seconds

        # Register cleanup handler to ensure final report is generated
        atexit.register(self._cleanup_agent)
        
        self.logger.info(f"SimulationMonitorAgent initialized with poll_interval={poll_interval}s")
        self.logger.info(f"Status file: {self.status_file}")
    
    def _setup_agent(self):
        """Set up the monitor agent."""
        self.logger.info("Setting up Simulation Monitor Agent")

        # Discover daemon log files for real-time mining detection
        self._discover_daemon_log_files()

        # Try to relocate status file to shadow.data for convenience
        self._relocate_status_file_to_shadow_data()

        # Ensure the status file directory exists
        os.makedirs(os.path.dirname(self.status_file), exist_ok=True)

        # Initialize status file with header
        self._initialize_status_file()

        # Create monitoring directory for historical data
        monitoring_dir = self.shared_dir / "monitoring"
        monitoring_dir.mkdir(exist_ok=True)

        # Load miner registry
        self._load_miner_registry()

        self.logger.info("Simulation Monitor Agent setup complete")

    def _relocate_status_file_to_shadow_data(self):
        """Move status file to shadow.data directory if found."""
        hosts_dir = self._find_shadow_data_hosts()
        if not hosts_dir:
            return

        # shadow.data is parent of hosts
        shadow_data_dir = hosts_dir.parent
        self.status_file = str(shadow_data_dir / "monerosim_monitor.log")
        self.logger.info(f"Status file: {self.status_file}")

    def _load_miner_registry(self):
        """
        Load miner configuration from miners.json and agent registry.
        This identifies which nodes are miners and their hashrate weights.
        """
        try:
            # Load miners.json for weight/hashrate distribution
            miners_file = self.shared_dir / "miners.json"
            if miners_file.exists():
                with open(miners_file, 'r') as f:
                    miners_data = json.load(f)

                for miner in miners_data.get("miners", []):
                    agent_id = miner.get("agent_id")
                    if agent_id:
                        self.miner_registry[agent_id] = {
                            "ip_addr": miner.get("ip_addr"),
                            "weight": miner.get("weight", 0),
                            "is_miner": True,
                            "blocks_produced": 0
                        }

                self.logger.info(f"Loaded {len(self.miner_registry)} miners from registry")

            # Also check agent registry for is_miner attribute
            agent_registry = self.discovery.get_agent_registry(force_refresh=True)
            for agent in agent_registry.get("agents", []):
                agent_id = agent.get("id")
                is_miner = agent.get("attributes", {}).get("is_miner") == "true"

                if is_miner and agent_id not in self.miner_registry:
                    self.miner_registry[agent_id] = {
                        "ip_addr": agent.get("ip_addr"),
                        "weight": 0,  # Unknown weight
                        "is_miner": True,
                        "blocks_produced": 0
                    }

        except Exception as e:
            self.logger.error(f"Error loading miner registry: {e}")

    def _find_shadow_data_hosts(self) -> Optional[Path]:
        """
        Find the shadow.data/hosts directory by searching common locations.
        Returns the path if found, None otherwise.
        """
        # List of candidate paths to check
        candidates = []

        # If output_dir specified, check there first
        if self.output_dir:
            candidates.append(self.output_dir / "shadow.data" / "hosts")

        # Check relative to current working directory
        candidates.append(Path("shadow.data/hosts"))
        candidates.append(Path("shadow_output/shadow.data/hosts"))

        # Check parent directories (shadow might run from a subdirectory)
        cwd = Path.cwd()
        for parent in [cwd.parent, cwd.parent.parent]:
            candidates.append(parent / "shadow.data" / "hosts")
            candidates.append(parent / "shadow_output" / "shadow.data" / "hosts")

        for candidate in candidates:
            if candidate.exists():
                self.logger.debug(f"Found shadow.data/hosts at: {candidate}")
                return candidate

        return None

    def _discover_daemon_log_files(self):
        """
        Discover daemon log files for all hosts in shadow.data/hosts/.
        These are the bash.*.stdout files that contain monerod output.
        """
        try:
            hosts_dir = self._find_shadow_data_hosts()

            if not hosts_dir:
                self.logger.warning("Could not find shadow.data/hosts directory")
                return

            for host_dir in hosts_dir.iterdir():
                if not host_dir.is_dir():
                    continue

                host_name = host_dir.name

                # Find bash.*.stdout files (daemon logs)
                log_files = list(host_dir.glob("bash.*.stdout"))
                if log_files:
                    # Use the largest file (usually the daemon log)
                    # or the first one - daemon is typically bash.1000.stdout
                    daemon_log = None
                    for log_file in sorted(log_files):
                        # Check if this looks like a daemon log by reading first few lines
                        try:
                            with open(log_file, 'r', errors='ignore') as f:
                                header = f.read(1000)
                                if 'monerod' in header.lower() or 'monero' in header.lower() or 'blockchain' in header.lower():
                                    daemon_log = log_file
                                    break
                        except Exception:
                            continue

                    if daemon_log is None and log_files:
                        # Fallback to first/largest file
                        daemon_log = max(log_files, key=lambda f: f.stat().st_size)

                    if daemon_log:
                        self.daemon_log_files[host_name] = str(daemon_log)
                        # Initialize file position
                        if str(daemon_log) not in self.log_file_positions:
                            # Always start at beginning to catch all blocks from simulation start
                            self.log_file_positions[str(daemon_log)] = 0
                            if self.last_daemon_discovery_time != 0:
                                self.logger.info(f"Discovered new daemon log for late-joining agent: {host_name}")

            self.logger.info(f"Discovered daemon logs for {len(self.daemon_log_files)} hosts")

        except Exception as e:
            self.logger.error(f"Error discovering daemon log files: {e}")

    def _parse_daemon_logs_for_mining(self):
        """
        Parse daemon logs for mining events (blocks mined).
        This reads new content since last check (like tail -f).
        """
        # Regex patterns for mining detection
        # Pattern 1: "mined new block" with height
        mined_pattern = re.compile(
            r'mined new block.*height[=:\s]*(\d+)',
            re.IGNORECASE
        )

        # Pattern 2: "BLOCK SUCCESSFULLY ADDED" followed by block details
        block_added_pattern = re.compile(
            r'\+{5,}\s*BLOCK SUCCESSFULLY ADDED',
            re.IGNORECASE
        )

        # Pattern 3: Block ID/hash after successful add
        block_id_pattern = re.compile(
            r'id:\s*<([0-9a-f]{64})>',
            re.IGNORECASE
        )

        # Pattern 4: Height from block info
        height_pattern = re.compile(
            r'HEIGHT\s+(\d+)',
            re.IGNORECASE
        )

        # Pattern 5: PoW indicator (present in all blocks, not just mined ones)
        pow_pattern = re.compile(
            r'PoW:\s*<([0-9a-f]{64})>',
            re.IGNORECASE
        )

        # Pattern 6: Received block from network (means NOT locally mined)
        received_block_pattern = re.compile(
            r'Received NOTIFY_NEW_FLUFFY_BLOCK|NOTIFY_NEW_BLOCK',
            re.IGNORECASE
        )

        # Pattern 7: generateblocks RPC call (means locally mined via RPC)
        generateblocks_pattern = re.compile(
            r'generateblocks',
            re.IGNORECASE
        )

        for agent_id, log_file in self.daemon_log_files.items():
            try:
                if not os.path.exists(log_file):
                    continue

                current_size = os.path.getsize(log_file)
                last_position = self.log_file_positions.get(log_file, 0)

                # Skip if no new content
                if current_size <= last_position:
                    continue

                # Read new content
                with open(log_file, 'r', errors='ignore') as f:
                    f.seek(last_position)
                    new_content = f.read()

                # Update position
                self.log_file_positions[log_file] = current_size

                # Parse for mining events
                lines = new_content.split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i]

                    # Check for "mined new block" pattern
                    mined_match = mined_pattern.search(line)
                    if mined_match:
                        height = int(mined_match.group(1))
                        self._record_block_mined(agent_id, height)
                        i += 1
                        continue

                    # Check for "BLOCK SUCCESSFULLY ADDED" pattern
                    if block_added_pattern.search(line):
                        # Look BACK to check if this was locally mined vs received from network
                        # Received blocks have "NOTIFY_NEW_FLUFFY_BLOCK" before them
                        # Mined blocks have "generateblocks" RPC call before them
                        is_received_from_network = False
                        is_locally_mined = False

                        # Look back up to 5 lines for context
                        for j in range(max(0, i - 5), i):
                            check_line = lines[j]
                            if received_block_pattern.search(check_line):
                                is_received_from_network = True
                                break
                            if generateblocks_pattern.search(check_line):
                                is_locally_mined = True

                        # Skip if this block was received from network (not locally mined)
                        if is_received_from_network:
                            i += 1
                            continue

                        # Look ahead for height info
                        block_height = None
                        for j in range(i, min(i + 10, len(lines))):
                            check_line = lines[j]
                            height_match = height_pattern.search(check_line)
                            if height_match:
                                block_height = int(height_match.group(1))
                                break

                        # Record if we have height, it was locally mined, and it's not genesis block
                        # Genesis block (height 0) is generated by all nodes, not "mined"
                        if block_height is not None and block_height > 0 and is_locally_mined:
                            self._record_block_mined(agent_id, block_height)

                    i += 1

            except Exception as e:
                self.logger.warning(f"Error parsing log for {agent_id}: {e}")

    def _record_block_mined(self, agent_id: str, height: int):
        """
        Record that an agent mined a block.

        De-duplicates by height - if multiple miners log the same block height,
        only the first one is credited. This handles the case where multiple
        autonomous miners might generate blocks at the same height, but only
        one survives on the chain.

        Args:
            agent_id: The agent that mined the block
            height: The block height
        """
        # Check if this height was already recorded (de-duplication)
        if height in self.blocks_mined_by_height:
            # Already recorded - skip to avoid double-counting
            self.logger.debug(f"Block at height {height} already recorded by "
                            f"{self.blocks_mined_by_height[height]}, skipping {agent_id}")
            return

        # Initialize tracking for this agent if needed
        if agent_id not in self.recent_blocks_mined:
            self.recent_blocks_mined[agent_id] = []
        if agent_id not in self.total_blocks_mined_by_agent:
            self.total_blocks_mined_by_agent[agent_id] = 0

        # Record this height as mined by this agent (first to log wins)
        self.blocks_mined_by_height[height] = agent_id

        # Record the block (with timestamp for rate calculation)
        current_time = time.time()
        self.recent_blocks_mined[agent_id].append((height, current_time))

        # Keep only recent blocks (last 10 minutes worth)
        cutoff_time = current_time - 600
        self.recent_blocks_mined[agent_id] = [
            (h, t) for h, t in self.recent_blocks_mined[agent_id]
            if t > cutoff_time
        ]

        # Update total count
        self.total_blocks_mined_by_agent[agent_id] += 1

        self.logger.debug(f"Block mined by {agent_id} at height {height}")

    def _get_git_commit_hash(self) -> str:
        """Get the current git commit hash of the monerosim codebase."""
        try:
            import subprocess
            # Try to get git commit from the monerosim directory
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def _get_config_metadata(self) -> Dict[str, Any]:
        """Read metadata from the monerosim config file."""
        import yaml

        # Try common config file locations
        config_candidates = [
            Path("monerosim.yaml"),
            Path("config.yaml"),
            self.shared_dir / "config_metadata.json",
        ]

        # Also check parent directories
        cwd = Path.cwd()
        for parent in [cwd, cwd.parent, cwd.parent.parent]:
            config_candidates.append(parent / "monerosim.yaml")
            config_candidates.append(parent / "config.yaml")

        for config_path in config_candidates:
            try:
                if config_path.exists():
                    if config_path.suffix == '.json':
                        with open(config_path, 'r') as f:
                            return json.load(f)
                    else:
                        with open(config_path, 'r') as f:
                            config = yaml.safe_load(f)
                            if config and 'metadata' in config:
                                return config['metadata']
            except Exception as e:
                self.logger.debug(f"Could not read config from {config_path}: {e}")
                continue

        return {}

    def _initialize_status_file(self):
        """Create and initialize the status file with header."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.status_file), exist_ok=True)

            # Get config metadata and git commit
            metadata = self._get_config_metadata()
            git_commit = self._get_git_commit_hash()

            # Write initial header
            with open(self.status_file, 'w') as f:
                f.write("=" * 70 + "\n")
                f.write("  MoneroSim Simulation Monitor\n")
                f.write("=" * 70 + "\n\n")

                # Git commit info
                f.write(f"Monerosim Version: git commit {git_commit}\n")
                f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                f.write(f"Poll Interval: {self.poll_interval} seconds\n\n")

                # Config metadata if available
                if metadata:
                    f.write("-" * 70 + "\n")
                    f.write("Configuration Metadata:\n")
                    f.write("-" * 70 + "\n")

                    # Basic info
                    if 'user_request' in metadata:
                        f.write(f"  Request: {metadata.get('user_request', 'N/A')}\n")
                    if 'scenario' in metadata:
                        f.write(f"  Scenario Type: {metadata.get('scenario', 'N/A')}\n")
                    if 'generator' in metadata:
                        f.write(f"  Generator: {metadata.get('generator', 'N/A')} v{metadata.get('version', '?')}\n")

                    # Agent counts
                    agents = metadata.get('agents', {})
                    if agents:
                        f.write(f"  Agents: {agents.get('total', 'N/A')} total\n")
                        f.write(f"    - Miners: {agents.get('miners', 0)}\n")
                        f.write(f"    - Users: {agents.get('users', 0)}\n")
                        f.write(f"    - Spy Nodes: {agents.get('spy_nodes', 0)}\n")

                    # Timing info
                    timing = metadata.get('timing', {})
                    if timing:
                        f.write("  Timing:\n")
                        duration_h = timing.get('duration_s', 0) / 3600
                        bootstrap_h = timing.get('bootstrap_end_s', 0) / 3600
                        f.write(f"    - Duration: {duration_h:.1f}h ({timing.get('duration_s', 0)}s)\n")
                        f.write(f"    - Bootstrap End: {bootstrap_h:.1f}h ({timing.get('bootstrap_end_s', 0)}s)\n")
                        if 'user_spawn_start_s' in timing:
                            spawn_start = timing.get('user_spawn_start_s', 0)
                            spawn_end = timing.get('user_spawn_end_s', spawn_start)
                            f.write(f"    - User Spawn: {spawn_start}s - {spawn_end}s\n")
                        if 'activity_start_s' in timing:
                            f.write(f"    - Activity Start: {timing.get('activity_start_s', 0)}s\n")

                    # Settings
                    settings = metadata.get('settings', {})
                    if settings:
                        f.write("  Settings:\n")
                        f.write(f"    - Network: {settings.get('network', 'N/A')}\n")
                        f.write(f"    - Peer Mode: {settings.get('peer_mode', 'N/A')}\n")
                        f.write(f"    - Seed: {settings.get('seed', 'N/A')}\n")

                    f.write("\n")

                f.write("=" * 70 + "\n")
                f.write("Waiting for first status update...\n\n")
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
            # Periodically re-discover daemon log files to pick up late-joining agents
            current_time = time.time()
            if current_time - self.last_daemon_discovery_time > self.daemon_discovery_interval:
                self._discover_daemon_log_files()
                self.last_daemon_discovery_time = current_time

            # Parse daemon logs for mining activity (real-time detection)
            self._parse_daemon_logs_for_mining()

            # Collect data from all nodes
            node_data = self._collect_node_data()
            
            # Analyze network status
            network_metrics = self._analyze_network_health(node_data)
            
            # Track transactions and blocks
            self._track_transactions_and_blocks(node_data)
            
            # Write real-time status to file (includes alerts)
            self._write_status_update(node_data, network_metrics)

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

        Only polls agents that have daemon log files (meaning monerod has started).
        This prevents wasting time on RPC timeouts for agents not yet running.

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

            # Filter to only agents that have daemon log files (i.e., monerod has started)
            online_agents = []
            pending_count = 0
            for agent in agents:
                agent_id = agent.get("id", "unknown")
                # Check if this agent has a daemon log file
                if agent_id in self.daemon_log_files:
                    online_agents.append(agent)
                else:
                    pending_count += 1

            if pending_count > 0:
                self.logger.info(f"Collecting data from {len(online_agents)} online agents ({pending_count} pending startup)")
            else:
                self.logger.info(f"Collecting data from {len(online_agents)} agents")

            for agent in online_agents:
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

            # Store pending count for status reporting
            self._pending_agents_count = pending_count

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

            agent_id = rpc_info.get("agent_id", "unknown")

            # Collect daemon information
            data = {}

            try:
                info = daemon_rpc.get_info()
                current_height = info.get("height", 0)
                difficulty = info.get("difficulty", 0)

                data.update({
                    "height": current_height,
                    "connections": daemon_rpc.get_connections(),
                    "synced": info.get("synchronized", False),
                    "difficulty": difficulty,
                    "target_height": info.get("target_height", 0),
                    "incoming_connections": info.get("incoming_connections_count", 0),
                    "outgoing_connections": info.get("outgoing_connections_count", 0),
                    "network_height": info.get("height_without_bootstrap", 0)
                })

                # Update network difficulty
                if difficulty > 0:
                    self.network_difficulty = difficulty

            except Exception as e:
                data["info_error"] = str(e)

            # Determine mining status from registry and actual log parsing
            is_registered_miner = agent_id in self.miner_registry
            miner_info = self.miner_registry.get(agent_id, {})
            weight = miner_info.get("weight", 0)

            # Get actual mining activity from log parsing
            total_blocks_mined = self.total_blocks_mined_by_agent.get(agent_id, 0)
            recent_blocks = self.recent_blocks_mined.get(agent_id, [])

            # Calculate recent mining rate (blocks per 10 minutes)
            recent_block_count = len(recent_blocks)

            # A miner is "actively mining" if they've mined blocks recently or are registered
            is_actively_mining = recent_block_count > 0 or is_registered_miner

            # Calculate effective hashrate based on weight percentage
            total_weight = sum(m.get("weight", 0) for m in self.miner_registry.values())
            if total_weight > 0 and weight > 0:
                effective_hashrate = weight
            else:
                effective_hashrate = 0

            data.update({
                "mining_active": is_actively_mining,
                "mining_hashrate": effective_hashrate,
                "mining_weight": weight,
                "is_registered_miner": is_registered_miner,
                "blocks_mined_total": total_blocks_mined,
                "blocks_mined_recent": recent_block_count,
                "is_actively_mining": recent_block_count > 0
            })

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
        # Calculate total blocks mined from log parsing
        total_blocks_from_logs = sum(self.total_blocks_mined_by_agent.values())
        actively_mining_count = sum(1 for blocks in self.recent_blocks_mined.values() if len(blocks) > 0)

        metrics = {
            "total_nodes": len(node_data),
            "synced_nodes": 0,
            "active_miners": 0,
            "actively_mining": actively_mining_count,  # From log parsing
            "registered_miners": len(self.miner_registry),
            "total_connections": 0,
            "heights": [],
            "mining_hashrates": [],
            "mining_weights": [],
            "total_mining_weight": 0,
            "network_difficulty": self.network_difficulty,
            "total_blocks_mined": total_blocks_from_logs,  # From log parsing
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

            # Check mining status (from log parsing for actual activity)
            is_actively_mining = daemon.get("is_actively_mining", False)
            is_registered = daemon.get("is_registered_miner", False)

            if is_actively_mining or is_registered:
                metrics["active_miners"] += 1
                weight = daemon.get("mining_weight", 0)
                metrics["mining_hashrates"].append(daemon.get("mining_hashrate", 0))
                metrics["mining_weights"].append(weight)
                metrics["total_mining_weight"] += weight
            
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
        Track transactions and blocks across the network by querying daemon RPC
        and reading the shared state files.

        Args:
            node_data: Dictionary containing data from all nodes
        """
        try:
            # Read transaction data from shared state file
            self._read_transaction_data()

            # Find current max height and set up reference daemon
            current_max_height = 0
            total_nodes_with_txs = 0

            for node_id, data in node_data.items():
                daemon = data.get("daemon", {})
                wallet = data.get("wallet", {})

                # Track block height
                height = daemon.get("height", 0)
                if height > current_max_height:
                    current_max_height = height

                    # Set reference daemon if not already set or if this is a better candidate
                    if self.reference_daemon is None:
                        agent_info = data.get("agent_info", {})
                        rpc_info = self._get_agent_rpc_info(agent_info)
                        if rpc_info:
                            self.reference_daemon = self._get_daemon_rpc(rpc_info)

                # Track transactions in wallet
                if wallet.get("balance", 0) > 0 or wallet.get("unlocked_balance", 0) > 0:
                    # This node has received transactions
                    if node_id not in self.transaction_stats["node_tx_counts"]:
                        self.transaction_stats["node_tx_counts"][node_id] = 0
                    self.transaction_stats["node_tx_counts"][node_id] += 1
                    total_nodes_with_txs += 1

            # Update block statistics
            self.transaction_stats["last_block_height"] = current_max_height
            self.transaction_stats["blocks_mined"] = max(0, current_max_height - 1)  # Subtract genesis block

            # Query new blocks for transaction data via RPC
            self._extract_transactions_from_blocks(current_max_height)

            # Update broadcast count (nodes that have received transactions)
            if total_nodes_with_txs > len(self.transaction_stats["node_tx_counts"]):
                self.transaction_stats["total_broadcast"] = total_nodes_with_txs

            # Save enhanced tracking data
            self._save_transaction_tracking_data()

        except Exception as e:
            self.logger.error(f"Error tracking transactions and blocks: {e}")

    def _extract_transactions_from_blocks(self, current_height: int):
        """
        Extract transaction hashes from blocks via daemon RPC.

        Args:
            current_height: Current blockchain height
        """
        if not self.reference_daemon:
            self.logger.debug("No reference daemon available for block queries")
            return

        last_processed = self.transaction_stats["last_processed_height"]

        # Process new blocks since last check
        # Start from height 2 (skip genesis block) or last processed + 1
        start_height = max(2, last_processed + 1)

        if start_height > current_height:
            return  # No new blocks to process

        self.logger.debug(f"Processing blocks {start_height} to {current_height}")

        for height in range(start_height, current_height + 1):
            try:
                block_info = self.reference_daemon.get_block(height=height)

                # Extract transaction hashes from block
                tx_hashes = block_info.get("tx_hashes", [])

                if tx_hashes:
                    self.transaction_stats["tx_to_block_mapping"][height] = tx_hashes
                    self.transaction_stats["included_txs"].update(tx_hashes)
                    self.logger.debug(f"Block {height}: {len(tx_hashes)} transactions")

                self.transaction_stats["last_processed_height"] = height

            except Exception as e:
                self.logger.warning(f"Failed to get block {height}: {e}")
                # Don't update last_processed_height so we retry this block next time
                break

        # Update total transactions in blocks count
        self.transaction_stats["total_in_blocks"] = len(self.transaction_stats["included_txs"])
    
    def _read_transaction_data(self):
        """Read transaction data from the shared state file."""
        try:
            transactions_file = self.shared_dir / "transactions.json"
            if transactions_file.exists():
                with open(transactions_file, 'r') as f:
                    transactions = json.load(f)

                # Update transaction count
                self.transaction_stats["total_created"] = len(transactions)

                # Reset per-node creation counts
                self.transaction_stats["tx_created_by_node"] = {}

                # Track unique transaction hashes and per-sender counts
                for tx in transactions:
                    if isinstance(tx, dict):
                        # Track tx hash
                        if "tx_hash" in tx:
                            tx_hash = tx["tx_hash"]
                            if isinstance(tx_hash, dict) and "tx_hash" in tx_hash:
                                self.transaction_stats["unique_tx_hashes"].add(tx_hash["tx_hash"])
                            elif isinstance(tx_hash, str):
                                self.transaction_stats["unique_tx_hashes"].add(tx_hash)

                        # Track transactions created per sender node
                        if "sender_id" in tx:
                            sender = tx["sender_id"]
                            if sender not in self.transaction_stats["tx_created_by_node"]:
                                self.transaction_stats["tx_created_by_node"][sender] = 0
                            self.transaction_stats["tx_created_by_node"][sender] += 1

                self.logger.debug(f"Read {len(transactions)} transactions from shared state")

        except Exception as e:
            self.logger.error(f"Error reading transaction data: {e}")
    
    def _read_enhanced_block_data(self):
        """
        Legacy method - block data is now read via RPC in _extract_transactions_from_blocks.
        This method is kept for backwards compatibility but does nothing.
        """
        pass
    
    def _save_transaction_tracking_data(self):
        """Save enhanced transaction tracking data to shared files."""
        try:
            # Convert tx_to_block_mapping keys to strings for JSON serialization
            # (keys are block heights as integers)
            tx_mapping_serializable = {
                str(k): v for k, v in self.transaction_stats["tx_to_block_mapping"].items()
            }

            # Save transaction tracking data
            tracking_data = {
                "tx_to_block_mapping": tx_mapping_serializable,
                "included_txs": list(self.transaction_stats["included_txs"]),
                "pending_txs": list(self.transaction_stats["pending_txs"]),
                "total_in_blocks": self.transaction_stats["total_in_blocks"],
                "last_processed_height": self.transaction_stats["last_processed_height"],
                "blocks_mined": self.transaction_stats["blocks_mined"],
                "last_updated": time.time()
            }

            with open(self.tx_tracking_file, 'w') as f:
                json.dump(tracking_data, f, indent=2)

            # Generate enhanced blocks data from RPC-collected data
            enhanced_blocks = []
            for height, tx_hashes in sorted(self.transaction_stats["tx_to_block_mapping"].items()):
                enhanced_block = {
                    "height": height,
                    "transactions": tx_hashes,
                    "tx_count": len(tx_hashes)
                }
                enhanced_blocks.append(enhanced_block)

            if enhanced_blocks:
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
                # Write header with timestamp
                sim_time = self._get_simulation_time()
                f.write(f"\n{'='*60}\n")
                f.write(f"=== MoneroSim Simulation Monitor ===\n")
                f.write(f"Sim Time: {sim_time} | Cycle: {self.cycle_count}\n\n")
                
                # Write network status
                f.write("NETWORK STATUS:\n")
                pending = getattr(self, '_pending_agents_count', 0)
                total_registered = network_metrics['total_nodes'] + pending
                f.write(f"- Online Nodes: {network_metrics['total_nodes']}/{total_registered}")
                if pending > 0:
                    f.write(f" ({pending} pending startup)\n")
                else:
                    f.write("\n")
                f.write(f"- Synchronized: {network_metrics['synced_nodes']}/{network_metrics['total_nodes']} "
                       f"({network_metrics['sync_percentage']:.1f}%)\n")
                f.write(f"- Average Height: {network_metrics['avg_height']:.0f}\n")
                f.write(f"- Height Variance: {network_metrics['height_variance']:.2f}\n")

                # Show mining status with both registered and actively mining counts
                registered = network_metrics.get('registered_miners', 0)
                actively_mining = network_metrics.get('actively_mining', 0)
                total_blocks = network_metrics.get('total_blocks_mined', 0)
                f.write(f"- Registered Miners: {registered}\n")
                f.write(f"- Actively Mining: {actively_mining} (detected {total_blocks} blocks from logs)\n\n")
                
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
        f.write("(Heights polled serially - variance expected during active mining)\n\n")

        # Table header - showing Blocks mined, Weight, and TXs created
        f.write("┌─────────────┬───────┬───────┬──────────┬────────┬────────┬─────────┬──────┐\n")
        f.write("│ Node        │ Height│ Sync  │ Mining   │ Blocks │ Weight │ Conns   │ TXs  │\n")
        f.write("├─────────────┼───────┼───────┼──────────┼────────┼────────┼─────────┼──────┤\n")

        # Table rows
        for node_id, data in node_data.items():
            agent_info = data.get("agent_info", {})
            daemon = data.get("daemon", {})

            # Determine node type based on miner registry
            is_miner = node_id in self.miner_registry
            if not is_miner:
                is_miner = agent_info.get("attributes", {}).get("is_miner") == "true"
            node_type = "miner" if is_miner else "user"

            # Format values
            height = daemon.get("height", 0)
            sync_status = "✓" if daemon.get("synced", False) else "✗"

            # Mining status - show if actively mining (from log parsing)
            is_actively_mining = daemon.get("is_actively_mining", False)
            blocks_mined = daemon.get("blocks_mined_total", 0)

            if is_actively_mining:
                mining_status = "✓ Active"
            elif is_miner:
                mining_status = "◐ Idle"
            else:
                mining_status = "- N/A"

            # Show blocks mined for miners
            if is_miner:
                blocks_str = str(blocks_mined)
            else:
                blocks_str = "-"

            # Show weight for miners
            weight = daemon.get("mining_weight", 0)
            if is_miner and weight > 0:
                weight_str = f"{weight}"
            elif is_miner:
                weight_str = "-"
            else:
                weight_str = "-"

            connections = daemon.get("connections", 0)

            # Get transactions created by this node
            tx_created = self.transaction_stats["tx_created_by_node"].get(node_id, 0)
            tx_str = str(tx_created) if tx_created > 0 else "-"

            # Truncate node ID if needed
            node_display = f"{node_id} ({node_type})"
            if len(node_display) > 11:
                node_display = node_display[:11]

            f.write(f"│ {node_display:<11} │ {height:>5} │ {sync_status:<5} │ {mining_status:<8} │ {blocks_str:>6} │ {weight_str:>6} │ {connections:>7} │ {tx_str:>4} │\n")

        f.write("└─────────────┴───────┴───────┴──────────┴────────┴────────┴─────────┴──────┘\n\n")
    
    def _write_transaction_status(self, f, network_metrics: Dict[str, Any]):
        """Write transaction status information."""
        f.write("TRANSACTION STATUS:\n")
        f.write(f"- Total Pool Size: {network_metrics['total_pool_size']}\n")
        
        # Write comprehensive transaction statistics
        f.write(f"- Total Transactions Created: {self.transaction_stats['total_created']}\n")
        f.write(f"- Total Transactions in Blocks: {self.transaction_stats['total_in_blocks']}\n")
        f.write(f"- Blockchain Height: {self.transaction_stats['blocks_mined']} (excluding genesis)\n")
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

        # Show difficulty
        difficulty = network_metrics.get('network_difficulty', 0)
        if difficulty > 0:
            f.write(f"- Network Difficulty: {difficulty:,}\n")

        # Show total mining weight instead of hashrate
        total_weight = network_metrics.get('total_mining_weight', 0)
        if total_weight > 0:
            f.write(f"- Total Mining Weight: {total_weight}\n")

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
        
        # Check for no miners - use registered_miners count
        registered_miners = network_metrics.get('registered_miners', 0)
        active_miners = network_metrics.get('active_miners', 0)
        if registered_miners == 0 and active_miners == 0:
            alerts.append({
                "type": "no_miners",
                "severity": "critical",
                "message": "No miners registered or detected"
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
            
            # Convert sets to lists for JSON serialization
            tx_stats_copy = self.transaction_stats.copy()
            tx_stats_copy["unique_tx_hashes"] = list(self.transaction_stats["unique_tx_hashes"])
            tx_stats_copy["pending_txs"] = list(self.transaction_stats["pending_txs"])
            tx_stats_copy["included_txs"] = list(self.transaction_stats["included_txs"])
            
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
            
            # Convert sets to lists for JSON serialization
            tx_stats_copy = self.transaction_stats.copy()
            tx_stats_copy["unique_tx_hashes"] = list(self.transaction_stats["unique_tx_hashes"])
            tx_stats_copy["pending_txs"] = list(self.transaction_stats["pending_txs"])
            tx_stats_copy["included_txs"] = list(self.transaction_stats["included_txs"])
            
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
        parser.add_argument('--output-dir', type=str, default=None,
                          help='Shadow output directory for daemon log discovery')
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
            output_dir=args.output_dir,
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
