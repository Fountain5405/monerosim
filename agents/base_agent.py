"""
Base agent framework for Monerosim network participants.
Provides lifecycle management, RPC connections, and shared functionality.
"""

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
import fcntl
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List

from .monero_rpc import MoneroRPC, WalletRPC, RPCError
from .public_node_discovery import PublicNodeDiscovery, DaemonSelectionStrategy, parse_selection_strategy

# Shared constants
DEFAULT_SHARED_DIR = "/tmp/monerosim_shared"
MONERO_P2P_PORT = 18080
MONERO_RPC_PORT = 18081
MONERO_WALLET_RPC_PORT = 18082
SHADOW_EPOCH = 946684800  # 2000-01-01T00:00:00 UTC


def retry_with_backoff(fn, *, max_retries: int = 3, initial_delay: float = 1.0,
                       backoff_factor: float = 2.0, logger: Optional[logging.Logger] = None):
    """Call *fn* with exponential-backoff retries.

    Args:
        fn: Zero-argument callable to execute.
        max_retries: Maximum number of attempts.
        initial_delay: Seconds to wait after the first failure.
        backoff_factor: Multiplier applied to the delay after each failure.
        logger: Optional logger for warning/error messages.

    Returns:
        The return value of *fn* on success.

    Raises:
        The exception from the last failed attempt if all retries are exhausted.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            if logger:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {exc}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= backoff_factor
            else:
                if logger:
                    logger.error(f"All {max_retries} attempts failed")
                raise


class BaseAgent(ABC):
    """Abstract base class for all Monerosim agents"""

    def __init__(self, agent_id: str,
                 shared_dir: Optional[Path] = None,
                 daemon_rpc_port: Optional[int] = None,
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
        self.daemon_rpc_port = daemon_rpc_port
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
            shared_dir = Path(DEFAULT_SHARED_DIR)
        self._shared_dir = shared_dir
        self._shared_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Initialize RPC connections first (required for logging context)
        self.daemon_rpc: Optional[MoneroRPC] = None
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
        
    @staticmethod
    def parse_bool(value, default: bool = False) -> bool:
        """Parse a boolean from various types (str, bool, int, float).

        Accepts 'true'/'1'/'yes'/'on' as True and 'false'/'0'/'no'/'off' as False
        (case-insensitive). Returns *default* for unrecognized values.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lower = value.lower()
            if lower in ('true', '1', 'yes', 'on'):
                return True
            if lower in ('false', '0', 'no', 'off'):
                return False
        return default

    def _extract_is_miner(self):
        """Extract is_miner from attributes and handle both string and boolean values"""
        if 'is_miner' in self.attributes:
            self._is_miner = self.parse_bool(self.attributes['is_miner'])
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
        self._is_wallet_only = (self.remote_daemon is not None and self.daemon_rpc_port is None)

        # Connect to daemon RPC if port provided (local daemon)
        if self.daemon_rpc_port:
            self.logger.info(f"Connecting to daemon RPC at {self.rpc_host}:{self.daemon_rpc_port}")
            self.daemon_rpc = MoneroRPC(self.rpc_host, self.daemon_rpc_port)
            try:
                self.daemon_rpc.wait_until_ready(max_wait=120)
                info = self.daemon_rpc.get_info()
                self.logger.info(f"Connected to daemon: height={info.get('height', 0)}")
            except RPCError as e:
                self.logger.error(f"Failed to connect to daemon RPC: {e}")
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

            while self.running:
                self.logger.debug("Starting agent iteration")
                try:
                    sleep_duration = self.run_iteration()
                    sleep_duration = sleep_duration or 1.0
                except Exception as e:
                    self.logger.error(f"Error in agent iteration: {e}", exc_info=True)
                    sleep_duration = 5.0  # Default sleep on error

                # Sleep for the requested duration, checking for shutdown every second
                # This reduces wakeups from 10/sec (old 0.1s sleep) to 1/sec while
                # still being responsive to shutdown signals
                self.interruptible_sleep(sleep_duration)

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
            except Exception as e:
                self.logger.debug(f"Error closing wallet during cleanup: {e}")
                
        # Call agent-specific cleanup
        self._cleanup_agent()
        
        self.logger.info("Agent shutdown complete")
        
    def _cleanup_agent(self):
        """Agent-specific cleanup logic (can be overridden by subclasses)"""
        pass

    def restart_wallet_rpc(self) -> bool:
        """Kill and restart the wallet-rpc process.

        Uses the WALLET_RPC_CMD environment variable (set by the Rust config
        generator) to know how to re-launch the process.  Returns True on
        success, False on failure.
        """
        wallet_cmd = os.environ.get('WALLET_RPC_CMD')
        if not wallet_cmd:
            self.logger.warning(
                "WALLET_RPC_CMD not set — cannot restart wallet-rpc "
                "(config may predate restart support)"
            )
            return False

        self.logger.info("Attempting wallet-rpc process restart")

        # Step 1: Find and kill the existing process
        pid = self._find_wallet_rpc_pid()
        if pid is not None:
            self.logger.info(f"Found wallet-rpc process with PID {pid}, sending SIGKILL")
            try:
                os.kill(pid, signal.SIGKILL)
                # Wait for process to die (up to 5s)
                for _ in range(50):
                    try:
                        os.kill(pid, 0)  # Check if still alive
                        time.sleep(0.1)
                    except OSError:
                        break
                self.logger.info(f"Wallet-rpc process {pid} terminated")
            except OSError as e:
                self.logger.warning(f"Failed to kill wallet-rpc PID {pid}: {e}")
        else:
            self.logger.warning("Could not find wallet-rpc PID — process may already be dead")

        # Step 2: Wait for port release
        time.sleep(2)

        # Step 3: Spawn new wallet-rpc process
        try:
            self.logger.info(f"Spawning new wallet-rpc: {wallet_cmd}")
            subprocess.Popen(
                wallet_cmd,
                shell=True,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            self.logger.error(f"Failed to spawn wallet-rpc process: {e}")
            return False

        # Step 4: Reset RPC session and wait for new process to be ready
        try:
            self.wallet_rpc.reset_session()
            self.wallet_rpc.wait_until_ready(max_wait=120)
            self.logger.info("New wallet-rpc process is ready")
        except Exception as e:
            self.logger.error(f"New wallet-rpc process failed to become ready: {e}")
            return False

        # Step 5: Re-open wallet and reconnect to daemon
        try:
            wallet_name = f"{self.agent_id}_wallet"
            self.wallet_rpc.open_wallet(wallet_name, password="")
            self.logger.info(f"Re-opened wallet '{wallet_name}'")

            if self.daemon_rpc_port:
                daemon_address = f"http://{self.rpc_host}:{self.daemon_rpc_port}"
                self.wallet_rpc.set_daemon(daemon_address, trusted=True)
                self.logger.info(f"Wallet reconnected to daemon at {daemon_address}")

            self.wallet_rpc.refresh()
            self.logger.info("Wallet refresh completed after restart")
        except Exception as e:
            self.logger.error(f"Failed to restore wallet state after restart: {e}")
            return False

        self.logger.info("Wallet-rpc restart completed successfully")
        return True

    def _find_wallet_rpc_pid(self) -> Optional[int]:
        """Find the PID of the wallet-rpc process for this agent.

        Uses pgrep as primary method with /proc scan as fallback.
        Returns the highest matching PID (the actual process, not a bash wrapper).
        """
        pattern = f'monero-wallet-rpc.*--rpc-bind-ip={self.rpc_host}'

        # Primary: use pgrep
        try:
            result = subprocess.run(
                ['pgrep', '-f', pattern],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = [int(p) for p in result.stdout.strip().split('\n') if p.strip()]
                if pids:
                    pid = max(pids)
                    self.logger.debug(f"pgrep found wallet-rpc PID(s): {pids}, using {pid}")
                    return pid
        except Exception as e:
            self.logger.debug(f"pgrep failed: {e}")

        # Fallback: scan /proc
        try:
            pids = []
            for entry in os.listdir('/proc'):
                if not entry.isdigit():
                    continue
                try:
                    cmdline_path = f'/proc/{entry}/cmdline'
                    with open(cmdline_path, 'rb') as f:
                        cmdline = f.read().decode('utf-8', errors='replace')
                    # /proc cmdline uses null bytes as separators
                    if 'monero-wallet-rpc' in cmdline and f'--rpc-bind-ip={self.rpc_host}' in cmdline:
                        pids.append(int(entry))
                except (IOError, OSError, ValueError):
                    continue
            if pids:
                pid = max(pids)
                self.logger.debug(f"/proc scan found wallet-rpc PID(s): {pids}, using {pid}")
                return pid
        except Exception as e:
            self.logger.debug(f"/proc scan failed: {e}")

        return None

    def interruptible_sleep(self, duration: float) -> None:
        """Sleep for *duration* seconds, checking ``self.running`` every second.

        Returns early if ``self.running`` becomes ``False``.
        """
        remaining = duration
        while remaining > 0 and self.running:
            time.sleep(min(remaining, 1.0))
            remaining -= 1.0

    def _is_public_node(self) -> bool:
        """Check if this agent is configured as a public node"""
        return self.parse_bool(self.attributes.get('is_public_node', ''))

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
        if not self.daemon_rpc_port:
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
    
    def write_shared_state(self, filename: str, data: Dict[str, Any], use_lock: bool = True):
        """Write data to shared state file with optional locking for determinism.

        Args:
            filename: Name of the file to write
            data: Dictionary data to write as JSON
            use_lock: If True, use file locking to prevent race conditions
        """
        filepath = self.shared_dir / filename
        lock_path = filepath.with_suffix('.lock')
        temp_filepath = filepath.with_suffix('.tmp')

        try:
            if use_lock:
                # Use lock file to prevent race conditions
                with open(lock_path, 'w') as lock_f:
                    fcntl.flock(lock_f, fcntl.LOCK_EX)
                    try:
                        with open(temp_filepath, 'w') as f:
                            json.dump(data, f, indent=2)
                        # Atomic rename
                        temp_filepath.rename(filepath)
                    finally:
                        fcntl.flock(lock_f, fcntl.LOCK_UN)
            else:
                with open(temp_filepath, 'w') as f:
                    json.dump(data, f, indent=2)
                # Atomic rename
                temp_filepath.rename(filepath)
            self.logger.debug(f"Wrote shared state to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to write shared state {filename}: {e}")
            raise
            
    def read_shared_state(self, filename: str, use_lock: bool = False) -> Optional[Dict[str, Any]]:
        """Read data from shared state file with optional locking.

        Args:
            filename: Name of the file to read
            use_lock: If True, use shared lock while reading (for consistency)
        """
        filepath = self.shared_dir / filename
        lock_path = filepath.with_suffix('.lock')

        try:
            if filepath.exists():
                if use_lock:
                    with open(lock_path, 'w') as lock_f:
                        fcntl.flock(lock_f, fcntl.LOCK_SH)  # Shared lock for reading
                        try:
                            with open(filepath, 'r') as f:
                                return json.load(f)
                        finally:
                            fcntl.flock(lock_f, fcntl.LOCK_UN)
                else:
                    with open(filepath, 'r') as f:
                        return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Failed to read shared state {filename}: {e}")
            return None

    def append_shared_list(self, filename: str, item: Any):
        """Append item to a shared list file with locking to prevent race conditions.

        Uses exclusive locking to ensure atomic read-modify-write operations.
        """
        filepath = self.shared_dir / filename
        lock_path = filepath.with_suffix('.lock')
        temp_filepath = filepath.with_suffix('.tmp')

        try:
            with open(lock_path, 'w') as lock_f:
                fcntl.flock(lock_f, fcntl.LOCK_EX)
                try:
                    # Read current data
                    if filepath.exists():
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                    else:
                        data = []

                    # Append new item
                    data.append(item)

                    # Write atomically
                    with open(temp_filepath, 'w') as f:
                        json.dump(data, f, indent=2)
                    temp_filepath.rename(filepath)
                finally:
                    fcntl.flock(lock_f, fcntl.LOCK_UN)
            self.logger.debug(f"Appended item to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to append to shared list {filename}: {e}")
            raise
        
    def read_shared_list(self, filename: str) -> List[Any]:
        """Read a shared list file"""
        data = self.read_shared_state(filename)
        return data if isinstance(data, list) else []
        
    def _register_self(self):
        """Register this agent in the node registry with atomic file updates"""
        registry_path = self.shared_dir / "agent_registry.json"
        lock_path = self.shared_dir / "agent_registry.lock"
        
        self.logger.debug(f"Registering in agent registry: {registry_path}")

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
                            "type": re.sub(r'(?<=[a-z])(?=[A-Z])', '_', self.__class__.__name__).lower().removesuffix('_agent'),
                            "attributes": self.attributes,
                            "hash_rate": getattr(self, 'hash_rate', None),
                            "ip_addr": self.rpc_host,
                            "p2p_port": self.p2p_port,
                            "daemon_rpc_port": self.daemon_rpc_port,
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
        if not self.daemon_rpc:
            raise RuntimeError("No agent RPC connection")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_height = self.daemon_rpc.get_height()
            if current_height >= target_height:
                return True
            self.logger.debug(f"Waiting for height {target_height}, current: {current_height}")
            time.sleep(1)
            
        return False
        
    def wait_for_wallet_sync(self, timeout: int = 300):
        """Wait for wallet to sync with daemon"""
        if not self.wallet_rpc or not self.daemon_rpc:
            raise RuntimeError("Missing RPC connections")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            wallet_height = self.wallet_rpc.get_height()
            daemon_height = self.daemon_rpc.get_height()
            
            if wallet_height >= daemon_height - 1:  # Allow 1 block difference
                self.logger.info(f"Wallet synced at height {wallet_height}")
                return True
                
            self.logger.debug(f"Wallet sync: {wallet_height}/{daemon_height}")
            self.wallet_rpc.refresh()
            time.sleep(1)
            
        return False
        
    @staticmethod
    def create_argument_parser(description: str, default_shared_dir: str = DEFAULT_SHARED_DIR,
                             default_rpc_host: str = '127.0.0.1', default_log_level: str = 'INFO') -> argparse.ArgumentParser:
        """Create standard argument parser for agents"""
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument('--id', required=True, help='Agent ID')
        parser.add_argument('--shared-dir', type=Path, default=Path(default_shared_dir),
                          help='Shared directory for simulation state')
        parser.add_argument('--rpc-host', default=default_rpc_host, help='RPC host address')
        parser.add_argument('--daemon-rpc-port', type=int, help='Daemon RPC port')
        parser.add_argument('--agent-rpc-port', type=int, dest='daemon_rpc_port',
                          help='(Deprecated: use --daemon-rpc-port) Daemon RPC port')
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