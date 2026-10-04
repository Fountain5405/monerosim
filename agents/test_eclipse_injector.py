"""Tests for the eclipse Levin responder (agents.eclipse_injector) and
levin_lib.pop_bucket.

serve_ports replaced a thread-per-connection server: under Shadow every
thread also costs Shadow-side state, and a dialing fake-peer fleet pushes tens
of thousands of connections through each process (the 20260928 eclipse OOM).
These tests pin the wire behaviour (same replies as before) and that
connections no longer cost threads.
"""
import socket
import struct
import threading
import time

import pytest

from agents import eclipse_injector as EI
from agents import levin_lib as L

RECORDS = [("10.0.%d.%d" % (i // 250, i % 250 + 1), 18080 + i % 5) for i in range(600)]


# ---- pop_bucket ------------------------------------------------------------
def _bucket(command, payload=b"", flags=L.LEVIN_PACKET_REQUEST, expect=True):
    return L.pack_header(command, len(payload), flags, expect_response=expect) + payload


def test_pop_bucket_waits_for_complete_header_and_payload():
    whole = _bucket(L.COMMAND_PING, b"xyz")
    buf = bytearray()
    for i in range(len(whole) - 1):
        buf = bytearray(whole[:i])
        assert L.pop_bucket(buf) is None and len(buf) == i
    buf = bytearray(whole + _bucket(L.COMMAND_TIMED_SYNC))
    command, flags, _rc, expect, payload = L.pop_bucket(buf)
    assert (command, flags, expect, payload) == (L.COMMAND_PING, L.LEVIN_PACKET_REQUEST, True, b"xyz")
    assert L.pop_bucket(buf)[0] == L.COMMAND_TIMED_SYNC
    assert buf == bytearray()


def test_pop_bucket_rejects_bad_signature_and_oversize():
    bad = bytearray(_bucket(L.COMMAND_PING))
    bad[0] ^= 0xFF
    with pytest.raises(ValueError):
        L.pop_bucket(bad)
    big = bytearray(L.pack_header(L.COMMAND_PING, L.LEVIN_DEFAULT_MAX_PACKET_SIZE + 1,
                                  L.LEVIN_PACKET_REQUEST))
    with pytest.raises(ValueError):
        L.pop_bucket(big)


# ---- serve_ports -----------------------------------------------------------
def _free_ports(n):
    socks = [socket.socket() for _ in range(n)]
    for s in socks:
        s.bind(("127.0.0.1", 0))
    ports = [s.getsockname()[1] for s in socks]
    for s in socks:
        s.close()
    return ports


@pytest.fixture
def server():
    records = list(RECORDS)
    cfg = EI.InjectorConfig(network_id=L.NETWORK_ID_MAINNET, peer_id=0xDEADBEEF,
                            my_port=18080, records_fn=lambda: records, max_records=250)
    ports = _free_ports(2)
    stop = threading.Event()
    t = threading.Thread(target=EI.serve_ports, args=("127.0.0.1", ports, cfg, stop),
                         kwargs={"idle_timeout": 1.0}, daemon=True)
    t.start()
    time.sleep(0.2)
    yield cfg, ports, records, stop
    stop.set()
    t.join(timeout=5)
    assert not t.is_alive()


def _request(sock, command, section=None, expect=True):
    payload = L.serialize(section or {})
    sock.sendall(L.pack_header(command, len(payload), L.LEVIN_PACKET_REQUEST,
                               expect_response=expect) + payload)


def _reply(sock):
    command, flags, rc, _expect, payload = L.read_bucket(sock)
    assert flags == L.LEVIN_PACKET_RESPONSE and rc == 1
    return command, L.parse(payload)


def test_handshake_timed_sync_ping_and_support_flags(server):
    cfg, ports, records, _stop = server
    s = L.connect("127.0.0.1", ports[0], timeout=5)
    _request(s, L.COMMAND_HANDSHAKE)
    command, body = _reply(s)
    assert command == L.COMMAND_HANDSHAKE
    assert set(body) == {"node_data", "payload_data", "local_peerlist_new"}
    assert len(body["local_peerlist_new"]) == 250
    _request(s, L.COMMAND_TIMED_SYNC)
    command, body = _reply(s)
    assert command == L.COMMAND_TIMED_SYNC and set(body) == {"payload_data", "local_peerlist_new"}
    _request(s, L.COMMAND_PING)
    command, body = _reply(s)
    assert command == L.COMMAND_PING and body["status"] == L.PING_OK_RESPONSE_STATUS_TEXT
    _request(s, L.COMMAND_REQUEST_SUPPORT_FLAGS)
    command, body = _reply(s)
    assert command == L.COMMAND_REQUEST_SUPPORT_FLAGS and body["support_flags"] == 1
    s.close()
    assert cfg.injected == 500
    assert records == RECORDS  # sampling must not reorder a shared records list


def test_notifications_are_ignored_and_connection_stays_up(server):
    _cfg, ports, _records, _stop = server
    s = L.connect("127.0.0.1", ports[1], timeout=5)
    s.sendall(_bucket(2002, b"\x00" * 100, flags=L.LEVIN_PACKET_REQUEST & 0, expect=False))
    _request(s, L.COMMAND_PING)
    assert _reply(s)[0] == L.COMMAND_PING  # first reply is the ping's, not the notify's
    s.close()


def test_many_connections_cost_no_threads(server):
    cfg, ports, _records, _stop = server
    threads_before = threading.active_count()
    socks = [L.connect("127.0.0.1", ports[i % 2], timeout=5) for i in range(60)]
    for s in socks:
        _request(s, L.COMMAND_HANDSHAKE)
    for s in socks:
        assert _reply(s)[0] == L.COMMAND_HANDSHAKE
    assert threading.active_count() == threads_before
    assert cfg.live == 60 and cfg.conns == 60
    for s in socks:
        s.close()
    deadline = time.time() + 3
    while cfg.live and time.time() < deadline:
        time.sleep(0.05)
    assert cfg.live == 0


def test_idle_connections_are_closed(server):
    cfg, ports, _records, _stop = server
    s = L.connect("127.0.0.1", ports[0], timeout=5)
    time.sleep(2.5)  # idle_timeout=1.0 in the fixture, sweep once a second
    assert s.recv(1) == b""
    assert cfg.live == 0
    s.close()


def test_bad_framing_closes_only_that_connection(server):
    cfg, ports, _records, _stop = server
    good = L.connect("127.0.0.1", ports[0], timeout=5)
    bad = L.connect("127.0.0.1", ports[0], timeout=5)
    bad.sendall(b"\x00" * L.HEADER_SIZE)
    assert bad.recv(1) == b""
    _request(good, L.COMMAND_PING)
    assert _reply(good)[0] == L.COMMAND_PING
    good.close()
    bad.close()


def test_handle_connection_sends_same_replies(server):
    """The blocking single-connection path shares _response with serve_ports."""
    cfg, _ports, _records, _stop = server
    a, b = socket.socketpair()
    t = threading.Thread(target=EI.handle_connection, args=(b, cfg), daemon=True)
    t.start()
    _request(a, L.COMMAND_PING)
    command, body = _reply(a)
    assert command == L.COMMAND_PING and body["peer_id"] == 0xDEADBEEF
    a.close()
    t.join(timeout=5)


# ---- RegistryCache ---------------------------------------------------------
class _FakeDiscovery:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def get_agent_registry(self, force_refresh=False):
        self.calls += 1
        time.sleep(0.01)
        if self.fail:
            raise OSError("registry unreadable")
        return {"agents": {"a": {"id": "relay-1", "ip_addr": "1.2.3.4"}}}


def test_registry_cache_parses_once_per_ttl_even_under_concurrency():
    disc = _FakeDiscovery()
    cache = EI.RegistryCache(disc, ttl=60)
    out = []
    threads = [threading.Thread(target=lambda: out.append(cache.agents())) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert disc.calls == 1
    assert all(o == [{"id": "relay-1", "ip_addr": "1.2.3.4"}] for o in out)


def test_registry_cache_refreshes_after_ttl_and_keeps_last_good():
    disc = _FakeDiscovery()
    cache = EI.RegistryCache(disc, ttl=0.05)
    first = cache.agents()
    time.sleep(0.1)
    disc.fail = True
    assert cache.agents() == first  # failed refresh keeps the snapshot
    assert disc.calls == 2
    assert EI.RegistryCache(disc, ttl=60).agents() == []  # never loaded -> empty
