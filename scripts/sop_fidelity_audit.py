#!/usr/bin/env python3
"""Sims versus the race model, per alpha (2026-10-26, experiment 4 of the
post-ladder plan): the 72 h cells' JSONs (matrix_runs/<spec>/cells/*.json:
share, attacker_orphan_rate, network_orphan_rate, canonical_blocks) against
the model's baseline rows (data/sop_search/baseline.jsonl, the sim's own
rule through sop_attacker_search.evaluate: share, att_orphan_rate,
net_orphan_rate, reveals per 2000 d). Reads JSON only; no simulation.

    python scripts/sop_fidelity_audit.py [spec] [baseline.jsonl]
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_cells(spec: str):
    cells = defaultdict(list)
    for p in sorted(glob.glob(str(ROOT / "matrix_runs" / spec / "cells" / "*.json"))):
        m = re.search(r"_a0(\d\d)_s\d+", p)
        if not m:
            continue
        with open(p) as f:
            cells[int(m.group(1)) / 100].append(json.load(f))
    return cells


def load_model(path: Path):
    model = defaultdict(list)
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if not r["knobs"]:            # the baseline: all knobs at their defaults
                    model[round(r["alpha"], 2)].append(r)
    return model


def mean(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else float("nan")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    spec = argv[0] if argv else "sop_v4_o5_noown_72h"
    base = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "sop_search" / "baseline.jsonl"
    cells, model = load_cells(spec), load_model(base)
    print(f"{spec} (sims, 72 h cells) vs race model (sim_stubborn, {base.name})")
    print(f"{'alpha':>5} | {'share':>7} {'att_orph':>8} {'net_orph':>8} {'blocks':>6} n | "
          f"{'share':>7} {'att_orph':>8} {'net_orph':>8} {'rev/day':>7} {'reorg':>5} n | {'d share':>7}")
    for a in sorted(set(cells) | set(model)):
        cs, ms = cells.get(a, []), model.get(a, [])
        rev_day = mean(ms, "reveals") / mean(ms, "days") if ms else float("nan")
        print(f"{a:5.2f} | {mean(cs, 'share'):7.4f} {mean(cs, 'attacker_orphan_rate'):8.3f} "
              f"{mean(cs, 'network_orphan_rate'):8.3f} {mean(cs, 'canonical_blocks'):6.0f} {len(cs)} | "
              f"{mean(ms, 'share'):7.4f} {mean(ms, 'att_orphan_rate'):8.3f} {mean(ms, 'net_orphan_rate'):8.3f} "
              f"{rev_day:7.1f} {mean(ms, 'mean_reorg'):5.2f} {len(ms)} | {mean(cs, 'share') - mean(ms, 'share'):+7.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
