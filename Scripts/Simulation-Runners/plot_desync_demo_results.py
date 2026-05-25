"""
plot_desync_demo_results.py
Generate paper-style charts from actual COOJA desync-demo simulation results.

Reads:
  Results/Desync-Demo/Proposed/desync_results.csv
  Results/Desync-Demo/Base/desync_results.csv

Produces (Results/Desync-Demo/Charts/):
  01_energy_per_round.png   — per-device mean energy (mJ) per round, both schemes
  02_cpu_per_round.png      — per-device mean CPU time (s) per round, both schemes
  03_total_energy.png       — total energy (all devices) per round, both schemes
  04_total_cpu.png          — total CPU time (all devices) per round, both schemes
  05_recovery_overhead.png  — Before vs After packet-loss comparison (2×2 grouped bars)

Usage:
  python3 plot_desync_demo_results.py
  python3 plot_desync_demo_results.py --show
"""

import os, csv, argparse, math, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

REPO    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
SRC_DIR = os.path.join(REPO, "Results", "Desync-Demo")
OUT_DIR = os.path.join(SRC_DIR, "Charts")

ROUNDS = ["ENROLL", "ROUND1", "ROUND2", "ROUND3", "ROUND4"]
ROUND_LABELS = {
    "ENROLL": "Enrollment",
    "ROUND1": "Round 1\n(Normal Auth)",
    "ROUND2": "Round 2\n(Pkt Drop)",
    "ROUND3": "Round 3\n(Recovery)",
    "ROUND4": "Round 4\n(Post-Recovery)",
}

C_PROPOSED = "#2C6FAC"
C_BASE     = "#B85C2C"
H_PROPOSED = "///"
H_BASE     = "\\\\"

_CHART_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    16,
    "axes.titleweight":  "bold",
    "axes.labelsize":    17,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   13,
    "ytick.labelsize":   13,
    "xtick.major.size":  0,
    "legend.fontsize":   12,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}


# ── Data loading ──────────────────────────────────────────────────────────────
def load_csv(scheme):
    """
    Returns {round_label: {"vals": [per-device-mean per seed], "n_devices": int}}
    Per-seed per-device mean = mean over all device nodes for that seed.
    """
    path = os.path.join(SRC_DIR, scheme, "desync_results.csv")
    if not os.path.isfile(path):
        print(f"  WARNING: {path} not found — skipping {scheme}")
        return None

    # seed → round → list of values (one per device node)
    raw = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seed  = int(row["Seed"])
            node  = int(row["Node"])
            rnd   = row["Round"]
            cpu   = float(row["CPU_s"])
            energy= float(row["Energy_mJ"])
            raw.setdefault(seed, {}).setdefault(rnd, {}).setdefault(node, {})
            raw[seed][rnd][node] = {"cpu": cpu, "energy": energy}

    result = {}
    for rnd in ROUNDS:
        seed_means_energy = []
        seed_means_cpu    = []
        n_dev_set         = set()
        for seed, rounds in raw.items():
            if rnd not in rounds:
                continue
            nodes = rounds[rnd]
            n_dev_set.add(len(nodes))
            energies = [v["energy"] for v in nodes.values()]
            cpus     = [v["cpu"]    for v in nodes.values()]
            seed_means_energy.append(statistics.mean(energies))
            seed_means_cpu.append(statistics.mean(cpus))
        if seed_means_energy:
            result[rnd] = {
                "energy_vals": seed_means_energy,
                "cpu_vals":    seed_means_cpu,
                "n_devices":   max(n_dev_set) if n_dev_set else 0,
            }
    return result


def agg(vals):
    """mean + 95% CI (t-based approx via 1.96*std/sqrt(n))"""
    if not vals:
        return 0.0, 0.0
    n = len(vals)
    mu = statistics.mean(vals)
    if n < 2:
        return mu, 0.0
    sd = statistics.stdev(vals)
    ci = 1.96 * sd / math.sqrt(n)
    return mu, ci


# ── Chart helpers ─────────────────────────────────────────────────────────────
def _save(fig, fname, show):
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, fname)
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    plt.close(fig)
    print(f"  Saved: {fname}")


