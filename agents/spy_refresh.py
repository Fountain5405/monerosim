#!/usr/bin/env python3
"""Active-recency spy refresher (py-Levin) — the open-question-13 adversary, v2 (front ports).

SIMULATION-ONLY research artifact (journal open question 13; plan section 7, revised
order item 2), running inside Shadow on each spy host next to that host's variant-R spy
daemon (stock monerod-sim), to MEASURE whether the candidate-rule finding survives an
adversary that keeps itself newest.

v1 dialed every honest node advertising the spy daemon's own (ip, 18080), expecting the
ping-back to refresh the spies' white-list entries. The first smoke (run 88) disproved
that premise at the source: an inbound handshake's successful ping-back calls
append_with_peer_white(pe) with the default trust_last_seen=false, and the guard
(src/p2p/net_peerlist.h, "do not overwrite the last seen timestamp, incoming peer lists
are untrusted") preserves the existing entry's timestamp. Only a node's OWN outbound
connections refresh timestamps (set_peer_just_seen, trust=true). No re-handshake
adversary can refresh an entry that is already white — in the lab or on mainnet.

What the ping path DOES do is INSERT a fresh white entry, last_seen=now, at the
ADVERTISED (socket ip, my_port) whenever that address is not already white. And the
outbound draw's port-dedup (net_node.inl make_new_connection_from_peerlist) keeps only
the NEWEST entry per host (foreach walks the white list newest-first), so the
advertiser's freshest port becomes the host's representative; subnet-dedup then sorts
by last_seen, cuts the newest 20 candidates, and the cubic draw front-loads them. The
achievable active adversary is therefore a FRONT-END: listen on extra ports, advertise
a rotating one, and every honest node holds an always-fresh white entry for the spy's
host — the documented mainnet proxy architecture (ProbeLab 2026; the lab's variant P).
Rotation is required because an inserted entry ages from its insert: once a node is
connected to a front port, its timed syncs keep that entry fresh, but while it is not,
only a new port can be fresh again. Retired ports keep their listeners (live
connections are not cut); their entries simply age out of the candidate cut.

The responder presents the SPY DAEMON's identity (peer id learned from its own
handshake response, chain state polled over its RPC, its white list served back), so a
node that dials a front port reaches a synced-looking peer that answers HANDSHAKE /
TIMED_SYNC / PING / support flags, and holds it as an outbound stem slot — the same
validated stack as agents/eclipse_fakepeer.py and agents/spy_proxy.py.
"""
import json
import os
import random
import socket
import threading
import time
import urllib.request

from agents import levin_lib as L
from agents.base_agent import MONERO_P2P_PORT, MONERO_RPC_PORT
from agents.agent_discovery import AgentDiscovery
from agents.eclipse_injector import InjectorConfig, serve_ports

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


def ip_from_le_u32(v):
    """get_peer_list returns each ip as a little-endian uint32; render dotted."""
    if isinstance(v, str):
        return v
    v = int(v)
    return ".".join(str((v >> (8 * i)) & 0xFF) for i in range(4))


