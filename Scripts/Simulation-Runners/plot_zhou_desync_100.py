"""
plot_zhou_desync_100.py
Plot Zhou Scenario A desync results, with optional comparison against
Base (DAuth) and Proposed schemes from the desync comparison study.

Usage:
  python3 plot_zhou_desync_100.py              # Zhou only
  python3 plot_zhou_desync_100.py --compare    # Zhou + Base + Proposed (3-scheme bar)

Output charts:
  Zhou-Scheme/Simulation-Results/Desync-100/charts/
    zhou_desync_bars.png        — Normal vs Recovery for Zhou
    zhou_desync_compare.png     — Recovery comparison across all 3 schemes (--compare)
"""

import os
import csv
import argparse
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

ZHOU_BAR   = os.path.join(REPO, "Zhou-Scheme",       "Simulation-Results", "Desync-100", "csv", "bar_summary.csv")
BASE_BAR   = os.path.join(REPO, "Base-Scheme",        "Simulation-Results", "Desync-100", "csv", "bar_summary.csv")
PROP_BAR   = os.path.join(REPO, "Revised-Anonymity",  "Simulation-Results", "Desync-100", "csv", "bar_summary.csv")

CHART_DIR = os.path.join(REPO, "Zhou-Scheme", "Simulation-Results", "Desync-100", "charts")

# ─────────────────────────────────────────────────────────────────────────────
# Colour palette (consistent with run_desync_comparison_100 / paper charts)
# ─────────────────────────────────────────────────────────────────────────────
C_ZHOU     = "#D55E00"   # vermilion  — Zhou
C_BASE     = "#7E5BA6"   # purple     — Base / DAuth
C_PROPOSED = "#0072B2"   # blue       — Proposed

C_NORMAL   = "#56B4E9"   # sky-blue   — Normal bar
C_RECOVERY = "#E69F00"   # gold       — Recovery bar

# ─────────────────────────────────────────────────────────────────────────────
# CSV reader
# ─────────────────────────────────────────────────────────────────────────────

def read_bar_csv(path):
    """Return {'Normal': (energy_mJ, std_mJ), 'Recovery': (energy_mJ, std_mJ)}."""
    if not os.path.isfile(path):
        return None
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label    = row["Bar"].strip()
            energy   = float(row["Avg_Energy_mJ"])
            std      = float(row["Std_Energy_mJ"])
            rows[label] = (energy, std)
    return rows if rows else None


# ─────────────────────────────────────────────────────────────────────────────
# Plot 1: Zhou Normal vs Recovery (single-scheme bar chart)
# ─────────────────────────────────────────────────────────────────────────────

