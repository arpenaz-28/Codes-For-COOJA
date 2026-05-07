"""
plot_network_variation.py
Generate energy and CPU scalability charts for the network-variation study.

Reads summary.csv from each scheme / network-size results folder and produces:
  01_energy_vs_network_size_enrollment.png
  02_energy_vs_network_size_auth.png
  03_energy_vs_network_size_keyex.png
  04_energy_vs_network_size_auth_keyex.png
  05_cpu_vs_network_size_enrollment.png
  06_cpu_vs_network_size_auth.png
  07_cpu_vs_network_size_keyex.png
  08_cpu_vs_network_size_auth_keyex.png
  09_combined_energy_all_phases.png
  10_combined_cpu_all_phases.png
  network_variation_summary.csv

All charts go to  Results/Charts/Network_variation/

Usage:
  python3 plot_network_variation.py          # expects results already collected
  python3 plot_network_variation.py --show   # also opens windows interactively
"""

import os, csv, argparse, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
REPO     = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OUT_DIR  = os.path.join(REPO, "Results", "Charts", "Network_variation")
SIZES    = [20, 50, 80, 100]

RESULTS = {
    "Revised-Anonymity": os.path.join(REPO, "Revised-Anonymity",
                                      "Simulation results", "network-variation"),
    "LAAKA":             os.path.join(REPO, "LAAKA",
                                      "Simulation results", "network-variation"),
    "Zhou":              os.path.join(REPO, "Zhou-Scheme",
                                      "Simulation results", "network-variation"),
}

SCHEME_COLORS = {
    "Revised-Anonymity": "#2196F3",   # blue
    "LAAKA":             "#FF9800",   # orange
    "Zhou":              "#4CAF50",   # green
}
SCHEME_MARKERS = {
    "Revised-Anonymity": "o",
    "LAAKA":             "s",
    "Zhou":              "^",
}

PHASE_LABELS = {
    "Enrollment":     "Enrollment",
    "Authentication": "Authentication",
    "Key Exchange":   "Key Exchange",
    "Auth+KeyEx":     "Auth + Key Exchange",
}

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
def load_summary(scheme_label, n_total):
    """Return dict keyed by phase name → {avg_cpu, ci_cpu, avg_energy_mj, ci_energy_mj}"""
    path = os.path.join(RESULTS[scheme_label], f"N{n_total}", "csv", "summary.csv")
    if not os.path.isfile(path):
        return None
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            phase = row["Phase"]
            result[phase] = {
                "avg_cpu":      float(row["Avg_CPU_s"]),
                "ci_cpu":       float(row["CI95_CPU_s"]),
                "avg_energy":   float(row["Avg_Energy_mJ"]),
                "ci_energy":    float(row["CI95_Energy_mJ"]),
                "n_devices":    int(row["n_devices"]),
            }
    # compute Auth+KeyEx if not already present
    if "Auth+KeyEx" not in result:
        a = result.get("Authentication")
        k = result.get("Key Exchange")
        if a and k:
            result["Auth+KeyEx"] = {
                "avg_cpu":    a["avg_cpu"]    + k["avg_cpu"],
                "ci_cpu":     math.sqrt(a["ci_cpu"]**2    + k["ci_cpu"]**2),
                "avg_energy": a["avg_energy"] + k["avg_energy"],
                "ci_energy":  math.sqrt(a["ci_energy"]**2 + k["ci_energy"]**2),
                "n_devices":  a["n_devices"],
            }
    return result


def build_series(phase_name, metric):
    """
    Returns dict: scheme_label → (sizes, values, errors)
    Only includes sizes where data exists.
    """
    series = {}
    for scheme in RESULTS:
        xs, ys, errs = [], [], []
        for n in SIZES:
            d = load_summary(scheme, n)
            if d is None or phase_name not in d:
                continue
            xs.append(n)
            ys.append(d[phase_name][metric])
            err_key = "ci_energy" if "energy" in metric else "ci_cpu"
            errs.append(d[phase_name][err_key])
        if xs:
            series[scheme] = (xs, ys, errs)
    return series


# ─────────────────────────────────────────────────────────────────────────────
# Plotting helpers
# ─────────────────────────────────────────────────────────name = "Energy"───────
# ─────────────────────────────────────────────────────────────────────────────
def _apply_style(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10)
    ax.set_xticks(SIZES)


