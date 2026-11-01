#!/usr/bin/env python3
"""Share-aware attacker runs (2026-10-20, owner: "go ahead and queue the
runs"), on monerod-sim with the share RPCs (built 2026-10-20 16:47 UTC).

Two lanes, so two 12-daemon runs (14 cores each) fit the box's 32 physical
cores without CPU pile-up. Most important first:
  lane 1: sop_v3_hs_h10_72h cells hs_a045_d5, built_a045_d5, hs_a040_d2,
          built_a040_d2, hs_a030_d2, built_a030_d2 (window_stubborn, 72 h each)
  lane 2: sop_v3_hs_h10_72h cell hs_a045_d2, then deep_hunt_sop_hs_a045 (72 h),
          then deep_hunt_sop_hs_a040 (240 h)

Then the checks on every run: share embedding (embed_check.py: gossiped shares
must be > 0 at the attacker's miner in hs runs and 0 in built runs), the spec
oracle, sop_reveals.py stats and depths, flip-back scan, lateness probe and
pending shares. Outputs in .claude/campaign8/hs/. Log:
.claude/campaign8/queue_hs.log. Launch from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_queue_hs.py \
      > .claude/campaign8/run_queue_hs.out 2>&1 &
"""
import subprocess
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
A = REPO / "archived_runs"
C8 = REPO / ".claude/campaign8"
LOG = C8 / "queue_hs.log"
OUT = C8 / "hs"
T0 = time.time() - 5
_lock = threading.Lock()
WS = "sop_v3_hs_h10_72h"


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def matrix(spec, cells=None):
    args = [PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{spec}.yaml", "--parallel", "1"]
    if cells:
        args += ["--cells", cells]
    log("start " + " ".join(args[1:]))
    t = time.time()
    with open(OUT / f"{spec}.matrix.out", "a") as fh:
        r = subprocess.run(args, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"done {spec} {cells or ''} rc={r.returncode} {(time.time() - t) / 3600:.2f} h")


def lane_1():
    for cell in ("hs_a045_d5", "built_a045_d5", "hs_a040_d2", "built_a040_d2", "hs_a030_d2", "built_a030_d2"):
        matrix(WS, cell)


def lane_2():
    time.sleep(120)   # let lane 1's run take its CPU plan first
    matrix(WS, "hs_a045_d2")
    matrix("deep_hunt_sop_hs_a045")
    matrix("deep_hunt_sop_hs_a040")


def runs(spec):
    return sorted(p for p in A.glob(f"*_{spec}__*") if p.is_dir() and p.stat().st_mtime >= T0)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log("queue start (share-aware attacker)")
    lanes = [threading.Thread(target=lane_1), threading.Thread(target=lane_2)]
    for t in lanes:
        t.start()
    for t in lanes:
        t.join()
    every = runs(WS) + runs("deep_hunt_sop_hs_a045") + runs("deep_hunt_sop_hs_a040")
    log("checks on: " + str([p.name for p in every]))
    with open(OUT / "embed.out", "w") as fh:
        for p in every:
            r = subprocess.run(["nice", "-n", "10", PY, ".claude/campaign8/embed_check.py", p.name],
                               cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"check embed rc={r.returncode if every else 'n/a'}")
    jobs = {
        "oracle": ["scripts/sop_oracle.py", "check", *map(str, every)],
        "probe": ["-m", "scripts.sop_lateness_probe", "replay", *map(str, every)],
        "flipback": ["scripts/selfish_mining/flipback_scan.py", *map(str, every)],
        "reveals_stats": ["scripts/selfish_mining/sop_reveals.py", "stats", str(OUT / "reveals_stats.json"), *map(str, every)],
        "reveals_depths": ["scripts/selfish_mining/sop_reveals.py", "depths", str(OUT / "reveals_depths.json"), *map(str, every)],
        "pending": ["-m", "scripts.selfish_mining.sop_pending", *map(str, every)],
    }
    for k, args in jobs.items():
        with open(OUT / f"{k}.out", "w") as fh:
            r = subprocess.run(["nice", "-n", "10", PY, *args], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
        log(f"check {k} rc={r.returncode}")
    log("queue end")


if __name__ == "__main__":
    main()
