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
    .owner_pid   -> "live" while /proc/<pid> exists AND, when .owner_pid's
                    second token (process start time) is present, that pid
                    still has that exact start time (guards against pid reuse)
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


def proc_start_time(pid: int, proc_root: Path = Path("/proc")) -> Optional[int]:
    """Field 22 of /proc/<pid>/stat (process start time in clock ticks since
    boot), or None if the pid or its stat file doesn't exist. comm (field 2)
    is parenthesized and may itself contain ") ", so the safe parse (per
    proc(5)) is to split on the LAST ") " in the line; starttime is then the
    20th field of what remains (fields 3..22 overall = 20 fields)."""
    try:
        text = (proc_root / str(pid) / "stat").read_text()
    except OSError:
        return None
    rest = text.rpartition(") ")[2]
    fields = rest.split()
    if len(fields) < 20:
        return None
    try:
        return int(fields[19])
    except ValueError:
        return None


def pid_alive(pid: int, proc_root: Path = Path("/proc"), start: Optional[int] = None) -> bool:
    """True if a process with this pid exists. /proc rather than os.kill so a
    process owned by another user (EPERM) still counts as alive. When `start`
    is given (the recorded process start time), the pid must ALSO still have
    that exact start time -- guards against pid reuse; an unreadable stat
    file counts as dead in that case."""
    if not (proc_root / str(pid)).exists():
        return False
    if start is None:
        return True
    return proc_start_time(pid, proc_root) == start


def owner_pid(run_dir: Path) -> Optional[int]:
    try:
        text = (run_dir / OWNER_PID_FILE).read_text().strip()
    except OSError:
        return None
    tokens = text.split()
    if not tokens:
        return None
    try:
        return int(tokens[0])
    except ValueError:
        return None


def owner_start(run_dir: Path) -> Optional[int]:
    """The recorded process start time (second token of .owner_pid), or None
    for legacy single-token files or an unreadable/malformed one."""
    try:
        tokens = (run_dir / OWNER_PID_FILE).read_text().split()
    except OSError:
        return None
    if len(tokens) < 2:
        return None
    try:
        return int(tokens[1])
    except ValueError:
        return None


def run_state(run_dir: Path, proc_root: Path = Path("/proc")) -> str:
    pid = owner_pid(run_dir)
    if pid is not None and pid_alive(pid, proc_root, owner_start(run_dir)):
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


def announce(run_dir: Path, file=None) -> str:
    """Print (and return) 'run: <dir> (<state>)'. `file` defaults to the
    *current* sys.stderr, looked up at call time rather than baked into the
    default argument, so it plays nicely with test capture fixtures that
    monkeypatch sys.stderr per-test."""
    if file is None:
        file = sys.stderr
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
            if pid is None or pid == exclude_pid or not pid_alive(pid, proc_root, owner_start(d)):
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
            if pid is None or pid == exclude_pid or not pid_alive(pid, proc_root, owner_start(d)):
                continue
            found[run_id] = LiveRun(run_id, pid, "tmp", None, d, run_id_started(run_id))
    return [found[k] for k in sorted(found)]
