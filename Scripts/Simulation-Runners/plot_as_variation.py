"""
plot_as_variation.py
Visualise the authenticator-variation study (RA vs LAAKA, 2/5/10/15 active AS).

Reads:
  {scheme}/Simulation results/as-variation/N{count}/csv/summary.csv
    Columns: Phase, Seeds, n_devices, Avg_CPU_s, ..., Avg_Energy_mJ, CI95_Energy_mJ, CI95_CPU_s

Outputs (Results/Charts/Authenticator_variation/):
  01_as_variation_total_energy.png  — total energy across all devices, all phases
  02_as_variation_total_time.png    — total CPU time across all devices, all phases
  as_variation_summary.csv          — aggregated numbers for both charts

Usage:
  python3 plot_as_variation.py
  python3 plot_as_variation.py --out /path/to/output/dir
"""

import os, csv, math, argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

SCHEMES = {
    "RA":    os.path.join(REPO, "Revised-Anonymity", "Simulation results", "as-variation"),
    "LAAKA": os.path.join(REPO, "LAAKA",             "Simulation results", "as-variation"),
    "Zhou":  os.path.join(REPO, "Zhou-Scheme",        "Simulation results", "as-variation"),
}

AS_COUNTS  = [2, 5, 10]
N_DEVICES  = 20   # fixed for all variants
PHASES     = ["Enrollment", "Authentication", "Key Exchange"]

# Colour palette consistent with compare_revised_laaka_zhou.py / plot_network_variation.py
COLORS = {
    "RA":    "#2C6FAC",   # deep steel blue
    "LAAKA": "#B85C2C",   # muted terracotta
    "Zhou":  "#3A7D44",   # muted forest green
}
HATCH = {
    "RA":    "",
    "LAAKA": "///",
    "Zhou":  "xxx",
}

OUT_DEFAULT = os.path.join(REPO, "Results", "Charts", "Authenticator_variation")


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
def load_summary(path):
    """
    Return dict keyed by phase name:
      { "Enrollment": {"avg_energy_mj": ..., "ci95_energy_mj": ...,
                       "avg_cpu_s":     ..., "ci95_cpu_s":     ...,
                       "n_devices": ...},
        ... }
    """
    result = {}
    if not os.path.isfile(path):
        return result
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            phase = row["Phase"].strip()
            try:
                result[phase] = {
                    "avg_energy_mj": float(row["Avg_Energy_mJ"]),
                    "ci95_energy_mj": float(row["CI95_Energy_mJ"]),
                    "avg_cpu_s":     float(row["Avg_CPU_s"]),
                    "ci95_cpu_s":    float(row["CI95_CPU_s"]),
                    "n_devices":     int(row["n_devices"]),
                    "seeds":         int(row["Seeds"]),
                }
            except (ValueError, KeyError):
                pass
    return result


def collect_data():
    """
    Returns nested dict:
      data[scheme][n_as] = {
        "total_energy_mj":  float  (sum across phases × n_devices),
        "ci95_energy_mj":   float  (propagated from per-phase CIs),
        "total_cpu_s":      float,
        "ci95_cpu_s":       float,
        "n_seeds":          int,
        "phases":           {phase: {...}}   (raw per-phase values)
      }
    """
    data = {s: {} for s in SCHEMES}

    for scheme, base in SCHEMES.items():
        for n in AS_COUNTS:
            summary_path = os.path.join(base, f"N{n}", "csv", "summary.csv")
            # Zhou: path uses "Zhou-Scheme/Simulation results/as-variation/N{n}/csv/summary.csv"
            # (already accounted for in SCHEMES dict)
            phases = load_summary(summary_path)
            if not phases:
                print(f"  [WARN] Missing data: {summary_path}")
                continue

            # Aggregate across phases — total per device × N_DEVICES
            total_e, total_c = 0.0, 0.0
            ci_e_sq, ci_c_sq = 0.0, 0.0
            n_seeds = 0
            for phase in PHASES:
                if phase not in phases:
                    print(f"  [WARN] Phase '{phase}' missing for {scheme} N={n}")
                    continue
                p = phases[phase]
                nd = p.get("n_devices", N_DEVICES)
                total_e += p["avg_energy_mj"] * nd
                total_c += p["avg_cpu_s"]     * nd
                # propagate CI by quadrature (phases are independent)
                ci_e_sq += (p["ci95_energy_mj"] * nd) ** 2
                ci_c_sq += (p["ci95_cpu_s"]     * nd) ** 2
                n_seeds = max(n_seeds, p.get("seeds", 0))

            data[scheme][n] = {
                "total_energy_mj": total_e,
                "ci95_energy_mj":  math.sqrt(ci_e_sq),
                "total_cpu_s":     total_c,
                "ci95_cpu_s":      math.sqrt(ci_c_sq),
                "n_seeds":         n_seeds,
                "phases":          phases,
            }

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Chart helpers
# ─────────────────────────────────────────────────────────────────────────────
def save_fig(fig, path):
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path}")


