#!/usr/bin/env python3
"""
error_handling.py - Standardized error handling library for MoneroSim

This library provides common error handling, logging, retry mechanisms,
and verification functions for critical processes.

This is a Python port of error_handling.sh, providing the same functionality
in a more Pythonic way.
"""

import sys
import time
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Callable
from pathlib import Path
from enum import Enum
import subprocess
from functools import wraps

# ===== ERROR LOGGING FUNCTIONS =====

class LogLevel(Enum):
    """Enumeration for log severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ColorCodes:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    NC = '\033[0m'  # No Color

class ErrorHandler:
    """Main error handling class providing logging and utility functions."""
    
    def __init__(self, error_log_file: str = "monerosim_errors.log"):
        """
        Initialize the error handler.
        
        Args:
            error_log_file: Path to the error log file
        """
        self.error_log_file = Path(error_log_file)
        self._setup_file_logger()
    
    def _setup_file_logger(self):
        """Set up file logging for errors and critical messages."""
        self.file_logger = logging.getLogger('monerosim_errors')
        self.file_logger.setLevel(logging.ERROR)
        
        # Create file handler
        file_handler = logging.FileHandler(self.error_log_file, mode='a')
        file_handler.setLevel(logging.ERROR)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(component)s] %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.file_logger.addHandler(file_handler)
    
    def log_message(self, level: LogLevel, component: str, message: str) -> None:
        """
        Log a message with timestamp and severity level.
        
        Args:
            level: Severity level of the message
            component: Component name generating the log
            message: The log message
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Set color based on severity level
        color_map = {
            LogLevel.INFO: ColorCodes.GREEN,
            LogLevel.WARNING: ColorCodes.YELLOW,
            LogLevel.ERROR: ColorCodes.RED,
            LogLevel.CRITICAL: ColorCodes.PURPLE
        }
        color = color_map.get(level, ColorCodes.BLUE)
        
        # Print to stderr with color
        print(f"{color}{timestamp} [{level.value}] [{component}] {message}{ColorCodes.NC}", 
              file=sys.stderr)
        
        # Log to file if error or critical
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            self.file_logger.log(
                logging.ERROR if level == LogLevel.ERROR else logging.CRITICAL,
                message,
                extra={'component': component}
            )
    
    def log_info(self, component: str, message: str) -> None:
        """Log an info message."""
        self.log_message(LogLevel.INFO, component, message)
    
    def log_warning(self, component: str, message: str) -> None:
        """Log a warning message."""
        self.log_message(LogLevel.WARNING, component, message)
    
    def log_error(self, component: str, message: str) -> None:
        """Log an error message."""
        self.log_message(LogLevel.ERROR, component, message)
    
    def log_critical(self, component: str, message: str) -> None:
        """Log a critical message."""
        self.log_message(LogLevel.CRITICAL, component, message)

# ===== RETRY MECHANISMS =====

