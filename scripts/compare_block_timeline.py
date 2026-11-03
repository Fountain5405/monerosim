#!/usr/bin/env python3
"""compare_block_timeline.py - do two runs have the same block timeline?

The block ids of two runs made with different daemon binaries always differ:
the coinbase key is drawn from the daemon's random stream, and any change to
the binary shifts that stream (2026-11-03, stock monerod against an unflagged
monerod-sim on quickstart: every block from height 1 on had a different id
and nothing else). What the agents drive, and what a patch that quietly
changed consensus or mining would disturb, is the timeline: each height's
timestamp, block version and difficulty. This tool compares that.

Headers come from each run's archived chain database
(<run>/blockchain/<node>/data.mdb, one node per type by default) through a
stock monerod started offline on a copy of the database, so the archive is
never touched.

    scripts/compare_block_timeline.py RUN_A RUN_B [--node NAME ...]
        [--tx-tolerance 0.02] [--monerod ~/.monerosim/bin/monerod] [--json OUT]

Per node present in both archives, over the heights both runs reached:
  judged   timestamp, major_version, minor_version, difficulty: identical at
           every height; total num_txes: within --tx-tolerance (a fraction of
           the larger total; default 2%, transactions can straddle a block)
  reported hash, miner_tx_hash, nonce, num_txes per block, block_size: how
           many heights agree (they follow the random stream)

Exit 0: every node's timeline is identical and its tx totals agree.
Exit 1: a timeline differs (first height and field printed) or tx totals
        are outside the tolerance.
Exit 2: cannot compare (no chain archived in both runs, monerod missing or
        not answering).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

JUDGED = ("timestamp", "major_version", "minor_version", "difficulty")
REPORTED = ("hash", "miner_tx_hash", "nonce", "num_txes", "block_size")
DEFAULT_MONEROD = Path.home() / ".monerosim" / "bin" / "monerod"


# --- the comparison -----------------------------------------------------------

@dataclass
class NodeResult:
    node: str
    top_a: int | None
    top_b: int | None
    common: int
    first_difference: tuple | None    # (height, field, a, b)
    tx_total: tuple[int, int]
    tx_ok: bool
    same: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def timeline_ok(self) -> bool:
        return self.error is None and self.first_difference is None

    @property
    def ok(self) -> bool:
        return self.timeline_ok and self.tx_ok


def compare_headers(a: list[dict], b: list[dict], tx_tolerance: float, node: str = "") -> NodeResult:
    by_a = {h["height"]: h for h in a}
    by_b = {h["height"]: h for h in b}
    common = sorted(set(by_a) & set(by_b))
    first = None
    for h in common:
        for f in JUDGED:
            if by_a[h][f] != by_b[h][f]:
                first = (h, f, by_a[h][f], by_b[h][f])
                break
        if first:
            break
    ta = sum(by_a[h]["num_txes"] for h in common)
    tb = sum(by_b[h]["num_txes"] for h in common)
    tx_ok = abs(ta - tb) <= tx_tolerance * max(ta, tb, 1)
    same = {f: sum(1 for h in common if by_a[h].get(f) == by_b[h].get(f)) for f in REPORTED}
    return NodeResult(node, max(by_a, default=None), max(by_b, default=None), len(common),
                      first, (ta, tb), tx_ok, same)


# --- fetching headers from an archived chain ----------------------------------

def archived_nodes(run_a: Path, run_b: Path) -> list[str]:
    """Nodes whose chain database both runs archived."""
    def nodes(run):
        d = Path(run) / "blockchain"
        return {p.name for p in d.iterdir() if (p / "data.mdb").is_file()} if d.is_dir() else set()
    return sorted(nodes(run_a) & nodes(run_b))


def _free_port(start: int) -> int:
    for port in range(start, start + 200, 2):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free port")


def _rpc(port: int, path: str, payload: dict | None, timeout: float = 5) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_headers(run: Path, node: str, monerod: Path = DEFAULT_MONEROD, base_port: int = 48201,
                  startup_timeout: float = 120) -> list[dict]:
    """All block headers of <run>/blockchain/<node>, via monerod offline on a copy."""
    src = Path(run) / "blockchain" / node
    if not (src / "data.mdb").is_file():
        raise FileNotFoundError(f"{src}/data.mdb")
    if not Path(monerod).is_file():
        raise FileNotFoundError(f"monerod not found at {monerod}")
    with tempfile.TemporaryDirectory(prefix="block_timeline.") as tmp:
        data_dir = Path(tmp) / "data"
        lmdb = data_dir / "fake" / "lmdb"
        lmdb.mkdir(parents=True)
        for p in src.iterdir():
            if p.is_file() and p.name != "lock.mdb":
                shutil.copy2(p, lmdb / p.name)
        port = _free_port(base_port)
        log = Path(tmp) / "monerod.log"
        proc = subprocess.Popen(
            [str(monerod), "--data-dir", str(data_dir), "--regtest", "--keep-fakechain", "--offline",
             "--no-zmq", "--non-interactive", "--rpc-bind-ip", "127.0.0.1", "--rpc-bind-port", str(port),
             "--p2p-bind-port", str(port + 1), "--log-file", str(log), "--log-level", "0"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            deadline = time.monotonic() + startup_timeout
            height = None
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f"monerod exited with {proc.returncode} (log: {log.read_text()[-2000:] if log.exists() else 'none'})")
                try:
                    height = _rpc(port, "/get_height", None)["height"]
                    break
                except Exception:
                    time.sleep(0.5)
            if height is None:
                raise RuntimeError(f"monerod on port {port} did not answer within {startup_timeout}s")
            headers: list[dict] = []
            step = 1000
            for start in range(0, height, step):
                end = min(start + step, height) - 1
                res = _rpc(port, "/json_rpc", {"jsonrpc": "2.0", "id": "0", "method": "get_block_headers_range",
                                               "params": {"start_height": start, "end_height": end}}, timeout=120)
                headers.extend(res["result"]["headers"])
            return headers
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()


# --- CLI --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_a")
    p.add_argument("run_b")
    p.add_argument("--node", action="append", default=[], help="compare only this archived node (repeatable)")
    p.add_argument("--tx-tolerance", type=float, default=0.02,
                   help="allowed difference of total num_txes as a fraction of the larger total (default 0.02)")
    p.add_argument("--monerod", type=Path, default=DEFAULT_MONEROD, help="stock monerod to read the archives with")
    p.add_argument("--base-port", type=int, default=48201, help="first RPC port to try for the offline daemon")
    p.add_argument("--json", type=Path, help="also write the results here")
    args = p.parse_args(argv)

    run_a, run_b = Path(args.run_a), Path(args.run_b)
    if not args.monerod.is_file():
        print(f"monerod not found at {args.monerod} (--monerod)", file=sys.stderr)
        return 2
    nodes = args.node or archived_nodes(run_a, run_b)
    if not nodes:
        print(f"no chain database archived in both {run_a} and {run_b} (blockchain/<node>/data.mdb)", file=sys.stderr)
        return 2

    results: list[NodeResult] = []
    rc = 0
    for node in nodes:
        try:
            a = fetch_headers(run_a, node, args.monerod, args.base_port)
            b = fetch_headers(run_b, node, args.monerod, args.base_port)
        except Exception as e:  # noqa: BLE001 - any fetch failure is "cannot compare"
            results.append(NodeResult(node, None, None, 0, None, (0, 0), False, {}, str(e)))
            print(f"{node}: ERROR {e}")
            rc = 2
            continue
        r = compare_headers(a, b, args.tx_tolerance, node)
        results.append(r)
        if r.first_difference:
            h, f, va, vb = r.first_difference
            print(f"{node}: timeline DIFFERS at height {h}: {f} {va} vs {vb} (tops {r.top_a} / {r.top_b})")
            rc = max(rc, 1)
        else:
            print(f"{node}: timeline identical over {r.common} common heights "
                  f"(timestamp, block version, difficulty; tops {r.top_a} / {r.top_b})")
        ta, tb = r.tx_total
        print(f"{node}: transactions in blocks {ta} vs {tb}"
              f" ({'within' if r.tx_ok else 'OUTSIDE'} {args.tx_tolerance:.0%})")
        if not r.tx_ok:
            rc = max(rc, 1)
        print(f"{node}: random-stream fields, heights agreeing of {r.common}: "
              + ", ".join(f"{f} {n}" for f, n in r.same.items()))

    verdict = "ERROR" if rc == 2 else ("SAME" if rc == 0 else "DIFFERS")
    print(f"{verdict}: {sum(1 for r in results if r.ok)} of {len(results)} archived chains have the same timeline")
    if args.json:
        args.json.write_text(json.dumps({
            "run_a": str(run_a), "run_b": str(run_b), "verdict": verdict, "tx_tolerance": args.tx_tolerance,
            "nodes": [{"node": r.node, "top_a": r.top_a, "top_b": r.top_b, "common": r.common,
                       "first_difference": r.first_difference, "tx_total": r.tx_total, "tx_ok": r.tx_ok,
                       "same": r.same, "error": r.error} for r in results],
        }, indent=2) + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
