"""Tests for analysis/spy/txrelay_check.py on a hand-built 3-node run.

Run: python3 -m pytest analysis/spy/test_txrelay_check.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import txrelay_check  # noqa: E402

IPS = {"user-001": "10.0.0.1", "relay-001": "10.0.0.2", "relay-002": "10.0.0.3"}


def peer(node):
    return {"conn": "c-" + node, "addr": IPS[node] + ":18080"}


def write_run(tmp_path, logs, txs):
    for node, events in logs.items():
        d = tmp_path / "daemon_logs" / ("monero-" + node)
        d.mkdir(parents=True)
        (d / "txrelay.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    reg = tmp_path / "transaction_registry"
    reg.mkdir()
    agents = [{"id": n, "ip_addr": ip} for n, ip in IPS.items()]
    (reg / "agent_registry.json").write_text(json.dumps({"agents": agents}))
    (reg / "transactions.json").write_text(json.dumps(txs))
    return tmp_path


def test_two_hop_stem_ending_in_embargo(tmp_path):
    logs = {
        "user-001": [
            {"t": 1, "ev": "epoch", "fluff": False, "stems": [peer("relay-001")]},
            {"t": 10, "ev": "send", "txs": ["aa"], "method": "local", "src": "self"},
            {"t": 11, "ev": "stem", "txs": ["aa"], "method": "local", "to": peer("relay-001")},
        ],
        "relay-001": [
            {"t": 2, "ev": "epoch", "fluff": False, "stems": [peer("relay-002")]},
            {"t": 12, "ev": "rx", "tx": "aa", "conn": "x", "addr": "10.0.0.1:5000", "dir": "in", "fluff": False, "result": "stem"},
            {"t": 13, "ev": "stem", "txs": ["aa"], "method": "stem", "to": peer("relay-002")},
        ],
        "relay-002": [
            {"t": 3, "ev": "epoch", "fluff": True, "stems": []},
            {"t": 14, "ev": "rx", "tx": "aa", "conn": "y", "addr": "10.0.0.2:6000", "dir": "in", "fluff": False, "result": "stem"},
            {"t": 60, "ev": "pool_relay", "tx": "aa", "was": "stem"},
        ],
    }
    run = write_run(tmp_path, logs, [{"tx_hashes": ["aa"], "sender_id": "user-001"}])
    r = txrelay_check.check(run)
    assert r["logs"] == 3
    assert r["origin_found"] == 1 and r["origin_matches_sender"] == 1
    assert r["stem_hops_hist"] == {2: 1}
    assert r["stem_end"] == {"embargo": 1}
    assert r["stem_hops_without_rx"] == 0
    assert r["epochs"] == 3 and r["fluff_epoch_share"] == 0.333


def test_fluff_epoch_at_first_relay_and_missing_rx(tmp_path):
    logs = {
        "user-001": [
            {"t": 10, "ev": "send", "txs": ["bb"], "method": "local", "src": "self"},
            {"t": 11, "ev": "stem", "txs": ["bb"], "method": "local", "to": peer("relay-001")},
        ],
        "relay-001": [
            {"t": 13, "ev": "fluff", "txs": ["bb"], "method": "stem", "reason": "epoch"},
        ],
    }
    run = write_run(tmp_path, logs, [{"tx_hashes": ["bb"], "sender_id": "relay-002"}])
    r = txrelay_check.check(run)
    assert r["origin_matches_sender"] == 0
    assert r["stem_hops_hist"] == {1: 1}
    assert r["stem_end"] == {"epoch": 1}
    assert r["stem_hops_without_rx"] == 1


def test_loop_and_unlogged_node(tmp_path):
    logs = {
        "user-001": [
            {"t": 10, "ev": "send", "txs": ["cc", "dd"], "method": "local", "src": "self"},
            {"t": 11, "ev": "stem", "txs": ["cc"], "method": "local", "to": peer("relay-001")},
            {"t": 11, "ev": "stem", "txs": ["dd"], "method": "local", "to": peer("relay-002")},
            {"t": 13, "ev": "rx", "tx": "cc", "conn": "z", "addr": "10.0.0.2:7000", "dir": "in", "fluff": False, "result": "fluff"},
        ],
        "relay-001": [
            {"t": 12, "ev": "rx", "tx": "cc", "conn": "x", "addr": "10.0.0.1:5000", "dir": "in", "fluff": False, "result": "stem"},
            {"t": 12, "ev": "stem", "txs": ["cc"], "method": "stem", "to": peer("user-001")},
        ],
    }
    txs = [{"tx_hashes": ["cc"], "sender_id": "user-001"}, {"tx_hashes": ["dd"], "sender_id": "user-001"}]
    r = txrelay_check.check(write_run(tmp_path, logs, txs))
    assert r["stem_end"] == {"loop": 1, "unlogged_node": 1}
    assert r["stem_hops_without_rx"] == 0
