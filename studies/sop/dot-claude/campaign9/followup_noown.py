#!/usr/bin/env python3
"""sop_v4_noown_72h follow-up cell (2026-10-22): run share_sop2_noown_hs_a045_d2
(count_own_tip_shares 'false'), then check_run.py on its archived run.
Single cell, launched by the owner's order, so no GO gate. Logs to
campaign9/queue.log (same timeline as the 4-cell campaign); a nonzero rc or a
gate failure writes campaign9/HALT so status.py --events and the heartbeat see
it. Detached launch:
  setsid nohup venv/bin/python .claude/campaign9/followup_noown.py \
    >> .claude/campaign9/noown.out 2>&1 < /dev/null &
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
C9 = REPO / ".claude/campaign9"
LOG = C9 / "queue.log"
SPEC = "sop_v4_noown_72h"
CELL = "share_sop2_noown_hs_a045_d2"


def log(msg):
    with open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}Z {msg}\n")


def main():
    log(f"noown start cell {CELL}")
    t = time.time()
    r = subprocess.run([PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{SPEC}.yaml",
                        "--parallel", "1", "--cells", CELL], cwd=REPO,
                       stdout=open(C9 / f"{CELL}.matrix.out", "a"), stderr=subprocess.STDOUT)
    marker = REPO / "matrix_runs" / SPEC / "cells" / f"{CELL}.json"
    row = json.loads(marker.read_text()) if marker.exists() else {}
    rc = r.returncode or row.get("returncode", 1 if not row else 0)
    log(f"noown finished {CELL} rc={rc} wall={(time.time() - t) / 3600:.2f} h")
    run_dir = row.get("run_dir")
    if rc != 0 or not run_dir:
        (C9 / "HALT").write_text(f"noown cell rc={rc} run_dir={run_dir} "
                                 f"({row.get('error', 'no marker')})\n")
        log(f"noown HALT rc={rc} run_dir={run_dir}")
        return 1
    c = subprocess.run([PY, str(C9 / "check_run.py"), run_dir], cwd=REPO,
                       capture_output=True, text=True)
    log(f"noown check {CELL} rc={c.returncode}: "
        f"{(c.stdout.strip() or c.stderr.strip())[-500:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
