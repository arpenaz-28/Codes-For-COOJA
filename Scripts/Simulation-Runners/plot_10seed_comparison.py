"""
plot_10seed_comparison.py

Generate two comparison charts from 10-seed COOJA simulation results
(Proposed/RA, LAAKA, Zhou).

Chart 1 — Total cost across ALL 20 devices (sum per seed, then mean ± 95% CI)
Chart 2 — Per-device MEAN cost           (mean over 20 devices per seed, then
                                           mean ± 95% CI across seeds)

Each chart has two side-by-side panels: Energy (mJ) and CPU Time (s).

Reads:  Results/COOJA-Simulation/10-Seed-Comparison/{Proposed,LAAKA,Zhou}/seed_results.csv
Writes: Results/COOJA-Simulation/10-Seed-Comparison/Charts/
  cooja_01_total_energy_cpu.png
  cooja_02_perdev_energy_cpu.png
"""

import csv, math, os, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

REPO     = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
DATA_DIR = os.path.join(REPO, "Results", "COOJA-Simulation", "10-Seed-Comparison")
OUT_DIR  = os.path.join(DATA_DIR, "Charts")
os.makedirs(OUT_DIR, exist_ok=True)

SCHEMES      = ["Proposed", "DAuth", "LAAKA", "Zhou"]
SCHEME_LABEL = {"Proposed": "Proposed", "DAuth": "DAuth", "LAAKA": "LAAKA", "Zhou": "Zhou"}
COLORS       = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6", "LAAKA": "#B85C2C", "Zhou": "#2E8B57"}
HATCHES      = {"Proposed": "///",     "DAuth": "...",     "LAAKA": "\\\\\\", "Zhou": "xxx"}

_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         19,
    "axes.titlesize":    23,
    "axes.titleweight":  "bold",
    "axes.labelsize":    22,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   20,
    "ytick.labelsize":   19,
    "xtick.major.size":  0,
    "legend.fontsize":   18,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}


# ── Data loading ──────────────────────────────────────────────────────────────
def load_seed_results(scheme):
    """
    Return list of per-seed dicts:
      [{"total_energy_mJ": float, "total_cpu_s": float,
        "mean_energy_mJ": float,  "mean_cpu_s": float}, ...]
    One entry per seed.
    """
    path = os.path.join(DATA_DIR, scheme, "seed_results.csv")
    if not os.path.isfile(path):
        print(f"  WARNING: {path} not found — skipping {scheme}")
        return []

    seed_data = {}   # seed → list of (total_energy_mJ, total_cpu_s) per device
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seed = int(row["Seed"])
            seed_data.setdefault(seed, []).append(
                (float(row["Total_Energy_mJ"]), float(row["Total_CPU_s"]))
            )

    results = []
    for seed in sorted(seed_data):
        vals = seed_data[seed]
        total_e = sum(v[0] for v in vals)           # sum across all 20 devices
        total_c = sum(v[1] for v in vals)
        mean_e  = statistics.mean(v[0] for v in vals)  # mean per device
        mean_c  = statistics.mean(v[1] for v in vals)
        results.append({
            "seed":            seed,
            "total_energy_mJ": total_e,
            "total_cpu_s":     total_c,
            "mean_energy_mJ":  mean_e,
            "mean_cpu_s":      mean_c,
        })
    return results


def agg(vals):
    n  = len(vals)
    mu = statistics.mean(vals)
    ci = 1.96 * statistics.stdev(vals) / math.sqrt(n) if n > 1 else 0.0
    return mu, ci


# ── Bar-chart panel ───────────────────────────────────────────────────────────
def draw_panel(ax, stats, ylabel, fmt):
    """
    stats: list of (scheme_name, mean, ci) in order Proposed / LAAKA / Zhou
    """
    pos = np.arange(len(stats))
    w   = 0.42
    max_val = max(mu + ci for _, mu, ci in stats)

    for i, (name, mu, ci) in enumerate(stats):
        color  = COLORS[name]
        hatch  = HATCHES[name]
        ax.bar(pos[i], mu, w,
               facecolor="none", edgecolor=color, hatch=hatch, linewidth=1.5)

    ax.set_xticks(pos)
    ax.set_xticklabels([SCHEME_LABEL[s] for s, _, _ in stats],
                       fontsize=20, ha="center")
    ax.set_ylabel(ylabel, labelpad=20, fontsize=22, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, max_val * 1.15)


