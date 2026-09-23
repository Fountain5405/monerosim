#!/usr/bin/env python3
"""Proxy spy front-end (py-Levin) for the mainnet-replica "variant P" spy class.

This is a SIMULATION-ONLY research artifact. It runs entirely inside Shadow
against nodes the researcher controls, and it reproduces spy/proxy behaviour that
is already publicly documented for the live Monero network:

  * ProbeLab 2026: reachable "spy" nodes are a few real back-ends fronted by many
    lightweight IPs; the peer-id in a node's handshake differs from the id it
    returns to a PING (the front-end routes the ping elsewhere / mints a fresh id).
  * Boog900 (research-lab #126) and Friend-or-Foe (arXiv:2509.10214): proxy nodes
    are custom software that answers the admin protocol while proxying a real
    back-end, sometimes omitting support flags or returning oversized peer lists.
  * Our own 2026-09-23 crawl: ~74% of reachable IPs are such proxies, clustered
    in dense /24s in a single ASN.

The purpose is to MEASURE the deanonymisation risk these nodes create (stage-3 of
docs/superpowers/specs/2026-09-23-mainnet-replica-design.md) so it can be
understood and countered. It is the proxy counterpart of the real-node spy
(variant R = stock monerod); functionally it is a sibling of the already-merged
agents/eclipse_fakepeer.py, which uses the same Levin responder stack.

One process = one front-end IP. It:
  * Listens on a Levin admin port and answers HANDSHAKE / TIMED_SYNC / PING /
    REQUEST_SUPPORT_FLAGS via the shared responder (agents.eclipse_injector).
  * Reports the BACKEND monerod's real chain state (polled over RPC), so it looks
    like a live, synced peer rather than using the eclipse "genesis trick".
  * Presents the configurable fingerprints above (peer-id mismatch, support-flag
    presence), off/realistic by default per attributes.
  * Serves a peer list mixing the front-end fleet with the backend's real white
    list (fleet_share controls the mix).
  * Optionally holds a few outbound connections to honest reachable nodes so it
    occupies their inbound slots, as the real fleet does.

NOTE on transaction observation: the Levin layer here speaks only the ADMIN
protocol (commands 1001-1007). Receiving NOTIFY_NEW_TRANSACTIONS (2002) requires
completing the cryptonote handshake as a synced peer, which this stack does not
do; any 2002 bucket that does arrive is logged, but the tx-observation feed for
stage-3 experiment 1 is carried by the real-node spies (variant R), which log tx
arrivals at monitor log level. Full proxy-side tx observation is a follow-up.
"""
import random
import threading
import time
import json
import urllib.request

from agents import levin_lib as L
from agents.eclipse_injector import InjectorConfig, serve_forever, handle_connection


def ip_from_le_u32(v):
    """get_peer_list returns each ip as a little-endian uint32; render dotted."""
    if isinstance(v, str):
        return v
    v = int(v)
    return ".".join(str((v >> (8 * i)) & 0xFF) for i in range(4))


def mix_records(fleet, honest, n, fleet_share):
    """Build the served peer list: `fleet_share` of n from the front-end fleet,
    the rest from the backend's honest white list, shuffled together."""
    n_fleet = int(round(n * fleet_share))
    fleet = list(fleet)
    honest = list(honest)
    random.shuffle(fleet)
    random.shuffle(honest)
    recs = fleet[:n_fleet] + honest[: n - n_fleet]
    random.shuffle(recs)
    return recs[:n]


