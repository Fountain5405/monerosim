# Per-Run Directories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any number of `run_sim.sh` instances run concurrently from one checkout by giving every run a single directory for its whole life and teaching every tool to address a run explicitly.

**Architecture:** `run_sim.sh` stops writing anything at the checkout root: Shadow's `-d` and the generator's `--output` both point inside `archived_runs/<run_id>/`, which the script creates atomically and marks with `.owner_pid`. Two tiny resolver libraries (`scripts/run_dirs.py`, `scripts/run_dir_lib.sh`) implement one "which run" contract (explicit > `$MONEROSIM_RUN_DIR` > newest) and one state vocabulary (live / complete / incomplete) that `check_sim.sh`, `start_here.sh`, the analysers, the prune script and the preflight report all reuse. Preflight enumerates other live runs through the owner-pid breadcrumbs and subtracts their projected growth from free disk.

**Tech Stack:** bash (run_sim.sh and tools), Python 3.12 + pytest (helpers, resolvers, tests), Rust generator untouched.

**Spec:** `docs/superpowers/specs/2026-09-04-per-run-directories-design.md`

## Global Constraints

- The Rust generator (`src/`), the generated YAML, wrapper scripts and golden tests (`cargo test`) do not change.
- Nothing under the checkout root is created, written or deleted during a run (spec §2). `shadow.data/`, `shadow_output/`, `shadow.log` at the root are legacy leftovers and are never touched.
- Run directories are created with plain `mkdir` (never `mkdir -p` on the leaf) and get `_2`..`_99` suffixes on collision (spec §3.1).
- Shadow creates its own data directory. Never pre-create `shadow.data` (Shadow refuses an existing, even empty, `-d` path; verified 2026-09-04).
- Liveness is `/proc/<pid>` existence, not `kill -0`, so another user's run counts as live (this box is shared).
- Run-dir resolution order everywhere: explicit argument, then `$MONEROSIM_RUN_DIR`, then newest `^[0-9]{8}_[0-9]{6}_` name under `$MONEROSIM_ARCHIVE_BASE` or `<checkout>/archived_runs`. Every tool prints `run: <dir> (<state>)` to stderr (spec §4.1).
- Process operations in tests and scripts are scoped to the current user (`pgrep -u "$(id -u)"`); never an unscoped `pkill`.
- Commit after every task with a conventional-commit subject and the session trailer:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Ae22Qvzt8RtCFFVxNyswTD
  ```
- Run Python tests with `python3 -m pytest <file> -q` from the checkout root (pytest is configured in `pyproject.toml`; `scripts/__init__.py` exists so `from scripts.x import y` works). Run bash syntax checks with `bash -n <file>`; run `shellcheck <file>` if `shellcheck` is installed.
- Work on branch `feat/per-run-directories` (created from `main` at the plan commit).

---

### Task 1: `scripts/run_dirs.py` — the Python run-directory resolver

**Files:**
- Create: `scripts/run_dirs.py`
- Test: `scripts/test_run_dirs.py`

**Interfaces:**
- Produces (used by Tasks 4, 9):
  - `resolve_run_dir(explicit: str | None = None, *, base: Path | None = None, env=os.environ) -> Path` (raises `RunDirNotFound`)
  - `run_state(run_dir: Path, proc_root: Path = Path("/proc")) -> str` returning `"live" | "complete" | "incomplete"`
  - `newest_run_dir(base: Path) -> Path | None`
  - `announce(run_dir: Path, file=sys.stderr) -> str` printing `run: <dir> (<state>)`
  - `list_live_runs(base: Path, *, tmp_root=Path("/tmp"), exclude_pid: int | None = None, proc_root=Path("/proc")) -> list[LiveRun]`
  - `LiveRun` dataclass: `run_id: str, pid: int, source: str ("archive"|"tmp"), run_dir: Path | None, tmp_dir: Path | None, started: datetime | None`
  - `run_id_started(run_id: str) -> datetime | None`
  - `read_run_env(run_dir: Path) -> dict[str, str]` parsing `KEY="value"` lines of `<run>/shadow_output/run_env.sh`
  - `daemon_log_dir(run_dir: Path) -> Path | None`: `<run>/daemon_logs` if it exists, else the live `MONEROSIM_DAEMON_DATA_DIR` from `run_env.sh` if it contains `monero-*/bitmonero.log`, else `None`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_run_dirs.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest scripts/test_run_dirs.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'scripts.run_dirs'`.

- [ ] **Step 3: Write the module**

Create `scripts/run_dirs.py`:

```python
"""
run_dirs.py - locate and classify monerosim run directories.

Since 2026-09 every run_sim.sh run lives, for its whole life, in one
directory: <archive base>/<run_id>/ where run_id = YYYYmmdd_HHMMSS_<name>[_N].
Out-of-band tools resolve "which run" through resolve_run_dir():

    1. an explicit path given by the caller;
    2. $MONEROSIM_RUN_DIR (run_sim.sh exports it to its children);
    3. the newest run directory under the archive base
       ($MONEROSIM_ARCHIVE_BASE, default <checkout>/archived_runs).

A run's state comes from two breadcrumbs run_sim.sh leaves:
    .owner_pid   -> "live" while /proc/<pid> exists
    summary.txt  -> "complete" (run_sim.sh writes it last)
    neither      -> "incomplete" (crashed, killed, or --no-archive)

scripts/run_dir_lib.sh is the bash twin of this module; keep them in sync.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Optional

ARCHIVE_BASE_ENV = "MONEROSIM_ARCHIVE_BASE"
RUN_DIR_ENV = "MONEROSIM_RUN_DIR"
RUN_ID_RE = re.compile(r"^(\d{8})_(\d{6})_")
OWNER_PID_FILE = ".owner_pid"
COMPLETE_MARKER = "summary.txt"
RUN_ENV_FILE = Path("shadow_output") / "run_env.sh"
TMP_PREFIX = "monerosim-"

STATE_LIVE = "live"
STATE_COMPLETE = "complete"
STATE_INCOMPLETE = "incomplete"


class RunDirNotFound(Exception):
    """No run directory could be resolved."""


def default_archive_base(env: Mapping[str, str] = os.environ) -> Path:
    override = env.get(ARCHIVE_BASE_ENV)
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "archived_runs"


def pid_alive(pid: int, proc_root: Path = Path("/proc")) -> bool:
    """True if a process with this pid exists. /proc rather than os.kill so a
    process owned by another user (EPERM) still counts as alive."""
    return (proc_root / str(pid)).exists()


def owner_pid(run_dir: Path) -> Optional[int]:
    try:
        return int((run_dir / OWNER_PID_FILE).read_text().strip())
    except (OSError, ValueError):
        return None


def run_state(run_dir: Path, proc_root: Path = Path("/proc")) -> str:
    pid = owner_pid(run_dir)
    if pid is not None and pid_alive(pid, proc_root):
        return STATE_LIVE
    if (run_dir / COMPLETE_MARKER).is_file():
        return STATE_COMPLETE
    return STATE_INCOMPLETE


def is_run_dir_name(name: str) -> bool:
    return RUN_ID_RE.match(name) is not None


def newest_run_dir(base: Path) -> Optional[Path]:
    if not base.is_dir():
        return None
    names = sorted(p.name for p in base.iterdir() if p.is_dir() and is_run_dir_name(p.name))
    return base / names[-1] if names else None


def resolve_run_dir(
    explicit: Optional[str] = None,
    *,
    base: Optional[Path] = None,
    env: Mapping[str, str] = os.environ,
) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            raise RunDirNotFound(f"not a directory: {explicit}")
        return p
    from_env = env.get(RUN_DIR_ENV)
    if from_env:
        p = Path(from_env).resolve()
        if not p.is_dir():
            raise RunDirNotFound(f"${RUN_DIR_ENV}={from_env} is not a directory")
        return p
    base = base if base is not None else default_archive_base(env)
    newest = newest_run_dir(base)
    if newest is None:
        raise RunDirNotFound(
            f"no run directory: none given, ${RUN_DIR_ENV} unset, and nothing under {base}"
        )
    return newest.resolve()


def announce(run_dir: Path, file=sys.stderr) -> str:
    line = f"run: {run_dir} ({run_state(run_dir)})"
    print(line, file=file)
    return line


def run_id_started(run_id: str) -> Optional[datetime]:
    m = RUN_ID_RE.match(run_id)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def read_run_env(run_dir: Path) -> dict[str, str]:
    """Parse the KEY="value" lines run_sim.sh writes to <run>/shadow_output/run_env.sh."""
    out: dict[str, str] = {}
    try:
        text = (run_dir / RUN_ENV_FILE).read_text()
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r'^([A-Z_][A-Z0-9_]*)="(.*)"$', line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def daemon_log_dir(run_dir: Path) -> Optional[Path]:
    """Where this run's monero-*/bitmonero.log files are right now:
    the archived daemon_logs/ if present, else the live /tmp namespace
    named in run_env.sh if it already holds logs, else None."""
    archived = run_dir / "daemon_logs"
    if archived.is_dir():
        return archived
    live = read_run_env(run_dir).get("MONEROSIM_DAEMON_DATA_DIR")
    if live and any(Path(live).glob("monero-*/bitmonero.log")):
        return Path(live)
    return None


@dataclass
class LiveRun:
    run_id: str
    pid: int
    source: str                  # "archive" (run dir known) or "tmp" (namespace only)
    run_dir: Optional[Path]
    tmp_dir: Optional[Path]
    started: Optional[datetime]


def list_live_runs(
    base: Path,
    *,
    tmp_root: Path = Path("/tmp"),
    exclude_pid: Optional[int] = None,
    proc_root: Path = Path("/proc"),
) -> list[LiveRun]:
    """Every run whose owner pid is alive, other than exclude_pid, found via
    <base>/*/.owner_pid and <tmp_root>/monerosim-*/.owner_pid, deduplicated
    by run id and sorted by run id."""
    found: dict[str, LiveRun] = {}
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if not d.is_dir() or not is_run_dir_name(d.name):
                continue
            pid = owner_pid(d)
            if pid is None or pid == exclude_pid or not pid_alive(pid, proc_root):
                continue
            tmp = tmp_root / f"{TMP_PREFIX}{d.name}"
            found[d.name] = LiveRun(d.name, pid, "archive", d, tmp if tmp.is_dir() else None,
                                    run_id_started(d.name))
    if tmp_root.is_dir():
        for d in sorted(tmp_root.glob(f"{TMP_PREFIX}*")):
            run_id = d.name[len(TMP_PREFIX):]
            if run_id in found or not d.is_dir():
                continue
            pid = owner_pid(d)
            if pid is None or pid == exclude_pid or not pid_alive(pid, proc_root):
                continue
            found[run_id] = LiveRun(run_id, pid, "tmp", None, d, run_id_started(run_id))
    return [found[k] for k in sorted(found)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/test_run_dirs.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_dirs.py scripts/test_run_dirs.py
git commit -m "feat(run-dirs): Python resolver for per-run directories (explicit > env > newest, live/complete/incomplete)"
```

---

### Task 2: `scripts/run_dir_lib.sh` — the bash twin, plus atomic run-dir allocation

**Files:**
- Create: `scripts/run_dir_lib.sh`
- Test: `scripts/test_run_dir_lib.py` (drives bash through subprocess)