def refresh_once(ip, port, ident, timeout):
    """One re-handshake advertising the current front port. The white-list
    insert is done by the target's asynchronous ping-back to (our ip,
    ident['my_port']); this returns once the handshake exchange is complete."""
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
        "OQ13 active-recency spy refresher (rotating front ports: every honest "
        "node holds a always-fresh white entry for this spy's host)")
    parser.add_argument("--refresh_interval", "--refresh-interval",
                        dest="refresh_interval", type=int, default=0,
                        help="sim-seconds between full sweeps (0 = use the "
                             "refresh_interval attribute, else 300)")
    parser.add_argument("--dial_timeout", "--dial-timeout", dest="dial_timeout",
                        type=float, default=6.0,
                        help="per-dial connect/IO timeout in sim-seconds")
    parser.add_argument("--front_port_base", "--front-port-base",
                        dest="front_port_base", type=int, default=18090,
                        help="first front port (the daemon's p2p is 18080)")
    parser.add_argument("--front_port_count", "--front-port-count",
                        dest="front_port_count", type=int, default=64,
                        help="how many front ports; one is advertised per "
                             "rotation window, all stay listable")
    parser.add_argument("--rotate_period", "--rotate-period",
                        dest="rotate_period", type=int, default=1800,
                        help="sim-seconds a front port is the advertised one "
                             "before rotating to the next")
    args, _unknown = parser.parse_known_args()

    class SpyRefreshAgent(BaseAgent):
        def _setup_agent(self):
            a = getattr(self, "attributes", {}) or {}
            self._interval = float(args.refresh_interval or a.get("refresh_interval") or 300)
            self._ports = list(range(args.front_port_base,
                                     args.front_port_base + max(1, args.front_port_count)))
            self._rotate = max(1, int(args.rotate_period or a.get("rotate_period") or 1800))
            self._daemon_ip = (self.rpc_host
                               if self.rpc_host not in (None, "", "127.0.0.1")
                               else _local_ip())
            self._rpc_port = self.daemon_rpc_port or MONERO_RPC_PORT
            self._discovery = AgentDiscovery(str(self.shared_dir) if self.shared_dir else None)
            self._stop = threading.Event()
            # Last-good chain state; height 1 / genesis top_id is a valid
            # behind-peer handshake if the daemon RPC is briefly unreachable.
            self._chain = {"height": 1, "cumdiff": 1,
                           "top_id": b"\x00" * 32, "top_version": 1}
            self._daemon_peers = []  # [(ip, port)] served back to dialers
            # The front-end responder: the daemon's identity, live chain state,
            # and its own white list as the served peer list. peer_id is filled
            # in on the first identity fetch; nothing dials us before our first
            # sweep has inserted entries.
            self._cfg = InjectorConfig(
                network_id=L.NETWORK_ID_MAINNET,
                peer_id=0,
                my_port=self._ports[0],
                records_fn=self._records,
                logger=self.logger,
            )
            threading.Thread(target=serve_ports,
                             args=("0.0.0.0", self._ports, self._cfg, self._stop),
                             daemon=True).start()
            sim_seed = os.environ.get("SIMULATION_SEED")
            if sim_seed:
                random.seed(f"{sim_seed}:{self.agent_id}")
            self.logger.info(
                "SpyRefreshAgent up: daemon %s:%d, front ports %d..%d, sweep "
                "every %.0fs, rotate every %ds",
                self._daemon_ip, self._rpc_port, self._ports[0], self._ports[-1],
                self._interval, self._rotate)

        def _current_port(self):
            """The port advertised this rotation window (sim time; the sweep
            re-advertises it so nodes that missed it still insert it)."""
            return self._ports[int(time.time() // self._rotate) % len(self._ports)]

        def _fetch_peer_id(self):
            """Our daemon's real peer id, from its own HANDSHAKE response.
            We advertise my_port 0 so the daemon ping-backs nothing and writes
            no entry for us."""
            s = L.connect(self._daemon_ip, MONERO_P2P_PORT, timeout=args.dial_timeout)
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
                self._cfg.height = self._chain["height"]
                self._cfg.cumdiff = self._chain["cumdiff"]
                self._cfg.top_id = self._chain["top_id"]
                self._cfg.top_version = self._chain["top_version"]
                try:
                    pl = _rpc(self._daemon_ip, self._rpc_port, "get_peer_list")
                    white = pl.get("white_list", []) if isinstance(pl, dict) else []
                    self._daemon_peers = [
                        (ip_from_le_u32(e.get("ip")), e.get("port", MONERO_P2P_PORT))
                        for e in white if e.get("ip")]
                except Exception:  # noqa: BLE001 - served records are best-effort
                    pass
            except Exception as e:  # noqa: BLE001 - a stale cache is a valid behind-peer
                self.logger.debug("chain poll failed (%s); keeping last state", e)

        def _records(self):
            return self._daemon_peers

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
            port = self._current_port()
            self._cfg.peer_id = peer_id
            self._cfg.my_port = port
            ident = dict(self._chain, peer_id=peer_id, my_port=port)

            targets = self._targets()
            ok = fail = 0
            # Leave headroom inside the interval; a sweep that would overrun
            # (many targets still starting, long timeouts) resumes next cycle.
            deadline = time.monotonic() + self._interval * 0.8
            for ip, tport in targets:
                if not self.running or time.monotonic() > deadline:
                    break
                try:
                    refresh_once(ip, tport, ident, args.dial_timeout)
                    ok += 1
                except Exception as e:  # noqa: BLE001 - one dead target must not kill the sweep
                    fail += 1
                    self.logger.debug("dial %s:%d failed: %s", ip, tport, e)
            self.logger.info(
                "spy_refresh: %d/%d honest nodes swept on front port %d as peer %x @ h=%d "
                "(ok=%d fail=%d%s)",
                ok, len(targets), port, peer_id, self._chain["height"], ok, fail,
                "" if ok + fail == len(targets)
                else f", {len(targets) - ok - fail} deferred to next sweep")
            return self._interval

        def _cleanup_agent(self):
            self._stop.set()

    agent = SpyRefreshAgent(
        agent_id=args.id, shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port, wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port, rpc_host=args.rpc_host, log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
