"""
Monero RPC client wrappers for daemon and wallet communication.
Provides a clean interface for agents to interact with Monero processes.
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List
import requests


class RPCError(Exception):
    """Custom exception for RPC-related errors"""
    pass


class MethodNotAvailableError(RPCError):
    """Exception raised when an RPC method is not available"""
    pass


class WalletError(RPCError):
    """Exception raised for wallet-specific errors"""
    pass


class BaseRPC:
    """Base class for RPC communication"""
    
    def __init__(self, host: str, port: int, timeout: int = 60):
        self.url = f"http://{host}:{port}/json_rpc"
        self.timeout = timeout
        self.session = self._create_session()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.available_methods = {}
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic"""
        session = requests.Session()
        return session
        
    def reset_session(self):
        """Reset the HTTP session to recover from stale/broken connections.

        This is needed after daemon restarts (e.g., during upgrades) where
        the persistent HTTP connection becomes stale and all requests timeout.
        """
        try:
            self.session.close()
        except Exception:
            pass
        self.session = self._create_session()
        self.logger.info("HTTP session reset - new connection will be established")

    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an RPC request"""
        payload = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": method
        }
        if params:
            payload["params"] = params
            
        try:
            response = self.session.post(
                self.url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            if "error" in result:
                raise RPCError(f"RPC error: {result['error']}")
                
            return result.get("result", {})
            
        except requests.exceptions.RequestException as e:
            raise RPCError(f"Request failed: {str(e)}")
            
    def is_ready(self) -> bool:
        """Check if the RPC service is ready"""
        try:
            # For wallets, we just need to check if we can make any RPC call
            # We'll use get_version which doesn't require a wallet to be loaded
            self._make_request("get_version")
            return True
        except Exception as e:
            self.logger.debug(f"RPC service not ready: {e}")
            return False
    
    def detect_available_methods(self, methods_to_check: List[str]) -> Dict[str, bool]:
        """
        Detect which RPC methods are available in this Monero instance.
        
        Args:
            methods_to_check: List of method names to check
            
        Returns:
            Dictionary mapping method names to availability (True/False)
        """
        result = {}
        for method in methods_to_check:
            try:
                # Make a minimal request to check if the method exists
                # We use empty params or minimal required params
                if method == "start_mining":
                    # start_mining requires wallet_address
                    self._make_request(method, {"wallet_address": "dummy", "threads_count": 1})
                elif method == "generateblocks":
                    # generateblocks requires wallet_address and amount_of_blocks
                    self._make_request(method, {"wallet_address": "dummy", "amount_of_blocks": 1})
                else:
                    # For other methods, try with empty params
                    self._make_request(method, {})
                result[method] = True
            except RPCError as e:
                # Check if the error indicates method not found vs other errors
                error_str = str(e).lower()
                if "method not found" in error_str or "unknown method" in error_str:
                    result[method] = False
                else:
                    # If we get other errors, the method exists but had parameter issues
                    result[method] = True
            except Exception:
                # For any other exception, assume method is not available
                result[method] = False
        
        self.available_methods.update(result)
        self.logger.info(f"Detected available methods: {result}")
        return result
            
    def wait_until_ready(self, max_wait: int = 120, check_interval: int = 1):
        """Wait until the RPC service is ready with exponential backoff"""
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < max_wait:
            if self.is_ready():
                self.logger.info(f"RPC service ready at {self.url}")
                return
            # Exponential backoff with jitter
            delay = min(check_interval * (2 ** attempt), 10)  # Cap at 10 seconds
            self.logger.debug(f"RPC service not ready, retrying in {delay:.1f}s (attempt {attempt + 1})")
            time.sleep(delay)
            attempt += 1
        raise RPCError(f"RPC service not ready after {max_wait} seconds")


class MoneroRPC(BaseRPC):
    """Monero daemon RPC client"""
    
    def __init__(self, host: str, port: int, timeout: int = 60):
        super().__init__(host, port, timeout)
        # Initialize with common methods to check
        self.mining_methods = ["start_mining", "stop_mining", "mining_status", "generateblocks"]
        
    def get_info(self) -> Dict[str, Any]:
        """Get general daemon information"""
        return self._make_request("get_info")
        
    def get_height(self) -> int:
        """Get current blockchain height"""
        info = self.get_info()
        return info.get("height", 0)
        
    def get_connections(self) -> int:
        """Get number of peer connections"""
        info = self.get_info()
        return info.get("incoming_connections_count", 0) + info.get("outgoing_connections_count", 0)
        
    def get_peer_list(self) -> Dict[str, Any]:
        """Get list of peers"""
        return self._make_request("get_peer_list")
        
    def start_mining(self, wallet_address: str, threads: int = 1) -> Dict[str, Any]:
        """Start mining"""
        params = {
            "wallet_address": wallet_address,
            "threads_count": threads,
            "do_background_mining": False,
            "ignore_battery": True
        }
        try:
            return self._make_request("start_mining", params)
        except RPCError as e:
            error_str = str(e).lower()
            if "method not found" in error_str or "unknown method" in error_str:
                self.logger.warning("start_mining method not available")
                self.available_methods["start_mining"] = False
                raise MethodNotAvailableError("start_mining method not available")
            raise
        
    def stop_mining(self) -> Dict[str, Any]:
        """Stop mining"""
        try:
            return self._make_request("stop_mining")
        except RPCError as e:
            error_str = str(e).lower()
            if "method not found" in error_str or "unknown method" in error_str:
                self.logger.warning("stop_mining method not available")
                self.available_methods["stop_mining"] = False
                raise MethodNotAvailableError("stop_mining method not available")
            raise
        
    def mining_status(self) -> Dict[str, Any]:
        """Get mining status"""
        try:
            return self._make_request("mining_status")
        except RPCError as e:
            error_str = str(e).lower()
            if "method not found" in error_str or "unknown method" in error_str:
                self.logger.warning("mining_status method not available")
                self.available_methods["mining_status"] = False
                raise MethodNotAvailableError("mining_status method not available")
            raise
        
    def get_block_count(self) -> int:
        """Get block count"""
        result = self._make_request("get_block_count")
        return result.get("count", 0)
        
    def sync_info(self) -> Dict[str, Any]:
        """Get synchronization info"""
        return self._make_request("sync_info")
        
    def get_alternate_chains(self) -> List[Dict[str, Any]]:
        """Get alternate chains"""
        result = self._make_request("get_alternate_chains")
        return result.get("chains", [])

    def get_block(self, height: Optional[int] = None, block_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Get block information by height or hash.

        Args:
            height: Block height (optional if hash provided)
            block_hash: Block hash (optional if height provided)

        Returns:
            Dictionary with block info including:
            - block_header: Header information
            - tx_hashes: List of transaction hashes in the block
            - miner_tx_hash: Hash of the miner (coinbase) transaction
        """
        params = {}
        if height is not None:
            params["height"] = height
        if block_hash is not None:
            params["hash"] = block_hash

        if not params:
            raise RPCError("Either height or hash must be provided")

        return self._make_request("get_block", params)

    def get_block_header_by_height(self, height: int) -> Dict[str, Any]:
        """
        Get block header by height.

        Args:
            height: Block height

        Returns:
            Dictionary with block header information
        """
        params = {"height": height}
        result = self._make_request("get_block_header_by_height", params)
        return result.get("block_header", {})

    def get_transaction_pool(self) -> Dict[str, Any]:
        """
        Get information about the transaction pool (mempool).

        Returns:
            Dictionary with transactions in the pool
        """
        # This endpoint uses a different path, not json_rpc
        try:
            url = self.url.replace("/json_rpc", "/get_transaction_pool")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RPCError(f"Failed to get transaction pool: {e}")
        
    def generate_block(self, wallet_address: str, amount_of_blocks: int = 1) -> Dict[str, Any]:
        """
        Generate a new block on the network. This is a restricted RPC call.
        Requires monerod to be run with --regtest and --confirm-external-bind,
        or with RPC authentication.
        """
        params = {
            "amount_of_blocks": amount_of_blocks,
            "wallet_address": wallet_address,
            "pre_pow_blob": "sim"  # Special value for simulation to prevent hanging
        }
        try:
            return self._make_request("generateblocks", params)
        except RPCError as e:
            error_str = str(e).lower()
            if "method not found" in error_str or "unknown method" in error_str:
                self.logger.warning("generateblocks method not available")
                self.available_methods["generateblocks"] = False
                raise MethodNotAvailableError("generateblocks method not available")
            raise
    
    def ensure_mining(self, wallet_address: str, threads: int = 1) -> Dict[str, Any]:
        """
        Ensure mining is active using available methods.
        This method tries different mining approaches based on what's available.
        
        Args:
            wallet_address: The wallet address to mine to
            threads: Number of mining threads
            
        Returns:
            Dictionary with mining status
            
        Raises:
            MethodNotAvailableError: If no mining methods are available
        """
        # Check if we've already detected available methods
        if not self.available_methods:
            self.detect_available_methods(self.mining_methods)
        
        # Try start_mining first if available
        if self.available_methods.get("start_mining", True):
            try:
                self.logger.info(f"Attempting to start mining using start_mining method")
                result = self.start_mining(wallet_address, threads)
                self.logger.info(f"Mining started successfully with start_mining")
                return {"status": "OK", "method": "start_mining", "result": result}
            except MethodNotAvailableError:
                self.logger.warning("start_mining method not available, trying alternatives")
            except RPCError as e:
                self.logger.warning(f"start_mining failed: {e}, trying alternatives")
        
        # Try generateblocks if start_mining is not available or failed
        if self.available_methods.get("generateblocks", True):
            try:
                self.logger.info(f"Attempting to generate blocks using generateblocks method")
                result = self.generate_block(wallet_address, 1)
                self.logger.info(f"Block generated successfully with generateblocks")
                return {"status": "OK", "method": "generateblocks", "result": result}
            except MethodNotAvailableError:
                self.logger.warning("generateblocks method not available")
            except RPCError as e:
                self.logger.warning(f"generateblocks failed: {e}")
        
        # If we get here, no mining methods are available
        error_msg = "No mining methods available (tried: start_mining, generateblocks)"
        self.logger.error(error_msg)
        raise MethodNotAvailableError(error_msg)


