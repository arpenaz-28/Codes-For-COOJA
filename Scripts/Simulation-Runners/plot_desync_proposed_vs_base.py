"""
plot_desync_proposed_vs_base.py
Desynchronisation recovery cost: Proposed scheme vs Base scheme (das2026comsnets).

CORRECTED SCENARIO
------------------
Phase 3 (Key Exchange): AS sends (mH, ts2) to D.
  mH = m_new XOR H(...)   — masked new nonce
  ts2                      — Phase-2 timestamp reused for freshness of mH

If this packet is lost, D retains stale m_curr and cannot update its PID.

PRE-LOSS SESSION (the session in which the loss occurs):
  Both schemes:  Enrollment + Authentication + Key Exchange
  (Enrollment is needed because this models the full lifecycle from join.)

POST-LOSS SESSION (next session, after D's state is stale):
  • Proposed  — AS stores (m_curr, m_old, PID_curr, PID_old).
                D presents PID_old; AS matches it via dual-state, re-runs Phase 3.
                Post-loss cost = Authentication + Key Exchange  (no re-enrol).
                Recovery overhead vs a normal session = Auth+KeyEx = 28.87 mJ.

  • Base       — AS stores only m_curr; it has no PID mechanism.
    (das2026comsnets)
                D computes auth token using stale m_curr → nonce mismatch → rejected.
                D must re-enrol before it can authenticate again.
                Post-loss cost = Enrollment + Authentication + Key Exchange.
                Recovery overhead vs a normal session = Enrol+Auth+KeyEx = 91.22 mJ.

OVERHEAD PER DESYNC EVENT:
  Proposed:  +28.87 mJ  (one extra Auth+KeyEx session)
  Base:      +91.22 mJ  (one extra Enrol+Auth+KeyEx session)
  Base costs 3.16× more per desync event.

All numbers: 5-seed, 20-device, 100-node COOJA simulation.
Source: Results/Charts/Revised-vs-LAAKA-vs-Zhou/comparison_summary.csv
Base-scheme row is "LAAKA" (das2026comsnets = LAAKA).

OUTPUTS  →  Results/Desync-Recovery-Analysis/
  01_desync_session_breakdown.png   stacked bars: pre-loss vs post-loss sessions
  02_desync_overhead.png            overhead per single desync event (stacked phases)
  03_desync_cumulative.png          cumulative energy over 6 sessions, loss at session 3
  desync_proposed_vs_base_summary.csv
"""

import os, csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ─── paths ───────────────────────────────────────────────────────────────────
REPO    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
SRC_CSV = os.path.join(REPO, "Results", "Charts",
                       "Revised-vs-LAAKA-vs-Zhou", "comparison_summary.csv")
OUT_DIR = os.path.join(REPO, "Results", "Desync-Recovery-Analysis")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── style ───────────────────────────────────────────────────────────────────
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

# Phase colours (same across all charts for consistency)
C_ENROLL = "#5BA4CF"   # steel blue   — Enrollment
C_AUTH   = "#F4A261"   # amber        — Authentication
C_KEYEX  = "#2A9D8F"   # teal         — Key Exchange

C_PROPOSED = "#2C6FAC"
C_BASE     = "#B85C2C"


