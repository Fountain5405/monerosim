#!/usr/bin/env python3
"""One-shot post-run inspector.
Parses a run_sim.sh stdout log, finds this run's tmp/shared + archive dirs,
locates eclipse_metrics.jsonl, and prints the paper-comparison analysis
(writing CSV + SVG into results/<run_name>/). If no metrics are found, dumps the
eclipse-monitor agent stdout so the failure is visible.

Usage: analyze_run.py <run_sim_stdout.log>
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze  # noqa: E402

log = sys.argv[1]
txt = open(log, errors="replace").read()

m_tmp = re.search(r"Run tmp dir:\s*(/tmp/monerosim-[^\s]+?)(?:\s|\()", txt)
m_arch = re.search(r"Archive:\s*(\S+)", txt) or re.search(r"Run directory:\s*(\S+)", txt)
tmp = m_tmp.group(1).rstrip("/") if m_tmp else None
arch = m_arch.group(1).rstrip("/") if m_arch else None
print("run tmp dir :", tmp)
print("archive dir :", arch)

met = None
if tmp:
    cand = tmp + "/shared/eclipse_metrics.jsonl"
    if os.path.isfile(cand):
        met = cand
if not met and arch:
    hits = glob.glob(arch + "/**/eclipse_metrics.jsonl", recursive=True)
    met = hits[0] if hits else None

if met:
    run_name = os.path.basename(arch) if arch else "run"
    out_dir = os.path.join(HERE, "results", run_name)
    print("metrics     :", met)
    print()
    sys.argv = ["analyze.py", met, out_dir]
    analyze.main()
else:
    print("\n!!! no eclipse_metrics.jsonl found — dumping eclipse-monitor stdout for debug")
    pats = []
    for base in (arch, tmp):
        if base:
            pats += glob.glob(base + "/**/eclipse-monitor/*.stdout", recursive=True)
            pats += glob.glob(base + "/shadow.data/hosts/eclipse-monitor/*", recursive=True)
    pats = sorted(set(p for p in pats if os.path.isfile(p) and os.path.getsize(p) > 0))
    for p in pats:
        print("---", p)
        for line in open(p, errors="replace").read().splitlines()[-40:]:
            print(line[:400])
