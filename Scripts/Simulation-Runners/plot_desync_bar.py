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
    "font.size":         26,
    "axes.titlesize":    30,
    "axes.titleweight":  "bold",
    "axes.labelsize":    30,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.9,
    "xtick.labelsize":   28,
    "ytick.labelsize":   26,
    "xtick.major.size":  0,
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

SCHEMES   = ["DAuth", "Proposed"]
BAR_TYPES = ["Recovery"]

# Single bar per scheme: Round 3 — recovery round cost (per device).
#   DAuth:    failed auth + full re-enrolment to AS + retry auth + keyex
#   Proposed: direct recovery via PID_old (no re-enrolment)
#   Zhou:     failed auth + full re-registration to GW + retry auth
BAR_ROUNDS = {
    "Recovery": ["Round 3"],
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
def draw_panel(ax, stats, ylabel, fmt):
    """
    stats: [(scheme, "Recovery", mean, ci), ...]
    One bar per scheme — the per-device recovery-round cost.
    """
    n_schemes = len(SCHEMES)
    bar_w     = 0.55

    max_val = max(mean + ci for _, _, mean, ci in stats)

    for s_idx, scheme in enumerate(SCHEMES):
        entry = next(e for e in stats if e[0] == scheme)
        _, _, mean, ci = entry
        ax.bar(s_idx, mean, bar_w,
               facecolor="none",
               edgecolor=SCHEME_COLORS[scheme],
               hatch="xxx",
               linewidth=2.2,
               zorder=3)
        ax.text(s_idx, mean + max_val * 0.02, fmt.format(mean),
                ha="center", va="bottom", fontsize=22, fontweight="bold",
                color=SCHEME_COLORS[scheme])

    ax.set_xticks(range(n_schemes))
    ax.set_xticklabels(SCHEMES, fontsize=28, ha="center")
    ax.set_ylabel(ylabel, labelpad=20, fontsize=30, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, max_val * 1.22)
    ax.set_xlim(-0.7, n_schemes - 0.3)


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

        draw_panel(ax_e, e_stats, "Avg. Energy (mJ)", "{:.1f}")
        draw_panel(ax_c, c_stats, "Avg. CPU Time (s)", "{:.2f}")
        ax_e.set_xlabel("(a)", fontsize=30, fontweight="bold")
        ax_c.set_xlabel("(b)", fontsize=30, fontweight="bold")

        fig.tight_layout(rect=[0, 0.02, 1, 1.0])
        fig.savefig(OUT_FILE,   dpi=180, bbox_inches="tight", facecolor="white")
        fig.savefig(PAPER_FILE, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)

    print(f"\nSaved: {OUT_FILE}")
    print(f"Saved: {PAPER_FILE}")


if __name__ == "__main__":
    main()