**Interfaces:**
- Produces (used by Tasks 6, 8, 10, 11), all after `source scripts/run_dir_lib.sh`:
  - `run_dir_archive_base` echoes the base (`$MONEROSIM_ARCHIVE_BASE` or `<repo>/archived_runs`)
  - `run_dir_is_live DIR` returns 0 iff `DIR/.owner_pid` names a pid with `/proc/<pid>`
  - `run_dir_state DIR` echoes `live|complete|incomplete`
  - `newest_run_dir [BASE]` echoes the newest run dir, rc 1 if none
  - `resolve_run_dir [DIR]` echoes the resolved dir, prints `run: DIR (STATE)` to stderr, rc 2 if none
  - `allocate_run_dir BASE NAME` creates `BASE/<ts>_NAME` (suffix `_2`..`_99` on collision), writes `.owner_pid` = `$$`, echoes the run id; rc 1 after 99 collisions. `MONEROSIM_RUN_TS` overrides the timestamp (tests only).

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_run_dir_lib.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest scripts/test_run_dir_lib.py -q`
Expected: every test fails (bash reports `No such file or directory` for the lib).

- [ ] **Step 3: Write the library**

Create `scripts/run_dir_lib.sh`:

```bash
#!/bin/bash
#
# run_dir_lib.sh - resolve, classify and allocate monerosim run directories.
#
# Bash twin of scripts/run_dirs.py (keep them in sync). Sourced by run_sim.sh,
# scripts/check_sim.sh, start_here.sh and scripts/prune_archives.sh.
#
# A run lives for its whole life in <archive base>/<run_id>/ where
# run_id = YYYYmmdd_HHMMSS_<name>[_N]. Resolution order (resolve_run_dir):
#   1. explicit argument   2. $MONEROSIM_RUN_DIR   3. newest under the base.
# State (run_dir_state): live (.owner_pid names a process that exists),
# complete (summary.txt present), incomplete (neither).

