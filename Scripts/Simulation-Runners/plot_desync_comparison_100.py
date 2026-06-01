"""
plot_desync_comparison_100.py
Generate the desync recovery comparison bar chart from 100-node simulation results.

2 bars per scheme, 4 bars total:
  Base Normal     = Enrollment + Round 1 energy (clean path)
  Base Recovery   = Enrollment + Round 1 + Round 2 + Round 3 energy
  Proposed Normal = same (clean path, lower cost)
  Proposed Rec.   = same (recovery via PID_old, much lower than Base Recovery)

Data sources:
  Base-Scheme/Simulation-Results/Desync-100/csv/bar_summary.csv
  Revised-Anonymity/Simulation-Results/Desync-100/csv/bar_summary.csv

Usage:
  python3 plot_desync_comparison_100.py
  python3 plot_desync_comparison_100.py --out myplot.png
  python3 plot_desync_comparison_100.py --raw   # use raw per-seed CSVs
"""

import os, csv, sys, argparse, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

SCHEMES = {
    "Base":     os.path.join(REPO, "Base-Scheme",       "Simulation-Results", "Desync-100", "csv"),
    "Proposed": os.path.join(REPO, "Revised-Anonymity", "Simulation-Results", "Desync-100", "csv"),
}

ROUND_KEYS = [
    "DESYNC_ENROLL_ENERGY",
    "DESYNC_ROUND1_ENERGY",
    "DESYNC_ROUND2_ENERGY",
    "DESYNC_ROUND3_ENERGY",
    "DESYNC_ROUND4_ENERGY",
]

OUT_DIR = os.path.join(REPO, "Results", "COOJA-Simulation", "Desync-Recovery-Analysis")

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def _avg(lst): return sum(lst) / len(lst) if lst else 0.0
def _std(lst):
    if len(lst) < 2: return 0.0
    a = _avg(lst)
    return math.sqrt(sum((x - a) ** 2 for x in lst) / len(lst))


def load_bar_summary(csv_dir):
    """Read bar_summary.csv produced by run_desync_comparison_100.py."""
    path = os.path.join(csv_dir, "bar_summary.csv")
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bar  = row["Bar"]
            mean = float(row["Avg_Energy_mJ"])
            std  = float(row["Std_Energy_mJ"])
            result[bar] = (mean, std)
    return result   # {"Normal": (mean_mJ, std_mJ), "Recovery": (mean_mJ, std_mJ)}


