#!/usr/bin/env python3
"""Second half of the v3 smokes, 2026-10-19. run_smokes_v3.py's 12-daemon step
reused the 2026-10-15 sop_rev2_smoke result (selfish_matrix skips cells it has
results for), so its 40-daemon smoke started first and alone; that queue was
stopped before its checks. This waits for that 40-daemon matrix process to
exit, then runs the 12-daemon smoke under a new spec name (sop_v3_smoke), then
the checks on both: spec oracle, lateness probe, late-start scan, and
SIM-SoP-DEC records by log version (all should be v3).

Usage, from the repo root:
  setsid nohup venv/bin/python .claude/campaign8/run_smokes_v3b.py WAIT_PID \
      > .claude/campaign8/run_smokes_v3b.out 2>&1 &
"""
import os
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
T0 = time.mktime(time.strptime("2026-10-19 10:15:00", "%Y-%m-%d %H:%M:%S"))
SMALL = ["scripts/selfish_matrix.py", ".claude/campaign8/after_queue/sop_v3_smoke.yaml",
         "--cells", "share_sop2_a040_d2", "--parallel", "1"]
DEC_V = re.compile(r'SIM-SoP-DEC.*?"v":\s*(\d+)')


def log(msg):
    with open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def runs_since(spec):
    return sorted(p for p in A.glob(f"*_{spec}__*") if p.is_dir() and p.stat().st_mtime >= T0)


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
    wait_pid = int(sys.argv[1])
    OUT.mkdir(exist_ok=True)
    log(f"v3b start; waiting for pid {wait_pid} (40-daemon smoke)")
    while alive(wait_pid):
        time.sleep(30)
    log("40-daemon smoke process gone")
    log("start " + " ".join(SMALL))
    with open(OUT / "small.out", "w") as fh:
        r = subprocess.run([PY, *SMALL], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"small done rc={r.returncode}")
    runs = runs_since("sop_v3_smoke") + runs_since("sop_v3_smoke_n40")
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
            rr = subprocess.run(["nice", "-n", "10", PY, *args], cwd=REPO, stdout=fh,
                                stderr=subprocess.STDOUT)
        log(f"check {k} rc={rr.returncode}")
    with open(OUT / "versions.out", "w") as fh:
        for p in runs:
            fh.write(f"{p.name}: {dict(version_counts(p))}\n")
    log("check versions done")
    log("queue end")


if __name__ == "__main__":
    main()
