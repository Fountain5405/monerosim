#!/usr/bin/env python3
"""Emit compact JS arrays (sim-minutes, value) for the report charts."""
import json
import sys

import os
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RUNS = {
    "baseline": "20260913_141812_eclipse_baseline.expanded",
    "attack": "20260913_143528_eclipse_attack.expanded",
    "inject": "20260913_160145_eclipse_inject_smoke.expanded",
}
extra = sys.argv[1] if len(sys.argv) > 1 else None
if extra:
    RUNS["capstone"] = extra


def series(run):
    rows = [json.loads(l) for l in open("%s/%s/eclipse_metrics.jsonl" % (RES, run)) if l.strip()]
    ctr, bor = [], []
    for r in rows:
        ts = r.get("targets") or []
        t = ts[0] if ts else {}
        m = round(r["sim_t"] / 60.0, 1)
        if t.get("n_out"):
            ctr.append([m, t.get("out_attacker", 0)])
        if r.get("benign_or_median") is not None:
            bor.append([m, round(r["benign_or_median"], 3)])
    # downsample to <= 40 points
    def ds(a):
        if len(a) <= 40:
            return a
        step = len(a) / 40.0
        return [a[int(i * step)] for i in range(40)]
    return ds(ctr), ds(bor)


out = {}
for name, run in RUNS.items():
    try:
        c, b = series(run)
        out[name] = {"ctr": c, "bor": b, "final_ctr": c[-1][1] if c else None,
                     "final_bor": b[-1][1] if b else None}
    except FileNotFoundError:
        pass
print("CHARTDATA=" + json.dumps(out))