def _annotate_bars(ax, positions, vals, cis, max_val, fmt):
    for xi, (v, ci) in enumerate(zip(vals, cis)):
        ax.text(positions[xi], v + ci + max_val * 0.015,
                f"{v:{fmt}}",
                ha="center", va="bottom",
                fontsize=13, fontweight="bold", color="#222222")


# ── Chart 1 & 2: per-device mean per round (grouped bars) ────────────────────
def chart_per_round(data_p, data_b, metric, ylabel, title, fname, show):
    """Grouped bar: for each round, two bars (Proposed, Base)."""
    rounds_avail = [r for r in ROUNDS
                    if (data_p and r in data_p) or (data_b and r in data_b)]
    n = len(rounds_avail)
    x = np.arange(n)
    w = 0.32

    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("white")

        all_top = []
        for si, (label, data, color, hatch) in enumerate([
            ("Proposed", data_p, C_PROPOSED, H_PROPOSED),
            ("Base",     data_b, C_BASE,     H_BASE),
        ]):
            vals, cis = [], []
            for rnd in rounds_avail:
                if data and rnd in data:
                    v, ci = agg(data[rnd][f"{metric}_vals"])
                else:
                    v, ci = 0.0, 0.0
                vals.append(v)
                cis.append(ci)

            offsets = x + (si - 0.5) * w
            ax.bar(offsets, vals, w,
                   facecolor="none", edgecolor=color,
                   hatch=hatch, linewidth=1.5,
                   yerr=cis, capsize=5,
                   error_kw={"linewidth": 1.5, "ecolor": color},
                   label=label)
            all_top.extend(v + ci for v, ci in zip(vals, cis))

        max_val = max(all_top) if all_top else 1
        fmt = ".2f" if metric == "cpu" else ".1f"

        # Re-draw annotations
        for si, (label, data, color, hatch) in enumerate([
            ("Proposed", data_p, C_PROPOSED, H_PROPOSED),
            ("Base",     data_b, C_BASE,     H_BASE),
        ]):
            vals, cis = [], []
            for rnd in rounds_avail:
                if data and rnd in data:
                    v, ci = agg(data[rnd][f"{metric}_vals"])
                else:
                    v, ci = 0.0, 0.0
                vals.append(v)
                cis.append(ci)
            offsets = x + (si - 0.5) * w
            _annotate_bars(ax, offsets, vals, cis, max_val, fmt)

        ax.set_xticks(x)
        ax.set_xticklabels([ROUND_LABELS[r] for r in rounds_avail],
                           rotation=0, ha="center", fontsize=12)
        ax.set_ylabel(ylabel, labelpad=12, fontsize=17, fontweight="bold")
        ax.set_title(title, fontsize=16, fontweight="bold", pad=14, color="#222222")
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.set_ylim(0, max_val * 1.28)
        ax.legend(loc="upper left", framealpha=0.9, edgecolor="#dddddd",
                  handlelength=2.0, handleheight=1.4)

        fig.tight_layout()
        _save(fig, fname, show)


