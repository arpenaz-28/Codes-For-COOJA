import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import csv, os

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

CSVS = {
    "Proposed": [
        os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N100", "csv", "enroll-results.csv"),
        os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N100", "csv", "keyex-results.csv"),
    ],
    "DAuth": [
        os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep", "network-variation", "N100", "csv", "enroll-results.csv"),
        os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep", "network-variation", "N100", "csv", "keyex-results.csv"),
    ],
    "Li": [
        os.path.join(REPO, "Li-Scheme", "Simulation results", "network-variation", "N100", "csv", "enroll-results.csv"),
        os.path.join(REPO, "Li-Scheme", "Simulation results", "network-variation", "N100", "csv", "keyex-results.csv"),
    ],
}

OUT = os.path.join(REPO, "Li-Scheme", "Simulation results", "network-variation", "N100", "Charts", "proposed_dauth_li_bar.png")

COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6", "Li": "#C0392B"}
HATCHES = {"Proposed": "///",     "DAuth": "...",     "Li": "xxx"}
SCHEMES = ["Proposed", "DAuth", "Li"]
PHASES  = ["Enrollment", "Auth + Key Exchange"]


def mean_of_csv(path):
    energies, cpus = [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            energies.append(float(row["Energy_J"]) * 1000)
            cpus.append(float(row["CPU_Time_s"]))
    return np.mean(energies), np.mean(cpus)


# Build data arrays: shape (n_phases, n_schemes)
energy = np.zeros((2, 3))
cpu    = np.zeros((2, 3))
for si, scheme in enumerate(SCHEMES):
    for pi in range(2):
        e, t = mean_of_csv(CSVS[scheme][pi])
        energy[pi, si] = e
        cpu[pi, si]    = t

x      = np.arange(len(PHASES))
width  = 0.22
offsets = [-width, 0, width]

fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(10, 4.5))
fig.subplots_adjust(wspace=0.38)

for si, scheme in enumerate(SCHEMES):
    kw = dict(width=width, color=COLORS[scheme], hatch=HATCHES[scheme],
              edgecolor="white", linewidth=0.5, label=scheme)
    bars_e = ax_e.bar(x + offsets[si], energy[:, si], **kw)
    bars_t = ax_t.bar(x + offsets[si], cpu[:, si],    **kw)

    # value labels on top of each bar
    for bar in bars_e:
        h = bar.get_height()
        ax_e.text(bar.get_x() + bar.get_width()/2, h + 0.4,
                  f"{h:.1f}", ha="center", va="bottom", fontsize=8)
    for bar in bars_t:
        h = bar.get_height()
        ax_t.text(bar.get_x() + bar.get_width()/2, h + 0.003,
                  f"{h:.3f}", ha="center", va="bottom", fontsize=8)

for ax, ylabel, title in [
    (ax_e, "Energy (mJ)",  "Per-Device Mean Energy"),
    (ax_t, "CPU Time (s)", "Per-Device Mean CPU Time"),
]:
    ax.set_xticks(x)
    ax.set_xticklabels(PHASES, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, color="#e5e5e5", linewidth=0.6)
    ax.set_axisbelow(True)

ax_e.legend(fontsize=10, framealpha=0.9)
ax_e.set_ylim(0, ax_e.get_ylim()[1] * 1.18)
ax_t.set_ylim(0, ax_t.get_ylim()[1] * 1.18)

fig.suptitle("Proposed vs DAuth vs Li — N=100, 20 devices", fontsize=12, y=1.01)
fig.savefig(OUT, dpi=180, bbox_inches="tight", facecolor="white")
print(f"Saved: {OUT}")
