#!/usr/bin/env python3
"""R3/R4 probes over log-v4 runs: python sop_v4_probes.py RUN_DIR...

Per node: v4 decisions; objective decisions with pool_main_counted or
pool_alt_counted > 0; decisions with alt_tips >= 2 (R4); decisions a later
share arrival would flip (R3, each record counted once)."""
import copy
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sop_oracle import decide_v4, parse_log_line  # noqa: E402

SHARE = re.compile(r"SIM-SoP: pooled (?:local|remote) share <(\w+)> at height \d+ "
                   r"prev <?(\w+)>? slot (\d+) tip [01]")


def stamp_ms(line):
    """Arrival time in ms from the leading 'YYYY-MM-DD HH:MM:SS.mmm'."""
    try:
        t = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return None
    return int(t.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _flipped(rec, adds_alt, adds_main):
    r = copy.deepcopy(rec)
    r["pool_alt"] = list(r.get("pool_alt") or []) + adds_alt
    r["pool_main"] = list(r.get("pool_main") or []) + adds_main
    return decide_v4(r)["expected"] != decide_v4(rec)["expected"]


def probe_log(path):
    out = {"v4": 0, "pool_counted": 0, "r4": 0, "flips": 0}
    last = {}  # (alt_tip, main_tip) -> [rec, adds_alt, adds_main]

    def close(key):
        rec, aa, am = last.pop(key)
        if (aa or am) and _flipped(rec, aa, am):
            out["flips"] += 1

    with open(path, errors="replace") as f:
        for line in f:
            rec = parse_log_line(line) if "SIM-SoP-DEC" in line else None
            if rec is not None:
                if rec.get("v", 0) < 4:
                    continue
                d = decide_v4(rec)
                out["v4"] += 1
                if d["regime"] == "objective" and (
                        d["pool_main_counted"] > 0 or d["pool_alt_counted"] > 0):
                    out["pool_counted"] += 1
                if rec.get("alt_tips", 0) >= 2:
                    out["r4"] += 1
                key = (rec["alt_tip"], rec["main_tip"])
                if key in last:
                    close(key)
                last[key] = [rec, [], []]
                continue
            m = SHARE.search(line)
            if not m:
                continue
            seen = stamp_ms(line)
            entry = {"id": m.group(1), "slot": int(m.group(3)), "seen": seen,
                     "pow_ok": True}
            for (alt, main), st in last.items():
                if m.group(2) == alt:
                    st[1].append(entry)
                if m.group(2) == main:
                    st[2].append(entry)
    for key in list(last):
        close(key)
    return out


def probe_run(run_dir):
    logs = sorted(Path(run_dir).glob("daemon_logs/*/bitmonero.log"))
    return {p.parent.name: probe_log(p) for p in logs}


def main(argv=None):
    tot = {"v4": 0, "pool_counted": 0, "r4": 0, "flips": 0}
    for rd in (argv if argv is not None else sys.argv[1:]):
        print(f"== {rd}")
        for node, s in probe_run(rd).items():
            print(f"{node}: v4={s['v4']} pool_counted={s['pool_counted']} "
                  f"r4={s['r4']} r3_flips={s['flips']}")
            for k in tot:
                tot[k] += s[k]
    print(f"TOTAL: v4={tot['v4']} pool_counted={tot['pool_counted']} "
          f"r4={tot['r4']} r3_flips={tot['flips']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
