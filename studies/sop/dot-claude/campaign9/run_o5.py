#!/usr/bin/env python3
"""The objects-give-up attacker on 12 daemons (owner-ordered 2026-10-23):
sop_v4_o5_72h, cells share_sop2_a045_s1 and _s2 (two draws of the a045 hs
cell with give_up_objects 5), 72 h each, both lanes started at once (14 + 14
of 32 cores, the reps precedent). After each cell: check_run.py; a nonzero
returncode or gate failure writes campaign9/HALT (rc=2 WARN continues). Log:
campaign9/queue.log, `o5 ...` lines. Detached launch:
  setsid nohup venv/bin/python .claude/campaign9/run_o5.py \
    >> .claude/campaign9/o5.out 2>&1 < /dev/null &
Afterwards: scripts/selfish_mining/sop_stuck_time.py <run dirs>.
"""
import json
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
SPEC = "sop_v4_o5_72h"
CELLS = ["share_sop2_a045_s1", "share_sop2_a045_s2"]
_lock = threading.Lock()


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}Z {msg}\n")


def run_cell(lane, cell):
    if HALT.exists():
        log(f"o5 lane {lane}: HALT exists at start; not running {cell}")
        return
    log(f"o5 lane {lane} start {SPEC}/{cell}")
    t = time.time()
    r = subprocess.run([PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{SPEC}.yaml",
                        "--parallel", "1", "--cells", cell], cwd=REPO,
                       stdout=open(C9 / f"{SPEC}__{cell}.matrix.out", "a"),
                       stderr=subprocess.STDOUT)
    marker = REPO / "matrix_runs" / SPEC / "cells" / f"{cell}.json"
    row = json.loads(marker.read_text()) if marker.exists() else {}
    rc = r.returncode or row.get("returncode", 1 if not row else 0)
    log(f"o5 lane {lane} finished {SPEC}/{cell} rc={rc} wall={(time.time() - t) / 3600:.2f} h")
    run_dir = row.get("run_dir")
    if rc != 0 or not run_dir:
        HALT.write_text(f"o5 cell rc={rc} run_dir={run_dir} ({SPEC}/{cell}: {row.get('error', 'no marker')})\n")
        log(f"o5 HALT {SPEC}/{cell} rc={rc} run_dir={run_dir}")
        return
    c = subprocess.run([PY, str(C9 / "check_run.py"), run_dir], cwd=REPO,
                       capture_output=True, text=True)
    log(f"o5 check {SPEC}/{cell} rc={c.returncode}: {(c.stdout.strip() or c.stderr.strip())[-500:]}")
    if c.returncode == 1:
        HALT.write_text(f"o5 check_run gate failed ({SPEC}/{cell})\n")
        log(f"o5 HALT check gate {SPEC}/{cell}")


def main():
    log(f"o5 queue start lanes=2 ({SPEC})")
    ts = [threading.Thread(target=run_cell, args=(i + 1, c)) for i, c in enumerate(CELLS)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    log("o5 queue done" if not HALT.exists() else "o5 queue stopped (HALT)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
