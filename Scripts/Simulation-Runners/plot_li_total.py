import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import csv, os

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

CSVS = {
    "Proposed": {
        "Enrollment":   os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N100", "csv", "enroll-results.csv"),
        "Authentication": os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N100", "csv", "auth-results.csv"),
        "Key Exchange": os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N100", "csv", "keyex-results.csv"),
    },
    "DAuth": {
        "Enrollment":   os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep", "network-variation", "N100", "csv", "enroll-results.csv"),
        "Authentication": os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep", "network-variation", "N100", "csv", "auth-results.csv"),
        "Key Exchange": os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep", "network-variation", "N100", "csv", "keyex-results.csv"),
    },
    "Li et al.": {
        "Enrollment":   os.path.join(REPO, "Li-Scheme", "Simulation results", "network-variation", "N100", "csv", "enroll-results.csv"),
        "Key Exchange": os.path.join(REPO, "Li-Scheme", "Simulation results", "network-variation", "N100", "csv", "keyex-results.csv"),
    },
}

OUT = os.path.join(REPO, "Li-Scheme", "Simulation results",
                   "network-variation", "N100", "Charts",
                   "proposed_dauth_li_total.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

PHASE_COLORS = {
    "Enrollment":     "#5B9BD5",
    "Authentication": "#ED7D31",
    "Key Exchange":   "#A9D18E",
}

SCHEME_EDGE = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6", "Li et al.": "#C0392B"}
SCHEMES     = ["Proposed", "DAuth", "Li et al."]
PHASES      = ["Enrollment", "Authentication", "Key Exchange"]

def mean_csv(path):
    e, c = [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            e.append(float(row["Energy_J"]) * 1000)
            c.append(float(row["CPU_Time_s"]))
    return np.mean(e), np.mean(c)

# Build per-scheme per-phase values
data_e = {s: {} for s in SCHEMES}
data_c = {s: {} for s in SCHEMES}
for scheme, phases in CSVS.items():
    for phase, path in phases.items():
        e, c = mean_csv(path)
        data_e[scheme][phase] = e
        data_c[scheme][phase] = c

x     = np.arange(len(SCHEMES))
width = 0.42

fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(10, 5))
fig.subplots_adjust(wspace=0.38)

for ax, data, ylabel, title in [
    (ax_e, data_e, "Energy (mJ)",  "Total Per-Device Energy"),
    (ax_t, data_c, "CPU Time (s)", "Total Per-Device CPU Time"),
]:
    bottoms = np.zeros(len(SCHEMES))
    for phase in PHASES:
        vals = np.array([data[s].get(phase, 0.0) for s in SCHEMES])
        bars = ax.bar(x, vals, width, bottom=bottoms,
                      color=PHASE_COLORS[phase], label=phase,
                      edgecolor="white", linewidth=0.6)
        # label each segment if tall enough
        for i, (bar, v) in enumerate(zip(bars, vals)):
            if v > 0.8 if ylabel == "CPU Time (s)" else v > 1.0:
                ax.text(bar.get_x() + bar.get_width()/2,
                        bottoms[i] + v / 2,
                        f"{v:.1f}", ha="center", va="center",
                        fontsize=9, color="white", fontweight="bold")
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels(SCHEMES, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, color="#e5e5e5", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.set_ylim(0, bottoms.max() * 1.22)

    # total label on top of each bar — placed AFTER set_ylim so offset is correct
    offset = ax.get_ylim()[1] * 0.012
    for i, s in enumerate(SCHEMES):
        total = sum(data[s].values())
        ax.text(i, bottoms[i] + offset,
                f"{total:.1f}", ha="center", va="bottom",
                fontsize=10, fontweight="bold",
                color=SCHEME_EDGE[s])

ax_e.legend(loc="upper right", fontsize=10, framealpha=0.9)
fig.suptitle("Total Per-Device Cost — N=100, 20 devices (avg over seeds)",
             fontsize=12, y=1.01)

fig.savefig(OUT, dpi=180, bbox_inches="tight", facecolor="white")
print(f"Saved: {OUT}")