# ─── load data ───────────────────────────────────────────────────────────────
def load_data():
    raw = {}
    with open(SRC_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = ("Proposed" if row["Scheme"] == "Revised-Anonymity" else
                   "Base"     if row["Scheme"] == "LAAKA"             else None)
            if key is None:
                continue
            raw.setdefault(key, {})[row["Phase"]] = {
                "e":    float(row["Avg_Energy_mJ"]),
                "ci_e": float(row["CI95_Energy_mJ"]),
                "c":    float(row["Avg_CPU_s"]),
                "ci_c": float(row["CI95_CPU_s"]),
            }
    return raw


def derive(data):
    """
    Pre-compute all scenario values used across charts.

    pre_loss  = Enrollment + Auth + KeyEx  (the session where (mH,ts2) is lost)
    post_loss = Proposed: Auth+KeyEx only  (recovery via dual-state, no re-enrol)
                Base:     Enrol+Auth+KeyEx (forced re-enrol after nonce mismatch)
    overhead  = post_loss (= cost of the extra session caused by the desync event)
    normal    = Auth+KeyEx  (a plain session with no desync; for cumulative chart)
    """
    sc = {}
    for s in ("Proposed", "Base"):
        d  = data[s]
        en = d["Enrollment"]
        au = d["Authentication"]
        kx = d["Key Exchange"]
        ak = d["Auth+KeyEx"]

        pre_e  = en["e"] + ak["e"]
        pre_c  = en["c"] + ak["c"]
        pre_ci_e = math.sqrt(en["ci_e"]**2 + ak["ci_e"]**2)
        pre_ci_c = math.sqrt(en["ci_c"]**2 + ak["ci_c"]**2)

        if s == "Proposed":
            post_e   = ak["e"];  post_c   = ak["c"]
            post_ci_e = ak["ci_e"]; post_ci_c = ak["ci_c"]
        else:
            post_e   = en["e"] + ak["e"];  post_c = en["c"] + ak["c"]
            post_ci_e = math.sqrt(en["ci_e"]**2 + ak["ci_e"]**2)
            post_ci_c = math.sqrt(en["ci_c"]**2 + ak["ci_c"]**2)

        sc[s] = {
            # individual phases (for stacked bars)
            "enroll_e": en["e"], "enroll_c": en["c"],
            "auth_e":   au["e"], "auth_c":   au["c"],
            "keyex_e":  kx["e"], "keyex_c":  kx["c"],
            "ak_e":     ak["e"], "ak_c":     ak["c"],
            # scenario totals
            "pre_e":  pre_e,  "pre_c":  pre_c,
            "pre_ci_e": pre_ci_e, "pre_ci_c": pre_ci_c,
            "post_e": post_e, "post_c": post_c,
            "post_ci_e": post_ci_e, "post_ci_c": post_ci_c,
            # normal session (used in cumulative)
            "normal_e": ak["e"], "normal_c": ak["c"],
        }
    return sc


# ─── Chart 1: Pre-loss vs Post-loss session breakdown ────────────────────────
def chart_session_breakdown(sc):
    """
    Stacked grouped bars: 2 groups (Pre-loss, Post-loss) × 2 schemes.
    Each bar is phase-coloured: Enrollment / Authentication / Key Exchange.
    Shows that:
      - Pre-loss: both schemes do Enrol+Auth+KeyEx (different absolute costs)
      - Post-loss: Proposed does only Auth+KeyEx; Base does Enrol+Auth+KeyEx again
    """
    groups   = ["Pre-loss Session\n(Enrol + Auth + KeyEx)",
                "Post-loss Session\n(recovery)"]
    schemes  = ["Proposed", "Base"]
    n_g, n_s = len(groups), len(schemes)
    x     = np.arange(n_g)
    w     = 0.30
    offsets = [-(w/2), +(w/2)]

    # Data: [group][scheme] for each phase
    enroll_vals = [
        [sc["Proposed"]["enroll_e"], sc["Base"]["enroll_e"]],   # pre-loss
        [0,                          sc["Base"]["enroll_e"]],   # post-loss
    ]
    auth_vals = [
        [sc["Proposed"]["auth_e"],   sc["Base"]["auth_e"]],
        [sc["Proposed"]["auth_e"],   sc["Base"]["auth_e"]],
    ]
    keyex_vals = [
        [sc["Proposed"]["keyex_e"],  sc["Base"]["keyex_e"]],
        [sc["Proposed"]["keyex_e"],  sc["Base"]["keyex_e"]],
    ]
    ci_vals = [
        [sc["Proposed"]["pre_ci_e"],  sc["Base"]["pre_ci_e"]],
        [sc["Proposed"]["post_ci_e"], sc["Base"]["post_ci_e"]],
    ]
    totals = [
        [sc["Proposed"]["pre_e"],  sc["Base"]["pre_e"]],
        [sc["Proposed"]["post_e"], sc["Base"]["post_e"]],
    ]
    scheme_colors = [C_PROPOSED, C_BASE]

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(11, 6))
        fig.patch.set_facecolor("white")

        for gi, group in enumerate(groups):
            for si, scheme in enumerate(schemes):
                xpos = x[gi] + offsets[si]
                ev = enroll_vals[gi][si]
                av = auth_vals[gi][si]
                kv = keyex_vals[gi][si]
                ci = ci_vals[gi][si]
                tot = totals[gi][si]
                alpha = 0.88

                ax.bar(xpos, ev, w, color=C_ENROLL, alpha=alpha,
                       edgecolor="white", linewidth=0.8)
                ax.bar(xpos, av, w, bottom=ev, color=C_AUTH, alpha=alpha,
                       edgecolor="white", linewidth=0.8)
                ax.bar(xpos, kv, w, bottom=ev + av, color=C_KEYEX, alpha=alpha,
                       edgecolor="white", linewidth=0.8,
                       yerr=ci, capsize=4, error_kw={"linewidth": 1.1, "ecolor": "#555"})

                # Scheme label below bar
                ax.text(xpos, -6, scheme, ha="center", va="top",
                        fontsize=10, color=scheme_colors[si], fontweight="bold")

                # Total value above bar
                ax.text(xpos, tot + ci + 1.5, f"{tot:.1f}",
                        ha="center", va="bottom", fontsize=11, fontweight="bold",
                        color="#333")

        # Annotate the "overhead" arrow for post-loss difference
        p_post = sc["Proposed"]["post_e"]
        b_post = sc["Base"]["post_e"]
        xm = x[1]
        ax.annotate("",
                    xy=(xm + offsets[1], b_post),
                    xytext=(xm + offsets[1], p_post),
                    arrowprops=dict(arrowstyle="<->", color=C_BASE, lw=1.8))
        saving = b_post - p_post
        pct    = saving / b_post * 100
        ax.text(xm + offsets[1] + 0.18, (p_post + b_post) / 2,
                f"Base pays\n{saving:.1f} mJ more\n({pct:.0f}% higher)",
                ha="left", va="center", fontsize=10, color=C_BASE)

        ax.set_xticks(x)
        ax.set_xticklabels(groups, fontsize=12)
        ax.set_ylabel("Avg Energy per Device (mJ)", fontsize=13, fontweight="bold")
        ax.set_title(
            "Session Energy Breakdown: Pre-loss vs Post-(mH, ts2)-loss\n"
            "Proposed (dual-state recovery) vs Base scheme (nonce mismatch → re-enrol)",
            fontsize=13, fontweight="bold", pad=10
        )
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=-14)

        legend_handles = [
            mpatches.Patch(color=C_ENROLL, alpha=0.88, label="Enrollment"),
            mpatches.Patch(color=C_AUTH,   alpha=0.88, label="Authentication"),
            mpatches.Patch(color=C_KEYEX,  alpha=0.88, label="Key Exchange"),
        ]
        ax.legend(handles=legend_handles, loc="upper right",
                  fontsize=11, framealpha=0.92)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, "01_desync_session_breakdown.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: 01_desync_session_breakdown.png")


