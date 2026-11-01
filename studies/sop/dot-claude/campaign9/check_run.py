#!/usr/bin/env python3
"""Task 7 Step 4 checks on one archived run.
Usage: check_run.py RUN_DIR [--out DIR] [--wait-pid PID]
Exit 0 PASS, 1 FAIL (gate), 2 WARN (a secondary check errored)."""
import argparse
import glob
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / "venv/bin/python")
A3_STR = "tip shares: published"        # agents/selfish_miner.py:366
UNDELIV_STR = "tip shares: bridge never reached"   # agents/selfish_miner.py:349
REVEAL_STR = ": reveal fork="    # agents/selfish_miner.py:950 INFO "<strategy>: reveal fork=.. a=.. h=.."
REJECT_STR = "reveal rejected by the bridge"
ALT_STR = "pooled remote share"          # patches/monero-sim-pop.patch:1876 (" tip 1/0" suffix)
NODE_RE = re.compile(r"^(\S+)\s+decisions=(\d+)\s+skipped=(\d+)\s+ties=(\d+)\s+mismatches=(\d+)")


def parse_oracle(text):
    """-> (node_lines, total_mismatches, has_traceback)"""
    nodes, mm = 0, 0
    for ln in text.splitlines():
        m = NODE_RE.match(ln)
        if m:
            nodes += 1
            mm += int(m.group(5))
    return nodes, mm, "Traceback" in text


def tip_shares_enabled(text):
    return re.search(r"tip_shares\s*:\s*['\"]?(true|1|yes)\b", text, re.I) is not None


def gate(nodes, mm, tb, tip_shares, a3, reveals=1, dead=()):
    """-> True when the run FAILS the gate. A3 missing is a failure only if the
    attacker made a reveal (else A3 was untested). A dead daemon always fails."""
    return nodes < 10 or mm > 0 or tb or bool(dead) or (tip_shares and reveals > 0 and a3 == 0)


DAEMON_TS = re.compile(rb"^(2000-\d\d-\d\d \d\d:\d\d:\d\d)")
DEAD_SLACK_S = 2 * 3600


def _last_ts(path, tail=65536):
    """Sim timestamp of the last timestamped line of a daemon log (None if none)."""
    import datetime as dt
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        fh.seek(max(0, fh.tell() - tail))
        lines = fh.read().splitlines()
    for ln in reversed(lines):
        m = DAEMON_TS.match(ln)
        if m:
            return dt.datetime.strptime(m.group(1).decode(), "%Y-%m-%d %H:%M:%S")
    return None


def dead_daemons(run_dir, slack_s=DEAD_SLACK_S):
    """Hosts whose monerod-sim log ends more than slack_s before the run's latest
    daemon line (2026-10-26: OOM-killed daemons left a run 'PASS' with a 1813-block
    split). Every live daemon logs each block (~2 min), so a 2 h gap is a dead one."""
    ends = {}
    for f in glob.glob(f"{run_dir}/shadow.data/hosts/*/monerod-sim.*.stdout"):
        t = _last_ts(f)
        if t is not None:
            ends[Path(f).parent.name] = t
    if not ends:
        return []
    ref = max(ends.values())
    return sorted(h for h, t in ends.items() if (ref - t).total_seconds() > slack_s)


def distinct_lines(files, needle):
    """Distinct agent log messages containing needle (the log is written twice per line; dedupe on timestamp+message)."""
    seen = set()
    for f in files:
        with open(f, "rb") as fh:
            for ln in fh:
                if needle.encode() in ln:
                    t = ln.decode(errors="replace")
                    i = t.find("SelfishMinerAgent")
                    seen.add((f, t[:23], t[i:].strip()))
    return seen


def count_reveals(files):
    return len(distinct_lines(files, REVEAL_STR))


def count_shares(files):
    """Sum of N over distinct 'tip shares: published N on' lines."""
    return sum(int(m.group(1)) for _, _, msg in distinct_lines(files, A3_STR)
               if (m := re.search(r"published (\d+) on", msg)))


def verdict(fail, secondary_errors):
    return "FAIL" if fail else ("WARN" if secondary_errors else "PASS")


