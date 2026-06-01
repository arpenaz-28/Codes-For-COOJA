"""
plot_desync_phases_100.py
Three-phase grouped bar chart for the desync recovery comparison (100-node).

X-axis phases (2 bars each — Base vs Proposed):
  1. Enrollment
  2. Auth+KeyEx (Normal)   — clean session, no desync
  3. Auth+KeyEx (Recovery) — Base: re-enrol+retry; Proposed: PID_old re-auth

Each bar = mean of 20 devices × 5 seeds.

Data source: summary.csv from run_desync_comparison_100.py
"""

import os, csv, sys, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

SCHEME_CSV = {
    "Base":     os.path.join(REPO, "Base-Scheme",       "Simulation-Results", "Desync-100", "csv", "summary.csv"),
    "Proposed": os.path.join(REPO, "Revised-Anonymity", "Simulation-Results", "Desync-100", "csv", "summary.csv"),
}

OUT_PATH = os.path.join(
    REPO, "Results", "COOJA-Simulation", "Desync-Recovery-Analysis",
    "desync100_phases.png"
)

# summary.csv round-label → phase display name
PHASE_MAP = {
    "Enrollment": "Enrollment",
    "Round 1":    "Auth+KeyEx\n(Normal)",
    "Round 3":    "Auth+KeyEx\n(Recovery)",
}

SCHEME_COLORS = {
    "Base":     "#1565C0",   # dark blue
    "Proposed": "#42A5F5",   # lighter blue
}
SCHEME_HATCHES = {
    "Base":     "",
    "Proposed": "//",
}

# ─────────────────────────────────────────────────────────────────────────────

def _avg(lst): return sum(lst) / len(lst) if lst else 0.0
def _std(lst):
    if len(lst) < 2: return 0.0
    a = _avg(lst)
    return math.sqrt(sum((x - a) ** 2 for x in lst) / len(lst))


def load_summary(path):
    """Return {round_label: (avg_energy_mJ, std_energy_mJ)}."""
    data = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            data[row["Round"]] = (float(row["Avg_Energy_mJ"]), float(row["Std_Energy_mJ"]))
    return data