# ─── Chart 2: Overhead per desync event ──────────────────────────────────────
def chart_overhead(sc):
    """
    Horizontal stacked bar: the cost of the extra session that desync forces.
    Proposed: Auth+KeyEx (28.87 mJ) — dual-state recovery session
    Base:     Enrol+Auth+KeyEx (91.22 mJ) — forced re-enrol + full session

    Both schemes pay something; the point is Proposed pays 3.16x less.
    """
    schemes = ["Proposed\n(with recovery)", "Base scheme\n(no recovery)"]
    e_vals  = [sc["Proposed"]["post_e"], sc["Base"]["post_e"]]
    # phase breakdown for stacked bars
    enroll_part = [0,                          sc["Base"]["enroll_e"]]
    auth_part   = [sc["Proposed"]["auth_e"],   sc["Base"]["auth_e"]]
    keyex_part  = [sc["Proposed"]["keyex_e"],  sc["Base"]["keyex_e"]]

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 3.6))
        fig.patch.set_facecolor("white")

        y = np.arange(len(schemes))
        h = 0.38

        bars_e = ax.barh(y, enroll_part, h, color=C_ENROLL, alpha=0.88,
                         edgecolor="white", label="Enrollment")
        bars_a = ax.barh(y, auth_part,   h, left=enroll_part,
                         color=C_AUTH,   alpha=0.88, edgecolor="white",
                         label="Authentication")
        bars_k = ax.barh(y, keyex_part,  h,
                         left=[enroll_part[i] + auth_part[i] for i in range(len(y))],
                         color=C_KEYEX,  alpha=0.88, edgecolor="white",
                         label="Key Exchange")

        # Total labels at end of each bar
        for i, (scheme, total) in enumerate(zip(schemes, e_vals)):
            ax.text(total + 0.8, y[i], f"{total:.2f} mJ",
                    va="center", ha="left", fontsize=12, fontweight="bold",
                    color=C_PROPOSED if i == 0 else C_BASE)

        # Ratio annotation
        ratio = sc["Base"]["post_e"] / sc["Proposed"]["post_e"]
        ax.text(max(e_vals) * 0.55, -0.52,
                f"Base scheme pays {ratio:.2f}× more per desync event",
                fontsize=11, color=C_BASE, fontstyle="italic")

        ax.set_yticks(y)
        ax.set_yticklabels(schemes, fontsize=12)
        ax.set_xlabel("Energy Cost of Recovery Session (mJ)", fontsize=13,
                      fontweight="bold")
        ax.set_title(
            "Overhead per (mH, ts2) Loss Event\n"
            "(Cost of the extra session forced by desynchronisation)",
            fontsize=13, fontweight="bold"
        )
        ax.set_xlim(0, max(e_vals) * 1.30)
        ax.xaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0)
        ax.legend(loc="lower right", fontsize=11, framealpha=0.92)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, "02_desync_overhead.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: 02_desync_overhead.png")


