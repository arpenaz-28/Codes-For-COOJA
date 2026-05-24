"""
plot_desync_recovery_comparison.py
Visualise the cost advantage of the dual-state desynchronisation recovery
mechanism in the Proposed scheme vs LAAKA and Zhou (which have no recovery).

MEASUREMENT LOGIC
-----------------
After a successful Phase 1 (Enrollment) + Phase 2/3 (Auth+KeyEx) cycle,
suppose the Phase 3 delivery to the device is lost (one packet drop).

• Proposed (with desync recovery)
    AS stores (m_curr, m_old, PID_curr, PID_old).
    On the next auth attempt the device presents PID_old; AS recognises it
    via the dual-state lookup and completes authentication normally.
    → Next-cycle cost = Auth + KeyEx  (SAME as the no-loss path)
    → Recovery overhead = 0

• LAAKA / Zhou (no desync recovery)
    AS has already advanced to the new nonce; the old PID is unknown to it.
    Authentication is rejected.  The device must RE-ENROL before it can
    authenticate again.
    → Next-cycle cost = Re-Enrollment + Auth + KeyEx
    → Recovery overhead = Enrollment cost

All numbers come from the 5-seed, 20-device, 100-node COOJA simulation
stored in Results/Charts/Revised-vs-LAAKA-vs-Zhou/comparison_summary.csv.

OUTPUTS
-------
  01_desync_recovery_stacked.png   — grouped+stacked bars (Normal vs After-Loss)
  02_desync_recovery_overhead.png  — extra energy/CPU incurred by the loss event
  03_desync_recovery_cycles.png    — cumulative cost over multiple auth cycles
  desync_recovery_summary.csv      — numerical summary table
"""

import os, csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
REPO     = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
DATA_CSV = os.path.join(REPO, "Results", "Charts",
                        "Revised-vs-LAAKA-vs-Zhou", "comparison_summary.csv")
OUT_DIR  = os.path.join(REPO, "Results", "Desync-Recovery-Analysis")

_CHART_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    15,
    "axes.titleweight":  "bold",
    "axes.labelsize":    14,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   12,
    "ytick.labelsize":   12,
    "xtick.major.size":  0,
    "legend.fontsize":   11,
    "legend.framealpha": 0.92,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

# Phase colour palette
COL_ENROLL = "#90CAF9"   # light blue
COL_AUTH   = "#FFB74D"   # amber
COL_KEYEX  = "#A5D6A7"   # green
COL_EXTRA  = "#EF9A9A"   # soft red  — marks the "penalty" bar segment

