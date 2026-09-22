"""The peer-list dump analyser must read both run layouts.

Eclipse B/OR metrics come from monerod's `--peerlist-dump-file` output, not
from the eclipse_metrics.jsonl sidecar. Those dumps live in two places
depending on how the run was invoked, and for a long time archived runs simply
lost them: archive_daemon_logs() collected only bitmonero.log, then
cleanup_tmp_monero --full deleted the daemon data dirs. run_sim.sh now moves
each dump into daemon_logs/<node>/, so the analyser has to handle the archived
layout as well as the raw /tmp one that the original eclipse study used.

These tests pin both layouts and the registry search order.
"""
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYZER = os.path.join(REPO, "analysis", "eclipse", "analyze_peerlist_dumps.py")

TARGET = "monero-relay-4000"
TARGET_IP = "10.0.0.40"
BENIGN_IP = "10.0.0.10"


def _registry():
    return {
        "agents": [
            {"id": TARGET, "ip_addr": TARGET_IP,
             "attributes": {"eclipse_role": "target"}},
            {"id": "monero-relay-2001", "ip_addr": BENIGN_IP,
             "attributes": {"eclipse_role": "benign"}},
        ]
    }


def _snapshots():
    """Two snapshots: one benign gray entry, then evicted by trash."""
    return [
        {"t": 1000, "white_n": 1, "gray_n": 1,
         "white": [["%s:18080" % BENIGN_IP, 1000]],
         "gray": [["%s:18080" % BENIGN_IP, 1000]]},
        {"t": 1030, "white_n": 1, "gray_n": 1,
         "white": [["%s:18080" % BENIGN_IP, 1030]],
         "gray": [["203.0.113.7:18080", 1030]]},
    ]


def _write(path, obj_lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for o in obj_lines:
            f.write(json.dumps(o) + "\n")


def _write_registry(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(_registry(), f)


def _make_archived(root):
    """archived_runs/<run_id>/ as run_sim.sh writes it."""
    _write(os.path.join(root, "daemon_logs", TARGET, "peerlist_dump.jsonl"),
           _snapshots())
    _write_registry(os.path.join(root, "transaction_registry",
                                 "agent_registry.json"))
    return root


def _make_raw(root):
    """/tmp/monerosim-<run_id>/, or a preserved raw-data tree."""
    _write(os.path.join(root, TARGET, "fake", "peerlist_dump.jsonl"),
           _snapshots())
    _write_registry(os.path.join(root, "shared", "agent_registry.json"))
    return root


def _run(run_dir):
    proc = subprocess.run([sys.executable, ANALYZER, run_dir],
                          capture_output=True, text=True)
    return proc


@pytest.mark.parametrize("build", [_make_archived, _make_raw],
                         ids=["archived_run", "raw_tmp_dir"])
def test_finds_dump_in_both_layouts(tmp_path, build):
    out = _run(build(str(tmp_path)))
    assert out.returncode == 0, out.stderr
    assert "NO target dump found" not in out.stdout
    assert "(2 snapshots)" in out.stdout
    # B collapses 1 -> 0 as the benign gray entry is evicted by trash.
    assert "B trajectory: peak=1  final=0" in out.stdout


def test_both_layouts_agree(tmp_path):
    """Same data in either layout must yield the same trajectory."""
    arch = _run(_make_archived(str(tmp_path / "arch")))
    raw = _run(_make_raw(str(tmp_path / "raw")))
    assert arch.returncode == 0 and raw.returncode == 0

    def trajectory(stdout):
        return [ln for ln in stdout.splitlines() if "B trajectory" in ln]

    assert trajectory(arch.stdout) == trajectory(raw.stdout)


def test_archived_registry_is_found(tmp_path):
    """transaction_registry/ is the archived home; shared/ is the raw one."""
    out = _run(_make_archived(str(tmp_path)))
    assert "transaction_registry" in out.stdout
    assert "(2 ip->role)" in out.stdout


def test_missing_registry_fails_loudly(tmp_path):
    """No registry anywhere must be a clear error, not a silent empty run."""
    root = str(tmp_path)
    _write(os.path.join(root, "daemon_logs", TARGET, "peerlist_dump.jsonl"),
           _snapshots())
    out = _run(root)
    assert out.returncode != 0
    assert "no agent_registry.json" in (out.stderr + out.stdout)


def test_pre_fix_archive_reports_missing_dump(tmp_path):
    """An archive from before the fix has daemon_logs/ but no dumps.

    It must say so rather than silently printing an empty table.
    """
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "daemon_logs", TARGET))
    with open(os.path.join(root, "daemon_logs", TARGET, "bitmonero.log"),
              "w") as f:
        f.write("not a dump\n")
    _write_registry(os.path.join(root, "transaction_registry",
                                 "agent_registry.json"))
    out = _run(root)
    assert out.returncode == 0, out.stderr
    assert "NO target dump found" in out.stdout
