"""Tests for scripts/chain_snapshot.py.

The daemon-driving tests (export / build-template against a real
monerod-sim) are skipped unless ~/.monerosim/bin/monerod-sim exists.
"""
import gzip
import json
import subprocess
from pathlib import Path

import pytest

from scripts.chain_snapshot import (
    DEFAULT_BINARY,
    SHADOW_EPOCH,
    ChainSnapshotError,
    cmd_build_template,
    cmd_export,
    load_blocks,
    load_manifest,
    manifest_key,
    verify_manifest,
)

MONEROD_SIM = Path(DEFAULT_BINARY)


def _manifest(**overrides):
    base = {
        "height": 10,
        "D0": 6000,
        "total_hashrate": 50,
        "monero_pin": "v0.18.5.1",
        "hf_schedule": None,
        "network_id": "regtest-fakechain",
        "genesis_hash": "a" * 64,
        "tip_timestamp": SHADOW_EPOCH - 600,
        "tip_hash": "b" * 64,
        "generated_by_run": "test-run",
        "created_at": "2026-09-23T00:00:00Z",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# manifest key derivation
# --------------------------------------------------------------------------

def test_manifest_key_deterministic():
    m1 = _manifest()
    m2 = _manifest()
    assert manifest_key(m1) == manifest_key(m2)


def test_manifest_key_changes_with_inputs():
    base_key = manifest_key(_manifest())
    assert manifest_key(_manifest(D0=7000)) != base_key
    assert manifest_key(_manifest(monero_pin="v0.18.6.0")) != base_key
    assert manifest_key(_manifest(hf_schedule="1:0,14:1")) != base_key
    assert manifest_key(_manifest(network_id="mainnet")) != base_key
    assert manifest_key(_manifest(height=11)) != base_key


def test_manifest_key_null_and_empty_hf_schedule_equal():
    # hf_schedule=None and hf_schedule="" must hash the same (both mean "no
    # schedule"): the key derivation coerces None -> "".
    assert manifest_key(_manifest(hf_schedule=None)) == manifest_key(_manifest(hf_schedule=""))


def test_manifest_key_is_short_hex():
    key = manifest_key(_manifest())
    assert len(key) == 16
    int(key, 16)  # raises if not hex


# --------------------------------------------------------------------------
# JSONL round trip
# --------------------------------------------------------------------------

def test_blocks_jsonl_round_trip(tmp_path):
    preset_dir = tmp_path / "preset"
    preset_dir.mkdir()
    blocks = [
        {"height": 2, "hash": "h2", "blob": "b2"},
        {"height": 1, "hash": "h1", "blob": "b1"},
        {"height": 3, "hash": "h3", "blob": "b3"},
    ]
    with gzip.open(preset_dir / "blocks.jsonl.gz", "wt", encoding="utf-8") as gz:
        for b in blocks:
            gz.write(json.dumps(b) + "\n")

    loaded = load_blocks(preset_dir)
    assert [b["height"] for b in loaded] == [1, 2, 3]
    assert loaded[0] == {"height": 1, "hash": "h1", "blob": "b1"}


def test_load_blocks_missing_file(tmp_path):
    with pytest.raises(ChainSnapshotError):
        load_blocks(tmp_path)


def test_load_manifest_round_trip(tmp_path):
    manifest = _manifest()
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)
    assert load_manifest(tmp_path) == manifest


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(ChainSnapshotError):
        load_manifest(tmp_path)


# --------------------------------------------------------------------------
# verify()
# --------------------------------------------------------------------------

def test_verify_pass():
    failures = verify_manifest(_manifest(), expected_monero_pin="v0.18.5.1")
    assert failures == []


def test_verify_missing_key():
    m = _manifest()
    del m["tip_hash"]
    failures = verify_manifest(m, expected_monero_pin="v0.18.5.1")
    assert any("tip_hash" in f for f in failures)


def test_verify_pin_mismatch():
    failures = verify_manifest(_manifest(monero_pin="v0.18.0.0"), expected_monero_pin="v0.18.5.1")
    assert any("monero_pin mismatch" in f for f in failures)


def test_verify_tip_in_future():
    failures = verify_manifest(_manifest(tip_timestamp=SHADOW_EPOCH + 10), expected_monero_pin="v0.18.5.1")
    assert any("not before the Shadow epoch" in f for f in failures)


def test_verify_tip_at_epoch_fails():
    # tip_timestamp == epoch is not strictly before it.
    failures = verify_manifest(_manifest(tip_timestamp=SHADOW_EPOCH), expected_monero_pin="v0.18.5.1")
    assert any("not before the Shadow epoch" in f for f in failures)


