"""
plot_compute_miracl.py  (self-contained, lives in Hardware/MIRACLE/)

Compute-only hardware analysis: pure cryptographic computation measured LIVE on
an RPi 4B via MIRACL Core (NIST P-256), running each scheme's actual operation
sequence (no TCP). NOT used in the paper — exploratory/archive only.

Reads:  run_*.csv  (this directory) from scheme_compute_bench.c
Writes: hw_compute_miracl.png, compute_miracl_aggregate.json  (this directory)
Energy = compute_time * 3.8 W (3800 mW), matching the end-to-end hardware model.
"""
import os
import glob
import csv
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE   = os.path.dirname(os.path.abspath(__file__))
OUTPNG = os.path.join(HERE, "hw_compute_miracl.png")
OUTJSN = os.path.join(HERE, "compute_miracl_aggregate.json")

POWER_W = 3.8
SCHEMES = ["Proposed", "DAuth", "LAAKA", "Zhou"]
PHASE   = "auth"        # per-round recurring compute

COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6",
           "LAAKA":    "#B85C2C", "Zhou":  "#3A7D44"}
HATCHES = {"Proposed": "///", "DAuth": "...", "LAAKA": "\\\\", "Zhou": "xxx"}
X       = np.arange(len(SCHEMES))
_STYLE  = {
    "font.family": "DejaVu Sans", "font.size": 15,
    "axes.titlesize": 18, "axes.titleweight": "bold", "axes.labelsize": 19,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.7,
    "xtick.labelsize": 15, "ytick.labelsize": 15, "xtick.major.size": 0,
    "grid.color": "#e5e5e5", "grid.linewidth": 0.6,
}


def load():
    runs = sorted(glob.glob(os.path.join(HERE, "run_*.csv")))
    if not runs:
        raise SystemExit(f"No run_*.csv in {HERE}")
    acc = {s: {"auth": [], "enroll": []} for s in SCHEMES}
    for f in runs:
        with open(f, newline="") as fh:
            for row in csv.DictReader(fh):
                s, ph = row["scheme"], row["phase"]
                if s in acc and ph in acc[s]:
                    acc[s][ph].append(float(row["mean_ms"]))
    print(f"Loaded {len(runs)} runs")
    return acc, len(runs)


def aggregate(acc):
    out = {}
    for s in SCHEMES:
        for ph in ("auth", "enroll"):
            v = np.array(acc[s][ph])
            t_ms = float(v.mean())
            t_sd = float(v.std(ddof=1)) if len(v) > 1 else 0.0
            out.setdefault(s, {})[ph] = {
                "time_ms": round(t_ms, 6), "time_sd_ms": round(t_sd, 6),
                "energy_mj": round(t_ms * POWER_W, 6),
                "energy_sd_mj": round(t_sd * POWER_W, 6),
            }
    return out


def draw(ax, agg, key, sd, ylabel, title):
    means = [agg[s][PHASE][key] for s in SCHEMES]
    sds   = [agg[s][PHASE][sd] for s in SCHEMES]
    for i, s in enumerate(SCHEMES):
        ax.bar(i, means[i], width=0.45, facecolor="none", edgecolor=COLORS[s],
               hatch=HATCHES[s], linewidth=1.5, zorder=3)
        ax.errorbar(i, means[i], yerr=sds[i], fmt="none", ecolor="#555",
                    elinewidth=1.0, capsize=3, zorder=4)
        ax.text(i, means[i] + max(means) * 0.02, f"{means[i]:.3f}",
                ha="center", va="bottom", fontsize=11, fontweight="bold",
                color=COLORS[s])
    ax.set_xticks(X); ax.set_xticklabels(SCHEMES, fontsize=15)
    ax.set_ylabel(ylabel, fontsize=17, fontweight="bold", labelpad=10)
    ax.set_title(title, fontsize=17, fontweight="bold", pad=10)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True); ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc"); ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, max(means) * 1.25)


def main():
    acc, nruns = load()
    agg = aggregate(acc)
    print(f"\nPer-round (Auth) compute — {POWER_W*1000:.0f} mW, {nruns} runs")
    for s in SCHEMES:
        a = agg[s][PHASE]
        print(f"  {s:<10} {a['time_ms']:.4f} ms -> {a['energy_mj']:.4f} mJ "
              f"(sd {a['time_sd_ms']:.4f} ms)")
    zhou = agg["Zhou"][PHASE]["time_ms"]
    light = max(agg[s][PHASE]["time_ms"] for s in SCHEMES if s != "Zhou")
    ratio = round(zhou / light, 1)
    print(f"\nZhou = {ratio}x the heaviest non-ECC scheme (ECC fuzzy extractor).")

    with open(OUTJSN, "w") as fh:
        json.dump({"power_mw": POWER_W * 1000, "num_runs": nruns,
                   "phase_reported": PHASE, "zhou_vs_light_ratio": ratio,
                   "schemes": agg}, fh, indent=2)
    print("Saved:", OUTJSN)

    with plt.rc_context(_STYLE):
        fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(11, 5))
        draw(ax_e, agg, "energy_mj", "energy_sd_mj", "Compute energy (mJ)", "(a)")
        draw(ax_t, agg, "time_ms", "time_sd_ms", "Compute time (ms)", "(b)")
        fig.suptitle("Per-round cryptographic computation — RPi 4B / MIRACL Core (NIST P-256)",
                     fontsize=14, fontweight="bold", y=1.02)
        fig.tight_layout()
        fig.savefig(OUTPNG, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", OUTPNG)


if __name__ == "__main__":
    main()
