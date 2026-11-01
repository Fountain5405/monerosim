#!/usr/bin/env python3
"""deep_hunt queue (2026-10-19, owner: "queue the deep_hunt runs after the
smokes"). Runs on the spec-only build installed 10:13Z.

1. Wait for the v3 smoke queue (run_smokes_v3b.py) to log "queue end"; go on
   only if its log-version count shows nothing but v3 records and its oracle
   output has no mismatches.
2. deep_hunt_smoke (6 h, both arms at alpha 0.45, --parallel 2). Go on only if
   both cells exit 0 and the stock cell has at least one reveal on honest-001
   (Model B: about 6 expected at 10+ blocks).
3. Two lanes, the shorter-job lane started first:
     lane 1: deep_hunt_sop_a045 (72 h), then deep_hunt_stock (3 cells x 48 h)
     lane 2: deep_hunt_sop_a040 (240 h), once lane 1's run has its cpu_plan.txt
4. Checks on every deep_hunt run: sop_reveals.py stats and depths, the flip-back
   scan, and the spec oracle on the SoP runs. Outputs in
   .claude/campaign8/deep_hunt/checks/.

Log: .claude/campaign8/queue_deep_hunt.log. Launch from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_queue_deep_hunt.py \
      > .claude/campaign8/run_queue_deep_hunt.out 2>&1 &
"""
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
A = REPO / "archived_runs"
C8 = REPO / ".claude/campaign8"
LOG = C8 / "queue_deep_hunt.log"
OUT = C8 / "deep_hunt/checks"
SMOKE_LOG = C8 / "queue_smokes_v3.log"
T0 = time.time() - 5
_lock = threading.Lock()


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def matrix(spec, cells=None, parallel=1):
    args = [PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{spec}.yaml", "--parallel", str(parallel)]
    if cells:
        args[3:3] = ["--cells", cells]
    log("start " + " ".join(args[1:]))
    t = time.time()
    with open(OUT / f"{spec}.matrix.out", "a") as fh:
        r = subprocess.run(args, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"done {spec} rc={r.returncode} {(time.time() - t) / 3600:.2f} h")
    return r.returncode


def runs(spec):
    return sorted(p for p in A.glob(f"*_{spec}__*") if p.is_dir() and p.stat().st_mtime >= T0)


def gate_v3_smokes():
    while not (SMOKE_LOG.exists() and "queue end" in SMOKE_LOG.read_text()):
        time.sleep(60)
    sm = C8 / "smokes_v3"
    versions = (sm / "versions.out").read_text() if (sm / "versions.out").exists() else ""
    oracle = (sm / "oracle.out").read_text() if (sm / "oracle.out").exists() else ""
    vs = set(re.findall(r"'([^']+)':", versions))
    bad = re.findall(r"mismatches=([1-9]\d*)", oracle)
    log(f"v3 smokes: versions {sorted(vs)}; oracle mismatching nodes {len(bad)}; "
        f"oracle lines {oracle.count('decisions=')}")
    return vs == {"3"} and not bad and oracle.count("decisions=") > 0


def stats(run_dirs, name):
    out = OUT / f"{name}_stats.json"
    with open(OUT / f"{name}_stats.out", "w") as fh:
        subprocess.run(["nice", "-n", "10", PY, "scripts/selfish_mining/sop_reveals.py", "stats", str(out),
                        *map(str, run_dirs)], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    return json.loads(out.read_text()) if out.exists() else {}


def lane1():
    if matrix("deep_hunt_sop_a045") != 0:
        log("lane 1: sop_a045 failed; skipping stock")
        return
    matrix("deep_hunt_stock")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log("queue start (deep_hunt); waiting for the v3 smokes")
    if not gate_v3_smokes():
        log("v3 smoke gate FAILED; nothing started; queue end")
        sys.exit(1)

    if matrix("deep_hunt_smoke", parallel=2) != 0:
        log("deep_hunt smoke failed; queue end")
        sys.exit(1)
    smoke = runs("deep_hunt_smoke")
    st = stats(smoke, "smoke")
    for run, v in st.items():
        log(f"smoke {run}: reveals={len(v.get('reveals', []))} depths={v.get('depth_hist')} "
            f"share={v.get('share')}")
    stock = [v for r, v in st.items() if "block_stock" in r]
    if len(smoke) != 2 or not stock or not stock[0].get("reveals"):
        log("deep_hunt smoke gate FAILED (need 2 runs and a stock reveal); queue end")
        sys.exit(1)

    t1 = threading.Thread(target=lane1)
    t1.start()
    deadline = time.time() + 1800
    while time.time() < deadline and not any((p / "shadow_output/cpu_plan.txt").exists()
                                             for p in runs("deep_hunt_sop_a045")):
        time.sleep(15)
    time.sleep(30)
    t2 = threading.Thread(target=matrix, args=("deep_hunt_sop_a040",))
    t2.start()
    t1.join()
    t2.join()

    every = runs("deep_hunt_smoke") + runs("deep_hunt_stock") + runs("deep_hunt_sop_a045") + runs("deep_hunt_sop_a040")
    sop = [p for p in every if "share_sop2" in p.name]
    log("checks on: " + str([p.name for p in every]))
    stats(every, "all")
    jobs = {
        "depths": ["scripts/selfish_mining/sop_reveals.py", "depths", str(OUT / "all_depths.json"), *map(str, every)],
        "flipback": ["scripts/selfish_mining/flipback_scan.py", *map(str, every)],
        "oracle_sop": ["scripts/sop_oracle.py", "check", *map(str, sop)],
    }
    for k, args in jobs.items():
        with open(OUT / f"{k}.out", "w") as fh:
            r = subprocess.run(["nice", "-n", "10", PY, *args], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
        log(f"check {k} rc={r.returncode}")
    log("queue end")


if __name__ == "__main__":
    main()
