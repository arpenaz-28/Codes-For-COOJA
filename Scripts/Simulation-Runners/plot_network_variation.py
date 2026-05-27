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
OUT_DIR  = os.path.join(REPO, "Results", "COOJA-Simulation", "Charts", "Network_variation")
PAPER_DIR = os.path.join(REPO, "Paper")
SIZES    = [30, 50, 80, 100]

# Path to the consolidated small-network summary (contains N=30 data)
_SMALL_NET_CSV = os.path.join(
    REPO, "Results", "COOJA-Simulation", "Network-Variation", "Charts",
    "small_network_variation_summary.csv"
)

RESULTS = {
    "Proposed": os.path.join(REPO, "Revised-Anonymity",
                             "Simulation results", "network-variation"),
    "LAAKA":    os.path.join(REPO, "LAAKA",
                             "Simulation results", "network-variation"),
    "Zhou":     os.path.join(REPO, "Results", "COOJA-Simulation",
                             "Zhou-Simulation", "network-variation"),
}

# Raw per-device CSV directories: direct source of truth for the bar charts.
# Each folder must contain enroll-results.csv, auth-results.csv, keyex-results.csv
# (seed-averaged per-device values).  N=30 data lives in the small-network tree.
_SMALL_RAW = os.path.join(REPO, "Results", "COOJA-Simulation", "Network-Variation", "CSV-Data")
_RAW_CSV_DIRS = {
    ("Proposed", 30):  os.path.join(_SMALL_RAW, "RA",    "N30"),
    ("Proposed", 50):  os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N50",  "csv"),
    ("Proposed", 80):  os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N80",  "csv"),
    ("Proposed", 100): os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation", "N100", "csv"),
    ("LAAKA",    30):  os.path.join(_SMALL_RAW, "LAAKA", "N30"),
    ("LAAKA",    50):  os.path.join(REPO, "LAAKA", "Simulation results", "network-variation", "N50",  "csv"),
    ("LAAKA",    80):  os.path.join(REPO, "LAAKA", "Simulation results", "network-variation", "N80",  "csv"),
    ("LAAKA",    100): os.path.join(REPO, "LAAKA", "Simulation results", "network-variation", "N100", "csv"),
    ("Zhou",     30):  os.path.join(_SMALL_RAW, "Zhou",  "N30"),
    ("Zhou",     50):  os.path.join(REPO, "Results", "COOJA-Simulation", "Zhou-Simulation", "network-variation", "N50",  "csv"),
    ("Zhou",     80):  os.path.join(REPO, "Results", "COOJA-Simulation", "Zhou-Simulation", "network-variation", "N80",  "csv"),
    ("Zhou",     100): os.path.join(REPO, "Results", "COOJA-Simulation", "Zhou-Simulation", "network-variation", "N100", "csv"),
}

SCHEME_COLORS = {
    "Proposed": "#2C6FAC",   # deep steel blue
    "LAAKA":    "#B85C2C",   # muted terracotta
    "Zhou":     "#3A7D44",   # muted forest green
}
SCHEME_MARKERS = {
    "Proposed": "o",
    "LAAKA":    "s",
    "Zhou":     "^",
}
SCHEME_HATCHES = {
    "Proposed": "///",
    "LAAKA":    "\\\\",
    "Zhou":     "xxx",
}