def _rpc(ip, port, method, params=None, timeout=5):
    body = json.dumps({"jsonrpc": "2.0", "id": "0", "method": method,
                       "params": params or {}}).encode()
    req = urllib.request.Request(
        f"http://{ip}:{port}/json_rpc", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("result", {})


def main():
    from agents.base_agent import BaseAgent
    from agents.agent_discovery import AgentDiscovery

    parser = BaseAgent.create_argument_parser("Monero proxy spy front-end")
    parser.add_argument("--port_base", "--port-base", dest="port_base", type=int, default=18080)
    parser.add_argument("--port_count", "--port-count", dest="port_count", type=int, default=1)
    parser.add_argument("--sync_interval", "--sync-interval", dest="sync_interval", type=int, default=30)
    parser.add_argument("--dial_budget", "--dial-budget", dest="dial_budget", type=int, default=8)
    args, _unknown = parser.parse_known_args()

    class SpyProxyAgent(BaseAgent):
        def _setup_agent(self):
            a = getattr(self, "attributes", {}) or {}
            self._discovery = AgentDiscovery(
                str(self.shared_dir) if self.shared_dir else None)
            self._ports = list(range(args.port_base,
                                     args.port_base + max(1, args.port_count)))
            self._stop = threading.Event()

            # --- attributes (defaults = realistic mainnet-2026 proxy behaviour) ---
            self._backend_group = str(a.get("backend_group", "spy-backend"))
            self._peer_id_mismatch = self.parse_bool(a.get("peer_id_mismatch", "true"))
            sf = str(a.get("support_flags", "present")).strip().lower()
            self._support_flags = 0 if sf in ("absent", "0", "none", "off") else 1
            self._oversized = int(a.get("oversized_peerlist", "0"))  # 0 = stock 250
            self._fleet_share = float(a.get("fleet_share", "0.5"))

            handshake_id = random.getrandbits(64)
            ping_id = random.getrandbits(64) if self._peer_id_mismatch else None
            max_records = self._oversized if self._oversized > 250 else 250

            # Chain state, refreshed from the backend by the poll thread. Start at
            # the genesis-trick fallback so we are still a valid-looking behind
            # peer if the backend is briefly unreachable at boot.
            self._chain = {"height": 1, "cumdiff": 1,
                           "top_id": b"\x00" * 32, "top_version": 1}
            self._honest_peers = []   # [(ip, port)] from the backend white list
            self._backends = []       # [(ip, rpc_port)]

            self._cfg = InjectorConfig(
                network_id=L.NETWORK_ID_MAINNET,
                peer_id=handshake_id,
                my_port=args.port_base,
                records_fn=self._records,
                max_records=max_records,
                logger=self.logger,
                ping_peer_id=ping_id,
                support_flags=self._support_flags,
            )
            self._resolve_backends()
            self._poll_backend()  # prime chain state + honest peers before serving

            for p in self._ports:
                threading.Thread(target=serve_forever,
                                 args=("0.0.0.0", p, self._cfg, self._stop),
                                 daemon=True).start()
            threading.Thread(target=self._poll_loop, daemon=True).start()
            if args.dial_budget > 0:
                threading.Thread(target=self._dial_loop, daemon=True).start()

            self.logger.info(
                "SpyProxyAgent up: %d port(s), backend_group=%s, "
                "peer_id_mismatch=%s, support_flags=%s, oversized=%d, "
                "fleet_share=%.2f, dial_budget=%d",
                len(self._ports), self._backend_group, self._peer_id_mismatch,
                self._support_flags, self._oversized, self._fleet_share,
                args.dial_budget)

        # ---- backend discovery + chain-state polling ----
        def _resolve_backends(self):
            reg = self._discovery.get_agent_registry(force_refresh=True) or {}
            agents = reg.get("agents", reg if isinstance(reg, list) else [])
            self._backends = []
            self._fleet = []
            for ad in agents:
                aid = ad.get("id", "")
                ip = ad.get("ip_addr")
                if not ip:
                    continue
                if aid.startswith(self._backend_group) and ad.get("daemon"):
                    self._backends.append((ip, ad.get("daemon_rpc_port", 18081)))
                if ad.get("user_script") == "agents.spy_proxy":
                    self._fleet.append(ip)
            self.logger.info("resolved %d backend(s), %d fleet front-end(s)",
                             len(self._backends), len(self._fleet))

        def _poll_backend(self):
            for ip, rpc in self._backends:
                try:
                    info = _rpc(ip, rpc, "get_info")
                    hf = _rpc(ip, rpc, "hard_fork_info")
                    top = info.get("top_block_hash", "")
                    self._chain = {
                        "height": int(info.get("height", 1)),
                        "cumdiff": int(info.get("cumulative_difficulty", 1)),
                        "top_id": bytes.fromhex(top) if top else b"\x00" * 32,
                        "top_version": int(hf.get("version", 1)),
                    }
                    c = self._chain
                    self._cfg.height, self._cfg.cumdiff = c["height"], c["cumdiff"]
                    self._cfg.top_id, self._cfg.top_version = c["top_id"], c["top_version"]
                    try:
                        pl = _rpc(ip, rpc, "get_peer_list")
                        white = pl.get("white_list", []) if isinstance(pl, dict) else []
                        self._honest_peers = [
                            (ip_from_le_u32(e.get("ip")), e.get("port", 18080))
                            for e in white if e.get("ip")]
                    except Exception:
                        pass
                    return True
                except Exception as e:
                    self.logger.debug("backend %s:%s poll failed: %s", ip, rpc, e)
            self.logger.warning(
                "no backend in group '%s' reachable; serving genesis-trick "
                "fallback chain state until one is", self._backend_group)
            return False

        def _poll_loop(self):
            while not self._stop.is_set():
                self._stop.wait(args.sync_interval)
                if not self._stop.is_set():
                    self._poll_backend()

            v = int(v)
            return ".".join(str((v >> (8 * i)) & 0xFF) for i in range(4))

        # ---- peer list served to dialers: fleet mixed with the backend white list ----
        def _records(self):
            fleet = [(ip, p) for ip in self._fleet for p in self._ports]
            return mix_records(fleet, self._honest_peers,
                               self._cfg.max_records, self._fleet_share)

        # ---- hold a few outbound connections to honest reachable nodes ----
        def _dial_loop(self):
            while not self._stop.is_set():
                targets = [t for t in self._honest_peers if t[0] not in self._fleet]
                random.shuffle(targets)
                held = 0
                for ip, port in targets[: args.dial_budget]:
                    if self._stop.is_set():
                        break
                    if self._hold_one(ip, port):
                        held += 1
                self.logger.debug("dialer: holding ~%d outbound", held)
                self._stop.wait(max(30, args.sync_interval))

        def _hold_one(self, ip, port):
            def worker():
                try:
                    s = L.connect(ip, port, timeout=10)
                except OSError:
                    return
                try:
                    c = self._chain
                    req = L.serialize(L.handshake_request(
                        L.NETWORK_ID_MAINNET, args.port_base, self._cfg.peer_id,
                        c["height"], c["cumdiff"], c["top_id"], c["top_version"]))
                    s.sendall(L.pack_header(L.COMMAND_HANDSHAKE, len(req),
                                            L.LEVIN_PACKET_REQUEST, expect_response=True))
                    s.sendall(req)
                    try:
                        L.read_bucket(s)
                    except OSError:
                        pass
                    # keep the socket open (occupies the peer's inbound slot);
                    # answer any admin request it sends us as our own responder would.
                    s.settimeout(120)
                    handle_connection(s, self._cfg)
                except OSError:
                    try:
                        s.close()
                    except OSError:
                        pass
            threading.Thread(target=worker, daemon=True).start()
            return True

        def run_iteration(self):
            # The responder, poller and dialer run in their own threads; the main
            # loop just reports footprint periodically. Returns the sleep interval.
            self.logger.info(
                "spy_proxy: serving %d port(s) at chain h=%d; conns=%d "
                "records=%d (fleet=%d honest=%d)",
                len(self._ports), self._chain["height"], self._cfg.conns,
                len(self._records()), len(self._fleet), len(self._honest_peers))
            return float(max(30, args.sync_interval))

    agent = SpyProxyAgent(
        agent_id=args.id, shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port, wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port, rpc_host=args.rpc_host, log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