SCHEME_COLORS = {
    "Proposed": "#2C6FAC",
    "LAAKA":    "#B85C2C",
    "Zhou":     "#3A7D44",
}

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
def load_data():
    raw = {}
    with open(DATA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s = row["Scheme"].replace("Revised-Anonymity", "Proposed")
            p = row["Phase"]
            raw.setdefault(s, {})[p] = {
                "energy": float(row["Avg_Energy_mJ"]),
                "ci_e":   float(row["CI95_Energy_mJ"]),
                "cpu":    float(row["Avg_CPU_s"]),
                "ci_c":   float(row["CI95_CPU_s"]),
            }
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# Chart 1 — Stacked grouped bars: Normal path vs After-Phase3-Loss path
# ─────────────────────────────────────────────────────────────────────────────
def chart_stacked(data, show=False):
    """
    Two bars per scheme:
      Left  (Normal)    : Auth + KeyEx only
      Right (After Loss): Re-Enrollment + Auth + KeyEx  (LAAKA/Zhou)
                          Auth + KeyEx only              (Proposed — same as normal)
    """
    schemes = ["Proposed", "LAAKA", "Zhou"]
    labels  = ["Proposed\n(w/ desync\nrecovery)", "LAAKA\n(no recovery)", "Zhou\n(no recovery)"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharey=False)

    for ax_idx, (metric, unit, ci_key) in enumerate(
            [("energy", "mJ", "ci_e"), ("cpu", "s", "ci_c")]):

        ax = axes[ax_idx]
        x  = np.arange(len(schemes))
        w  = 0.32

        with plt.rc_context(_CHART_STYLE):
            for si, scheme in enumerate(schemes):
                d   = data[scheme]
                enr = d.get("Enrollment",  {"energy": 0, "cpu": 0, "ci_e": 0, "ci_c": 0})
                auth = d.get("Authentication", {"energy": 0, "cpu": 0, "ci_e": 0, "ci_c": 0})
                kex  = d.get("Key Exchange",   {"energy": 0, "cpu": 0, "ci_e": 0, "ci_c": 0})
                # Zhou has no separate KeyEx
                auth_kex = d.get("Auth+KeyEx", {metric: auth[metric] + kex[metric]})

                # --- Normal bar (left) ---
                normal_val = auth[metric] + kex[metric]
                # Zhou uses combined Auth+KeyEx
                if scheme == "Zhou":
                    normal_val = auth_kex[metric]

                ax.bar(x[si] - w / 2, auth[metric] if scheme != "Zhou" else auth_kex[metric],
                       w, color=COL_AUTH, edgecolor="white", linewidth=0.6, zorder=3)
                if scheme != "Zhou" and kex[metric] > 0:
                    ax.bar(x[si] - w / 2, kex[metric], w,
                           bottom=auth[metric],
                           color=COL_KEYEX, edgecolor="white", linewidth=0.6, zorder=3)

                # --- After-Loss bar (right) ---
                if scheme == "Proposed":
                    # Desync recovery: identical to normal path — re-use same segments
                    ax.bar(x[si] + w / 2, auth[metric], w,
                           color=COL_AUTH, edgecolor="white", linewidth=0.6, zorder=3)
                    ax.bar(x[si] + w / 2, kex[metric], w,
                           bottom=auth[metric],
                           color=COL_KEYEX, edgecolor="white", linewidth=0.6, zorder=3)
                else:
                    # No recovery: must re-enrol first (shown in red), then auth again
                    ax.bar(x[si] + w / 2, enr[metric], w,
                           color=COL_EXTRA, edgecolor="white", linewidth=0.6, zorder=3,
                           label="_nolegend_")
                    base = enr[metric]
                    if scheme == "Zhou":
                        ax.bar(x[si] + w / 2, auth_kex[metric], w,
                               bottom=base,
                               color=COL_AUTH, edgecolor="white", linewidth=0.6, zorder=3)
                    else:
                        ax.bar(x[si] + w / 2, auth[metric], w,
                               bottom=base,
                               color=COL_AUTH, edgecolor="white", linewidth=0.6, zorder=3)
                        ax.bar(x[si] + w / 2, kex[metric], w,
                               bottom=base + auth[metric],
                               color=COL_KEYEX, edgecolor="white", linewidth=0.6, zorder=3)
                    # Overhead label
                    total_loss = enr[metric] + (auth_kex[metric] if scheme == "Zhou"
                                                else auth[metric] + kex[metric])
                    overhead_pct = (enr[metric] /
                                    (auth_kex[metric] if scheme == "Zhou"
                                     else auth[metric] + kex[metric])) * 100
                    ax.text(x[si] + w / 2, total_loss + (ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 5) * 0.01,
                            f"+{overhead_pct:.0f}%",
                            ha="center", va="bottom", fontsize=10,
                            color="#C62828", fontweight="bold")

        # x-axis labels — two ticks per scheme group
        tick_pos  = np.concatenate([x - w/2, x + w/2])
        tick_labs = ([f"{l}\nNormal" for l in labels] +
                     [f"{l}\nAfter Loss" for l in labels])
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_labs, fontsize=9)

        ylabel = ("Energy per Device (mJ)" if metric == "energy"
                  else "CPU Time per Device (s)")
        ax.set_ylabel(ylabel, fontsize=13, fontweight="bold")
        title  = ("Energy Cost: Normal vs. After Phase 3 Packet Loss"
                  if metric == "energy"
                  else "CPU Time: Normal vs. After Phase 3 Packet Loss")
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)

    # Shared legend
    legend_patches = [
        mpatches.Patch(color=COL_AUTH,   label="Authentication"),
        mpatches.Patch(color=COL_KEYEX,  label="Key Exchange"),
        mpatches.Patch(color=COL_EXTRA,  label="Re-Enrollment (penalty)"),
    ]
    fig.legend(handles=legend_patches, loc="upper center", ncol=3,
               fontsize=11, framealpha=0.9, bbox_to_anchor=(0.5, 1.01))

    fig.suptitle(
        "Desynchronisation Recovery: Cost After a Single Phase 3 Packet Loss",
        fontsize=14, fontweight="bold", y=1.06,
    )
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "01_desync_recovery_stacked.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    if show: plt.show()
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out)}")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 2 — Recovery overhead (extra cost from ONE packet loss)
# ─────────────────────────────────────────────────────────────────────────────
def chart_overhead(data, show=False):
    """
    Simple side-by-side bar:
      Shows only the EXTRA cost imposed by a Phase 3 packet loss event.
      Proposed = 0 (desync recovery, zero penalty)
      LAAKA/Zhou = re-enrollment cost
    """
    schemes = ["Proposed", "LAAKA", "Zhou"]
    labels  = ["Proposed\n(w/ desync recovery)", "LAAKA\n(no recovery)", "Zhou\n(no recovery)"]
    colors  = [SCHEME_COLORS[s] for s in schemes]

    extra_e, extra_c, ci_e, ci_c = [], [], [], []
    for scheme in schemes:
        d   = data[scheme]
        enr = d.get("Enrollment", {"energy": 0, "cpu": 0, "ci_e": 0, "ci_c": 0})
        extra_e.append(enr["energy"])
        extra_c.append(enr["cpu"])
        ci_e.append(enr["ci_e"])
        ci_c.append(enr["ci_c"])

    x = np.arange(len(schemes))
    w = 0.35

    with plt.rc_context(_CHART_STYLE):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
        fig.patch.set_facecolor("white")

        for ax, vals, errs, ylabel, title in [
            (ax1, extra_e, ci_e,
             "Extra Energy per Device (mJ)",
             "Extra Energy Due to Phase 3\nPacket Loss (Re-Enrolment Penalty)"),
            (ax2, extra_c, ci_c,
             "Extra CPU Time per Device (s)",
             "Extra CPU Time Due to Phase 3\nPacket Loss (Re-Enrolment Penalty)"),
        ]:
            bars = ax.bar(x, vals, w, yerr=errs, capsize=6,
                          color=colors, alpha=0.88,
                          edgecolor="white", linewidth=0.8, zorder=3)

            # Value labels
            for bar, val in zip(bars, vals):
                label = "0 (Free Recovery)" if val == 0 else f"{val:.1f}"
                color = "#1B5E20" if val == 0 else "#444444"
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(vals) * 0.02,
                        label, ha="center", va="bottom",
                        fontsize=10, color=color, fontweight="bold")

            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=11)
            ax.set_ylabel(ylabel, fontsize=13, fontweight="bold")
            ax.set_title(title, fontsize=12, fontweight="bold")
            ax.yaxis.grid(True, linestyle="--", alpha=0.5)
            ax.set_axisbelow(True)
            ax.set_ylim(0, max(vals) * 1.28 if max(vals) > 0 else 5)

            # Annotate Proposed bar with green checkmark note
            ax.annotate("Dual-state\nlookup handles\npacket loss",
                        xy=(x[0], 0.2 if ax == ax1 else 0.005),
                        xytext=(x[0] + 0.4, max(vals) * 0.35),
                        fontsize=9, color="#1B5E20",
                        arrowprops=dict(arrowstyle="->", color="#1B5E20", lw=1.2))

        fig.suptitle(
            "Recovery Overhead per Device After One Phase 3 Packet Loss\n"
            "(Proposed: zero overhead · LAAKA/Zhou: must re-enrol)",
            fontsize=13, fontweight="bold",
        )
        fig.tight_layout()
        out = os.path.join(OUT_DIR, "02_desync_recovery_overhead.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        if show: plt.show()
        plt.close(fig)
    print(f"  Saved: {os.path.basename(out)}")


# ─────────────────────────────────────────────────────────────────────────────
# Chart 3 — Cumulative cost over N authentication cycles with one packet loss
# ─────────────────────────────────────────────────────────────────────────────
def chart_cumulative(data, cycles=6, loss_at=2, show=False):
    """
    Line chart: cumulative per-device energy across `cycles` auth sessions.
    A Phase 3 packet loss occurs after session `loss_at`.
    Proposed recovers in the very next session; LAAKA/Zhou add re-enrollment.
    """
    schemes = ["Proposed", "LAAKA", "Zhou"]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("white")

    with plt.rc_context(_CHART_STYLE):
        for scheme in schemes:
            d    = data[scheme]
            enr  = d.get("Enrollment",  {"energy": 0})["energy"]
            auth_kex = d.get("Auth+KeyEx", {"energy":
                d.get("Authentication", {"energy": 0})["energy"] +
                d.get("Key Exchange",   {"energy": 0})["energy"]
            })["energy"]

            cumulative = [enr]      # session 0 = enrollment
            total      = enr

            for i in range(1, cycles + 1):
                if i == loss_at + 1 and scheme != "Proposed":
                    # Loss occurred after session loss_at → must re-enrol
                    total += enr + auth_kex
                else:
                    total += auth_kex
                cumulative.append(total)

            xs = list(range(cycles + 1))
            ax.plot(xs, cumulative,
                    label=scheme,
                    color=SCHEME_COLORS[scheme],
                    marker="o", linewidth=2.2, markersize=7)

            # Annotate the penalty jump
            if scheme != "Proposed":
                jump_y  = cumulative[loss_at + 1]
                jump_y0 = cumulative[loss_at] + auth_kex
                ax.annotate(
                    f"+{enr:.1f} mJ\n(re-enrol)",
                    xy=(loss_at + 1, jump_y),
                    xytext=(loss_at + 1.15, jump_y0 + enr * 0.4),
                    fontsize=9, color=SCHEME_COLORS[scheme],
                    arrowprops=dict(arrowstyle="->",
                                    color=SCHEME_COLORS[scheme], lw=1.1),
                )

        # Mark the loss event
        ax.axvline(x=loss_at + 0.5, color="gray", linestyle="--",
                   linewidth=1.2, alpha=0.7)
        ax.text(loss_at + 0.55, ax.get_ylim()[0] if ax.get_ylim()[0] > 0 else 0,
                "← Phase 3\n   packet loss\n   occurs here",
                fontsize=9, color="gray", va="bottom")

        ax.set_xlabel("Authentication Session (0 = Enrollment)", fontsize=14, fontweight="bold")
        ax.set_ylabel("Cumulative Energy per Device (mJ)", fontsize=14, fontweight="bold")
        ax.set_title(
            f"Cumulative Cost over {cycles} Sessions\n"
            f"(Phase 3 packet loss after session {loss_at})",
            fontsize=14, fontweight="bold",
        )
        ax.set_xticks(range(cycles + 1))
        ax.set_xticklabels(
            ["Enrol"] + [f"Auth {i}" for i in range(1, cycles + 1)],
            fontsize=10,
        )
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        ax.legend(loc="upper left", fontsize=12)

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "03_desync_recovery_cumulative.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    if show: plt.show()
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out)}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary CSV
# ─────────────────────────────────────────────────────────────────────────────
def write_summary(data):
    schemes = ["Proposed", "LAAKA", "Zhou"]
    out = os.path.join(OUT_DIR, "desync_recovery_summary.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Scheme", "Has_Desync_Recovery",
            "Normal_Path_Energy_mJ", "After_Loss_Energy_mJ",
            "Overhead_Energy_mJ", "Overhead_Pct",
            "Normal_Path_CPU_s", "After_Loss_CPU_s",
            "Overhead_CPU_s",
        ])
        for scheme in schemes:
            d = data[scheme]
            enr = d.get("Enrollment", {"energy": 0, "cpu": 0})
            ak  = d.get("Auth+KeyEx", {
                "energy": d.get("Authentication", {"energy": 0})["energy"] +
                          d.get("Key Exchange",   {"energy": 0})["energy"],
                "cpu":    d.get("Authentication", {"cpu": 0})["cpu"] +
                          d.get("Key Exchange",   {"cpu": 0})["cpu"],
            })
            has_recovery = (scheme == "Proposed")
            normal_e = ak["energy"]
            loss_e   = ak["energy"] if has_recovery else enr["energy"] + ak["energy"]
            normal_c = ak["cpu"]
            loss_c   = ak["cpu"] if has_recovery else enr["cpu"] + ak["cpu"]
            overhead_e   = loss_e - normal_e
            overhead_pct = (overhead_e / normal_e * 100) if normal_e > 0 else 0
            w.writerow([
                scheme, "Yes" if has_recovery else "No",
                f"{normal_e:.4f}", f"{loss_e:.4f}",
                f"{overhead_e:.4f}", f"{overhead_pct:.1f}",
                f"{normal_c:.6f}", f"{loss_c:.6f}",
                f"{loss_c - normal_c:.6f}",
            ])
    print(f"  Summary → {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--loss-at", type=int, default=2,
                        help="Session after which Phase 3 loss occurs (default: 2)")
    parser.add_argument("--cycles", type=int, default=6,
                        help="Total auth sessions to plot in cumulative chart (default: 6)")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    data = load_data()

    print("Chart 1 — Stacked: Normal vs After-Loss path")
    chart_stacked(data, show=args.show)

    print("Chart 2 — Recovery overhead (extra cost per packet loss)")
    chart_overhead(data, show=args.show)

    print("Chart 3 — Cumulative cost over multiple sessions")
    chart_cumulative(data, cycles=args.cycles, loss_at=args.loss_at, show=args.show)

    print("Summary CSV")
    summary = write_summary(data)

    # Print key numbers
    print("\n" + "=" * 60)
    print("KEY NUMBERS (from 100-node, 20-device COOJA simulation)")
    print("=" * 60)
    for scheme in ["Proposed", "LAAKA", "Zhou"]:
        d   = data[scheme]
        enr = d.get("Enrollment", {"energy": 0})["energy"]
        ak  = d.get("Auth+KeyEx", {
            "energy": d.get("Authentication", {"energy": 0})["energy"] +
                      d.get("Key Exchange",   {"energy": 0})["energy"]
        })["energy"]
        has = (scheme == "Proposed")
        loss_cost = ak if has else enr + ak
        pct = 0 if has else enr / ak * 100
        print(f"  {scheme:12s}  normal={ak:.2f} mJ  after-loss={loss_cost:.2f} mJ  "
              f"overhead={pct:.1f}%  recovery={'YES (free)' if has else 'NO (re-enrol)'}")
    print("=" * 60)
    print(f"\nAll outputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
