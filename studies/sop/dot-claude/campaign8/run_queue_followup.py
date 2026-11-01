#!/usr/bin/env python3
"""Follow-up runs on the spec-only build (2026-10-19, owner: "yes queue
them"), behind the deep_hunt queue.

  lane X, once deep_hunt's lane 1 is done ("done deep_hunt_stock") or its
          queue ended: sop_v3_n40_rep2 --cells block_stock (40 daemons, 48 h),
          then sop_v3_n40_depth_rep --cells share_sop2 (40 daemons, 48 h, d5)
  lane Y, once deep_hunt's 240 h run is done ("done deep_hunt_sop_a040") or
          its queue ended: sop_v3_h10_a045_72h --cells share_sop2_a045 (72 h)

Then the per-job checks on the three runs: spec oracle (SoP runs), lateness
probe, flip-back and late-start scans, sop_reveals.py stats and depths, and
sop_pending (as a module). Outputs in .claude/campaign8/followup/. Log:
.claude/campaign8/queue_followup.log. Launch from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_queue_followup.py \
      > .claude/campaign8/run_queue_followup.out 2>&1 &
"""
import subprocess
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
A = REPO / "archived_runs"
C8 = REPO / ".claude/campaign8"
LOG = C8 / "queue_followup.log"
OUT = C8 / "followup"
DH_LOG = C8 / "queue_deep_hunt.log"
T0 = time.time() - 5
_lock = threading.Lock()


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def wait_for(*markers):
    while True:
        text = DH_LOG.read_text() if DH_LOG.exists() else ""
        if any(m in text for m in markers):
            return
        time.sleep(60)


def matrix(spec, cells):
    args = [PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{spec}.yaml", "--cells", cells, "--parallel", "1"]
    log("start " + " ".join(args[1:]))
    t = time.time()
    with open(OUT / f"{spec}.matrix.out", "a") as fh:
        r = subprocess.run(args, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"done {spec} rc={r.returncode} {(time.time() - t) / 3600:.2f} h")


def lane_x():
    wait_for("done deep_hunt_stock", "queue end")
    matrix("sop_v3_n40_rep2", "block_stock")
    matrix("sop_v3_n40_depth_rep", "share_sop2")


def lane_y():
    wait_for("done deep_hunt_sop_a040", "queue end")
    time.sleep(120)   # let the deep_hunt checks start before a 14-core run lands
    matrix("sop_v3_h10_a045_72h", "share_sop2_a045")


def runs(spec):
    return sorted(p for p in A.glob(f"*_{spec}__*") if p.is_dir() and p.stat().st_mtime >= T0)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log("queue start (follow-up); waiting on the deep_hunt queue")
    tx, ty = threading.Thread(target=lane_x), threading.Thread(target=lane_y)
    tx.start()
    ty.start()
    tx.join()
    ty.join()
    every = runs("sop_v3_n40_rep2") + runs("sop_v3_n40_depth_rep") + runs("sop_v3_h10_a045_72h")
    sop = [p for p in every if "share_sop2" in p.name]
    log("checks on: " + str([p.name for p in every]))
    jobs = {
        "oracle": ["scripts/sop_oracle.py", "check", *map(str, sop)],
        "probe": ["-m", "scripts.sop_lateness_probe", "replay", *map(str, sop)],
        "flipback": ["scripts/selfish_mining/flipback_scan.py", *map(str, every)],
        "late_new": [".claude/campaign8/late_start_scan.py", *[p.name for p in sop]],
        "reveals_stats": ["scripts/selfish_mining/sop_reveals.py", "stats", str(OUT / "reveals_stats.json"), *map(str, every)],
        "reveals_depths": ["scripts/selfish_mining/sop_reveals.py", "depths", str(OUT / "reveals_depths.json"), *map(str, every)],
        "pending": ["-m", "scripts.selfish_mining.sop_pending", *map(str, sop)],
    }
    for k, args in jobs.items():
        with open(OUT / f"{k}.out", "w") as fh:
            r = subprocess.run(["nice", "-n", "10", PY, *args], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
        log(f"check {k} rc={r.returncode}")
    log("queue end")


if __name__ == "__main__":
    main()
