#!/usr/bin/env python3
"""Second-round readout for sop_v4_param_72h (2026-10-27): per alpha, the sims'
mean share over seeds next to the race model's prediction for the same knobs
(data/sop_search/stage3_curve.jsonl, 2000 d x 3 seeds), reveals per 1,000 found
blocks (model and, with --pool, sims), and the
sims' crossing of honest mining two ways: linear interpolation of the mean
(share - alpha) between the two alphas that bracket zero, and a least-squares
line of (share - alpha) on alpha over every cell from 0.45 to 0.48.
Usage: sop_param_readout.py <cells dir> [stage3 jsonl] [--pool=<archive pool>]
(the pool's lane-gate summaries give the sims' reveal counts)"""
import glob
import json
import math
import re
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


def model_reveals_per_1000_found(row: dict) -> float:
    """A race-model result line's reveals per 1,000 found blocks (canonical and
    orphaned): the only basis comparable with the sims (the model's 72 h is 2,160
    found blocks, a sim's 72 h holds 1.4-1.6x that, 2026-10-27)."""
    found = row["att_final"] + row["att_orphaned"] + row["hon_final"] + row["hon_orphaned"]
    return row["reveals"] / found * 1000


def sim_reveals_per_1000_found(cell: dict, pool: str):
    """A sim cell's reveals (the lane gate's summary.txt 'reveals=N' for the cell's
    run, anywhere under <pool>/*/campaign9/) per 1,000 found blocks
    (canonical / (1 - network orphan rate)); None when no summary is found."""
    run = str(cell.get("run_dir", "")).rstrip("/").split("/")[-1]
    for f in glob.glob(f"{pool}/*/campaign9/{run}/summary.txt"):
        m = re.search(r"reveals=(\d+)", open(f).read())
        if m:
            found = cell["canonical_blocks"] / (1.0 - cell["network_orphan_rate"])
            return int(m.group(1)) / found * 1000
    return None


def fit_crossing(points):
    """points: [(alpha, share - alpha)] -> alpha where the least-squares line is 0."""
    xs, ys = zip(*points)
    mx, my = st.mean(xs), st.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in points) / sum((x - mx) ** 2 for x in xs)
    return mx - my / b, b


def main(argv):
    args = [x for x in argv[1:] if not x.startswith("--pool=")]
    pool = next((x.split("=", 1)[1] for x in argv[1:] if x.startswith("--pool=")), None)
    cells = args[0]
    model = model_rows(args[1] if len(args) > 1 else "data/sop_search/stage3_curve.jsonl")
    sims = sim_cells(cells)
    print("| alpha | knobs | model share | sim shares | sim mean | sim - model | sim - alpha | "
          "reveals per 1,000 found, model / sims | health |")
    print("|---|---|---|---|---|---|---|---|---|")
    pts, means = [], {}
    for a in sorted(sims):
        m = model.get(a, [])
        ms = st.mean(r["share"] for r in m) if m else float("nan")
        mrev = st.mean(model_reveals_per_1000_found(r) for r in m) if m else float("nan")
        srev = [x for x in (sim_reveals_per_1000_found(d, pool) for _, d in sims[a]) if x is not None] if pool else []
        srev_s = f"{st.mean(srev):.1f}" if srev else "-"
        shares = [d["share"] for _, d in sims[a]]
        mean = st.mean(shares)
        means[a] = mean
        health = ",".join(sorted({(d.get("health") or {}).get("summary", "?") if isinstance(d.get("health"), dict) else str(d.get("health")) for _, d in sims[a]}))
        k = KNOBS.get(a, {})
        print(f"| {a:.2f} | G={k.get('G')} L={k.get('L')} R={k.get('R')} | {ms:.3f} | "
              f"{', '.join(f'{x:.3f}' for x in shares)} | {mean:.3f} | {mean - ms:+.3f} | {mean - a:+.3f} | "
              f"{mrev:.1f} / {srev_s} | {health} |")
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
