#!/usr/bin/env python3
"""Share-aware attacker runs, queue v2 (2026-10-20; owner: --bootfast for the
remaining cells, tail-emission smoke plus one pair). Replaces run_queue_hs.py
without restarting its two running cells: each lane first waits for its
adopted selfish_matrix process to exit. Later cells run with --bootfast (the
specs' 'bootfast: true'). Two 12-daemon lanes (14 cores each) plus the
2 h tail smoke on the 4 cores left over.

  lane 0: tail smoke sop_v3_hs_tail_smoke --cells hs_a045_d5 (2 h), then its
          checks: tail_check.py (blocks from 995 pay 0.6 XMR), spec oracle, and
          gossiped shares embedded by the attacker's miner > 0
  lane 1: (adopted) sop_v3_hs_h10_72h hs_a045_d5; then built_a045_d5,
          hs_a040_d2, built_a040_d2, hs_a030_d2, built_a030_d2, then
          deep_hunt_sop_hs_a045 (72 h)
  lane 2: (adopted) sop_v3_hs_h10_72h hs_a045_d2; then, only if the smoke
          passed, sop_v3_hs_tail_h10_72h hs_a045_d5 and built_a045_d5; then
          deep_hunt_sop_hs_a040 (240 h)

Then the checks on every run since the first queue started (16:58 UTC),
as in run_queue_hs.py, plus tail_check on the tail runs. Outputs in
.claude/campaign8/hs/; log .claude/campaign8/queue_hs.log (shared with v1).
"""
import calendar
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
T0 = calendar.timegm(time.strptime("2026-10-20 16:58:46", "%Y-%m-%d %H:%M:%S"))   # v1's start, UTC
WS, WS_TAIL, SMOKE = "sop_v3_hs_h10_72h", "sop_v3_hs_tail_h10_72h", "sop_v3_hs_tail_smoke"
ADOPT = {1: (2223909, "hs_a045_d5"), 2: (2225287, "hs_a045_d2")}
_lock = threading.Lock()
smoke_done = threading.Event()
smoke_ok = [False]


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [v2] {msg}\n")


def matrix(spec, cells=None):
    args = [PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{spec}.yaml", "--parallel", "1"]
    if cells:
        args += ["--cells", cells]
    log("start " + " ".join(args[1:]))
    t = time.time()
    with open(OUT / f"{spec}.matrix.out", "a") as fh:
        r = subprocess.run(args, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"done {spec} {cells or ''} rc={r.returncode} {(time.time() - t) / 3600:.2f} h")


def adopt(lane):
    pid, cell = ADOPT[lane]
    proc = Path(f"/proc/{pid}/cmdline")
    if not proc.exists():
        log(f"lane {lane}: adopted pid {pid} ({cell}) already gone")
        return
    if cell not in proc.read_bytes().decode(errors="replace"):
        log(f"lane {lane}: pid {pid} is not the {cell} matrix process; not waiting on it")
        return
    log(f"lane {lane}: waiting on running {WS} {cell} (pid {pid})")
    while proc.exists():
        time.sleep(60)
    log(f"done (adopted) {WS} {cell}")


def runs(spec):
    return sorted(p for p in A.glob(f"*_{spec}__*") if p.is_dir() and p.stat().st_mtime >= T0)


def check(name, args, out):
    with open(out, "w") as fh:
        r = subprocess.run(["nice", "-n", "10", PY, *args], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log(f"check {name} rc={r.returncode}")
    return r.returncode


def lane_0():
    try:
        matrix(SMOKE, "hs_a045_d5")
        smoke = runs(SMOKE)
        if not smoke:
            log("tail smoke: no run dir")
            return
        run = smoke[-1]
        ok_tail = check("smoke tail", [".claude/campaign8/tail_check.py", str(run)], OUT / "smoke_tail.out") == 0
        ok_oracle = check("smoke oracle", ["scripts/sop_oracle.py", "check", str(run)], OUT / "smoke_oracle.out") == 0
        check("smoke embed", [".claude/campaign8/embed_check.py", run.name], OUT / "smoke_embed.out")
        remote = 0
        for line in (OUT / "smoke_embed.out").read_text().splitlines():
            if "attacker-miner/bitmonero.log" in line:
                remote = int(line.split()[3])
        smoke_ok[0] = ok_tail and ok_oracle and remote > 0
        log(f"tail smoke {'PASS' if smoke_ok[0] else 'FAIL'}: tail={ok_tail} oracle={ok_oracle} "
            f"attacker gossiped shares embedded={remote}")
    finally:
        smoke_done.set()


def lane_1():
    adopt(1)
    for cell in ("built_a045_d5", "hs_a040_d2", "built_a040_d2", "hs_a030_d2", "built_a030_d2"):
        matrix(WS, cell)
    matrix("deep_hunt_sop_hs_a045")


def lane_2():
    adopt(2)
    smoke_done.wait()
    if smoke_ok[0]:
        matrix(WS_TAIL, "hs_a045_d5")
        matrix(WS_TAIL, "built_a045_d5")
    else:
        log("tail smoke did not pass: tail pair skipped")
    matrix("deep_hunt_sop_hs_a040")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log("queue v2 start: adopts v1's running cells, bootfast for the rest, tail smoke + pair")
    lanes = [threading.Thread(target=f) for f in (lane_0, lane_1, lane_2)]
    for t in lanes:
        t.start()
    for t in lanes:
        t.join()
    every = runs(WS) + runs(WS_TAIL) + runs("deep_hunt_sop_hs_a045") + runs("deep_hunt_sop_hs_a040")
    log("checks on: " + str([p.name for p in every]))
    with open(OUT / "embed.out", "w") as fh:
        for p in every:
            subprocess.run(["nice", "-n", "10", PY, ".claude/campaign8/embed_check.py", p.name],
                           cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log("check embed done")
    with open(OUT / "tail.out", "w") as fh:
        for p in runs(WS_TAIL):
            subprocess.run(["nice", "-n", "10", PY, ".claude/campaign8/tail_check.py", str(p)],
                           cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    log("check tail done")
    jobs = {
        "oracle": ["scripts/sop_oracle.py", "check", *map(str, every)],
        "probe": ["-m", "scripts.sop_lateness_probe", "replay", *map(str, every)],
        "flipback": ["scripts/selfish_mining/flipback_scan.py", *map(str, every)],
        "reveals_stats": ["scripts/selfish_mining/sop_reveals.py", "stats", str(OUT / "reveals_stats.json"), *map(str, every)],
        "reveals_depths": ["scripts/selfish_mining/sop_reveals.py", "depths", str(OUT / "reveals_depths.json"), *map(str, every)],
        "pending": ["-m", "scripts.selfish_mining.sop_pending", *map(str, every)],
    }
    for k, args in jobs.items():
        check(k, args, OUT / f"{k}.out")
    log("queue end")


if __name__ == "__main__":
    main()