# ── Chart 3 & 4: total (all devices) per round ───────────────────────────────
def chart_total_per_round(data_p, data_b, metric, ylabel, title, fname, show):
    """Total across all devices per round."""
    rounds_avail = [r for r in ROUNDS
                    if (data_p and r in data_p) or (data_b and r in data_b)]
    n = len(rounds_avail)
    x = np.arange(n)
    w = 0.32

    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("white")

        all_top = []
        for si, (label, data, color, hatch) in enumerate([
            ("Proposed", data_p, C_PROPOSED, H_PROPOSED),
            ("Base",     data_b, C_BASE,     H_BASE),
        ]):
            vals, cis = [], []
            for rnd in rounds_avail:
                if data and rnd in data:
                    n_dev = data[rnd]["n_devices"]
                    v, ci = agg(data[rnd][f"{metric}_vals"])
                    v  *= n_dev
                    ci *= n_dev
                else:
                    v, ci = 0.0, 0.0
                vals.append(v)
                cis.append(ci)

            offsets = x + (si - 0.5) * w
            ax.bar(offsets, vals, w,
                   facecolor="none", edgecolor=color,
                   hatch=hatch, linewidth=1.5,
                   yerr=cis, capsize=5,
                   error_kw={"linewidth": 1.5, "ecolor": color},
                   label=label)
            all_top.extend(v + ci for v, ci in zip(vals, cis))

        max_val = max(all_top) if all_top else 1
        fmt = ".2f" if metric == "cpu" else ".1f"

        for si, (label, data, color, hatch) in enumerate([
            ("Proposed", data_p, C_PROPOSED, H_PROPOSED),
            ("Base",     data_b, C_BASE,     H_BASE),
        ]):
            vals, cis = [], []
            for rnd in rounds_avail:
                if data and rnd in data:
                    n_dev = data[rnd]["n_devices"]
                    v, ci = agg(data[rnd][f"{metric}_vals"])
                    v  *= n_dev
                    ci *= n_dev
                else:
                    v, ci = 0.0, 0.0
                vals.append(v)
                cis.append(ci)
            offsets = x + (si - 0.5) * w
            _annotate_bars(ax, offsets, vals, cis, max_val, fmt)

        ax.set_xticks(x)
        ax.set_xticklabels([ROUND_LABELS[r] for r in rounds_avail],
                           rotation=0, ha="center", fontsize=12)
        ax.set_ylabel(ylabel, labelpad=12, fontsize=17, fontweight="bold")
        ax.set_title(title, fontsize=16, fontweight="bold", pad=14, color="#222222")
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.set_ylim(0, max_val * 1.28)
        ax.legend(loc="upper left", framealpha=0.9, edgecolor="#dddddd",
                  handlelength=2.0, handleheight=1.4)

        fig.tight_layout()
        _save(fig, fname, show)