def exponential_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt: Current attempt number (1-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        
    Returns:
        Calculated delay in seconds
    """
    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    return delay

class RetryHandler:
    """Handles retry logic for commands and RPC calls."""
    
    def __init__(self, error_handler: ErrorHandler):
        """
        Initialize retry handler.
        
        Args:
            error_handler: ErrorHandler instance for logging
        """
        self.error_handler = error_handler
    
    def retry_command(self, command: list, max_attempts: int, delay: float, 
                     component: str) -> Tuple[bool, str]:
        """
        Execute a command with retries.
        
        Args:
            command: Command and arguments as a list
            max_attempts: Maximum number of attempts
            delay: Delay between attempts in seconds
            component: Component name for logging
            
        Returns:
            Tuple of (success, output)
        """
        for attempt in range(1, max_attempts + 1):
            self.error_handler.log_info(component, 
                f"Attempt {attempt}/{max_attempts}: {' '.join(command)}")
            
            try:
                result = subprocess.run(command, capture_output=True, text=True, 
                                      check=True)
                self.error_handler.log_info(component, 
                    f"Command succeeded on attempt {attempt}")
                return True, result.stdout
            except subprocess.CalledProcessError as e:
                if attempt < max_attempts:
                    self.error_handler.log_warning(component,
                        f"Command failed on attempt {attempt}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    self.error_handler.log_error(component,
                        f"Command failed after {max_attempts} attempts")
                    return False, e.stderr if e.stderr else str(e)
        
        return False, "Max attempts reached"
    
    def call_daemon_with_retry(self, daemon_url: str, method: str, params: Dict[str, Any],
                              max_attempts: int, delay: float, component: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Call daemon RPC with retry logic.
        
        Args:
            daemon_url: URL of the daemon RPC endpoint
            method: RPC method name
            params: RPC parameters
            max_attempts: Maximum number of attempts
            delay: Base delay between attempts
            component: Component name for logging
            
        Returns:
            Tuple of (success, response_dict)
        """
        for attempt in range(1, max_attempts + 1):
            current_delay = exponential_backoff(attempt, delay, 60)
            
            self.error_handler.log_info(component,
                f"RPC call attempt {attempt}/{max_attempts}: {method}")
            
            try:
                # Check if daemon is reachable
                ping_response = requests.get(daemon_url, timeout=5)
                if ping_response.status_code not in [200, 405]:
                    raise requests.RequestException(
                        f"Daemon not reachable (HTTP {ping_response.status_code})")
            except requests.RequestException as e:
                self.error_handler.log_warning(component,
                    f"Daemon URL {daemon_url} is not reachable: {e}")
                if attempt < max_attempts:
                    self.error_handler.log_info(component,
                        f"Retrying in {current_delay} seconds...")
                    time.sleep(current_delay)
                    continue
                else:
                    self.error_handler.log_error(component,
                        f"Daemon URL {daemon_url} is not reachable after {max_attempts} attempts")
                    return False, {"error": "Daemon URL not reachable"}
            
            # Make the actual RPC call
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": "0",
                    "method": method,
                    "params": params
                }
                response = requests.post(daemon_url, json=payload, timeout=30)
                response_data = response.json()
                
                if "result" in response_data:
                    self.error_handler.log_info(component,
                        f"RPC call succeeded on attempt {attempt}")
                    return True, response_data
                elif "error" in response_data:
                    error_info = response_data["error"]
                    self.error_handler.log_warning(component,
                        f"RPC call returned error on attempt {attempt}: {error_info}")
                    if attempt < max_attempts:
                        self.error_handler.log_info(component,
                            f"Retrying in {current_delay} seconds...")
                        time.sleep(current_delay)
                        continue
                    else:
                        return False, response_data
                else:
                    raise ValueError("Invalid response format")
                    
            except Exception as e:
                self.error_handler.log_warning(component,
                    f"RPC call failed on attempt {attempt}: {e}")
                if attempt < max_attempts:
                    self.error_handler.log_info(component,
                        f"Retrying in {current_delay} seconds...")
                    time.sleep(current_delay)
                    continue
                else:
                    self.error_handler.log_error(component,
                        f"RPC call failed after {max_attempts} attempts: {e}")
                    return False, {"error": str(e)}
        
        return False, {"error": "Max attempts reached"}
    
    def call_wallet_with_retry(self, wallet_url: str, method: str, params: Dict[str, Any],
                              max_attempts: int, delay: float, component: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Call wallet RPC with retry logic.
        
        Args:
            wallet_url: URL of the wallet RPC endpoint
            method: RPC method name
            params: RPC parameters
            max_attempts: Maximum number of attempts
            delay: Base delay between attempts
            component: Component name for logging
            
        Returns:
            Tuple of (success, response_dict)
        """
        for attempt in range(1, max_attempts + 1):
            current_delay = exponential_backoff(attempt, delay, 60)
            
            self.error_handler.log_info(component,
                f"Wallet RPC call attempt {attempt}/{max_attempts}: {method}")
            
            try:
                # Check if wallet is reachable
                ping_response = requests.get(wallet_url, timeout=5)
                if ping_response.status_code not in [200, 405]:
                    raise requests.RequestException(
                        f"Wallet not reachable (HTTP {ping_response.status_code})")
            except requests.RequestException as e:
                self.error_handler.log_warning(component,
                    f"Wallet URL {wallet_url} is not reachable: {e}")
                if attempt < max_attempts:
                    self.error_handler.log_info(component,
                        f"Retrying in {current_delay} seconds...")
                    time.sleep(current_delay)
                    continue
                else:
                    self.error_handler.log_error(component,
                        f"Wallet URL {wallet_url} is not reachable after {max_attempts} attempts")
                    return False, {"error": "Wallet URL not reachable"}
            
            # Make the actual RPC call
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": "0",
                    "method": method,
                    "params": params
                }
                response = requests.post(wallet_url, json=payload, timeout=30)
                response_data = response.json()
                
                if "result" in response_data:
                    self.error_handler.log_info(component,
                        f"Wallet RPC call succeeded on attempt {attempt}")
                    return True, response_data
                elif "error" in response_data:
                    error_info = response_data["error"]
                    error_code = error_info.get("code", None)
                    error_message = error_info.get("message", "")
                    
                    self.error_handler.log_warning(component,
                        f"Wallet RPC call returned error on attempt {attempt}: "
                        f"code={error_code}, message={error_message}")
                    
                    # Special handling for wallet already exists error
                    if (error_code == -1 and method == "create_wallet" and 
                        "already exists" in error_message):
                        self.error_handler.log_info(component,
                            "Wallet already exists, trying to open it instead...")
                        
                        # Try to open the wallet
                        open_params = {
                            "filename": params.get("filename"),
                            "password": params.get("password", "")
                        }
                        open_payload = {
                            "jsonrpc": "2.0",
                            "id": "0",
                            "method": "open_wallet",
                            "params": open_params
                        }
                        open_response = requests.post(wallet_url, json=open_payload, timeout=30)
                        open_data = open_response.json()
                        
                        if "result" in open_data:
                            self.error_handler.log_info(component,
                                "Successfully opened existing wallet")
                            return True, open_data
                    
                    if attempt < max_attempts:
                        self.error_handler.log_info(component,
                            f"Retrying in {current_delay} seconds...")
                        time.sleep(current_delay)
                        continue
                    else:
                        return False, response_data
                else:
                    raise ValueError("Invalid response format")
                    
            except Exception as e:
                self.error_handler.log_warning(component,
                    f"Wallet RPC call failed on attempt {attempt}: {e}")
                if attempt < max_attempts:
                    self.error_handler.log_info(component,
                        f"Retrying in {current_delay} seconds...")
                    time.sleep(current_delay)
                    continue
                else:
                    self.error_handler.log_error(component,
                        f"Wallet RPC call failed after {max_attempts} attempts: {e}")
                    return False, {"error": str(e)}
        
        return False, {"error": "Max attempts reached"}

# ===== VERIFICATION FUNCTIONS =====

class VerificationHandler:
    """Handles verification of various MoneroSim components."""
    
    def __init__(self, error_handler: ErrorHandler, retry_handler: RetryHandler):
        """
        Initialize verification handler.
        
        Args:
            error_handler: ErrorHandler instance for logging
            retry_handler: RetryHandler instance for RPC calls
        """
        self.error_handler = error_handler
        self.retry_handler = retry_handler
    
    def verify_daemon_ready(self, daemon_url: str, daemon_name: str,
                           max_attempts: int, delay: float, component: str) -> bool:
        """
        Verify daemon readiness.
        
        Args:
            daemon_url: URL of the daemon RPC endpoint
            daemon_name: Name of the daemon for logging
            max_attempts: Maximum number of attempts
            delay: Delay between attempts
            component: Component name for logging
            
        Returns:
            True if daemon is ready, False otherwise
        """
        self.error_handler.log_info(component, f"Verifying {daemon_name} readiness...")
        
        success, response = self.retry_handler.call_daemon_with_retry(
            daemon_url, "get_info", {}, max_attempts, delay, component)
        
        if success:
            result = response.get("result", {})
            daemon_status = result.get("status", "unknown")
            height = result.get("height", 0)
            
            self.error_handler.log_info(component,
                f"{daemon_name} is ready. Status: {daemon_status}, Height: {height}")
            return True
        else:
            self.error_handler.log_critical(component,
                f"Failed to verify {daemon_name} readiness")
            return False
    
    def verify_wallet_created(self, wallet_url: str, wallet_name: str, wallet_password: str,
                             max_attempts: int, delay: float, component: str) -> bool:
        """
        Verify wallet creation.
        
        Args:
            wallet_url: URL of the wallet RPC endpoint
            wallet_name: Name of the wallet
            wallet_password: Password for the wallet
            max_attempts: Maximum number of attempts
            delay: Delay between attempts
            component: Component name for logging
            
        Returns:
            True if wallet is created/opened, False otherwise
        """
        self.error_handler.log_info(component, f"Verifying wallet creation for {wallet_name}...")
        
        # First try to open existing wallet
        open_params = {"filename": wallet_name, "password": wallet_password}
        success, response = self.retry_handler.call_wallet_with_retry(
            wallet_url, "open_wallet", open_params, max_attempts, delay, component)
        
        if success:
            self.error_handler.log_info(component,
                f"Wallet {wallet_name} already exists and was opened successfully")
            return True
        
        # If opening failed, try to create new wallet
        self.error_handler.log_info(component, f"Creating new wallet {wallet_name}...")
        create_params = {
            "filename": wallet_name,
            "password": wallet_password,
            "language": "English"
        }
        success, response = self.retry_handler.call_wallet_with_retry(
            wallet_url, "create_wallet", create_params, max_attempts, delay, component)
        
        if success:
            self.error_handler.log_info(component, f"Wallet {wallet_name} created successfully")
            return True
        else:
            self.error_handler.log_critical(component, f"Failed to create wallet {wallet_name}")
            return False
    
    def verify_wallet_open(self, wallet_url: str, wallet_name: str, wallet_password: str,
                          max_attempts: int, delay: float, component: str) -> bool:
        """
        Verify wallet opening.
        
        Args:
            wallet_url: URL of the wallet RPC endpoint
            wallet_name: Name of the wallet
            wallet_password: Password for the wallet
            max_attempts: Maximum number of attempts
            delay: Delay between attempts
            component: Component name for logging
            
        Returns:
            True if wallet is opened, False otherwise
        """
        self.error_handler.log_info(component, f"Verifying wallet opening for {wallet_name}...")
        
        open_params = {"filename": wallet_name, "password": wallet_password}
        success, response = self.retry_handler.call_wallet_with_retry(
            wallet_url, "open_wallet", open_params, max_attempts, delay, component)
        
        if success:
            self.error_handler.log_info(component, f"Wallet {wallet_name} opened successfully")
            
            # Verify we can get the address
            success, addr_response = self.retry_handler.call_wallet_with_retry(
                wallet_url, "get_address", {"account_index": 0}, max_attempts, delay, component)
            
            if success:
                address = addr_response.get("result", {}).get("address", "")
                self.error_handler.log_info(component, f"Wallet address verified: {address}")
                return True
            else:
                self.error_handler.log_warning(component,
                    "Wallet opened but address verification failed")
                return True  # Still consider it a success
        else:
            self.error_handler.log_critical(component, f"Failed to open wallet {wallet_name}")
            return False
    
    def verify_block_generation(self, daemon_url: str, wallet_address: str, num_blocks: int,
                               max_attempts: int, delay: float, component: str) -> bool:
        """
        Verify block generation.
        
        Args:
            daemon_url: URL of the daemon RPC endpoint
            wallet_address: Address to receive mining rewards
            num_blocks: Number of blocks to generate
            max_attempts: Maximum number of attempts
            delay: Delay between attempts
            component: Component name for logging
            
        Returns:
            True if blocks were generated, False otherwise
        """
        self.error_handler.log_info(component, "Verifying block generation...")
        
        # Get initial height
        success, initial_response = self.retry_handler.call_daemon_with_retry(
            daemon_url, "get_info", {}, max_attempts, delay, component)
        
        if not success:
            self.error_handler.log_critical(component, "Failed to get initial block height")
            return False
        
        initial_height = initial_response.get("result", {}).get("height", 0)
        self.error_handler.log_info(component, f"Initial block height: {initial_height}")
        
        # Generate blocks
        self.error_handler.log_info(component, f"Generating {num_blocks} blocks...")
        gen_params = {
            "amount_of_blocks": num_blocks,
            "reserve_size": 1,
            "wallet_address": wallet_address
        }
        success, gen_response = self.retry_handler.call_daemon_with_retry(
            daemon_url, "generateblocks", gen_params, max_attempts, delay, component)
        
        if not success:
            self.error_handler.log_critical(component, "Failed to generate blocks")
            return False
        
        # Count generated blocks
        blocks = gen_response.get("result", {}).get("blocks", [])
        blocks_generated = len(blocks)
        self.error_handler.log_info(component, f"Blocks generated: {blocks_generated}")
        
        # Verify new height
        success, final_response = self.retry_handler.call_daemon_with_retry(
            daemon_url, "get_info", {}, max_attempts, delay, component)
        
        if not success:
            self.error_handler.log_critical(component, "Failed to get final block height")
            return False
        
        final_height = final_response.get("result", {}).get("height", 0)
        self.error_handler.log_info(component, f"Final block height: {final_height}")
        
        # Check if height increased by expected amount
        expected_height = initial_height + num_blocks
        if final_height >= expected_height:
            self.error_handler.log_info(component,
                f"Block generation verified: Height increased from {initial_height} to {final_height}")
            return True
        else:
            self.error_handler.log_error(component,
                f"Block generation verification failed: Expected height {expected_height}, got {final_height}")
            return False
    
    def verify_transaction(self, from_wallet_url: str, to_address: str, amount: int,
                          max_attempts: int, delay: float, component: str) -> Optional[str]:
        """
        Verify transaction processing.
        
        Args:
            from_wallet_url: URL of the sending wallet RPC endpoint
            to_address: Recipient address
            amount: Amount in atomic units
            max_attempts: Maximum number of attempts
            delay: Delay between attempts
            component: Component name for logging
            
        Returns:
            Transaction hash if successful, None otherwise
        """
        self.error_handler.log_info(component,
            f"Verifying transaction of {amount} atomic units to {to_address}...")
        
        # Get initial balance
        success, balance_response = self.retry_handler.call_wallet_with_retry(
            from_wallet_url, "get_balance", {"account_index": 0}, max_attempts, delay, component)
        
        if not success:
            self.error_handler.log_critical(component, "Failed to get initial balance")
            return None
        
        unlocked_balance = balance_response.get("result", {}).get("unlocked_balance", 0)
        self.error_handler.log_info(component, f"Initial unlocked balance: {unlocked_balance} atomic units")
        
        # Check if we have enough funds
        if unlocked_balance < amount:
            self.error_handler.log_error(component,
                f"Insufficient funds: Have {unlocked_balance}, need {amount}")
            return None
        
        # Send transaction
        self.error_handler.log_info(component, "Sending transaction...")
        transfer_params = {
            "destinations": [{"amount": amount, "address": to_address}],
            "account_index": 0,
            "priority": 1,
            "get_tx_key": True
        }
        success, transfer_response = self.retry_handler.call_wallet_with_retry(
            from_wallet_url, "transfer", transfer_params, max_attempts, delay, component)
        
        if not success:
            self.error_handler.log_critical(component, "Failed to send transaction")
            return None
        
        # Extract transaction hash
        tx_hash = transfer_response.get("result", {}).get("tx_hash", "")
        if not tx_hash:
            self.error_handler.log_error(component, "Failed to extract transaction hash")
            return None
        
        self.error_handler.log_info(component, f"Transaction sent successfully. Hash: {tx_hash}")
        return tx_hash
    
    def verify_network_sync(self, node1_url: str, node2_url: str, max_height_diff: int,
                           max_attempts: int, delay: float, component: str) -> bool:
        """
        Verify network synchronization between two nodes.
        
        Args:
            node1_url: URL of the first node
            node2_url: URL of the second node
            max_height_diff: Maximum allowed height difference
            max_attempts: Maximum number of attempts
            delay: Delay between attempts
            component: Component name for logging
            
        Returns:
            True if nodes are synchronized, False otherwise
        """
        self.error_handler.log_info(component, "Verifying network synchronization...")
        
        for attempt in range(1, max_attempts + 1):
            self.error_handler.log_info(component, f"Sync check attempt {attempt}/{max_attempts}")
            
            # Get info from both nodes
            success1, node1_response = self.retry_handler.call_daemon_with_retry(
                node1_url, "get_info", {}, 3, 2, component)
            success2, node2_response = self.retry_handler.call_daemon_with_retry(
                node2_url, "get_info", {}, 3, 2, component)
            
            if not success1 or not success2:
                self.error_handler.log_warning(component,
                    "Failed to get info from one or both nodes")
                time.sleep(delay)
                continue
            
            # Extract heights and hashes
            node1_info = node1_response.get("result", {})
            node2_info = node2_response.get("result", {})
            
            node1_height = node1_info.get("height", 0)
            node2_height = node2_info.get("height", 0)
            node1_hash = node1_info.get("top_block_hash", "")
            node2_hash = node2_info.get("top_block_hash", "")
            
            self.error_handler.log_info(component,
                f"Node1 height: {node1_height}, hash: {node1_hash}")
            self.error_handler.log_info(component,
                f"Node2 height: {node2_height}, hash: {node2_hash}")
            
            # Calculate height difference
            height_diff = abs(node1_height - node2_height)
            self.error_handler.log_info(component, f"Height difference: {height_diff} blocks")
            
            # Check if synchronized
            if height_diff <= max_height_diff:
                if node1_hash == node2_hash or node1_height == node2_height:
                    self.error_handler.log_info(component,
                        "Synchronization verified: Nodes are in sync")
                    return True
                else:
                    self.error_handler.log_warning(component,
                        "Heights are close but top block hashes differ")
            else:
                self.error_handler.log_warning(component,
                    f"Nodes are not yet synchronized (diff: {height_diff})")
            
            time.sleep(delay)
        
        self.error_handler.log_error(component,
            f"Synchronization verification failed after {max_attempts} attempts")
        return False
    
    def verify_p2p_connectivity(self, node1_url: str, node1_name: str,
                               node2_url: str, node2_name: str,
                               max_attempts: int, retry_delay: float,
                               component: str) -> bool:
        """
        Verify P2P connectivity between two nodes.
        
        Args:
            node1_url: URL of the first node
            node1_name: Name of the first node
            node2_url: URL of the second node
            node2_name: Name of the second node
            max_attempts: Maximum number of attempts
            retry_delay: Delay between attempts
            component: Component name for logging
            
        Returns:
            True if nodes are connected, False otherwise
        """
        self.error_handler.log_info(component,
            f"Verifying P2P connectivity between {node1_name} and {node2_name}...")
        
        # Extract IPs from URLs
        import re
        ip_pattern = r'(\d+\.\d+\.\d+\.\d+)'
        node1_ip_match = re.search(ip_pattern, node1_url)
        node2_ip_match = re.search(ip_pattern, node2_url)
        
        if not node1_ip_match or not node2_ip_match:
            self.error_handler.log_error(component, "Failed to extract IP addresses from URLs")
            return False
        
        node1_ip = node1_ip_match.group(1)
        node2_ip = node2_ip_match.group(1)
        
        for attempt in range(1, max_attempts + 1):
            self.error_handler.log_info(component,
                f"P2P connectivity check attempt {attempt}/{max_attempts}")
            
            # Check connections on both nodes
            success1, conn1_response = self.retry_handler.call_daemon_with_retry(
                node1_url, "get_connections", {}, 3, 2, component)
            success2, conn2_response = self.retry_handler.call_daemon_with_retry(
                node2_url, "get_connections", {}, 3, 2, component)
            
            if not success1 or not success2:
                self.error_handler.log_warning(component,
                    "Failed to get connection information from one or both nodes")
                time.sleep(retry_delay)
                continue
            
            # Extract connections
            connections1 = conn1_response.get("result", {}).get("connections", [])
            connections2 = conn2_response.get("result", {}).get("connections", [])
            
            conn_count1 = len(connections1)
            conn_count2 = len(connections2)
            
            self.error_handler.log_info(component, f"{node1_name} has {conn_count1} P2P connections")
            self.error_handler.log_info(component, f"{node2_name} has {conn_count2} P2P connections")
            
            # Check if nodes have any connections
            if conn_count1 == 0 and conn_count2 == 0:
                self.error_handler.log_warning(component,
                    f"Both nodes have no P2P connections. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            
            # Check if nodes are connected to each other
            node1_connected_to_node2 = False
            node2_connected_to_node1 = False
            
            # Check node1's connections for node2
            for conn in connections1:
                peer_address = conn.get("address", "")
                if node2_ip in peer_address:
                    node1_connected_to_node2 = True
                    self.error_handler.log_info(component,
                        f"✅ {node1_name} is connected to {node2_name}")
                    break
            
            if not node1_connected_to_node2:
                self.error_handler.log_warning(component,
                    f"❌ {node1_name} is NOT connected to {node2_name}")
            
            # Check node2's connections for node1
            for conn in connections2:
                peer_address = conn.get("address", "")
                if node1_ip in peer_address:
                    node2_connected_to_node1 = True
                    self.error_handler.log_info(component,
                        f"✅ {node2_name} is connected to {node1_name}")
                    break
            
            if not node2_connected_to_node1:
                self.error_handler.log_warning(component,
                    f"❌ {node2_name} is NOT connected to {node1_name}")
            
            # Count incoming/outgoing connections
            node1_incoming = sum(1 for c in connections1 if c.get("incoming", False))
            node1_outgoing = conn_count1 - node1_incoming
            node2_incoming = sum(1 for c in connections2 if c.get("incoming", False))
            node2_outgoing = conn_count2 - node2_incoming
            
            self.error_handler.log_info(component,
                f"{node1_name} has {node1_incoming} incoming and {node1_outgoing} outgoing connections")
            self.error_handler.log_info(component,
                f"{node2_name} has {node2_incoming} incoming and {node2_outgoing} outgoing connections")
            
            # Check if both nodes are connected to each other
            if node1_connected_to_node2 and node2_connected_to_node1:
                self.error_handler.log_info(component,
                    f"✅ P2P connectivity verified: Bidirectional connection established "
                    f"between {node1_name} and {node2_name}")
                
                # Log connection details
                self.error_handler.log_info(component, "Connection details:")
                
                # Log node1's connection to node2
                for conn in connections1:
                    if node2_ip in conn.get("address", ""):
                        state = conn.get("state", "unknown")
                        live_time = conn.get("live_time", 0)
                        incoming = conn.get("incoming", False)
                        self.error_handler.log_info(component,
                            f"  {node1_name} -> {node2_name}: State={state}, "
                            f"Live time={live_time}s, Incoming={incoming}")
                
                # Log node2's connection to node1
                for conn in connections2:
                    if node1_ip in conn.get("address", ""):
                        state = conn.get("state", "unknown")
                        live_time = conn.get("live_time", 0)
                        incoming = conn.get("incoming", False)
                        self.error_handler.log_info(component,
                            f"  {node2_name} -> {node1_name}: State={state}, "
                            f"Live time={live_time}s, Incoming={incoming}")
                
                return True
            else:
                # On last attempt, provide detailed diagnostics
                if attempt == max_attempts:
                    self.error_handler.log_error(component,
                        f"❌ P2P connectivity verification failed after {max_attempts} attempts")
                    
                    # Check peer lists for diagnostic information
                    self.error_handler.log_info(component,
                        "Checking peer lists for diagnostic information...")
                    
                    success1, peer1_response = self.retry_handler.call_daemon_with_retry(
                        node1_url, "get_peer_list", {}, 3, 2, component)
                    success2, peer2_response = self.retry_handler.call_daemon_with_retry(
                        node2_url, "get_peer_list", {}, 3, 2, component)
                    
                    if success1 and success2:
                        # Check if nodes know about each other
                        peer_list1 = str(peer1_response)
                        peer_list2 = str(peer2_response)
                        
                        if node2_ip in peer_list1:
                            self.error_handler.log_info(component,
                                f"{node1_name} knows about {node2_name} in its peer list")
                        else:
                            self.error_handler.log_error(component,
                                f"{node1_name} does NOT have {node2_name} in its peer list")
                        
                        if node1_ip in peer_list2:
                            self.error_handler.log_info(component,
                                f"{node2_name} knows about {node1_name} in its peer list")
                        else:
                            self.error_handler.log_error(component,
                                f"{node2_name} does NOT have {node1_name} in its peer list")
                    
                    self.error_handler.log_error(component,
                        "Possible reasons for P2P connectivity failure:")
                    self.error_handler.log_error(component,
                        "1. Firewall or network configuration issues")
                    self.error_handler.log_error(component,
                        "2. Incorrect exclusive/priority node settings")
                    self.error_handler.log_error(component,
                        "3. P2P port conflicts")
                    self.error_handler.log_error(component,
                        "4. Node startup timing issues")
                    
                    return False
                
                self.error_handler.log_warning(component,
                    f"Nodes are not fully connected. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
        
        self.error_handler.log_error(component,
            f"P2P connectivity verification failed after {max_attempts} attempts")
        return False
    
    def verify_wallet_directory(self, wallet_dir: str, component: str) -> bool:
        """
        Verify wallet directory exists and is writable.
        
        Args:
            wallet_dir: Path to the wallet directory
            component: Component name for logging
            
        Returns:
            True if directory is ready, False otherwise
        """
        self.error_handler.log_info(component, f"Verifying wallet directory: {wallet_dir}")
        
        wallet_path = Path(wallet_dir)
        
        if not wallet_path.exists():
            self.error_handler.log_warning(component,
                f"Wallet directory does not exist, creating it: {wallet_dir}")
            try:
                wallet_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.error_handler.log_critical(component,
                    f"Failed to create wallet directory: {wallet_dir} - {e}")
                return False
        
        if not wallet_path.is_dir():
            self.error_handler.log_critical(component,
                f"Wallet path exists but is not a directory: {wallet_dir}")
            return False
        
        # Check if writable
        test_file = wallet_path / ".test_write"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            self.error_handler.log_critical(component,
                f"Wallet directory is not writable: {wallet_dir} - {e}")
            return False
        
        # Try to set permissions
        try:
            wallet_path.chmod(0o700)
        except Exception as e:
            self.error_handler.log_warning(component,
                f"Failed to set permissions on wallet directory, continuing anyway: {e}")
        
        self.error_handler.log_info(component, f"Wallet directory verified: {wallet_dir}")
        return True

# ===== UTILITY FUNCTIONS =====

def handle_exit(exit_code: int, component: str, message: str,
                error_handler: Optional[ErrorHandler] = None) -> None:
    """
    Handle script exit with logging.
    
    Args:
        exit_code: Exit code to use
        component: Component name for logging
        message: Exit message
        error_handler: Optional ErrorHandler instance
    """
    if error_handler is None:
        error_handler = ErrorHandler()
    
    if exit_code == 0:
        error_handler.log_info(component, f"Script completed successfully: {message}")
    else:
        error_handler.log_critical(component, f"Script failed with exit code {exit_code}: {message}")
    
    sys.exit(exit_code)

# ===== CONVENIENCE FUNCTIONS =====
# These functions provide a simple interface similar to the bash script

_default_error_handler = None
_default_retry_handler = None
_default_verification_handler = None

def get_default_handlers() -> Tuple[ErrorHandler, RetryHandler, VerificationHandler]:
    """Get or create default handler instances."""
    global _default_error_handler, _default_retry_handler, _default_verification_handler
    
    if _default_error_handler is None:
        _default_error_handler = ErrorHandler()
    if _default_retry_handler is None:
        _default_retry_handler = RetryHandler(_default_error_handler)
    if _default_verification_handler is None:
        _default_verification_handler = VerificationHandler(_default_error_handler, _default_retry_handler)
    
    return _default_error_handler, _default_retry_handler, _default_verification_handler

# Convenience logging functions
def log_info(component: str, message: str) -> None:
    """Log an info message using the default handler."""
    error_handler, _, _ = get_default_handlers()
    error_handler.log_info(component, message)

def log_warning(component: str, message: str) -> None:
    """Log a warning message using the default handler."""
    error_handler, _, _ = get_default_handlers()
    error_handler.log_warning(component, message)

def log_error(component: str, message: str) -> None:
    """Log an error message using the default handler."""
    error_handler, _, _ = get_default_handlers()
    error_handler.log_error(component, message)

def log_critical(component: str, message: str) -> None:
    """Log a critical message using the default handler."""
    error_handler, _, _ = get_default_handlers()
    error_handler.log_critical(component, message)

# Add log_success convenience function
def log_success(component: str, message: str) -> None:
    """Log a success message (displayed as info with green color) using the default handler."""
    error_handler, _, _ = get_default_handlers()
    error_handler.log_info(component, f"✓ {message}")

# Convenience retry functions
def retry_command(command: list, max_attempts: int, delay: float,
                 component: str) -> Tuple[bool, str]:
    """Execute a command with retries using the default handler."""
    _, retry_handler, _ = get_default_handlers()
    return retry_handler.retry_command(command, max_attempts, delay, component)

def call_daemon_with_retry(daemon_url: str, method: str, params: Dict[str, Any],
                          max_attempts: int, delay: float, component: str) -> Tuple[bool, Dict[str, Any]]:
    """Call daemon RPC with retry using the default handler."""
    _, retry_handler, _ = get_default_handlers()
    return retry_handler.call_daemon_with_retry(daemon_url, method, params,
                                               max_attempts, delay, component)

def call_wallet_with_retry(wallet_url: str, method: str, params: Dict[str, Any],
                          max_attempts: int, delay: float, component: str) -> Tuple[bool, Dict[str, Any]]:
    """Call wallet RPC with retry using the default handler."""
    _, retry_handler, _ = get_default_handlers()
    return retry_handler.call_wallet_with_retry(wallet_url, method, params,
                                               max_attempts, delay, component)

# Convenience verification functions
def verify_daemon_ready(daemon_url: str, daemon_name: str,
                       max_attempts: int, delay: float, component: str) -> bool:
    """Verify daemon readiness using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_daemon_ready(daemon_url, daemon_name,
                                                   max_attempts, delay, component)

def verify_wallet_created(wallet_url: str, wallet_name: str, wallet_password: str,
                         max_attempts: int, delay: float, component: str) -> bool:
    """Verify wallet creation using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_wallet_created(wallet_url, wallet_name, wallet_password,
                                                     max_attempts, delay, component)

def verify_wallet_open(wallet_url: str, wallet_name: str, wallet_password: str,
                      max_attempts: int, delay: float, component: str) -> bool:
    """Verify wallet opening using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_wallet_open(wallet_url, wallet_name, wallet_password,
                                                  max_attempts, delay, component)

def verify_block_generation(daemon_url: str, wallet_address: str, num_blocks: int,
                           max_attempts: int, delay: float, component: str) -> bool:
    """Verify block generation using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_block_generation(daemon_url, wallet_address, num_blocks,
                                                       max_attempts, delay, component)

def verify_transaction(from_wallet_url: str, to_address: str, amount: int,
                      max_attempts: int, delay: float, component: str) -> Optional[str]:
    """Verify transaction processing using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_transaction(from_wallet_url, to_address, amount,
                                                  max_attempts, delay, component)

def verify_network_sync(node1_url: str, node2_url: str, max_height_diff: int,
                       max_attempts: int, delay: float, component: str) -> bool:
    """Verify network synchronization using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_network_sync(node1_url, node2_url, max_height_diff,
                                                   max_attempts, delay, component)

def verify_p2p_connectivity(node1_url: str, node1_name: str,
                           node2_url: str, node2_name: str,
                           max_attempts: int, retry_delay: float,
                           component: str) -> bool:
    """Verify P2P connectivity using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_p2p_connectivity(node1_url, node1_name,
                                                       node2_url, node2_name,
                                                       max_attempts, retry_delay, component)

def verify_wallet_directory(wallet_dir: str, component: str) -> bool:
    """Verify wallet directory using the default handler."""
    _, _, verification_handler = get_default_handlers()
    return verification_handler.verify_wallet_directory(wallet_dir, component)

# Main entry point for testing
if __name__ == "__main__":
    # Example usage
    log_info("TEST", "Testing error_handling.py module")
    log_warning("TEST", "This is a warning message")
    log_error("TEST", "This is an error message")
    log_critical("TEST", "This is a critical message")
    
    # Test command retry
    success, output = retry_command(["echo", "Hello, World!"], 3, 1, "TEST")
    if success:
        log_info("TEST", f"Command output: {output.strip()}")
    
    log_info("TEST", "Error handling module test completed")