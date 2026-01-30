#!/usr/bin/env python3
"""
tcp_mining_agent.py - TCP-based mining agent for mininghooks mode.

This agent communicates with monerod running in --simulation-mode --simulation-tcp
mode. It receives mining requests via TCP socket and returns simulated nonces
after a Poisson-distributed delay based on the configured hashrate.

Protocol:
  Request (monerod -> agent): 48 bytes
    [0:32]   block_header_hash (bytes)
    [32:40]  difficulty (uint64_le)
    [40:48]  template_id (uint64_le)

  Response (agent -> monerod): 12 bytes
    [0:4]    nonce (uint32_le)
    [4:12]   template_id (uint64_le)
"""

import argparse
import json
import logging
import math
import random
import signal
import socket
import struct
import sys
import time
import urllib.request
import urllib.error
from typing import Tuple, Optional

# Protocol constants
REQUEST_SIZE = 48
RESPONSE_SIZE = 12
DEFAULT_PORT = 19000
DEFAULT_HASHRATE = 100.0  # H/s

# Global flag for graceful shutdown
shutdown_requested = False

# Standard regtest address for mining rewards
TEST_MINER_ADDRESS = "44AFFq5kSiGBoZ4NMDwYtN18obc8AemS33DBLWs3H7otXft3XjrpDtQGv7SqSsaBYBb98uNbr2VBBEt7f2wfn3RVGQBEP3A"


def start_mining_rpc(rpc_host: str, rpc_port: int, miner_address: str,
                     threads: int = 1, logger: logging.Logger = None,
                     max_retries: int = 30, retry_delay: float = 2.0) -> bool:
    """
    Call start_mining RPC on monerod to initiate mining.

    Args:
        rpc_host: monerod RPC host
        rpc_port: monerod RPC port
        miner_address: Address to receive mining rewards
        threads: Number of mining threads
        logger: Logger instance
        max_retries: Maximum number of retry attempts for BUSY status
        retry_delay: Seconds to wait between retries

    Returns:
        True if mining started successfully
    """
    url = f"http://{rpc_host}:{rpc_port}/start_mining"
    payload = {
        "miner_address": miner_address,
        "threads_count": threads,
        "do_background_mining": False,
        "ignore_battery": True
    }

    data = json.dumps(payload).encode('utf-8')

    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                status = result.get("status")

                if status == "OK":
                    if logger:
                        logger.info(f"Mining started successfully on {rpc_host}:{rpc_port}")
                    return True
                elif status == "BUSY":
                    # Daemon is busy (still syncing or initializing), retry
                    if logger:
                        logger.info(f"Daemon BUSY, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    if logger:
                        logger.warning(f"start_mining response: {result}")
                    return False
        except urllib.error.URLError as e:
            if logger:
                logger.error(f"Failed to call start_mining: {e}")
            return False
        except Exception as e:
            if logger:
                logger.error(f"Unexpected error calling start_mining: {e}")
            return False

    if logger:
        logger.error(f"Failed to start mining after {max_retries} retries (daemon stayed BUSY)")
    return False


def wait_for_daemon_ready(rpc_host: str, rpc_port: int, timeout: int = 120,
                          logger: logging.Logger = None) -> bool:
    """
    Wait for monerod daemon to be ready and synchronized.

    Args:
        rpc_host: monerod RPC host
        rpc_port: monerod RPC port
        timeout: Maximum time to wait in seconds
        logger: Logger instance

    Returns:
        True if daemon is ready
    """
    url = f"http://{rpc_host}:{rpc_port}/json_rpc"
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_info",
        "params": {}
    }

    data = json.dumps(payload).encode('utf-8')
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "result" in result:
                    info = result["result"]
                    synced = info.get("synchronized", False)
                    height = info.get("height", 0)
                    if logger:
                        logger.info(f"Daemon ready: height={height}, synchronized={synced}")
                    return True
        except Exception as e:
            if logger:
                logger.debug(f"Waiting for daemon... ({e})")
        time.sleep(2)

    if logger:
        logger.error(f"Timeout waiting for daemon after {timeout}s")
    return False


