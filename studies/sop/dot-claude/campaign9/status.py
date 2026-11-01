#!/usr/bin/env python3
"""Compact campaign status. Usage: status.py [--events]"""
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
C9 = REPO / ".claude/campaign9"
PROG = re.compile(r"Progress:\s*(\d+)%.*?simulated:\s*([\d:.]+)/([\d:.]+),\s*realtime:\s*([\d:.]+)")
ALERT_BAD = re.compile(r"RAM 9|RAM 100")
SWAP = re.compile(r"swap\s+([\d.]+)\s*GB")


def hms(s):
    p = [float(x) for x in s.split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def fmt(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def parse_progress(text):
    """Last Progress line (lines separated by \\r or \\n) ->
    dict(pct, sim, total, real, eta) in seconds, or None."""
    last = None
    for ln in re.split(r"[\r\n]", text):
        m = PROG.search(ln)
        if m:
            last = m
    if not last:
        return None
    pct, sim, tot, real = int(last[1]), hms(last[2]), hms(last[3]), hms(last[4])
    eta = (tot - sim) * real / sim if sim > 0 else None
    return {"pct": pct, "sim": sim, "total": tot, "real": real, "eta": eta}


def alert_is_bad(line):
    if ALERT_BAD.search(line):
        return True
    m = SWAP.search(line)
    return bool(m and float(m[1]) > 300)


def diff_state(prev, cur):
    """States: {'runs': {name: pct}, 'queue': [lines], 'chain': [lines],
    'go': str, 'halt': str, 'alerts': {name: [lines]}}. -> list of event strings."""
    ev = []
    for n in cur["runs"]:
        if n not in prev["runs"]:
            ev.append(f"RUN appeared: {n} ({cur['runs'][n]}%)")
    for n in prev["runs"]:
        if n not in cur["runs"]:
            ev.append(f"RUN gone: {n} (last {prev['runs'][n]}%)")
    for n, p in cur["runs"].items():
        if n in prev["runs"] and p // 10 > prev["runs"][n] // 10:
            ev.append(f"PROGRESS {n}: {p}%")
    for key in ("queue", "chain"):
        for ln in cur[key][len(prev[key]):]:
            ev.append(f"{key}.log: {ln}")
    for key in ("go", "halt"):
        if cur[key] != prev[key]:
            ev.append(f"{key.upper()} changed: {prev[key]!r} -> {cur[key]!r}")
    for n, lines in cur["alerts"].items():
        for ln in lines[len(prev["alerts"].get(n, lines if n not in prev["alerts"] else [])):]:
            if alert_is_bad(ln):
                ev.append(f"ALERT {n}: {ln}")
    return ev


def live_runs():
    """[(run_dir Path)] from `pgrep -ax shadow`."""
    out = subprocess.run(["pgrep", "-ax", "shadow"], capture_output=True, text=True).stdout
    runs = []
    for ln in out.splitlines():
        m = re.search(r"\s-d\s+(\S+)", ln)
        if m and re.match(r"\d+ \S*shadow\s", ln):
            runs.append(Path(m[1]).parent)
    return runs


def read_tail(p, n=None):
    try:
        lines = Path(p).read_text(errors="replace").splitlines()
    except OSError:
        return []
    return lines[-n:] if n else lines


def read_text(p):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return ""


def last_progress(run):
    p = run / "shadow_run.log"
    try:
        with open(p, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 20000))
            return parse_progress(fh.read().decode(errors="replace"))
    except OSError:
        return None


def snapshot():
    runs, alerts = {}, {}
    for r in live_runs():
        pr = last_progress(r)
        runs[r.name] = pr["pct"] if pr else 0
        alerts[r.name] = read_tail(r / "memory_alerts.log")
    return {"runs": runs, "queue": read_tail(C9 / "queue.log"), "chain": read_tail(C9 / "chain.log"),
            "go": read_text(C9 / "GO"), "halt": read_text(C9 / "HALT"), "alerts": alerts}


def box():
    mi = {}
    for ln in open("/proc/meminfo"):
        k, v = ln.split(":")
        mi[k] = int(v.split()[0]) / 1048576
    used = mi["MemTotal"] - mi["MemAvailable"]
    swap = mi["SwapTotal"] - mi["SwapFree"]
    load = open("/proc/loadavg").read().split()[:3]
    ps = subprocess.run(["ps", "-eo", "user:20,comm"], capture_output=True, text=True).stdout.splitlines()[1:]
    nshadow = sum(1 for l in ps if l.split()[-1] == "shadow")
    others = sorted({l.split()[0] for l in ps if l.split()[-1] in ("shadow", "knell")} - {_me()})
    knell = any(l.split()[-1] == "knell" for l in ps)
    return (f"box: RAM used {used:.0f} GB / free {mi['MemAvailable']:.0f} GB, load {' '.join(load)}, "
            f"swap used {swap:.0f} GB, shadow procs {nshadow}, knell {'RUNNING' if knell else 'no'}, "
            f"other users running shadow/knell: {', '.join(others) or 'none'}")


def _me():
    import getpass
    return getpass.getuser()


def show():
    print(f"time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC")
    print(box())
    runs = live_runs()
    for r in runs:
        pr = last_progress(r)
        if pr:
            eta = fmt(pr["eta"]) if pr["eta"] is not None else "?"
            print(f"run {r.name}: {pr['pct']}%  sim {fmt(pr['sim'])}/{fmt(pr['total'])}  real {fmt(pr['real'])}  ETA {eta}")
        else:
            print(f"run {r.name}: no Progress line yet")
        al = read_tail(r / "memory_alerts.log", 1)
        if al:
            print(f"  last alert: {al[0]}")
    if not runs:
        print("no live shadow run")
    for name in ("GO", "HALT"):
        print(f"{name}: {read_text(C9 / name) if (C9 / name).exists() else '(absent)'}")
    for name in ("queue.log", "chain.log"):
        t = read_tail(C9 / name, 5)
        if t:
            print(f"--- {name} (last 5)")
            print("\n".join(t))


def idle():
    for pat in ("shadow", "run_queue_v4.py", "chain.py"):
        f = "-x" if pat == "shadow" else "-f"
        r = subprocess.run(["pgrep", f, pat], capture_output=True, text=True)
        pids = [p for p in r.stdout.split() if int(p) != __import__("os").getpid()]
        if pids:
            return False
    return True


def watch():
    print("WATCH started", flush=True)
    prev, quiet = snapshot(), 0
    while True:
        time.sleep(60)
        cur = snapshot()
        for e in diff_state(prev, cur):
            print(f"{time.strftime('%H:%M:%S', time.gmtime())} {e}", flush=True)
        prev = cur
        quiet = quiet + 1 if idle() else 0
        if quiet >= 3:
            print("IDLE: nothing running", flush=True)
            return


if __name__ == "__main__":
    if "--events" in sys.argv:
        watch()
    else:
        show()