# ── Chart 5: Before vs After loss comparison (4-bar) ─────────────────────────
def chart_recovery_overhead(data_p, data_b, metric, ylabel, title, fname, show):
    """
    4-bar chart (same layout as plot_desync_proposed_vs_base.py but using
    actual measured values instead of analytic estimates).

    Before = ENROLL + ROUND1  (a full normal session prior to drop)
    After  = ROUND3           (the recovery session)
    """
    H_BEFORE = "///"
    H_AFTER  = "\\\\"

    def before_after(data):
        if not data:
            return (0.0, 0.0), (0.0, 0.0)
        # Before = mean of (enroll + round1) per seed
        before_vals = []
        after_vals  = []
        seeds_e  = set(range(len(data.get("ENROLL",  {}).get(f"{metric}_vals", []))))
        seeds_r1 = set(range(len(data.get("ROUND1",  {}).get(f"{metric}_vals", []))))
        seeds_r3 = set(range(len(data.get("ROUND3",  {}).get(f"{metric}_vals", []))))
        n = min(len(data.get("ENROLL",  {}).get(f"{metric}_vals", [])),
                len(data.get("ROUND1",  {}).get(f"{metric}_vals", [])),
                len(data.get("ROUND3",  {}).get(f"{metric}_vals", [])))
        for i in range(n):
            e  = data["ENROLL"][f"{metric}_vals"][i]
            r1 = data["ROUND1"][f"{metric}_vals"][i]
            r3 = data["ROUND3"][f"{metric}_vals"][i]
            before_vals.append(e + r1)
            after_vals.append(r3)
        return agg(before_vals), agg(after_vals)

    (pb_v, pb_ci), (pa_v, pa_ci) = before_after(data_p)
    (bb_v, bb_ci), (ba_v, ba_ci) = before_after(data_b)

    vals    = [pb_v, pa_v, bb_v, ba_v]
    cis     = [pb_ci, pa_ci, bb_ci, ba_ci]
    colors  = [C_PROPOSED, C_PROPOSED, C_BASE, C_BASE]
    hatches = [H_BEFORE, H_AFTER, H_BEFORE, H_AFTER]
    pos     = [0, 1, 2.6, 3.6]
    w       = 0.7
    xlabels = [
        "Proposed\nBefore loss",
        "Proposed\nAfter loss",
        "Base\nBefore loss",
        "Base\nAfter loss",
    ]

    fmt = ".3f" if metric == "cpu" else ".1f"
    max_val = max(v + ci for v, ci in zip(vals, cis)) if vals else 1

    with plt.rc_context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(11, 7))
        fig.patch.set_facecolor("white")

        for xi, (v, ci, color, hatch) in enumerate(zip(vals, cis, colors, hatches)):
            ax.bar(pos[xi], v, w,
                   facecolor="none", edgecolor=color,
                   hatch=hatch, linewidth=1.5,
                   yerr=ci, capsize=6,
                   error_kw={"linewidth": 1.5, "ecolor": color})
            ax.text(pos[xi], v + ci + max_val * 0.015,
                    f"{v:{fmt}}",
                    ha="center", va="bottom",
                    fontsize=17, fontweight="bold", color="#222222")

        ax.set_xticks(pos)
        ax.set_xticklabels(xlabels, rotation=0, ha="center", fontsize=15)
        ax.set_ylabel(ylabel, labelpad=14, fontsize=19, fontweight="bold")
        ax.set_title(title, fontsize=18, fontweight="bold", pad=14, color="#222222")
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.set_ylim(0, max_val * 1.22)

        legend_handles = [
            mpatches.Patch(facecolor="none", edgecolor=C_PROPOSED,
                           hatch=H_BEFORE, linewidth=1.5,
                           label="Proposed — Before loss\n(Enrol + Normal Auth)"),
            mpatches.Patch(facecolor="none", edgecolor=C_PROPOSED,
                           hatch=H_AFTER,  linewidth=1.5,
                           label="Proposed — After loss\n(Dual-state Recovery)"),
            mpatches.Patch(facecolor="none", edgecolor=C_BASE,
                           hatch=H_BEFORE, linewidth=1.5,
                           label="Base — Before loss\n(Enrol + Normal Auth)"),
            mpatches.Patch(facecolor="none", edgecolor=C_BASE,
                           hatch=H_AFTER,  linewidth=1.5,
                           label="Base — After loss\n(Re-Enrol + Auth)"),
        ]
        ax.legend(handles=legend_handles, loc="upper left",
                  fontsize=12, framealpha=0.88,
                  edgecolor="#dddddd", handlelength=2.0, handleheight=1.4)

        fig.tight_layout()
        _save(fig, fname, show)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    data_p = load_csv("Proposed")
    data_b = load_csv("Base")

    if data_p is None and data_b is None:
        print("No simulation results found. Run run_desync_demo.py first.")
        return

    print("Generating per-device mean energy per round...")
    chart_per_round(
        data_p, data_b, "energy",
        "Avg Energy per Device (mJ)",
        "Per-Device Mean Energy — Desync Demo\n(Deliberate Phase 3 Packet Drop)",
        "01_energy_per_round.png", args.show,
    )

    print("Generating per-device mean CPU per round...")
    chart_per_round(
        data_p, data_b, "cpu",
        "Avg CPU Time per Device (s)",
        "Per-Device Mean CPU Time — Desync Demo\n(Deliberate Phase 3 Packet Drop)",
        "02_cpu_per_round.png", args.show,
    )

    print("Generating total energy per round (all devices)...")
    chart_total_per_round(
        data_p, data_b, "energy",
        "Total Energy — All Devices (mJ)",
        "Total Energy vs Round — Desync Demo",
        "03_total_energy.png", args.show,
    )

    print("Generating total CPU per round (all devices)...")
    chart_total_per_round(
        data_p, data_b, "cpu",
        "Total CPU Time — All Devices (s)",
        "Total CPU Time vs Round — Desync Demo",
        "04_total_cpu.png", args.show,
    )

    print("Generating recovery overhead comparison chart (energy)...")
    chart_recovery_overhead(
        data_p, data_b, "energy",
        "Avg Energy per Device (mJ)",
        "Energy Cost: Before vs After (mH, ts2) Loss — Measured",
        "05_recovery_overhead_energy.png", args.show,
    )

    print("Generating recovery overhead comparison chart (CPU)...")
    chart_recovery_overhead(
        data_p, data_b, "cpu",
        "Avg CPU Time per Device (s)",
        "CPU Time: Before vs After (mH, ts2) Loss — Measured",
        "06_recovery_overhead_cpu.png", args.show,
    )

    print(f"\nAll charts → {OUT_DIR}")


if __name__ == "__main__":
    main()
