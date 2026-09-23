#!/usr/bin/env python3
"""chain_snapshot.py - generate, cache and verify native-mining chain snapshots.

See docs/CHAIN_SNAPSHOT.md and
docs/superpowers/specs/2026-09-23-difficulty-preload-design.md Sec 5 "A: chain
snapshot" for the design this implements.

Three subcommands:

  export         Drive an offline monerod-sim over a generator run's data dir
                 and dump every block from height 1..tip into a git-trackable
                 preset (blocks.jsonl.gz + manifest.json).

  build-template Materialize a preset into a real LMDB data dir once per
                 machine, cached under ~/.monerosim/chain_snapshots/<key>/, by
                 replaying its blocks through a fresh offline monerod-sim's
                 submit_block RPC (real PoW re-verification).

  verify         Check a preset's manifest against schema + monero.pin +
                 the "tip lands just before the Shadow epoch" timestamp rule.

Deviation from the design doc: blocks are gzip-compressed (blocks.jsonl.gz),
not zstd, to avoid adding a new Python dependency.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_ROOT = Path.home() / ".monerosim" / "chain_snapshots"
DEFAULT_BINARY = Path.home() / ".monerosim" / "bin" / "monerod-sim"
NETWORK_ID = "regtest-fakechain"
# Shadow's simulated clock starts at 2000-01-01 00:00 UTC.
SHADOW_EPOCH = 946684800
MAX_TIP_GAP_SECONDS = 1800  # 30 minutes; see design doc Sec 5 "Gap check".
RPC_READY_TIMEOUT_S = 60
RPC_TIMEOUT_S = 30
DAEMON_STOP_TIMEOUT_S = 30


class ChainSnapshotError(Exception):
    """Raised for any export/build-template/verify failure."""


# --------------------------------------------------------------------------
# small RPC + process helpers
# --------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _rpc_call(port: int, method: str, params: Any = None, timeout: int = RPC_TIMEOUT_S) -> Any:
    payload: dict = {"jsonrpc": "2.0", "id": "0", "method": method}
    if params is not None:
        payload["params"] = params
    resp = requests.post(
        f"http://127.0.0.1:{port}/json_rpc",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise ChainSnapshotError(f"RPC {method} failed: {body['error']}")
    return body["result"]


def _wait_for_rpc(port: int, proc: subprocess.Popen, timeout: int = RPC_READY_TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout
    last_err: Optional[Exception] = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise ChainSnapshotError(
                f"monerod-sim exited early (code {proc.returncode}) while waiting for RPC"
            )
        try:
            _rpc_call(port, "get_info", timeout=5)
            return
        except (requests.RequestException, ChainSnapshotError) as e:
            last_err = e
            time.sleep(0.5)
    raise ChainSnapshotError(f"monerod-sim RPC never became ready on port {port}: {last_err}")


def _start_daemon(
    binary: Path,
    data_dir: Path,
    rpc_port: int,
    p2p_port: int,
    log_path: Path,
    extra_args: Optional[list] = None,
) -> subprocess.Popen:
    data_dir.mkdir(parents=True, exist_ok=True)
    args = [
        str(binary),
        "--regtest",
        "--keep-fakechain",
        "--offline",
        "--data-dir", str(data_dir),
        "--rpc-bind-port", str(rpc_port),
        "--p2p-bind-port", str(p2p_port),
        "--no-igd",
        "--non-interactive",
        "--log-level", "0",
        "--log-file", str(log_path),
    ]
    if extra_args:
        args.extend(extra_args)
    with open(log_path, "ab") as logf:
        proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    return proc


def _stop_daemon(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=DAEMON_STOP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _copy_sparse(src: Path, dst: Path) -> None:
    """Copy a directory tree, preserving LMDB sparse holes. dst must not exist."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "--sparse=always", "-r", str(src), str(dst)], check=True)


def _read_monero_pin() -> str:
    return (REPO_ROOT / "monero.pin").read_text().strip()


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

