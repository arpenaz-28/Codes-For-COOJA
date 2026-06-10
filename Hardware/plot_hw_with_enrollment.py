"""
plot_hw_with_enrollment.py
Stacked bar chart — Enrollment (bottom) + Avg Auth/round (top) per scheme.
Replaces the grouped-bar version.

Output: Hardware/Charts/hw_enrollment_comparison.png
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

OUT_DIR  = os.path.join(os.path.dirname(__file__), "Charts")
OUT_FILE = os.path.join(OUT_DIR, "hw_enrollment_comparison.png")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Measured values (RPi 4B, 3800 mW, wall_time × 3.8 W) ──────────────────────
SCHEMES = ["Proposed", "DAuth", "LAAKA", "Zhou"]

# DAuth enrollment: avg of 2 RPi 4B runs (0.4576 J + 0.3748 J) / 2
ENROLL_ENERGY_J = {"Proposed": 0.5231, "DAuth": 0.4162, "LAAKA": 0.0398, "Zhou": 0.4693}
ENROLL_TIME_S   = {"Proposed": 0.1377, "DAuth": 0.1095, "LAAKA": 0.0285, "Zhou": 0.1235}

# Per-round avg = (3-round sum) / 3, enrollment excluded
# DAuth auth: avg of 2 RPi 4B runs (0.5211 J + 0.5426 J) / 2 / 3 rounds
AUTH_ENERGY_J   = {"Proposed": 0.2860, "DAuth": 0.1773, "LAAKA": 0.6023, "Zhou": 0.3334}
AUTH_TIME_S     = {"Proposed": 0.0753, "DAuth": 0.0467, "LAAKA": 0.1585, "Zhou": 0.0877}

# ── Style ──────────────────────────────────────────────────────────────────────
COLORS = {
    "Proposed": "#2C6FAC",
    "DAuth":    "#7E5BA6",
    "LAAKA":    "#B85C2C",
    "Zhou":     "#3A7D44",
}
HATCH_ENROLL = "..."
HATCH_AUTH   = {"Proposed": "///", "DAuth": "///", "LAAKA": "\\\\", "Zhou": "xxx"}

_STYLE = {
    "font.size":         13,
    "axes.titlesize":    15,
    "axes.titleweight":  "bold",
    "axes.labelsize":    14,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   13,
    "ytick.labelsize":   13,
    "xtick.major.size":  0,
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

BAR_W = 0.45
X     = np.arange(len(SCHEMES))


def _draw_panel(ax, enroll_vals, auth_vals, ylabel, title, unit_fmt):
    totals = [enroll_vals[s] + auth_vals[s] for s in SCHEMES]
    max_v  = max(totals)

    for i, scheme in enumerate(SCHEMES):
        ev    = enroll_vals[scheme]
        av    = auth_vals[scheme]
        color = COLORS[scheme]

        # Bottom segment — Enrollment (dotted hatch, slightly transparent)
        ax.bar(X[i], ev, width=BAR_W,
               facecolor="none", edgecolor=color,
               hatch=HATCH_ENROLL, linewidth=1.4,
               alpha=0.65, zorder=3, label="_nolegend_")

        # Top segment — Per-round Auth (solid hatch)
        ax.bar(X[i], av, width=BAR_W, bottom=ev,
               facecolor="none", edgecolor=color,
               hatch=HATCH_AUTH[scheme], linewidth=1.4,
               zorder=3, label="_nolegend_")

        # Segment label inside enrollment bar (if tall enough)
        if ev > max_v * 0.07:
            ax.text(X[i], ev / 2,
                    unit_fmt.format(ev),
                    ha="center", va="center", fontsize=9.5,
                    color=color, alpha=0.85)

        # Segment label inside auth bar
        ax.text(X[i], ev + av / 2,
                unit_fmt.format(av),
                ha="center", va="center", fontsize=9.5,
                color=color, fontweight="bold")

        # Total annotation above bar
        total = ev + av
        ax.text(X[i], total + max_v * 0.025,
                unit_fmt.format(total),
                ha="center", va="bottom", fontsize=11,
                color="#222222", fontweight="bold")

    ax.set_xticks(X)
    ax.set_xticklabels(SCHEMES, fontsize=13)
    ax.set_ylabel(ylabel, fontsize=13, fontweight="bold", labelpad=8)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=10)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, max_v * 1.28)


with plt.rc_context(_STYLE):
    fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(11, 5))

    _draw_panel(ax_e, ENROLL_ENERGY_J, AUTH_ENERGY_J,
                "Energy (J)", "Energy", "{:.4f} J")
    _draw_panel(ax_t, ENROLL_TIME_S,   AUTH_TIME_S,
                "Time (s)",   "Time",   "{:.4f} s")

    # Shared legend
    legend_elems = [
        Patch(facecolor="none", edgecolor="#555", hatch=HATCH_ENROLL,
              alpha=0.65, label="Enrollment (one-time)"),
        Patch(facecolor="none", edgecolor="#555", hatch="///",
              label="Avg Auth / Round"),
    ]
    fig.legend(handles=legend_elems, loc="upper center",
               ncol=2, fontsize=12, frameon=False,
               bbox_to_anchor=(0.5, 1.04))

    fig.suptitle("Hardware Simulation — Enrollment + Per-Round Auth",
                 fontsize=14, fontweight="bold", y=1.10, color="#222222")

    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", OUT_FILE)
