#!/usr/bin/env python3
"""Per (K, w) of the countermeasure: the best attacker share per alpha, the
sim's rule's share, and the crossing where the best attacker's share passes
alpha, from a sop_attacker_search.py results file (data/sop_search/kw_sweep.jsonl).

    python scripts/sop_kw_table.py [kw_sweep.jsonl]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from scripts.sop_attacker_search import crossing

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else ROOT / "data" / "sop_search" / "kw_sweep.jsonl"
    rows = [json.loads(l) for l in open(path) if l.strip()]
    # (K, w, combo, alpha) -> shares
    by = defaultdict(list)
    for r in rows:
        by[(r["K"], r["w"], json.dumps(r["knobs"], sort_keys=True), r["alpha"])].append(r["share"])
    means = {k: sum(v) / len(v) for k, v in by.items()}
    kws = sorted({(K, w) for K, w, _, _ in means})
    alphas = sorted({a for _, _, _, a in means})
    print(f"{'K':>2} {'w':>3} {'window':>6} | " + " ".join(f"best@{a:.2f}" for a in alphas) + " | "
          + " ".join(f"base@{a:.2f}" for a in alphas) + " | best crossing (combo)        | base crossing")
    for K, w in kws:
        combos = sorted({c for (k, ww, c, _) in means if (k, ww) == (K, w)})
        best = {}
        for a in alphas:
            cands = [(means[(K, w, c, a)], c) for c in combos if (K, w, c, a) in means and json.loads(c)]
            best[a] = max(cands) if cands else (float("nan"), "")
        base = {a: means.get((K, w, "{}", a), float("nan")) for a in alphas}
        xs = []
        for c in combos:
            pts = [(a, means[(K, w, c, a)]) for a in alphas if (K, w, c, a) in means]
            if len(pts) >= 3:
                x = crossing(pts)
                xs.append((x if x is not None else 9.0, c))
        bx = min(xs) if xs else (9.0, "")
        bc = crossing([(a, base[a]) for a in alphas if base[a] == base[a]]) if base else None
        label = " ".join(f"{k}={v}" for k, v in json.loads(bx[1]).items()) if bx[1] else "-"
        print(f"{K:>2} {w:>3} {(K - 1) * w:>6} | " + " ".join(f"{best[a][0]:9.4f}" for a in alphas) + " | "
              + " ".join(f"{base[a]:9.4f}" for a in alphas)
              + f" | {('%.4f' % bx[0]) if bx[0] < 9 else 'none  '} {label:22s} | {('%.4f' % bc) if bc is not None else 'none'}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
