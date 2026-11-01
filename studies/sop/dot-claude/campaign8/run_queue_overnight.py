#!/usr/bin/env python3
"""Overnight 2026-10-19, on the installed rev2 monerod-sim (1f7ac1fb's patch;
the specs still carry sim-sop-nf-rule: either, so apply.py must NOT run first):
  1. sop_rev2_h10_a045_72h share_sop2_a045_d2: 12 daemons, alpha 0.45, 72 h
     (deep-reorg probe: Model B predicts 10+ reorgs most days, never measured);
  2. sop_rev2_n40_rep share_sop2_a033_d2: 40 daemons, 48 h (error bars).
The small run starts first; the 40-daemon run starts once the small run has
recorded its CPU plan, so it gets the cores left over (no stacking on 0..N-1).
Then the per-job checks on both run dirs, outputs in .claude/campaign8/overnight/.

Run detached from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_queue_overnight.py > .claude/campaign8/run_queue_overnight.out 2>&1 &
Progress: .claude/campaign8/queue_overnight.log. Stop: kill the queue's process group.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOG = Path(__file__).with_name("queue_overnight.log")
OUT = Path(__file__).with_name("overnight")
PY = str(REPO / "venv/bin/python")
M = "scripts/selfish_matrix.py"
SMALL = [M, "test_configs/matrix/sop_rev2_h10_a045_72h.yaml", "--cells", "share_sop2_a045", "--parallel", "1"]
BIG = [M, "test_configs/matrix/sop_rev2_n40_rep.yaml", "--cells", "share_sop2", "--parallel", "1"]
_lock = threading.Lock()


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with _lock:
        print(line, flush=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")


def run(args, out=None):
    t0 = time.time()
    log(f"start {' '.join(args[1:] if args[0] == PY else args)}")
    if out:
        with open(out, "w") as fh:
            p = subprocess.run(args, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
        tail = []
    else:
        p = subprocess.run([PY] + args, cwd=REPO, capture_output=True, text=True)
        tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    log(f"done rc={p.returncode} {(time.time() - t0) / 3600:.2f} h"
        + "".join(f"\n    {t}" for t in tail))
    return p.returncode


def run_dir(spec_name, since):
    dirs = [d for d in (REPO / "archived_runs").glob(f"*_{spec_name}__*")
            if d.is_dir() and d.stat().st_mtime >= since - 60]
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def main():
    OUT.mkdir(exist_ok=True)
    t_start = time.time()
    log("queue start (overnight)")
    small = threading.Thread(target=run, args=(SMALL,))
    small.start()
    # wait (max 30 min) for the small run's CPU plan before launching the big one
    deadline = time.time() + 1800
    while time.time() < deadline:
        d = run_dir("sop_rev2_h10_a045_72h", t_start)
        if d and (d / "shadow_output" / "cpu_plan.txt").exists():
            log(f"small run planned: {(d / 'shadow_output' / 'cpu_plan.txt').read_text().strip()[:200]}")
            break
        time.sleep(20)
    else:
        log("no CPU plan from the small run after 30 min; starting the big run anyway")
    time.sleep(30)
    run(BIG)
    small.join()

    runs = [run_dir("sop_rev2_h10_a045_72h", t_start), run_dir("sop_rev2_n40_rep", t_start)]
    runs = [str(r) for r in runs if r]
    names = [Path(r).name for r in runs]
    log(f"checks on: {names}")
    nice = ["nice", "-n", "10", PY]
    run(nice + ["scripts/sop_oracle.py", "check", *runs], OUT / "oracle.out")
    run(nice + ["-m", "scripts.sop_lateness_probe", "replay", *runs], OUT / "probe.out")
    run(nice + ["scripts/selfish_mining/flipback_scan.py", *runs], OUT / "flipback.out")
    run(nice + [".claude/campaign8/late_start_scan.py", *names], OUT / "late_new.out")
    run(nice + ["scripts/selfish_mining/sop_reveals.py", "stats", str(OUT / "reveals_stats.json"), *runs],
        OUT / "reveals_stats.out")
    run(nice + ["scripts/selfish_mining/sop_reveals.py", "depths", str(OUT / "reveals_depths.json"), *runs],
        OUT / "reveals_depths.out")
    run(nice + ["scripts/selfish_mining/sop_pending.py", *runs], OUT / "pending.out")
    log("queue end")
    return 0


if __name__ == "__main__":
    sys.exit(main())