# ─── Chart 3: Cumulative cost over sessions ───────────────────────────────────
def chart_cumulative(sc):
    """
    Line chart: cumulative energy over 6 sessions.
    Session 1 = Enrollment + Auth+KeyEx (initial join).
    Sessions 2, 3 = normal Auth+KeyEx.
    (mH, ts2) lost at end of session 3 → session 4 is the post-loss session.
    Sessions 5, 6 = normal Auth+KeyEx again.
    """
    N       = 6
    loss_at = 3   # packet lost at end of session 3; session 4 is post-loss

    def cumulative(scheme):
        cum  = 0.0
        vals = []
        for i in range(1, N + 1):
            if i == 1:
                cost = sc[scheme]["pre_e"]        # Enrol + Auth+KeyEx
            elif i == loss_at + 1:
                cost = sc[scheme]["post_e"]       # post-loss session
            else:
                cost = sc[scheme]["normal_e"]     # normal Auth+KeyEx
            cum += cost
            vals.append(cum)
        return vals

    sessions = list(range(1, N + 1))
    cum_p = cumulative("Proposed")
    cum_b = cumulative("Base")

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 5.5))
        fig.patch.set_facecolor("white")

        ax.plot(sessions, cum_p, color=C_PROPOSED, marker="o", linewidth=2.5,
                markersize=8, label="Proposed (dual-state recovery)")
        ax.plot(sessions, cum_b, color=C_BASE, marker="s", linewidth=2.5,
                markersize=8, label="Base scheme (no recovery)", linestyle="--")

        # Shade gap from session loss_at+1 onwards
        ax.fill_between(sessions[loss_at:], cum_p[loss_at:], cum_b[loss_at:],
                        alpha=0.10, color=C_BASE,
                        label="Energy saved by Proposed scheme")

        # Mark loss event
        ax.axvline(x=loss_at + 0.5, color="#888888", linestyle=":", linewidth=1.5)
        ax.text(loss_at + 0.58, max(cum_b) * 0.18,
                "(mH, ts2)\nlost here",
                fontsize=10, color="#666", va="bottom")

        # Mark session 1 as enrollment
        ax.annotate("Session 1:\nEnrol + Auth + KeyEx",
                    xy=(1, max(cum_p[0], cum_b[0])),
                    xytext=(1.3, max(cum_b) * 0.40),
                    fontsize=9, color="#555",
                    arrowprops=dict(arrowstyle="->", color="#888", lw=1.0))

        # Annotate divergence at session N
        gap = cum_b[-1] - cum_p[-1]
        ax.annotate(f"Gap after {N} sessions:\n{gap:.1f} mJ saved",
                    xy=(sessions[-1], (cum_p[-1] + cum_b[-1]) / 2),
                    xytext=(sessions[-1] - 2.0, (cum_p[-1] + cum_b[-1]) / 2),
                    fontsize=11, color=C_BASE,
                    arrowprops=dict(arrowstyle="->", color=C_BASE, lw=1.2))

        ax.set_xlabel("Session number", fontsize=13, fontweight="bold")
        ax.set_ylabel("Cumulative Energy per Device (mJ)", fontsize=13,
                      fontweight="bold")
        ax.set_title(
            "Cumulative Energy: 6 Sessions with (mH, ts2) Loss at Session 3\n"
            "Session 1 = Enrol+Auth+KeyEx; Sessions 2,3,5,6 = Auth+KeyEx; Session 4 = recovery",
            fontsize=12, fontweight="bold"
        )
        ax.set_xticks(sessions)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        ax.legend(fontsize=11, loc="upper left")

        fig.tight_layout()
        out = os.path.join(OUT_DIR, "03_desync_cumulative.png")
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: 03_desync_cumulative.png")


