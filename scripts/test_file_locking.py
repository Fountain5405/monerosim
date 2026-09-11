"""Tests for agents/file_locking.py -- Shadow-safe non-blocking flock helpers.

A blocking flock() under Shadow runs natively on the simulator's worker thread and
deadlocks the whole simulation when the lock holder is a descheduled host, so agents
must only ever poll with LOCK_NB and sleep. These tests exercise acquire_flock's
polling/timeout behaviour and guard against a regression that reintroduces a bare
blocking fcntl.flock() call anywhere in agents/.
"""
import fcntl
import threading
import time
from pathlib import Path

import pytest

from agents.file_locking import acquire_flock, release_flock

AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"


@pytest.fixture
def lock_path(tmp_path):
    p = tmp_path / "test.lock"
    p.touch()
    return p


def test_free_lock_acquires_immediately(lock_path):
    with open(lock_path, "w") as lock_f:
        start = time.monotonic()
        acquire_flock(lock_f, fcntl.LOCK_EX)
        elapsed = time.monotonic() - start
        release_flock(lock_f)
    assert elapsed < 0.05


def test_two_shared_locks_on_separate_handles_both_succeed(lock_path):
    with open(lock_path, "w") as f1, open(lock_path, "w") as f2:
        acquire_flock(f1, fcntl.LOCK_SH)
        acquire_flock(f2, fcntl.LOCK_SH)
        release_flock(f2)
        release_flock(f1)


def test_conflicting_exclusive_lock_times_out(lock_path):
    with open(lock_path, "w") as holder, open(lock_path, "w") as waiter:
        acquire_flock(holder, fcntl.LOCK_EX)
        try:
            start = time.monotonic()
            with pytest.raises(TimeoutError):
                acquire_flock(waiter, fcntl.LOCK_EX, timeout_s=0.2, interval_s=0.02)
            elapsed = time.monotonic() - start
            assert 0.2 <= elapsed < 1.0
        finally:
            release_flock(holder)


def test_lock_released_by_timer_lets_waiter_succeed(lock_path):
    with open(lock_path, "w") as holder, open(lock_path, "w") as waiter:
        acquire_flock(holder, fcntl.LOCK_EX)
        timer = threading.Timer(0.1, release_flock, args=(holder,))
        timer.start()
        try:
            acquire_flock(waiter, fcntl.LOCK_EX, timeout_s=2.0)
        finally:
            timer.join()
        release_flock(waiter)


def test_rejects_lock_un_and_operations_with_lock_nb(lock_path):
    with open(lock_path, "w") as lock_f:
        with pytest.raises(ValueError):
            acquire_flock(lock_f, fcntl.LOCK_UN)
        with pytest.raises(ValueError):
            acquire_flock(lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError):
            acquire_flock(lock_f, fcntl.LOCK_SH | fcntl.LOCK_NB)


def test_no_blocking_flock_call_outside_file_locking_module():
    """Regression guard: every agent must go through acquire_flock/release_flock."""
    offenders = [
        str(path)
        for path in AGENTS_DIR.rglob("*.py")
        if path.name != "file_locking.py" and "fcntl.flock(" in path.read_text()
    ]
    assert offenders == []
