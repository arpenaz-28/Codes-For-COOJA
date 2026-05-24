"""
plot_desync_proposed_vs_base.py
Two 4-bar charts comparing Proposed vs Base scheme across a desync event.

SCENARIO
--------
Phase 3 Key Exchange: AS sends (mH, ts2) to D.
If this packet is lost, D retains stale m_curr and cannot update its PID.

Before-loss session  = Enrollment + Authentication + Key Exchange
After-loss session:
  Proposed — dual-state (m_curr, m_old, PID_curr, PID_old): D presents PID_old,
             AS recognises it and re-runs Phase 3. No re-enrolment.
             After-loss cost = Authentication + Key Exchange only.
  Base     — stores only m_curr; nonce mismatch → auth rejected → forced re-enrol.
             After-loss cost = Enrollment + Authentication + Key Exchange.

OUTPUTS → Results/Desync-Recovery-Analysis/
  01_energy_before_after.png   — 4-bar energy chart
  02_cpu_before_after.png      — 4-bar CPU time chart
"""

import os, csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

REPO    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
SRC_CSV = os.path.join(REPO, "Results", "Charts",
                       "Revised-vs-LAAKA-vs-Zhou", "comparison_summary.csv")
OUT_DIR = os.path.join(REPO, "Results", "Desync-Recovery-Analysis")
os.makedirs(OUT_DIR, exist_ok=True)

STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    14,
    "axes.titleweight":  "bold",
    "axes.labelsize":    13,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.labelsize":   12,
    "ytick.labelsize":   12,
    "xtick.major.size":  0,
    "legend.fontsize":   11,
    "legend.framealpha": 0.92,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

C_ENROLL = "#5BA4CF"
C_AUTH   = "#F4A261"
C_KEYEX  = "#2A9D8F"


