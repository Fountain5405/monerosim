"""
Base agent framework for Monerosim network participants.
Provides lifecycle management, RPC connections, and shared functionality.
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
import fcntl
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List

from .monero_rpc import MoneroRPC, WalletRPC, RPCError
from .public_node_discovery import PublicNodeDiscovery, DaemonSelectionStrategy, parse_selection_strategy


class BaseAgent(ABC):
    """Abstract base class for all Monerosim agents"""

    def __init__(self, agent_id: str,
                 shared_dir: Optional[Path] = None,
                 agent_rpc_port: Optional[int] = None,
                 wallet_rpc_port: Optional[int] = None,
                 p2p_port: Optional[int] = None,
                 rpc_host: str = "127.0.0.1",
                 log_level: str = "INFO",
                 attributes: Optional[List[str]] = None,
                 hash_rate: Optional[int] = None,
                 tx_frequency: Optional[int] = None,
                 remote_daemon: Optional[str] = None,
                 daemon_selection_strategy: Optional[str] = None):
        self.agent_id = agent_id
        self._shared_dir = shared_dir
        self.agent_rpc_port = agent_rpc_port
        self.wallet_rpc_port = wallet_rpc_port
        self.p2p_port = p2p_port
        self.rpc_host = rpc_host
        self.log_level = log_level
        self.attributes_list = attributes or []
        self.hash_rate = hash_rate
        self.tx_frequency = tx_frequency
        self.remote_daemon = remote_daemon  # Remote daemon address or "auto"
        self.daemon_selection_strategy = daemon_selection_strategy  # Strategy for auto-discovery
        self.running = True
        self._is_miner = False  # Default to False
        self._is_wallet_only = False  # Will be set in setup if no local daemon

        # Set up logging first
        self.logger = self._setup_logging()
        
        # Convert attributes list to a dictionary
        # attributes_list is a list of [key, value] pairs from argparse action='append'
        self.attributes: Dict[str, Any] = {}
        if self.attributes_list:
            for pair in self.attributes_list:
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    self.attributes[pair[0]] = pair[1]
                else:
                    self.logger.warning(f"Invalid attribute pair: {pair}")
        
        # Extract is_miner from attributes
        self._extract_is_miner()
        
        # Shared state directory
        if shared_dir is None:
            shared_dir = Path("/tmp/monerosim_shared")
        self._shared_dir = shared_dir
        self._shared_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Initialize RPC connections first (required for logging context)
        self.agent_rpc: Optional[MoneroRPC] = None
        self.wallet_rpc: Optional[WalletRPC] = None
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info(f"Initialized {self.__class__.__name__} with ID: {agent_id}")
        self.logger.debug(f"Shared directory: {self._shared_dir}")
        
    @property
    def shared_dir(self):
        return self._shared_dir
        
    @shared_dir.setter
    def shared_dir(self, value):
        self._shared_dir = value
        
    @property
    def is_miner(self) -> bool:
        """Return whether this agent is a miner"""
        return self._is_miner
        
    def _extract_is_miner(self):
        """Extract is_miner from attributes and handle both string and boolean values"""
        if 'is_miner' in self.attributes:
            is_miner_value = self.attributes['is_miner']
            
            # Handle string representations
            if isinstance(is_miner_value, str):
                if is_miner_value.lower() in ('true', '1', 'yes', 'on'):
                    self._is_miner = True
                elif is_miner_value.lower() in ('false', '0', 'no', 'off'):
                    self._is_miner = False
                else:
                    self.logger.warning(f"Invalid string value for is_miner: '{is_miner_value}'. Defaulting to False.")
                    self._is_miner = False
            
            # Handle boolean values
            elif isinstance(is_miner_value, bool):
                self._is_miner = is_miner_value
            
            # Handle numeric values
            elif isinstance(is_miner_value, (int, float)):
                self._is_miner = bool(is_miner_value)
            
            # Handle other types
            else:
                self.logger.warning(f"Unsupported type for is_miner: {type(is_miner_value)}. Defaulting to False.")
                self._is_miner = False
                
            self.logger.debug(f"Extracted is_miner={self._is_miner} from attributes")
        else:
            self.logger.debug("No is_miner attribute found, defaulting to False")
            self._is_miner = False
            
    def _setup_logging(self) -> logging.Logger:
        """Set up agent-specific logging"""
        logger = logging.getLogger(f"{self.__class__.__name__}[{self.agent_id}]")
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        logger.setLevel(level)
        
        # Console handler with formatting
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            f'%(asctime)s - {self.agent_id} - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, setting self.running to False")
        self.running = False
        self.logger.info("Shutdown signal handled")
        
    def setup(self):
        """Set up RPC connections and perform agent-specific initialization"""
        # Determine if this is a wallet-only agent
        self._is_wallet_only = (self.remote_daemon is not None and self.agent_rpc_port is None)

        # Connect to agent RPC if port provided (local daemon)
        if self.agent_rpc_port:
            self.logger.info(f"Connecting to agent RPC at {self.rpc_host}:{self.agent_rpc_port}")
            self.agent_rpc = MoneroRPC(self.rpc_host, self.agent_rpc_port)
            try:
                self.agent_rpc.wait_until_ready(max_wait=120)
                info = self.agent_rpc.get_info()
                self.logger.info(f"Connected to agent: height={info.get('height', 0)}")
            except RPCError as e:
                self.logger.error(f"Failed to connect to agent RPC: {e}")
                raise

        # Connect to wallet RPC if port provided
        if self.wallet_rpc_port:
            self.logger.info(f"Connecting to wallet RPC at {self.rpc_host}:{self.wallet_rpc_port}")
            self.wallet_rpc = WalletRPC(self.rpc_host, self.wallet_rpc_port)
            try:
                self.wallet_rpc.wait_until_ready(max_wait=180)
                self.logger.info("Connected to wallet RPC")
            except RPCError as e:
                self.logger.error(f"Failed to connect to wallet RPC: {e}")
                raise

            # For wallet-only agents, set up remote daemon connection
            if self._is_wallet_only:
                self._setup_remote_daemon_connection()

        # Call agent-specific setup after RPC connections are established
        self._setup_agent()

        # Register self in the node registry after wallet is set up
        self._register_self()

        # If this agent is a public node, register in the public nodes registry
        if self._is_public_node():
            self._register_as_public_node()
        
    @abstractmethod
    def _setup_agent(self):
        """Agent-specific setup logic (to be implemented by subclasses)"""
        pass
        
    @abstractmethod
    def run_iteration(self) -> float:
        """
        Single iteration of agent behavior.
        Returns:
            float: The recommended time to sleep (in seconds) before the next iteration.
        """
        pass

    def run(self):
        """Main agent loop"""
        try:
            self.setup()
            self.logger.info("Starting main agent loop")

            next_run_time = time.time()

            while self.running:
                if time.time() >= next_run_time:
                    self.logger.debug("Starting agent iteration")
                    try:
                        sleep_duration = self.run_iteration()
                        next_run_time = time.time() + (sleep_duration or 1.0)
                    except Exception as e:
                        self.logger.error(f"Error in agent iteration: {e}", exc_info=True)
                        next_run_time = time.time() + 5  # Default sleep on error

                # Responsive sleep
                time.sleep(0.1)

            self.logger.info("Agent run loop finished")
                
        except Exception as e:
            self.logger.error(f"Fatal error in agent: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources before shutdown"""
        self.logger.info("Cleaning up agent resources")
        
        # Close wallet if open
        if self.wallet_rpc:
            try:
                self.wallet_rpc.close_wallet()
            except:
                pass
                
        # Call agent-specific cleanup
        self._cleanup_agent()
        
        self.logger.info("Agent shutdown complete")
        
    def _cleanup_agent(self):
        """Agent-specific cleanup logic (can be overridden by subclasses)"""
        pass

    def _is_public_node(self) -> bool:
        """Check if this agent is configured as a public node"""
        is_public = self.attributes.get('is_public_node', '')
        if isinstance(is_public, str):
            return is_public.lower() in ('true', '1', 'yes', 'on')
        return bool(is_public)

    def _setup_remote_daemon_connection(self):
        """
        Set up connection to a remote daemon for wallet-only agents.

        This method handles both explicit daemon addresses and auto-discovery
        from the public nodes registry.
        """
        if not self.wallet_rpc:
            self.logger.warning("Cannot set up remote daemon: no wallet RPC connection")
            return

        daemon_address = None

        if self.remote_daemon == "auto":
            # Use public node discovery to find a daemon
            self.logger.info("Auto-discovering remote daemon from public nodes registry")
            discovery = PublicNodeDiscovery(self.shared_dir)
            strategy = parse_selection_strategy(self.daemon_selection_strategy)

            daemon_address = discovery.select_daemon(
                strategy=strategy,
                exclude_ids=[self.agent_id]  # Don't select ourselves
            )

            if not daemon_address:
                self.logger.error("No public nodes available for auto-discovery")
                raise RuntimeError("Failed to find a remote daemon via auto-discovery")

            self.logger.info(f"Auto-discovered daemon: {daemon_address} (strategy: {strategy.value})")
        elif self.remote_daemon:
            # Use the explicitly provided daemon address
            daemon_address = self.remote_daemon
            self.logger.info(f"Using configured remote daemon: {daemon_address}")

        if daemon_address:
            # Connect wallet to the remote daemon via set_daemon RPC call
            try:
                self.logger.info(f"Setting wallet daemon to {daemon_address}")
                self.wallet_rpc.set_daemon(daemon_address)
                self.logger.info(f"Successfully connected wallet to remote daemon: {daemon_address}")
            except RPCError as e:
                self.logger.error(f"Failed to set remote daemon: {e}")
                raise

    def _register_as_public_node(self):
        """
        Register this agent as a public node in the public nodes registry.

        This updates the status to 'available' for this agent in public_nodes.json.
        """
        if not self.agent_rpc_port:
            self.logger.warning("Cannot register as public node: no local daemon")
            return

        discovery = PublicNodeDiscovery(self.shared_dir)
        success = discovery.update_node_status(
            agent_id=self.agent_id,
            status="available"
        )

        if success:
            self.logger.info(f"Registered {self.agent_id} as available public node")
        else:
            self.logger.warning(f"Failed to register {self.agent_id} as public node")

    # Shared state management methods
    
    def write_shared_state(self, filename: str, data: Dict[str, Any]):
        """Write data to shared state file"""
        filepath = self.shared_dir / filename
        temp_filepath = filepath.with_suffix('.tmp')
        
        try:
            with open(temp_filepath, 'w') as f:
                json.dump(data, f, indent=2)
            # Atomic rename
            temp_filepath.rename(filepath)
            self.logger.debug(f"Wrote shared state to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to write shared state {filename}: {e}")
            raise
            
    def read_shared_state(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read data from shared state file"""
        filepath = self.shared_dir / filename
        
        try:
            if filepath.exists():
                with open(filepath, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Failed to read shared state {filename}: {e}")
            return None
            
    def append_shared_list(self, filename: str, item: Any):
        """Append item to a shared list file"""
        data = self.read_shared_state(filename) or []
        if not isinstance(data, list):
            data = []
        data.append(item)
        self.write_shared_state(filename, data)
        
    def read_shared_list(self, filename: str) -> List[Any]:
        """Read a shared list file"""
        data = self.read_shared_state(filename)
        return data if isinstance(data, list) else []
        
    def _register_self(self):
        """Register this agent in the node registry with atomic file updates"""
        registry_path = self.shared_dir / "agent_registry.json"
        lock_path = self.shared_dir / "agent_registry.lock"
        
        self.logger.info(f"Attempting to register in agent registry: {registry_path.resolve()}")
        
        # DIAGNOSTIC: Check if shared directory exists and is accessible
        self.logger.info(f"Shared directory exists: {self.shared_dir.exists()}")
        self.logger.info(f"Shared directory is directory: {self.shared_dir.is_dir()}")
        self.logger.info(f"Registry file exists: {registry_path.exists()}")
        
        if registry_path.exists():
            try:
                file_size = registry_path.stat().st_size
                self.logger.info(f"Registry file size: {file_size} bytes")
                with open(registry_path, 'r') as f:
                    content_preview = f.read(200)
                    self.logger.info(f"Registry file preview: {content_preview[:200]}")
            except Exception as e:
                self.logger.error(f"Failed to read existing registry file: {e}")
        else:
            self.logger.warning(f"Registry file does NOT exist at {registry_path.resolve()}")
            self.logger.info(f"Directory contents: {list(self.shared_dir.iterdir()) if self.shared_dir.exists() else 'N/A'}")

        # First, ensure the file exists using a separate lock file for creation
        try:
            with open(lock_path, "w") as lock_f:
                self.logger.debug(f"Acquiring lock on {lock_path}")
                fcntl.flock(lock_f, fcntl.LOCK_EX)
                self.logger.debug(f"Acquired lock on {lock_path}")
                try:
                    if not registry_path.exists():
                        self.logger.warning(f"Registry file not found at {registry_path}. Creating it.")
                        with open(registry_path, "w") as f:
                            json.dump({"agents": []}, f, indent=4)
                        self.logger.info(f"Successfully created registry file at {registry_path}")
                finally:
                    self.logger.debug(f"Releasing lock on {lock_path}")
                    fcntl.flock(lock_f, fcntl.LOCK_UN)
        except Exception as e:
            self.logger.error(f"Failed to create or lock registry file: {e}", exc_info=True)
            return

        # Now, atomically update the now-existing registry file
        try:
            with open(registry_path, "r+") as f:
                self.logger.debug(f"Acquiring lock on {registry_path}")
                fcntl.flock(f, fcntl.LOCK_EX)
                self.logger.debug(f"Acquired lock on {registry_path}")
                try:
                    # Handle potentially empty file
                    content = f.read()
                    if not content.strip():
                        data = {"agents": []}
                    else:
                        f.seek(0)
                        data = json.load(f)
                    
                    # Find and update the agent's entry or create a new one
                    agent_found = False
                    for agent in data.get("agents", []):
                        if agent.get("id") == self.agent_id:
                            agent["wallet_address"] = getattr(self, 'wallet_address', None)
                            agent_found = True
                            break
                    
                    if not agent_found:
                        new_agent_entry = {
                            "id": self.agent_id,
                            "type": self.__class__.__name__.lower().replace('agent', ''),
                            "attributes": self.attributes,
                            "hash_rate": getattr(self, 'hash_rate', None),
                            "ip_addr": self.rpc_host,
                            "p2p_port": self.p2p_port,
                            "agent_rpc_port": self.agent_rpc_port,
                            "wallet_rpc_port": self.wallet_rpc_port,
                            "wallet_address": getattr(self, 'wallet_address', None),
                            "timestamp": time.time()
                        }
                        data.setdefault("agents", []).append(new_agent_entry)
                    
                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
                finally:
                    self.logger.debug(f"Releasing lock on {registry_path}")
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            self.logger.error(f"Failed to lock and update registry file: {e}", exc_info=True)
            return

        self.logger.info(f"Successfully registered agent {self.agent_id} in agent registry")
        
    # Utility methods
    
    def wait_for_height(self, target_height: int, timeout: int = 300):
        """Wait for blockchain to reach target height"""
        if not self.agent_rpc:
            raise RuntimeError("No agent RPC connection")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_height = self.agent_rpc.get_height()
            if current_height >= target_height:
                return True
            self.logger.debug(f"Waiting for height {target_height}, current: {current_height}")
            time.sleep(1)
            
        return False
        
    def wait_for_wallet_sync(self, timeout: int = 300):
        """Wait for wallet to sync with daemon"""
        if not self.wallet_rpc or not self.agent_rpc:
            raise RuntimeError("Missing RPC connections")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            wallet_height = self.wallet_rpc.get_height()
            daemon_height = self.agent_rpc.get_height()
            
            if wallet_height >= daemon_height - 1:  # Allow 1 block difference
                self.logger.info(f"Wallet synced at height {wallet_height}")
                return True
                
            self.logger.debug(f"Wallet sync: {wallet_height}/{daemon_height}")
            self.wallet_rpc.refresh()
            time.sleep(1)
            
        return False
        
    @staticmethod
    def create_argument_parser(description: str, default_shared_dir: str = '/tmp/monerosim_shared',
                             default_rpc_host: str = '127.0.0.1', default_log_level: str = 'INFO') -> argparse.ArgumentParser:
        """Create standard argument parser for agents"""
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument('--id', required=True, help='Agent ID')
        parser.add_argument('--shared-dir', type=Path, default=Path(default_shared_dir),
                          help='Shared directory for simulation state')
        parser.add_argument('--rpc-host', default=default_rpc_host, help='RPC host address')
        parser.add_argument('--agent-rpc-port', type=int, help='Agent RPC port')
        parser.add_argument('--wallet-rpc-port', type=int, help='Wallet RPC port')
        parser.add_argument('--p2p-port', type=int, help='P2P port of the agent\'s node')
        parser.add_argument('--log-level', default=default_log_level,
                          choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Logging level')
        parser.add_argument('--attributes', nargs=2, action='append', default=[], metavar=('KEY', 'VALUE'), help='Agent attribute as key-value pair (can be specified multiple times)')
        parser.add_argument('--hash-rate', type=int, help='Hash rate for mining agents')
        parser.add_argument('--tx-frequency', type=int, help='Transaction frequency in seconds for regular users')
        parser.add_argument('--remote-daemon', type=str, help='Remote daemon address (ip:port) or "auto" for public node discovery')
        parser.add_argument('--daemon-selection-strategy', type=str, choices=['random', 'first', 'round_robin'],
                          default='random', help='Strategy for selecting a daemon when using auto-discovery')
        return parser