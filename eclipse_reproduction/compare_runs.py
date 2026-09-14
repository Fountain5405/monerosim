#!/usr/bin/env python3
"""Overlay CTR (and benign OR) of several runs on one SVG for the report.
Usage: compare_runs.py OUT.svg LABEL1=metrics1.jsonl LABEL2=metrics2.jsonl ...
"""
import json
import sys

out = sys.argv[1]
series = []
COLORS = ["#c0392b", "#2980b9", "#27ae60", "#e67e22", "#8e44ad"]


def load(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    pts_ctr, pts_or = [], []
    for r in rows:
        ts = r.get("targets") or []
        t = ts[0] if ts else {}
        if t.get("ctr") is not None:
            pts_ctr.append((r["sim_t"] / 60.0, t["ctr"]))
        if r.get("benign_or_median") is not None:
            pts_or.append((r["sim_t"] / 60.0, r["benign_or_median"]))
    return pts_ctr, pts_or


runs = []
for a in sys.argv[2:]:
    label, path = a.split("=", 1)
    runs.append((label, load(path)))

W, H, PAD = 820, 340, 56
allx = [x for _, (c, o) in runs for x, _ in (c + o)] or [0, 1]
xmin, xmax = min(allx), max(allx)
xr = (xmax - xmin) or 1.0


def sx(x):
    return PAD + (x - xmin) / xr * (W - 2 * PAD)


def sy(y):
    return H - PAD - y * (H - 2 * PAD)


el = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="sans-serif">' % (W, H)]
el.append('<rect width="%d" height="%d" fill="white"/>' % (W, H))
el.append('<text x="%d" y="26" font-size="16" font-weight="bold">Eclipse takeover: control vs attack (target CTR over time)</text>' % PAD)
for frac in (0, .25, .5, .75, 1.0):
    y = sy(frac)
    el.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#eee"/>' % (PAD, y, W - PAD, y))
    el.append('<text x="8" y="%.1f" font-size="10" fill="#555">%d%%</text>' % (y + 3, int(frac * 100)))
el.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#888"/>' % (PAD, H - PAD, W - PAD, H - PAD))
for frac in (0, .25, .5, .75, 1.0):
    x = xmin + frac * xr
    el.append('<text x="%.1f" y="%d" font-size="10" fill="#555" text-anchor="middle">%.0fm</text>' % (sx(x), H - PAD + 16, x))
el.append('<text x="%d" y="%d" font-size="11" fill="#555" text-anchor="middle">simulated time (min)</text>' % (W // 2, H - 8))
el.append('<text x="14" y="%d" font-size="11" fill="#555" transform="rotate(-90 14 %d)" text-anchor="middle">CTR = attacker outbound / 12</text>' % (H // 2, H // 2))
ly = PAD + 8
for i, (label, (ctr, _or)) in enumerate(runs):
    col = COLORS[i % len(COLORS)]
    if ctr:
        d = " ".join("%s%.1f,%.1f" % ("M" if j == 0 else "L", sx(x), sy(y)) for j, (x, y) in enumerate(ctr))
        el.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.5"/>' % (d, col))
    el.append('<rect x="%d" y="%d" width="12" height="12" fill="%s"/>' % (W - 220, ly - 10, col))
    el.append('<text x="%d" y="%d" font-size="12">%s</text>' % (W - 202, ly, label))
    ly += 18
el.append("</svg>")
open(out, "w").write("\n".join(el))
print("wrote", out)