def grouped_bar_chart(data, metric_key, ci_key, ylabel, title, out_path,
                      unit_scale=1.0, unit_label=""):
    """Generic grouped bar chart: x = active-AS count, groups = schemes."""
    schemes     = [s for s in SCHEMES if any(n in data[s] for n in AS_COUNTS)]
    n_schemes   = len(schemes)
    n_groups    = len(AS_COUNTS)
    bar_width   = 0.28
    group_gap   = 0.12
    total_width = n_schemes * bar_width + group_gap

    x = np.arange(n_groups) * total_width
    offsets = np.linspace(-(n_schemes - 1) / 2, (n_schemes - 1) / 2, n_schemes) * bar_width

    fig, ax = plt.subplots(figsize=(9, 5))

    for i, scheme in enumerate(schemes):
        vals  = []
        cis   = []
        for n in AS_COUNTS:
            if n in data[scheme]:
                vals.append(data[scheme][n][metric_key] * unit_scale)
                cis.append(data[scheme][n][ci_key]      * unit_scale)
            else:
                vals.append(0.0)
                cis.append(0.0)

        bars = ax.bar(
            x + offsets[i], vals,
            width=bar_width,
            label=scheme,
            color=COLORS[scheme],
            hatch=HATCH[scheme],
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )

        # Value labels on bars
        all_vals = [v for v in vals if v > 0]
        top_ref  = max(all_vals) if all_vals else 1
        for bar, v in zip(bars, vals):
            if v > 0:
                lbl = f"{v:.1f}" if abs(v) < 1000 else f"{v:.0f}"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01 * top_ref,
                    lbl,
                    ha="center", va="bottom",
                    fontsize=7, color="#222",
                )

    # Centre ticks on each group
    ax.set_xticks(x + offsets[n_schemes // 2] / 2)
    ax.set_xticklabels([str(n) for n in AS_COUNTS], fontsize=11)
    ax.set_xlabel("Number of Active Authentication Servers", fontsize=11)
    ax.set_ylabel(f"{ylabel}{' (' + unit_label + ')' if unit_label else ''}", fontsize=11)
    ax.set_title(title, fontsize=12, pad=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=10, framealpha=0.85)
    fig.tight_layout()
    save_fig(fig, out_path)


def stacked_bar_chart(data, metric_key_prefix, ci_key_prefix, ylabel, title, out_path,
                       unit_scale=1.0, unit_label=""):
    """
    Stacked bar chart showing per-phase breakdown within each scheme×AS-count group.
    metric_key_prefix: "energy" or "cpu" — looks up per-phase data.
    """
    phase_colors = {
        "Enrollment":     "#4E91C9",
        "Authentication": "#E07D3B",
        "Key Exchange":   "#5BAA68",
    }
    phase_hatch = {
        "RA":    {"Enrollment": "",    "Authentication": "",   "Key Exchange": ""},
        "LAAKA": {"Enrollment": "///", "Authentication": "///","Key Exchange": "///"},
        "Zhou":  {"Enrollment": "xxx", "Authentication": "xxx","Key Exchange": "xxx"},
    }

    schemes   = [s for s in SCHEMES if any(n in data[s] for n in AS_COUNTS)]
    n_schemes = len(schemes)
    bar_width = 0.35
    group_gap = 0.1
    total_width = n_schemes * bar_width + group_gap
    x = np.arange(len(AS_COUNTS)) * total_width
    offsets = np.linspace(-(n_schemes - 1) / 2, (n_schemes - 1) / 2, n_schemes) * bar_width

    fig, ax = plt.subplots(figsize=(10, 5))

    for i, scheme in enumerate(schemes):
        bottoms = np.zeros(len(AS_COUNTS))
        for phase in PHASES:
            phase_vals = []
            for n in AS_COUNTS:
                if n in data[scheme] and phase in data[scheme][n]["phases"]:
                    p  = data[scheme][n]["phases"][phase]
                    nd = p.get("n_devices", N_DEVICES)
                    if metric_key_prefix == "energy":
                        phase_vals.append(p["avg_energy_mj"] * nd * unit_scale)
                    else:
                        phase_vals.append(p["avg_cpu_s"] * nd * unit_scale)
                else:
                    phase_vals.append(0.0)

            phase_arr = np.array(phase_vals)
            lbl = f"{scheme} – {phase}" if i == 0 or True else None
            ax.bar(
                x + offsets[i], phase_arr,
                width=bar_width,
                bottom=bottoms,
                label=f"{scheme} – {phase}",
                color=phase_colors[phase],
                hatch=phase_hatch[scheme][phase],
                edgecolor="white",
                linewidth=0.5,
                alpha=0.88,
                zorder=3,
            )
            bottoms += phase_arr

    ax.set_xticks(x + (bar_width / 2) * (n_schemes - 1) / n_schemes * 0.5)
    ax.set_xticklabels([str(n) for n in AS_COUNTS], fontsize=11)
    ax.set_xlabel("Number of Active Authentication Servers", fontsize=11)
    ax.set_ylabel(f"{ylabel}{' (' + unit_label + ')' if unit_label else ''}", fontsize=11)
    ax.set_title(title, fontsize=12, pad=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, framealpha=0.85, ncol=2, loc="upper right")
    fig.tight_layout()
    save_fig(fig, out_path)


# ─────────────────────────────────────────────────────────────────────────────
# CSV summary
# ─────────────────────────────────────────────────────────────────────────────
def write_summary_csv(data, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "ActiveAS", "Seeds",
                    "Total_Energy_mJ", "CI95_Energy_mJ",
                    "Total_CPU_s",     "CI95_CPU_s"])
        for scheme in sorted(data):
            for n in AS_COUNTS:
                if n not in data[scheme]:
                    continue
                d = data[scheme][n]
                w.writerow([scheme, n, d["n_seeds"],
                             f"{d['total_energy_mj']:.4f}",
                             f"{d['ci95_energy_mj']:.4f}",
                             f"{d['total_cpu_s']:.4f}",
                             f"{d['ci95_cpu_s']:.4f}"])
    print(f"  CSV    → {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Plot authenticator-variation results")
    parser.add_argument("--out", default=OUT_DEFAULT,
                        help="Output directory for charts")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print("Loading simulation results...")
    data = collect_data()

    has_data = any(data[s] for s in data)
    if not has_data:
        print("No data found. Run run_as_variation.py first.")
        return

    print("Generating charts...")

    # Chart 01 — Total energy (all phases, all devices)
    grouped_bar_chart(
        data,
        metric_key="total_energy_mj",
        ci_key="ci95_energy_mj",
        ylabel="Total Energy (all devices, all phases)",
        title="Total Authentication Energy vs. Number of Active AS\n"
              "(20 devices × Enrollment + Auth + Key Exchange)",
        out_path=os.path.join(args.out, "01_as_variation_total_energy.png"),
        unit_label="mJ",
    )

    # Chart 02 — Total CPU time (all phases, all devices)
    grouped_bar_chart(
        data,
        metric_key="total_cpu_s",
        ci_key="ci95_cpu_s",
        ylabel="Total CPU Time (all devices, all phases)",
        title="Total Authentication CPU Time vs. Number of Active AS\n"
              "(20 devices × Enrollment + Auth + Key Exchange)",
        out_path=os.path.join(args.out, "02_as_variation_total_time.png"),
        unit_label="s",
    )

    # Chart 03 — Stacked energy breakdown by phase
    stacked_bar_chart(
        data,
        metric_key_prefix="energy",
        ci_key_prefix="energy",
        ylabel="Total Energy (all devices)",
        title="Per-Phase Energy Breakdown vs. Number of Active AS",
        out_path=os.path.join(args.out, "03_as_variation_stacked_energy.png"),
        unit_label="mJ",
    )

    # Chart 04 — Stacked CPU time breakdown by phase
    stacked_bar_chart(
        data,
        metric_key_prefix="cpu",
        ci_key_prefix="cpu",
        ylabel="Total CPU Time (all devices)",
        title="Per-Phase CPU Time Breakdown vs. Number of Active AS",
        out_path=os.path.join(args.out, "04_as_variation_stacked_time.png"),
        unit_label="s",
    )

    # Per-device average line chart (optional, for extra insight)
    _plot_per_device_line(data, args.out)

    # Summary CSV
    write_summary_csv(data, os.path.join(args.out, "as_variation_summary.csv"))

    print("\nDone.  Charts saved to:", args.out)


def _plot_per_device_line(data, out_dir):
    """Line chart: avg per-device total cost vs AS count, with shaded CI band."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    metrics = [
        ("total_energy_mj", "ci95_energy_mj", "Avg Per-Device Total Energy (mJ)",
         "Energy"),
        ("total_cpu_s",     "ci95_cpu_s",     "Avg Per-Device Total CPU Time (s)",
         "CPU Time"),
    ]
    for ax, (mk, ck, ylabel, _) in zip(axes, metrics):
        for scheme in sorted(data):
            xs, ys, errs = [], [], []
            for n in AS_COUNTS:
                if n in data[scheme]:
                    xs.append(n)
                    ys.append(data[scheme][n][mk] / N_DEVICES)
                    errs.append(data[scheme][n][ck] / N_DEVICES)
            if not xs:
                continue
            xs_arr = np.array(xs)
            ys_arr = np.array(ys)
            errs_arr = np.array(errs)
            ax.plot(xs_arr, ys_arr, marker="o", label=scheme,
                    color=COLORS[scheme], linewidth=1.8)
            ax.fill_between(xs_arr, ys_arr - errs_arr, ys_arr + errs_arr,
                            alpha=0.18, color=COLORS[scheme])

        ax.set_xlabel("Number of Active Authentication Servers", fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_xticks(AS_COUNTS)
        ax.yaxis.grid(True, linestyle="--", alpha=0.45)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(fontsize=9)

    axes[0].set_title("Per-Device Energy vs. Active AS Count", fontsize=11)
    axes[1].set_title("Per-Device CPU Time vs. Active AS Count", fontsize=11)
    fig.tight_layout()
    save_fig(fig, os.path.join(out_dir, "05_as_variation_per_device_line.png"))


if __name__ == "__main__":
    main()
