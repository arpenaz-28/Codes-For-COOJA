"""
plot_hw_3charts.py
Produces 3 hardware comparison bar charts from raw run JSON files:

  Chart 1 — Total        : Enrollment + 3 × (Auth+Key+Data) per scheme
  Chart 2 — Auth+Key+Data: avg per round (no enrollment)
  Chart 3 — Auth+Key     : avg per round auth+keyex only (no data, no enrollment)

Each chart is a 2-panel figure: Energy (J) | Time (s)
Output: Hardware/Charts/hw_chart1_total.png
                        hw_chart2_auth_key_data.png
                        hw_chart3_auth_key.png
"""

import os, glob, json, math, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────────
HERE     = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(HERE, "Charts")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Scheme config ──────────────────────────────────────────────────────────────
# ak_key / ak_t_key: the per-round JSON key for Auth+Key energy / time
SCHEME_CFG = {
    "Proposed": {
        "run_dir": os.path.join(HERE, "Proposed", "results"),
        "ak_key":  "ak_energy_j",
        "akt_key": "ak_s",
    },
    "DAuth": {
        "run_dir": os.path.join(HERE, "DAuth", "results"),
        "ak_key":  "ak_energy_j",
        "akt_key": "ak_s",
    },
    "LAAKA": {
        "run_dir": os.path.join(HERE, "LAAKA", "results"),
        "ak_key":  "aa_energy_j",
        "akt_key": "aa_s",
    },
    "Zhou": {
        "run_dir": os.path.join(HERE, "Zhou", "results"),
        "ak_key":  "auth_energy_j",
        "akt_key": "auth_s",
    },
}
SCHEMES   = ["Proposed", "DAuth", "LAAKA", "Zhou"]
NUM_MEAS  = 3   # measured rounds per run (warm-up already discarded)

# ── Style ──────────────────────────────────────────────────────────────────────
COLORS = {
    "Proposed": "#2C6FAC",
    "DAuth":    "#7E5BA6",
    "LAAKA":    "#B85C2C",
    "Zhou":     "#3A7D44",
}
HATCHES = {
    "Proposed": "///",
    "DAuth":    "...",
    "LAAKA":    "\\\\",
    "Zhou":     "xxx",
}
_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         13,
    "axes.titlesize":    15,
    "axes.titleweight":  "bold",
    "axes.labelsize":    14,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   13,
    "ytick.labelsize":   13,
    "xtick.major.size":  0,
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}
BAR_W = 0.45
X     = np.arange(len(SCHEMES))


# ── Data loading ───────────────────────────────────────────────────────────────
def _mean_ci(vals):
    m  = statistics.mean(vals)
    ci = 1.96 * statistics.stdev(vals) / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
    return m, ci


def load_scheme(scheme):
    cfg      = SCHEME_CFG[scheme]
    run_files = sorted(glob.glob(os.path.join(cfg["run_dir"], "run_*.json")))
    if not run_files:
        raise FileNotFoundError(f"No run_*.json in {cfg['run_dir']}")

    per_run = []
    for path in run_files:
        with open(path) as f:
            d = json.load(f)
        enr_e  = d["enrollment"]["energy_j"]
        enr_t  = d["enrollment"]["wall_s"]
        rounds = d["rounds"]
        ak_e   = statistics.mean(r[cfg["ak_key"]]  for r in rounds)
        ak_t   = statistics.mean(r[cfg["akt_key"]] for r in rounds)
        tot_e  = statistics.mean(r["total_energy_j"] for r in rounds)
        tot_t  = statistics.mean(r["total_s"]         for r in rounds)
        per_run.append({
            "enr_e": enr_e, "enr_t": enr_t,
            "ak_e":  ak_e,  "ak_t":  ak_t,
            "tot_e": tot_e, "tot_t": tot_t,
            "grand_e": enr_e + NUM_MEAS * tot_e,
            "grand_t": enr_t + NUM_MEAS * tot_t,
        })

    grand_e_m,  grand_e_ci  = _mean_ci([r["grand_e"] for r in per_run])
    tot_e_m,    tot_e_ci    = _mean_ci([r["tot_e"]   for r in per_run])
    ak_e_m,     ak_e_ci     = _mean_ci([r["ak_e"]    for r in per_run])
    grand_t_m,  grand_t_ci  = _mean_ci([r["grand_t"] for r in per_run])
    tot_t_m,    tot_t_ci    = _mean_ci([r["tot_t"]   for r in per_run])
    ak_t_m,     ak_t_ci     = _mean_ci([r["ak_t"]    for r in per_run])
    return {
        "grand_e": (grand_e_m, grand_e_ci),
        "tot_e":   (tot_e_m,   tot_e_ci),
        "ak_e":    (ak_e_m,    ak_e_ci),
        "grand_t": (grand_t_m, grand_t_ci),
        "tot_t":   (tot_t_m,   tot_t_ci),
        "ak_t":    (ak_t_m,    ak_t_ci),
    }


