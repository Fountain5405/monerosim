"""Tests for agents.eclipse_probe's raw_probe output.

The probe is always ended from outside (Shadow shutdown, OOM, SIGKILL), so its
output must be complete and readable without a clean close. It now writes plain
JSONL (one unbuffered append per record); run_sim.sh's compress_probe_dumps
gzips it at archive time. History (GitHub issue #11): a single long-lived gzip
stream never got its trailer, so every archived file failed ``gzip -d``; the
interim fix (one gzip member per record) was valid but 4-5x larger.
"""
import json
import logging
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from agents.eclipse_probe import EclipseProbeAgent

REPO_ROOT = Path(__file__).resolve().parents[1]


def _bare_probe(path):
    """An EclipseProbeAgent with just the state _dump() needs (no daemon/RPC)."""
    probe = EclipseProbeAgent.__new__(EclipseProbeAgent)
    probe._lock = threading.Lock()
    probe._path = Path(path)
    probe._fd = os.open(probe._path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o664)
    probe._role = "target"
    probe.agent_id = "relay-4000"
    probe.logger = logging.getLogger("test_eclipse_probe")
    return probe


def test_dump_writes_complete_jsonl_lines(tmp_path):
    path = tmp_path / "raw_relay-4000.jsonl"
    probe = _bare_probe(path)
    for i in range(5):
        probe._dump("info", {"height": i}, sim_t=float(i))

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["data"]["height"] for r in records] == [0, 1, 2, 3, 4]
    assert records[0]["id"] == "relay-4000"
    assert records[0]["role"] == "target"


def test_dump_appends_across_reopen(tmp_path):
    """A restarted probe appends to, and never truncates, an existing dump."""
    path = tmp_path / "raw_relay-4000.jsonl"
    _bare_probe(path)._dump("info", {"n": 1}, sim_t=1.0)
    _bare_probe(path)._dump("info", {"n": 2}, sim_t=2.0)
    assert [json.loads(l)["data"]["n"] for l in path.read_text().splitlines()] == [1, 2]


def test_output_survives_sigkill(tmp_path):
    """A writer killed with SIGKILL (as by Shadow or the OOM killer) leaves
    every record it wrote, each as a complete JSON line."""
    path = tmp_path / "raw_relay-4000.jsonl"
    script = (
        "import logging, os, signal, sys, threading\n"
        "from pathlib import Path\n"
        "from agents.eclipse_probe import EclipseProbeAgent\n"
        "p = EclipseProbeAgent.__new__(EclipseProbeAgent)\n"
        "p._lock = threading.Lock(); p._path = Path(sys.argv[1])\n"
        "p._fd = os.open(p._path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o664)\n"
        "p._role = 'target'; p.agent_id = 'relay-4000'\n"
        "p.logger = logging.getLogger('x')\n"
        "for i in range(50):\n"
        "    p._dump('connections', {'n': i}, sim_t=float(i))\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    proc = subprocess.run([sys.executable, "-c", script, str(path)], cwd=REPO_ROOT)
    assert proc.returncode == -signal.SIGKILL

    lines = path.read_text().splitlines()
    assert [json.loads(line)["data"]["n"] for line in lines] == list(range(50))
