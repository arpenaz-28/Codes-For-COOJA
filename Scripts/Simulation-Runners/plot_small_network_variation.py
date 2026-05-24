"""
plot_small_network_variation.py
Generate energy and CPU scalability charts for the small-network study (N=10,20,30).

Reads CSV-Data/{RA,LAAKA,Zhou}/N{10,20,30}/summary.csv and produces:
  01_energy_enrollment.png
  02_energy_auth.png
  03_energy_keyex.png
  04_energy_auth_keyex.png
  05_cpu_enrollment.png
  06_cpu_auth.png
  07_cpu_keyex.png
  08_cpu_auth_keyex.png
  09_total_energy_grouped_bar.png
  10_total_cpu_grouped_bar.png
  11_combined_energy_all_phases.png
  12_combined_cpu_all_phases.png
  small_network_variation_summary.csv

All outputs go to  Results/Small-Network-Variation/Charts/

Usage:
  python3 plot_small_network_variation.py
  python3 plot_small_network_variation.py --show
"""

import os, csv, argparse, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
REPO     = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
BASE     = os.path.join(REPO, "Results", "Small-Network-Variation")
OUT_DIR  = os.path.join(BASE, "Charts")
SIZES    = [10, 20, 30]

RESULTS = {
    "Proposed": os.path.join(BASE, "CSV-Data", "RA"),
    "LAAKA":    os.path.join(BASE, "CSV-Data", "LAAKA"),
    "Zhou":     os.path.join(BASE, "CSV-Data", "Zhou"),
}

SCHEME_COLORS = {
    "Proposed": "#2C6FAC",
    "LAAKA":    "#B85C2C",
    "Zhou":     "#3A7D44",
}
SCHEME_MARKERS = {
    "Proposed": "o",
    "LAAKA":    "s",
    "Zhou":     "^",
}

_CHART_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    16,
    "axes.titleweight":  "bold",
    "axes.labelsize":    17,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   13,
    "ytick.labelsize":   13,
    "xtick.major.size":  0,
    "legend.fontsize":   13,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

PHASE_LABELS = {
    "Enrollment":     "Enrollment",
    "Authentication": "Authentication",
    "Key Exchange":   "Key Exchange",
    "Auth+KeyEx":     "Auth + Key Exchange",
}

PHASE_STYLES = {
    "Enrollment":     {"linestyle": "-",  "marker": "o"},
    "Authentication": {"linestyle": "--", "marker": "s"},
    "Key Exchange":   {"linestyle": ":",  "marker": "^"},
}


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
def load_summary(scheme_label, n_total):
    path = os.path.join(RESULTS[scheme_label], f"N{n_total}", "summary.csv")
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
                "ci_cpu":     math.sqrt(a["ci_cpu"] ** 2 + k["ci_cpu"] ** 2),
                "avg_energy": a["avg_energy"] + k["avg_energy"],
                "ci_energy":  math.sqrt(a["ci_energy"] ** 2 + k["ci_energy"] ** 2),
                "n_devices":  a["n_devices"],
            }
    return result


def build_series(phase_name, metric):
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
# ─────────────────────────────────────────────────────────────────────────────
def _apply_style(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, fontsize=17, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=17, fontweight="bold")
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(fontsize=13)
    ax.set_xticks(SIZES)


def line_chart(series, ylabel, title, out_path, show=False):
    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(9, 5))
        for scheme, (xs, ys, errs) in series.items():
            ax.errorbar(xs, ys, yerr=errs,
                        label=scheme,
                        color=SCHEME_COLORS[scheme],
                        marker=SCHEME_MARKERS[scheme],
                        linewidth=2, markersize=7, capsize=5)
        _apply_style(ax, "Total Network Nodes", ylabel, title)
        ax.set_xticks(SIZES)
        fig.tight_layout()
        fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
        if show:
            plt.show()
        plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