def load_from_raw(csv_dir):
    """
    Fallback: compute bar values from per-seed raw_seed*.csv files.
    Returns {"Normal": (mean_mJ, std_mJ), "Recovery": (mean_mJ, std_mJ)}.
    """
    import glob, re

    normal_keys   = ["ENROLL", "ROUND1"]
    recovery_keys = ["ENROLL", "ROUND1", "ROUND2", "ROUND3"]

    def _round_idx(name):
        # column header is like "ENROLL_energy_j", "ROUND1_energy_j", etc.
        for i, k in enumerate(["ENROLL","ROUND1","ROUND2","ROUND3","ROUND4"]):
            if k in name: return i
        return -1

    per_seed_normal, per_seed_recovery = [], []

    for seed_csv in sorted(glob.glob(os.path.join(csv_dir, "raw_seed*.csv"))):
        normal_devs, recovery_devs = [], []
        with open(seed_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    enroll = float(row["ENROLL_energy_j"])
                    r1     = float(row["ROUND1_energy_j"])
                    r2     = float(row["ROUND2_energy_j"])
                    r3     = float(row["ROUND3_energy_j"])
                except (KeyError, ValueError):
                    continue
                if any(math.isnan(v) for v in [enroll, r1, r2, r3]):
                    continue
                normal_devs.append((enroll + r1) * 1000)
                recovery_devs.append((enroll + r1 + r2 + r3) * 1000)
        if normal_devs:
            per_seed_normal.append(_avg(normal_devs))
        if recovery_devs:
            per_seed_recovery.append(_avg(recovery_devs))

    return {
        "Normal":   (_avg(per_seed_normal),   _std(per_seed_normal)),
        "Recovery": (_avg(per_seed_recovery), _std(per_seed_recovery)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Plotting
# ─────────────────────────────────────────────────────────────────────────────

def plot(data, out_path):
    """
    data: {scheme_name: {"Normal": (mean, std), "Recovery": (mean, std)}}
    """
    scheme_names = list(data.keys())     # ["Base", "Proposed"]
    bars         = ["Normal", "Recovery"]

    # x positions: one group per scheme, two bars per group
    n_schemes = len(scheme_names)
    n_bars    = len(bars)
    group_w   = 0.5
    bar_w     = group_w / n_bars * 0.9

    colors = {
        "Normal":   ("#2196F3", "#90CAF9"),   # (Base, Proposed) blue shades
        "Recovery": ("#F44336", "#FF8A80"),   # red shades
    }
    bar_colors = {
        "Base":     {"Normal": "#2196F3", "Recovery": "#F44336"},
        "Proposed": {"Normal": "#42A5F5", "Recovery": "#EF9A9A"},
    }
    hatches = {
        "Normal":   "",
        "Recovery": "//",
    }

    fig, ax = plt.subplots(figsize=(7, 4.5))

    x_groups = np.arange(n_schemes)
    offsets  = np.linspace(-group_w/2 + bar_w/2, group_w/2 - bar_w/2, n_bars)

    for b_idx, bar_name in enumerate(bars):
        means = [data[s][bar_name][0] for s in scheme_names]
        stds  = [data[s][bar_name][1] for s in scheme_names]
        clrs  = [bar_colors[s][bar_name] for s in scheme_names]
        xs    = x_groups + offsets[b_idx]
        rects = ax.bar(xs, means, bar_w,
                       yerr=stds, capsize=4,
                       color=clrs,
                       hatch=hatches[bar_name],
                       edgecolor="black", linewidth=0.7,
                       label=bar_name,
                       error_kw=dict(elinewidth=1.0, ecolor="black"))

        # Value labels on bars
        for rect, m in zip(rects, means):
            ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 0.5,
                    f"{m:.1f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x_groups)
    ax.set_xticklabels(scheme_names, fontsize=11)
    ax.set_ylabel("Per-device energy (mJ)", fontsize=11)
    ax.set_title("Desync Recovery Cost: Base vs Proposed\n"
                 "(100-node, 20 devices, 5 seeds, multi-hop RPL)", fontsize=11)
    ax.legend(title="Scenario", fontsize=9, title_fontsize=9)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # Annotate recovery overhead ratio
    for s_idx, scheme in enumerate(scheme_names):
        n_mean = data[scheme]["Normal"][0]
        r_mean = data[scheme]["Recovery"][0]
        if n_mean > 0:
            overhead = (r_mean / n_mean - 1) * 100
            ax.annotate(f"+{overhead:.0f}%",
                        xy=(x_groups[s_idx] + offsets[1], r_mean),
                        xytext=(0, 18), textcoords="offset points",
                        ha="center", fontsize=8, color="dimgray")

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {out_path}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plot desync comparison (100-node)")
    parser.add_argument("--out", default=None,
                        help="Output PNG path (default: Results/…/desync100_comparison.png)")
    parser.add_argument("--raw", action="store_true",
                        help="Load from raw per-seed CSVs instead of bar_summary.csv")
    args = parser.parse_args()

    out_path = args.out or os.path.join(OUT_DIR, "desync100_comparison.png")

    data = {}
    for scheme, csv_dir in SCHEMES.items():
        if not os.path.isdir(csv_dir):
            print(f"  WARNING: No results directory for {scheme}: {csv_dir}")
            continue
        try:
            if args.raw:
                d = load_from_raw(csv_dir)
            else:
                bar_csv = os.path.join(csv_dir, "bar_summary.csv")
                if os.path.isfile(bar_csv):
                    d = load_bar_summary(csv_dir)
                else:
                    print(f"  bar_summary.csv not found for {scheme}, falling back to raw")
                    d = load_from_raw(csv_dir)
            data[scheme] = d
            for bar, (mean, std) in d.items():
                print(f"  {scheme:10s} {bar:10s}: {mean:.2f} ± {std:.2f} mJ")
        except Exception as e:
            print(f"  ERROR loading {scheme}: {e}")

    if not data:
        print("No data loaded. Run run_desync_comparison_100.py first.")
        sys.exit(1)

    plot(data, out_path)


if __name__ == "__main__":
    main()
