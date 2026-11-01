#!/usr/bin/env python3
"""Wait for the smoke, check it, then launch run_queue_v4.py on GO.
Usage: chain.py --wait-pid PID --smoke-run DIR [--queue-cmd CMD ...]"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
C9 = REPO / ".claude/campaign9"
LOG = C9 / "chain.log"
DEFAULT_QUEUE = [str(REPO / "venv/bin/python"), str(C9 / "run_queue_v4.py")]


def log(msg):
    with open(LOG, "a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC {msg}\n")


def read_go(path=None):
    try:
        return int((path or C9 / "GO").read_text().strip())
    except (OSError, ValueError):
        return 0


def decide(rc, go, halt_exists):
    """-> 'halt' | 'launch' | 'wait'"""
    if rc == 1 or halt_exists:
        return "halt"
    return "launch" if go >= 1 else "wait"


def launch(cmd):
    with open(C9 / "queue.out", "a") as out:
        p = subprocess.Popen(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    log(f"launched queue pid {p.pid}: {' '.join(cmd)}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-pid", type=int, required=True)
    ap.add_argument("--smoke-run", required=True)
    ap.add_argument("--queue-cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.queue_cmd or DEFAULT_QUEUE
    log(f"waiting for pid {a.wait_pid}")
    while os.path.exists(f"/proc/{a.wait_pid}"):
        time.sleep(10)
    log(f"smoke ended (pid {a.wait_pid} gone)")
    r = subprocess.run([sys.executable, str(C9 / "check_run.py"), a.smoke_run], cwd=REPO, capture_output=True, text=True)
    summ = [l for l in r.stdout.splitlines() if l.startswith("CHECK")]
    log(summ[-1] if summ else f"check_run rc={r.returncode} no CHECK line: {r.stderr[-300:]}")
    halt = C9 / "HALT"
    d = decide(r.returncode, read_go(), halt.exists())
    if d == "halt":
        if not halt.exists():
            halt.write_text(f"smoke check FAILED: {summ[-1] if summ else 'rc=' + str(r.returncode)}\n")
        log("decision: HALT written, stopping")
        return 1
    state = "PASS" if r.returncode == 0 else "WARN"
    if d == "launch":
        log(f"decision: smoke gate {state}, GO={read_go()}: launching queue")
        launch(cmd)
        return 0
    log(f"smoke gate {state}; waiting for GO")
    deadline = time.time() + 12 * 3600
    while time.time() < deadline:
        time.sleep(60)
        if halt.exists():
            log("HALT exists; not launching")
            return 1
        if read_go() >= 1:
            log(f"GO={read_go()}: launching queue")
            launch(cmd)
            return 0
    log("GO wait timed out after 12 h; not launching")
    return 1


if __name__ == "__main__":
    sys.exit(main())