# Global aesthetic style applied to both charts
_CHART_STYLE = {
    "font.family":        "Liberation Sans",
    "font.size":          15,
    "axes.titlesize":     18,
    "axes.titleweight":   "bold",
    "axes.labelsize":     19,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.linewidth":     0.7,
    "xtick.labelsize":    15,
    "ytick.labelsize":    15,
    "xtick.major.size":   0,
    "legend.fontsize":    15,
    "legend.framealpha":  0.9,
    "legend.edgecolor":   "#cccccc",
    "grid.color":         "#e5e5e5",
    "grid.linewidth":     0.6,
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

def load_raw_total(scheme_label, n, metric):
    """
    Read enroll/auth/keyex raw per-device CSVs and return (total, n_devices).
      metric="energy" → sum of Energy_J across all devices × all phases, converted to mJ
      metric="cpu"    → sum of CPU_Time_s across all devices × all phases
    This is the transparent approach: no intermediate averaging, direct sum from
    seed-averaged per-device measurements logged by COOJA.
    Returns (0.0, 0) when data is unavailable.
    """
    csv_dir = _RAW_CSV_DIRS.get((scheme_label, n))
    if not csv_dir or not os.path.isdir(csv_dir):
        return 0.0, 0

    col = "Energy_J" if metric == "energy" else "CPU_Time_s"
    device_totals = {}

    for phase_file in ["enroll-results.csv", "auth-results.csv", "keyex-results.csv"]:
        path = os.path.join(csv_dir, phase_file)
        if not os.path.isfile(path):
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                did = int(row["Device_ID"])
                device_totals[did] = device_totals.get(did, 0.0) + float(row[col])

    if not device_totals:
        return 0.0, 0

    total = sum(device_totals.values())
    if metric == "energy":
        total *= 1000   # J → mJ
    return total, len(device_totals)


_N30_CACHE = {}   # {scheme_label: {phase: {...}}}  — used by line charts only

def _load_n30_data():
    """Parse consolidated small_network_variation_summary.csv for N=30 rows."""
    global _N30_CACHE
    data = {s: {} for s in RESULTS}
    if not os.path.isfile(_SMALL_NET_CSV):
        return data
    with open(_SMALL_NET_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["N_total"]) != 30:
                continue
            scheme = row["Scheme"]
            phase  = row["Phase"]
            if scheme not in data:
                continue
            data[scheme][phase] = {
                "avg_cpu":    float(row["Avg_CPU_s"]),
                "ci_cpu":     float(row["CI95_CPU_s"]),
                "avg_energy": float(row["Avg_Energy_mJ"]),
                "ci_energy":  float(row["CI95_Energy_mJ"]),
                "n_devices":  int(row["N_devices"]),
            }
    for scheme in data:
        r = data[scheme]
        if "Auth+KeyEx" not in r:
            a = r.get("Authentication")
            k = r.get("Key Exchange")
            if a and k:
                r["Auth+KeyEx"] = {
                    "avg_cpu":    a["avg_cpu"]    + k["avg_cpu"],
                    "ci_cpu":     math.sqrt(a["ci_cpu"]**2    + k["ci_cpu"]**2),
                    "avg_energy": a["avg_energy"] + k["avg_energy"],
                    "ci_energy":  math.sqrt(a["ci_energy"]**2 + k["ci_energy"]**2),
                    "n_devices":  a["n_devices"],
                }
    _N30_CACHE = data
    return data


def load_summary(scheme_label, n_total):
    """Return dict keyed by phase name → {avg_cpu, ci_cpu, avg_energy, ci_energy, n_devices}"""
    if n_total == 30:
        if not _N30_CACHE:
            _load_n30_data()
        return _N30_CACHE.get(scheme_label)
    path = os.path.join(RESULTS[scheme_label], f"N{n_total}", "csv", "summary.csv")
    if not os.path.isfile(path):
        return None
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            phase = row["Phase"]
            result[phase] = {
                "avg_cpu":    float(row["Avg_CPU_s"]),
                "ci_cpu":     float(row["CI95_CPU_s"]),
                "avg_energy": float(row["Avg_Energy_mJ"]),
                "ci_energy":  float(row["CI95_Energy_mJ"]),
                "n_devices":  int(row["n_devices"]),
            }
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
    ax.set_xlabel(xlabel, fontsize=19, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=19, fontweight="bold")
    ax.set_title(title, fontsize=18, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(fontsize=15)
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
                   facecolor="none",
                   edgecolor=SCHEME_COLORS[scheme],
                   hatch=SCHEME_HATCHES[scheme],
                   linewidth=1.2)
            idx += 1

    ax.set_xticks(x)
    ax.set_xticklabels([f"N={n}" for n in SIZES])
    ax.set_xlabel("Total Network Nodes", fontsize=14)
    ax.set_ylabel(ylabel, fontsize=14)
    ax.set_title(title, fontsize=15, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, ncol=3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


# ─────────────────────────────────────────────────────────────────────────────
# Combined all-schemes × all-phases line chart
# ─────────────────────────────────────────────────────────────────────────────
PHASE_STYLES = {
    "Enrollment":     {"linestyle": "-",  "marker": "o"},
    "Authentication": {"linestyle": "--", "marker": "s"},
    "Key Exchange":   {"linestyle": ":",  "marker": "^"},
}

def combined_energy_line_chart(out_path, show=False):
    """
    Single figure: energy vs network size.
    Colour = scheme, line style+marker = phase.
    Zhou has no Key Exchange phase — only two lines are drawn for it.
    """
    phases = ["Enrollment", "Authentication", "Key Exchange"]

    fig, ax = plt.subplots(figsize=(10, 6))

    for scheme in RESULTS:
        color = SCHEME_COLORS[scheme]
        marker_scheme = SCHEME_MARKERS[scheme]
        for phase in phases:
            xs, ys, errs = [], [], []
            for n in SIZES:
                d = load_summary(scheme, n)
                if d is None or phase not in d:
                    continue
                xs.append(n)
                ys.append(d[phase]["avg_energy"])
                errs.append(d[phase]["ci_energy"])
            if not xs:
                continue
            style = PHASE_STYLES[phase]
            label = f"{scheme} — {PHASE_LABELS[phase]}"
            ax.errorbar(xs, ys, yerr=errs,
                        label=label,
                        color=color,
                        linestyle=style["linestyle"],
                        marker=marker_scheme,
                        linewidth=2, markersize=7, capsize=4,
                        alpha=0.9)

    ax.set_xlabel("Total Network Nodes", fontsize=14)
    ax.set_ylabel("Average Energy per Device (mJ)", fontsize=14)
    ax.set_title("Energy Consumption vs Network Size\nAll Schemes · All Phases",
                 fontsize=15, fontweight="bold")
    ax.set_xticks(SIZES)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # Two-column legend: schemes as colour, phases as line style
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, fontsize=11, ncol=2,
              loc="upper left", framealpha=0.85)

    # Annotation explaining Zhou's missing Key Exchange
    ax.annotate("† Zhou scheme has no separate\n  Key Exchange phase",
                xy=(0.99, 0.02), xycoords="axes fraction",
                ha="right", va="bottom", fontsize=10,
                color="#4CAF50",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


# ─────────────────────────────────────────────────────────────────────────────
# Grouped + stacked bar: total energy per network, all schemes, all phases
# ─────────────────────────────────────────────────────────────────────────────
PHASE_COLORS = {
    "Enrollment":     "#90CAF9",   # light blue
    "Authentication": "#FFB74D",   # light orange
    "Key Exchange":   "#A5D6A7",   # light green
}

def _grouped_bar(metric, ylabel, title, out_path, paper_path=None, show=False):
    """
    Shared renderer for charts 12 and 13.
    metric : "avg_energy" | "avg_cpu"
    """
    schemes = list(RESULTS.keys())
    n_s     = len(schemes)
    spacing = 0.80                          # reduce inter-group gap
    x       = np.arange(len(SIZES)) * spacing
    width   = 0.20

    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(12, 6.5))
        fig.patch.set_facecolor("white")

        raw_metric = "energy" if metric == "avg_energy" else "cpu"

        all_totals = []
        bar_data = []    # (offsets, bar_totals, scheme) — collected first pass
        for si, scheme in enumerate(schemes):
            offsets    = x + (si - (n_s - 1) / 2) * width
            bar_totals = []
            for n in SIZES:
                tot, _ = load_raw_total(scheme, n, raw_metric)
                bar_totals.append(tot)
            all_totals.extend(bar_totals)
            bar_data.append((offsets, bar_totals, scheme))

        global_max = max(all_totals) if all_totals else 1
        ax.set_ylim(0, global_max * 1.32)
        ax.set_xlim(-spacing * 0.6, x[-1] + spacing * 0.6)

        for offsets, bar_totals, scheme in bar_data:
            color = SCHEME_COLORS[scheme]
            ax.bar(offsets, bar_totals, width,
                   label=scheme,
                   facecolor="none",
                   edgecolor=color,
                   hatch=SCHEME_HATCHES[scheme],
                   linewidth=1.5)

            for offset, val in zip(offsets, bar_totals):
                if val > 0:
                    ax.text(offset, val + global_max * 0.015,
                            f"{val:.0f}" if metric == "avg_energy" else f"{val:.1f}",
                            ha="center", va="bottom",
                            fontsize=15, color="#333333", fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels([f"N = {n}" for n in SIZES], fontsize=17)
        ax.set_xlabel("Total Network Nodes", labelpad=8, fontsize=20, fontweight="bold")
        ax.set_ylabel(ylabel, labelpad=8, fontsize=20, fontweight="bold")
        ax.set_title(title, pad=14, color="#222222", fontsize=21, fontweight="bold")

        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0, labelsize=16)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")

        ax.legend(loc="upper left",
                  frameon=True, framealpha=0.92,
                  edgecolor="#dddddd",
                  handlelength=1.4, handleheight=1.0,
                  borderpad=0.7, fontsize=16)

        fig.tight_layout()
        fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
        if paper_path:
            fig.savefig(paper_path, dpi=180, bbox_inches="tight", facecolor="white")
            print(f"  Saved: {os.path.basename(paper_path)}  (Paper/)")
        if show:
            plt.show()
        plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


def total_energy_grouped_bar(out_path, paper_path=None, show=False):
    _grouped_bar(
        "avg_energy",
        "Total Energy — All Devices (mJ)",
        "Total Energy Consumption vs Network Size",
        out_path, paper_path, show,
    )


def total_cpu_grouped_bar(out_path, paper_path=None, show=False):
    _grouped_bar(
        "avg_cpu",
        "Total CPU Time — All Devices (s)",
        "Total CPU Time vs Network Size",
        out_path, paper_path, show,
    )


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

    print("Generating total-energy grouped bar chart")
    total_energy_grouped_bar(
        os.path.join(OUT_DIR, "12_total_energy_grouped_bar.png"),
        paper_path=os.path.join(PAPER_DIR, "fig_sim_net_energy.png"),
        show=args.show,
    )

    print("\nGenerating total-CPU grouped bar chart")
    total_cpu_grouped_bar(
        os.path.join(OUT_DIR, "13_total_cpu_grouped_bar.png"),
        paper_path=os.path.join(PAPER_DIR, "fig_sim_net_cpu.png"),
        show=args.show,
    )

    print("\nWriting master summary CSV")
    write_master_summary()

    print(f"\nAll charts saved to:\n  {OUT_DIR}")


if __name__ == "__main__":
    main()
