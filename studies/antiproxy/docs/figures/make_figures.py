#!/usr/bin/env python3
"""Figures for the antiproxy findings report (20261111_findings_summary.md).

Every value below is a journal-cited measurement (entry noted per figure); the
per-run artifacts live in docs/spy_journal/runs/. Regenerate with:
    venv/bin/python studies/antiproxy/docs/figures/make_figures.py
Writes PNGs next to this script. Single-measure charts (one hue + gray
references); the one two-family chart uses the palette's first two slots.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import textwrap
from pathlib import Path

OUT = Path(__file__).parent
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1a1a1a", "#6b6b6b", "#dddddd"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "font.size": 10.5, "text.color": INK, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.dpi": 200,
})

def style(ax, ylab, title, sub, wrap=100):
    ax.set_ylabel(ylab)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK, pad=34)
    ax.text(0, 1.022, textwrap.fill(sub, wrap), transform=ax.transAxes,
            fontsize=9, color=MUTED, va="bottom", linespacing=1.3)

def bars(ax, labels, vals, color=BLUE, fmt="{:.2f}", vpad=0.012):
    ax.bar(range(len(vals)), vals, width=0.58, color=color, zorder=3)
    ax.set_xticks(range(len(labels)), labels)
    top = max(vals)
    for i, v in enumerate(vals):
        ax.text(i, v + top * vpad, fmt.format(v), ha="center", fontsize=9.5, color=INK)
    ax.set_ylim(0, top * 1.18)
    ax.grid(axis="x", visible=False)

# F1 — the white-list cap sweep: multiplier of the pool share (Finding 1).
fig, ax = plt.subplots(figsize=(6.4, 3.6))
bars(ax, ["35", "70", "140", "Stock\n(cap 1000)"], [0.99, 1.06, 1.07, 2.20], fmt="{:.2f}x")
ax.axhline(1.0, color=MUTED, lw=1.2, ls=(0, (4, 3)))
ax.text(3.42, 1.03, "pool share (1.0x)", fontsize=9, color=MUTED, ha="right")
style(ax, "Fleet slot share / pool share", "The 20-newest candidate cut is the entire multiplier",
      "Passive spy fleet, k42-m1 (42 endpoints in 42 /24s). E45 (35/70), E49 (140), E27 (stock).", wrap=70)
fig.tight_layout(); fig.savefig(OUT / "f1_cap_sweep.png"); plt.close(fig)

# F2 — the enforcement arc: fleet slot share by arm (Finding 10, E76-E78).
fig, ax = plt.subplots(figsize=(8.2, 3.8))
arms = ["Stock\nbaseline", "Shared id\nno enforce", "Separate ids\n+ enforce",
        "Shared id\n+ v1", "Shared id\n+ v3.1", "Shared id\n+ v3.2"]
vals = [0.3467, 0.3542, 0.3521, 0.3487, 0.1019, 0.0359]
bars(ax, arms, vals)
ax.annotate("", xy=(5, 0.078), xytext=(0, 0.36), arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.1))
ax.text(2.6, 0.235, "9.7x", fontsize=12, color=INK, fontweight="bold")
style(ax, "Fleet share of honest outbound slots", "Id-consistency enforcement collapses a shared-id fleet",
      "k42-m7, 294 endpoints sharing one backing id. I1 baseline; S1/S3 are means of 3 binaries (E76-E78).")
fig.tight_layout(); fig.savefig(OUT / "f2_enforcement_arc.png"); plt.close(fig)

# F3 — what the fleet learns: first-hop sender deanonymization by defense.
fig, ax = plt.subplots(figsize=(9.4, 4.2))
slot_defs = ["Stock", "Uniform\npick", "Uncapped\ndraw", "Uncapped\n+ uniform", "Trim 70", "Trim 35"]
slot_vals = [0.126, 0.101, 0.139, 0.158, 0.135, 0.144]   # uncapped+uniform = mean of 3 seeds
ax.bar(range(6), slot_vals, width=0.58, color=BLUE, label="slot-share defenses", zorder=3)
seeds = [0.173, 0.154, 0.146]                            # the 3 seeds of uncapped+uniform
ax.scatter([3] * 3, seeds, s=30, color=INK, zorder=4)
ax.bar([6.7], [0.021], width=0.58, color=ORANGE, label="enforcement v3.2", zorder=3)
ax.bar([7.8], [0.119], width=0.58, color="#c9c9c9", label="stock baseline (m7)", zorder=3)
ax.text(6.7, 0.031, "0.021", ha="center", fontsize=9.5)
ax.text(7.8, 0.129, "0.119", ha="center", fontsize=9.5)
ax.set_xticks(list(range(6)) + [6.7, 7.8], slot_defs + ["Enforcement\nv3.2", "Stock\n(m7)"], fontsize=9)
top = 0.215
for i, v in enumerate(slot_vals):
    dy = 0.021 if i == 3 else top * 0.018   # clear the seed dots on the mean bar
    ax.text(i, v + dy, f"{v:.3f}", ha="center", fontsize=9)
ax.set_ylim(0, top)
ax.set_xlim(-0.7, 8.5)
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, fontsize=9, loc="upper center", ncol=3)
style(ax, "User transactions deanonymized at first hop",
      "Slot-share fairness is not sender privacy; enforcement is",
      "sp-estimator recall at precision 1.000. Draw arms: k42-m1, E27/E36/E37 (uncapped+uniform: 3 seeds, dots; bar = mean). Enforcement: k42-m7, E78.")
fig.tight_layout(); fig.savefig(OUT / "f3_deanonymization_ladder.png"); plt.close(fig)

# F4 — the version ladder: same smoke cell, only the defense varies.
fig, ax = plt.subplots(figsize=(6.8, 3.6))
vers = ["v1\ninert", "v2\n+ both-direction\nobservation", "v3\n+ standing\ngate", "v3.1\n(log fix)", "v3.2\n+ advertised\nkeying"]
vals = [0.1614, 0.6422, 0.1380, 0.1422, 0.0726]
ax.plot(range(5), vals, "-", color=BLUE, lw=2, zorder=3)
ax.scatter(range(5), vals, s=64, color=BLUE, zorder=4)
for i, v in enumerate(vals):
    ax.text(i, v + 0.036, f"{v:.4f}".rstrip("0"), ha="center", fontsize=9.5,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
ax.axhline(0.1614, color=MUTED, lw=1.1, ls=(0, (4, 3)))
ax.text(4.35, 0.175, "inert reference", fontsize=9, color=MUTED, ha="right")
ax.annotate("eviction without a gate\namplifies the attack", xy=(1, 0.6422), xytext=(1.7, 0.55),
            fontsize=9, color=INK, arrowprops=dict(arrowstyle="->", color=MUTED, lw=1))
ax.set_xticks(range(5), vers)
ax.set_ylim(0, 0.72)
ax.grid(axis="x", visible=False)
style(ax, "Fleet share of honest outbound slots", "Four versions, one cell, one seed",
      "Flagged smoke dc644293 (k9, 63 shared-id spies); only the binary changed. E77-E78 decision rows.", wrap=70)
fig.tight_layout(); fig.savefig(OUT / "f4_version_ladder.png"); plt.close(fig)

# F5 — what the fleet loses under enforcement: two measures, two panels.
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.2, 3.5))
arms3 = ["Baseline", "v3.1", "v3.2"]
bars(a1, arms3, [11.9, 5.6, 2.1], fmt="{:.1f}%")
style(a1, "User txs attributed (%)", "First-hop attribution", "sp recall at precision 1.000; I1, E77, E78.")
bars(a2, arms3, [1004, 455, 187], fmt="{:,.0f}")
style(a2, "Stem receipts at spies", "Dandelion++ exposure", "spy_stem_rx census; I1, E77, E78.")
fig.tight_layout(); fig.savefig(OUT / "f5_fleet_losses.png"); plt.close(fig)

print("wrote:", *[p.name for p in sorted(OUT.glob("f*.png"))])
