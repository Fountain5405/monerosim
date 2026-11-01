#!/usr/bin/env python3
"""Scale smoke rung 1 (owner-ordered 2026-10-23): sop_scale_n300_hs_a045_d5_8h
on the v4 build, cell share_sop2_a045. Launches the matrix run with
MONEROSIM_SHADOW_CPU_PINNING=0 (313 hosts over 32 physical cores; pinned runs
stack on CPUs 0..N-1 past 32), samples used memory + swap every 60 s to
campaign9/scale_n300_mem.csv, then runs check_run.py on the run dir. Logs
wall time, sim/wall ratio and peak RAM as `scale ...` lines to queue.log;
HALT on a nonzero rc or a gate failure. Run it ALONE (the ratio is the
measurement; no other sim, no compile). Detached launch:
  setsid nohup venv/bin/python .claude/campaign9/scale_smoke.py \
    >> .claude/campaign9/scale.out 2>&1 < /dev/null &
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
C9 = REPO / ".claude/campaign9"
LOG = C9 / "queue.log"
HALT = C9 / "HALT"
SPEC = "sop_scale_n300_hs_a045_d5_8h"
CELL = "share_sop2_a045"
STOP_S = 8 * 3600
MEMCSV = C9 / "scale_n300_mem.csv"


def log(msg):
    with open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}Z {msg}\n")


def sample_once():
    mi = {}
    for ln in open("/proc/meminfo"):
        k, _, v = ln.partition(":")
        mi[k] = int(v.split()[0]) * 1024
    used = (mi["MemTotal"] - mi["MemAvailable"]) / 2**30
    swap = (mi["SwapTotal"] - mi["SwapFree"]) / 2**30
    return used, swap


def sampler(stop, peak):
    with open(MEMCSV, "a") as fh:
        while not stop.is_set():
            used, swap = sample_once()
            peak["used"] = max(peak.get("used", 0.0), used)
            peak["swap"] = max(peak.get("swap", 0.0), swap)
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},"
                     f"{used:.1f},{swap:.1f}\n")
            fh.flush()
            stop.wait(60)


def main():
    log(f"scale smoke start {SPEC}/{CELL} (pinning off, 313 hosts, alone on the box)")
    env = dict(os.environ, MONEROSIM_SHADOW_CPU_PINNING="0")
    stop = threading.Event()
    peak = {}
    th = threading.Thread(target=sampler, args=(stop, peak), daemon=True)
    th.start()
    t0 = time.time()
    r = subprocess.run([PY, "scripts/selfish_matrix.py",
                        f"test_configs/matrix/{SPEC}.yaml",
                        "--parallel", "1", "--cells", CELL], cwd=REPO, env=env,
                       stdout=open(C9 / f"{SPEC}__{CELL}.matrix.out", "a"),
                       stderr=subprocess.STDOUT)
    wall = time.time() - t0
    stop.set()
    th.join()
    marker = REPO / "matrix_runs" / SPEC / "cells" / f"{CELL}.json"
    row = json.loads(marker.read_text()) if marker.exists() else {}
    rc = r.returncode or row.get("returncode", 1 if not row else 0)
    ratio = STOP_S / wall if wall else 0.0
    log(f"scale smoke finished {SPEC}/{CELL} rc={rc} wall={wall / 3600:.2f} h "
        f"ratio={ratio:.3f} peakRAM={peak.get('used', 0):.0f} GB "
        f"peakswap={peak.get('swap', 0):.1f} GB")
    run_dir = row.get("run_dir")
    if rc != 0 or not run_dir:
        HALT.write_text(f"scale smoke rc={rc} run_dir={run_dir} "
                        f"({row.get('error', 'no marker')})\n")
        log(f"scale HALT rc={rc} run_dir={run_dir}")
        return 1
    c = subprocess.run([PY, str(C9 / "check_run.py"), run_dir], cwd=REPO,
                       capture_output=True, text=True)
    log(f"scale check {SPEC}/{CELL} rc={c.returncode}: "
        f"{(c.stdout.strip() or c.stderr.strip())[-500:]}")
    if c.returncode == 1:
        HALT.write_text(f"scale smoke check_run gate failed ({SPEC}/{CELL})\n")
        log("scale HALT check gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
