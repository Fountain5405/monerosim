"""Tests for scripts/run_dir_lib.sh, driven through bash."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "scripts" / "run_dir_lib.sh"


def bash(snippet, env=None, cwd=None):
    """Run `source run_dir_lib.sh; <snippet>` in bash; return (rc, stdout, stderr)."""
    full_env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/")}
    full_env.update(env or {})
    r = subprocess.run(
        ["bash", "-c", f"source '{LIB}'; {snippet}"],
        capture_output=True, text=True, env=full_env, cwd=cwd or ROOT,
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _mk_run(base, name, *, owner=None, complete=False):
    d = base / name
    d.mkdir(parents=True)
    if owner is not None:
        (d / ".owner_pid").write_text(f"{owner}\n")
    if complete:
        (d / "summary.txt").write_text("Exit code: 0\n")
    return d


def test_state_live_uses_proc(tmp_path):
    d = _mk_run(tmp_path, "20260904_120000_a", owner=os.getpid(), complete=True)
    assert bash(f"run_dir_state '{d}'")[1] == "live"
    assert bash(f"run_dir_is_live '{d}'")[0] == 0


def test_state_complete_and_incomplete(tmp_path):
    c = _mk_run(tmp_path, "20260904_120000_a", owner=2**22 - 1, complete=True)
    i = _mk_run(tmp_path, "20260904_120001_b")
    assert bash(f"run_dir_state '{c}'")[1] == "complete"
    assert bash(f"run_dir_state '{i}'")[1] == "incomplete"
    assert bash(f"run_dir_is_live '{i}'")[0] == 1


def test_newest_run_dir(tmp_path):
    _mk_run(tmp_path, "20260904_120000_zzz")
    b = _mk_run(tmp_path, "20260904_130000_aaa")
    _mk_run(tmp_path, "notes")
    assert bash(f"newest_run_dir '{tmp_path}'")[1] == str(b)
    assert bash(f"newest_run_dir '{tmp_path / 'empty'}'")[0] == 1


def test_newest_run_dir_ignores_non_directory(tmp_path):
    b = _mk_run(tmp_path, "20260904_130000_b")
    (tmp_path / "20260904_140000_file").write_text("not a run dir\n")
    assert bash(f"newest_run_dir '{tmp_path}'")[1] == str(b)


def test_resolve_order_explicit_env_newest(tmp_path):
    a = _mk_run(tmp_path, "20260904_120000_a", complete=True)
    b = _mk_run(tmp_path, "20260904_130000_b")
    env = {"MONEROSIM_ARCHIVE_BASE": str(tmp_path)}
    rc, out, err = bash(f"resolve_run_dir '{a}'", env={**env, "MONEROSIM_RUN_DIR": str(b)})
    assert (rc, out) == (0, str(a)) and err == f"run: {a} (complete)"
    rc, out, err = bash("resolve_run_dir", env={**env, "MONEROSIM_RUN_DIR": str(a)})
    assert (rc, out) == (0, str(a))
    rc, out, err = bash("resolve_run_dir", env=env)
    assert (rc, out) == (0, str(b)) and err == f"run: {b} (incomplete)"


def test_resolve_rc2_when_nothing(tmp_path):
    rc, out, err = bash("resolve_run_dir", env={"MONEROSIM_ARCHIVE_BASE": str(tmp_path)})
    assert rc == 2 and out == "" and "no run directory" in err
    rc, out, err = bash(f"resolve_run_dir '{tmp_path / 'missing'}'")
    assert rc == 2


def test_allocate_run_dir_suffixes_on_collision(tmp_path):
    env = {"MONEROSIM_RUN_TS": "20260904_120000"}
    ids = [bash(f"allocate_run_dir '{tmp_path}' quick", env=env)[1] for _ in range(3)]
    assert ids == ["20260904_120000_quick", "20260904_120000_quick_2", "20260904_120000_quick_3"]
    for rid in ids:
        pid = (tmp_path / rid / ".owner_pid").read_text().strip()
        assert pid.isdigit()


def test_allocate_run_dir_gives_up_after_99(tmp_path):
    env = {"MONEROSIM_RUN_TS": "20260904_120000"}
    (tmp_path / "20260904_120000_q").mkdir()
    for n in range(2, 100):
        (tmp_path / f"20260904_120000_q_{n}").mkdir()
    rc, out, err = bash(f"allocate_run_dir '{tmp_path}' q", env=env)
    assert rc == 1 and out == "" and "99 collisions" in err


def test_allocate_run_dir_reports_mkdir_error_not_collisions(tmp_path):
    readonly_parent = tmp_path / "readonly"
    readonly_parent.mkdir()
    readonly_parent.chmod(0o500)
    base = readonly_parent / "sub"
    env = {"MONEROSIM_RUN_TS": "20260904_120000"}
    try:
        rc, out, err = bash(f"allocate_run_dir '{base}' q", env=env)
        assert rc == 1 and out == ""
        assert "cannot create" in err
        assert "99 collisions" not in err
    finally:
        readonly_parent.chmod(0o700)
