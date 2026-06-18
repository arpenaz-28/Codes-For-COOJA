"""
plot_proposed_dauth_li.py

Per-device per-phase energy and CPU time: Proposed vs DAuth vs Li
  N=100, 20 devices (IDs 81-100), averaged over available seeds.

Phases:
  Enrollment  — registration / device setup
  Auth        — Phase 2 authentication  (Proposed/DAuth)
                cumulative auth+KE+data (Li — marked with †)
  Key Exchange— Phase 3 key exchange    (Proposed/DAuth)
                3-message auth+KE only  (Li)

Layout: 3 rows (phases) × 2 cols (Energy | CPU Time)
"""

import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

# (enroll, auth, keyex) CSV paths per scheme
CSVS = {
    "Proposed": (
        os.path.join(REPO, "Revised-Anonymity", "Simulation results",
                     "network-variation", "N100", "csv", "enroll-results.csv"),
        os.path.join(REPO, "Revised-Anonymity", "Simulation results",
                     "network-variation", "N100", "csv", "auth-results.csv"),
        os.path.join(REPO, "Revised-Anonymity", "Simulation results",
                     "network-variation", "N100", "csv", "keyex-results.csv"),
    ),
    "DAuth": (
        os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep",
                     "network-variation", "N100", "csv", "enroll-results.csv"),
        os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep",
                     "network-variation", "N100", "csv", "auth-results.csv"),
        os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep",
                     "network-variation", "N100", "csv", "keyex-results.csv"),
    ),
    "Li": (
        os.path.join(REPO, "Li-Scheme", "Simulation results",
                     "network-variation", "N100", "csv", "enroll-results.csv"),
        os.path.join(REPO, "Li-Scheme", "Simulation results",
                     "network-variation", "N100", "csv", "auth-results.csv"),
        os.path.join(REPO, "Li-Scheme", "Simulation results",
                     "network-variation", "N100", "csv", "keyex-results.csv"),
    ),
}

OUT_DIR = os.path.join(REPO, "Li-Scheme", "Simulation results",
                       "network-variation", "N100", "Charts")
os.makedirs(OUT_DIR, exist_ok=True)

COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6", "Li": "#C0392B"}
MARKERS = {"Proposed": "o",       "DAuth": "s",       "Li": "^"}
LABELS  = {"Proposed": "Proposed", "DAuth": "DAuth",  "Li": "Li et al."}

PHASE_TITLES = [
    ("(a)", "(b)", "Enrollment"),
    ("(c)", "(d)", "Authentication†"),
    ("(e)", "(f)", "Key Exchange"),
]

_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         12,
    "axes.titlesize":    13,
    "axes.titleweight":  "bold",
    "axes.labelsize":    12,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   10,
    "ytick.labelsize":   10,
    "xtick.major.size":  3,
    "legend.fontsize":   11,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e8e8e8",
    "grid.linewidth":    0.6,
}


def load_phase(path):
    """Return {device_id: (cpu_s, energy_mJ)}, handles both column orderings."""
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            did = int(row["Device_ID"])
            cpu = float(row["CPU_Time_s"])
            emj = float(row["Energy_J"]) * 1000
            result[did] = (cpu, emj)
    return dict(sorted(result.items()))


def arrays(data):
    ids = sorted(data.keys())
    return [data[d][0] for d in ids], [data[d][1] for d in ids]


with plt.rc_context(_STYLE):
    fig, axes = plt.subplots(3, 2, figsize=(12, 11),
                             gridspec_kw={"hspace": 0.55, "wspace": 0.32})

    x = list(range(1, 21))

    for row, (phase_idx, (lbl_e, lbl_t, phase_name)) in \
            enumerate(zip(range(3), PHASE_TITLES)):

        ax_e = axes[row, 0]
        ax_t = axes[row, 1]

        for scheme in ["Proposed", "DAuth", "Li"]:
            path = CSVS[scheme][phase_idx]
            data = load_phase(path)
            cpu, emj = arrays(data)

            kw = dict(color=COLORS[scheme], marker=MARKERS[scheme],
                      markersize=4.5, linewidth=1.4, label=LABELS[scheme])
            ax_e.plot(x, emj, **kw)
            ax_t.plot(x, cpu, **kw)

            ax_e.axhline(np.mean(emj), color=COLORS[scheme],
                         linestyle="--", linewidth=0.65, alpha=0.4)
            ax_t.axhline(np.mean(cpu), color=COLORS[scheme],
                         linestyle="--", linewidth=0.65, alpha=0.4)

        for ax, lbl, ylabel in [(ax_e, lbl_e, "Energy (mJ)"),
                                 (ax_t, lbl_t, "CPU Time (s)")]:
            ax.set_title(f"{lbl} {phase_name} — {ylabel.split()[0]}", pad=6)
            ax.set_ylabel(ylabel)
            ax.set_xticks(range(1, 21, 2))
            ax.grid(axis="y")
            ax.set_xlim(0.5, 20.5)

        # x-label only on bottom row
        if row == 2:
            ax_e.set_xlabel("Device index  (1 = node 81, 20 = node 100)")
            ax_t.set_xlabel("Device index  (1 = node 81, 20 = node 100)")

    axes[0, 0].legend(loc="upper right")

    # footnote
    note = (
        "† Li Authentication = cumulative snapshot (Auth + Key Exchange + Data comm).\n"
        "  Proposed/DAuth Authentication = Phase 2 challenge-response only.\n"
        "  Li Key Exchange = 3-message direct auth+KE protocol (M1→M2→M3)."
    )
    fig.text(0.01, -0.01, note, fontsize=8.5, color="#444444",
             va="top", style="italic",
             bbox=dict(boxstyle="round,pad=0.35", fc="#fafafa",
                       ec="#cccccc", lw=0.5))

    out = os.path.join(OUT_DIR, "proposed_dauth_li_perdev.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"Saved: {out}")

    # print mean table
    print(f"\n{'Phase':<14} {'Scheme':<12} {'Energy (mJ)':>12} {'CPU (s)':>10}")
    print("-" * 52)
    for phase_idx, phase_name in enumerate(["Enrollment", "Auth", "KeyEx"]):
        for scheme in ["Proposed", "DAuth", "Li"]:
            cpu, emj = arrays(load_phase(CSVS[scheme][phase_idx]))
            print(f"{phase_name:<14} {LABELS[scheme]:<12} "
                  f"{np.mean(emj):>12.2f} {np.mean(cpu):>10.4f}")