def setup_logging(agent_id: str, log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the agent."""
    logger = logging.getLogger(f"tcp_mining_agent.{agent_id}")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        f'[%(asctime)s] [{agent_id}] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def compute_poisson_delay(difficulty: int, hashrate: float) -> float:
    """
    Compute mining time using Poisson process.

    The time to find a block follows an exponential distribution with
    expected value = difficulty / hashrate.

    Args:
        difficulty: Current mining difficulty
        hashrate: Miner's hash rate in H/s

    Returns:
        Simulated time in seconds until block is found
    """
    if hashrate <= 0:
        raise ValueError("Hashrate must be positive")

    expected_time = difficulty / hashrate

    # Generate exponentially distributed random variable
    u = random.random()
    if u == 0:
        u = 1e-10  # Avoid log(0)

    return -math.log(u) * expected_time


def parse_request(data: bytes) -> Tuple[bytes, int, int]:
    """
    Parse mining request from binary data.

    Args:
        data: Raw bytes from monerod (48 bytes)

    Returns:
        Tuple of (block_hash, difficulty, template_id)
    """
    if len(data) != REQUEST_SIZE:
        raise ValueError(f"Expected {REQUEST_SIZE} bytes, got {len(data)}")

    block_hash = data[0:32]
    difficulty = struct.unpack('<Q', data[32:40])[0]
    template_id = struct.unpack('<Q', data[40:48])[0]

    return block_hash, difficulty, template_id


def pack_response(nonce: int, template_id: int) -> bytes:
    """
    Pack mining response into binary data.

    Args:
        nonce: The found nonce (uint32)
        template_id: The template ID to return (uint64)

    Returns:
        12 bytes of packed response
    """
    return struct.pack('<I', nonce) + struct.pack('<Q', template_id)


def handle_client(conn: socket.socket, hashrate: float, logger: logging.Logger) -> bool:
    """
    Handle a single mining request from monerod.

    Args:
        conn: The client socket connection
        hashrate: This miner's hash rate in H/s
        logger: Logger instance

    Returns:
        True if request was handled successfully, False otherwise
    """
    global shutdown_requested

    logger.debug("New connection received")

    # Read the full request
    data = b''
    conn.settimeout(30.0)  # 30 second timeout for reading

    try:
        while len(data) < REQUEST_SIZE:
            if shutdown_requested:
                logger.info("Shutdown requested, closing connection")
                return False

            chunk = conn.recv(REQUEST_SIZE - len(data))
            if not chunk:
                logger.warning("Connection closed before full request received")
                return False
            data += chunk
    except socket.timeout:
        logger.error("Timeout waiting for request data")
        return False

    # Parse the request
    try:
        block_hash, difficulty, template_id = parse_request(data)
    except ValueError as e:
        logger.error(f"Failed to parse request: {e}")
        return False

    logger.info(f"Mining request: difficulty={difficulty}, template_id={template_id}")
    logger.debug(f"Block hash: {block_hash.hex()[:16]}...")

    # Compute simulated mining time
    delay = compute_poisson_delay(difficulty, hashrate)
    expected_time = difficulty / hashrate

    logger.info(f"Mining simulation: expected={expected_time:.2f}s, actual={delay:.2f}s")

    # Sleep to simulate mining time
    # For very long delays, check shutdown flag periodically
    remaining = delay
    while remaining > 0 and not shutdown_requested:
        sleep_time = min(remaining, 1.0)  # Sleep at most 1 second at a time
        time.sleep(sleep_time)
        remaining -= sleep_time

    if shutdown_requested:
        logger.info("Shutdown during mining simulation")
        return False

    # Generate random nonce
    nonce = random.randint(0, 0xFFFFFFFF)

    logger.info(f"Block found: nonce=0x{nonce:08x}")

    # Send response
    try:
        response = pack_response(nonce, template_id)
        conn.sendall(response)
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        return False

    return True


def run_agent(host: str, port: int, hashrate: float, agent_id: str,
              rpc_host: str = None, rpc_port: int = 18081,
              miner_address: str = None, log_level: str = "INFO") -> None:
    """
    Run the TCP mining agent.

    Args:
        host: IP address to bind to for TCP socket
        port: TCP port to listen on
        hashrate: Simulated hashrate in H/s
        agent_id: Unique identifier for this agent
        rpc_host: monerod RPC host (defaults to same as host)
        rpc_port: monerod RPC port
        miner_address: Address for mining rewards
        log_level: Logging level
    """
    global shutdown_requested

    logger = setup_logging(agent_id, log_level)

    # Default rpc_host to same as listen host
    if rpc_host is None:
        rpc_host = host

    # Default miner address
    if miner_address is None:
        miner_address = TEST_MINER_ADDRESS

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        global shutdown_requested
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_requested = True

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create TCP socket first so monerod can connect
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((host, port))
        server.listen(1)
        server.settimeout(1.0)  # Allow periodic shutdown checks
    except Exception as e:
        logger.error(f"Failed to bind to {host}:{port}: {e}")
        sys.exit(1)

    logger.info("=== TCP Mining Agent Started ===")
    logger.info(f"Listening on: {host}:{port}")
    logger.info(f"Hashrate: {hashrate} H/s")

    # Wait for daemon to be ready before starting mining
    logger.info(f"Waiting for daemon at {rpc_host}:{rpc_port}...")
    if wait_for_daemon_ready(rpc_host, rpc_port, timeout=120, logger=logger):
        # Start mining via RPC
        logger.info("Triggering start_mining RPC...")
        if start_mining_rpc(rpc_host, rpc_port, miner_address, threads=1, logger=logger):
            logger.info("Mining initiated, waiting for requests...")
        else:
            logger.warning("Failed to start mining, will wait for requests anyway...")
    else:
        logger.warning("Daemon not ready, will wait for requests anyway...")

    logger.info("Waiting for mining requests from monerod...")

    blocks_found = 0
    start_time = time.time()

    try:
        while not shutdown_requested:
            try:
                conn, addr = server.accept()
                logger.debug(f"Connection from {addr}")

                try:
                    if handle_client(conn, hashrate, logger):
                        blocks_found += 1
                finally:
                    conn.close()

            except socket.timeout:
                # Normal timeout, just check shutdown flag
                continue
            except Exception as e:
                if not shutdown_requested:
                    logger.error(f"Error accepting connection: {e}")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        server.close()

    elapsed = time.time() - start_time
    logger.info("=== TCP Mining Agent Stopped ===")
    logger.info(f"Blocks found: {blocks_found}")
    logger.info(f"Runtime: {elapsed:.1f}s")
    if blocks_found > 0 and elapsed > 0:
        logger.info(f"Average block time: {elapsed/blocks_found:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="TCP mining agent for monerod simulation mode"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="IP address to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port to listen on (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--hashrate", "-r",
        type=float,
        default=DEFAULT_HASHRATE,
        help=f"Simulated hashrate in H/s (default: {DEFAULT_HASHRATE})"
    )
    parser.add_argument(
        "--id",
        type=str,
        default="miner",
        help="Agent identifier for logging (default: miner)"
    )
    parser.add_argument(
        "--rpc-host",
        type=str,
        default=None,
        help="monerod RPC host for start_mining call (default: same as --host)"
    )
    parser.add_argument(
        "--rpc-port",
        type=int,
        default=18081,
        help="monerod RPC port (default: 18081)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    run_agent(
        host=args.host,
        port=args.port,
        hashrate=args.hashrate,
        agent_id=args.id,
        rpc_host=args.rpc_host,
        rpc_port=args.rpc_port,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
