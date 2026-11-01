#!/usr/bin/env python3
"""Second samples for noise (owner-approved 2026-10-22 ~14:55Z): cell 4
(sop_v4_h10_72h_s2) and the noown cell (sop_v4_noown_72h_s2), 72 h each.

Lane 1 starts the cell-4 repeat immediately (alongside the in-flight noown
run: 14 + 14 = 28 of 32 cores). Lane 2 waits for the in-flight noown runner
(--wait-pid, followup_noown.py) to exit, then starts the noown repeat only if
its check did not FAIL (no HALT, and the last `noown check` line in queue.log
is not rc=1). After each cell: check_run.py; a nonzero returncode or gate
failure writes campaign9/HALT and no further cells start (rc=2 WARN
continues). Log: campaign9/queue.log, `reps ...` lines. Detached launch:
  setsid nohup venv/bin/python .claude/campaign9/run_repeats.py \
    --wait-pid <followup_noown pid> >> .claude/campaign9/reps.out 2>&1 \
    < /dev/null &
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
C9 = REPO / ".claude/campaign9"
LOG = C9 / "queue.log"
HALT = C9 / "HALT"
CELLS = [("sop_v4_h10_72h_s2", "share_sop2_hs_a045_d2"),
         ("sop_v4_noown_72h_s2", "share_sop2_noown_hs_a045_d2")]
POLL = 60
_lock = threading.Lock()
_claimed = {"n": 0}


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}Z {msg}\n")


def noown_check_failed():
    """True once the in-flight noown cell's check line exists and is rc=1."""
    last = None
    try:
        for line in LOG.read_text().splitlines():
            if "noown check" in line:
                last = line
    except OSError:
        pass
    return last is not None and "rc=1:" in last


def wait_pid(pid):
    while pid and os.path.exists(f"/proc/{pid}"):
        time.sleep(POLL)


def run_cell(lane, i):
    spec, cell = CELLS[i]
    log(f"reps lane {lane} start cell {i + 1} {spec}/{cell}")
    t = time.time()
    r = subprocess.run([PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{spec}.yaml",
                        "--parallel", "1", "--cells", cell], cwd=REPO,
                       stdout=open(C9 / f"{spec}__{cell}.matrix.out", "a"),
                       stderr=subprocess.STDOUT)
    marker = REPO / "matrix_runs" / spec / "cells" / f"{cell}.json"
    row = json.loads(marker.read_text()) if marker.exists() else {}
    rc = r.returncode or row.get("returncode", 1 if not row else 0)
    log(f"reps lane {lane} finished {spec}/{cell} rc={rc} wall={(time.time() - t) / 3600:.2f} h")
    if rc != 0:
        HALT.write_text(f"reps cell returncode {rc} ({spec}/{cell})\n")
        return
    run_dir = row.get("run_dir")
    if not run_dir:
        HALT.write_text(f"reps no run_dir ({spec}/{cell}: {row.get('error', 'no marker')})\n")
        log(f"reps HALT no run_dir {spec}/{cell}")
        return
    c = subprocess.run([PY, str(C9 / "check_run.py"), run_dir], cwd=REPO,
                       capture_output=True, text=True)
    log(f"reps check {spec}/{cell} rc={c.returncode}: "
        f"{(c.stdout.strip() or c.stderr.strip())[-500:]}")
    if c.returncode == 1:
        HALT.write_text(f"reps check_run gate failed ({spec}/{cell})\n")
        log(f"reps HALT check gate {spec}/{cell}")


def lane(n, wait_pid_num):
    if n == 1:
        if HALT.exists():
            log("reps lane 1: HALT exists at start; not running")
            return
        run_cell(1, 0)
        return
    wait_pid(wait_pid_num)
    if HALT.exists():
        log("reps lane 2: HALT exists; not starting the noown repeat")
        return
    if noown_check_failed():
        log("reps lane 2: in-flight noown check FAILED; not starting the noown repeat")
        return
    run_cell(2, 1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-pid", type=int, default=0,
                    help="followup_noown.py pid; lane 2 starts after it exits")
    a = ap.parse_args(argv)
    log(f"reps queue start (wait_pid={a.wait_pid or 'none'})")
    ts = [threading.Thread(target=lane, args=(n + 1, a.wait_pid)) for n in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    log("reps queue done" if not HALT.exists() else "reps queue stopped (HALT)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
