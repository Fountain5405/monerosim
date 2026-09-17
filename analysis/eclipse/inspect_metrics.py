#!/usr/bin/env python3
"""Inspect a metrics file + monitor stdout for schema/errors.
Usage: inspect_metrics.py <run_tmp_dir> <archive_dir>"""
import glob
import json
import os
import sys

tmp = sys.argv[1].rstrip("/")
arch = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else ""
met = tmp + "/shared/eclipse_metrics.jsonl"

if os.path.isfile(met):
    rows = [json.loads(l) for l in open(met) if l.strip()]
    print("rows:", len(rows))
    last = rows[-1]
    print("\n=== last record (top-level) ===")
    print({k: v for k, v in last.items() if k != "targets"})
    print("\n=== last target record (all fields) ===")
    if last.get("targets"):
        print(json.dumps(last["targets"][0], indent=1))
    # find first record that has any peerlist error or white data
    for r in rows:
        t = (r.get("targets") or [{}])[0]
        if t.get("peerlist_err") or t.get("white_total"):
            print("\n=== first target w/ peerlist info (sim_t=%s) ===" % r.get("sim_t"))
            print(json.dumps(t, indent=1))
            break

# monitor stdout: SAMPLE + error lines
print("\n=== eclipse-monitor stdout (SAMPLE/err/log lines) ===")
pats = []
for base in (arch, tmp):
    if base:
        pats += glob.glob(base + "/shadow.data/hosts/eclipse-monitor/*.stdout", recursive=True)
pats = sorted(set(p for p in pats if os.path.isfile(p) and os.path.getsize(p) > 0))
for p in pats:
    txt = open(p, errors="replace").read().splitlines()
    keep = [l for l in txt if ("SAMPLE" in l or "err" in l.lower() or "Traceback" in l or "EclipseMonitor up" in l)]
    print("---", p, "(%d lines, showing %d matched)" % (len(txt), len(keep)))
    for l in keep[:40]:
        print(l[:500])
