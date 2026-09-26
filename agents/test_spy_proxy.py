"""Tests for the proxy-spy front-end helpers and the shared Levin responder's
fingerprint knobs (ping-id mismatch, support-flags). Localhost sockets only; no
Shadow, no real network."""
import socket
import threading
import time

import pytest

from agents import levin_lib as L
from agents.eclipse_injector import InjectorConfig, serve_forever
from agents.spy_proxy import ip_from_le_u32, mix_records


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _serve(cfg):
    port = _free_port()
    stop = threading.Event()
    t = threading.Thread(target=serve_forever,
                         args=("127.0.0.1", port, cfg, stop), daemon=True)
    t.start()
    time.sleep(0.2)
    return port, stop


def _handshake_and_ping(port, height=12345):
    s = L.connect("127.0.0.1", port, timeout=5)
    req = L.serialize(L.handshake_request(
        L.NETWORK_ID_MAINNET, port, 0, height, 1, b"\x00" * 32, 1))
    s.sendall(L.pack_header(L.COMMAND_HANDSHAKE, len(req),
                            L.LEVIN_PACKET_REQUEST, expect_response=True))
    s.sendall(req)
    _, _, _, _, hs_payload = L.read_bucket(s)
    hs = L.parse(hs_payload)
    ping_payload = L.serialize(L.ping_request())
    s.sendall(L.pack_header(L.COMMAND_PING, len(ping_payload),
                            L.LEVIN_PACKET_REQUEST, expect_response=True))
    s.sendall(ping_payload)
    _, _, _, _, pong = L.read_bucket(s)
    ping = L.parse(pong)
    s.close()
    return hs, ping


def _cfg(**kw):
    return InjectorConfig(network_id=L.NETWORK_ID_MAINNET, peer_id=0xAAAA,
                          my_port=18080, records_fn=lambda: [], **kw)


# ---- responder fingerprints (the mechanism variant P adds) ----

def test_ping_id_mismatch_is_reported_when_set():
    cfg = _cfg(ping_peer_id=0xBBBB, height=999)
    port, stop = _serve(cfg)
    try:
        hs, ping = _handshake_and_ping(port)
        assert hs["node_data"]["peer_id"] == 0xAAAA          # handshake id
        assert ping["peer_id"] == 0xBBBB                      # different ping id
        assert hs["node_data"]["peer_id"] != ping["peer_id"]  # the fingerprint
    finally:
        stop.set()


def test_ping_id_matches_handshake_by_default():
    # eclipse behaviour is unchanged: no ping_peer_id -> ping id == handshake id.
    cfg = _cfg(height=999)
    port, stop = _serve(cfg)
    try:
        hs, ping = _handshake_and_ping(port)
        assert hs["node_data"]["peer_id"] == ping["peer_id"] == 0xAAAA
    finally:
        stop.set()


def test_backend_chain_height_is_reported():
    cfg = _cfg(height=3768893, cumdiff=42)
    port, stop = _serve(cfg)
    try:
        hs, _ = _handshake_and_ping(port)
        assert hs["payload_data"]["current_height"] == 3768893
    finally:
        stop.set()


# ---- pure helpers ----

def test_ip_from_le_u32_matches_get_peer_list_encoding():
    # 3.0.0.11 little-endian uint32 = 11<<24 | 0 | 0 | 3
    assert ip_from_le_u32(3) == "3.0.0.0"
    assert ip_from_le_u32((11 << 24) | 3) == "3.0.0.11"
    assert ip_from_le_u32("3.0.0.11") == "3.0.0.11"  # already dotted


def test_mix_records_respects_fleet_share_and_cap():
    fleet = [("200.2.0.%d" % i, 18080) for i in range(200)]
    honest = [("3.0.0.%d" % i, 18080) for i in range(200)]
    recs = mix_records(fleet, honest, n=100, fleet_share=0.5)
    assert len(recs) == 100
    n_fleet = sum(1 for ip, _ in recs if ip.startswith("200.2.0."))
    assert n_fleet == 50  # 0.5 * 100

    all_fleet = mix_records(fleet, honest, n=100, fleet_share=1.0)
    assert all(ip.startswith("200.2.0.") for ip, _ in all_fleet)

    all_honest = mix_records(fleet, honest, n=100, fleet_share=0.0)
    assert all(ip.startswith("3.0.0.") for ip, _ in all_honest)


def test_mix_records_handles_short_lists():
    recs = mix_records([("1.1.1.1", 18080)], [], n=100, fleet_share=0.5)
    assert recs == [("1.1.1.1", 18080)]
    assert mix_records([], [], n=100, fleet_share=0.5) == []
