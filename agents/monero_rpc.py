"""
Monero RPC client wrappers for daemon and wallet communication.
Provides a clean interface for agents to interact with Monero processes.
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class RPCError(Exception):
    """Custom exception for RPC-related errors"""
    pass


class BaseRPC:
    """Base class for RPC communication"""
    
    def __init__(self, host: str, port: int, timeout: int = 30):
        self.url = f"http://{host}:{port}/json_rpc"
        self.timeout = timeout
        self.session = self._create_session()
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic"""
        session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504)
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
        
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
        except Exception:
            return False
            
    def wait_until_ready(self, max_wait: int = 60, check_interval: int = 1):
        """Wait until the RPC service is ready"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if self.is_ready():
                self.logger.info(f"RPC service ready at {self.url}")
                return
            time.sleep(check_interval)
        raise RPCError(f"RPC service not ready after {max_wait} seconds")


class MoneroRPC(BaseRPC):
    """Monero daemon RPC client"""
    
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
        return self._make_request("start_mining", params)
        
    def stop_mining(self) -> Dict[str, Any]:
        """Stop mining"""
        return self._make_request("stop_mining")
        
    def mining_status(self) -> Dict[str, Any]:
        """Get mining status"""
        return self._make_request("mining_status")
        
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
        return self._make_request("generateblocks", params)


class WalletRPC(BaseRPC):
    """Monero wallet RPC client"""
    
    def __init__(self, host: str, port: int, timeout: int = 30):
        super().__init__(host, port, timeout)
        # Wallet RPC uses a different endpoint
        self.url = f"http://{host}:{port}/json_rpc"
        
    def create_wallet(self, filename: str, password: str = "", language: str = "English") -> Dict[str, Any]:
        """Create a new wallet"""
        params = {
            "filename": filename,
            "password": password,
            "language": language
        }
        return self._make_request("create_wallet", params)
        
    def open_wallet(self, filename: str, password: str = "") -> Dict[str, Any]:
        """Open an existing wallet"""
        params = {
            "filename": filename,
            "password": password
        }
        return self._make_request("open_wallet", params)
        
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
                if "No wallet file" in str(e):
                    if i < max_retries - 1:
                        self.logger.warning(f"Wallet file not yet available, retrying in {retry_delay}s... ({i+1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                    else:
                        self.logger.error(f"Wallet file not available after {max_retries} retries. Aborting.")
                        raise
                else:
                    raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred in get_address: {e}")
                raise

        raise RPCError("Failed to get wallet address after multiple retries.")
        
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