def load():
    data = {}
    with open(SRC_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = ("Proposed" if row["Scheme"] == "Revised-Anonymity" else
                   "Base"     if row["Scheme"] == "LAAKA"             else None)
            if key is None:
                continue
            data.setdefault(key, {})[row["Phase"]] = {
                "e":    float(row["Avg_Energy_mJ"]),
                "ci_e": float(row["CI95_Energy_mJ"]),
                "c":    float(row["Avg_CPU_s"]),
                "ci_c": float(row["CI95_CPU_s"]),
            }
    return data


def make_chart(data, metric, ylabel, title, filename):
    """
    4-bar grouped chart:
      Group 1 — Proposed: [Before | After]
      Group 2 — Base:     [Before | After]

    Each bar is phase-stacked: Enrollment / Authentication / Key Exchange.
    Before = Enrol + Auth + KeyEx  (same for both schemes).
    After  = Proposed: Auth + KeyEx  |  Base: Enrol + Auth + KeyEx.
    """
    ci_key = "ci_e" if metric == "e" else "ci_c"

    # Proposed
    p_en = data["Proposed"]["Enrollment"][metric]
    p_au = data["Proposed"]["Authentication"][metric]
    p_kx = data["Proposed"]["Key Exchange"][metric]
    p_ak = data["Proposed"]["Auth+KeyEx"][metric]
    p_ci_b = math.sqrt(data["Proposed"]["Enrollment"][ci_key]**2 +
                       data["Proposed"]["Auth+KeyEx"][ci_key]**2)
    p_ci_a = data["Proposed"]["Auth+KeyEx"][ci_key]

    # Base
    b_en = data["Base"]["Enrollment"][metric]
    b_au = data["Base"]["Authentication"][metric]
    b_kx = data["Base"]["Key Exchange"][metric]
    b_ak = data["Base"]["Auth+KeyEx"][metric]
    b_ci_b = math.sqrt(data["Base"]["Enrollment"][ci_key]**2 +
                       data["Base"]["Auth+KeyEx"][ci_key]**2)
    b_ci_a = math.sqrt(data["Base"]["Enrollment"][ci_key]**2 +
                       data["Base"]["Auth+KeyEx"][ci_key]**2)

    # Bar positions: 4 bars with a gap between the two groups
    # Proposed-Before=0, Proposed-After=1, gap, Base-Before=2.6, Base-After=3.6
    pos = [0, 1, 2.6, 3.6]
    w   = 0.7

    # Stacked values for each bar
    #           P-Before        P-After      B-Before      B-After
    enroll_v = [p_en,           0,           b_en,         b_en]
    auth_v   = [p_au,           p_au,        b_au,         b_au]
    keyex_v  = [p_kx,           p_kx,        b_kx,         b_kx]
    totals   = [p_en+p_ak,      p_ak,        b_en+b_ak,    b_en+b_ak]
    cis      = [p_ci_b,         p_ci_a,      b_ci_b,       b_ci_a]

    xlabels = [
        "Proposed\nBefore loss",
        "Proposed\nAfter loss",
        "Base\nBefore loss",
        "Base\nAfter loss",
    ]

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor("white")

        for i in range(4):
            ev, av, kv = enroll_v[i], auth_v[i], keyex_v[i]
            ci, tot = cis[i], totals[i]
            alpha = 0.88

            ax.bar(pos[i], ev, w, color=C_ENROLL, alpha=alpha,
                   edgecolor="white", linewidth=0.8)
            ax.bar(pos[i], av, w, bottom=ev, color=C_AUTH, alpha=alpha,
                   edgecolor="white", linewidth=0.8)
            ax.bar(pos[i], kv, w, bottom=ev + av, color=C_KEYEX, alpha=alpha,
                   edgecolor="white", linewidth=0.8,
                   yerr=ci, capsize=5,
                   error_kw={"linewidth": 1.3, "ecolor": "#555"})

            fmt = ".1f" if metric == "e" else ".3f"
            ax.text(pos[i], tot + ci + (max(totals)*0.015),
                    f"{tot:{fmt}}",
                    ha="center", va="bottom", fontsize=12, fontweight="bold")

        # Group labels underneath
        ax.text(0.5,  -max(totals)*0.10, "Proposed (with recovery)",
                ha="center", fontsize=12, color="#2C6FAC", fontweight="bold")
        ax.text(3.1, -max(totals)*0.10, "Base scheme (no recovery)",
                ha="center", fontsize=12, color="#B85C2C", fontweight="bold")

        # Bracket lines above each pair
        def bracket(x1, x2, y, label, color):
            pad = max(totals) * 0.03
            ax.plot([x1, x1, x2, x2], [y+pad, y+2*pad, y+2*pad, y+pad],
                    color=color, lw=1.2)
            ax.text((x1+x2)/2, y+2.5*pad, label,
                    ha="center", va="bottom", fontsize=10, color=color)

        bracket(pos[0], pos[1], max(totals[0], totals[1]),
                "Proposed", "#2C6FAC")
        bracket(pos[2], pos[3], max(totals[2], totals[3]),
                "Base", "#B85C2C")

        ax.set_xticks(pos)
        ax.set_xticklabels(xlabels, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=13, fontweight="bold")
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.set_ylim(bottom=-max(totals)*0.14)

        legend_handles = [
            mpatches.Patch(color=C_ENROLL, alpha=0.88, label="Enrollment"),
            mpatches.Patch(color=C_AUTH,   alpha=0.88, label="Authentication"),
            mpatches.Patch(color=C_KEYEX,  alpha=0.88, label="Key Exchange"),
        ]
        ax.legend(handles=legend_handles, loc="upper right", fontsize=11)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, filename)
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: {filename}")


def main():
    data = load()

    fmt = ".2f"
    p_before = data["Proposed"]["Enrollment"]["e"] + data["Proposed"]["Auth+KeyEx"]["e"]
    p_after  = data["Proposed"]["Auth+KeyEx"]["e"]
    b_before = data["Base"]["Enrollment"]["e"] + data["Base"]["Auth+KeyEx"]["e"]
    b_after  = data["Base"]["Enrollment"]["e"] + data["Base"]["Auth+KeyEx"]["e"]
    print(f"Proposed before={p_before:.2f} mJ  after={p_after:.2f} mJ")
    print(f"Base     before={b_before:.2f} mJ  after={b_after:.2f} mJ")

    make_chart(
        data, "e",
        "Avg Energy per Device (mJ)",
        "Energy Cost: Before vs After (mH, ts2) Loss in Phase 3\n"
        "Proposed (dual-state recovery) vs Base scheme (forced re-enrolment)",
        "01_energy_before_after.png",
    )

    make_chart(
        data, "c",
        "Avg CPU Time per Device (s)",
        "CPU Time: Before vs After (mH, ts2) Loss in Phase 3\n"
        "Proposed (dual-state recovery) vs Base scheme (forced re-enrolment)",
        "02_cpu_before_after.png",
    )

    print(f"\nAll outputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
