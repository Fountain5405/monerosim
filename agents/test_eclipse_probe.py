"""Tests for agents.eclipse_probe's raw_probe gzip output.

The probe used to hold ONE gzip stream open for the whole run and only
flush() it. A flush pushes data out but never writes the gzip trailer, and the
process is always ended from outside (Shadow shutdown, OOM, SIGKILL), so every
archived raw_<id>.jsonl.gz failed ``gzip -d`` with "unexpected end of file"
(GitHub issue #11). Each record must now land as its own complete gzip member.
"""
import gzip
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from agents.eclipse_probe import EclipseProbeAgent

REPO_ROOT = Path(__file__).resolve().parents[1]


def _bare_probe(path):
    """An EclipseProbeAgent with just the state _dump() needs (no daemon/RPC)."""
    probe = EclipseProbeAgent.__new__(EclipseProbeAgent)
    probe._lock = threading.Lock()
    probe._path = Path(path)
    probe._role = "target"
    probe.agent_id = "relay-4000"
    probe.logger = logging.getLogger("test_eclipse_probe")
    return probe


def _gzip_test_ok(path):
    """True if the system gzip accepts the file (the reporter's exact check)."""
    return subprocess.run(["gzip", "-t", str(path)], capture_output=True).returncode == 0


def test_dump_output_is_valid_gzip_without_close(tmp_path):
    path = tmp_path / "raw_relay-4000.jsonl.gz"
    probe = _bare_probe(path)
    for i in range(5):
        probe._dump("info", {"height": i}, sim_t=float(i))

    with gzip.open(path, "rt") as fh:
        records = [json.loads(line) for line in fh]
    assert [r["data"]["height"] for r in records] == [0, 1, 2, 3, 4]
    assert records[0]["id"] == "relay-4000"
    assert records[0]["role"] == "target"
    if shutil.which("gzip"):
        assert _gzip_test_ok(path)


@pytest.mark.skipif(shutil.which("gzip") is None, reason="needs system gzip")
def test_output_survives_sigkill(tmp_path):
    """A writer killed with SIGKILL (as by Shadow or the OOM killer) still
    leaves a file that ``gzip -d`` accepts, holding every record written."""
    path = tmp_path / "raw_relay-4000.jsonl.gz"
    script = (
        "import logging, os, signal, sys, threading\n"
        "from pathlib import Path\n"
        "from agents.eclipse_probe import EclipseProbeAgent\n"
        "p = EclipseProbeAgent.__new__(EclipseProbeAgent)\n"
        "p._lock = threading.Lock(); p._path = Path(sys.argv[1])\n"
        "p._role = 'target'; p.agent_id = 'relay-4000'\n"
        "p.logger = logging.getLogger('x')\n"
        "for i in range(50):\n"
        "    p._dump('connections', {'n': i}, sim_t=float(i))\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    proc = subprocess.run([sys.executable, "-c", script, str(path)], cwd=REPO_ROOT)
    assert proc.returncode == -signal.SIGKILL

    assert _gzip_test_ok(path)
    out = subprocess.run(["gzip", "-dc", str(path)], capture_output=True, check=True)
    lines = out.stdout.decode().splitlines()
    assert [json.loads(line)["data"]["n"] for line in lines] == list(range(50))
