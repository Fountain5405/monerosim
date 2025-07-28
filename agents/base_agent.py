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
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List

from .monero_rpc import MoneroRPC, WalletRPC, RPCError


class BaseAgent(ABC):
    """Abstract base class for all Monerosim agents"""
    
    def __init__(self, agent_id: str, node_rpc_port: Optional[int] = None,
                 wallet_rpc_port: Optional[int] = None, rpc_host: str = "127.0.0.1"):
        self.agent_id = agent_id
        self.node_rpc_port = node_rpc_port
        self.wallet_rpc_port = wallet_rpc_port
        self.rpc_host = rpc_host
        self.running = True
        
        # Set up logging
        self.logger = self._setup_logging()
        
        # RPC connections (initialized in setup)
        self.node_rpc: Optional[MoneroRPC] = None
        self.wallet_rpc: Optional[WalletRPC] = None
        
        # Shared state directory
        self.shared_dir = Path("/tmp/monerosim_shared")
        self.shared_dir.mkdir(exist_ok=True)
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info(f"Initialized {self.__class__.__name__} with ID: {agent_id}")
        
    def _setup_logging(self) -> logging.Logger:
        """Set up agent-specific logging"""
        logger = logging.getLogger(f"{self.__class__.__name__}[{self.agent_id}]")
        logger.setLevel(logging.INFO)
        
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
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
    def setup(self):
        """Set up RPC connections and perform agent-specific initialization"""
        # Connect to node RPC if port provided
        if self.node_rpc_port:
            self.logger.info(f"Connecting to node RPC at {self.rpc_host}:{self.node_rpc_port}")
            self.node_rpc = MoneroRPC(self.rpc_host, self.node_rpc_port)
            try:
                self.node_rpc.wait_until_ready(max_wait=120)
                info = self.node_rpc.get_info()
                self.logger.info(f"Connected to node: height={info.get('height', 0)}")
            except RPCError as e:
                self.logger.error(f"Failed to connect to node RPC: {e}")
                raise
                
        # Connect to wallet RPC if port provided
        if self.wallet_rpc_port:
            self.logger.info(f"Connecting to wallet RPC at {self.rpc_host}:{self.wallet_rpc_port}")
            self.wallet_rpc = WalletRPC(self.rpc_host, self.wallet_rpc_port)
            try:
                self.wallet_rpc.wait_until_ready(max_wait=120)
                self.logger.info("Connected to wallet RPC")
            except RPCError as e:
                self.logger.error(f"Failed to connect to wallet RPC: {e}")
                raise
                
        # Call agent-specific setup
        self._setup_agent()
        
    @abstractmethod
    def _setup_agent(self):
        """Agent-specific setup logic (to be implemented by subclasses)"""
        pass
        
    @abstractmethod
    def run_iteration(self):
        """Single iteration of agent behavior (to be implemented by subclasses)"""
        pass
        
    def run(self):
        """Main agent loop"""
        try:
            # Initial setup
            self.setup()
            
            self.logger.info("Starting main agent loop")
            
            # Main behavior loop
            while self.running:
                try:
                    self.run_iteration()
                except Exception as e:
                    self.logger.error(f"Error in agent iteration: {e}", exc_info=True)
                    # Continue running unless it's a critical error
                    
                # Small sleep to prevent tight loops
                time.sleep(0.1)
                
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
        
    # Utility methods
    
    def wait_for_height(self, target_height: int, timeout: int = 300):
        """Wait for blockchain to reach target height"""
        if not self.node_rpc:
            raise RuntimeError("No node RPC connection")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_height = self.node_rpc.get_height()
            if current_height >= target_height:
                return True
            self.logger.debug(f"Waiting for height {target_height}, current: {current_height}")
            time.sleep(1)
            
        return False
        
    def wait_for_wallet_sync(self, timeout: int = 300):
        """Wait for wallet to sync with daemon"""
        if not self.wallet_rpc or not self.node_rpc:
            raise RuntimeError("Missing RPC connections")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            wallet_height = self.wallet_rpc.get_height()
            daemon_height = self.node_rpc.get_height()
            
            if wallet_height >= daemon_height - 1:  # Allow 1 block difference
                self.logger.info(f"Wallet synced at height {wallet_height}")
                return True
                
            self.logger.debug(f"Wallet sync: {wallet_height}/{daemon_height}")
            self.wallet_rpc.refresh()
            time.sleep(1)
            
        return False
        
    @staticmethod
    def create_argument_parser(description: str) -> argparse.ArgumentParser:
        """Create standard argument parser for agents"""
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument('--id', required=True, help='Agent ID')
        parser.add_argument('--node-rpc', type=int, help='Node RPC port')
        parser.add_argument('--wallet-rpc', type=int, help='Wallet RPC port')
        parser.add_argument('--rpc-host', default='127.0.0.1', help='RPC host address')
        parser.add_argument('--log-level', default='INFO',
                          choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                          help='Logging level')
        return parser