def test_verify_tip_too_old():
    failures = verify_manifest(_manifest(tip_timestamp=SHADOW_EPOCH - 3600), expected_monero_pin="v0.18.5.1")
    assert any("max gap" in f for f in failures)


def test_verify_tip_gap_at_boundary_passes():
    failures = verify_manifest(_manifest(tip_timestamp=SHADOW_EPOCH - 1800), expected_monero_pin="v0.18.5.1")
    assert failures == []


def test_verify_no_pin_check_when_expected_is_none():
    failures = verify_manifest(_manifest(monero_pin="anything"), expected_monero_pin=None)
    assert failures == []


# --------------------------------------------------------------------------
# integration: real daemon (skipped unless monerod-sim is installed)
# --------------------------------------------------------------------------

requires_monerod_sim = pytest.mark.skipif(
    not MONEROD_SIM.exists(), reason="~/.monerosim/bin/monerod-sim not installed"
)


@requires_monerod_sim
def test_export_and_build_template_round_trip(tmp_path):
    import argparse

    # 1. Mine a tiny real chain natively (generateblocks; no throttling).
    gen_data_dir = tmp_path / "gen_data"
    gen_data_dir.mkdir()
    rpc_port = _free_port_for_test()
    p2p_port = _free_port_for_test()
    log_path = tmp_path / "gen_monerod.log"
    proc = subprocess.Popen(
        [
            str(MONEROD_SIM),
            "--regtest", "--keep-fakechain", "--offline",
            "--data-dir", str(gen_data_dir),
            "--rpc-bind-port", str(rpc_port),
            "--p2p-bind-port", str(p2p_port),
            "--no-igd", "--non-interactive",
            "--log-level", "0", "--log-file", str(log_path),
            # Fixed difficulty keeps this tiny fixture chain's generation fast
            # and bounded: unthrottled generateblocks mines faster than the
            # 120s target, and the real DAA would escalate difficulty block
            # over block. build-template below replays under the same fixed
            # difficulty for the same reason (see its --fixed-difficulty).
            "--fixed-difficulty", "1",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        _wait_rpc_for_test(rpc_port, proc)
        addr = _regtest_address_for_test()
        import requests
        r = requests.post(
            f"http://127.0.0.1:{rpc_port}/json_rpc",
            json={
                "jsonrpc": "2.0", "id": "0", "method": "generateblocks",
                "params": {"amount_of_blocks": 5, "wallet_address": addr, "starting_nonce": 0},
            },
            timeout=30,
        )
        r.raise_for_status()
        assert "error" not in r.json(), r.json()
    finally:
        proc.terminate()
        proc.wait(timeout=30)

    # 2. export
    preset_dir = tmp_path / "preset"
    export_args = argparse.Namespace(
        data_dir=str(gen_data_dir),
        out=str(preset_dir),
        total_hashrate=50,
        d0=6000,
        generated_by="pytest",
        hf_schedule=None,
        binary=str(MONEROD_SIM),
    )
    assert cmd_export(export_args) == 0

    manifest = load_manifest(preset_dir)
    assert manifest["height"] == 5
    blocks = load_blocks(preset_dir)
    assert [b["height"] for b in blocks] == [1, 2, 3, 4, 5]

    # 3. build-template into a temp cache root
    cache_root = tmp_path / "cache"
    build_args = argparse.Namespace(
        preset=str(preset_dir),
        cache_root=str(cache_root),
        binary=str(MONEROD_SIM),
        fixed_difficulty=1,
    )
    assert cmd_build_template(build_args) == 0

    key = manifest_key(manifest)
    cache_dir = cache_root / key
    assert cache_dir.is_dir()
    assert (cache_dir / "manifest.json").is_file()

    # 4. no-op on second call (cache hit)
    assert cmd_build_template(build_args) == 0


def _free_port_for_test():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_rpc_for_test(port, proc, timeout=60):
    import time
    import requests
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"monerod-sim exited early (code {proc.returncode})")
        try:
            resp = requests.post(
                f"http://127.0.0.1:{port}/json_rpc",
                json={"jsonrpc": "2.0", "id": "0", "method": "get_info"},
                timeout=5,
            )
            resp.raise_for_status()
            return
        except requests.RequestException:
            time.sleep(0.5)
    raise RuntimeError("monerod-sim RPC never became ready")


def _regtest_address_for_test():
    """A syntactically valid Monero primary address, accepted by regtest's
    generateblocks (which only validates the address format, not the net)."""
    return "4BDdEeZ2ZqB3hZx82JpgCHJqdgJxiXiTo39NYCsEdpsEAURVPq4jD3L1mDdYYtcRUaeoH2ussqDb5ZvC77uaJX5gRTdWkap"
