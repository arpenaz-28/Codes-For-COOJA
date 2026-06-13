"""
plot_hw_comparison.py
Hardware comparison chart — Proposed, DAuth, LAAKA, Zhou.

Proposed, DAuth : Auth+Key avg (3 runs)
LAAKA, Zhou     : Enrollment + Auth+Key avg (3 runs)

Output: Hardware/Charts/hw_total_comparison.png
"""

import os, glob, json, math, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE     = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(HERE, "Charts")
OUT_FILE = os.path.join(OUT_DIR, "hw_total_comparison.png")
os.makedirs(OUT_DIR, exist_ok=True)

SCHEME_CFG = {
    "Proposed": {"run_dir": os.path.join(HERE, "Proposed", "results"),
                 "ak_e": "ak_energy_j", "ak_t": "ak_s",     "enroll": False},
    "DAuth":    {"run_dir": os.path.join(HERE, "DAuth",    "results"),
                 "ak_e": "ak_energy_j", "ak_t": "ak_s",     "enroll": False},
    "LAAKA":    {"run_dir": os.path.join(HERE, "LAAKA",    "results"),
                 "ak_e": "aa_energy_j", "ak_t": "aa_s",     "enroll": True},
    "Zhou":     {"run_dir": os.path.join(HERE, "Zhou",     "results"),
                 "ak_e": "auth_energy_j", "ak_t": "auth_s", "enroll": True},
}
SCHEMES = ["Proposed", "DAuth", "LAAKA", "Zhou"]


def _mean_ci(vals):
    m  = statistics.mean(vals)
    ci = 1.96 * statistics.stdev(vals) / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
    return m, ci


def load_scheme(scheme):
    cfg   = SCHEME_CFG[scheme]
    files = sorted(glob.glob(os.path.join(cfg["run_dir"], "run_*.json")))
    tot_es, tot_ts = [], []
    for path in files:
        with open(path) as f:
            d = json.load(f)
        ak_e = statistics.mean(r[cfg["ak_e"]] for r in d["rounds"])
        ak_t = statistics.mean(r[cfg["ak_t"]] for r in d["rounds"])
        enr_e = d["enrollment"]["energy_j"] if cfg["enroll"] else 0
        enr_t = d["enrollment"]["wall_s"]   if cfg["enroll"] else 0
        tot_es.append(enr_e + ak_e)
        tot_ts.append(enr_t + ak_t)
    return {"e": _mean_ci(tot_es), "t": _mean_ci(tot_ts)}


data = {s: load_scheme(s) for s in SCHEMES}

for s in SCHEMES:
    print(f"{s:<10}  {data[s]['e'][0]:.4f} J (±{data[s]['e'][1]:.4f})  "
          f"{data[s]['t'][0]:.4f} s (±{data[s]['t'][1]:.4f})")

# ── Style (matches COOJA simulation charts) ────────────────────────────────────
COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6",
           "LAAKA":    "#B85C2C", "Zhou":  "#3A7D44"}
HATCHES = {"Proposed": "///", "DAuth": "...", "LAAKA": "\\\\", "Zhou": "xxx"}
BAR_W   = 0.45
X       = np.arange(len(SCHEMES))
_STYLE  = {
    "font.family":       "DejaVu Sans",
    "font.size":         15,
    "axes.titlesize":    18,
    "axes.titleweight":  "bold",
    "axes.labelsize":    19,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   15,
    "ytick.labelsize":   15,
    "xtick.major.size":  0,
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}


def _draw_panel(ax, metric, ylabel, title, fmt):
    means = [data[s][metric][0] for s in SCHEMES]
    cis   = [data[s][metric][1] for s in SCHEMES]
    max_v = max(means)
    for i, scheme in enumerate(SCHEMES):
        v  = means[i]
        ci = cis[i]
        ax.bar(i, v, width=BAR_W, facecolor="none",
               edgecolor=COLORS[scheme], hatch=HATCHES[scheme],
               linewidth=1.5, zorder=3)
        ax.errorbar(i, v, yerr=ci, fmt="none", ecolor="#333333",
                    elinewidth=1.2, capsize=4, capthick=1.2, zorder=4)
        ax.text(i, v + ci + max_v * 0.025, fmt.format(v),
                ha="center", va="bottom", fontsize=11,
                color=COLORS[scheme], fontweight="bold")
    ax.set_xticks(X)
    ax.set_xticklabels(SCHEMES, fontsize=15)
    ax.set_ylabel(ylabel, fontsize=17, fontweight="bold", labelpad=10)
    ax.set_title(title, fontsize=17, fontweight="bold", pad=10)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, (max_v + max(cis)) * 1.30)


with plt.rc_context(_STYLE):
    fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(11, 5))
    _draw_panel(ax_e, "e", "Energy (J)", "(a)", "{:.3f} J")
    _draw_panel(ax_t, "t", "Time (s)",   "(b)", "{:.3f} s")
    fig.suptitle("Hardware Simulation",
                 fontsize=16, fontweight="bold", y=1.04, color="#222222")
    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", OUT_FILE)
