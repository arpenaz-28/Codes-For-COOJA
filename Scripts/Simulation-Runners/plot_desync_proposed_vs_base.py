"""
plot_desync_proposed_vs_base.py
Two 4-bar charts (energy + CPU) matching the paper chart style exactly.

SCENARIO
--------
Phase 3: AS sends (mH, ts2) to D. If lost, D retains stale m_curr.

Before-loss session = Enrollment + Authentication + Key Exchange
After-loss session:
  Proposed — dual-state lookup finds PID_old, re-runs Phase 3. No re-enrol.
             After cost = Authentication + Key Exchange only.
  Base     — nonce mismatch → auth rejected → forced re-enrol.
             After cost = Enrollment + Authentication + Key Exchange.

Visual style: hollow hatched bars, Liberation Sans, matching paper figures.
  Same hatch angle = same condition (Before / After)
  Same edge colour = same scheme (Proposed / Base)

OUTPUTS → Results/Desync-Recovery-Analysis/
  01_energy_before_after.png
  02_cpu_before_after.png
"""

import os, csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

REPO    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
SRC_CSV = os.path.join(REPO, "Results", "Charts",
                       "Revised-vs-LAAKA-vs-Zhou", "comparison_summary.csv")
OUT_DIR = os.path.join(REPO, "Results", "Desync-Recovery-Analysis")
os.makedirs(OUT_DIR, exist_ok=True)

# ── exact paper style ────────────────────────────────────────────────────────
_CHART_STYLE = {
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
    "legend.fontsize":   14,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

C_PROPOSED = "#2C6FAC"   # muted steel blue  (paper Proposed)
C_BASE     = "#B85C2C"   # terracotta        (paper LAAKA = base scheme)

# Same hatch angle = same condition; same colour = same scheme
# Before loss → forward-slash hatch  ///
# After loss  → backward-slash hatch  \\\
H_BEFORE = "///"
H_AFTER  = "\\\\"


# ── data loading ─────────────────────────────────────────────────────────────
def load():
    d = {}
    with open(SRC_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = ("Proposed" if row["Scheme"] == "Revised-Anonymity" else
                   "Base"     if row["Scheme"] == "LAAKA"             else None)
            if key is None:
                continue
            d.setdefault(key, {})[row["Phase"]] = {
                "e":    float(row["Avg_Energy_mJ"]),
                "ci_e": float(row["CI95_Energy_mJ"]),
                "c":    float(row["Avg_CPU_s"]),
                "ci_c": float(row["CI95_CPU_s"]),
            }
    return d


# ── chart generator ───────────────────────────────────────────────────────────
def make_chart(data, metric, ylabel, title, filename):
    """
    4-bar grouped chart in the paper's hollow-hatch style.

    Layout (gap between scheme groups):
      pos 0: Proposed — Before loss   (/// blue)
      pos 1: Proposed — After  loss   (\\\ blue)
      [gap]
      pos 2.6: Base — Before loss     (/// orange)
      pos 3.6: Base — After  loss     (\\\ orange)
    """
    ci_key = "ci_e" if metric == "e" else "ci_c"

    p = data["Proposed"]
    b = data["Base"]

    # Before = Enrol + Auth+KeyEx, After = Proposed:Auth+KeyEx / Base:Enrol+Auth+KeyEx
    vals = [
        p["Enrollment"][metric] + p["Auth+KeyEx"][metric],   # P-Before
        p["Auth+KeyEx"][metric],                              # P-After
        b["Enrollment"][metric] + b["Auth+KeyEx"][metric],   # B-Before
        b["Enrollment"][metric] + b["Auth+KeyEx"][metric],   # B-After
    ]
    cis = [
        math.sqrt(p["Enrollment"][ci_key]**2 + p["Auth+KeyEx"][ci_key]**2),
        p["Auth+KeyEx"][ci_key],
        math.sqrt(b["Enrollment"][ci_key]**2 + b["Auth+KeyEx"][ci_key]**2),
        math.sqrt(b["Enrollment"][ci_key]**2 + b["Auth+KeyEx"][ci_key]**2),
    ]
    colors  = [C_PROPOSED, C_PROPOSED, C_BASE, C_BASE]
    hatches = [H_BEFORE,   H_AFTER,    H_BEFORE, H_AFTER]
    pos     = [0, 1, 2.6, 3.6]
    w       = 0.7

    xlabels = [
        "Proposed\nBefore loss",
        "Proposed\nAfter loss",
        "Base\nBefore loss",
        "Base\nAfter loss",
    ]

    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(11, 7))
        fig.patch.set_facecolor("white")

        fmt = ".1f" if metric == "e" else ".3f"
        max_val = max(vals)

        for xi, (v, ci, color, hatch) in enumerate(zip(vals, cis, colors, hatches)):
            ax.bar(pos[xi], v, w,
                   facecolor="none", edgecolor=color,
                   hatch=hatch, linewidth=1.5,
                   yerr=ci, capsize=6,
                   error_kw={"linewidth": 1.5, "ecolor": color})
            ax.text(pos[xi], v + ci + max_val * 0.015,
                    f"{v:{fmt}}",
                    ha="center", va="bottom",
                    fontsize=17, fontweight="bold", color="#222222")

        ax.set_xticks(pos)
        ax.set_xticklabels(xlabels, rotation=0, ha="center", fontsize=15)
        ax.set_ylabel(ylabel, labelpad=14, fontsize=19, fontweight="bold")
        ax.set_title(title, fontsize=18, fontweight="bold", pad=14, color="#222222")
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.set_ylim(0, max_val * 1.22)

        legend_handles = [
            mpatches.Patch(facecolor="none", edgecolor=C_PROPOSED,
                           hatch=H_BEFORE, linewidth=1.5,
                           label="Proposed — Before loss\n(Enrol + Auth + Key Exchange)"),
            mpatches.Patch(facecolor="none", edgecolor=C_PROPOSED,
                           hatch=H_AFTER,  linewidth=1.5,
                           label="Proposed — After loss\n(Auth + Key Exchange only)"),
            mpatches.Patch(facecolor="none", edgecolor=C_BASE,
                           hatch=H_BEFORE, linewidth=1.5,
                           label="Base — Before loss\n(Enrol + Auth + Key Exchange)"),
            mpatches.Patch(facecolor="none", edgecolor=C_BASE,
                           hatch=H_AFTER,  linewidth=1.5,
                           label="Base — After loss\n(Enrol + Auth + Key Exchange)"),
        ]
        ax.legend(handles=legend_handles, loc="upper right",
                  fontsize=12, framealpha=0.88,
                  edgecolor="#dddddd", handlelength=2.0, handleheight=1.4)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, filename)
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: {filename}")


def main():
    data = load()

    make_chart(
        data, "e",
        "Avg Energy per Device (mJ)",
        "Energy Cost: Before vs After (mH, ts2) Loss in Phase 3",
        "01_energy_before_after.png",
    )
    make_chart(
        data, "c",
        "Avg CPU Time per Device (s)",
        "CPU Time: Before vs After (mH, ts2) Loss in Phase 3",
        "02_cpu_before_after.png",
    )

    print(f"\nAll outputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
