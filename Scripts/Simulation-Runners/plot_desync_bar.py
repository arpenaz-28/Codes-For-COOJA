"""
plot_desync_bar.py

Desync recovery comparison: Base (Das) vs Proposed — 4-bar chart.
Each scheme shows 2 bars:
  • Before Packet Loss  = Round 1 (normal auth+key exchange, per device)
  • Recovery            = Round 3 (re-auth after desync event, per device)

Data: summary.csv from each scheme's Desync-100/csv/ directory.
Outputs two panels (Energy and CPU Time) in the same style as fig_sim_total.png.

Usage:
  python3 Scripts/Simulation-Runners/plot_desync_bar.py
"""

import csv, math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

DATA = {
    "DAuth":    os.path.join(REPO, "Base-Scheme",       "Simulation-Results", "Desync-100", "csv", "summary.csv"),
    "Proposed": os.path.join(REPO, "Revised-Anonymity", "Simulation-Results", "Desync-100", "csv", "summary.csv"),
    "Zhou":     os.path.join(REPO, "Zhou-Scheme",       "Simulation-Results", "Desync-100", "csv", "summary.csv"),
}

OUT_DIR  = os.path.join(REPO, "Results", "COOJA-Simulation", "Desync-Recovery-Analysis")
OUT_FILE = os.path.join(OUT_DIR, "desync_bar.png")
PAPER_FILE = os.path.join(REPO, "Paper", "fig_desync_bar.png")

# ── Style (matches existing comparison charts) ────────────────────────────────
SCHEME_COLORS = {
    "DAuth":    "#7E5BA6",   # muted purple  (consistent with all other figures)
    "Proposed": "#2C6FAC",   # deep steel blue
    "Zhou":     "#2E8B57",   # sea green     (consistent with all other figures)
}
BAR_HATCHES = {
    "Before Packet Loss": "///",
    "Recovery":           "xxx",
}
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
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

SCHEMES   = ["DAuth", "Proposed", "Zhou"]
BAR_TYPES = ["Before Packet Loss", "Recovery"]

# Bar 1: Round 1 — normal auth+keyex (before any desync)
# Bar 2: Round 3 — recovery auth+keyex
#   DAuth:    failed auth + 2-step re-enrol to AS + retry auth + keyex
#   Proposed: direct recovery via PID_old (no re-enrol)
#   Zhou:     failed auth + 1-step re-enrol to GW + retry auth
BAR_ROUNDS = {
    "Before Packet Loss": ["Round 1"],
    "Recovery":           ["Round 3"],
}


# ── Data loading ──────────────────────────────────────────────────────────────
def load_summary(path):
    """Return {round_name: {avg_energy_mj, ci_energy_mj, avg_cpu_s, ci_cpu_s}}"""
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n = int(row["Seeds"])
            std_e = float(row["Std_Energy_mJ"])
            std_c = float(row["Std_CPU_s"])
            result[row["Round"]] = {
                "avg_energy_mj": float(row["Avg_Energy_mJ"]),
                "ci_energy_mj":  1.96 * std_e / math.sqrt(n) if n > 1 else 0.0,
                "avg_cpu_s":     float(row["Avg_CPU_s"]),
                "ci_cpu_s":      1.96 * std_c / math.sqrt(n) if n > 1 else 0.0,
            }
    return result


def aggregate_bar(rounds_data, round_keys):
    """Sum means and propagate CIs in quadrature across the given rounds."""
    total_e = sum(rounds_data[r]["avg_energy_mj"] for r in round_keys)
    total_c = sum(rounds_data[r]["avg_cpu_s"]     for r in round_keys)
    ci_e    = math.sqrt(sum(rounds_data[r]["ci_energy_mj"] ** 2 for r in round_keys))
    ci_c    = math.sqrt(sum(rounds_data[r]["ci_cpu_s"]     ** 2 for r in round_keys))
    return {"avg_energy_mj": total_e, "ci_energy_mj": ci_e,
            "avg_cpu_s": total_c,     "ci_cpu_s": ci_c}