def plot_zhou_bars(zhou):
    os.makedirs(CHART_DIR, exist_ok=True)

    normal_e,   normal_s   = zhou.get("Normal",   (0, 0))
    recovery_e, recovery_s = zhou.get("Recovery", (0, 0))

    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    x      = np.array([0, 1])
    values = [normal_e, recovery_e]
    errs   = [normal_s, recovery_s]
    colors = [C_NORMAL, C_RECOVERY]

    bars = ax.bar(x, values, yerr=errs, width=0.55,
                  color=colors, capsize=6, edgecolor="white", linewidth=1.2,
                  error_kw={"elinewidth": 1.5, "ecolor": "#333333"})

    # Value labels
    for bar, val, err in zip(bars, values, errs):
        ax.text(bar.get_x() + bar.get_width() / 2,
                val + err + max(values) * 0.015,
                f"{val:.2f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    # Recovery overhead annotation
    if normal_e > 0:
        overhead = (recovery_e - normal_e) / normal_e * 100
        ax.annotate(f"+{overhead:.1f}%\noverhead",
                    xy=(1, recovery_e),
                    xytext=(1.35, recovery_e * 0.85),
                    fontsize=9.5, color="#AA3311",
                    arrowprops=dict(arrowstyle="->", color="#AA3311", lw=1.2))

    ax.set_xticks(x)
    ax.set_xticklabels(["Normal\n(Enroll + R1)", "Recovery\n(Enroll + R1 + R2 + R3)"],
                       fontsize=11)
    ax.set_ylabel("Per-user total energy (mJ)", fontsize=11)
    ax.set_title("Zhou Desync Demo — Scenario A (M3-loss)\n100-node COOJA, 20 users",
                 fontsize=11, pad=8)
    ax.set_ylim(0, max(recovery_e + recovery_s, normal_e + normal_s) * 1.25)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_patches = [
        mpatches.Patch(color=C_NORMAL,   label="Normal (no desync)"),
        mpatches.Patch(color=C_RECOVERY, label="Recovery (re-enroll required)"),
    ]
    ax.legend(handles=legend_patches, fontsize=9.5, loc="upper left")

    fig.tight_layout()
    out = os.path.join(CHART_DIR, "zhou_desync_bars.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Plot 2: Recovery comparison — Zhou vs Base vs Proposed
# ─────────────────────────────────────────────────────────────────────────────

def plot_compare(zhou, base, proposed):
    os.makedirs(CHART_DIR, exist_ok=True)

    schemes = []
    if zhou     and "Recovery" in zhou:     schemes.append(("Zhou",     *zhou["Recovery"],     C_ZHOU))
    if base     and "Recovery" in base:     schemes.append(("DAuth\n(Base)", *base["Recovery"], C_BASE))
    if proposed and "Recovery" in proposed: schemes.append(("Proposed", *proposed["Recovery"], C_PROPOSED))

    if not schemes:
        print("  No recovery data available for comparison chart.")
        return

    labels  = [s[0] for s in schemes]
    values  = [s[1] for s in schemes]
    errs    = [s[2] for s in schemes]
    colors  = [s[3] for s in schemes]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    x = np.arange(len(schemes))
    bars = ax.bar(x, values, yerr=errs, width=0.55,
                  color=colors, capsize=6, edgecolor="white", linewidth=1.2,
                  error_kw={"elinewidth": 1.5, "ecolor": "#333333"})

    max_val = max(values)
    for bar, val, err in zip(bars, values, errs):
        ax.text(bar.get_x() + bar.get_width() / 2,
                val + err + max_val * 0.015,
                f"{val:.2f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Per-user recovery energy (mJ)", fontsize=11)
    ax.set_title("Desync Recovery Cost Comparison\n(Enroll + R1 + R2 + R3), 100-node COOJA",
                 fontsize=11, pad=8)
    ax.set_ylim(0, max_val * 1.3)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Highlight Proposed as lowest
    if proposed and "Recovery" in proposed:
        prop_val = proposed["Recovery"][0]
        ax.axhline(prop_val, color=C_PROPOSED, linestyle="--", linewidth=1.2, alpha=0.7)

    fig.tight_layout()
    out = os.path.join(CHART_DIR, "zhou_desync_compare.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plot Zhou desync demo results")
    parser.add_argument("--compare", action="store_true",
                        help="Also plot comparison against Base/Proposed schemes")
    args = parser.parse_args()

    print("Zhou Desync Demo Plotter")

    zhou = read_bar_csv(ZHOU_BAR)
    if not zhou:
        print(f"  ERROR: Zhou bar summary not found: {ZHOU_BAR}")
        print("  Run run_zhou_desync_100.py first.")
        return

    print(f"  Zhou:  Normal={zhou.get('Normal', ('n/a',))[0]:.2f} mJ  "
          f"Recovery={zhou.get('Recovery', ('n/a',))[0]:.2f} mJ")

    plot_zhou_bars(zhou)

    if args.compare:
        base     = read_bar_csv(BASE_BAR)
        proposed = read_bar_csv(PROP_BAR)

        if base:
            print(f"  Base:     Recovery={base.get('Recovery', ('n/a',))[0]:.2f} mJ")
        else:
            print(f"  Base bar summary not found: {BASE_BAR}")

        if proposed:
            print(f"  Proposed: Recovery={proposed.get('Recovery', ('n/a',))[0]:.2f} mJ")
        else:
            print(f"  Proposed bar summary not found: {PROP_BAR}")

        plot_compare(zhou, base, proposed)

        if base and proposed:
            zr = zhou.get("Recovery", (0, 0))[0]
            br = base.get("Recovery", (0, 0))[0]
            pr = proposed.get("Recovery", (0, 0))[0]
            if pr > 0:
                print(f"\n  Recovery overhead vs Proposed:")
                print(f"    Zhou:  {zr:.2f} mJ  (+{(zr-pr)/pr*100:.1f}% vs Proposed)")
                print(f"    Base:  {br:.2f} mJ  (+{(br-pr)/pr*100:.1f}% vs Proposed)")
                print(f"    Proposed: {pr:.2f} mJ  (baseline)")


if __name__ == "__main__":
    main()