data = {s: load_scheme(s) for s in SCHEMES}

for s, v in data.items():
    print(f"{s:10s}  grand={v['grand_e'][0]:.4f}J  tot/rnd={v['tot_e'][0]:.4f}J  ak/rnd={v['ak_e'][0]:.4f}J"
          f"  |  {v['grand_t'][0]:.4f}s  {v['tot_t'][0]:.4f}s  {v['ak_t'][0]:.4f}s")


# ── Drawing helper ─────────────────────────────────────────────────────────────
def _draw_panel(ax, means, cis, ylabel, title, fmt):
    max_v = max(means)
    for i, scheme in enumerate(SCHEMES):
        ax.bar(
            i, means[i],
            width=BAR_W,
            facecolor="none",
            edgecolor=COLORS[scheme],
            hatch=HATCHES[scheme],
            linewidth=1.5,
            zorder=3,
        )
        ax.errorbar(i, means[i], yerr=cis[i],
                    fmt="none", ecolor="#333333", elinewidth=1.2,
                    capsize=4, capthick=1.2, zorder=4)
        ax.text(i, means[i] + cis[i] + max_v * 0.025,
                fmt.format(means[i]),
                ha="center", va="bottom", fontsize=10,
                color=COLORS[scheme], fontweight="bold")
    ax.set_xticks(X)
    ax.set_xticklabels(SCHEMES, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=13, fontweight="bold", labelpad=8)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=8)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_ylim(0, (max_v + max(cis)) * 1.30)


def make_chart(e_key, t_key, suptitle, subtitle, fname, e_fmt, t_fmt):
    means_e = [data[s][e_key][0] for s in SCHEMES]
    cis_e   = [data[s][e_key][1] for s in SCHEMES]
    means_t = [data[s][t_key][0] for s in SCHEMES]
    cis_t   = [data[s][t_key][1] for s in SCHEMES]

    with plt.rc_context(_STYLE):
        fig, (ax_e, ax_t) = plt.subplots(1, 2, figsize=(11, 5))
        _draw_panel(ax_e, means_e, cis_e, "Energy (J)", "Energy", e_fmt)
        _draw_panel(ax_t, means_t, cis_t, "Time (s)",   "Time",   t_fmt)
        fig.suptitle(f"{suptitle}\n{subtitle}",
                     fontsize=14, fontweight="bold", y=1.04, color="#222222")
        fig.tight_layout()
        out = os.path.join(OUT_DIR, fname)
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"Saved: {out}")


# ── Chart 1: Total (Enrollment + 3 × Auth+Key+Data) ──────────────────────────
make_chart(
    "grand_e", "grand_t",
    "Chart 1 — Total Cost",
    f"Enrollment + {NUM_MEAS} rounds of Auth+Key+Data  (RPi 4B, 3800 mW)",
    "hw_chart1_total.png",
    "{:.3f} J", "{:.3f} s",
)

# ── Chart 2: Auth+Key+Data per round ─────────────────────────────────────────
make_chart(
    "tot_e", "tot_t",
    "Chart 2 — Auth+Key+Data per Round",
    "Avg per measured round, enrollment excluded  (RPi 4B, 3800 mW)",
    "hw_chart2_auth_key_data.png",
    "{:.3f} J", "{:.4f} s",
)

# ── Chart 3: Auth+Key per round ───────────────────────────────────────────────
make_chart(
    "ak_e", "ak_t",
    "Chart 3 — Auth+Key per Round",
    "Avg per measured round, data & enrollment excluded  (RPi 4B, 3800 mW)",
    "hw_chart3_auth_key.png",
    "{:.3f} J", "{:.4f} s",
)