# ─── Summary CSV ─────────────────────────────────────────────────────────────
def write_summary(sc):
    out = os.path.join(OUT_DIR, "desync_proposed_vs_base_summary.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "Session_type", "Phases_included",
                    "Energy_mJ", "CPU_s", "Note"])
        rows = [
            ("Proposed", "Pre-loss",  "Enrol+Auth+KeyEx",
             sc["Proposed"]["pre_e"],  sc["Proposed"]["pre_c"],
             "Normal first session"),
            ("Proposed", "Post-loss", "Auth+KeyEx",
             sc["Proposed"]["post_e"], sc["Proposed"]["post_c"],
             "Dual-state recovery; no re-enrol"),
            ("Proposed", "Overhead",  "Auth+KeyEx",
             sc["Proposed"]["post_e"], sc["Proposed"]["post_c"],
             "Extra session cost per desync event"),
            ("Base",     "Pre-loss",  "Enrol+Auth+KeyEx",
             sc["Base"]["pre_e"],      sc["Base"]["pre_c"],
             "Normal first session"),
            ("Base",     "Post-loss", "Enrol+Auth+KeyEx",
             sc["Base"]["post_e"],     sc["Base"]["post_c"],
             "Forced re-enrol after nonce mismatch"),
            ("Base",     "Overhead",  "Enrol+Auth+KeyEx",
             sc["Base"]["post_e"],     sc["Base"]["post_c"],
             "Extra session cost per desync event"),
        ]
        for scheme, stype, phases, e, c, note in rows:
            w.writerow([scheme, stype, phases, f"{e:.4f}", f"{c:.6f}", note])
    print(f"  Summary CSV → {out}")


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    data = load_data()
    sc   = derive(data)

    print("\nKey numbers (energy, mJ):")
    for s in ("Proposed", "Base"):
        print(f"  {s:10s}  pre-loss={sc[s]['pre_e']:.2f}  "
              f"post-loss(recovery)={sc[s]['post_e']:.2f}  "
              f"overhead={sc[s]['post_e']:.2f} mJ per desync event")
    ratio = sc["Base"]["post_e"] / sc["Proposed"]["post_e"]
    print(f"\n  Base scheme costs {ratio:.2f}x more per desync event than Proposed")

    print("\nChart 1 — Session breakdown (pre-loss vs post-loss)")
    chart_session_breakdown(sc)

    print("Chart 2 — Recovery overhead per event")
    chart_overhead(sc)

    print("Chart 3 — Cumulative over 6 sessions")
    chart_cumulative(sc)

    print("\nSummary CSV")
    write_summary(sc)

    print(f"\nAll outputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
