"""
plot_desync_proposed_vs_base.py
Visualise desynchronisation recovery cost: Proposed scheme vs Base scheme only.

SCENARIO
--------
In Phase 3 (Key Exchange), AS sends (mH, ts2) to D via GW.
  - mH = m_new XOR H(...)  — masked new nonce
  - ts2                    — timestamp for freshness verification

If this packet is lost:
  • D retains its stale nonce m_curr → PID_old = H(ID_D || m_curr)
  • AS/GW advances to m_new → PID_curr = H(ID_D || m_new)

Recovery on next authentication attempt:
  • Proposed scheme  — AS stores (m_curr, m_old, PID_curr, PID_old).
                       D presents PID_old; AS recognises it via dual-state lookup
                       and re-runs Phase 3 transparently.  Cost = Auth+KeyEx only.
                       Overhead = 0.

  • Base scheme      — AS stores only m_curr; PID_old is unknown.
    (das2026comsnets)  Authentication rejected → D must re-enrol before it can
                       proceed.  Cost = Enrol + Auth+KeyEx.
                       Overhead = Enrolment cost.

All numbers come from the 5-seed, 20-device, 100-node COOJA simulation in
Results/Charts/Revised-vs-LAAKA-vs-Zhou/comparison_summary.csv.
The Base scheme data is the "LAAKA" row (das2026comsnets = LAAKA).

OUTPUTS (Results/Desync-Recovery-Analysis/)
-------------------------------------------
  01_desync_normal_vs_postloss.png   — per-cycle cost: normal vs post-loss
  02_desync_overhead.png             — extra energy/CPU added per loss event
  03_desync_cumulative.png           — cumulative cost over 6 sessions (loss at s3)
  desync_proposed_vs_base_summary.csv
"""

import os, csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ─── paths ──────────────────────────────────────────────────────────────────
REPO    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
SRC_CSV = os.path.join(REPO, "Results", "Charts",
                       "Revised-vs-LAAKA-vs-Zhou", "comparison_summary.csv")
OUT_DIR = os.path.join(REPO, "Results", "Desync-Recovery-Analysis")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── style ──────────────────────────────────────────────────────────────────
STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    15,
    "axes.titleweight":  "bold",
    "axes.labelsize":    14,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.labelsize":   13,
    "ytick.labelsize":   13,
    "xtick.major.size":  0,
    "legend.fontsize":   12,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

C_PROPOSED = "#2C6FAC"   # blue
C_BASE     = "#B85C2C"   # orange-red
C_ENROLL   = "#E8A87C"   # light orange (re-enrollment highlight)
C_AK       = "#7EB8E8"   # light blue  (auth+keyex highlight)

SCHEME_LABELS = {
    "Proposed": "Proposed\n(with recovery)",
    "Base":     "Base scheme\n(no recovery)",
}