def line_chart(series, ylabel, title, out_path, show=False):
    fig, ax = plt.subplots(figsize=(9, 5))
    for scheme, (xs, ys, errs) in series.items():
        ax.errorbar(xs, ys, yerr=errs,
                    label=scheme,
                    color=SCHEME_COLORS[scheme],
                    marker=SCHEME_MARKERS[scheme],
                    linewidth=2, markersize=7, capsize=5)
    _apply_style(ax, "Total Network Nodes", ylabel, title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


def grouped_bar_chart(phases, metric, ylabel, title, out_path, show=False):
    """
    Grouped bars: x-axis = network size, groups = phases, colours = schemes.
    phases = list of phase names to include side-by-side.
    """
    n_schemes = len(RESULTS)
    n_phases  = len(phases)
    width     = 0.8 / (n_schemes * n_phases)
    x         = np.arange(len(SIZES))

    fig, ax = plt.subplots(figsize=(13, 6))
    idx = 0
    for pi, phase in enumerate(phases):
        for si, scheme in enumerate(RESULTS):
            series = build_series(phase, metric)
            if scheme not in series:
                idx += 1
                continue
            xs, ys, errs = series[scheme]
            # align x positions
            offsets = [x[SIZES.index(n)] + (idx - (n_phases * n_schemes) / 2) * width
                       for n in xs]
            ax.bar(offsets, ys, width, yerr=errs, capsize=4,
                   label=f"{scheme} – {PHASE_LABELS.get(phase, phase)}",
                   color=SCHEME_COLORS[scheme],
                   alpha=0.6 + 0.15 * pi,
                   edgecolor="black", linewidth=0.5)
            idx += 1

    ax.set_xticks(x)
    ax.set_xticklabels([f"N={n}" for n in SIZES])
    ax.set_xlabel("Total Network Nodes", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary CSV
# ─────────────────────────────────────────────────────────────────────────────
def write_master_summary():
    out = os.path.join(OUT_DIR, "network_variation_summary.csv")
    phases = ["Enrollment", "Authentication", "Key Exchange", "Auth+KeyEx"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "N_total", "Phase",
                    "Avg_Energy_mJ", "CI95_Energy_mJ",
                    "Avg_CPU_s",    "CI95_CPU_s",
                    "N_devices"])
        for scheme in RESULTS:
            for n in SIZES:
                d = load_summary(scheme, n)
                if d is None:
                    continue
                for phase in phases:
                    if phase not in d:
                        continue
                    p = d[phase]
                    w.writerow([scheme, n, phase,
                                f"{p['avg_energy']:.4f}",
                                f"{p['ci_energy']:.4f}",
                                f"{p['avg_cpu']:.6f}",
                                f"{p['ci_cpu']:.6f}",
                                p['n_devices']])
    print(f"  Master summary → {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    phases_energy = [
        ("Enrollment",     "01_energy_vs_network_size_enrollment.png"),
        ("Authentication", "02_energy_vs_network_size_auth.png"),
        ("Key Exchange",   "03_energy_vs_network_size_keyex.png"),
        ("Auth+KeyEx",     "04_energy_vs_network_size_auth_keyex.png"),
    ]
    phases_cpu = [
        ("Enrollment",     "05_cpu_vs_network_size_enrollment.png"),
        ("Authentication", "06_cpu_vs_network_size_auth.png"),
        ("Key Exchange",   "07_cpu_vs_network_size_keyex.png"),
        ("Auth+KeyEx",     "08_cpu_vs_network_size_auth_keyex.png"),
    ]

    print("Generating line charts — Energy vs Network Size")
    for phase, fname in phases_energy:
        series = build_series(phase, "avg_energy")
        if not series:
            print(f"  No data for {phase} — skipping.")
            continue
        line_chart(
            series,
            ylabel=f"Average Energy (mJ) — {PHASE_LABELS.get(phase, phase)}",
            title=f"Energy Consumption vs Network Size\n{PHASE_LABELS.get(phase, phase)} Phase",
            out_path=os.path.join(OUT_DIR, fname),
            show=args.show,
        )

    print("\nGenerating line charts — CPU vs Network Size")
    for phase, fname in phases_cpu:
        series = build_series(phase, "avg_cpu")
        if not series:
            print(f"  No data for {phase} — skipping.")
            continue
        line_chart(
            series,
            ylabel=f"Average CPU Time (s) — {PHASE_LABELS.get(phase, phase)}",
            title=f"CPU Time vs Network Size\n{PHASE_LABELS.get(phase, phase)} Phase",
            out_path=os.path.join(OUT_DIR, fname),
            show=args.show,
        )

    print("\nGenerating combined grouped bar charts")
    grouped_bar_chart(
        ["Enrollment", "Authentication", "Key Exchange"],
        "avg_energy",
        "Average Energy (mJ)",
        "Energy per Phase vs Network Size — All Schemes",
        os.path.join(OUT_DIR, "09_combined_energy_all_phases.png"),
        show=args.show,
    )
    grouped_bar_chart(
        ["Enrollment", "Authentication", "Key Exchange"],
        "avg_cpu",
        "Average CPU Time (s)",
        "CPU Time per Phase vs Network Size — All Schemes",
        os.path.join(OUT_DIR, "10_combined_cpu_all_phases.png"),
        show=args.show,
    )

    print("\nWriting master summary CSV")
    write_master_summary()

    print(f"\nAll charts saved to:\n  {OUT_DIR}")


if __name__ == "__main__":
    main()
