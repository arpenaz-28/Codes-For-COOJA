"""
plot_banerjee_comparison.py

Bar chart: Proposed vs DAuth vs Banerjee
Total per-device cost (Enrollment + Auth + KeyEx summed), averaged over
all 20 devices and 10 seeds, N=100.

One bar per scheme — dual panel: Energy (mJ) and CPU Time (s).
Error bars = combined 95% CI (quadrature: sqrt(ΣCI_i²)).

Reads summary.csv from each scheme's results folder.
Writes: Results/COOJA-Simulation/Banerjee-Comparison/banerjee_comparison.png
"""

import csv, math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OUT_DIR = os.path.join(REPO, "Results", "COOJA-Simulation", "Banerjee-Comparison")
os.makedirs(OUT_DIR, exist_ok=True)

SUMMARY_PATHS = {
    "Proposed": os.path.join(REPO, "Revised-Anonymity", "Simulation results",
                             "network-variation", "N100", "csv", "summary.csv"),
    "DAuth":    os.path.join(REPO, "Results", "COOJA-Simulation",
                             "DAuth-Sweep", "network-variation", "N100", "csv", "summary.csv"),
    "Banerjee": os.path.join(REPO, "Banerjee-Scheme", "Simulation results",
                             "network-variation", "N100", "csv", "summary.csv"),
}

COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6", "Banerjee": "#C0392B"}
HATCHES = {"Proposed": "///",     "DAuth": "...",     "Banerjee": "xxx"}

PHASES = ["Enrollment", "Authentication", "Key Exchange"]

_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    14,
    "axes.titleweight":  "bold",
    "axes.labelsize":    13,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   13,
    "ytick.labelsize":   12,
    "xtick.major.size":  0,
    "legend.fontsize":   11,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}


def load_totals(path):
    """Sum energy and CPU across all phases; combine CI95 in quadrature."""
    total_e, total_c = 0.0, 0.0
    ci_e_sq, ci_c_sq = 0.0, 0.0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["Phase"] not in PHASES:
                continue
            total_e += float(row["Avg_Energy_mJ"])
            total_c += float(row["Avg_CPU_s"])
            ci_e_sq += float(row["CI95_Energy_mJ"]) ** 2
            ci_c_sq += float(row["CI95_CPU_s"])     ** 2
    return {
        "energy_mJ": total_e,
        "ci_energy":  math.sqrt(ci_e_sq),
        "cpu_s":      total_c,
        "ci_cpu":     math.sqrt(ci_c_sq),
    }


def main():
    schemes = list(SUMMARY_PATHS.keys())
    data    = {s: load_totals(p) for s, p in SUMMARY_PATHS.items()}

    with plt.rc_context(_STYLE):
        fig, axes = plt.subplots(1, 2, figsize=(9, 5))
        fig.suptitle(
            "Total per-device cost  —  Proposed vs DAuth vs Banerjee\n"
            "N=100, 20 devices, 10 seeds  (Enroll + Auth + KeyEx)",
            fontsize=13, fontweight="bold", y=1.02,
        )

        x     = np.arange(len(schemes))
        width = 0.50

        for ax, metric, ylabel, ci_key, unit in [
            (axes[0], "energy_mJ", "Total Energy (mJ)", "ci_energy", "mJ"),
            (axes[1], "cpu_s",     "Total CPU Time (s)", "ci_cpu",   "s"),
        ]:
            vals = [data[s][metric]  for s in schemes]
            errs = [data[s][ci_key] for s in schemes]

            bars = ax.bar(
                x, vals, width,
                color   = [COLORS[s]  for s in schemes],
                hatch   = [HATCHES[s] for s in schemes],
                edgecolor="white", linewidth=0.6,
                yerr=errs,
                error_kw=dict(elinewidth=1.5, capsize=5,
                              ecolor="#333333", capthick=1.5),
                zorder=3,
            )

            # value labels centred above each bar
            for bar, v, e in zip(bars, vals, errs):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + e + ax.get_ylim()[1] * 0.01,
                    f"{v:.1f} {unit}",
                    ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color="#111111",
                )

            ax.set_xticks(x)
            ax.set_xticklabels(schemes)
            ax.set_ylabel(ylabel)
            ax.yaxis.grid(True, zorder=0)
            ax.set_axisbelow(True)
            # start y-axis at 0
            ax.set_ylim(0, max(vals) * 1.25)

        plt.tight_layout()
        out = os.path.join(OUT_DIR, "banerjee_comparison.png")
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved → {out}")
        for s in schemes:
            d = data[s]
            print(f"  {s:10s}  {d['energy_mJ']:.2f} mJ ±{d['ci_energy']:.2f}  |  "
                  f"{d['cpu_s']:.3f} s ±{d['ci_cpu']:.3f}")


if __name__ == "__main__":
    main()
