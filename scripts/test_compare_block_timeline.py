"""scripts/compare_block_timeline.py: the agent-driven block timeline of two runs.

Headers come from each run's archived chain database
(<run>/blockchain/<node>/data.mdb) through a stock monerod started offline on
a copy. Two runs match when every common height has the same timestamp,
major/minor version and difficulty, and the transaction totals agree within
a tolerance. Fields that depend on the daemon's random stream (hash, nonce,
coinbase key, byte sizes) are reported, not judged.

The fetch path is tested against a fake monerod (an HTTP server that reads a
headers.json next to the copied data.mdb).
"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "compare_block_timeline.py"
spec = importlib.util.spec_from_file_location("compare_block_timeline", SCRIPT)
cbt = importlib.util.module_from_spec(spec)
sys.modules["compare_block_timeline"] = cbt
spec.loader.exec_module(cbt)

FAKE_MONEROD = r'''#!/usr/bin/env python3
"""Fake monerod: serves get_height and get_block_headers_range from
<data-dir>/fake/lmdb/headers.json on --rpc-bind-port."""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
args = sys.argv[1:]
data_dir = args[args.index("--data-dir") + 1]
port = int(args[args.index("--rpc-bind-port") + 1])
headers = json.load(open(f"{data_dir}/fake/lmdb/headers.json"))
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == "/get_height": self._send({"height": len(headers), "status": "OK"})
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); req = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/get_height": return self._send({"height": len(headers), "status": "OK"})
        p = req.get("params", {})
        sel = headers[p["start_height"]:p["end_height"] + 1]
        self._send({"jsonrpc": "2.0", "id": req.get("id"), "result": {"headers": sel, "status": "OK"}})
HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def header(h, ts, diff=1, txes=0, size=85, hash_=None):
    return {"height": h, "timestamp": ts, "major_version": 16, "minor_version": 16,
            "difficulty": diff, "cumulative_difficulty": diff * (h + 1), "num_txes": txes,
            "block_size": size, "block_weight": size, "nonce": h, "reward": 35,
            "hash": hash_ or f"{h:064x}", "miner_tx_hash": f"{h + 1000:064x}"}


def write_run(root: Path, name: str, chains: dict) -> Path:
    """chains: {node: [header, ...]}; writes blockchain/<node>/{data.mdb,headers.json}."""
    run = root / name
    for node, headers in chains.items():
        d = run / "blockchain" / node
        d.mkdir(parents=True)
        (d / "data.mdb").write_bytes(b"not a real lmdb")
        (d / "headers.json").write_text(json.dumps(headers))
    return run


def fake_monerod(tmp_path: Path) -> Path:
    p = tmp_path / "monerod"
    p.write_text(FAKE_MONEROD)
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return p


# --- the comparison itself (pure) ---------------------------------------------

def test_identical_timeline_passes():
    a = [header(0, 0), header(1, 100, txes=1), header(2, 220, diff=2)]
    b = [header(0, 0), header(1, 100, txes=1, hash_="f" * 64), header(2, 220, diff=2, size=86)]
    r = cbt.compare_headers(a, b, tx_tolerance=0.02)
    assert r.timeline_ok and r.first_difference is None
    assert r.common == 3
    assert r.tx_total == (1, 1)
    assert r.same["hash"] == 2 and r.same["block_size"] == 2


def test_timestamp_difference_is_reported_with_height_and_field():
    a = [header(0, 0), header(1, 100), header(2, 220)]
    b = [header(0, 0), header(1, 100), header(2, 221)]
    r = cbt.compare_headers(a, b, tx_tolerance=0.02)
    assert not r.timeline_ok
    assert r.first_difference == (2, "timestamp", 220, 221)


def test_difficulty_and_version_are_judged():
    a = [header(0, 0), header(1, 100, diff=3)]
    b = [header(0, 0), header(1, 100, diff=4)]
    assert cbt.compare_headers(a, b, 0.02).first_difference == (1, "difficulty", 3, 4)
    c = [header(0, 0), header(1, 100, diff=3)]
    d = [header(0, 0), dict(header(1, 100, diff=3), minor_version=15)]
    assert cbt.compare_headers(c, d, 0.02).first_difference == (1, "minor_version", 16, 15)


def test_tx_totals_outside_tolerance_fail():
    a = [header(0, 0)] + [header(h, h * 100, txes=1) for h in range(1, 101)]   # 100 txs
    b = [header(0, 0)] + [header(h, h * 100, txes=1) for h in range(1, 98)] + \
        [header(h, h * 100, txes=0) for h in range(98, 101)]                 # 97 txs
    r = cbt.compare_headers(a, b, tx_tolerance=0.02)
    assert r.timeline_ok and not r.tx_ok and r.tx_total == (100, 97)
    assert cbt.compare_headers(a, b, tx_tolerance=0.05).tx_ok


def test_tx_totals_shifted_between_blocks_pass():
    a = [header(0, 0), header(1, 100, txes=2), header(2, 220, txes=0)]
    b = [header(0, 0), header(1, 100, txes=1), header(2, 220, txes=1)]
    r = cbt.compare_headers(a, b, tx_tolerance=0.0)
    assert r.timeline_ok and r.tx_ok and r.same["num_txes"] == 1


def test_only_common_heights_are_compared():
    a = [header(0, 0), header(1, 100), header(2, 220)]
    b = [header(0, 0), header(1, 100)]
    r = cbt.compare_headers(a, b, 0.02)
    assert r.common == 2 and r.timeline_ok and (r.top_a, r.top_b) == (2, 1)


# --- fetching through monerod --------------------------------------------------

def test_fetch_headers_through_offline_monerod(tmp_path):
    run = write_run(tmp_path, "a", {"monero-miner-001": [header(0, 0), header(1, 100)]})
    got = cbt.fetch_headers(run, "monero-miner-001", monerod=fake_monerod(tmp_path), base_port=48301)
    assert [h["height"] for h in got] == [0, 1]
    assert got[1]["timestamp"] == 100
    # the archive itself is untouched (no lock.mdb written next to data.mdb)
    assert sorted(p.name for p in (run / "blockchain" / "monero-miner-001").iterdir()) == ["data.mdb", "headers.json"]


def test_archived_nodes_lists_chains_present_in_both_runs(tmp_path):
    a = write_run(tmp_path, "a", {"n1": [header(0, 0)], "n2": [header(0, 0)]})
    b = write_run(tmp_path, "b", {"n2": [header(0, 0)], "n3": [header(0, 0)]})
    assert cbt.archived_nodes(a, b) == ["n2"]


# --- CLI --------------------------------------------------------------------------

def run_cli(tmp_path, *args):
    env = dict(os.environ, PATH=os.environ["PATH"])
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args),
                           "--monerod", str(fake_monerod(tmp_path)), "--base-port", "48311"],
                          capture_output=True, text=True, env=env)


def test_cli_pass_exit_0(tmp_path):
    a = write_run(tmp_path, "a", {"m": [header(0, 0), header(1, 100, txes=1)]})
    b = write_run(tmp_path, "b", {"m": [header(0, 0), header(1, 100, txes=1, hash_="f" * 64)]})
    p = run_cli(tmp_path, a, b)
    assert p.returncode == 0, p.stderr + p.stdout
    assert "m: timeline identical over 2 common heights" in p.stdout
    assert "hash" in p.stdout  # the random-dependent fields are reported


def test_cli_timeline_difference_exit_1(tmp_path):
    a = write_run(tmp_path, "a", {"m": [header(0, 0), header(1, 100), header(2, 220)]})
    b = write_run(tmp_path, "b", {"m": [header(0, 0), header(1, 100), header(2, 221)]})
    out = tmp_path / "r.json"
    p = run_cli(tmp_path, a, b, "--json", out)
    assert p.returncode == 1
    assert "height 2" in p.stdout and "timestamp" in p.stdout
    data = json.loads(out.read_text())
    assert data["verdict"] == "DIFFERS"
    assert data["nodes"][0]["first_difference"] == [2, "timestamp", 220, 221]


def test_cli_no_common_chain_exit_2(tmp_path):
    a = write_run(tmp_path, "a", {"m": [header(0, 0)]})
    b = write_run(tmp_path, "b", {"n": [header(0, 0)]})
    assert run_cli(tmp_path, a, b).returncode == 2


def test_cli_monerod_missing_exit_2(tmp_path):
    a = write_run(tmp_path, "a", {"m": [header(0, 0)]})
    b = write_run(tmp_path, "b", {"m": [header(0, 0)]})
    p = subprocess.run([sys.executable, str(SCRIPT), str(a), str(b), "--monerod", str(tmp_path / "nope")],
                       capture_output=True, text=True)
    assert p.returncode == 2
