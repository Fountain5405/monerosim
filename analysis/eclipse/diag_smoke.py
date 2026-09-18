#!/usr/bin/env python3
"""Diagnose a run: find eclipse metrics + the eclipse-monitor agent log.
Usage: diag_smoke.py <run_tmp_dir> <archive_dir>"""
import glob
import os
import sys

tmp = sys.argv[1].rstrip("/")
arch = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else ""

print("=== shared dir contents:", tmp + "/shared ===")
sd = tmp + "/shared"
if os.path.isdir(sd):
    for f in sorted(os.listdir(sd)):
        p = os.path.join(sd, f)
        try:
            sz = os.path.getsize(p)
        except OSError:
            sz = -1
        print("  %10d  %s" % (sz, f))
else:
    print("  (missing)")

met = sd + "/eclipse_metrics.jsonl"
if os.path.isfile(met):
    n = sum(1 for _ in open(met))
    print("\n=== eclipse_metrics.jsonl: %d lines ===" % n)
    lines = open(met).read().splitlines()
    for l in lines[:2]:
        print("  FIRST:", l[:500])
    for l in lines[-3:]:
        print("  LAST :", l[:500])
else:
    print("\n=== NO eclipse_metrics.jsonl in shared dir ===")

# find eclipse-monitor agent log/stdout anywhere under tmp and arch
print("\n=== eclipse-monitor logs ===")
pats = []
for base in [tmp, arch]:
    if not base:
        continue
    pats += glob.glob(base + "/**/*eclipse-monitor*", recursive=True)
    pats += glob.glob(base + "/**/eclipse-monitor/**", recursive=True)
# shadow.data host dirs
for base in [tmp, arch]:
    if not base:
        continue
    pats += glob.glob(base + "/shadow.data/hosts/eclipse-monitor/*", recursive=True)
pats = sorted(set(p for p in pats if os.path.isfile(p)))
for p in pats[:12]:
    print("  file:", p, os.path.getsize(p))
# dump the most promising (largest stdout/err)
cand = [p for p in pats if p.endswith((".stdout", ".stderr", ".log")) or "monitor" in os.path.basename(p)]
cand.sort(key=lambda p: os.path.getsize(p), reverse=True)
if cand:
    p = cand[0]
    print("\n=== tail of %s ===" % p)
    txt = open(p, errors="replace").read().splitlines()
    for l in txt[-60:]:
        print(l[:400])
else:
    print("  (no monitor stdout/log file found)")