def main():
    # Load data for each scheme
    scheme_data = {}
    for scheme, path in SCHEME_CSV.items():
        if not os.path.isfile(path):
            print(f"Missing: {path}")
            sys.exit(1)
        raw = load_summary(path)
        scheme_data[scheme] = {
            phase_label: raw[csv_label]
            for csv_label, phase_label in PHASE_MAP.items()
            if csv_label in raw
        }

    # Print table
    phases = list(PHASE_MAP.values())
    schemes = list(SCHEME_CSV.keys())
    print(f"\n{'Phase':<26} {'Base (mJ)':>18} {'Proposed (mJ)':>18}")
    print("-" * 64)
    for ph in phases:
        b = scheme_data["Base"][ph]
        p = scheme_data["Proposed"][ph]
        print(f"{ph.replace(chr(10),' '):<26}  {b[0]:>7.1f} ± {b[1]:>6.1f}    {p[0]:>7.1f} ± {p[1]:>6.1f}")

    # ── broken-axis plot: top panel = Enrollment, bottom panel = Auth phases ──
    # Enrollment ~2765–2947 mJ; Auth phases ~62–135 mJ — ratio ~22:1.
    # Use a 2-row subplot with a break indicator between them.

    n_schemes = len(schemes)
    group_w   = 0.50
    bar_w     = group_w / n_schemes * 0.88
    offsets   = np.linspace(-group_w / 2 + bar_w / 2,
                             group_w / 2 - bar_w / 2, n_schemes)

    # Axis limits
    ENROLL_YMIN, ENROLL_YMAX = 2400, 3400   # top panel  (Enrollment)
    AUTH_YMIN,   AUTH_YMAX   =    0,  200   # bottom panel (Auth phases)

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1,
        figsize=(8, 6),
        gridspec_kw={"height_ratios": [1.6, 2.4], "hspace": 0.08},
    )

    # ── helper: draw bars on a given ax for a given phase subset ──
    def _draw_bars(ax, phase_indices, x_positions):
        handles = []
        for s_idx, scheme in enumerate(schemes):
            bars_list = []
            for i, ph_idx in enumerate(phase_indices):
                ph   = phases[ph_idx]
                mean = scheme_data[scheme][ph][0]
                std  = scheme_data[scheme][ph][1]
                xpos = x_positions[i] + offsets[s_idx]
                bar  = ax.bar(
                    xpos, mean, bar_w,
                    yerr=std, capsize=4,
                    color=SCHEME_COLORS[scheme],
                    hatch=SCHEME_HATCHES[scheme],
                    edgecolor="black", linewidth=0.8,
                    label=scheme if i == 0 else "_nolegend_",
                    error_kw=dict(elinewidth=1.1, ecolor="black"),
                )
                bars_list.append((bar, mean, std))
            handles.append(bars_list[0][0])

            # value labels
            for bar, mean, std in bars_list:
                for rect in bar:
                    ax.text(
                        rect.get_x() + rect.get_width() / 2,
                        rect.get_height() + std * 0.05 + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.015,
                        f"{mean:.1f}",
                        ha="center", va="bottom", fontsize=9, fontweight="bold",
                    )
        return handles

    # ── top panel: Enrollment only ─────────────────────────────────────────
    x_enroll = np.array([0])
    _draw_bars(ax_top, [0], x_enroll)
    ax_top.set_ylim(ENROLL_YMIN, ENROLL_YMAX)
    ax_top.set_xlim(-0.55, 0.55)
    ax_top.set_xticks([])
    ax_top.set_ylabel("Energy (mJ)", fontsize=10, labelpad=4)
    ax_top.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax_top.set_axisbelow(True)
    ax_top.spines["bottom"].set_visible(False)
    ax_top.tick_params(bottom=False)
    # Phase label as x-axis annotation in axes coords (bottom, no overlap with bars)
    ax_top.annotate("Enrollment", xy=(0.5, 0), xycoords="axes fraction",
                    xytext=(0, -4), textcoords="offset points",
                    ha="center", va="top", fontsize=11, fontweight="bold", color="#333333")

    # Percentage annotation: above the SHORTER bar (Proposed at 2765)
    b0 = scheme_data["Base"][phases[0]][0]
    p0 = scheme_data["Proposed"][phases[0]][0]
    b0_std = scheme_data["Base"][phases[0]][1]
    d0 = (p0 / b0 - 1) * 100
    ax_top.annotate(
        f"Proposed {d0:+.1f}%",
        xy=(offsets[1], p0 + b0_std + 10),
        ha="center", va="bottom", fontsize=9, color="seagreen", fontweight="bold",
    )
    ax_top.set_title(
        "Desync Recovery — Phase-by-Phase Energy: Base vs Proposed\n"
        "(100-node network, 20 devices, 5 seeds, multi-hop RPL, COOJA/TelosB)",
        fontsize=11, pad=8,
    )

    # ── bottom panel: Auth+KeyEx (Normal) + Auth+KeyEx (Recovery) ──────────
    x_auth = np.array([0, 1])
    handles = _draw_bars(ax_bot, [1, 2], x_auth)
    ax_bot.set_ylim(AUTH_YMIN, AUTH_YMAX)
    ax_bot.set_xlim(-0.55, 1.55)
    ax_bot.set_xticks(x_auth)
    ax_bot.set_xticklabels(
        [phases[1], phases[2]], fontsize=11,
    )
    ax_bot.set_ylabel("Energy (mJ)", fontsize=10, labelpad=4)
    ax_bot.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bot.set_axisbelow(True)
    ax_bot.spines["top"].set_visible(False)
    ax_bot.legend(handles=handles, labels=schemes, fontsize=10, framealpha=0.9,
                  loc="upper right")

    # Percentage annotations on bottom panel — anchored above the TALLER bar
    for i, ph_idx in enumerate([1, 2]):
        b = scheme_data["Base"][phases[ph_idx]][0]
        p = scheme_data["Proposed"][phases[ph_idx]][0]
        b_std = scheme_data["Base"][phases[ph_idx]][1]
        p_std = scheme_data["Proposed"][phases[ph_idx]][1]
        d = (p / b - 1) * 100
        sign = "+" if d > 0 else ""
        color = "crimson" if d > 5 else "seagreen"
        # anchor at the taller bar's tip + error bar
        if b >= p:
            xpos = x_auth[i] + offsets[0]   # Base bar centre
            ypos = b + b_std + 8
        else:
            xpos = x_auth[i] + offsets[1]   # Proposed bar centre
            ypos = p + p_std + 8
        ax_bot.text(xpos, ypos,
                    f"Proposed {sign}{d:.1f}%",
                    ha="center", va="bottom", fontsize=9, color=color, fontweight="bold")

    # ── break diagonal lines ───────────────────────────────────────────────
    d = 0.012
    kw = dict(transform=fig.transFigure, color="black", clip_on=False, linewidth=1.2)
    # find approximate figure coordinates of the break
    pos_top = ax_top.get_position()
    pos_bot = ax_bot.get_position()
    y_break = (pos_top.y0 + pos_bot.y1) / 2
    for xf in [pos_top.x0 + 0.01, pos_top.x1 - 0.01]:
        fig.lines.extend([
            plt.Line2D([xf - d, xf + d], [y_break - d * 1.5, y_break + d * 1.5], **kw),
        ])

    # shared y-label
    fig.text(0.01, 0.5,
             "Per-device energy (mJ)\n[mean of 20 devices, 5 seeds]",
             va="center", ha="center", rotation="vertical", fontsize=10)

    plt.tight_layout(rect=[0.06, 0, 1, 1])
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"\nSaved: {OUT_PATH}")
    plt.close()


if __name__ == "__main__":
    main()