# ─── load data ──────────────────────────────────────────────────────────────
def load_data():
    data = {}
    with open(SRC_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s, ph = row["Scheme"], row["Phase"]
            key = "Proposed" if row["Scheme"] == "Revised-Anonymity" else \
                  "Base"     if row["Scheme"] == "LAAKA"             else None
            if key is None:
                continue
            if key not in data:
                data[key] = {}
            data[key][ph] = {
                "energy": float(row["Avg_Energy_mJ"]),
                "ci_e":   float(row["CI95_Energy_mJ"]),
                "cpu":    float(row["Avg_CPU_s"]),
                "ci_c":   float(row["CI95_CPU_s"]),
            }
    return data


# ─── derived numbers ────────────────────────────────────────────────────────
def compute_scenarios(data):
    """
    Returns a dict with normal-cycle and post-loss-cycle costs.

    Normal:    Auth+KeyEx only (no re-enrol needed)
    Post-loss: Proposed → Auth+KeyEx (dual-state recovery, zero overhead)
               Base     → Enrol + Auth+KeyEx (must re-enrol after rejected auth)
    """
    res = {}
    for scheme in ("Proposed", "Base"):
        d = data[scheme]
        enroll  = d["Enrollment"]
        ak      = d["Auth+KeyEx"]
        res[scheme] = {
            "normal_energy":    ak["energy"],
            "normal_ci_e":      ak["ci_e"],
            "normal_cpu":       ak["cpu"],
            "normal_ci_c":      ak["ci_c"],
            "postloss_energy":  ak["energy"]  + (enroll["energy"] if scheme == "Base" else 0),
            "postloss_ci_e":    (ak["ci_e"]**2 + (enroll["ci_e"]**2 if scheme == "Base" else 0))**0.5,
            "postloss_cpu":     ak["cpu"]     + (enroll["cpu"]    if scheme == "Base" else 0),
            "postloss_ci_c":    (ak["ci_c"]**2 + (enroll["ci_c"]**2 if scheme == "Base" else 0))**0.5,
            "enroll_energy":    enroll["energy"],
            "enroll_cpu":       enroll["cpu"],
        }
    return res


# ─── Chart 1: Normal vs Post-loss per cycle ─────────────────────────────────
def chart_normal_vs_postloss(sc):
    """
    Grouped bars: for each scheme, two bars — Normal cycle and Post-(mH,ts2)-loss cycle.
    Energy and CPU panels side by side.
    """
    schemes  = ["Proposed", "Base"]
    labels   = [SCHEME_LABELS[s] for s in schemes]
    x        = np.arange(len(schemes))
    w        = 0.32

    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
        fig.patch.set_facecolor("white")
        fig.suptitle(
            "Per-Cycle Cost: Normal vs After (mH, ts2) Loss in Phase 3",
            fontsize=15, fontweight="bold", y=1.01
        )

        panels = [
            ("energy", "Avg Energy per Device (mJ)", "Energy"),
            ("cpu",    "Avg CPU Time per Device (s)", "CPU Time"),
        ]

        for ax, (metric, ylabel, panel_title) in zip(axes, panels):
            norm_vals = [sc[s][f"normal_{metric}"]   for s in schemes]
            post_vals = [sc[s][f"postloss_{metric}"] for s in schemes]
            norm_ci   = [sc[s][f"normal_ci_{metric[0]}"]   for s in schemes]
            post_ci   = [sc[s][f"postloss_ci_{metric[0]}"] for s in schemes]
            enroll_vals = [sc[s][f"enroll_{metric}"] if s == "Base" else 0 for s in schemes]

            # Normal bars
            bars_n = ax.bar(x - w/2, norm_vals, w,
                            label="Normal cycle\n(Auth + Key Exchange)",
                            color=[C_PROPOSED, C_BASE], alpha=0.85,
                            edgecolor="white", linewidth=0.8,
                            yerr=norm_ci, capsize=5, error_kw={"linewidth": 1.2})

            # Post-loss bars — stacked: Auth+KeyEx base + re-enrollment top
            ak_part = [sc[s][f"normal_{metric}"] for s in schemes]
            re_part = enroll_vals
            bars_b = ax.bar(x + w/2, ak_part, w,
                            label="Post-loss cycle\n(Auth + Key Exchange)",
                            color=[C_PROPOSED, C_BASE], alpha=0.45,
                            edgecolor="white", linewidth=0.8)
            bars_e = ax.bar(x + w/2, re_part, w,
                            bottom=ak_part,
                            label="Re-enrollment overhead",
                            color=C_ENROLL, alpha=0.9,
                            edgecolor="white", linewidth=0.8,
                            yerr=post_ci, capsize=5, error_kw={"linewidth": 1.2})

            # Annotate values
            max_val = max(post_vals) * 1.15 or 1
            fmt = ".1f" if metric == "energy" else ".3f"
            for i, (nv, pv) in enumerate(zip(norm_vals, post_vals)):
                ax.text(x[i] - w/2, nv + max_val*0.02, f"{nv:{fmt}}",
                        ha="center", va="bottom", fontsize=11)
                ax.text(x[i] + w/2, pv + max_val*0.02, f"{pv:{fmt}}",
                        ha="center", va="bottom", fontsize=11,
                        color="#B03030" if i == 1 else "#333333")

            # Overhead annotation for Base scheme
            overhead = sc["Base"][f"postloss_{metric}"] - sc["Base"][f"normal_{metric}"]
            if overhead > 0:
                suffix = "mJ" if metric == "energy" else "s"
                pct = overhead / sc["Base"][f"normal_{metric}"] * 100
                ax.annotate(f"+{overhead:{fmt}} {suffix}\n(+{pct:.1f}%)",
                            xy=(x[1] + w/2, sc["Base"][f"postloss_{metric}"]),
                            xytext=(x[1] + w/2 + 0.25, sc["Base"][f"postloss_{metric}"] * 0.85),
                            fontsize=11, color="#B03030",
                            arrowprops=dict(arrowstyle="->", color="#B03030", lw=1.2))

            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=13, fontweight="bold")
            ax.set_title(panel_title, fontsize=13, fontweight="bold", pad=8)
            ax.yaxis.grid(True, linestyle="--", alpha=0.5)
            ax.set_axisbelow(True)
            ax.tick_params(axis="y", length=0)

            # Legend (only on first panel)
            if ax is axes[0]:
                normal_patch  = mpatches.Patch(color=C_PROPOSED, alpha=0.85,
                                               label="Normal cycle (Auth + Key Exchange)")
                postloss_patch = mpatches.Patch(color=C_BASE, alpha=0.45,
                                                label="Post-loss: Auth + Key Exchange part")
                enroll_patch  = mpatches.Patch(color=C_ENROLL, alpha=0.9,
                                               label="Post-loss: Re-enrollment overhead")
                ax.legend(handles=[normal_patch, postloss_patch, enroll_patch],
                          fontsize=10, loc="upper left", framealpha=0.9)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, "01_desync_normal_vs_postloss.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: 01_desync_normal_vs_postloss.png")