def run(cmd, outfile, timeout=1200):
    """Run cmd, save stdout+stderr, return (rc, text). rc None = timeout."""
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, errors="replace", timeout=timeout)
        text, rc = r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        text, rc = f"TIMEOUT after {timeout}s\n{e.stdout or ''}", None
    Path(outfile).write_text(text)
    return rc, text


def grep_count(files, needle, also=None):
    """Lines containing needle (and also, if given), summed over files."""
    n = 0
    for f in files:
        with open(f, "rb") as fh:
            for ln in fh:
                if needle in ln and (also is None or also in ln):
                    n += 1
    return n


def agent_files(run_dir):
    fs = glob.glob(f"{run_dir}/agent_logs/*attacker*")
    # archived runs keep agent output under the Shadow host dirs
    fs += glob.glob(f"{run_dir}/shadow.data/hosts/*attacker*/*.std*")
    return fs


def wait_pid(pid):
    while os.path.exists(f"/proc/{pid}"):
        time.sleep(10)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out")
    ap.add_argument("--wait-pid", type=int)
    a = ap.parse_args(argv)
    if a.wait_pid:
        wait_pid(a.wait_pid)
    run_dir = Path(a.run_dir).resolve()
    base = run_dir.name
    out = Path(a.out) if a.out else REPO / ".claude/campaign9" / base
    out.mkdir(parents=True, exist_ok=True)
    rd = str(run_dir)

    rc_o, t_o = run([PY, "scripts/sop_oracle.py", "check", rd], out / "oracle.out")
    nodes, mm, tb = parse_oracle(t_o)
    rc_all, t_all = run([PY, "scripts/sop_oracle.py", "check", "--pool-rule", "all", rd], out / "oracle_all.out")
    rc_p, t_p = run([PY, "scripts/sop_v4_probes.py", rd], out / "probes.out")
    a3 = len(distinct_lines(agent_files(run_dir), A3_STR))
    (out / "a3.out").write_text(f"{a3}\n")
    a3u = len(distinct_lines(agent_files(run_dir), UNDELIV_STR))
    a3s = count_shares(agent_files(run_dir))
    nrej = len(distinct_lines(agent_files(run_dir), REJECT_STR))
    nrev = count_reveals(agent_files(run_dir))
    alt = grep_count(glob.glob(f"{rd}/daemon_logs/*honest-001/bitmonero.log"), ALT_STR.encode(), b" tip 0")
    (out / "alt_shares.out").write_text(f"{alt}\n")
    rc_e, _ = run([PY, ".claude/campaign8/embed_check.py", base], out / "embed.out")
    rc_l, _ = run([PY, "-m", "scripts.sop_lateness_probe", "replay", rd], out / "lateness.out")
    rc_r, _ = run([PY, "scripts/selfish_mining/sop_reveals.py", "stats", str(out / "reveals.json"), rd], out / "reveals.out")

    cfg = run_dir / "input_config.yaml"
    ts = tip_shares_enabled(cfg.read_text(errors="replace")) if cfg.exists() else False
    dead = dead_daemons(rd)
    fail = gate(nodes, mm, tb, ts, a3, nrev, dead)
    ok = lambda rc, t="": "ok" if rc == 0 and "Traceback" not in t else "ERR"
    probes, lat, rev, emb = ok(rc_p, t_p), ok(rc_l), ok(rc_r), ok(rc_e)
    sec = [x == "ERR" for x in (probes, lat, rev, emb)] + [rc_all != 0 or "Traceback" in t_all]
    untested = ts and nrev == 0 and a3 == 0
    v = verdict(fail, any(sec) or untested)
    line = (f"CHECK {base} oracle={mm}mm/{nodes}nodes a3={a3} reveals={nrev} a3_undelivered={a3u} a3_shares={a3s} rejected={nrej} alt_shares={alt} probes={probes} "
            f"lateness={lat} reveal_stats={rev} embed={emb} dead_daemons={','.join(dead) or 0} -> {v}")
    if untested:
        line += "  # A3 untested: attacker made no reveal"
    (out / "summary.txt").write_text(line + "\n")
    print(line, flush=True)
    return {"FAIL": 1, "WARN": 2, "PASS": 0}[v]


if __name__ == "__main__":
    sys.exit(main())
