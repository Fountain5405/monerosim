#!/usr/bin/env python3
"""Second-round readout for sop_v4_param_72h (2026-10-27): per alpha, the sims'
mean share over seeds next to the race model's prediction for the same knobs
(data/sop_search/stage3_curve.jsonl, 2000 d x 3 seeds), reveals per 72 h, and the
sims' crossing of honest mining two ways: linear interpolation of the mean
(share - alpha) between the two alphas that bracket zero, and a least-squares
line of (share - alpha) on alpha over every cell from 0.45 to 0.48.
Usage: sop_param_readout.py <cells dir> [stage3 jsonl]"""
import glob
import json
import math
import statistics as st
import sys

KNOBS = {  # the spec's knobs per alpha cell (test_configs/matrix/sop_v4_param_72h.yaml)
    0.45: dict(G=6, L=1, M=1, R=1, Z=1), 0.46: dict(G=6, L=1, M=1, R=1, Z=1),
    0.47: dict(G=6, L=1, M=1, R=1, Z=1), 0.48: dict(G=8, L=1, M=1, R=1, Z=1),
    0.50: dict(G=20, L=0, M=1, R=3, Z=1),
}


def model_rows(path):
    out = {}
    for ln in open(path):
        r = json.loads(ln)
        a = round(r["alpha"], 2)
        k = {x: r["knobs"].get(x) for x in ("G", "L", "M", "R", "Z")}
        if a in KNOBS and k == KNOBS[a] and r.get("K", 3) == 3 and r.get("w", 16) == 16:
            out.setdefault(a, []).append(r)
    return out


def sim_cells(cells_dir):
    out = {}
    for f in sorted(glob.glob(f"{cells_dir}/share_sop2_param_a0*_s*.json")):
        d = json.load(open(f))
        a = round(int(f.split("_a0")[1][:2]) / 100, 2)
        out.setdefault(a, []).append((f.rsplit("_", 1)[1][:-5], d))
    return out


def fit_crossing(points):
    """points: [(alpha, share - alpha)] -> alpha where the least-squares line is 0."""
    xs, ys = zip(*points)
    mx, my = st.mean(xs), st.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in points) / sum((x - mx) ** 2 for x in xs)
    return mx - my / b, b


def main(argv):
    cells = argv[1]
    model = model_rows(argv[2] if len(argv) > 2 else "data/sop_search/stage3_curve.jsonl")
    sims = sim_cells(cells)
    print("| alpha | knobs | model share | model reveals/72 h | sim shares | sim mean | sim - model | sim - alpha | health |")
    print("|---|---|---|---|---|---|---|---|---|")
    pts, means = [], {}
    for a in sorted(sims):
        m = model.get(a, [])
        ms = st.mean(r["share"] for r in m) if m else float("nan")
        mrev = st.mean(r["reveals"] * 3 / r["days"] for r in m) if m else float("nan")
        shares = [d["share"] for _, d in sims[a]]
        mean = st.mean(shares)
        means[a] = mean
        health = ",".join(sorted({(d.get("health") or {}).get("summary", "?") if isinstance(d.get("health"), dict) else str(d.get("health")) for _, d in sims[a]}))
        k = KNOBS.get(a, {})
        print(f"| {a:.2f} | G={k.get('G')} L={k.get('L')} R={k.get('R')} | {ms:.3f} | {mrev:.0f} | "
              f"{', '.join(f'{x:.3f}' for x in shares)} | {mean:.3f} | {mean - ms:+.3f} | {mean - a:+.3f} | "
              f"{health} |")
        if 0.45 <= a <= 0.48:
            pts += [(a, x - a) for x in shares]
    all_d = [x - st.mean(r["share"] for r in model[a]) for a in sims for x in [d["share"] for _, d in sims[a]] if model.get(a)]
    print(f"\ncells: {sum(len(v) for v in sims.values())}; mean sim - model over all cells: {st.mean(all_d):+.3f} "
          f"(sd {st.stdev(all_d):.3f})")
    al = sorted(means)
    for lo, hi in zip(al, al[1:]):
        if means[lo] - lo < 0 <= means[hi] - hi:
            ylo, yhi = means[lo] - lo, means[hi] - hi
            print(f"crossing (interpolated means, {lo:.2f}-{hi:.2f}): {lo + (hi - lo) * (-ylo) / (yhi - ylo):.4f}")
    c, b = fit_crossing(pts)
    res = [y - (b * (x - c)) for x, y in pts]
    se_y = math.sqrt(sum(r * r for r in res) / (len(pts) - 2))
    print(f"crossing (least squares over {len(pts)} cells 0.45-0.48): {c:.4f}; slope {b:.2f}; residual sd {se_y:.3f}; "
          f"one-sd band on the crossing ~ +-{se_y / b / math.sqrt(len(pts)):.4f}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
