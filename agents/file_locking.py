"""Shadow-safe advisory file locking for agents.

Shadow runs flock(2) natively on its worker thread. A blocking flock whose holder is
a descheduled simulated host never returns and freezes the whole simulation, so agents
must only ever poll with LOCK_NB and sleep between attempts (the sleep yields simulated
time so the holder can run). Root-caused 2026-09-11; see CHANGELOG.
"""
import errno
import fcntl
import time

DEFAULT_TIMEOUT_S = 120.0
DEFAULT_INTERVAL_S = 0.05


def acquire_flock(lock_f, operation, timeout_s=DEFAULT_TIMEOUT_S, interval_s=DEFAULT_INTERVAL_S):
    """Acquire `operation` (fcntl.LOCK_EX or fcntl.LOCK_SH) on the open file `lock_f`
    without ever blocking the calling thread in the kernel.

    Polls with LOCK_NB and sleeps `interval_s` between attempts so that, under Shadow,
    simulated time advances and the lock holder gets a chance to run and release.
    Raises TimeoutError after timeout_s (measured with time.monotonic).
    """
    if operation & fcntl.LOCK_NB:
        raise ValueError("operation must not already include LOCK_NB")
    if operation == fcntl.LOCK_UN:
        raise ValueError("acquire_flock does not accept LOCK_UN; use release_flock")

    start = time.monotonic()
    while True:
        try:
            fcntl.flock(lock_f, operation | fcntl.LOCK_NB)
            return
        except OSError as e:
            if e.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            if time.monotonic() - start >= timeout_s:
                raise TimeoutError(
                    f"could not acquire file lock on {getattr(lock_f, 'name', '?')} within {timeout_s}s"
                )
            time.sleep(interval_s)


def release_flock(lock_f):
    fcntl.flock(lock_f, fcntl.LOCK_UN)
