"""Candidate order of find_shadow_data_hosts: output-dir-relative first,
cwd-relative last, so a stale <checkout>/shadow.data never wins over the
run's own tree (runs are concurrent per checkout since 2026-09)."""
from pathlib import Path

from agents.simulation_monitor.status_paths import find_shadow_data_hosts


def test_output_dir_sibling_wins_over_cwd(tmp_path, monkeypatch):
    run = tmp_path / "run"
    (run / "shadow.data" / "hosts").mkdir(parents=True)
    output_dir = run / "shadow_output"
    output_dir.mkdir()
    stale_cwd = tmp_path / "checkout"
    (stale_cwd / "shadow.data" / "hosts").mkdir(parents=True)
    monkeypatch.chdir(stale_cwd)
    assert find_shadow_data_hosts(output_dir) == run / "shadow.data" / "hosts"


def test_cwd_is_last_resort(tmp_path, monkeypatch):
    cwd = tmp_path / "checkout"
    (cwd / "shadow.data" / "hosts").mkdir(parents=True)
    monkeypatch.chdir(cwd)
    assert find_shadow_data_hosts(tmp_path / "nowhere") == Path("shadow.data") / "hosts"
    assert find_shadow_data_hosts(None) == Path("shadow.data") / "hosts"


def test_none_when_nothing_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert find_shadow_data_hosts(tmp_path / "out") is None
