#!/usr/bin/env python3
"""Active-recency spy refresher (py-Levin) — the open-question-13 adversary.

SIMULATION-ONLY research artifact (journal open question 13; plan section 7,
revised order item 2). It runs inside Shadow, on each spy host, next to that
host's variant-R spy daemon (stock monerod-sim), and its purpose is to MEASURE
whether the candidate-rule finding survives an adversary that keeps itself
newest, so the defense work can be judged against the worst case.

Mechanism (verified in sibling_repos/monero, net_node.inl handle_handshake ->
try_ping; net_peerlist.h append_with_peer_white): an inbound handshake alone
writes nothing. The target refreshes the dialer's WHITE entry -- keyed by
(socket ip, advertised my_port), carrying the ADVERTISED peer id, last_seen =
now -- only after a ping-back to that address succeeds. So every interval this
agent dials each honest reachable node and completes a Levin HANDSHAKE
advertising the SPY DAEMON's identity: its listen port and its real peer id
(learned by dialing our own daemon, whose response carries node_data.peer_id),
plus chain state polled over daemon RPC so we handshake as a synced peer. The
target's try_ping then lands on the daemon, matches the id, and refreshes the
spy's entry. Gossip never refreshes last_seen (append_with_peer_gray preserves
timestamps), so between the spy's own connection events this is the only thing
keeping the fleet at the top of every white list's recency order.

The dial pattern is eclipse_injector.dial_and_handshake's, validated against
real monerod: connect, send HANDSHAKE, drain one response bucket, close. The
per-IP inbound cap (max-connections-per-ip, default 1) is not contended
because we hold nothing.
"""
import json
import os
import random
import socket
import time
import urllib.request

from agents import levin_lib as L
from agents.base_agent import MONERO_P2P_PORT, MONERO_RPC_PORT
from agents.agent_discovery import AgentDiscovery

# Registry ids that never take an inbound dial in the lean cells: our own
# fleet and the unreachable users (hide-my-port, nothing listens).
EXCLUDE_PREFIXES = ("spy-", "user-")

# A target IP that never answers; only used by the UDP local-ip trick.
_ANY_REMOTE = ("176.9.0.187", 18080)