# ─── Chart 2: Overhead per loss event ───────────────────────────────────────
def chart_overhead(sc):
    """
    Simple horizontal bar: extra energy and CPU added per single (mH,ts2) loss.
    Proposed = 0 (zero overhead), Base = Enrolment cost.
    """
    schemes = ["Proposed", "Base"]
    oh_e = [0.0, sc["Base"]["enroll_energy"]]
    oh_c = [0.0, sc["Base"]["enroll_cpu"]]

    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
        fig.patch.set_facecolor("white")
        fig.suptitle(
            "Extra Cost per (mH, ts2) Loss Event in Phase 3",
            fontsize=15, fontweight="bold", y=1.03
        )

        for ax, vals, ylabel, fmt, unit in [
            (axes[0], oh_e, "Extra Energy (mJ)",  ".1f", "mJ"),
            (axes[1], oh_c, "Extra CPU Time (s)", ".3f", "s"),
        ]:
            colors = [C_PROPOSED, C_BASE]
            bars = ax.barh([SCHEME_LABELS[s] for s in schemes], vals,
                           color=colors, alpha=0.85, edgecolor="white", height=0.45)
            for bar, v in zip(bars, vals):
                label = "0 (recovery is free)" if v == 0 else f"+{v:{fmt}} {unit}"
                ax.text(max(vals) * 0.03, bar.get_y() + bar.get_height()/2,
                        label,
                        va="center", ha="left", fontsize=12,
                        color="#2C6FAC" if v == 0 else "#B03030",
                        fontweight="bold")
            ax.set_xlabel(ylabel, fontsize=13, fontweight="bold")
            ax.set_xlim(0, max(vals) * 1.45 if max(vals) > 0 else 5)
            ax.xaxis.grid(True, linestyle="--", alpha=0.5)
            ax.set_axisbelow(True)
            ax.tick_params(axis="x", length=0)
            ax.spines["left"].set_color("#cccccc")
            ax.spines["bottom"].set_color("#cccccc")

        fig.tight_layout()
        out = os.path.join(OUT_DIR, "02_desync_overhead.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: 02_desync_overhead.png")