def legend_patches(metric_unit, stats):
    return [
        mpatches.Patch(
            facecolor="none", edgecolor=COLORS[name],
            hatch=HATCHES[name], linewidth=1.5,
            label=f"{SCHEME_LABEL[name]}: {mu:.1f} {metric_unit}"
                  f"  (±{ci:.1f})"
        )
        for name, mu, ci in stats
    ]


# ── Chart 1: total across all 20 devices ─────────────────────────────────────
def make_total_chart(scheme_records):
    e_stats, c_stats = [], []
    for scheme in SCHEMES:
        recs = scheme_records.get(scheme, [])
        if not recs:
            continue
        e_mu, e_ci = agg([r["total_energy_mJ"] for r in recs])
        c_mu, c_ci = agg([r["total_cpu_s"]     for r in recs])
        e_stats.append((scheme, e_mu, e_ci))
        c_stats.append((scheme, c_mu, c_ci))

    with plt.rc_context(_STYLE):
        fig, (ax_e, ax_c) = plt.subplots(1, 2, figsize=(14, 7))
        fig.patch.set_facecolor("white")

        draw_panel(ax_e, e_stats, "Total Energy — All Devices (mJ)", ".1f")
        draw_panel(ax_c, c_stats, "Total CPU Time — All Devices (s)", ".2f")

        ax_e.legend(handles=legend_patches("mJ", e_stats),
                    loc="upper right", fontsize=10, framealpha=0.9,
                    edgecolor="#dddddd", handlelength=2.0, handleheight=1.4)
        ax_c.legend(handles=legend_patches("s", c_stats),
                    loc="upper right", fontsize=10, framealpha=0.9,
                    edgecolor="#dddddd", handlelength=2.0, handleheight=1.4)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, "cooja_01_total_energy_cpu.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", pad_inches=0.02, facecolor="white")
        plt.close(fig)
    print(f"  Saved: cooja_01_total_energy_cpu.png")


# ── Chart 2: per-device mean cost ────────────────────────────────────────────
def make_perdev_chart(scheme_records):
    e_stats, c_stats = [], []
    for scheme in SCHEMES:
        recs = scheme_records.get(scheme, [])
        if not recs:
            continue
        e_mu, e_ci = agg([r["mean_energy_mJ"] for r in recs])
        c_mu, c_ci = agg([r["mean_cpu_s"]     for r in recs])
        e_stats.append((scheme, e_mu, e_ci))
        c_stats.append((scheme, c_mu, c_ci))

    with plt.rc_context(_STYLE):
        fig, (ax_e, ax_c) = plt.subplots(1, 2, figsize=(14, 7))
        fig.patch.set_facecolor("white")

        draw_panel(ax_e, e_stats, "Mean Energy (mJ)", ".2f")
        draw_panel(ax_c, c_stats, "Mean CPU Time (s)", ".3f")

        scheme_patches = [
            mpatches.Patch(facecolor="none", edgecolor=COLORS[s],
                           hatch=HATCHES[s], linewidth=1.5,
                           label=SCHEME_LABEL[s])
            for s in SCHEMES
        ]
        fig.legend(handles=scheme_patches,
                   loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=4, fontsize=19, framealpha=0.9,
                   edgecolor="#dddddd", handlelength=2.2, handleheight=1.6)

        fig.tight_layout(rect=[0, 0.09, 1, 1])
        out = os.path.join(OUT_DIR, "cooja_02_perdev_energy_cpu.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", pad_inches=0.02, facecolor="white")
        plt.close(fig)
    print(f"  Saved: cooja_02_perdev_energy_cpu.png")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Loading seed_results.csv for each scheme...")
    scheme_records = {}
    for scheme in SCHEMES:
        recs = load_seed_results(scheme)
        if recs:
            scheme_records[scheme] = recs
            print(f"  {scheme}: {len(recs)} seeds loaded")
        else:
            print(f"  {scheme}: no data")

    if not scheme_records:
        print("No data found — run run_10seed_cooja_comparison.py first")
        return

    print("\nGenerating charts...")
    make_total_chart(scheme_records)
    make_perdev_chart(scheme_records)
    print(f"\nOutputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
