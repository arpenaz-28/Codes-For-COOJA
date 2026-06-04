"""
plot_hw_comparison.py
Hardware simulation total comparison bar chart — Proposed vs LAAKA vs Zhou.

Produces a 2-panel figure:
  Left  : Grand Total Energy (J)   — enrollment + 3 auth rounds + 3 data rounds
  Right : Grand Total Time  (s)

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
# Grand Total = Enrollment/Registration + Round1 + Round2 + Round3
SCHEMES = ["Proposed", "LAAKA", "Zhou"]

ENERGY_J = {
    # Proposed: Enrollment + 3x Auth+KeyEx  (data exchange excluded)
    # LAAKA / Zhou: full grand total (Enrollment + 3x Auth + 3x Data)
    "Proposed": 1.7267,
    "LAAKA":    1.8628,
    "Zhou":     1.4695,
}
TIME_S = {
    "Proposed": 0.4544,
    "LAAKA":    0.4902,
    "Zhou":     0.3867,
}

# ── Style (matches existing COOJA simulation charts) ──────────────────────────
COLORS = {
    "Proposed": "#2C6FAC",
    "LAAKA":    "#B85C2C",
    "Zhou":     "#3A7D44",
}
HATCHES = {
    "Proposed": "///",
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

BAR_W = 0.50
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
        # Value label above bar
        ax.text(
            i, v + max_v * 0.025,
            unit_fmt.format(v),
            ha="center", va="bottom",
            fontsize=14, fontweight="bold",
            color="#222222",
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
    ax.set_ylim(0, max_v * 1.20)


with plt.rc_context(_STYLE):
    fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(11, 5))

    _draw_panel(ax_e, ENERGY_J, "Energy (J)",  "Total Energy",  "{:.3f} J")
    _draw_panel(ax_t, TIME_S,   "Time (s)",    "Total Time",    "{:.3f} s")

    # Shared legend above both panels
    handles = [
        plt.Rectangle(
            (0, 0), 1, 1,
            facecolor="none",
            edgecolor=COLORS[s],
            hatch=HATCHES[s],
            linewidth=1.5,
        )
        for s in SCHEMES
    ]
    fig.legend(
        handles, SCHEMES,
        loc="upper center",
        ncol=3,
        bbox_to_anchor=(0.5, 1.01),
        fontsize=15,
        framealpha=0.9,
        edgecolor="#cccccc",
        handlelength=2.0,
        handleheight=1.4,
    )

    fig.suptitle(
        "Hardware Measurement — Total (Enrollment + 3 Auth Rounds)\n"
        "Proposed: Auth+KeyEx only  |  LAAKA & Zhou: Auth + Data",
        fontsize=13, fontweight="bold", y=1.10, color="#222222",
    )

    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", OUT_FILE)