def _grouped_bar(metric, ylabel, title, out_path, show=False):
    phases  = ["Enrollment", "Authentication", "Key Exchange"]
    schemes = list(RESULTS.keys())
    n_s     = len(schemes)
    x       = np.arange(len(SIZES))
    width   = 0.24

    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(10, 5.5))
        fig.patch.set_facecolor("white")

        all_vals = []
        for si, scheme in enumerate(schemes):
            offsets    = x + (si - (n_s - 1) / 2) * width
            bar_totals = []
            for n in SIZES:
                d   = load_summary(scheme, n)
                tot = 0.0
                if d:
                    for phase in phases:
                        if phase in d:
                            key = "avg_energy" if metric == "avg_energy" else "avg_cpu"
                            tot += d[phase][key] * d[phase]["n_devices"]
                bar_totals.append(tot)
            all_vals.extend(bar_totals)

            ax.bar(offsets, bar_totals, width,
                   label=scheme,
                   color=SCHEME_COLORS[scheme], alpha=0.88,
                   edgecolor="white", linewidth=0.8)

            max_val = max(all_vals) if all_vals else 1
            for offset, val in zip(offsets, bar_totals):
                if val > 0:
                    ax.text(offset, val + max_val * 0.012,
                            f"{val:.1f}" if metric == "avg_energy" else f"{val:.2f}",
                            ha="center", va="bottom",
                            fontsize=11, color="#555555")

        ax.set_xticks(x)
        ax.set_xticklabels([f"N = {n}" for n in SIZES])
        ax.set_xlabel("Total Network Nodes", labelpad=8)
        ax.set_ylabel(ylabel, labelpad=8)
        ax.set_title(title, pad=14, color="#222222")
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.legend(loc="upper left", frameon=True, framealpha=0.92,
                  edgecolor="#dddddd", handlelength=1.4, handleheight=1.0, borderpad=0.7)

        fig.tight_layout()
        fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
        if show:
            plt.show()
        plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


def combined_phase_line_chart(metric, ylabel, title, out_path, show=False):
    phases = ["Enrollment", "Authentication", "Key Exchange"]
    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(10, 6))
        for scheme in RESULTS:
            color = SCHEME_COLORS[scheme]
            for phase in phases:
                xs, ys, errs = [], [], []
                for n in SIZES:
                    d = load_summary(scheme, n)
                    if d is None or phase not in d:
                        continue
                    xs.append(n)
                    ys.append(d[phase][metric])
                    err_key = "ci_energy" if "energy" in metric else "ci_cpu"
                    errs.append(d[phase][err_key])
                if not xs:
                    continue
                style = PHASE_STYLES[phase]
                ax.errorbar(xs, ys, yerr=errs,
                            label=f"{scheme} — {PHASE_LABELS[phase]}",
                            color=color,
                            linestyle=style["linestyle"],
                            marker=SCHEME_MARKERS[scheme],
                            linewidth=2, markersize=7, capsize=4, alpha=0.9)

        ax.set_xlabel("Total Network Nodes", fontsize=14, fontweight="bold")
        ax.set_ylabel(ylabel, fontsize=14, fontweight="bold")
        ax.set_title(title, fontsize=15, fontweight="bold")
        ax.set_xticks(SIZES)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, fontsize=9, ncol=2, loc="upper left", framealpha=0.85)
        ax.annotate("† Zhou scheme has no separate Key Exchange phase",
                    xy=(0.99, 0.02), xycoords="axes fraction",
                    ha="right", va="bottom", fontsize=8, color="#3A7D44",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))
        fig.tight_layout()
        fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
        if show:
            plt.show()
        plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


