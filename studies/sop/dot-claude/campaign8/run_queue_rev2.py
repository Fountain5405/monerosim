#!/usr/bin/env python3
"""Campaign 8, rev2: the same runs on the pop patch that follows MRL #146's
2026-10-15 revision (specs test_configs/matrix/sop_rev2_*.yaml; new names, so
the old-build results under matrix_runs/sop_either_* stay as they are).

Three lanes instead of barrier stages, so the 40-daemon runs (~27 h each)
overlap the 12-daemon ones without going past the 32 physical cores:
  small  A (12 x 6 h, one spec at a time, 4 runs each), then two rounds of
         three 240 h runs
  n40a   after A: n40 share_sop2, then n40_depth (alongside the 240 h rounds)
  n40b   after the small lane: n40 block_stock
Specs split across processes are re-scored with --reanalyze at the end.

Run detached from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_queue_rev2.py > .claude/campaign8/run_queue_rev2.out 2>&1 &
Progress: .claude/campaign8/queue_rev2.log. Stop: kill the queue's process group.
"""
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOG = Path(__file__).with_name("queue_rev2.log")
PY = str(REPO / "venv/bin/python")
M = "scripts/selfish_matrix.py"
_lock = threading.Lock()


def spec(name):
    return f"test_configs/matrix/{name}.yaml"


SHORT = "share_sop2_a040,share_sop2_a045"
SMALL = [
    ("A: 6 h (alpha 0.40/0.45)", 1, [
        [M, spec("sop_rev2_h10"), "--cells", SHORT, "--parallel", "4"],
        [M, spec("sop_rev2_h10_rep"), "--cells", SHORT, "--parallel", "4"],
        [M, spec("sop_rev2_h10_rep2"), "--cells", SHORT, "--parallel", "4"],
    ]),
    ("B1: 240 h, round 1", 3, [
        [M, spec("sop_rev2_h10_long"), "--cells", "share_sop2", "--parallel", "1"],
        [M, spec("sop_rev2_h10_long_rep"), "--cells", "share_sop2", "--parallel", "1"],
        [M, spec("sop_rev2_h10_long_depth"), "--cells", "d3", "--parallel", "1"],
    ]),
    ("B2: 240 h, round 2", 3, [
        [M, spec("sop_rev2_h10_long_depth"), "--cells", "d5", "--parallel", "1"],
        [M, spec("sop_rev2_h10_long_depth_rep"), "--cells", "d3", "--parallel", "1"],
        [M, spec("sop_rev2_h10_long_depth_rep"), "--cells", "d5", "--parallel", "1"],
    ]),
]
N40A = [
    [M, spec("sop_rev2_n40"), "--cells", "share_sop2", "--parallel", "1"],
    [M, spec("sop_rev2_n40_depth"), "--parallel", "1"],
]
N40B = [
    [M, spec("sop_rev2_n40"), "--cells", "block_stock", "--parallel", "1"],
]
REANALYZE = ["sop_rev2_h10", "sop_rev2_h10_rep", "sop_rev2_h10_rep2",
             "sop_rev2_h10_long", "sop_rev2_h10_long_rep",
             "sop_rev2_h10_long_depth", "sop_rev2_h10_long_depth_rep",
             "sop_rev2_n40", "sop_rev2_n40_depth"]

a_done = threading.Event()
small_done = threading.Event()
failed = []


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with _lock:
        print(line, flush=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")


def run(args):
    t0 = time.time()
    log(f"start {' '.join(args[1:])}")
    p = subprocess.run([PY] + args, cwd=REPO, capture_output=True, text=True)
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    log(f"done rc={p.returncode} {(time.time() - t0) / 3600:.1f} h {' '.join(args[1:])}"
        + "".join(f"\n    {t}" for t in tail))
    if p.returncode:
        failed.append(args)
    return p.returncode


def lane_small():
    try:
        for i, (title, limit, jobs) in enumerate(SMALL):
            log(f"== small lane: stage {title} ({len(jobs)} jobs, {limit} at a time)")
            with ThreadPoolExecutor(max_workers=limit) as pool:
                list(pool.map(run, jobs))
            if i == 0:
                a_done.set()
    finally:
        a_done.set()
        small_done.set()
        log("== small lane done")


def lane_seq(name, wait_for, jobs):
    wait_for.wait()
    log(f"== lane {name}: {len(jobs)} job(s), one at a time")
    for job in jobs:
        run(job)
    log(f"== lane {name} done")


def main():
    log("queue start (rev2)")
    lanes = [threading.Thread(target=lane_small),
             threading.Thread(target=lane_seq, args=("n40a", a_done, N40A)),
             threading.Thread(target=lane_seq, args=("n40b", small_done, N40B))]
    for t in lanes:
        t.start()
    for t in lanes:
        t.join()
    log("== re-scoring every spec")
    for name in REANALYZE:
        run([M, spec(name), "--reanalyze"])
    log(f"queue end ({len(failed)} job(s) returned non-zero)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
