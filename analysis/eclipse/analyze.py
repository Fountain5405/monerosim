#!/usr/bin/env python3
"""Analyze eclipse_metrics.jsonl produced by agents.eclipse_monitor and print a
paper-comparison table + write CSV and small SVG figures.

Usage: python3 analyze.py <path/to/eclipse_metrics.jsonl> [out_dir]
"""
import json
import sys
import os


def load(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def fmt_pct(x):
    return "-" if x is None else "%.1f%%" % (100.0 * x)


def sparkline(vals, lo=0.0, hi=1.0):
    blocks = "▁▂▃▄▅▆▇█"
    out = []
    for v in vals:
        if v is None:
            out.append(" ")
            continue
        t = 0.0 if hi == lo else max(0.0, min(1.0, (v - lo) / (hi - lo)))
        out.append(blocks[int(t * (len(blocks) - 1))])
    return "".join(out)


def svg_line(series, path, title, ymax=1.0, ylabel=""):
    """series: list of (label, color, [(x,y),...])."""
    W, H, PAD = 720, 260, 48
    xs = [x for _, _, pts in series for x, _ in pts]
    if not xs:
        return
    xmin, xmax = min(xs), max(xs)
    xr = (xmax - xmin) or 1.0

    def sx(x):
        return PAD + (x - xmin) / xr * (W - 2 * PAD)

    def sy(y):
        return H - PAD - (y / ymax) * (H - 2 * PAD)

    el = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="sans-serif">' % (W, H)]
    el.append('<rect width="%d" height="%d" fill="white"/>' % (W, H))
    el.append('<text x="%d" y="24" font-size="15" font-weight="bold">%s</text>' % (PAD, title))
    # axes
    el.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#888"/>' % (PAD, H - PAD, W - PAD, H - PAD))
    el.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#888"/>' % (PAD, PAD, PAD, H - PAD))
    # y gridlines
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = sy(frac * ymax)
        el.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#eee"/>' % (PAD, y, W - PAD, y))
        el.append('<text x="6" y="%.1f" font-size="10" fill="#555">%.2f</text>' % (y + 3, frac * ymax))
    # x labels (minutes)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = xmin + frac * xr
        el.append('<text x="%.1f" y="%d" font-size="10" fill="#555" text-anchor="middle">%.0fm</text>'
                  % (sx(x), H - PAD + 16, x / 60.0))
    el.append('<text x="%d" y="%d" font-size="10" fill="#555" text-anchor="middle">sim time</text>'
              % (W // 2, H - 6))
    # series
    ly = PAD + 6
    for label, color, pts in series:
        if not pts:
            continue
        d = " ".join(("%s%.1f,%.1f" % ("M" if i == 0 else "L", sx(x), sy(y))) for i, (x, y) in enumerate(pts))
        el.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (d, color))
        el.append('<rect x="%d" y="%d" width="10" height="10" fill="%s"/>' % (W - 190, ly - 9, color))
        el.append('<text x="%d" y="%d" font-size="11">%s</text>' % (W - 174, ly, label))
        ly += 16
    el.append("</svg>")
    with open(path, "w") as fh:
        fh.write("\n".join(el))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    rows = load(path)
    if not rows:
        print("no metric rows found in %s" % path)
        sys.exit(2)

    # focus on the first target across time
    def t0(r):
        ts = r.get("targets") or []
        return ts[0] if ts else {}

    times = [r["sim_t"] for r in rows]
    ctr = [(r["sim_t"], t0(r).get("ctr")) for r in rows if t0(r)]
    orwhite = [(r["sim_t"], t0(r).get("or_white")) for r in rows if t0(r)]
    benign_or = [(r["sim_t"], r.get("benign_or_median")) for r in rows if r.get("benign_or_median") is not None]
    Bt = [(r["sim_t"], t0(r).get("B_target")) for r in rows if t0(r)]

    # TTE + final + stability
    def is_full_eclipse(t):
        # full eclipse = the target's entire 12-slot outbound complement is attacker
        return bool(t) and t.get("n_out", 0) >= 12 \
            and t.get("out_attacker", 0) == t.get("n_out", 0) \
            and t.get("out_benign", 0) == 0 and t.get("out_other", 0) == 0

    tte = None
    final = t0(rows[-1])
    for r in rows:
        if is_full_eclipse(t0(r)):
            tte = r["sim_t"]
            break
    # stability: contiguous tail where full eclipse holds
    stable_from = None
    for r in rows:
        if is_full_eclipse(t0(r)):
            if stable_from is None:
                stable_from = r["sim_t"]
        else:
            stable_from = None
    stability = (rows[-1]["sim_t"] - stable_from) if stable_from is not None else 0.0

    # CSV
    csv_path = os.path.join(out_dir, "eclipse_timeseries.csv")
    with open(csv_path, "w") as fh:
        fh.write("sim_t,benign_or_median,target_ctr,target_or_white,target_B,out_attacker,out_benign,out_other,n_out\n")
        for r in rows:
            t = t0(r)
            fh.write("%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (
                r["sim_t"], r.get("benign_or_median", ""),
                t.get("ctr", ""), t.get("or_white", ""), t.get("B_target", ""),
                t.get("out_attacker", ""), t.get("out_benign", ""), t.get("out_other", ""), t.get("n_out", ""),
            ))

    # SVG figures
    svg_line(
        [("target CTR (attacker outbound / 12)", "#c0392b", [(x, y) for x, y in ctr if y is not None]),
         ("benign whitelist OR (median)", "#2980b9", [(x, y) for x, y in benign_or if y is not None]),
         ("target whitelist OR", "#27ae60", [(x, y) for x, y in orwhite if y is not None])],
        os.path.join(out_dir, "eclipse_ctr_or.svg"),
        "Nyx reproduction: takeover (CTR) and peerlist occupation (OR) over time", ymax=1.0)
    bmax = max([y for _, y in Bt if isinstance(y, (int, float))] or [1])
    svg_line(
        [("target graylist benign count B", "#8e44ad", [(x, y) for x, y in Bt if isinstance(y, (int, float))])],
        os.path.join(out_dir, "eclipse_B_target.svg"),
        "Target graylist benign records (B) over time", ymax=max(bmax, 1))

    # ---- report table ----
    print("=" * 74)
    print("ECLIPSE REPRODUCTION — metric summary  (source: %s)" % path)
    print("=" * 74)
    print("polls: %d   sim window: %.0fs .. %.0fs (%.1f min)" % (
        len(rows), times[0], times[-1], (times[-1] - times[0]) / 60.0))
    n_atk = rows[-1].get("n_attacker"); n_ben = rows[-1].get("n_benign")
    print("population (final): attacker nodes=%s benign relays=%s" % (n_atk, n_ben))
    print("-" * 74)
    print("%-42s %-16s %s" % ("metric", "this run", "paper (Nyx, 1200-node)"))
    print("-" * 74)
    last_benign_or = benign_or[-1][1] if benign_or else None
    med_benign_or = max((y for _, y in benign_or), default=None)
    print("%-42s %-16s %s" % ("benign whitelist OR (median, best)", fmt_pct(med_benign_or), "~98.5% @T+10m"))
    print("%-42s %-16s %s" % ("target CTR (final)", "%d/%d" % (final.get("out_attacker", 0), final.get("n_out", 0)), "12/12 (100%)"))
    print("%-42s %-16s %s" % ("target whitelist OR (final)", fmt_pct(final.get("or_white")), "-> ~100%"))
    gtot = final.get("gray_total") or 0
    gfrac = (final.get("gray_attacker", 0) / gtot) if gtot else None
    print("%-42s %-16s %s" % ("target graylist OR (attacker frac, final)", fmt_pct(gfrac), "-> ~97%+"))
    print("%-42s %-16s %s" % ("target graylist benign B (final)", str(final.get("B_target")), "717 -> ~2"))
    print("%-42s %-16s %s" % ("Time-To-Eclipse (CTR first 12/12)",
                              ("%.1f min" % (tte / 60.0)) if tte is not None else "not reached",
                              "~27 min"))
    print("%-42s %-16s %s" % ("eclipse stability (CTR=100% held)",
                              ("%.1f min" % (stability / 60.0)) if stability else "n/a", "17h47m"))
    print("-" * 74)
    print("CTR over time      : %s" % sparkline([y for _, y in ctr]))
    print("benign OR over time: %s" % sparkline([y for _, y in benign_or]))
    print("target B over time : %s (max=%d)" % (
        sparkline([(y if isinstance(y, (int, float)) else None) for _, y in Bt], 0, max(bmax, 1)), bmax))
    print("-" * 74)
    print("wrote: %s" % csv_path)
    print("wrote: %s" % os.path.join(out_dir, "eclipse_ctr_or.svg"))
    print("wrote: %s" % os.path.join(out_dir, "eclipse_B_target.svg"))


if __name__ == "__main__":
    main()
