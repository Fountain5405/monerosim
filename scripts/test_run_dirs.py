"""Tests for scripts/run_dirs.py (run-directory resolution and state)."""
import os
from datetime import datetime
from pathlib import Path

import pytest

from scripts.run_dirs import (
    LiveRun,
    RunDirNotFound,
    announce,
    daemon_log_dir,
    list_live_runs,
    newest_run_dir,
    read_run_env,
    resolve_run_dir,
    run_id_started,
    run_state,
)


@pytest.fixture
def proc(tmp_path):
    """Fake /proc: a pid is 'alive' when tmp_path/proc/<pid> exists."""
    p = tmp_path / "proc"
    p.mkdir()
    (p / "4242").mkdir()  # alive
    return p


def _mk_run(base, name, *, owner=None, complete=False):
    d = base / name
    d.mkdir(parents=True)
    if owner is not None:
        (d / ".owner_pid").write_text(f"{owner}\n")
    if complete:
        (d / "summary.txt").write_text("Exit code: 0\n")
    return d


def test_run_state_live_when_owner_pid_exists(tmp_path, proc):
    d = _mk_run(tmp_path, "20260904_120000_a", owner=4242, complete=True)
    assert run_state(d, proc) == "live"


def test_run_state_complete_when_owner_dead_and_summary(tmp_path, proc):
    d = _mk_run(tmp_path, "20260904_120000_a", owner=9999, complete=True)
    assert run_state(d, proc) == "complete"


def test_run_state_incomplete_otherwise(tmp_path, proc):
    d = _mk_run(tmp_path, "20260904_120000_a", owner=9999)
    assert run_state(d, proc) == "incomplete"
    assert run_state(_mk_run(tmp_path, "20260904_120001_b"), proc) == "incomplete"


def test_newest_run_dir_is_lexically_greatest_run_name(tmp_path):
    _mk_run(tmp_path, "20260904_120000_zzz")
    _mk_run(tmp_path, "20260904_130000_aaa")
    _mk_run(tmp_path, "notes")            # ignored: not a run name
    (tmp_path / "20260905_000000_file").write_text("")  # ignored: not a dir
    assert newest_run_dir(tmp_path) == tmp_path / "20260904_130000_aaa"


def test_newest_run_dir_none_when_empty_or_missing(tmp_path):
    assert newest_run_dir(tmp_path) is None
    assert newest_run_dir(tmp_path / "nope") is None


def test_resolve_explicit_wins_over_env(tmp_path):
    a = _mk_run(tmp_path, "20260904_120000_a")
    b = _mk_run(tmp_path, "20260904_130000_b")
    env = {"MONEROSIM_RUN_DIR": str(b)}
    assert resolve_run_dir(str(a), base=tmp_path, env=env) == a.resolve()


def test_resolve_env_wins_over_newest(tmp_path):
    a = _mk_run(tmp_path, "20260904_120000_a")
    _mk_run(tmp_path, "20260904_130000_b")
    env = {"MONEROSIM_RUN_DIR": str(a)}
    assert resolve_run_dir(None, base=tmp_path, env=env) == a.resolve()


def test_resolve_falls_back_to_newest(tmp_path):
    _mk_run(tmp_path, "20260904_120000_a")
    b = _mk_run(tmp_path, "20260904_130000_b")
    assert resolve_run_dir(None, base=tmp_path, env={}) == b.resolve()


def test_resolve_raises_when_nothing_matches(tmp_path):
    with pytest.raises(RunDirNotFound):
        resolve_run_dir(None, base=tmp_path, env={})
    with pytest.raises(RunDirNotFound):
        resolve_run_dir(str(tmp_path / "missing"), base=tmp_path, env={})


def test_announce_format(tmp_path, proc, capsys):
    d = _mk_run(tmp_path, "20260904_120000_a", owner=9999, complete=True)
    line = announce(d)
    assert line == f"run: {d} (complete)"
    assert capsys.readouterr().err.strip() == line


def test_run_id_started():
    assert run_id_started("20260904_151956_100_agent_x") == datetime(2026, 9, 4, 15, 19, 56)
    assert run_id_started("notes") is None
    assert run_id_started("20261399_999999_x") is None


def test_list_live_runs_merges_archive_and_tmp_and_skips_dead(tmp_path, proc):
    base = tmp_path / "archived_runs"
    tmp_root = tmp_path / "tmp"
    tmp_root.mkdir()
    (proc / "5151").mkdir()
    (proc / "6161").mkdir()
    # live, known from archive AND tmp -> one entry, source archive
    _mk_run(base, "20260904_120000_a", owner=4242)
    (tmp_root / "monerosim-20260904_120000_a").mkdir()
    (tmp_root / "monerosim-20260904_120000_a" / ".owner_pid").write_text("4242")
    (tmp_root / "monerosim-20260904_120000_a" / "monero-miner-001").mkdir()
    # dead owner -> skipped
    _mk_run(base, "20260904_121000_dead", owner=9999)
    # live, tmp only (another checkout) -> source tmp
    t = tmp_root / "monerosim-20260904_122000_other"
    t.mkdir()
    (t / ".owner_pid").write_text("5151")
    # our own pid -> excluded
    _mk_run(base, "20260904_123000_me", owner=6161)

    runs = list_live_runs(base, tmp_root=tmp_root, exclude_pid=6161, proc_root=proc)
    assert [(r.run_id, r.pid, r.source) for r in runs] == [
        ("20260904_120000_a", 4242, "archive"),
        ("20260904_122000_other", 5151, "tmp"),
    ]
    assert runs[0].run_dir == base / "20260904_120000_a"
    assert runs[0].tmp_dir == tmp_root / "monerosim-20260904_120000_a"
    assert runs[0].started == datetime(2026, 9, 4, 12, 0, 0)
    assert runs[1].run_dir is None and runs[1].tmp_dir == t


def test_read_run_env_and_daemon_log_dir_prefers_archive(tmp_path):
    run = _mk_run(tmp_path, "20260904_120000_a")
    (run / "shadow_output").mkdir()
    live = tmp_path / "live"
    (live / "monero-miner-001").mkdir(parents=True)
    (live / "monero-miner-001" / "bitmonero.log").write_text("x")
    (run / "shadow_output" / "run_env.sh").write_text(
        f'MONEROSIM_RUN_ID="20260904_120000_a"\nMONEROSIM_DAEMON_DATA_DIR="{live}"\n'
    )
    assert read_run_env(run)["MONEROSIM_DAEMON_DATA_DIR"] == str(live)
    assert daemon_log_dir(run) == live            # live namespace
    (run / "daemon_logs").mkdir()
    assert daemon_log_dir(run) == run / "daemon_logs"   # archived copy wins


def test_daemon_log_dir_none_without_breadcrumb_or_logs(tmp_path):
    run = _mk_run(tmp_path, "20260904_120000_a")
    assert daemon_log_dir(run) is None
    assert read_run_env(run) == {}