def cmd_export(args: argparse.Namespace) -> int:
    src_data_dir = Path(args.data_dir).resolve()
    if not src_data_dir.is_dir():
        raise ChainSnapshotError(f"--data-dir not found: {src_data_dir}")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="chain_snapshot_export_") as tmp:
        tmp_path = Path(tmp)
        work_data_dir = tmp_path / "data"
        # Never mutate the input: work on a copy.
        _copy_sparse(src_data_dir, work_data_dir)

        rpc_port = _free_port()
        p2p_port = _free_port()
        log_path = tmp_path / "monerod.log"
        proc = _start_daemon(Path(args.binary), work_data_dir, rpc_port, p2p_port, log_path)
        try:
            _wait_for_rpc(rpc_port, proc)

            count = _rpc_call(rpc_port, "get_block_count")["count"]
            tip_height = count - 1
            if tip_height < 1:
                raise ChainSnapshotError(f"chain at {src_data_dir} has no mined blocks (height {tip_height})")

            genesis = _rpc_call(rpc_port, "get_block", {"height": 0})
            genesis_hash = genesis["block_header"]["hash"]

            blocks_path = out_dir / "blocks.jsonl.gz"
            tip_hash = None
            tip_timestamp = None
            with gzip.open(blocks_path, "wt", encoding="utf-8") as gz:
                for height in range(1, tip_height + 1):
                    blk = _rpc_call(rpc_port, "get_block", {"height": height})
                    header = blk["block_header"]
                    gz.write(json.dumps({
                        "height": height,
                        "hash": header["hash"],
                        "blob": blk["blob"],
                    }) + "\n")
                    tip_hash = header["hash"]
                    tip_timestamp = header["timestamp"]
        finally:
            _stop_daemon(proc)

    manifest = {
        "height": tip_height,
        "D0": args.d0,
        "total_hashrate": args.total_hashrate,
        "monero_pin": _read_monero_pin(),
        "hf_schedule": args.hf_schedule,
        "network_id": NETWORK_ID,
        "genesis_hash": genesis_hash,
        "tip_timestamp": tip_timestamp,
        "tip_hash": tip_hash,
        "generated_by_run": args.generated_by,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(out_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Exported {tip_height} blocks to {out_dir}")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


# --------------------------------------------------------------------------
# build-template
# --------------------------------------------------------------------------

def manifest_key(manifest: dict) -> str:
    """Deterministic cache key: sha256(D0, monero_pin, hf_schedule, network_id, height)[:16]."""
    parts = [
        str(manifest["D0"]),
        str(manifest["monero_pin"]),
        str(manifest.get("hf_schedule") or ""),
        str(manifest["network_id"]),
        str(manifest["height"]),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def load_manifest(preset_dir: Path) -> dict:
    manifest_path = preset_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ChainSnapshotError(f"no manifest.json in {preset_dir}")
    with open(manifest_path) as f:
        return json.load(f)


def load_blocks(preset_dir: Path) -> list:
    blocks_path = preset_dir / "blocks.jsonl.gz"
    if not blocks_path.is_file():
        raise ChainSnapshotError(f"no blocks.jsonl.gz in {preset_dir}")
    blocks = []
    with gzip.open(blocks_path, "rt", encoding="utf-8") as gz:
        for line in gz:
            line = line.strip()
            if not line:
                continue
            blocks.append(json.loads(line))
    blocks.sort(key=lambda b: b["height"])
    return blocks


def cmd_build_template(args: argparse.Namespace) -> int:
    preset_dir = Path(args.preset)
    manifest = load_manifest(preset_dir)
    key = manifest_key(manifest)
    cache_root = Path(args.cache_root)
    cache_dir = cache_root / key

    if cache_dir.is_dir() and (cache_dir / "manifest.json").is_file():
        print(f"Cache hit: {cache_dir}")
        return 0

    blocks = load_blocks(preset_dir)
    if len(blocks) != manifest["height"]:
        raise ChainSnapshotError(
            f"manifest height {manifest['height']} does not match {len(blocks)} blocks in blocks.jsonl.gz"
        )

    with tempfile.TemporaryDirectory(prefix="chain_snapshot_build_") as tmp:
        tmp_path = Path(tmp)
        work_data_dir = tmp_path / "data"
        rpc_port = _free_port()
        p2p_port = _free_port()
        log_path = tmp_path / "monerod.log"
        extra_args = None
        if getattr(args, "fixed_difficulty", None):
            # Dev/test convenience only (e.g. tiny fixture presets): the real
            # generation recipe never sets this, since it defeats the DAA the
            # snapshot exists to warm up. Must match whatever regime the
            # preset's blocks were actually mined under, or replay's own
            # difficulty computation (a pure function of the chain's own
            # history) will disagree with the embedded PoW targets.
            extra_args = ["--fixed-difficulty", str(args.fixed_difficulty)]
        proc = _start_daemon(Path(args.binary), work_data_dir, rpc_port, p2p_port, log_path, extra_args)
        try:
            _wait_for_rpc(rpc_port, proc)
            for block in blocks:
                _rpc_call(rpc_port, "submit_block", [block["blob"]])

            count = _rpc_call(rpc_port, "get_block_count")["count"]
            got_height = count - 1
            if got_height != manifest["height"]:
                raise ChainSnapshotError(
                    f"after replay, height {got_height} != manifest height {manifest['height']}"
                )
            last = _rpc_call(rpc_port, "get_last_block_header")["block_header"]
            if last["hash"] != manifest["tip_hash"]:
                raise ChainSnapshotError(
                    f"after replay, tip hash {last['hash']} != manifest tip_hash {manifest['tip_hash']}"
                )
        finally:
            _stop_daemon(proc)

        cache_root.mkdir(parents=True, exist_ok=True)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        shutil.move(str(work_data_dir), str(cache_dir))

    with open(cache_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Built template cache: {cache_dir}")
    return 0


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

REQUIRED_MANIFEST_KEYS = [
    "height", "D0", "total_hashrate", "monero_pin", "hf_schedule",
    "network_id", "genesis_hash", "tip_timestamp", "tip_hash",
    "generated_by_run", "created_at",
]


def verify_manifest(manifest: dict, expected_monero_pin: Optional[str] = None) -> list:
    """Return a list of failure strings; empty list = PASS."""
    failures = []

    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            failures.append(f"manifest missing required key '{key}'")
    if failures:
        # Can't check the rest meaningfully without the base keys.
        return failures

    if expected_monero_pin is not None and manifest["monero_pin"] != expected_monero_pin:
        failures.append(
            f"monero_pin mismatch: manifest has '{manifest['monero_pin']}', repo pin is '{expected_monero_pin}'"
        )

    tip_timestamp = manifest["tip_timestamp"]
    if tip_timestamp >= SHADOW_EPOCH:
        failures.append(
            f"tip_timestamp {tip_timestamp} is not before the Shadow epoch {SHADOW_EPOCH}"
        )
    else:
        gap = SHADOW_EPOCH - tip_timestamp
        if gap > MAX_TIP_GAP_SECONDS:
            failures.append(
                f"tip is {gap}s before the Shadow epoch, exceeds the {MAX_TIP_GAP_SECONDS}s max gap"
            )

    return failures


def cmd_verify(args: argparse.Namespace) -> int:
    preset_dir = Path(args.preset)
    manifest = load_manifest(preset_dir)
    failures = verify_manifest(manifest, expected_monero_pin=_read_monero_pin())
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"PASS: {preset_dir} (height={manifest['height']}, D0={manifest['D0']})")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="dump a generator run's chain into a preset")
    p_export.add_argument("--data-dir", required=True, help="a generator run's monerod data dir (read-only)")
    p_export.add_argument("--out", required=True, help="output preset directory (e.g. chain_snapshots/h50/)")
    p_export.add_argument("--total-hashrate", type=int, required=True, help="sum of generator miners' h/s")
    p_export.add_argument("--d0", type=int, required=True, dest="d0", help="the generator's target equilibrium difficulty")
    p_export.add_argument("--generated-by", required=True, help="run id or label recorded in the manifest")
    p_export.add_argument("--hf-schedule", default=None, help="the --fakechain-hard-forks string used, if any")
    p_export.add_argument("--binary", default=str(DEFAULT_BINARY), help="monerod-sim binary to drive")
    p_export.set_defaults(func=cmd_export)

    p_build = sub.add_parser("build-template", help="materialize a preset into a cached LMDB data dir")
    p_build.add_argument("--preset", required=True, help="preset directory (e.g. chain_snapshots/h50/)")
    p_build.add_argument("--cache-root", default=str(DEFAULT_CACHE_ROOT), help="cache root directory")
    p_build.add_argument("--binary", default=str(DEFAULT_BINARY), help="monerod-sim binary to drive")
    p_build.add_argument(
        "--fixed-difficulty", type=int, default=None,
        help="dev/test only: replay under a constant difficulty matching how the preset was mined "
             "(the real recipe never sets this)",
    )
    p_build.set_defaults(func=cmd_build_template)

    p_verify = sub.add_parser("verify", help="check a preset's manifest")
    p_verify.add_argument("--preset", required=True, help="preset directory (e.g. chain_snapshots/h50/)")
    p_verify.set_defaults(func=cmd_verify)

    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ChainSnapshotError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
