#!/usr/bin/env python3
"""Lane driver for one box (2026-10-24): run_o5.py generalised to take the spec
and its cells on the command line, so each lane box runs its own slice of a
grid without a per-box copy of the driver. One thread per cell, all started
at once (two cells = two lanes; a 12-daemon lane is ~3.5 GB RAM). After each
cell: check_run.py; a nonzero returncode or gate failure writes
campaign9/HALT (rc=2 WARN continues). Then the finished run is synced to the
archive pool on tr (owner's choice 2026-10-24): the run dir, the cell JSON
and table, and the check outputs, under <pool>/<this hostname>/ so boxes
never collide. A sync failure is logged, not a HALT (the data stays local).
Log: campaign9/queue.log, prefixed with the spec name. Detached launch, from
the repo root:
  MONEROSIM_SHADOW_CPU_PINNING=0 setsid nohup venv/bin/python \
    .claude/campaign9/run_lane.py <spec> <cell>... \
    >> .claude/campaign9/<spec>.out 2>&1 < /dev/null &
Afterwards, on the analysis box: selfish_matrix.py <spec>.yaml --reanalyze
over the pooled cell JSONs and scripts/selfish_mining/sop_stuck_time.py
<run dirs>.
"""
import json
import socket
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
POOL = "tr:/spinny/readfrom/20261024_monerosim_research_effort"
BOX = socket.gethostname()
STAGGER_S = 90
RSYNC = ["rsync", "-a", "--mkpath", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=20"]
_lock = threading.Lock()


def log(msg):
    with _lock, open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}Z {msg}\n")


def _rsync(src, dst):
    for attempt in (1, 2):
        r = subprocess.run(RSYNC + [str(src), dst], capture_output=True, text=True)
        if r.returncode == 0:
            return True
        time.sleep(30)
    log(f"sync FAILED {src} -> {dst}: {(r.stderr or r.stdout).strip()[-300:]}")
    return False


def sync_run(tag, spec, cell, run_dir):
    """Push one finished cell to the pool. Paths mirror the repo layout."""
    base = f"{POOL}/{BOX}"
    t = time.time()
    ok = True
    ok &= _rsync(Path(run_dir), f"{base}/archived_runs/")
    ok &= _rsync(REPO / "matrix_runs" / spec / "cells" / f"{cell}.json",
                 f"{base}/matrix_runs/{spec}/cells/")
    table = REPO / "matrix_runs" / spec / "table.md"
    if table.exists():
        ok &= _rsync(table, f"{base}/matrix_runs/{spec}/")
    chk = C9 / Path(run_dir).name
    if chk.is_dir():
        ok &= _rsync(chk, f"{base}/campaign9/")
    ok &= _rsync(LOG, f"{base}/campaign9/queue.{BOX}.log")
    log(f"{tag} sync {spec}/{cell} {'ok' if ok else 'INCOMPLETE'} "
        f"wall={(time.time() - t) / 60:.1f} min -> {base}")
    return ok


def run_cell(spec, lane, cell):
    tag = spec
    if HALT.exists():
        log(f"{tag} lane {lane}: HALT exists at start; not running {cell}")
        return
    log(f"{tag} lane {lane} start {spec}/{cell}")
    t = time.time()
    r = subprocess.run([PY, "scripts/selfish_matrix.py", f"test_configs/matrix/{spec}.yaml",
                        "--parallel", "1", "--cells", cell], cwd=REPO,
                       stdout=open(C9 / f"{spec}__{cell}.matrix.out", "a"),
                       stderr=subprocess.STDOUT)
    marker = REPO / "matrix_runs" / spec / "cells" / f"{cell}.json"
    row = json.loads(marker.read_text()) if marker.exists() else {}
    rc = r.returncode or row.get("returncode", 1 if not row else 0)
    log(f"{tag} lane {lane} finished {spec}/{cell} rc={rc} wall={(time.time() - t) / 3600:.2f} h")
    run_dir = row.get("run_dir")
    if rc != 0 or not run_dir:
        HALT.write_text(f"{tag} cell rc={rc} run_dir={run_dir} ({spec}/{cell}: {row.get('error', 'no marker')})\n")
        log(f"{tag} HALT {spec}/{cell} rc={rc} run_dir={run_dir}")
        if run_dir:
            sync_run(tag, spec, cell, run_dir)
        return
    c = subprocess.run([PY, str(C9 / "check_run.py"), run_dir], cwd=REPO,
                       capture_output=True, text=True)
    log(f"{tag} check {spec}/{cell} rc={c.returncode}: {(c.stdout.strip() or c.stderr.strip())[-500:]}")
    if c.returncode == 1:
        HALT.write_text(f"{tag} check_run gate failed ({spec}/{cell})\n")
        log(f"{tag} HALT check gate {spec}/{cell}")
    sync_run(tag, spec, cell, run_dir)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    spec, cells = argv[1], argv[2:]
    if not (REPO / "test_configs/matrix" / f"{spec}.yaml").exists():
        print(f"no spec test_configs/matrix/{spec}.yaml")
        return 2
    log(f"{spec} queue start lanes={len(cells)} cells={' '.join(cells)} box={BOX}")
    ts = [threading.Thread(target=run_cell, args=(spec, i + 1, c)) for i, c in enumerate(cells)]
    for i, t in enumerate(ts):
        if i:
            # Stagger lane starts: two cells starting in the same second on a
            # cold chain-snapshot cache both run build-template and the second
            # offline monerod-sim dies on the first one's RPC port (seen on all
            # three lane boxes, 2026-10-24). 90 s covers a cold h10 build.
            time.sleep(STAGGER_S)
        t.start()
    for t in ts:
        t.join()
    log(f"{spec} queue done" if not HALT.exists() else f"{spec} queue stopped (HALT)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
