#!/usr/bin/env python3
"""Scale smoke, held until queue v2 has finished (owner, 2026-10-21: "hold the
smoke until the whole queue finishes").

Waits for run_queue_hs2.py (pid QUEUE) to exit, requires its last log line to be
"queue end" (so a killed queue does not release the smoke), waits for any other
Shadow process to be gone (the smoke takes every free core), then runs
  scripts/selfish_matrix.py test_configs/matrix/sop_scale_n300_hs_a045_d5_8h.yaml
sampling memory once a minute to .claude/campaign8/hs/scale_n300_mem.csv.
Afterwards it logs the cell's wall time and sim/wall ratio and runs the oracle
and embed checks on the run. Everything is logged to queue_hs.log with the tag
[scale]. It does NOT start the 1,000-node run: that waits for the owner.

  venv/bin/python .claude/campaign8/run_scale_after_queue.py --check   # report only
Cancel before it fires: kill the watcher pid (it holds no sim).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
C8 = REPO / ".claude/campaign8"
LOG = C8 / "queue_hs.log"
OUT = C8 / "hs"
SPEC = "sop_scale_n300_hs_a045_d5_8h"
SIM_H = 8
HOSTS_SMOKE, HOSTS_FULL = 313, 1013
QUEUE = (2233636, "run_queue_hs2.py")


def log(msg):
    with open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [scale] {msg}\n")


def alive(pid, needle):
    try:
        return needle in Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace")
    except OSError:
        return False


def shadow_pids():
    out = []
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                argv = (d / "cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            if argv and argv[0].endswith(b"/shadow"):
                out.append(int(d.name))
    return out


def mem_gb():
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0])
    return (m["MemTotal"] - m["MemAvailable"]) / 1048576, m["MemAvailable"] / 1048576


def v2_last_line():
    lines = [x for x in LOG.read_text().splitlines() if " [v2] " in x]
    return lines[-1] if lines else ""


def check(name, args, out):
    with open(out, "w") as fh:
        r = subprocess.run(["nice", "-n", "10", PY, *args], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"check {name} rc={r.returncode}")


def report(cell_json, peak, base):
    d = json.loads(cell_json.read_text())
    ratio = SIM_H * 3600 / d["wall_s"]
    log(f"smoke cell {d['cell']}: rc={d['returncode']} health={d['health']['summary']} wall {d['wall_s'] / 3600:.2f} h "
        f"for {SIM_H} sim-h, ratio {ratio:.2f} (includes the ramp and start-up); "
        f"peak used memory {peak:.0f} GB, {base:.0f} GB before launch")
    log(f"ASSUMPTION, not measured: if cost per sim-second grows linearly with hosts, the {HOSTS_FULL}-host ratio is about "
        f"{ratio * HOSTS_SMOKE / HOSTS_FULL:.2f}, i.e. 72 sim-h in about "
        f"{72 / (ratio * HOSTS_SMOKE / HOSTS_FULL):.0f} wall-h")
    if d["returncode"] == 0 and d.get("run_dir"):
        run = Path(d["run_dir"])
        check("scale oracle", ["scripts/sop_oracle.py", "check", str(run)], OUT / "scale_n300_oracle.out")
        check("scale embed", [".claude/campaign8/embed_check.py", run.name], OUT / "scale_n300_embed.out")


def main():
    if "--check" in sys.argv:
        print("queue alive:", alive(*QUEUE), "| v2 last line:", v2_last_line() or "none")
        print("shadow pids:", shadow_pids(), "| mem used/avail GB: %.0f/%.0f" % mem_gb())
        print("would run:", PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{SPEC}.yaml", "--parallel 1")
        return 0
    if not alive(*QUEUE):
        log(f"queue pid {QUEUE[0]} ({QUEUE[1]}) is not running at start; NOT scheduling the smoke")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"holding the n300 scale smoke ({SPEC}) until queue v2 (pid {QUEUE[0]}) has finished")
    while alive(*QUEUE):
        time.sleep(60)
    last = v2_last_line()
    if not last.endswith("queue end"):
        log(f"queue v2 exited without 'queue end' (last v2 line: {last!r}); NOT starting the smoke")
        return 1
    waited = 0
    while shadow_pids():
        if waited % 60 == 0:
            log(f"queue v2 finished, but Shadow processes {shadow_pids()} are still running; waiting for a free box")
        waited += 1
        time.sleep(60)
    base, _ = mem_gb()
    log(f"queue v2 finished; starting {SPEC} ({base:.0f} GB memory used before launch)")
    args = [PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{SPEC}.yaml", "--parallel", "1"]
    t0, peak, n = time.time(), base, 0
    with open(OUT / f"{SPEC}.matrix.out", "a") as fh, open(OUT / "scale_n300_mem.csv", "a") as csv:
        csv.write("time,used_gb,avail_gb\n")
        proc = subprocess.Popen(args, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            used, avail = mem_gb()
            peak = max(peak, used)
            csv.write(f"{time.strftime('%F %T')},{used:.1f},{avail:.1f}\n")
            csv.flush()
            n += 1
            if n % 60 == 0:
                log(f"smoke running, {(time.time() - t0) / 3600:.1f} wall-h; memory used {used:.0f} GB (peak {peak:.0f})")
            time.sleep(60)
    wall_h = (time.time() - t0) / 3600
    log(f"smoke matrix process done rc={proc.returncode} after {wall_h:.2f} wall-h")
    cells = sorted((REPO / "matrix_runs" / SPEC / "cells").glob("*.json"))
    if cells:
        report(cells[-1], peak, base)
    else:
        log("no cell result file; no checks run")
    log(f"scale smoke end; {HOSTS_FULL}-host run sop_scale_n1000_hs_a045_d5_72h NOT started (owner decides after reading the ratio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
