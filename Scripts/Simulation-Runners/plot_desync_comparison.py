"""
plot_desync_comparison.py
Generate comparison chart for the desync recovery experiment.

Reads summary CSVs produced by run_desync_comparison.py and creates:
  fig_sim_desync.png — grouped bar chart: per-round energy (Base vs Proposed)
  Key result: Round 3 (Recovery) energy for Base >> Proposed
              Base requires re-enrollment; Proposed re-auths via PID_old only.

Saves to:
  Results/COOJA-Simulation/Charts/Desync_Recovery/desync_comparison.png
  Paper/fig_sim_desync.png

Usage:
  python3 plot_desync_comparison.py
"""

import os, csv, shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OUT_DIR   = os.path.join(REPO, "Results", "COOJA-Simulation", "Charts", "Desync_Recovery")
PAPER_DIR = os.path.join(REPO, "Paper")

SCHEMES = {
    "Base": {
        "summary": os.path.join(REPO, "Base-Scheme",
                                "Simulation-Results", "Desync", "csv", "summary.csv"),
        "label":  "DAuth",
        "color":  "#7E5BA6",   # muted purple (consistent with other DAuth charts)
        "hatch":  "",
    },
    "Proposed": {
        "summary": os.path.join(REPO, "Revised-Anonymity",
                                "Simulation-Results", "Desync", "csv", "summary.csv"),
        "label":  "Proposed",
        "color":  "#1f77b4",   # blue
        "hatch":  "",
    },
}

# All possible rounds; Round 4 missing for Base is handled as 0.
ROUNDS = ["Enrollment", "Round 1", "Round 2", "Round 3", "Round 4"]
ROUND_XLABELS = [
    "Enroll\n(Phase 0)",
    "R1: Normal\nAuth",
    "R2: Drop\n→ Desync",
    "R3: Recovery",
    "R4: Post-\nRecovery",
]


def load_summary(path):
    data = {}
    if not os.path.isfile(path):
        print(f"  WARNING: {path} not found")
        return data
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lbl    = row.get("Round", "").strip()
            avg_mJ = float(row.get("Avg_Energy_mJ", 0) or 0)
            std_mJ = float(row.get("Std_Energy_mJ", 0) or 0)
            data[lbl] = (avg_mJ, std_mJ)
    return data


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    scheme_data = {}
    for key, cfg in SCHEMES.items():
        d = load_summary(cfg["summary"])
        if d:
            scheme_data[key] = d
            print(f"  Loaded {key}: {list(d.keys())}")
        else:
            print(f"  No data for {key} — skipping.")

    if not scheme_data:
        print("  No data available. Run run_desync_comparison.py first.")
        return

    # ── Figure: grouped bar chart ────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(11, 5))

    x     = np.arange(len(ROUNDS))
    width = 0.35
    keys  = ["Base", "Proposed"]
    offs  = [-width / 2, width / 2]

    for offset, key in zip(offs, keys):
        if key not in scheme_data:
            continue
        cfg  = SCHEMES[key]
        data = scheme_data[key]
        avgs = [data.get(r, (0, 0))[0] for r in ROUNDS]
        stds = [data.get(r, (0, 0))[1] for r in ROUNDS]

        bars = ax.bar(
            x + offset, avgs, width,
            yerr=stds, capsize=4,
            color=cfg["color"], alpha=0.85,
            label=cfg["label"],
            error_kw={"elinewidth": 1.2, "capthick": 1.2},
        )

        # Value labels
        for bar, val, std in zip(bars, avgs, stds):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(stds) * 0.08 + 0.3,
                    f"{val:.1f}",
                    ha="center", va="bottom", fontsize=7.5, color="black",
                )

    # ── Annotate Round 3 savings ─────────────────────────────────────────────
    r3_idx    = ROUNDS.index("Round 3")
    base_mJ   = scheme_data.get("Base", {}).get("Round 3", (0, 0))[0]
    prop_mJ   = scheme_data.get("Proposed", {}).get("Round 3", (0, 0))[0]
    if base_mJ > 0 and prop_mJ > 0:
        saving_pct = (base_mJ - prop_mJ) / base_mJ * 100
        ymax = max(
            scheme_data.get("Base", {}).get("Enrollment", (0, 0))[0],
            scheme_data.get("Proposed", {}).get("Enrollment", (0, 0))[0],
        )
        ax.annotate(
            f"−{saving_pct:.1f}% energy\n(re-auth only\nvs re-enroll)",
            xy=(r3_idx - width / 2, base_mJ),
            xytext=(r3_idx + 0.7, base_mJ + ymax * 0.08),
            fontsize=8.5,
            color="#1f77b4",
            arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=1.3),
        )

    # ── Note about Base Round 4 ──────────────────────────────────────────────
    r4_idx = ROUNDS.index("Round 4")
    if "Proposed" in scheme_data and "Round 4" in scheme_data["Proposed"]:
        prop_r4 = scheme_data["Proposed"]["Round 4"][0]
        ax.text(
            r4_idx + width / 2, prop_r4 + 1.5,
            "✓ Confirmed\nresync",
            ha="center", va="bottom", fontsize=7, color="#1f77b4",
        )
    if "Base" not in scheme_data or "Round 4" not in scheme_data.get("Base", {}):
        ax.text(
            r4_idx - width / 2, 2,
            "N/A\n(ts₂ mismatch)",
            ha="center", va="bottom", fontsize=6.5, color="#888888",
        )

    ax.set_xlabel("Protocol Round", fontsize=11)
    ax.set_ylabel("Per-Device Energy (mJ)", fontsize=11)
    # chart title removed (figure caption describes it)
    ax.set_xticks(x)
    ax.set_xticklabels(ROUND_XLABELS, fontsize=9)
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_ylim(bottom=0)

    plt.tight_layout()

    out_path = os.path.join(OUT_DIR, "desync_comparison.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.02)
    print(f"  Saved: {out_path}")

    paper_path = os.path.join(PAPER_DIR, "fig_sim_desync.png")
    shutil.copy2(out_path, paper_path)
    print(f"  Copied: {paper_path}")

    plt.close()

    # ── Print summary table ──────────────────────────────────────────────────
    print("\n  Energy summary (mJ per device, avg ± std):")
    print(f"  {'Round':<12} {'Base':>16} {'Proposed':>16}")
    for r in ROUNDS:
        b = scheme_data.get("Base",     {}).get(r, (None, None))
        p = scheme_data.get("Proposed", {}).get(r, (None, None))
        bs = f"{b[0]:.2f} ± {b[1]:.2f}" if b[0] else "N/A"
        ps = f"{p[0]:.2f} ± {p[1]:.2f}" if p[0] else "N/A"
        print(f"  {r:<12} {bs:>16} {ps:>16}")
    print()


if __name__ == "__main__":
    main()