# Guard against double-sourcing.
if [[ -n "${MONEROSIM_RUN_DIR_LIB_SOURCED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
MONEROSIM_RUN_DIR_LIB_SOURCED=1

_run_dir_lib_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# run_dir_archive_base -> echo $MONEROSIM_ARCHIVE_BASE or <repo>/archived_runs
run_dir_archive_base() {
    echo "${MONEROSIM_ARCHIVE_BASE:-$_run_dir_lib_root/archived_runs}"
}

# run_dir_is_live DIR -> 0 iff DIR/.owner_pid names a process that exists.
# /proc rather than `kill -0` so another user's run counts as live.
run_dir_is_live() {
    local pid
    pid=$(cat "$1/.owner_pid" 2>/dev/null) || return 1
    [[ "$pid" =~ ^[0-9]+$ ]] && [[ -d "/proc/$pid" ]]
}

# run_dir_state DIR -> echo live | complete | incomplete
run_dir_state() {
    if run_dir_is_live "$1"; then
        echo live
    elif [[ -f "$1/summary.txt" ]]; then
        echo complete
    else
        echo incomplete
    fi
}

# newest_run_dir [BASE] -> echo the lexically greatest YYYYmmdd_HHMMSS_* dir; rc 1 if none
newest_run_dir() {
    local base="${1:-$(run_dir_archive_base)}" name
    [[ -d "$base" ]] || return 1
    name=$(ls -1 "$base" 2>/dev/null | grep -E '^[0-9]{8}_[0-9]{6}_' | sort | tail -1)
    [[ -n "$name" && -d "$base/$name" ]] || return 1
    echo "$base/$name"
}

# resolve_run_dir [DIR] -> echo the run dir; "run: DIR (STATE)" on stderr; rc 2 if none
resolve_run_dir() {
    local dir
    if [[ -n "${1:-}" ]]; then
        dir="$1"
        [[ -d "$dir" ]] || { echo "run dir not a directory: $dir" >&2; return 2; }
    elif [[ -n "${MONEROSIM_RUN_DIR:-}" ]]; then
        dir="$MONEROSIM_RUN_DIR"
        [[ -d "$dir" ]] || { echo "MONEROSIM_RUN_DIR is not a directory: $dir" >&2; return 2; }
    else
        dir=$(newest_run_dir) || {
            echo "no run directory: none given, MONEROSIM_RUN_DIR unset, nothing under $(run_dir_archive_base)" >&2
            return 2
        }
    fi
    dir=$(readlink -f "$dir")
    echo "run: $dir ($(run_dir_state "$dir"))" >&2
    echo "$dir"
}

# allocate_run_dir BASE NAME -> mkdir BASE/<ts>_NAME atomically (suffix _2.._99
# on collision), write .owner_pid = $$ (the sourcing shell), echo the run id.
# rc 1 after 99 collisions. MONEROSIM_RUN_TS overrides the timestamp (tests).
allocate_run_dir() {
    local base="$1" name="$2" ts candidate n=1
    ts="${MONEROSIM_RUN_TS:-$(date '+%Y%m%d_%H%M%S')}"
    mkdir -p "$base"
    candidate="${ts}_${name}"
    until mkdir "$base/$candidate" 2>/dev/null; do
        n=$((n + 1))
        if (( n > 99 )); then
            echo "allocate_run_dir: 99 collisions for $base/${ts}_${name}" >&2
            return 1
        fi
        candidate="${ts}_${name}_${n}"
    done
    echo $$ > "$base/$candidate/.owner_pid"
    echo "$candidate"
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/test_run_dir_lib.py -q && bash -n scripts/run_dir_lib.sh`
Expected: all pass; `bash -n` silent. If `shellcheck` is installed: `shellcheck scripts/run_dir_lib.sh` reports nothing.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_dir_lib.sh scripts/test_run_dir_lib.py
git commit -m "feat(run-dirs): bash resolver + atomic allocate_run_dir with collision suffixes"
```

---

### Task 3: `run_sim_helpers.py` — completeness-gated learner, pure estimator, stop-time parser, parallelism field

**Files:**
- Modify: `scripts/run_sim_helpers.py:80-113` (`cmd_config_summary`), `:132-241` (`cmd_estimate_disk_mb`), argparse block near `:766-786`
- Test: `scripts/test_run_sim_helpers.py`

**Interfaces:**
- Produces (used by Task 4 and Task 7):
  - `parse_stop_time_hours(value) -> float` (`"6h"`→6.0, `"90m"`→1.5, `"23400s"`→6.5, `"21600"`→6.0, junk→0.0)
  - `config_counts(config_path: str) -> dict` with keys `total, miners, users, relays, fb_seeds, parallelism, sim_hours`
  - `estimate_disk_mb(archive_dir: str, num_miners: int, num_users: int, num_relays: int, num_hosts: int, sim_hours: float) -> tuple[float, dict, str]` returning `(estimated_mb, rates, source)`
  - `config-summary` stdout gains a sixth field: `<total> <miners> <users> <relays> <fb_seeds> <parallelism>` (Task 6 updates the `read -r` in run_sim.sh accordingly)
  - The learner inside `estimate_disk_mb` only samples archives that contain `summary.txt`.

- [ ] **Step 1: Write the failing tests**

Append to `scripts/test_run_sim_helpers.py` (and add `parse_stop_time_hours, config_counts, estimate_disk_mb` to the existing `from scripts.run_sim_helpers import (...)` list):

```python
# ---------------------------------------------------------------------------
# stop-time parsing, config_counts, completeness-gated disk learner
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw, hours", [
    ("6h", 6.0), ("90m", 1.5), ("23400s", 6.5), ("21600", 6.0), (21600, 6.0),
    ("", 0.0), ("soon", 0.0), (None, 0.0),
])
def test_parse_stop_time_hours(raw, hours):
    assert parse_stop_time_hours(raw) == pytest.approx(hours)


def test_config_counts_includes_parallelism_and_hours(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "general:\n  stop_time: 6h\n  parallelism: 4\n  fallback_seeds: auto\n"
        "agents:\n  miner-001: {}\n  user-001: {}\n  relay-001: {}\n"
    )
    c = config_counts(str(cfg))
    assert (c["total"], c["miners"], c["users"], c["relays"], c["fb_seeds"]) == (3, 1, 1, 1, 6)
    assert c["parallelism"] == 4 and c["sim_hours"] == 6.0


def test_config_counts_parallelism_defaults_to_zero(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("general:\n  stop_time: 1h\nagents:\n  miner-001: {}\n")
    assert config_counts(str(cfg))["parallelism"] == 0


def _archive(base, name, *, hours="2h", complete=True, host_kb=1024):
    run = base / name
    (run / "shadow.data" / "hosts" / "miner-001").mkdir(parents=True)
    (run / "shadow.data" / "hosts" / "miner-001" / "bash.1000.stdout").write_bytes(b"x" * host_kb * 1024)
    (run / "input_config.yaml").write_text(f"general:\n  stop_time: {hours}\nagents:\n  miner-001: {{}}\n")
    if complete:
        (run / "summary.txt").write_text("Exit code: 0\n")
    return run


def test_estimate_disk_mb_learns_only_from_complete_runs(tmp_path):
    # Newest archive is a LIVE/incomplete run with a tiny partial footprint;
    # the learner must skip it and use the older complete run instead.
    _archive(tmp_path, "20260904_120000_complete", host_kb=2048)   # 2 MB over 2h -> 1 MB/h
    _archive(tmp_path, "20260904_130000_live", complete=False, host_kb=1)
    est_mb, rates, source = estimate_disk_mb(str(tmp_path), 1, 0, 0, 1, 10.0)
    assert source == "learned from previous run"
    assert rates["miner"] == pytest.approx(1.0, rel=0.05)
    assert est_mb == pytest.approx(1.0 * 10 * 1.2, rel=0.05)


def test_estimate_disk_mb_defaults_without_history(tmp_path):
    est_mb, rates, source = estimate_disk_mb(str(tmp_path), 1, 1, 1, 3, 1.0)
    assert source == "default estimates"
    assert est_mb == pytest.approx((4.0 + 2.0 + 1.25) * 1.2)
```

Then change the two existing config-summary assertions to expect the sixth field:

```python
    assert out.strip() == "5 2 1 1 6 0"
```
and
```python
    total, miners, users, relays, fb, par = out.strip().split()
    assert (total, miners, users, relays, fb, par) == ("2", "1", "1", "0", "0", "0")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest scripts/test_run_sim_helpers.py -q`
Expected: ImportError on the new names.

- [ ] **Step 3: Implement**

In `scripts/run_sim_helpers.py`, replace `cmd_config_summary` (lines 80-113) with:

```python
_STOP_TIME_RE = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*([hms]?)\s*$')


def parse_stop_time_hours(value) -> float:
    """'6h' -> 6.0, '90m' -> 1.5, '23400s' -> 6.5, bare number = seconds; else 0.0."""
    m = _STOP_TIME_RE.match(str(value if value is not None else ''))
    if not m:
        return 0.0
    n, unit = float(m.group(1)), m.group(2)
    if unit == 'h':
        return n
    if unit == 'm':
        return n / 60
    return n / 3600


def config_counts(config_path: str) -> dict:
    """Agent counts + Shadow parallelism + sim hours from a config YAML.

    Keys: total, miners, users, relays, fb_seeds, parallelism (0 = unset/auto),
    sim_hours (0.0 if stop_time is missing or unparseable).
    """
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}
    general = cfg.get('general', {}) or {}
    meta = cfg.get('metadata', {}) or {}
    agents_meta = meta.get('agents', {}) or {}
    agents = cfg.get('agents', {}) or {}
    miners = agents_meta.get(
        'miners',
        sum(1 for a in agents if a.startswith('miner-0') or a.startswith('miner-1')),
    )
    users = agents_meta.get('users', sum(1 for a in agents if a.startswith('user-')))
    total = agents_meta.get('total', len(agents))
    relays = sum(1 for a in agents if a.startswith('relay-'))
    fb_mode = (general.get('fallback_seeds') or 'auto').lower()
    custom_seeds = sum(1 for a in agents if a.startswith('monero-seed-'))
    if fb_mode == 'off':
        fb_seeds = 0
    elif fb_mode == 'custom':
        fb_seeds = custom_seeds
    else:
        fb_seeds = 6
    try:
        parallelism = int(general.get('parallelism') or 0)
    except (TypeError, ValueError):
        parallelism = 0
    return {
        'total': total, 'miners': miners, 'users': users, 'relays': relays,
        'fb_seeds': fb_seeds, 'parallelism': parallelism,
        'sim_hours': parse_stop_time_hours(general.get('stop_time', '')),
    }


def cmd_config_summary(args: argparse.Namespace) -> int:
    """Print agent counts as a single space-separated line.

    Format (consumed by run_sim.sh:
    `read -r CFG_TOTAL CFG_MINERS CFG_USERS CFG_RELAYS CFG_FALLBACK_SEEDS CFG_PARALLELISM`):
        <total> <miners> <users> <relays> <fb_seeds> <parallelism>
    """
    c = config_counts(args.config)
    print(f"{c['total']} {c['miners']} {c['users']} {c['relays']} {c['fb_seeds']} {c['parallelism']}")
    return 0
```

Replace `cmd_estimate_disk_mb` (lines 132-241) with a pure function plus a thin command. Keep the existing docstring comments about the three archive subdirs; the changes are (a) the `summary.txt` gate, (b) `parse_stop_time_hours` instead of the two regexes, (c) the split:

```python
def estimate_disk_mb(archive_dir: str, num_miners: int, num_users: int,
                     num_relays: int, num_hosts: int, sim_hours: float) -> tuple[float, dict, str]:
    """Estimate disk usage (MB) for a run; returns (estimate_mb, rates, source).

    Learns per-host-type MB/hour rates from the most recent COMPLETE archive
    under `archive_dir` (one that has summary.txt — live and crashed runs
    are never samples), aggregating shadow.data/hosts, daemon_logs and the
    sampled blockchain snapshots. Falls back to conservative defaults.
    """
    defaults = {'miner': 4.0, 'user': 2.0, 'relay': 1.25, 'other': 0.5}
    learned: dict[str, float] = {}
    listing: Iterable[str] = (
        sorted(os.listdir(archive_dir), reverse=True) if os.path.isdir(archive_dir) else []
    )
    for run_name in listing:
        run_path = os.path.join(archive_dir, run_name)
        hosts_dir = os.path.join(run_path, 'shadow.data', 'hosts')
        daemon_logs_dir = os.path.join(run_path, 'daemon_logs')
        blockchain_dir = os.path.join(run_path, 'blockchain')
        cfg_path = os.path.join(run_path, 'input_config.yaml')
        if not os.path.isfile(os.path.join(run_path, 'summary.txt')):
            continue  # live or crashed run: partial footprint would skew the rate
        if not os.path.isdir(hosts_dir) or not os.path.isfile(cfg_path):
            continue
        try:
            import yaml
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            h = parse_stop_time_hours((cfg.get('general', {}) or {}).get('stop_time', ''))
            if h <= 0:
                continue
        except Exception:
            continue
        by_type_log: dict[str, list[float]] = {}
        by_type_chain: dict[str, list[float]] = {}
        for host in os.listdir(hosts_dir):
            host_path = os.path.join(hosts_dir, host)
            if not os.path.isdir(host_path):
                continue
            size_kb = _disk_kb(host_path)
            log_path = os.path.join(daemon_logs_dir, 'monero-' + host)
            if os.path.isdir(log_path):
                size_kb += _disk_kb(log_path)
            chain_path = os.path.join(blockchain_dir, 'monero-' + host)
            chain_kb = _disk_kb(chain_path) if os.path.isdir(chain_path) else None
            if host.startswith('miner-'):
                t = 'miner'
            elif host.startswith('user-'):
                t = 'user'
            elif host.startswith('relay-'):
                t = 'relay'
            else:
                t = 'other'
            by_type_log.setdefault(t, []).append(size_kb)
            if chain_kb is not None:
                by_type_chain.setdefault(t, []).append(chain_kb)
        for t, sizes in by_type_log.items():
            avg_mb = (sum(sizes) / len(sizes)) / 1024
            chain_sizes = by_type_chain.get(t, [])
            if chain_sizes:
                avg_mb += (sum(chain_sizes) / len(chain_sizes)) / 1024
            rate = avg_mb / h
            if t not in learned or len(sizes) > 10:
                learned[t] = rate
        break  # most recent complete run only

    rates = {**defaults, **learned}
    source = 'learned from previous run' if learned else 'default estimates'
    others = max(0, num_hosts - num_miners - num_users - num_relays)
    est = (
        num_miners * rates['miner'] + num_users * rates['user']
        + num_relays * rates['relay'] + others * rates['other']
    ) * sim_hours * 1.2
    return est, rates, source


def cmd_estimate_disk_mb(args: argparse.Namespace) -> int:
    """Print estimated MB to stdout; `RATES:<json>|SOURCE:<text>` to stderr."""
    est, rates, source = estimate_disk_mb(
        args.archive_dir, args.num_miners, args.num_users, args.num_relays,
        args.num_hosts, args.sim_hours,
    )
    print(f'{est:.0f}')
    print(f'RATES:{json.dumps(rates)}|SOURCE:{source}', file=sys.stderr)
    return 0
```

Update the `config-summary` parser help string to `'Print "<total> <miners> <users> <relays> <fb_seeds> <parallelism>" from config YAML.'`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/test_run_sim_helpers.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_sim_helpers.py scripts/test_run_sim_helpers.py
git commit -m "feat(helpers): completeness-gated disk learner, pure estimate_disk_mb, config_counts with parallelism"
```

---

### Task 4: `run_sim_helpers.py live-runs` — the concurrency report subcommand

**Files:**
- Modify: `scripts/run_sim_helpers.py` (new command + parser entry after `estimate-disk-mb`)
- Test: `scripts/test_run_sim_helpers.py`

**Interfaces:**
- Consumes: Task 1 `list_live_runs`, Task 3 `config_counts`, `estimate_disk_mb`, existing `_disk_kb`.
- Produces: `python3 scripts/run_sim_helpers.py live-runs --archive-base B --exclude-pid PID [--tmp-root /tmp]` printing one TSV line per live run:
  `run_id \t pid \t elapsed_s \t daemons \t used_kb \t est_total_kb|- \t remaining_kb|- \t source \t parallelism|-`
  (`elapsed_s` is `-1` when the run id has no parseable timestamp; `parallelism` is the run's `general.parallelism`, `0` meaning auto). Task 7 consumes this.

- [ ] **Step 1: Write the failing test**

Append to `scripts/test_run_sim_helpers.py`:

```python
def test_live_runs_tsv(tmp_path, capsys, monkeypatch):
    import scripts.run_sim_helpers as helpers
    base = tmp_path / "archived_runs"
    tmp_root = tmp_path / "tmp"
    proc = tmp_path / "proc"
    (proc / "4242").mkdir(parents=True)
    # Live run with a parseable config: 1 miner, 2h, parallelism 2, 1 MB used.
    run = base / "20260904_120000_a"
    (run / "shadow.data" / "hosts").mkdir(parents=True)
    (run / "big.bin").write_bytes(b"x" * 1024 * 1024)
    (run / ".owner_pid").write_text("4242")
    (run / "input_config.yaml").write_text(
        "general:\n  stop_time: 2h\n  parallelism: 2\nagents:\n  miner-001: {}\n"
    )
    ns = tmp_root / "monerosim-20260904_120000_a"
    (ns / "monero-miner-001").mkdir(parents=True)
    (ns / ".owner_pid").write_text("4242")
    # Live run known only from /tmp (other checkout): no estimate.
    other = tmp_root / "monerosim-20260904_130000_other"
    other.mkdir()
    (other / ".owner_pid").write_text("4242")

    monkeypatch.setattr(helpers.run_dirs, "pid_alive", lambda pid, proc_root=None: (proc / str(pid)).exists())
    _, out = _run(capsys, ["live-runs", "--archive-base", str(base), "--exclude-pid", "1",
                           "--tmp-root", str(tmp_root)])
    rows = [line.split("\t") for line in out.strip().splitlines()]
    assert [r[0] for r in rows] == ["20260904_120000_a", "20260904_130000_other"]
    a, o = rows
    assert a[1] == "4242" and int(a[2]) >= 0 and a[3] == "1" and a[7] == "archive" and a[8] == "2"
    used_kb, est_kb, rem_kb = float(a[4]), float(a[5]), float(a[6])
    assert used_kb >= 1024                                  # the 1 MB file
    assert est_kb == pytest.approx(4.0 * 2 * 1.2 * 1024)   # default miner rate, 2h, margin
    assert rem_kb == pytest.approx(max(0.0, est_kb - used_kb))
    assert o[3] == "0" and o[5] == "-" and o[6] == "-" and o[7] == "tmp" and o[8] == "-"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest scripts/test_run_sim_helpers.py::test_live_runs_tsv -q`
Expected: `AttributeError: module ... has no attribute 'run_dirs'` (or argparse "invalid choice: 'live-runs'").

- [ ] **Step 3: Implement**

At the top of `scripts/run_sim_helpers.py`, after `from typing import Iterable`, add:

```python
from datetime import datetime
from pathlib import Path

try:  # imported as scripts.run_sim_helpers (tests)
    from scripts import run_dirs
except ImportError:  # invoked as `python3 scripts/run_sim_helpers.py`
    import run_dirs  # type: ignore
```

After `cmd_estimate_disk_mb` add:

```python
def cmd_live_runs(args: argparse.Namespace) -> int:
    """One TSV line per live run_sim.sh run on this box other than --exclude-pid.

    run_id  pid  elapsed_s  daemons  used_kb  est_total_kb|-  remaining_kb|-  source  parallelism|-

    Consumed by check_disk_space() in run_sim.sh to reserve the other runs'
    projected growth before comparing free space with this run's estimate.
    """
    runs = run_dirs.list_live_runs(
        Path(args.archive_base), tmp_root=Path(args.tmp_root), exclude_pid=args.exclude_pid,
    )
    now = datetime.now()

    def fmt(v):
        return '-' if v is None else f'{v:.0f}'

    for r in runs:
        elapsed = int((now - r.started).total_seconds()) if r.started else -1
        daemons = len(list(r.tmp_dir.glob('monero-*'))) if r.tmp_dir else 0
        used_kb = 0.0
        if r.run_dir:
            used_kb += _disk_kb(str(r.run_dir))
        if r.tmp_dir:
            used_kb += _disk_kb(str(r.tmp_dir))
        est_kb = rem_kb = par = None
        cfg_path = r.run_dir / 'input_config.yaml' if r.run_dir else None
        if cfg_path and cfg_path.is_file():
            try:
                c = config_counts(str(cfg_path))
                hosts = c['total'] + c['fb_seeds']
                est_mb, _, _ = estimate_disk_mb(
                    args.archive_base, c['miners'], c['users'], c['relays'], hosts,
                    max(1.0, c['sim_hours']),
                )
                est_kb = est_mb * 1024
                rem_kb = max(0.0, est_kb - used_kb)
                par = c['parallelism']
            except Exception:
                est_kb = rem_kb = par = None
        print('\t'.join([
            r.run_id, str(r.pid), str(elapsed), str(daemons), f'{used_kb:.0f}',
            fmt(est_kb), fmt(rem_kb), r.source, '-' if par is None else str(par),
        ]))
    return 0
```

In `build_parser()`, after the `estimate-disk-mb` block:

```python
    # live-runs
    p_lr = sub.add_parser(
        'live-runs',
        help='TSV of other live run_sim.sh runs on this box (for the concurrency-aware preflight).',
    )
    p_lr.add_argument('--archive-base', required=True)
    p_lr.add_argument('--exclude-pid', type=int, default=None)
    p_lr.add_argument('--tmp-root', default='/tmp')
    p_lr.set_defaults(func=cmd_live_runs)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/test_run_sim_helpers.py scripts/test_run_dirs.py -q`
Expected: all pass. Also run `python3 scripts/run_sim_helpers.py live-runs --archive-base archived_runs --exclude-pid $$` from the checkout root: it prints one line per live run on the box (there may be several owned by another user) or nothing, and exits 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_sim_helpers.py scripts/test_run_sim_helpers.py
git commit -m "feat(helpers): live-runs subcommand reporting other runs' usage and projected growth"
```

---

### Task 5: Monitor path discovery prefers the output directory

**Files:**
- Modify: `agents/simulation_monitor/status_paths.py:28-38`
- Test: `agents/test_status_paths.py` (new)

**Interfaces:**
- `find_shadow_data_hosts(output_dir: Optional[Path]) -> Optional[Path]` keeps its signature; candidate order becomes `output_dir/shadow.data/hosts`, `output_dir/hosts`, `output_dir.parent/shadow.data/hosts`, then `./shadow.data/hosts`, then `cwd/shadow.data/hosts`.

- [ ] **Step 1: Write the failing test**

Create `agents/test_status_paths.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest agents/test_status_paths.py -q`
Expected: `test_output_dir_sibling_wins_over_cwd` fails (returns the cwd path).

- [ ] **Step 3: Reorder the candidates**

Replace the body of `find_shadow_data_hosts` from `# Shadow creates shadow.data in its cwd` through the `if output_dir:` block with:

```python
    # Since 2026-09 run_sim.sh points Shadow's -d at <run_dir>/shadow.data,
    # next to the generator's <run_dir>/shadow_output (our output_dir), so
    # the output-relative candidates come first. The cwd-relative ones are
    # a last resort for hand-run Shadow invocations: with several runs per
    # checkout a stale <checkout>/shadow.data must never win.
    candidates = []
    if output_dir:
        candidates += [
            output_dir / "shadow.data" / "hosts",
            output_dir / "hosts",
            output_dir.parent / "shadow.data" / "hosts",
        ]
    candidates += [
        Path("shadow.data") / "hosts",           # Relative to cwd (where Shadow runs)
        Path.cwd() / "shadow.data" / "hosts",    # Absolute cwd
    ]
```

Also update the docstring's first paragraph to: `"""Find the shadow.data/hosts directory for this run (output-dir-relative first, cwd last)."""`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/test_status_paths.py agents/test_simulation_monitor.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add agents/simulation_monitor/status_paths.py agents/test_status_paths.py
git commit -m "fix(monitor): prefer output-dir-relative shadow.data over cwd (concurrent runs per checkout)"
```

---

### Task 6: `run_sim.sh` — per-run layout

**Files:**
- Modify: `run_sim.sh` (help text `:74-75`, `:86-96`, `:105-108`; variables `:33-48`, `:178`, `:216`, `:220`; `check_disk_space` `:647-660`, `:702`; `build_and_generate` `:746-749`, `:758-759`, `:872-877`; `run_simulation` `:885-906`; monitor trap `:1037`; `archive_results` `:1293-1300`; `preflight_checks` `:640`; `main` `:1731-1739`)

**Interfaces:**
- Consumes: Task 2 `allocate_run_dir`, `run_dir_lib.sh`; Task 3 six-field `config-summary`.
- Produces: `RUN_DIR` (== `ARCHIVE_DIR`), `DATA_DIR=$RUN_DIR/shadow.data` (or `$DATA_BASE/$RUN_ID/shadow.data`), `SHADOW_OUTPUT=$RUN_DIR/shadow_output`, exported `MONEROSIM_RUN_DIR`, `run_env.sh` with `MONEROSIM_RUN_DIR`, `MONEROSIM_SHADOW_DATA_DIR`, `MONEROSIM_SHADOW_OUTPUT_DIR`; `CFG_PARALLELISM` for Task 7.

- [ ] **Step 1: Variables and argument parsing**

Near line 33 (`RUN_NAME=""`) add:
```bash
DATA_BASE=""              # --data-dir: base under which <run_id>/shadow.data is placed (scratch volume)
RUN_DIR=""                # == ARCHIVE_DIR; the run's only home for its whole life
```
Change the `--data-dir)` case (line ~178) from `DATA_DIR="$2"` to `DATA_BASE="$2"`.
Delete line 216 (`[[ -z "$DATA_DIR" ]] && DATA_DIR="$SCRIPT_DIR/shadow.data"`) and replace it with:
```bash
DATA_DIR=""               # set in build_and_generate(): $RUN_DIR/shadow.data (Shadow creates it)
```
Change line 220 to:
```bash
SHADOW_OUTPUT=""          # set in build_and_generate(): $RUN_DIR/shadow_output
```
Right after the existing `source "$SCRIPT_DIR/scripts/log_lib.sh"` line (search for it; it is near the top), add:
```bash
# shellcheck source=scripts/run_dir_lib.sh
source "$SCRIPT_DIR/scripts/run_dir_lib.sh"
```

- [ ] **Step 2: Help text**

Replace the `--data-dir` lines (74-75) with:
```
  --data-dir <base>      Put this run's Shadow data at <base>/<run_id>/shadow.data
                         instead of archived_runs/<run_id>/shadow.data (e.g. a
                         scratch volume); it is moved into the run dir at the end.
```
Replace the `--preflight-only` explanation line `and exit. Does NOT touch shadow.data, /tmp, or` with `and exit. Creates no run directory, touches nothing in /tmp, does not`.
In the `--no-archive` block replace `and summary.txt are NOT preserved.` with `and summary.txt are NOT preserved (<run_dir>/shadow.data is deleted at the end).`
Replace the `Concurrency:` paragraph (105-108) with:
```
Concurrency: every run lives in its own archived_runs/<run_id>/ (shadow.data,
shadow_output, logs) and its own /tmp/monerosim-<run_id>/ daemon namespace, so
any number of runs can be launched concurrently FROM THIS CHECKOUT. Preflight
lists the other live runs and reserves their projected disk growth.
```

- [ ] **Step 3: Preflight reads six fields; disk check measures the bases**

Line 640: `read -r CFG_TOTAL CFG_MINERS CFG_USERS CFG_RELAYS CFG_FALLBACK_SEEDS CFG_PARALLELISM <<< "$CONFIG_SUMMARY"`.

In `check_disk_space` replace lines 650-657 (from `# Create dirs if needed` through `free_kb=...`) with:
```bash
    # Create the archive base if needed (for df). The run dir itself is only
    # created in build_and_generate(), so --preflight-only leaves no trace.
    mkdir -p "$archive_dir"
    local data_parent="${DATA_BASE:-$archive_dir}"
    [[ -n "$DATA_BASE" ]] && mkdir -p "$DATA_BASE"
    local free_kb
    free_kb=$(df -k "$data_parent" | tail -1 | awk '{print $4}')
```
and line 702 `log_info "Free disk space: ... (on $(dirname "$DATA_DIR"))"` to `log_info "Free disk space: $(format_kb "$free_kb") (on $data_parent)"`.

- [ ] **Step 4: Phase 2 allocates the run directory**

Replace lines 746-749 (`# Create archive directory with timestamp` through `log_ok "Archive directory: ..."`) with:
```bash
    # Allocate the run directory: the run's only home for its whole life
    # (shadow_output/, shadow.data/, logs, and the archive phase's copies).
    # Atomic mkdir with _2.._99 suffixes so two launches in the same second
    # never share a directory; .owner_pid marks it live for other tools.
    RUN_ID=$(allocate_run_dir "$ARCHIVE_BASE" "$RUN_NAME") || {
        log_err "Could not allocate a run directory under $ARCHIVE_BASE"
        exit 1
    }
    RUN_DIR="$ARCHIVE_BASE/$RUN_ID"
    ARCHIVE_DIR="$RUN_DIR"
    SHADOW_OUTPUT="$RUN_DIR/shadow_output"
    if [[ -n "$DATA_BASE" ]]; then
        DATA_DIR="$DATA_BASE/$RUN_ID/shadow.data"
        mkdir -p "$DATA_BASE/$RUN_ID"
        if [[ -e "$DATA_DIR" ]]; then
            log_err "Scratch data dir already exists: $DATA_DIR (Shadow refuses an existing -d path)"
            exit 1
        fi
    else
        DATA_DIR="$RUN_DIR/shadow.data"
    fi
    export MONEROSIM_RUN_DIR="$RUN_DIR"
    log_ok "Run directory: $RUN_DIR"
```
Then replace lines 758-759 (`RUN_ID="${TIMESTAMP}_${RUN_NAME}"` and `RUN_TMP_DIR=...`) with just:
```bash
    RUN_TMP_DIR="/tmp/monerosim-${RUN_ID}"
```
(`TIMESTAMP` is no longer used in this function; grep the file for other uses of `$TIMESTAMP` and, if any remain, set `TIMESTAMP="${RUN_ID:0:15}"` right after `RUN_DIR=` above.)

- [ ] **Step 5: run_env.sh breadcrumb gains the run paths**

Replace the block at lines 872-877 with:
```bash
    {
        echo "MONEROSIM_RUN_ID=\"$RUN_ID\""
        echo "MONEROSIM_RUN_DIR=\"$(readlink -f "$RUN_DIR")\""
        echo "MONEROSIM_SHADOW_DATA_DIR=\"$(readlink -f "$(dirname "$DATA_DIR")")/shadow.data\""
        echo "MONEROSIM_SHADOW_OUTPUT_DIR=\"$(readlink -f "$SHADOW_OUTPUT")\""
        echo "MONEROSIM_DAEMON_DATA_DIR=\"$DAEMON_DATA_BASE\""
        echo "MONEROSIM_SHARED_DIR=\"$SHARED_DIR\""
    } > "$SHADOW_OUTPUT/run_env.sh"
```
(`readlink -f` on the data dir's parent because `shadow.data` itself does not exist yet.)

- [ ] **Step 6: Phase 3 no longer wipes anything**

Delete lines 885-906 in `run_simulation` (from `# Clean old simulation data.` through `rm -rf "$DATA_DIR" shadow.log`) and put nothing in their place. Shadow creates `$DATA_DIR` itself.

- [ ] **Step 7: Status hint names the run**

Line 1037: `echo "Check status:      ./scripts/check_sim.sh $ARCHIVE_DIR"`.

- [ ] **Step 8: Archive step 5a only moves scratch data**

Replace lines 1293-1300 (`# 5a. Shadow data` block) with:
```bash
    # 5a. Shadow data: already in the run dir unless --data-dir put it on a
    # scratch volume, in which case move it home (cross-fs move = copy).
    if [[ "$DATA_DIR" != "$RUN_DIR/shadow.data" ]]; then
        if [[ -d "$DATA_DIR" ]]; then
            log_info "Moving $DATA_DIR into the run dir..."
            mv "$DATA_DIR" "$RUN_DIR/shadow.data"
            rmdir "$(dirname "$DATA_DIR")" 2>/dev/null || true
            DATA_DIR="$RUN_DIR/shadow.data"
            log_ok "shadow.data moved into run dir"
        else
            log_warn "$DATA_DIR not found"
        fi
    else
        log_ok "shadow.data already in run dir"
    fi
```

- [ ] **Step 9: `--no-archive` deletes the bulky data it promises not to keep**

In `main()` (lines 1731-1739) after `log_warn "remain in $ARCHIVE_DIR."` add:
```bash
        rm -rf "$RUN_DIR/shadow.data"
        if [[ "$DATA_DIR" != "$RUN_DIR/shadow.data" && -d "$DATA_DIR" ]]; then
            rm -rf "$DATA_DIR"
            rmdir "$(dirname "$DATA_DIR")" 2>/dev/null || true
        fi
```

- [ ] **Step 10: Static verification**

Run:
```bash
bash -n run_sim.sh && (command -v shellcheck >/dev/null && shellcheck -S warning run_sim.sh || true)
grep -n 'SCRIPT_DIR/shadow\.data\|SCRIPT_DIR/shadow_output\|rm -rf "\$DATA_DIR"\|shadow\.log' run_sim.sh
```
Expected: `bash -n` silent; the grep prints only help/comment lines (no code path referencing the checkout-root paths, no `rm -rf "$DATA_DIR"`, no `shadow.log`).

Then:
```bash
before=$(ls -A | sort); ./run_sim.sh --config test_configs/quickstart.yaml --preflight-only; after=$(ls -A | sort); diff <(echo "$before") <(echo "$after") && echo ROOT-UNCHANGED
ls -d archived_runs/*quickstart* 2>/dev/null | tail -1
```
Expected: preflight passes, `ROOT-UNCHANGED`, and no new `archived_runs/<now>_quickstart` directory was created by the preflight.

- [ ] **Step 11: One real run into the run directory**

Run (30-60 min wall; the box is shared, use nice):
```bash
nice ./run_sim.sh --config test_configs/quickstart.yaml --name layout_check --no-monitor
```
Then:
```bash
R=$(ls -d archived_runs/*_layout_check | tail -1); echo "$R"
ls "$R" | tr '\n' ' '; echo
test -f "$R/summary.txt" && test -d "$R/shadow.data/hosts" && test -f "$R/shadow_output/run_env.sh" && test -f "$R/.owner_pid" && echo LAYOUT-OK
cat "$R/shadow_output/run_env.sh"
grep -E 'Exit code|Sync:' "$R/summary.txt"
test ! -e shadow.log && echo NO-ROOT-SHADOW-LOG
python3 scripts/smoke_assertions.py --run-dir "$R"
```
Expected: `LAYOUT-OK`; `run_env.sh` shows the six variables with absolute run paths; `Exit code: 0` and `Sync: 100%`; `NO-ROOT-SHADOW-LOG`; smoke assertions pass against `tests/baselines/quickstart_metrics.json`. (The stale root-level `shadow.data/` and `shadow_output/` from before this change, if present, are untouched: compare their mtimes.)

- [ ] **Step 12: Commit**

```bash
git add run_sim.sh
git commit -m "feat(run_sim): per-run directories — shadow.data/shadow_output live under archived_runs/<run_id>/, no root writes"
```

---

### Task 7: Concurrency-aware preflight

**Files:**
- Modify: `run_sim.sh` `check_disk_space` (after `free_kb` is computed, and the comparison block at `:707-737`)

**Interfaces:**
- Consumes: Task 4 `live-runs` TSV, `CFG_PARALLELISM` from Task 6, existing `format_kb`, `format_duration`.

- [ ] **Step 1: Add the live-run report and effective free space**

In `check_disk_space`, immediately after `archive_free_kb=$(df -k ...)` insert:
```bash
    # Other live runs on this box. Their projected remaining growth is
    # reserved out of free space so one launch cannot fill the disk that
    # all of them share. Runs known only from /tmp (another checkout or
    # archive base) have no estimate and are reported as such.
    local nproc_n
    nproc_n=$(nproc 2>/dev/null || echo 0)
    local live_tsv other_remaining_kb=0 other_unknown=0 other_count=0 other_parallelism=0
    live_tsv=$(python3 scripts/run_sim_helpers.py live-runs \
        --archive-base "$archive_dir" --exclude-pid $$ 2>/dev/null || true)
    if [[ -n "$live_tsv" ]]; then
        log_info "Other live runs on this box:"
        local rid pid elapsed daemons used est rem src par el_txt est_txt
        while IFS=$'\t' read -r rid pid elapsed daemons used est rem src par; do
            [[ -n "$rid" ]] || continue
            other_count=$((other_count + 1))
            el_txt="?"; [[ "$elapsed" -ge 0 ]] && el_txt=$(format_duration "$elapsed")
            if [[ "$rem" != "-" ]]; then
                other_remaining_kb=$((other_remaining_kb + rem))
                est_txt="est. total $(format_kb "$est"), remaining $(format_kb "$rem")"
            else
                other_unknown=$((other_unknown + 1))
                est_txt="no estimate"
            fi
            [[ "$par" == "-" ]] && par=0
            (( par == 0 )) && par=$nproc_n
            other_parallelism=$((other_parallelism + par))
            log_info "  $rid  pid $pid  up $el_txt  $daemons daemons  used $(format_kb "$used")  ($est_txt) [$src]"
        done <<< "$live_tsv"
        log_info "  Reserving $(format_kb "$other_remaining_kb") for their projected growth ($other_unknown of $other_count with no estimate)"
    else
        log_info "Other live runs on this box: none"
    fi
    local effective_free_kb=$((free_kb - other_remaining_kb))
    (( effective_free_kb < 0 )) && effective_free_kb=0
```

- [ ] **Step 2: Compare against effective free space**

In the block starting `if [[ "$estimated_kb" -gt "$free_kb" ]]; then` (line ~707) replace every `$free_kb` inside the `if`/`elif`/`else` chain with `$effective_free_kb` (five occurrences: the condition, `Available:`, `Shortfall:`, the `elif`, and the two messages), and change the `Available:` line to:
```bash
        log_info "  Available: $(format_kb "$effective_free_kb") (free $(format_kb "$free_kb") minus $(format_kb "$other_remaining_kb") reserved for $other_count live runs)"
```
Keep the `log_info "Free disk space: ..."` line as is (raw free), and add right after it:
```bash
    (( other_remaining_kb > 0 )) && log_info "Effective free space: $(format_kb "$effective_free_kb") after reserving other live runs' growth"
```

- [ ] **Step 3: Worker-thread line**

After the disk comparison chain (end of `check_disk_space`, before its closing `}`) add:
```bash
    # Informational: Shadow worker threads across all live runs vs cores.
    # 0 (auto) counts as every core. Never blocks: contention slows wall
    # clock but leaves simulation results unchanged.
    local this_par="${CFG_PARALLELISM:-0}"
    (( this_par == 0 )) && this_par=$nproc_n
    local total_par=$((this_par + other_parallelism))
    if (( nproc_n > 0 && total_par > nproc_n )); then
        log_warn "Shadow worker threads: this run $this_par + other live runs $other_parallelism = $total_par > $nproc_n cores (wall clock will suffer; results unaffected)"
    else
        log_info "Shadow worker threads: this run $this_par + other live runs $other_parallelism = $total_par of $nproc_n cores"
    fi
```

- [ ] **Step 4: Verify**

Run:
```bash
bash -n run_sim.sh
./run_sim.sh --config test_configs/quickstart.yaml --preflight-only
```
Expected: the preflight output contains `Other live runs on this box:` followed either by `none` or one line per live run (this box usually has several owned by another user; they appear with `[tmp]` and `no estimate` when their run dirs are not under this archive base), a `Reserving ...` line when any had an estimate, and the `Shadow worker threads:` line. Exit 0.

To exercise the reservation path deterministically, fake a live run and re-run preflight:
```bash
F=archived_runs/20260904_000000_fakelive; mkdir -p "$F"; echo $$ > "$F/.owner_pid"; cp test_configs/quickstart.yaml "$F/input_config.yaml"
./run_sim.sh --config test_configs/quickstart.yaml --preflight-only | grep -E 'fakelive|Reserving|Effective|worker threads'
rm -rf "$F"
```
Expected: a `20260904_000000_fakelive` line with `est. total ... remaining ...` and `[archive]`, a `Reserving` line with a non-zero amount, an `Effective free space` line, and the thread line.

- [ ] **Step 5: Commit**

```bash
git add run_sim.sh
git commit -m "feat(run_sim): concurrency-aware preflight — list live runs, reserve their growth, sum worker threads"
```

---

### Task 8: `check_sim.sh` and `start_here.sh` on the run-directory contract

**Files:**
- Modify: `scripts/check_sim.sh:1-125` (header, daemon-base block, locate block), `:229-244` (Process Status)
- Modify: `start_here.sh:558-575`, `:603-624`
- Test: `scripts/test_check_sim.py` (new, subprocess)

**Interfaces:**
- Consumes: Task 2 `resolve_run_dir`, `run_dir_state`.
- Produces: `scripts/check_sim.sh [RUN_DIR]` (a `shadow.data` path is accepted and mapped to its run dir).

- [ ] **Step 1: Write the failing test**

Create `scripts/test_check_sim.py`:

```python
"""check_sim.sh resolves a run directory and reads that run's data only."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fixture_run(tmp_path, *, live=True):
    run = tmp_path / "archived_runs" / "20260904_120000_fx"
    host = run / "shadow.data" / "hosts" / "miner-001"
    host.mkdir(parents=True)
    (host / "bash.1000.stdout").write_text(
        "2000-01-01 00:10:00 AutonomousMiner starting\n2000-01-01 01:00:00 New height: 5\n"
    )
    (run / "input_config.yaml").write_text("general:\n  stop_time: 6h\nagents:\n  miner-001: {}\n")
    live_ns = tmp_path / "ns"
    (live_ns / "monero-miner-001").mkdir(parents=True)
    (live_ns / "monero-miner-001" / "bitmonero.log").write_text("2000-01-01 01:00:00 I Synced 5/5\n")
    (run / "shadow_output").mkdir()
    (run / "shadow_output" / "run_env.sh").write_text(
        f'MONEROSIM_RUN_ID="20260904_120000_fx"\nMONEROSIM_RUN_DIR="{run}"\n'
        f'MONEROSIM_SHADOW_DATA_DIR="{run}/shadow.data"\nMONEROSIM_DAEMON_DATA_DIR="{live_ns}"\n'
    )
    (run / ".owner_pid").write_text(str(os.getpid() if live else 2**22 - 1))
    return run


def _check(args, env=None):
    e = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/"), "VIRTUAL_ENV": "x"}
    e.update(env or {})
    return subprocess.run(["bash", str(ROOT / "scripts" / "check_sim.sh"), *args],
                          capture_output=True, text=True, env=e, cwd=ROOT)


def test_explicit_run_dir_live(tmp_path):
    run = _fixture_run(tmp_path)
    r = _check([str(run)])
    assert r.returncode == 0, r.stderr
    assert f"run: {run} (live)" in r.stderr
    assert "miner-001: height 5" in r.stdout
    assert "Sim time: 2000-01-01 01:00:00" in r.stdout


def test_shadow_data_path_maps_to_run_dir(tmp_path):
    run = _fixture_run(tmp_path, live=False)
    r = _check([str(run / "shadow.data")])
    assert r.returncode == 0, r.stderr
    assert f"run: {run} (incomplete)" in r.stderr


def test_newest_run_under_archive_base(tmp_path):
    run = _fixture_run(tmp_path, live=False)
    r = _check([], env={"MONEROSIM_ARCHIVE_BASE": str(tmp_path / "archived_runs")})
    assert r.returncode == 0, r.stderr
    assert f"run: {run} (incomplete)" in r.stderr


def test_no_run_is_an_error(tmp_path):
    r = _check([], env={"MONEROSIM_ARCHIVE_BASE": str(tmp_path / "none")})
    assert r.returncode != 0 and "no run directory" in r.stderr
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest scripts/test_check_sim.py -q`
Expected: failures (no `run:` line; explicit `shadow.data` arg not mapped; auto-detect looks for a running Shadow).

- [ ] **Step 3: Rewrite the locate section of `check_sim.sh`**

Replace the header comment (lines 2-13) with:
```bash
# check_sim.sh - Quick status check for a MoneroSim simulation
#
# Usage: ./check_sim.sh [RUN_DIR]
#
# RUN_DIR resolves as: explicit argument > $MONEROSIM_RUN_DIR > newest under
# archived_runs/ ($MONEROSIM_ARCHIVE_BASE). A shadow.data/ path is accepted
# too. The chosen run is echoed as "run: <dir> (live|complete|incomplete)".
# Daemon logs come from <run>/daemon_logs/ (archived) or the live /tmp
# namespace breadcrumbed in <run>/shadow_output/run_env.sh.
```
Replace everything from `# Live-run daemon data base:` (line 30) through the end of the `RUN_DIR` walk-up block (line 125, just before `# Parse config for timeline milestones`) with:
```bash
# shellcheck source=run_dir_lib.sh
source "$SCRIPT_DIR/run_dir_lib.sh"

# ============================================================
# Resolve the run directory
# ============================================================
ARG="${1:-}"
if [[ -n "$ARG" && -d "$ARG/hosts" && "$(basename "$(readlink -f "$ARG")")" == "shadow.data" ]]; then
    ARG="$(dirname "$(readlink -f "$ARG")")"
fi
RUN_DIR=$(resolve_run_dir "$ARG") || {
    log_info "Pass a run directory:  $0 archived_runs/<run_id>"
    exit 1
}
RUN_STATE=$(run_dir_state "$RUN_DIR")
LOG_SOURCE="$RUN_STATE"

# Breadcrumbs written by run_sim.sh (absent for hand-run Shadow invocations).
if [[ -f "$RUN_DIR/shadow_output/run_env.sh" ]]; then
    # shellcheck source=/dev/null
    source "$RUN_DIR/shadow_output/run_env.sh"
fi
SHADOW_DATA_DIR="${MONEROSIM_SHADOW_DATA_DIR:-$RUN_DIR/shadow.data}"
[[ -d "$SHADOW_DATA_DIR/hosts" ]] || SHADOW_DATA_DIR="$RUN_DIR/shadow.data"
HOSTS_DIR="$SHADOW_DATA_DIR/hosts"
if [[ ! -d "$HOSTS_DIR" ]]; then
    log_err "No shadow.data/hosts under $RUN_DIR (not started yet, pruned, or --no-archive)"
    exit 1
fi
HOSTS_DIR=$(readlink -f "$HOSTS_DIR")

# Daemon logs: archived copy, else the live namespace, else legacy /tmp.
if [[ -d "$RUN_DIR/daemon_logs" ]]; then
    DAEMON_DATA_BASE="$RUN_DIR/daemon_logs"
else
    DAEMON_DATA_BASE="${MONEROSIM_DAEMON_DATA_DIR:-/tmp}"
fi

CONFIG_FILE=""
[[ -f "$RUN_DIR/input_config.yaml" ]] && CONFIG_FILE=$(readlink -f "$RUN_DIR/input_config.yaml")

# THIS run's Shadow process (runs are concurrent: never "any shadow on the box").
SHADOW_PID=$(pgrep -u "$(id -u)" -f -- "shadow -d $SHADOW_DATA_DIR " 2>/dev/null | head -1 || true)
```
Replace the Process Status section body (lines 229-244, from `if [[ "$LOG_SOURCE" != "specified" ]]; then` through the matching `fi`) with:
```bash
if [ -n "$SHADOW_PID" ]; then
    log_ok "Shadow running (PID $SHADOW_PID)"
    ELAPSED=$(ps -o etime= -p "$SHADOW_PID" 2>/dev/null | xargs)
    log_info "Wall-clock elapsed: ${ELAPSED:-unknown}"
elif [[ "$RUN_STATE" == "live" ]]; then
    log_warn "run_sim.sh is alive (pid $(cat "$RUN_DIR/.owner_pid")) but no Shadow process for this run (starting up or archiving?)"
else
    log_info "Viewing $RUN_STATE run"
fi
log_info "Run dir:   $RUN_DIR ($RUN_STATE)"
```
Keep the following `log_info "Hosts dir: ..."` and config lines.

- [ ] **Step 4: `start_here.sh` picker**

Replace lines 558-561 (the `if [[ -d shadow.data ]] ...` LIVE block) with nothing, and change the `archived_runs` loop label to include the state. After `source "$(dirname ...)/scripts/log_lib.sh"` at the top of `start_here.sh` add `source "$(dirname "${BASH_SOURCE[0]}")/scripts/run_dir_lib.sh"` (mirror the exact form the file uses for log_lib.sh). In the loop replace `labels+=("${path##*/}")` with `labels+=("${path##*/}  ($(run_dir_state "$path"))")`. Replace the `if [[ ${#targets[@]} -eq 0 ]]` message with `log_warn "No entries in archived_runs/."`.
Replace lines 603-624 (from `if [[ "$target" == "LIVE" ]]; then` through the `fi` that closes the archive-missing check) with:
```bash
    data_dir="$target/shadow.data"
    out_dir="$target/analysis_output"
    if [[ "$(run_dir_state "$target")" == "live" ]] && [[ ! -d "$target/daemon_logs" ]]; then
        # Live run: daemon logs are still in the /tmp namespace breadcrumbed
        # by run_sim.sh. Export it so tx-analyzer's env-based defaults
        # (--log-dir omitted, --shared-dir default) resolve to this run.
        if [[ -f "$target/shadow_output/run_env.sh" ]]; then
            # shellcheck source=/dev/null
            source "$target/shadow_output/run_env.sh"
            export MONEROSIM_DAEMON_DATA_DIR MONEROSIM_SHARED_DIR
        fi
        log_dir=""
    else
        log_dir="$target/daemon_logs"
    fi
    if [[ ! -d "$data_dir" ]] || { [[ -n "$log_dir" ]] && [[ ! -d "$log_dir" ]]; }; then
        log_err "Run missing shadow.data/ or daemon_logs/ — not started yet, pruned, or --no-archive?"
        pause
        return
    fi
```

- [ ] **Step 5: Verify**

Run:
```bash
python3 -m pytest scripts/test_check_sim.py -q && bash -n scripts/check_sim.sh && bash -n start_here.sh
R=$(ls -d archived_runs/*_layout_check | tail -1); ./scripts/check_sim.sh "$R" | head -20
```
Expected: tests pass; `check_sim.sh` on the Task 6 run prints `run: ... (complete)` on stderr, `Viewing complete run`, and miner heights.

- [ ] **Step 6: Commit**

```bash
git add scripts/check_sim.sh start_here.sh scripts/test_check_sim.py
git commit -m "feat(tools): check_sim.sh and start_here.sh address a run directory (explicit > env > newest)"
```

---

### Task 9: Analysers and `post_run_analysis.sh` take `--run-dir`; outputs go into the run

**Files:**
- Modify: `scripts/analyze_success_criteria.py` (`analyze_simulation` signature `:195`, shadow-data derivation `:294-298`, `main` `:520-560`)
- Modify: `scripts/analyze_network_connectivity.py` (`__init__` `:94`, `_load_shadow_config` `:215-217`, `main` `:628-640`)
- Modify: `scripts/smoke_assertions.py` (`main` `:412-432`)
- Modify: `scripts/post_run_analysis.sh`
- Modify: `run_sim.sh` `run_analysis` (`:1568-1570`)
- Test: `scripts/test_analyze_success_criteria.py` (new), `scripts/test_smoke_assertions.py`

**Interfaces:**
- Consumes: Task 1 `resolve_run_dir`, `announce`, `daemon_log_dir`, `RunDirNotFound`.
- Produces: `resolve_run_paths(run_dir: Path) -> tuple[Path, Path, Path]` in `analyze_success_criteria.py` returning `(log_dir, shadow_data_dir, out_dir)`; `post_run_analysis.sh [CONFIG_FILE] [RUN_DIR]`.

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_analyze_success_criteria.py`:

```python
"""Run-directory path resolution for analyze_success_criteria.py."""
from pathlib import Path

from scripts.analyze_success_criteria import resolve_run_paths


def _run(tmp_path):
    run = tmp_path / "20260904_120000_a"
    (run / "shadow.data" / "hosts").mkdir(parents=True)
    return run


def test_archived_daemon_logs_preferred(tmp_path):
    run = _run(tmp_path)
    (run / "daemon_logs").mkdir()
    log_dir, shadow, out = resolve_run_paths(run)
    assert (log_dir, shadow, out) == (run / "daemon_logs", run / "shadow.data", run / "analysis_output")


def test_live_namespace_from_run_env(tmp_path):
    run = _run(tmp_path)
    live = tmp_path / "ns"
    (live / "monero-miner-001").mkdir(parents=True)
    (live / "monero-miner-001" / "bitmonero.log").write_text("x")
    (run / "shadow_output").mkdir()
    (run / "shadow_output" / "run_env.sh").write_text(f'MONEROSIM_DAEMON_DATA_DIR="{live}"\n')
    assert resolve_run_paths(run)[0] == live


def test_falls_back_to_hosts_dir(tmp_path):
    run = _run(tmp_path)
    assert resolve_run_paths(run)[0] == run / "shadow.data" / "hosts"
```

Append to `scripts/test_smoke_assertions.py`:

```python
def test_main_resolves_run_dir_from_env(tmp_path, monkeypatch, capsys):
    """--run-dir is optional: $MONEROSIM_RUN_DIR is used, and the chosen run is announced."""
    from scripts.smoke_assertions import main, EXIT_NO_SUMMARY
    run = tmp_path / "20260904_120000_x"
    run.mkdir()
    monkeypatch.setenv("MONEROSIM_RUN_DIR", str(run))
    monkeypatch.setattr("sys.argv", ["smoke_assertions.py"])
    assert main() == EXIT_NO_SUMMARY
    err = capsys.readouterr().err
    assert f"run: {run.resolve()} (incomplete)" in err and "missing summary.txt" in err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest scripts/test_analyze_success_criteria.py scripts/test_smoke_assertions.py -q`
Expected: ImportError for `resolve_run_paths`; the smoke test fails on argparse (`--run-dir` required).

- [ ] **Step 3: `analyze_success_criteria.py`**

After the existing `from scripts.monero_verification import log_info` add:
```python
from scripts.run_dirs import RunDirNotFound, announce, daemon_log_dir, resolve_run_dir
```
Add, above `analyze_simulation`:
```python
def resolve_run_paths(run_dir: Path) -> Tuple[Path, Path, Path]:
    """(log_dir, shadow_data_dir, out_dir) for a run directory.

    log_dir: <run>/daemon_logs (archived) > live /tmp namespace from
    shadow_output/run_env.sh (while the run is live) > shadow.data/hosts.
    All analysis outputs go under <run>/analysis_output/ so concurrent runs
    never write into the checkout root.
    """
    log_dir = daemon_log_dir(run_dir) or (run_dir / 'shadow.data' / 'hosts')
    return log_dir, run_dir / 'shadow.data', run_dir / 'analysis_output'
```
Change `analyze_simulation`'s signature to `def analyze_simulation(log_dir=None, max_workers=DEFAULT_MAX_WORKERS, shadow_data_dir=None):` (keep the existing default for `max_workers` exactly as the file has it) and replace lines 294-298 with:
```python
    # Shadow metadata (processed-config.yaml, sim-stats.json) lives in the
    # run's shadow.data/; derive it from log_path only for legacy calls.
    if shadow_data_dir is None:
        shadow_data_dir = Path('shadow.data')
        if log_path.name == 'hosts' and log_path.parent.name == 'shadow.data':
            shadow_data_dir = log_path.parent
    wall_clock = get_wall_clock_time(Path(shadow_data_dir))
```
In `main()` add the argument and the resolution:
```python
    parser.add_argument('--run-dir', type=str, default=None,
                       help='Run directory (default: $MONEROSIM_RUN_DIR, else newest under archived_runs/). '
                            'Ignored when --log-dir is given.')
    args = parser.parse_args()

    shadow_data_dir = None
    out_dir = Path('.')
    log_dir = args.log_dir
    if log_dir is None:
        try:
            run_dir = resolve_run_dir(args.run_dir)
        except RunDirNotFound as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return {'success': False, 'error': str(e)}
        announce(run_dir)
        log_dir, shadow_data_dir, out_dir = resolve_run_paths(run_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        log_dir = str(log_dir)
```
then pass `shadow_data_dir=shadow_data_dir` to `analyze_simulation(...)`, and route the three outputs through `out_dir`:
```python
        fingerprint_file = save_determinism_fingerprint(
            fingerprint, args.fingerprint_file or str(out_dir / f"determinism_fingerprint_{datetime.now():%Y%m%d_%H%M%S}.json"))
        ...
        summary_file = save_summary_report(
            report, str(out_dir / f"simulation_summary_report_{datetime.now():%Y%m%d_%H%M%S}.txt"))
        ...
        report_json = out_dir / 'success_analysis_report.json'
        with open(report_json, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"\nDetailed report saved to {report_json}")
```
(`datetime` is already imported at the top of the file.)

- [ ] **Step 4: `analyze_network_connectivity.py`**

After the existing `from agents.agent_discovery import AgentDiscovery` add:
```python
from scripts.run_dirs import RunDirNotFound, announce, daemon_log_dir, resolve_run_dir
```
Change `__init__` to `def __init__(self, config_file: str, logs_dir: str, output_dir: str, shadow_config: Optional[Path] = None):` (add `Optional` to the file's `typing` import if missing) and store `self.shadow_config = shadow_config`. In `_load_shadow_config` replace `shadow_config_path = find_latest_shadow_config()` with `shadow_config_path = self.shadow_config or find_latest_shadow_config()`.
Replace `main()` with:
```python
def main():
    parser = argparse.ArgumentParser(description="Analyze Monero P2P network connectivity from Shadow logs")
    parser.add_argument('--config', required=True, help='Path to simulation config file')
    parser.add_argument('--run-dir', default=None,
                        help='Run directory (default: $MONEROSIM_RUN_DIR, else newest under archived_runs/). '
                             'Supplies --logs, --output and the generated shadow_agents.yaml unless overridden.')
    parser.add_argument('--logs', default=None, help='Path to daemon log directory (default: from --run-dir)')
    parser.add_argument('--output', help='Output directory (default: <run>/analysis_output/network_connectivity)')
    args = parser.parse_args()

    logs, output, shadow_config = args.logs, args.output, None
    if logs is None or output is None:
        try:
            run_dir = resolve_run_dir(args.run_dir)
        except RunDirNotFound as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        announce(run_dir)
        logs = logs or str(daemon_log_dir(run_dir) or DEFAULT_LOGS_DIR)
        output = output or str(run_dir / 'analysis_output' / 'network_connectivity')
        candidate = run_dir / 'shadow_agents.yaml'
        shadow_config = candidate if candidate.is_file() else None
    analyzer = NetworkConnectivityAnalyzer(args.config, logs, output, shadow_config)
    analyzer.run_analysis()
    return 0
```
and make the `if __name__ == '__main__':` line `sys.exit(main())` (add `import sys` if the file lacks it).

- [ ] **Step 5: `smoke_assertions.py`**

After its existing imports add:
```python
from scripts.run_dirs import RunDirNotFound, announce, resolve_run_dir
```
(if the file has no `sys.path` repo-root insertion like the other two, add before it:
`sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` with `import os` present).
Change the `--run-dir` argument to `required=False, default=None, type=str` with help `"Run directory (default: $MONEROSIM_RUN_DIR, else newest under archived_runs/)."` and replace `run_dir: Path = args.run_dir.resolve()` with:
```python
    try:
        run_dir: Path = resolve_run_dir(args.run_dir)
    except RunDirNotFound as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_NO_SUMMARY
    announce(run_dir)
```

- [ ] **Step 6: `post_run_analysis.sh` and `run_sim.sh` pass the run directory**

Replace `scripts/post_run_analysis.sh` from `CONFIG_FILE="${1:-}"` to the end of the launch section with:
```bash
CONFIG_FILE="${1:-}"
RUN_DIR="${2:-${MONEROSIM_RUN_DIR:-}}"
RUN_ARGS=()
[[ -n "$RUN_DIR" ]] && RUN_ARGS=(--run-dir "$RUN_DIR")
[[ -n "$RUN_DIR" ]] && echo "Run directory: $RUN_DIR"

echo "Starting Python scripts..."

# (log_processor.py is now at attic/log_processor.py and unmaintained;
#  invoke manually with PYTHONPATH=. if needed)
pids=()
names=()

python3 scripts/analyze_success_criteria.py ${RUN_ARGS[@]+"${RUN_ARGS[@]}"} &
pids+=("$!")
names+=("analyze_success_criteria.py")

if [[ -n "$CONFIG_FILE" ]]; then
    python3 scripts/analyze_network_connectivity.py --config "$CONFIG_FILE" ${RUN_ARGS[@]+"${RUN_ARGS[@]}"} &
    pids+=("$!")
    names+=("analyze_network_connectivity.py")
else
    echo "No config file provided; skipping analyze_network_connectivity.py (needs --config)."
fi
```
and update its usage comment to `# Usage: ./post_run_analysis.sh [CONFIG_FILE] [RUN_DIR]` with `#   RUN_DIR - run directory (default: $MONEROSIM_RUN_DIR, else each analyser picks the newest).`
In `run_sim.sh` `run_analysis`, change `bash "$analysis_script" "$CONFIG" > "$ARCHIVE_DIR/analysis.log" 2>&1 || true` to `bash "$analysis_script" "$CONFIG" "$ARCHIVE_DIR" > "$ARCHIVE_DIR/analysis.log" 2>&1 || true`.

- [ ] **Step 7: Verify**

Run:
```bash
python3 -m pytest scripts/test_analyze_success_criteria.py scripts/test_smoke_assertions.py -q
bash -n scripts/post_run_analysis.sh
R=$(ls -d archived_runs/*_layout_check | tail -1)
bash scripts/post_run_analysis.sh test_configs/quickstart.yaml "$R" | tail -5
ls "$R/analysis_output" "$R/analysis_output/network_connectivity"
git status --short | grep -E 'success_analysis_report|simulation_summary_report|determinism_fingerprint|analysis_results' && echo ROOT-POLLUTED || echo ROOT-CLEAN
```
Expected: tests pass; both analysers finish successfully; `analysis_output/` holds `success_analysis_report.json`, a summary and a fingerprint, and `network_connectivity/` holds the connectivity outputs; `ROOT-CLEAN`.

- [ ] **Step 8: Commit**

```bash
git add scripts/analyze_success_criteria.py scripts/analyze_network_connectivity.py scripts/smoke_assertions.py scripts/post_run_analysis.sh run_sim.sh scripts/test_analyze_success_criteria.py scripts/test_smoke_assertions.py
git commit -m "feat(analysis): analysers take --run-dir and write into <run>/analysis_output/"
```

---

### Task 10: `prune_archives.sh` refuses live runs

**Files:**
- Modify: `scripts/prune_archives.sh:109-118` (`prune_one` entry), usage text
- Test: `scripts/test_prune_archives.py` (new)

- [ ] **Step 1: Write the failing test**

Create `scripts/test_prune_archives.py`:

```python
"""prune_archives.sh must never prune a run whose owner pid is alive."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prune_archives.sh"


def _archive(tmp_path, *, owner):
    a = tmp_path / "20260904_120000_p"
    (a / "shadow.data" / "hosts" / "user-007").mkdir(parents=True)
    (a / "daemon_logs" / "monero-user-007").mkdir(parents=True)
    (a / "summary.txt").write_text("Exit code: 0\n")
    (a / ".owner_pid").write_text(str(owner))
    return a


def _run(args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT)


def test_live_run_is_refused(tmp_path):
    a = _archive(tmp_path, owner=os.getpid())
    r = _run(["--dry-run", str(a)])
    assert "LIVE" in r.stderr and "WOULD DELETE" not in r.stdout


def test_live_run_pruned_with_force(tmp_path):
    a = _archive(tmp_path, owner=os.getpid())
    r = _run(["--dry-run", "--force", str(a)])
    assert "WOULD DELETE" in r.stdout


def test_dead_owner_is_pruned_normally(tmp_path):
    a = _archive(tmp_path, owner=2**22 - 1)
    r = _run(["--dry-run", str(a)])
    assert "WOULD DELETE" in r.stdout and "LIVE" not in r.stderr
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest scripts/test_prune_archives.py -q`
Expected: `test_live_run_is_refused` fails (the live run is listed for deletion).

- [ ] **Step 3: Add the guard**

After `set -euo pipefail` add:
```bash
# shellcheck source=run_dir_lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/run_dir_lib.sh"
```
In `prune_one`, right after `[[ -d "$archive" ]] || { ...; return 1; }` add:
```bash
    if run_dir_is_live "$archive" && [[ "$FORCE" == "false" ]]; then
        echo "Refusing $archive: run is LIVE (owner pid $(cat "$archive/.owner_pid")); use --force to prune anyway" >&2
        return 1
    fi
```
In the usage text change the `--force` line to `--force                   Prune even if summary.txt is missing (incomplete runs) or the run is still live`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest scripts/test_prune_archives.py -q && bash -n scripts/prune_archives.sh`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/prune_archives.sh scripts/test_prune_archives.py
git commit -m "feat(prune): refuse to prune a live run unless --force"
```

---

### Task 11: Acceptance test — two concurrent runs from one checkout

**Files:**
- Create: `scripts/test_parallel_runs.sh`

**Interfaces:**
- Consumes: everything above; `tests/baselines/quickstart_metrics.json` via `smoke_assertions.py`.

- [ ] **Step 1: Write the script**

Create `scripts/test_parallel_runs.sh` (make it executable):

```bash
#!/bin/bash
#
# test_parallel_runs.sh - acceptance test for per-run directories.
#
# Launches TWO quickstart runs concurrently from THIS checkout and asserts
# they do not interfere: distinct run dirs, both complete with summary.txt,
# both pass the quickstart smoke baseline, check_sim.sh addresses each one
# while both are live, and nothing new appears at the checkout root.
#
# Wall time: two 6h-sim quickstarts side by side, 30-90 min depending on
# box load. Runs are nice'd. Logs: /tmp/monerosim_partest_<pid>_{a,b}.log
#
# Usage: ./scripts/test_parallel_runs.sh [CONFIG]   (default test_configs/quickstart.yaml)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source scripts/log_lib.sh
source scripts/run_dir_lib.sh

CONFIG="${1:-test_configs/quickstart.yaml}"
STAMP=$(date +%H%M%S)
NAME_A="par_a_$STAMP"
NAME_B="par_b_$STAMP"
LOG_A="/tmp/monerosim_partest_$$_a.log"
LOG_B="/tmp/monerosim_partest_$$_b.log"
fail() { log_err "$*"; exit 1; }

root_before=$(ls -A "$ROOT" | sort)

log_step "Build once (both runs use --no-build)"
cargo build --release --quiet

log_step "Launch two runs concurrently from $ROOT"
nice ./run_sim.sh --config "$CONFIG" --name "$NAME_A" --no-build --no-monitor > "$LOG_A" 2>&1 &
PID_A=$!
sleep 1
nice ./run_sim.sh --config "$CONFIG" --name "$NAME_B" --no-build --no-monitor > "$LOG_B" 2>&1 &
PID_B=$!
log_info "run_sim.sh pids: $PID_A $PID_B"

find_run() { ls -d "$ROOT"/archived_runs/*_"$1" 2>/dev/null | tail -1; }

log_step "Wait for both runs to have a populated shadow.data/hosts (max 20 min)"
deadline=$((SECONDS + 1200))
RUN_A=""; RUN_B=""
while (( SECONDS < deadline )); do
    RUN_A=$(find_run "$NAME_A"); RUN_B=$(find_run "$NAME_B")
    if [[ -n "$RUN_A" && -n "$RUN_B" && -d "$RUN_A/shadow.data/hosts" && -d "$RUN_B/shadow.data/hosts" ]]; then
        break
    fi
    kill -0 "$PID_A" 2>/dev/null || fail "run A died early; see $LOG_A"
    kill -0 "$PID_B" 2>/dev/null || fail "run B died early; see $LOG_B"
    sleep 10
done
[[ -d "$RUN_A/shadow.data/hosts" && -d "$RUN_B/shadow.data/hosts" ]] || fail "hosts dirs did not appear in time"
[[ "$RUN_A" != "$RUN_B" ]] || fail "both runs resolved to the same directory: $RUN_A"
log_ok "run A: $RUN_A"
log_ok "run B: $RUN_B"

log_step "check_sim.sh addresses each live run"
for R in "$RUN_A" "$RUN_B"; do
    [[ "$(run_dir_state "$R")" == "live" ]] || fail "$R is not live while its run_sim.sh runs"
    out=$(./scripts/check_sim.sh "$R" 2>&1) || fail "check_sim.sh failed for $R: $out"
    grep -q "run: $R (live)" <<< "$out" || fail "check_sim.sh did not announce $R as live"
done
log_ok "check_sim.sh OK on both live runs"

log_step "Wait for completion"
status=0
wait "$PID_A" || { log_err "run A exited non-zero (see $LOG_A)"; status=1; }
wait "$PID_B" || { log_err "run B exited non-zero (see $LOG_B)"; status=1; }
(( status == 0 )) || exit 1

log_step "Assertions"
for R in "$RUN_A" "$RUN_B"; do
    [[ -f "$R/summary.txt" ]] || fail "$R has no summary.txt"
    [[ "$(run_dir_state "$R")" == "complete" ]] || fail "$R is not complete"
    grep -q 'Exit code:      0' "$R/summary.txt" || fail "$R: Shadow exit code not 0"
    (( $(ls "$R/shadow.data/hosts" | wc -l) > 0 )) || fail "$R: empty shadow.data/hosts"
    [[ -f "$R/shadow_output/run_env.sh" ]] || fail "$R: no run_env.sh"
    grep -q "MONEROSIM_RUN_DIR=\"$(readlink -f "$R")\"" "$R/shadow_output/run_env.sh" || fail "$R: run_env.sh names another run"
    python3 scripts/smoke_assertions.py --run-dir "$R" || fail "$R: smoke assertions failed"
    log_ok "$R: complete, exit 0, smoke assertions pass"
done
root_after=$(ls -A "$ROOT" | sort)
if [[ "$root_before" != "$root_after" ]]; then
    diff <(echo "$root_before") <(echo "$root_after") || true
    fail "checkout root changed during the runs"
fi
log_ok "checkout root unchanged"
rm -f "$LOG_A" "$LOG_B"
log_ok "PARALLEL RUNS OK: $RUN_A and $RUN_B"
```

- [ ] **Step 2: Run it**

Run: `chmod +x scripts/test_parallel_runs.sh && bash -n scripts/test_parallel_runs.sh && ./scripts/test_parallel_runs.sh`
Expected: ends with `PARALLEL RUNS OK: ...`. If a smoke assertion fails, read the failing metric and the run's `summary.txt` before concluding anything: a baseline miss on a heavily loaded box is a real finding to report, not something to paper over.

Also run the whole unit suite and the goldens once: `python3 -m pytest agents scripts -q && cargo test --quiet`.
Expected: all pass; goldens byte-identical (the generator did not change).

- [ ] **Step 3: Commit**

```bash
git add scripts/test_parallel_runs.sh
git commit -m "test: acceptance script for two concurrent runs from one checkout"
```

---

### Task 12: Documentation

**Files:**
- Create: `docs/20260904_per_run_directories.md`
- Modify: `docs/20260721_per_run_tmp_namespacing.md` (section 4), `CHANGELOG.md`, `README.md`, `QUICKSTART.md`, `docs/superpowers/specs/2026-09-04-per-run-directories-design.md`

- [ ] **Step 1: User-facing doc**

Create `docs/20260904_per_run_directories.md` with these sections, written from the spec and from what Task 11 observed (include the two run ids and wall times of the acceptance run):
1. **Why** — the 2026-09-04 six-run collision (table from spec §1, one paragraph on what was and was not affected).
2. **Layout** — the tree from spec §3.1 and the variable table from §3.2; note that `--data-dir` now takes a base directory and that `--no-archive` deletes `<run>/shadow.data`.
3. **Which run?** — the resolution order, the `run: <dir> (<state>)` line, the state definitions, and one example per tool (`check_sim.sh archived_runs/<id>`, `post_run_analysis.sh cfg.yaml <run>`, `smoke_assertions.py --run-dir`, `prune_archives.sh` refusing a live run).
4. **Preflight report** — a verbatim example of the `Other live runs on this box:` block from a `--preflight-only` run on this box, and what `Reserving` and the worker-thread line mean.
5. **Acceptance** — how to rerun `scripts/test_parallel_runs.sh` and what it checks.
6. **Compatibility** — existing archives untouched; root-level `shadow.data/`/`shadow_output/` are inert leftovers safe to delete; `run_env.sh` moved; tools that used to read `./shadow.data` now need a run dir.

- [ ] **Step 2: Supersede the July contract**

In `docs/20260721_per_run_tmp_namespacing.md` insert, directly under the `## 4. The concurrency contract` heading:
```
> **Superseded 2026-09-04.** Runs no longer need one checkout each: `shadow.data/`
> and `shadow_output/` now live under `archived_runs/<run_id>/`. See
> `docs/20260904_per_run_directories.md`. The rest of this section describes the
> July 2026 state.
```
Also change line 7-8 (`One run per checkout/worktree; the paths are breadcrumbed for tooling in shadow_output/run_env.sh.`) to `Any number of runs per checkout since 2026-09-04 (see docs/20260904_per_run_directories.md); the paths are breadcrumbed in <run_dir>/shadow_output/run_env.sh.`

- [ ] **Step 3: CHANGELOG, README, QUICKSTART**

Add to the top of `CHANGELOG.md` (follow the file's existing heading style) an entry: per-run directories; concurrent runs per checkout supported; **breaking:** `--data-dir` takes a base directory; `run_env.sh` moved from `<checkout>/shadow_output/` to `<run_dir>/shadow_output/`; analysers write into `<run>/analysis_output/`; `config-summary` prints a sixth field.
Run `grep -n 'check_sim.sh\|shadow\.data\|shadow_output' README.md QUICKSTART.md` and update every hit that tells the reader to look at the checkout root: `./scripts/check_sim.sh` becomes `./scripts/check_sim.sh archived_runs/<run_id>` (or no argument for the newest run), and `shadow.data/` becomes `archived_runs/<run_id>/shadow.data/`.

- [ ] **Step 4: Spec corrections found during implementation**

In the spec, section 4.3, change the `scripts/smoke_assertions.py` row to `makes --run-dir optional, defaulting per 4.1 (it already read <run>/shadow.data/hosts)`; in section 5 add `parallelism|-` as the ninth TSV column; in section 3.3 delete the "provisional RUN_ID" sentence (preflight needs no id: the run directory is allocated in Phase 2 and the live-run report excludes by pid).

- [ ] **Step 5: Verify and commit**

Run: `python3 -m pytest agents scripts -q` (docs only, but confirms nothing regressed) and read the new doc once end to end.
```bash
git add docs/20260904_per_run_directories.md docs/20260721_per_run_tmp_namespacing.md CHANGELOG.md README.md QUICKSTART.md docs/superpowers/specs/2026-09-04-per-run-directories-design.md
git commit -m "docs: per-run directories — layout, run-dir contract, preflight report; supersede July contract"
```