# ─────────────────────────────────────────────────────────────────────────────
# Master summary CSV
# ─────────────────────────────────────────────────────────────────────────────
def write_master_summary():
    out = os.path.join(OUT_DIR, "small_network_variation_summary.csv")
    phases = ["Enrollment", "Authentication", "Key Exchange", "Auth+KeyEx"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "N_total", "N_devices", "Phase",
                    "Avg_Energy_mJ", "CI95_Energy_mJ",
                    "Avg_CPU_s",    "CI95_CPU_s"])
        for scheme in RESULTS:
            for n in SIZES:
                d = load_summary(scheme, n)
                if d is None:
                    continue
                for phase in phases:
                    if phase not in d:
                        continue
                    p = d[phase]
                    w.writerow([scheme, n, p["n_devices"], phase,
                                f"{p['avg_energy']:.4f}", f"{p['ci_energy']:.4f}",
                                f"{p['avg_cpu']:.6f}",   f"{p['ci_cpu']:.6f}"])
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

    tasks = [
        # (phase, metric, ylabel, title, filename)
        ("Enrollment",     "avg_energy", "Avg Energy per Device (mJ)",
         "Energy — Enrollment Phase\n(Small Network, N=10/20/30)",
         "01_energy_enrollment.png"),
        ("Authentication", "avg_energy", "Avg Energy per Device (mJ)",
         "Energy — Authentication Phase\n(Small Network, N=10/20/30)",
         "02_energy_auth.png"),
        ("Key Exchange",   "avg_energy", "Avg Energy per Device (mJ)",
         "Energy — Key Exchange Phase\n(Small Network, N=10/20/30)",
         "03_energy_keyex.png"),
        ("Auth+KeyEx",     "avg_energy", "Avg Energy per Device (mJ)",
         "Energy — Auth + Key Exchange\n(Small Network, N=10/20/30)",
         "04_energy_auth_keyex.png"),
        ("Enrollment",     "avg_cpu",    "Avg CPU Time per Device (s)",
         "CPU Time — Enrollment Phase\n(Small Network, N=10/20/30)",
         "05_cpu_enrollment.png"),
        ("Authentication", "avg_cpu",    "Avg CPU Time per Device (s)",
         "CPU Time — Authentication Phase\n(Small Network, N=10/20/30)",
         "06_cpu_auth.png"),
        ("Key Exchange",   "avg_cpu",    "Avg CPU Time per Device (s)",
         "CPU Time — Key Exchange Phase\n(Small Network, N=10/20/30)",
         "07_cpu_keyex.png"),
        ("Auth+KeyEx",     "avg_cpu",    "Avg CPU Time per Device (s)",
         "CPU Time — Auth + Key Exchange\n(Small Network, N=10/20/30)",
         "08_cpu_auth_keyex.png"),
    ]

    for phase, metric, ylabel, title, fname in tasks:
        series = build_series(phase, metric)
        if not series:
            print(f"  Skipping {fname} (no data)")
            continue
        line_chart(series, ylabel, title, os.path.join(OUT_DIR, fname), show=args.show)

    print("\nGenerating total energy grouped bar chart")
    _grouped_bar("avg_energy",
                 "Total Energy — All Devices (mJ)",
                 "Total Energy vs Small Network Size",
                 os.path.join(OUT_DIR, "09_total_energy_grouped_bar.png"),
                 show=args.show)

    print("Generating total CPU grouped bar chart")
    _grouped_bar("avg_cpu",
                 "Total CPU Time — All Devices (s)",
                 "Total CPU Time vs Small Network Size",
                 os.path.join(OUT_DIR, "10_total_cpu_grouped_bar.png"),
                 show=args.show)

    print("Generating combined energy line chart (all phases)")
    combined_phase_line_chart(
        "avg_energy",
        "Avg Energy per Device (mJ)",
        "Energy vs Small Network Size — All Schemes & Phases",
        os.path.join(OUT_DIR, "11_combined_energy_all_phases.png"),
        show=args.show,
    )

    print("Generating combined CPU line chart (all phases)")
    combined_phase_line_chart(
        "avg_cpu",
        "Avg CPU Time per Device (s)",
        "CPU Time vs Small Network Size — All Schemes & Phases",
        os.path.join(OUT_DIR, "12_combined_cpu_all_phases.png"),
        show=args.show,
    )

    print("\nWriting master summary CSV")
    write_master_summary()

    print(f"\nAll charts saved to:\n  {OUT_DIR}")


if __name__ == "__main__":
    main()
