#!/usr/bin/env python3
"""sop_v4_h10_72h queue: N lanes (default 2), one cell at a time each, cells
in the spec's run order. Start gate: the integer in campaign9/GO (missing or
unparsable = 0); cell i (1-based) starts only if i <= GO, else poll every 60 s.
After each cell: campaign9/check_run.py <run_dir> (0 pass, 2 pass with
warnings, 1 gate failed). A nonzero cell returncode or check_run exit 1 writes
campaign9/HALT and no further cells start. Log: campaign9/queue.log (UTC).
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
C9 = REPO / ".claude/campaign9"
GO, HALT, LOG = C9 / "GO", C9 / "HALT", C9 / "queue.log"
SPEC = "sop_v4_h10_72h"
CELLS = ["share_sop2_built_a033_d2", "share_sop2_hs_a045_d5",
         "share_sop2_hs_a040_d2", "share_sop2_hs_a045_d2"]
POLL = 60
_lock = threading.Lock()
_state = {"started": 0}


def parse_go(text):
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return 0


def read_go():
    try:
        return parse_go(GO.read_text())
    except OSError:
        return 0


def decide(go, halted, n_started, n_cells):
    """'stop' (halted or all started), 'start' (next cell allowed) or 'wait'."""
    if halted or n_started >= n_cells:
        return "stop"
    return "start" if n_started + 1 <= go else "wait"


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z {msg}\n")
        fh.flush()


def claim():
    """Next cell index (0-based) for a lane, or None when the lane should exit."""
    while True:
        with _lock:
            d = decide(read_go(), HALT.exists(), _state["started"], len(CELLS))
            if d == "start":
                _state["started"] += 1
                return _state["started"] - 1
        if d == "stop":
            return None
        time.sleep(POLL)


def halt(reason, cell):
    HALT.write_text(f"{reason} ({cell})\n")
    log(f"HALT {reason} cell={cell}")


def run_cell(lane, i):
    cell = CELLS[i]
    log(f"lane {lane} start cell {i + 1} {cell}")
    t = time.time()
    r = subprocess.run([PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{SPEC}.yaml",
                        "--parallel", "1", "--cells", cell], cwd=REPO,
                       stdout=open(C9 / f"{cell}.matrix.out", "a"), stderr=subprocess.STDOUT)
    marker = REPO / "matrix_runs" / SPEC / "cells" / f"{cell}.json"
    row = json.loads(marker.read_text()) if marker.exists() else {}
    rc = r.returncode or row.get("returncode", 1 if not row else 0)
    log(f"lane {lane} finished {cell} rc={rc} wall={(time.time() - t) / 3600:.2f} h")
    if rc != 0:
        return halt(f"cell returncode {rc}", cell)
    run_dir = row.get("run_dir")
    if not run_dir:
        return halt(f"no run_dir ({row.get('error', 'no marker')})", cell)
    c = subprocess.run([PY, ".claude/campaign9/check_run.py", run_dir], cwd=REPO,
                       capture_output=True, text=True)
    log(f"check {cell} rc={c.returncode}: {(c.stdout.strip() or c.stderr.strip())[-500:]}")
    if c.returncode == 1:
        halt("check_run gate failed", cell)


def lane(n):
    while (i := claim()) is not None:
        run_cell(n, i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lanes", type=int, default=2)
    a = ap.parse_args()
    if a.dry_run:
        print(f"{a.lanes} lanes, gate GO={read_go()}, HALT={'yes' if HALT.exists() else 'no'}")
        for i, c in enumerate(CELLS, 1):
            print(f"{i}. {c}  (needs GO >= {i})")
        return
    C9.mkdir(exist_ok=True)
    log(f"queue start lanes={a.lanes}")
    ts = [threading.Thread(target=lane, args=(n + 1,)) for n in range(a.lanes)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    log("queue done" if not HALT.exists() else "queue stopped (HALT)")


if __name__ == "__main__":
    main()
