"""
plot_banerjee_as_variation.py

Simple grouped bar chart: Proposed vs DAuth vs Banerjee
X-axis: number of active AS/SD nodes (2, 5, 10)
Y-axis: total cost — sum over all devices, averaged over seeds (Enroll+Auth+KeyEx)
No CI error bars.

Two panels: Energy (mJ) | CPU Time (s)

Reads summary.csv from each scheme's as-variation results folder.
Output: Results/COOJA-Simulation/Banerjee-Comparison/banerjee_as_variation.png
"""

import os, csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OUT  = os.path.join(REPO, "Results", "COOJA-Simulation", "Banerjee-Comparison")
os.makedirs(OUT, exist_ok=True)

SUMMARY_DIRS = {
    "Proposed": os.path.join(REPO, "Revised-Anonymity",
                             "Simulation results", "as-variation"),
    "DAuth":    os.path.join(REPO, "Results", "COOJA-Simulation",
                             "DAuth-Sweep", "as-variation"),
    "Banerjee": os.path.join(REPO, "Banerjee-Scheme",
                             "Simulation results", "as-variation"),
}

AS_COUNTS = [2, 5, 10]
PHASES    = ["Enrollment", "Authentication", "Key Exchange"]
SCHEMES   = ["Proposed", "DAuth", "Banerjee"]

COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6", "Banerjee": "#C0392B"}
HATCHES = {"Proposed": "///",     "DAuth": "...",     "Banerjee": "xxx"}

_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    13,
    "axes.titleweight":  "bold",
    "axes.labelsize":    13,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   12,
    "ytick.labelsize":   12,
    "xtick.major.size":  0,
    "legend.fontsize":   11,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}


def load_total(scheme, n_as):
    """Sum all phases; scale by n_devices for total-all-devices cost."""
    path = os.path.join(SUMMARY_DIRS[scheme], f"N{n_as}", "csv", "summary.csv")
    if not os.path.isfile(path):
        return None, None
    total_e = total_c = 0.0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["Phase"] not in PHASES:
                continue
            nd = int(row["n_devices"])
            total_e += float(row["Avg_Energy_mJ"]) * nd
            total_c += float(row["Avg_CPU_s"])     * nd
    return total_e, total_c


def main():
    # Collect data
    energy = {s: [] for s in SCHEMES}
    cpu    = {s: [] for s in SCHEMES}
    for s in SCHEMES:
        for n in AS_COUNTS:
            e, c = load_total(s, n)
            energy[s].append(e)
            cpu[s].append(c)

    # Print table
    print(f"\n{'Scheme':12s}  {'AS':>4s}  {'Energy(mJ)':>12s}  {'CPU(s)':>10s}")
    print("-" * 44)
    for s in SCHEMES:
        for i, n in enumerate(AS_COUNTS):
            e, c = energy[s][i], cpu[s][i]
            if e is None:
                print(f"{s:12s}  {n:>4d}  {'MISSING':>12s}")
            else:
                print(f"{s:12s}  {n:>4d}  {e:>12.1f}  {c:>10.3f}")

    x      = np.arange(len(AS_COUNTS))
    width  = 0.22
    n_sc   = len(SCHEMES)
    offs   = np.linspace(-(n_sc-1)/2, (n_sc-1)/2, n_sc) * width

    with plt.rc_context(_STYLE):
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        for ax, metric, ylabel, title in [
            (axes[0], energy, "Avg. Energy — all devices (mJ)", "(a) Avg. Energy"),
            (axes[1], cpu,   "Avg. CPU Time — all devices (s)", "(b) Avg. CPU Time"),
        ]:
            for si, s in enumerate(SCHEMES):
                vals = metric[s]
                safe = [v if v is not None else 0 for v in vals]
                ax.bar(
                    x + offs[si], safe, width,
                    label=s,
                    color=COLORS[s], hatch=HATCHES[s],
                    edgecolor="white", linewidth=0.5,
                    zorder=3,
                )
                # value labels on top of each bar
                for xi, v in zip(x + offs[si], safe):
                    if v > 0:
                        ax.text(xi, v + ax.get_ylim()[1] * 0.005,
                                f"{v:.0f}" if metric is energy else f"{v:.1f}",
                                ha="center", va="bottom", fontsize=8,
                                fontweight="bold", color="#111111")

            ax.set_xticks(x)
            ax.set_xticklabels([str(n) for n in AS_COUNTS])
            ax.set_xlabel("Active AS / SD Count")
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            ax.yaxis.grid(True, zorder=0)
            ax.set_axisbelow(True)
            ax.set_ylim(0, max(v for s in SCHEMES for v in metric[s] if v) * 1.2)
            ax.legend(loc="upper right")

        plt.tight_layout()
        out = os.path.join(OUT, "banerjee_as_variation.png")
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
