#!/usr/bin/env python3
"""
plot_auth_keyex.py — simple bar chart (no error bars / CI) of the
Authentication & Key-Exchange phase cost per scheme, recomputed from the
pinned-governor run data. Output: Authentication&KeyExchange_HW.png
"""
import os, glob, json
import statistics as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "Authentication&KeyExchange_HW.png")
PAPER_OUT = os.path.normpath(os.path.join(HERE, "..", "..", "Paper", "fig_hw_comparison.png"))

# label -> (folder, energy-keys, time-keys)
SPECS = [
    ("Proposed",   "Proposed", ["auth_energy_j"],               ["auth_s"]),
    ("DAuth", "DAuth",    ["auth_energy_j"],               ["auth_s"]),
    ("LAAKA",      "LAAKA",    ["auth_energy_j", "ack_energy_j"],["auth_s", "ack_s"]),
    ("Zhou",       "Zhou",     ["auth_energy_j"],               ["auth_s"]),
]
COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6",
           "LAAKA": "#B85C2C", "Zhou": "#3A7D44"}
HATCHES = {"Proposed": "///", "DAuth": "...", "LAAKA": "\\\\", "Zhou": "xxx"}


def median_phase(folder, ek, tk):
    runs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(HERE, folder, "results", "run_0*.json")))]
    es = [st.mean(sum(r[k] for k in ek) for r in d["rounds"]) for d in runs]
    ts = [st.mean(sum(r[k] for k in tk) for r in d["rounds"]) for d in runs]
    return st.median(es), st.median(ts)


def main():
    labels = [s[0] for s in SPECS]
    E, T = [], []
    for label, folder, ek, tk in SPECS:
        e, t = median_phase(folder, ek, tk)
        E.append(e); T.append(t)
        print(f"{label:11}: {e:.4f} J / {t:.4f} s")

    x = np.arange(len(labels))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 16})
    fig, (axe, axt) = plt.subplots(1, 2, figsize=(11, 4.6))

    for ax, vals, ylabel, title, fmt in [
        (axe, E, "Energy (J)", "(a)", "{:.4f}"),
        (axt, T, "Time (s)",   "(b)", "{:.4f}"),
    ]:
        for i, lab in enumerate(labels):
            ax.bar(i, vals[i], width=0.6, facecolor="none", edgecolor=COLORS[lab],
                   hatch=HATCHES[lab], linewidth=1.8, zorder=3)
            ax.text(i, vals[i] + max(vals) * 0.02, fmt.format(vals[i]),
                    ha="center", va="bottom", fontsize=14, fontweight="normal", color=COLORS[lab])
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=15)
        ax.set_ylabel(ylabel, fontsize=16, fontweight="normal")
        ax.set_title(title, fontsize=15, fontweight="normal", pad=8)
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.set_ylim(0, max(vals) * 1.25)

    fig.tight_layout()
    fig.savefig(OUT, dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(PAPER_OUT, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", OUT)
    print("Saved:", PAPER_OUT)


if __name__ == "__main__":
    main()
