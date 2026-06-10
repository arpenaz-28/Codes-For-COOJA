"""
plot_hw_comparison.py
Hardware simulation per-round comparison bar chart — Proposed vs LAAKA vs Zhou.

Produces a 2-panel figure:
  Left  : Avg Energy per Auth round (J)
  Right : Avg Time   per Auth round (s)

Values = (3-round sum) / 3.  Enrollment excluded from all schemes.
Output: Hardware/Charts/hw_total_comparison.png
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Output ─────────────────────────────────────────────────────────────────────
OUT_DIR  = os.path.join(os.path.dirname(__file__), "Charts")
OUT_FILE = os.path.join(OUT_DIR, "hw_total_comparison.png")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Measured data (RPi 4B, 3800 mW, wall_time × 3.8 W) ────────────────────────
# Per-round averages = (3-round sum) / 3.  Enrollment excluded from all schemes.
# Proposed : Auth+KeyEx only (per round avg)
# LAAKA    : Auth+Ack + Data (per round avg)
# Zhou     : Auth M1->M4 + Data (per round avg)
SCHEMES = ["Proposed", "DAuth", "LAAKA", "Zhou"]

_NUM_ROUNDS = 3

# Auth+KeyEx only (Enrollment and Data excluded), 3-round sums.
# DAuth values: average of 2 hardware runs on RPi 4B (Apex=device, Pi=AS, Laptop=GW)
#   with 1 warm-up round discarded to eliminate TCP cold-start.
_ENERGY_SUM_J = {
    "Proposed": 0.8580,
    "DAuth":    0.5319,
    "LAAKA":    1.8069,
    "Zhou":     1.0002,
}
_TIME_SUM_S = {
    "Proposed": 0.2258,
    "DAuth":    0.1400,
    "LAAKA":    0.4755,
    "Zhou":     0.2632,
}

ENERGY_J = {k: round(v / _NUM_ROUNDS, 4) for k, v in _ENERGY_SUM_J.items()}
TIME_S   = {k: round(v / _NUM_ROUNDS, 4) for k, v in _TIME_SUM_S.items()}

# ── Style (matches existing COOJA simulation charts) ──────────────────────────
COLORS = {
    "Proposed": "#2C6FAC",
    "DAuth":    "#7E5BA6",
    "LAAKA":    "#B85C2C",
    "Zhou":     "#3A7D44",
}
HATCHES = {
    "Proposed": "///",
    "DAuth":    "...",
    "LAAKA":    "\\\\",
    "Zhou":     "xxx",
}
_STYLE = {
    "font.family":       "Liberation Sans",
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

BAR_W = 0.45
X     = np.arange(len(SCHEMES))


def _draw_panel(ax, values, ylabel, title, unit_fmt):
    """Draw one bar panel with value annotations."""
    max_v = max(values.values())

    for i, scheme in enumerate(SCHEMES):
        v = values[scheme]
        ax.bar(
            i, v,
            width=BAR_W,
            facecolor="none",
            edgecolor=COLORS[scheme],
            hatch=HATCHES[scheme],
            linewidth=1.5,
            label=scheme,
            zorder=3,
        )
    ax.set_xticks(X)
    ax.set_xticklabels(SCHEMES, fontsize=15)
    ax.set_ylabel(ylabel, fontsize=17, fontweight="bold", labelpad=10)
    ax.set_title(title, fontsize=17, fontweight="bold", pad=10)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, max_v * 1.15)


with plt.rc_context(_STYLE):
    fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(11, 5))

    _draw_panel(ax_e, ENERGY_J, "Energy (J)",  "Energy",  "{:.4f} J")
    _draw_panel(ax_t, TIME_S,   "Time (s)",    "Time",    "{:.4f} s")

    fig.suptitle(
        "Hardware Simulation",
        fontsize=16, fontweight="bold", y=1.04, color="#222222",
    )

    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", OUT_FILE)
