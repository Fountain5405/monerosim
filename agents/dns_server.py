#!/usr/bin/env python3
"""
DNS Server for Monerosim Shadow Simulation

A simple DNS server that responds to Monero's DNS queries for seed nodes
and checkpoints within the Shadow simulation environment.

This enables monerod to use its built-in DNS peer discovery mechanism
instead of requiring patched DNS-disabling code.
"""

import argparse
import fcntl
import json
import logging
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    from dnslib import DNSRecord, DNSHeader, RR, QTYPE, A, TXT, RCODE
    from dnslib.server import DNSServer, BaseResolver
except ImportError:
    print("ERROR: dnslib not installed. Run: pip install dnslib", file=sys.stderr)
    sys.exit(1)


class MoneroResolver(BaseResolver):
    """
    DNS resolver for Monero seed nodes and checkpoints.

    Responds to:
    - A record queries for seed node domains -> returns miner IPs
    - TXT record queries for checkpoint domains -> returns checkpoints (empty for now)
    """

    # Monero seed node domains
    SEED_DOMAINS: Set[str] = {
        "seeds.moneroseeds.se.",
        "seeds.moneroseeds.ae.org.",
        "seeds.moneroseeds.ch.",
        "seeds.moneroseeds.li.",
    }

    # Monero checkpoint domains
    CHECKPOINT_DOMAINS: Set[str] = {
        "checkpoints.moneropulse.se.",
        "checkpoints.moneropulse.org.",
        "checkpoints.moneropulse.net.",
        "checkpoints.moneropulse.co.",
    }

    # Testnet checkpoint domains
    TESTNET_CHECKPOINT_DOMAINS: Set[str] = {
        "testpoints.moneropulse.se.",
        "testpoints.moneropulse.org.",
        "testpoints.moneropulse.net.",
        "testpoints.moneropulse.co.",
    }

    def __init__(self, shared_dir: Path, logger: logging.Logger):
        self.shared_dir = shared_dir
        self.logger = logger
        self.seed_ips: List[str] = []
        self.checkpoints: Dict[int, str] = {}  # height -> block_hash
        self._last_registry_load = 0
        self._registry_cache_ttl = 5  # seconds

    def _load_seed_ips(self) -> List[str]:
        """Load miner IPs from agent registry as seed nodes."""
        now = time.time()
        if now - self._last_registry_load < self._registry_cache_ttl and self.seed_ips:
            return self.seed_ips

        registry_path = self.shared_dir / "agent_registry.json"
        lock_path = self.shared_dir / "agent_registry.lock"
        if not registry_path.exists():
            self.logger.warning(f"Agent registry not found: {registry_path}")
            return self.seed_ips

        try:
            # Use file locking for deterministic reads (consistent with base_agent.py)
            with open(lock_path, 'w') as lock_f:
                fcntl.flock(lock_f, fcntl.LOCK_SH)  # Shared lock for reading
                try:
                    with open(registry_path, 'r') as f:
                        registry = json.load(f)
                finally:
                    fcntl.flock(lock_f, fcntl.LOCK_UN)

            # Get IPs of miners (seed nodes)
            seed_ips = []
            for agent in registry.get("agents", []):
                # Miners are seed nodes
                attrs = agent.get("attributes", {})
                is_miner = str(attrs.get("is_miner", "")).lower() in ("true", "1", "yes")

                if is_miner and agent.get("ip_addr"):
                    seed_ips.append(agent["ip_addr"])

            if seed_ips:
                self.seed_ips = seed_ips
                self._last_registry_load = now
                self.logger.info(f"Loaded {len(seed_ips)} seed node IPs: {seed_ips}")
            else:
                self.logger.warning("No miner IPs found in registry")

        except Exception as e:
            self.logger.error(f"Failed to load agent registry: {e}")

        return self.seed_ips

    def _load_checkpoints(self) -> Dict[int, str]:
        """Load checkpoints from shared file (future feature)."""
        checkpoint_path = self.shared_dir / "dns_checkpoints.json"
        lock_path = self.shared_dir / "dns_checkpoints.lock"
        if not checkpoint_path.exists():
            return self.checkpoints

        try:
            # Use file locking for deterministic reads
            with open(lock_path, 'w') as lock_f:
                fcntl.flock(lock_f, fcntl.LOCK_SH)  # Shared lock for reading
                try:
                    with open(checkpoint_path, 'r') as f:
                        data = json.load(f)
                finally:
                    fcntl.flock(lock_f, fcntl.LOCK_UN)
            self.checkpoints = {int(k): v for k, v in data.items()}
            self.logger.info(f"Loaded {len(self.checkpoints)} checkpoints")
        except Exception as e:
            self.logger.error(f"Failed to load checkpoints: {e}")

        return self.checkpoints

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain name to have trailing dot (FQDN format)."""
        return domain if domain.endswith('.') else domain + '.'

    def _is_seed_domain(self, qname: str) -> bool:
        """Check if query is for a seed domain (handles trailing dot variations)."""
        normalized = self._normalize_domain(qname)
        return normalized in self.SEED_DOMAINS

    def _is_checkpoint_domain(self, qname: str) -> bool:
        """Check if query is for a checkpoint domain."""
        normalized = self._normalize_domain(qname)
        return normalized in (self.CHECKPOINT_DOMAINS | self.TESTNET_CHECKPOINT_DOMAINS)

    def resolve(self, request: DNSRecord, handler) -> DNSRecord:
        """Resolve DNS queries."""
        reply = request.reply()
        qname = str(request.q.qname)
        qtype = QTYPE[request.q.qtype]

        self.logger.debug(f"DNS query: {qname} ({qtype})")

        # Handle seed node queries (A records)
        if qtype == "A" and self._is_seed_domain(qname):
            seed_ips = self._load_seed_ips()
            for ip in seed_ips:
                reply.add_answer(RR(
                    rname=request.q.qname,
                    rtype=QTYPE.A,
                    ttl=300,
                    rdata=A(ip)
                ))
            self.logger.info(f"Responded to {qname} with {len(seed_ips)} A records")
            return reply

        # Handle checkpoint queries (TXT records)
        if qtype == "TXT" and self._is_checkpoint_domain(qname):
            checkpoints = self._load_checkpoints()
            for height, block_hash in checkpoints.items():
                txt_data = f"{height}:{block_hash}"
                reply.add_answer(RR(
                    rname=request.q.qname,
                    rtype=QTYPE.TXT,
                    ttl=300,
                    rdata=TXT(txt_data)
                ))
            self.logger.info(f"Responded to {qname} with {len(checkpoints)} TXT records")
            return reply

        # For unknown queries, return NXDOMAIN
        reply.header.rcode = RCODE.NXDOMAIN
        self.logger.debug(f"NXDOMAIN for {qname} ({qtype})")
        return reply


class MoneroDNSServer:
    """
    DNS server for Monerosim Shadow simulation.

    Runs as a script-only agent, providing DNS resolution for monerod's
    built-in peer discovery mechanism.
    """

    def __init__(
        self,
        agent_id: str,
        bind_ip: str = "0.0.0.0",
        port: int = 53,
        shared_dir: Path = Path("/tmp/monerosim_shared"),
        log_level: str = "INFO"
    ):
        self.agent_id = agent_id
        self.bind_ip = bind_ip
        self.port = port
        self.shared_dir = shared_dir
        self.running = True

        # Setup logging
        self.logger = self._setup_logging(log_level)

        # Create resolver
        self.resolver = MoneroResolver(shared_dir, self.logger)

        # DNS server will be created on start
        self.server: Optional[DNSServer] = None

        # Signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _setup_logging(self, log_level: str) -> logging.Logger:
        """Setup logging for the DNS server."""
        logger = logging.getLogger(f"DNSServer[{self.agent_id}]")
        level = getattr(logging, log_level.upper(), logging.INFO)
        logger.setLevel(level)

        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            f'%(asctime)s - {self.agent_id} - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down")
        self.running = False
        if self.server:
            self.server.stop()

    def start(self):
        """Start the DNS server."""
        self.logger.info(f"Starting DNS server on {self.bind_ip}:{self.port}")

        try:
            # Use UDP - standard DNS protocol. Shadow now supports UDP DNS queries
            # via the dns_server configuration option in shadow.yaml.
            self.server = DNSServer(
                self.resolver,
                port=self.port,
                address=self.bind_ip,
                tcp=False  # UDP mode - standard DNS protocol
            )
            self.server.start_thread()
            self.logger.info("DNS server started successfully (UDP mode)")

            # Keep running until signaled to stop
            while self.running and self.server.isAlive():
                time.sleep(1)

        except PermissionError:
            self.logger.error(f"Permission denied binding to port {self.port}. "
                            "DNS servers typically require root privileges for port 53.")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Failed to start DNS server: {e}")
            sys.exit(1)
        finally:
            if self.server:
                self.server.stop()
            self.logger.info("DNS server stopped")


def main():
    """Main entry point for the DNS server agent."""
    parser = argparse.ArgumentParser(
        description="DNS Server for Monerosim Shadow Simulation"
    )
    parser.add_argument('--id', required=True, help='Agent ID')
    parser.add_argument('--bind-ip', default='0.0.0.0', help='IP to bind to')
    parser.add_argument('--port', type=int, default=53, help='DNS port')
    parser.add_argument('--shared-dir', type=Path,
                       default=Path('/tmp/monerosim_shared'),
                       help='Shared state directory')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--rpc-host', help='Ignored (for compatibility)')
    parser.add_argument('--attributes', nargs=2, action='append', default=[],
                       help='Ignored (for compatibility)')

    args = parser.parse_args()

    server = MoneroDNSServer(
        agent_id=args.id,
        bind_ip=args.bind_ip,
        port=args.port,
        shared_dir=args.shared_dir,
        log_level=args.log_level
    )

    server.start()


if __name__ == "__main__":
    main()