# ─── Chart 3: Cumulative cost over sessions ──────────────────────────────────
def chart_cumulative(sc):
    """
    Line chart: cumulative energy over 6 sessions.
    (mH, ts2) is lost at the end of session 2 → session 3 incurs recovery/re-enrol cost.
    """
    N = 6
    loss_at = 2   # loss occurs at end of session 2; session 3 is the costly one

    def cumulative(scheme):
        normal   = sc[scheme]["normal_energy"]
        postloss = sc[scheme]["postloss_energy"]
        vals = []
        cum  = 0.0
        for i in range(1, N + 1):
            cost = postloss if i == loss_at + 1 else normal
            cum += cost
            vals.append(cum)
        return vals

    sessions = list(range(1, N + 1))
    cum_p = cumulative("Proposed")
    cum_b = cumulative("Base")

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(9, 5))
        fig.patch.set_facecolor("white")

        ax.plot(sessions, cum_p, color=C_PROPOSED, marker="o", linewidth=2.5,
                markersize=8, label="Proposed (with recovery)")
        ax.plot(sessions, cum_b, color=C_BASE,     marker="s", linewidth=2.5,
                markersize=8, label="Base scheme (no recovery)",
                linestyle="--")

        # Shade the gap after session 3
        ax.fill_between(sessions[loss_at:], cum_p[loss_at:], cum_b[loss_at:],
                        alpha=0.12, color=C_BASE, label="Wasted energy (base scheme)")

        # Mark the loss event
        ax.axvline(x=loss_at + 0.5, color="#888888", linestyle=":", linewidth=1.4)
        ax.text(loss_at + 0.55, max(cum_b) * 0.25,
                "(mH, ts2)\nlost here",
                fontsize=10, color="#888888", va="bottom")

        # Annotate divergence at session N
        gap = cum_b[-1] - cum_p[-1]
        ax.annotate(f"Gap: {gap:.1f} mJ\nafter {N} sessions",
                    xy=(sessions[-1], cum_b[-1]),
                    xytext=(sessions[-1] - 1.6, cum_b[-1] * 0.88),
                    fontsize=11, color=C_BASE,
                    arrowprops=dict(arrowstyle="->", color=C_BASE, lw=1.2))

        ax.set_xlabel("Session number", fontsize=14, fontweight="bold")
        ax.set_ylabel("Cumulative Energy per Device (mJ)", fontsize=14, fontweight="bold")
        ax.set_title(
            "Cumulative Energy Cost over Sessions\n(Phase 3 packet lost at end of session 2)",
            fontsize=14, fontweight="bold"
        )
        ax.set_xticks(sessions)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        ax.legend(fontsize=12, loc="upper left")

        fig.tight_layout()
        out = os.path.join(OUT_DIR, "03_desync_cumulative.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: 03_desync_cumulative.png")


# ─── Summary CSV ────────────────────────────────────────────────────────────
def write_summary(sc):
    out = os.path.join(OUT_DIR, "desync_proposed_vs_base_summary.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "Cycle", "Energy_mJ", "CPU_s",
                    "Overhead_Energy_mJ", "Overhead_CPU_s", "Overhead_pct"])
        for scheme in ("Proposed", "Base"):
            ne = sc[scheme]["normal_energy"]
            nc = sc[scheme]["normal_cpu"]
            pe = sc[scheme]["postloss_energy"]
            pc = sc[scheme]["postloss_cpu"]
            oe = pe - ne
            oc = pc - nc
            pct = oe / ne * 100
            w.writerow([SCHEME_LABELS[scheme].replace("\n", " "),
                        "Normal",   f"{ne:.4f}", f"{nc:.6f}", "0", "0", "0"])
            w.writerow([SCHEME_LABELS[scheme].replace("\n", " "),
                        "Post-loss", f"{pe:.4f}", f"{pc:.6f}",
                        f"{oe:.4f}", f"{oc:.6f}", f"{pct:.1f}"])
    print(f"  Summary CSV → {out}")


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    print("Loading simulation data...")
    data = load_data()
    sc   = compute_scenarios(data)

    print("\nKey numbers:")
    for scheme in ("Proposed", "Base"):
        ne = sc[scheme]["normal_energy"]
        pe = sc[scheme]["postloss_energy"]
        nc = sc[scheme]["normal_cpu"]
        pc = sc[scheme]["postloss_cpu"]
        print(f"  {scheme:10s}  normal={ne:.2f} mJ  post-loss={pe:.2f} mJ  "
              f"overhead={pe-ne:.2f} mJ ({(pe-ne)/ne*100:.1f}%)")

    print("\nChart 1 — Normal vs Post-loss per cycle")
    chart_normal_vs_postloss(sc)

    print("Chart 2 — Overhead per loss event")
    chart_overhead(sc)

    print("Chart 3 — Cumulative over 6 sessions")
    chart_cumulative(sc)

    print("\nSummary CSV")
    write_summary(sc)

    print(f"\nAll outputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
