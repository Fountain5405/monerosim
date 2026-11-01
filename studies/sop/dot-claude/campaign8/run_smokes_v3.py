#!/usr/bin/env python3
"""Smokes for the spec-only build (log v3), 2026-10-19, after the owner's
./setup.sh --sim-binary (monerod-sim built 10:13:42Z, pop patch b8b15002...).

SMALL first: one 12-daemon cell of sop_rev2_smoke. Once its cpu_plan.txt
exists, BIG: the 40-daemon share_sop2 smoke. Then, on both runs: the spec
oracle, the lateness probe, the late-start scan, and a count of SIM-SoP-DEC
records by log version (every record should be v3). Sequential checks at
nice 10. Log: .claude/campaign8/queue_smokes_v3.log; outputs in
.claude/campaign8/smokes_v3/.

Launch from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_smokes_v3.py \
      > .claude/campaign8/run_smokes_v3.out 2>&1 &
"""
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
A = REPO / "archived_runs"
LOG = REPO / ".claude/campaign8/queue_smokes_v3.log"
OUT = REPO / ".claude/campaign8/smokes_v3"
SMALL = ["scripts/selfish_matrix.py", "test_configs/matrix/sop_rev2_smoke.yaml",
         "--cells", "share_sop2_a040_d2", "--parallel", "1"]
BIG = ["scripts/selfish_matrix.py", ".claude/campaign8/after_queue/sop_v3_smoke_n40.yaml",
       "--cells", "share_sop2", "--parallel", "1"]
DEC_V = re.compile(r'SIM-SoP-DEC.*?"v":\s*(\d+)')


def log(msg):
    with open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def runs_since(spec, t0):
    return sorted(p for p in A.glob(f"*_{spec}__*") if p.is_dir() and p.stat().st_mtime >= t0)


def version_counts(run):
    c = Counter()
    for f in run.glob("daemon_logs/*/bitmonero.log"):
        with open(f, errors="replace") as fh:
            for line in fh:
                if "SIM-SoP-DEC" in line:
                    m = DEC_V.search(line)
                    c[m.group(1) if m else "none"] += 1
    return c


def main():
    OUT.mkdir(exist_ok=True)
    t0 = time.time() - 5
    log("queue start (smokes v3)")
    log("start " + " ".join(SMALL))
    small = subprocess.Popen([PY, *SMALL], cwd=REPO, stdout=open(OUT / "small.out", "w"),
                             stderr=subprocess.STDOUT)
    deadline = time.time() + 1800
    while time.time() < deadline and small.poll() is None:
        if any((p / "shadow_output/cpu_plan.txt").exists() for p in runs_since("sop_rev2_smoke", t0)):
            break
        time.sleep(15)
    if small.poll() not in (None, 0):
        log(f"small failed early rc={small.returncode}; not starting big")
        sys.exit(1)
    time.sleep(30)
    log("start " + " ".join(BIG))
    big = subprocess.Popen([PY, *BIG], cwd=REPO, stdout=open(OUT / "big.out", "w"),
                           stderr=subprocess.STDOUT)
    for name, p in (("small", small), ("big", big)):
        p.wait()
        log(f"{name} done rc={p.returncode} {(time.time() - t0) / 3600:.2f} h")
    runs = runs_since("sop_rev2_smoke", t0) + runs_since("sop_v3_smoke_n40", t0)
    log("checks on: " + str([p.name for p in runs]))
    if not runs:
        log("no runs found; queue end")
        return
    jobs = {
        "oracle": ["scripts/sop_oracle.py", "check", *map(str, runs)],
        "probe": ["-m", "scripts.sop_lateness_probe", "replay", *map(str, runs)],
        "late_new": [".claude/campaign8/late_start_scan.py", *[p.name for p in runs]],
    }
    for k, args in jobs.items():
        with open(OUT / f"{k}.out", "w") as fh:
            r = subprocess.run(["nice", "-n", "10", PY, *args], cwd=REPO, stdout=fh,
                               stderr=subprocess.STDOUT)
        log(f"check {k} rc={r.returncode}")
    with open(OUT / "versions.out", "w") as fh:
        for p in runs:
            fh.write(f"{p.name}: {dict(version_counts(p))}\n")
    log("check versions done")
    log("queue end")


if __name__ == "__main__":
    main()
