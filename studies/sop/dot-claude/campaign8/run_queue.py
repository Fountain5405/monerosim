#!/usr/bin/env python3
"""Campaign 8 run queue: re-run campaign 7 under --sim-sop-nf-rule=either,
then the 40-daemon network. Stages run in order; jobs inside a stage run
concurrently up to the stage's limit. Every job is one selfish_matrix.py
process (KSM comes from `ksm: true` in each spec). Specs whose cells are
split across processes are re-scored with --reanalyze at the end, since each
process rewrites results.json with only its own cells.

Run detached from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_queue.py > .claude/campaign8/run_queue.out 2>&1 &
Progress: .claude/campaign8/queue.log. Stop: kill the queue's process group.
"""
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOG = Path(__file__).with_name("queue.log")
PY = str(REPO / "venv/bin/python")
M = "scripts/selfish_matrix.py"


def spec(name):
    return f"test_configs/matrix/{name}.yaml"


SHORT = "share_sop2_a040,share_sop2_a045"
STAGES = [
    ("A: 6 h re-runs (alpha 0.40/0.45)", 1, [
        [M, spec("sop_either_h10"), "--cells", SHORT, "--parallel", "4"],
        [M, spec("sop_either_h10_rep"), "--cells", SHORT, "--parallel", "4"],
        [M, spec("sop_either_h10_rep2"), "--cells", SHORT, "--parallel", "4"],
    ]),
    ("B1: 240 h re-runs, round 1 + 40-daemon speed check", 4, [
        [M, spec("sop_either_h10_long"), "--cells", "share_sop2", "--parallel", "1"],
        [M, spec("sop_either_h10_long_rep"), "--cells", "share_sop2", "--parallel", "1"],
        [M, spec("sop_either_h10_long_depth"), "--cells", "d3", "--parallel", "1"],
        [M, spec("sop_either_n40_speed"), "--parallel", "1"],
    ]),
    ("B2: 240 h re-runs, round 2", 3, [
        [M, spec("sop_either_h10_long_depth"), "--cells", "d5", "--parallel", "1"],
        [M, spec("sop_either_h10_long_depth_rep"), "--cells", "d3", "--parallel", "1"],
        [M, spec("sop_either_h10_long_depth_rep"), "--cells", "d5", "--parallel", "1"],
    ]),
    ("C: 40-daemon 48 h runs", 1, [
        [M, spec("sop_either_n40"), "--parallel", "1"],
        [M, spec("sop_either_n40_depth"), "--parallel", "1"],
    ]),
]
REANALYZE = ["sop_either_h10", "sop_either_h10_rep", "sop_either_h10_rep2",
             "sop_either_h10_long", "sop_either_h10_long_rep",
             "sop_either_h10_long_depth", "sop_either_h10_long_depth_rep",
             "sop_either_n40_speed", "sop_either_n40", "sop_either_n40_depth"]


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
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
    return p.returncode


def main():
    log("queue start")
    failed = 0
    for title, limit, jobs in STAGES:
        log(f"== stage {title} ({len(jobs)} jobs, {limit} at a time)")
        with ThreadPoolExecutor(max_workers=limit) as pool:
            failed += sum(1 for rc in pool.map(run, jobs) if rc)
    log("== re-scoring every spec")
    for name in REANALYZE:
        run([M, spec(name), "--reanalyze"])
    log(f"queue end ({failed} job(s) returned non-zero)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