class WalletRPC(BaseRPC):
    """Monero wallet RPC client"""
    
    def __init__(self, host: str, port: int, timeout: int = 60):
        super().__init__(host, port, timeout)
        # Wallet RPC uses a different endpoint
        self.url = f"http://{host}:{port}/json_rpc"
        self.current_wallet = None
        
    def create_wallet(self, filename: str, password: str = "", language: str = "English") -> Dict[str, Any]:
        """Create a new wallet"""
        params = {
            "filename": filename,
            "password": password,
            "language": language
        }
        try:
            result = self._make_request("create_wallet", params)
            self.current_wallet = filename
            return result
        except RPCError as e:
            error_str = str(e).lower()
            if "already exists" in error_str:
                self.logger.info(f"Wallet '{filename}' already exists, trying to open it")
                return self.open_wallet(filename, password)
            raise WalletError(f"Failed to create wallet '{filename}': {e}")
        
    def open_wallet(self, filename: str, password: str = "") -> Dict[str, Any]:
        """Open an existing wallet"""
        params = {
            "filename": filename,
            "password": password
        }
        try:
            result = self._make_request("open_wallet", params)
            self.current_wallet = filename
            return result
        except RPCError as e:
            error_str = str(e).lower()
            if "no such file or directory" in error_str or "wallet file not found" in error_str:
                self.logger.info(f"Wallet '{filename}' not found, trying to create it")
                return self.create_wallet(filename, password)
            raise WalletError(f"Failed to open wallet '{filename}': {e}")
        
    def close_wallet(self) -> Dict[str, Any]:
        """Close the current wallet"""
        return self._make_request("close_wallet")
        
    def get_address(self, account_index: int = 0, address_index: int = 0) -> str:
        """Get the primary address of the wallet, with retries for 'No wallet file' error."""
        max_retries = 10
        retry_delay = 5  # seconds
        for i in range(max_retries):
            try:
                params = {
                    "account_index": account_index,
                    "address_index": [address_index]
                }
                response = self._make_request("get_address", params)
                if "addresses" in response and response["addresses"]:
                    return response["addresses"][0]["address"]
                else:
                    self.logger.warning(f"get_address response did not contain an address: {response}")
            except RPCError as e:
                error_str = str(e)
                if "No wallet file" in error_str or "wallet not loaded" in error_str.lower():
                    if i < max_retries - 1:
                        self.logger.warning(f"Wallet file not yet available, retrying in {retry_delay}s... ({i+1}/{max_retries})")
                        time.sleep(retry_delay)
                        
                        # Try to open the wallet if it's not loaded
                        if self.current_wallet:
                            try:
                                self.logger.info(f"Attempting to reopen wallet '{self.current_wallet}'")
                                self.open_wallet(self.current_wallet)
                            except Exception as open_err:
                                self.logger.warning(f"Failed to reopen wallet: {open_err}")
                        
                        continue
                    else:
                        self.logger.error(f"Wallet file not available after {max_retries} retries. Aborting.")
                        raise WalletError(f"Wallet file not available after {max_retries} retries: {e}")
                else:
                    raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred in get_address: {e}")
                raise

        raise WalletError("Failed to get wallet address after multiple retries.")
    
    def ensure_wallet_exists(self, filename: str, password: str = "") -> bool:
        """
        Ensure a wallet exists and is open, creating it if necessary.
        This method tries to open the wallet first, and only creates it if it doesn't exist.
        
        Args:
            filename: Wallet filename
            password: Wallet password
            
        Returns:
            True if wallet is successfully opened or created
            
        Raises:
            WalletError: If wallet cannot be opened or created
        """
        try:
            self.logger.info(f"Attempting to open wallet '{filename}'")
            self.open_wallet(filename, password)
            self.logger.info(f"Successfully opened wallet '{filename}'")
            return True
        except WalletError as e:
            if "not found" in str(e).lower():
                try:
                    self.logger.info(f"Wallet '{filename}' not found, creating it")
                    self.create_wallet(filename, password)
                    self.logger.info(f"Successfully created wallet '{filename}'")
                    return True
                except WalletError as create_err:
                    self.logger.error(f"Failed to create wallet '{filename}': {create_err}")
                    raise
            else:
                self.logger.error(f"Failed to open wallet '{filename}': {e}")
                raise
        
    def get_balance(self, account_index: int = 0) -> Dict[str, Any]:
        """Get wallet balance"""
        params = {"account_index": account_index}
        return self._make_request("get_balance", params)
        
    def refresh(self, start_height: Optional[int] = None) -> Dict[str, Any]:
        """Refresh wallet from blockchain"""
        params = {}
        if start_height is not None:
            params["start_height"] = start_height
        return self._make_request("refresh", params)
        
    def get_height(self) -> int:
        """Get wallet's blockchain height"""
        result = self._make_request("get_height")
        return result.get("height", 0)
        
    def transfer(self, destinations: List[Dict[str, Any]], priority: int = 0,
                 get_tx_key: bool = True, do_not_relay: bool = False) -> Dict[str, Any]:
        """Send a transaction"""
        params = {
            "destinations": destinations,
            "priority": priority,
            "get_tx_key": get_tx_key,
            "do_not_relay": do_not_relay
        }
        return self._make_request("transfer", params)

    def transfer_split(self, destinations: List[Dict[str, Any]], priority: int = 0,
                       get_tx_key: bool = True, do_not_relay: bool = False,
                       new_algorithm: bool = True) -> Dict[str, Any]:
        """
        Send a transaction, automatically splitting if too large.

        Unlike transfer(), this method will split the transaction into multiple
        smaller transactions if necessary to fit within Monero's size limits.

        Args:
            destinations: List of {address, amount} dicts
            priority: Transaction priority (0-3)
            get_tx_key: Whether to return tx keys
            do_not_relay: If True, don't relay to network
            new_algorithm: Use new transaction splitting algorithm

        Returns:
            Dict with tx_hash_list, tx_key_list, fee_list, amount_list
        """
        params = {
            "destinations": destinations,
            "priority": priority,
            "get_tx_key": get_tx_key,
            "do_not_relay": do_not_relay,
            "new_algorithm": new_algorithm
        }
        return self._make_request("transfer_split", params)

    def get_transfers(self, in_: bool = True, out: bool = True, pending: bool = True,
                     failed: bool = True, pool: bool = True) -> Dict[str, Any]:
        """Get list of transfers"""
        params = {
            "in": in_,
            "out": out,
            "pending": pending,
            "failed": failed,
            "pool": pool
        }
        return self._make_request("get_transfers", params)
        
    def incoming_transfers(self, transfer_type: str = "all") -> Dict[str, Any]:
        """Get incoming transfers"""
        params = {"transfer_type": transfer_type}
        return self._make_request("incoming_transfers", params)
        
    def store(self) -> Dict[str, Any]:
        """Save wallet file"""
        return self._make_request("store")
        
    def stop_wallet(self) -> Dict[str, Any]:
        """Stop wallet RPC server"""
        return self._make_request("stop_wallet")
        
    def rescan_blockchain(self) -> Dict[str, Any]:
        """Rescan blockchain from scratch"""
        return self._make_request("rescan_blockchain")
        
    def set_daemon(self, address: str, trusted: bool = True) -> Dict[str, Any]:
        """Set daemon connection"""
        params = {
            "address": address,
            "trusted": trusted
        }
        return self._make_request("set_daemon", params)