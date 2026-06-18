"""
plot_hw_comparison.py
Hardware comparison chart — Proposed, DAuth, LAAKA, Zhou.

Values match the paper paragraph (per-round Auth+Key).

Output: Hardware/Charts/hw_total_comparison.png
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE     = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(HERE, "Charts")
OUT_FILE = os.path.join(OUT_DIR, "hw_total_comparison.png")
os.makedirs(OUT_DIR, exist_ok=True)

SCHEMES = ["Proposed", "DAuth", "LAAKA", "Zhou"]

# Per-round values from paper paragraph
data = {
    "Proposed": {"e": (0.286, 0), "t": (0.075, 0)},
    "DAuth":    {"e": (0.152, 0), "t": (0.040, 0)},
    "LAAKA":    {"e": (0.602, 0), "t": (0.159, 0)},
    "Zhou":     {"e": (0.333, 0), "t": (0.088, 0)},
}

for s in SCHEMES:
    print(f"{s:<10}  {data[s]['e'][0]:.3f} J  {data[s]['t'][0]:.3f} s")

# ── Style (matches COOJA simulation charts) ────────────────────────────────────
COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6",
           "LAAKA":    "#B85C2C", "Zhou":  "#3A7D44"}
HATCHES = {"Proposed": "///", "DAuth": "...", "LAAKA": "\\\\", "Zhou": "xxx"}
BAR_W   = 0.45
X       = np.arange(len(SCHEMES))
_STYLE  = {
    "font.family":       "DejaVu Sans",
    "font.size":         15,
    "axes.titlesize":    18,
    "axes.titleweight":  "bold",
    "axes.labelsize":    19,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   15,
    "ytick.labelsize":   15,
    "xtick.major.size":  0,
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}


def _draw_panel(ax, metric, ylabel, title, fmt):
    means = [data[s][metric][0] for s in SCHEMES]
    max_v = max(means)
    for i, scheme in enumerate(SCHEMES):
        ax.bar(i, means[i], width=BAR_W, facecolor="none",
               edgecolor=COLORS[scheme], hatch=HATCHES[scheme],
               linewidth=1.5, zorder=3)
    ax.set_xticks(X)
    ax.set_xticklabels(SCHEMES, fontsize=15)
    ax.set_ylabel(ylabel, fontsize=17, fontweight="bold", labelpad=10)
    if title:
        ax.set_title(title, fontsize=17, fontweight="bold", pad=10)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, max_v * 1.25)


with plt.rc_context(_STYLE):
    fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(11, 5))
    _draw_panel(ax_e, "e", "Energy (J)", "(a)", "{:.3f} J")
    _draw_panel(ax_t, "t", "Time (s)",   "(b)", "{:.3f} s")

    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", OUT_FILE)
