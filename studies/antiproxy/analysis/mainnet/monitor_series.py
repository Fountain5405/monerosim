#!/usr/bin/env python3
"""Turn a poll_node.py monitor directory into address-free series.

Usage:
    monitor_series.py <monitor-dir> --spy-cidrs FILE [--csv series.csv] [--json summary.json]

--spy-cidrs: text file, one a.b.c.0/24 per line (# comments, blanks allowed).
Outputs hold aggregates only, never an address. With neither --csv nor --json
the JSON summary is printed to stdout.
"""
import argparse
import csv
import glob
import gzip
import json
import os
import statistics
import sys
from datetime import datetime, timezone

PEER_COLS = ["ts", "white_size", "gray_size", "spy_white", "spy_white_share",
             "spy_gray", "newest20_spy", "spy_age_med_s", "honest_age_med_s"]
CONN_COLS = ["n_in", "n_out", "spy_in", "spy_out"]


def ts_to_unix(ts):
    """poll_node ticks carry ts as unix seconds (float); also accept ISO text."""
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return float(ts)
    except ValueError:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()


def load_spy_cidrs(path):
    out = set()
    for line in open(path):
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(tuple(line.split("/")[0].split(".")[:3]))
    return out


def ip_of(entry):
    host = entry.get("host")
    if isinstance(host, str) and host.count(".") == 3:
        return host
    ip = entry.get("ip")
    if isinstance(ip, int):
        return ".".join(str((ip >> (8 * i)) & 0xff) for i in range(4))
    return ip if isinstance(ip, str) else None


def prefix(ip):
    return tuple(ip.split(".")[:3]) if ip else None


def read_jsonl(monitor_dir, stem):
    files = sorted(glob.glob(os.path.join(monitor_dir, stem + "-*.jsonl")) +
                   glob.glob(os.path.join(monitor_dir, stem + "-*.jsonl.gz")),
                   key=os.path.basename)
    for fn in files:
        op = gzip.open if fn.endswith(".gz") else open
        with op(fn, "rt") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue


def med(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def peer_row(t, white, gray, spy):
    white = white or []
    gray = gray or []
    ws = [(prefix(ip_of(e)), e) for e in white]
    spy_w = [e for p, e in ws if p in spy]
    ages_s = [t - e["last_seen"] for p, e in ws if p in spy and "last_seen" in e]
    ages_h = [t - e["last_seen"] for p, e in ws if p not in spy and "last_seen" in e]
    seen, newest = set(), []
    for p, e in sorted(ws, key=lambda x: -x[1].get("last_seen", 0)):
        if p in seen:
            continue
        seen.add(p)
        newest.append(p)
    return {
        "ts": t, "white_size": len(white), "gray_size": len(gray),
        "spy_white": len(spy_w),
        "spy_white_share": len(spy_w) / len(white) if spy_w else None,
        "spy_gray": sum(1 for e in gray if prefix(ip_of(e)) in spy),
        "newest20_spy": sum(1 for p in newest[:20] if p in spy),
        "spy_age_med_s": med(ages_s), "honest_age_med_s": med(ages_h),
    }


def conn_row(t, conns, spy):
    conns = conns or []
    inc = [c for c in conns if c.get("incoming")]
    out = [c for c in conns if not c.get("incoming")]
    return {"ts": t, "n_in": len(inc), "n_out": len(out),
            "spy_in": sum(1 for c in inc if prefix(ip_of(c)) in spy),
            "spy_out": sum(1 for c in out if prefix(ip_of(c)) in spy)}


def build(monitor_dir, spy):
    rows, last = [], None
    for tk in read_jsonl(monitor_dir, "peerlist"):
        if tk.get("error"):
            continue
        t = ts_to_unix(tk["ts"])
        if tk.get("unchanged"):
            if last is None:
                continue
        else:
            last = (tk.get("white_list"), tk.get("gray_list"))
        rows.append(peer_row(t, last[0], last[1], spy))
    conns = [conn_row(ts_to_unix(tk["ts"]), tk.get("connections"), spy)
             for tk in read_jsonl(monitor_dir, "connections")
             if not tk.get("error") and tk.get("connections") is not None]
    conns.sort(key=lambda r: r["ts"])
    j = -1
    for r in rows:
        while j + 1 < len(conns) and conns[j + 1]["ts"] <= r["ts"]:
            j += 1
        for c in CONN_COLS:
            r[c] = conns[j][c] if j >= 0 else None
    hours = {}
    for d in read_jsonl(monitor_dir, "dials"):
        h = int(ts_to_unix(d["ts"]) // 3600)
        tot, sp = hours.get(h, (0, 0))
        hours[h] = (tot + 1, sp + (prefix(d.get("ip")) in spy))
    return rows, conns, hours


def summary(rows, hours):
    return {
        "ticks": len(rows),
        "first_ts": rows[0]["ts"] if rows else None,
        "last_ts": rows[-1]["ts"] if rows else None,
        "white_size_med": med(r["white_size"] for r in rows),
        "spy_white_share_med": med(r["spy_white_share"] for r in rows),
        "newest20_spy_med": med(r["newest20_spy"] for r in rows),
        "spy_age_med_s_med": med(r["spy_age_med_s"] for r in rows),
        "honest_age_med_s_med": med(r["honest_age_med_s"] for r in rows),
        "n_in_med": med(r["n_in"] for r in rows),
        "spy_in_med": med(r["spy_in"] for r in rows),
        "dials_per_hour": {"total_med": med(v[0] for v in hours.values()),
                           "spy_med": med(v[1] for v in hours.values()),
                           "hours": len(hours)},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("monitor_dir")
    p.add_argument("--spy-cidrs", required=True)
    p.add_argument("--csv")
    p.add_argument("--json")
    a = p.parse_args()
    rows, _, hours = build(a.monitor_dir, load_spy_cidrs(a.spy_cidrs))
    summ = summary(rows, hours)
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, PEER_COLS + CONN_COLS)
            w.writeheader()
            for r in rows:
                w.writerow({k: ("" if r[k] is None else r[k]) for k in PEER_COLS + CONN_COLS})
    if a.json:
        with open(a.json, "w") as f:
            json.dump(summ, f, indent=2)
    if not a.csv and not a.json:
        print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
