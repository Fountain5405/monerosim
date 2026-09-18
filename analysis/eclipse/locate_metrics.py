#!/usr/bin/env python3
"""Parse a run_sim.sh stdout log to find this run's dirs and the eclipse metrics.
Usage: locate_metrics.py <run_sim_stdout.log>"""
import os
import re
import sys
import glob

log = sys.argv[1]
txt = open(log, errors="replace").read()

# tail of the log (last ~40 non-empty lines) for context
lines = [l for l in txt.splitlines() if l.strip()]
print("=== run log tail ===")
for l in lines[-30:]:
    print(l[:200])

# find candidate dirs
run_ids = set(re.findall(r"/tmp/monerosim-([A-Za-z0-9_\-]+)", txt))
arch = set(re.findall(r"(archived_runs/[A-Za-z0-9_\-./]+)", txt))
print("\n=== discovered ===")
print("run_ids:", sorted(run_ids))
print("archive paths (sample):", sorted(arch)[:5])

# locate eclipse_metrics.jsonl for these run ids
found = []
for rid in run_ids:
    for p in glob.glob("/tmp/monerosim-%s/shared/eclipse_metrics.jsonl" % rid) + \
             glob.glob("/tmp/monerosim-%s/**/eclipse_metrics.jsonl" % rid, recursive=True):
        found.append(p)
# also check archive dirs
for a in arch:
    for p in glob.glob(a + "/**/eclipse_metrics.jsonl", recursive=True):
        found.append(p)
found = sorted(set(found))
print("\n=== eclipse_metrics.jsonl candidates ===")
for p in found:
    try:
        n = sum(1 for _ in open(p))
    except OSError:
        n = -1
    print("%6d lines  %s" % (n, p))
if found:
    print("\nMETRICS_PATH=%s" % found[-1])
else:
    print("\nNO METRICS FILE FOUND")
    # help debug: list shared dirs for the run ids
    for rid in run_ids:
        d = "/tmp/monerosim-%s/shared" % rid
        if os.path.isdir(d):
            try:
                print("shared dir %s contents: %s" % (d, os.listdir(d)[:20]))
            except OSError as e:
                print("shared dir %s: %s" % (d, e))