def _local_ip():
    """This host's sim IP: connect (no packets sent) a UDP socket."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(_ANY_REMOTE)
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _rpc(ip, port, method, params=None, timeout=5):
    body = json.dumps({"jsonrpc": "2.0", "id": "0", "method": method,
                       "params": params or {}}).encode()
    req = urllib.request.Request(
        f"http://{ip}:{port}/json_rpc", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("result", {})


def refresh_once(ip, port, ident, timeout):
    """One re-handshake as the spy daemon. The white-list refresh is done by
    the target's asynchronous ping-back to (our ip, ident['my_port']); this
    returns once the handshake exchange is complete."""
    s = L.connect(ip, port, timeout=timeout)
    try:
        req = L.serialize(L.handshake_request(
            L.NETWORK_ID_MAINNET, ident["my_port"], ident["peer_id"],
            ident["height"], ident["cumdiff"], ident["top_id"],
            top_version=ident["top_version"]))
        s.sendall(L.pack_header(L.COMMAND_HANDSHAKE, len(req),
                                L.LEVIN_PACKET_REQUEST, expect_response=True))
        s.sendall(req)
        L.read_bucket(s)
        return True
    finally:
        try:
            s.close()
        except OSError:
            pass


def main():
    from agents.base_agent import BaseAgent

    parser = BaseAgent.create_argument_parser(
        "OQ13 active-recency spy refresher (re-handshakes the spy's identity "
        "with every honest reachable node on a timer)")
    parser.add_argument("--refresh_interval", "--refresh-interval",
                        dest="refresh_interval", type=int, default=0,
                        help="sim-seconds between full sweeps (0 = use the "
                             "refresh_interval attribute, else 300)")
    parser.add_argument("--dial_timeout", "--dial-timeout", dest="dial_timeout",
                        type=float, default=6.0,
                        help="per-dial connect/IO timeout in sim-seconds")
    args, _unknown = parser.parse_known_args()

    class SpyRefreshAgent(BaseAgent):
        def _setup_agent(self):
            a = getattr(self, "attributes", {}) or {}
            self._interval = float(args.refresh_interval or a.get("refresh_interval") or 300)
            self._my_port = self.p2p_port or MONERO_P2P_PORT
            self._daemon_ip = (self.rpc_host
                               if self.rpc_host not in (None, "", "127.0.0.1")
                               else _local_ip())
            self._rpc_port = self.daemon_rpc_port or MONERO_RPC_PORT
            self._discovery = AgentDiscovery(str(self.shared_dir) if self.shared_dir else None)
            # Last-good chain state; height 1 / genesis top_id is a valid
            # behind-peer handshake if the daemon RPC is briefly unreachable.
            self._chain = {"height": 1, "cumdiff": 1,
                           "top_id": b"\x00" * 32, "top_version": 1}
            self.logger.info(
                "SpyRefreshAgent up: daemon %s:%d (p2p %d), sweep every %.0fs",
                self._daemon_ip, self._rpc_port, self._my_port, self._interval)
            # Reproducible but per-spy distinct sweep order: same SIMULATION_SEED
            # replays a cell identically, the id keeps the fleet out of lockstep.
            sim_seed = os.environ.get("SIMULATION_SEED")
            if sim_seed:
                random.seed(f"{sim_seed}:{self.agent_id}")

        def _fetch_peer_id(self):
            """Our daemon's real peer id, from its own HANDSHAKE response.
            We advertise my_port 0 so the daemon ping-backs nothing and writes
            no entry for us."""
            s = L.connect(self._daemon_ip, self._my_port, timeout=args.dial_timeout)
            try:
                req = L.serialize(L.handshake_request(
                    L.NETWORK_ID_MAINNET, 0, random.getrandbits(64),
                    1, 1, b"\x00" * 32))
                s.sendall(L.pack_header(L.COMMAND_HANDSHAKE, len(req),
                                        L.LEVIN_PACKET_REQUEST,
                                        expect_response=True))
                s.sendall(req)
                _c, _f, _rc, _hr, payload = L.read_bucket(s)
                pid = (L.parse(payload).get("node_data") or {}).get("peer_id")
                if not isinstance(pid, int) or pid == 0:
                    raise ValueError("daemon handshake carried no peer_id")
                return pid
            finally:
                try:
                    s.close()
                except OSError:
                    pass

        def _poll_chain(self):
            try:
                info = _rpc(self._daemon_ip, self._rpc_port, "get_info")
                hf = _rpc(self._daemon_ip, self._rpc_port, "hard_fork_info")
                top = info.get("top_block_hash") or ""
                self._chain = {
                    "height": int(info.get("height", 1) or 1),
                    "cumdiff": int(info.get("cumulative_difficulty", 1) or 1),
                    "top_id": bytes.fromhex(top) if len(top) == 64 else b"\x00" * 32,
                    "top_version": int((hf or {}).get("version", 1) or 1),
                }
            except Exception as e:  # noqa: BLE001 - a stale cache is a valid behind-peer
                self.logger.debug("chain poll failed (%s); keeping last state", e)

        def _targets(self):
            """Honest reachable nodes: every registry daemon outside our own
            fleet and the unreachable users. Ordered by shuffle so the fleet's
            sweeps do not run in lockstep."""
            out = []
            try:
                agents = self._discovery.get_agent_registry(force_refresh=True).get("agents", [])
            except Exception as e:  # noqa: BLE001 - an unreadable registry skips one sweep
                self.logger.warning("registry read failed (%s); no sweep this cycle", e)
                return out
            for ag in agents if isinstance(agents, list) else []:
                aid = ag.get("id", "") or ""
                if not ag.get("daemon") or not ag.get("ip_addr"):
                    continue
                if aid == self.agent_id or aid.startswith(EXCLUDE_PREFIXES):
                    continue
                if ag.get("user_script") == "agents.spy_refresh":
                    continue
                out.append((ag["ip_addr"], MONERO_P2P_PORT))
            random.shuffle(out)
            return out

        def run_iteration(self):
            try:
                peer_id = self._fetch_peer_id()
            except Exception as e:  # noqa: BLE001 - daemon briefly down: retry next cycle
                self.logger.warning("daemon identity fetch failed (%s); retrying", e)
                return min(30.0, self._interval)
            self._poll_chain()
            ident = dict(self._chain, peer_id=peer_id, my_port=self._my_port)

            targets = self._targets()
            ok = fail = 0
            # Leave headroom inside the interval; a sweep that would overrun
            # (many targets still starting, long timeouts) resumes next cycle.
            deadline = time.monotonic() + self._interval * 0.8
            for ip, port in targets:
                if not self.running or time.monotonic() > deadline:
                    break
                try:
                    refresh_once(ip, port, ident, args.dial_timeout)
                    ok += 1
                except Exception as e:  # noqa: BLE001 - one dead target must not kill the sweep
                    fail += 1
                    self.logger.debug("dial %s:%d failed: %s", ip, port, e)
            self.logger.info(
                "spy_refresh: %d/%d honest nodes refreshed as peer %x @ h=%d "
                "(ok=%d fail=%d%s)",
                ok, len(targets), peer_id, self._chain["height"], ok, fail,
                "" if ok + fail == len(targets)
                else f", {len(targets) - ok - fail} deferred to next sweep")
            return self._interval

    agent = SpyRefreshAgent(
        agent_id=args.id, shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port, wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port, rpc_host=args.rpc_host, log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
