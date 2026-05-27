"""
plot_desync_sim_before_after.py
Produce two 4-bar charts (energy + CPU) in the exact paper style, using actual
COOJA desync-demo simulation results.

  Before loss = ROUND1  (normal auth session — baseline, no desync)
  After  loss = ROUND3  (recovery session — what happens after packet drop)

  Proposed ROUND3: dual-state lookup finds PID_old → re-runs Phase 3 only.
  Base     ROUND3: auth fails → forced re-enrol → retry auth+data.

Outputs → Results/Desync-Demo/Charts/
  sim_01_energy_before_after.png
  sim_02_cpu_before_after.png
"""

import os, csv, math, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

REPO    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
SRC_DIR = os.path.join(REPO, "Results", "Desync-Demo")
OUT_DIR = os.path.join(SRC_DIR, "Charts")
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
    "legend.fontsize":   13,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

C_PROPOSED = "#2C6FAC"
C_BASE     = "#B85C2C"
H_BEFORE   = "///"
H_AFTER    = "\\\\"


# ── data loading ─────────────────────────────────────────────────────────────
def load(scheme):
    """Return {round: {"energy": [per-device values], "cpu": [per-device values]}}"""
    path = os.path.join(SRC_DIR, scheme, "desync_results.csv")
    rounds = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rounds.setdefault(row["Round"], {"energy": [], "cpu": []})
            rounds[row["Round"]]["energy"].append(float(row["Energy_mJ"]))
            rounds[row["Round"]]["cpu"].append(float(row["CPU_s"]))
    return rounds


def agg(vals):
    n = len(vals)
    mu = statistics.mean(vals)
    ci = 1.96 * statistics.stdev(vals) / math.sqrt(n) if n > 1 else 0.0
    return mu, ci


# ── chart ────────────────────────────────────────────────────────────────────
def make_chart(metric, ylabel, title, filename):
    """
    4-bar chart matching the paper style exactly.

    pos 0  : Proposed — Before loss  (ROUND1)   /// blue
    pos 1  : Proposed — After  loss  (ROUND3)   \\\ blue
    [gap]
    pos 2.6: Base     — Before loss  (ROUND1)   /// orange
    pos 3.6: Base     — After  loss  (ROUND3)   \\\ orange
    """
    data_p = load("Proposed")
    data_b = load("Base")

    p_before, p_before_ci = agg(data_p["ROUND1"][metric])
    p_after,  p_after_ci  = agg(data_p["ROUND3"][metric])
    b_before, b_before_ci = agg(data_b["ROUND1"][metric])
    b_after,  b_after_ci  = agg(data_b["ROUND3"][metric])

    vals    = [p_before, p_after, b_before, b_after]
    cis     = [p_before_ci, p_after_ci, b_before_ci, b_after_ci]
    colors  = [C_PROPOSED, C_PROPOSED, C_BASE, C_BASE]
    hatches = [H_BEFORE,   H_AFTER,    H_BEFORE, H_AFTER]
    pos     = [0, 1, 2.6, 3.6]
    w       = 0.7

    xlabels = [
        "Proposed\nBefore loss\n(Enroll+Auth+KeyEx)",
        "Proposed\nAfter loss\n(Auth+KeyEx only)",
        "Base\nBefore loss\n(Enroll+Auth+KeyEx)",
        "Base\nAfter loss\n(Full re-enroll+Auth)",
    ]

    fmt     = ".1f" if metric == "energy" else ".3f"
    max_val = max(v + ci for v, ci in zip(vals, cis))

    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(11, 8.5))
        fig.patch.set_facecolor("white")

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
        ax.set_xticklabels(xlabels, rotation=0, ha="center", fontsize=12)
        ax.set_ylabel(ylabel, labelpad=14, fontsize=19, fontweight="bold")
        ax.set_title(title, fontsize=18, fontweight="bold", pad=14, color="#222222")
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.set_ylim(0, max_val * 1.32)

        unit = "mJ" if metric == "energy" else "s"
        legend_handles = [
            mpatches.Patch(facecolor="none", edgecolor=C_PROPOSED,
                           hatch=H_BEFORE, linewidth=1.5,
                           label=f"Proposed — Before loss\n(Enroll + Auth + Key Exchange: {p_before:{fmt}} {unit})"),
            mpatches.Patch(facecolor="none", edgecolor=C_PROPOSED,
                           hatch=H_AFTER,  linewidth=1.5,
                           label=f"Proposed — After loss\n(Auth + Key Exchange only: {p_after:{fmt}} {unit})"),
            mpatches.Patch(facecolor="none", edgecolor=C_BASE,
                           hatch=H_BEFORE, linewidth=1.5,
                           label=f"Base — Before loss\n(Enroll + Auth + Key Exchange: {b_before:{fmt}} {unit})"),
            mpatches.Patch(facecolor="none", edgecolor=C_BASE,
                           hatch=H_AFTER,  linewidth=1.5,
                           label=f"Base — After loss\n(Full re-enrollment + Auth: {b_after:{fmt}} {unit})"),
        ]
        ax.legend(handles=legend_handles, loc="upper left",
                  fontsize=12, framealpha=0.88,
                  edgecolor="#dddddd", handlelength=2.0, handleheight=1.4)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, filename)
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: {filename}")


def main():
    make_chart(
        "energy",
        "Avg Energy per Device (mJ)",
        "Energy Cost: Before vs After Phase-3 Packet Loss\n(COOJA Simulation — Deliberate Packet Drop)",
        "sim_01_energy_before_after.png",
    )
    make_chart(
        "cpu",
        "Avg CPU Time per Device (s)",
        "CPU Time: Before vs After Phase-3 Packet Loss\n(COOJA Simulation — Deliberate Packet Drop)",
        "sim_02_cpu_before_after.png",
    )
    print(f"\nOutputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