# ── Chart drawing ─────────────────────────────────────────────────────────────
def draw_panel(ax, stats, ylabel):
    """
    stats: [(scheme, bar_type, mean, ci), ...]  in order Base-Before, Base-Rec,
           Proposed-Before, Proposed-Rec
    Groups of 2 bars per scheme, separated by a small gap.
    """
    n_schemes  = len(SCHEMES)
    bar_w      = 0.30
    group_gap  = 0.25
    group_w    = 2 * bar_w + group_gap

    max_val = max(mean + ci for _, _, mean, ci in stats)

    for s_idx, scheme in enumerate(SCHEMES):
        x_center = s_idx * group_w
        for b_idx, bar_type in enumerate(BAR_TYPES):
            entry = next(e for e in stats
                         if e[0] == scheme and e[1] == bar_type)
            _, _, mean, ci = entry
            x = x_center + (b_idx - 0.5) * bar_w

            ax.bar(x, mean, bar_w,
                   facecolor="none",
                   edgecolor=SCHEME_COLORS[scheme],
                   hatch=BAR_HATCHES[bar_type],
                   linewidth=1.5,
                   zorder=3)

    # x-ticks centred on each scheme group
    x_ticks  = [s * group_w for s in range(n_schemes)]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(SCHEMES, fontsize=20, ha="center")
    ax.set_ylabel(ylabel, labelpad=20, fontsize=22, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, max_val * 1.20)

    # extend x limits for breathing room
    group_w_total = (n_schemes - 1) * group_w
    ax.set_xlim(-group_w * 0.55, group_w_total + group_w * 0.55)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    summaries = {}
    for scheme, path in DATA.items():
        summaries[scheme] = load_summary(path)

    # Aggregate rounds into bar values and print
    bar_data = {}   # {scheme: {bar_type: aggregated_dict}}
    for scheme in SCHEMES:
        bar_data[scheme] = {}
        for bt, rounds in BAR_ROUNDS.items():
            d = aggregate_bar(summaries[scheme], rounds)
            bar_data[scheme][bt] = d
            print(f"  {scheme:10s} {bt:22s}: "
                  f"{d['avg_energy_mj']:.2f} ± {d['ci_energy_mj']:.2f} mJ | "
                  f"{d['avg_cpu_s']:.4f} ± {d['ci_cpu_s']:.4f} s")

    # Build flat stats list in fixed order
    e_stats, c_stats = [], []
    for scheme in SCHEMES:
        for bar_type in BAR_TYPES:
            d = bar_data[scheme][bar_type]
            e_stats.append((scheme, bar_type, d["avg_energy_mj"], d["ci_energy_mj"]))
            c_stats.append((scheme, bar_type, d["avg_cpu_s"],     d["ci_cpu_s"]))

    with plt.rc_context(_STYLE):
        fig, (ax_e, ax_c) = plt.subplots(1, 2, figsize=(20, 7))
        fig.patch.set_facecolor("white")

        draw_panel(ax_e, e_stats, "Avg. Energy (mJ)")
        draw_panel(ax_c, c_stats, "Avg. CPU Time (s)")
        ax_e.set_xlabel("(a)", fontsize=22, fontweight="bold")
        ax_c.set_xlabel("(b)", fontsize=22, fontweight="bold")

        # Horizontal legend at bottom — bar types, not schemes
        legend_patches = [
            mpatches.Patch(facecolor="none", edgecolor="#555555",
                           hatch=BAR_HATCHES[bt], linewidth=1.5, label=bt)
            for bt in BAR_TYPES
        ]
        fig.legend(handles=legend_patches,
                   loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=2, fontsize=19, framealpha=0.9,
                   edgecolor="#dddddd", handlelength=2.2, handleheight=1.6)

        fig.tight_layout(rect=[0, 0.09, 1, 1.0])
        fig.savefig(OUT_FILE,   dpi=180, bbox_inches="tight", facecolor="white")
        fig.savefig(PAPER_FILE, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)

    print(f"\nSaved: {OUT_FILE}")
    print(f"Saved: {PAPER_FILE}")


if __name__ == "__main__":
    main()
