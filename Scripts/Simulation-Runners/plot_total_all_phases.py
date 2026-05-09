"""
plot_total_all_phases.py
Total energy and CPU time across ALL three phases (Enrollment + Auth + Key Exchange)
for Revised-Anonymity, LAAKA, and Zhou.

Produces one figure: side-by-side bars (energy left, CPU right).
Error bars = 95% Confidence Interval.
"""
import csv, os, math, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OUT_DIR = os.path.join(BASE, "Results", "Charts", "Revised-vs-LAAKA-vs-Zhou")
os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Style — matches plot_network_variation.py charts 12 & 13
# ─────────────────────────────────────────────────────────────────────────────
_CHART_STYLE = {
    "font.family":       "DejaVu Sans",
    "font.size":         10,
    "axes.titlesize":    12,
    "axes.titleweight":  "normal",
    "axes.labelsize":    10,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   10,
    "ytick.labelsize":   9,
    "xtick.major.size":  0,
    "legend.fontsize":   9,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

COLORS  = ["#2C6FAC", "#B85C2C", "#3A7D44"]   # muted steel blue, terracotta, forest green

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def load(path, id_col, cpu_col, en_col):
    rows = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows[int(r[id_col])] = {"cpu": float(r[cpu_col]),
                                        "en":  float(r[en_col])}
            except (ValueError, KeyError):
                pass
    return rows

def ci95(lst):
    n = len(lst)
    return 1.96 * statistics.stdev(lst) / math.sqrt(n) if n > 1 else 0

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
RA_DIR = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
ra_enr   = load(os.path.join(RA_DIR, "enroll-results.csv"), "Device",    "CPU_s",      "Energy_J")
ra_auth  = load(os.path.join(RA_DIR, "auth-results.csv"),   "Device",    "CPU_s",      "Energy_J")
ra_keyex = load(os.path.join(RA_DIR, "keyex-results.csv"),  "Device",    "CPU_s",      "Energy_J")

LK_DIR = os.path.join(BASE, "Results", "CSV-Data", "LAAKA")
lk_enr   = load(os.path.join(LK_DIR, "enroll-results.csv"), "Device_ID", "CPU_Time_s", "Energy_J")
lk_auth  = load(os.path.join(LK_DIR, "auth-results.csv"),   "Device_ID", "CPU_Time_s", "Energy_J")
lk_keyex = load(os.path.join(LK_DIR, "keyex-results.csv"),  "Device_ID", "CPU_Time_s", "Energy_J")

zh_raw = {}
with open(os.path.join(BASE, "Zhou-Scheme", "zhou-auth-results.csv"), newline="") as f:
    for r in csv.DictReader(f, skipinitialspace=True):
        try:
            zh_raw[int(r["Device_ID"])] = {
                "cpu":        float(r["Avg_CPU_s"]),
                "enroll_cpu": float(r.get("Enroll_CPU_s", 0)),
                "en":         float(r["Avg_Energy_J"]) + float(r["Enroll_Energy_J"])
            }
        except (ValueError, KeyError):
            pass

# ─────────────────────────────────────────────────────────────────────────────
# Per-device totals (only devices present in ALL phases of that scheme)
# ─────────────────────────────────────────────────────────────────────────────
ra_ids = sorted(set(ra_enr) & set(ra_auth) & set(ra_keyex))
ra_en  = [(ra_enr[i]["en"] + ra_auth[i]["en"] + ra_keyex[i]["en"]) * 1000 for i in ra_ids]
ra_cpu = [ ra_enr[i]["cpu"] + ra_auth[i]["cpu"] + ra_keyex[i]["cpu"]       for i in ra_ids]

lk_ids = sorted(set(lk_enr) & set(lk_auth) & set(lk_keyex))
lk_en  = [(lk_enr[i]["en"] + lk_auth[i]["en"] + lk_keyex[i]["en"]) * 1000 for i in lk_ids]
lk_cpu = [ lk_enr[i]["cpu"] + lk_auth[i]["cpu"] + lk_keyex[i]["cpu"]       for i in lk_ids]

zh_ids = sorted(zh_raw)
zh_en  = [zh_raw[i]["en"]  * 1000 for i in zh_ids]
zh_cpu = [zh_raw[i]["cpu"] + zh_raw[i]["enroll_cpu"] for i in zh_ids]

# ─────────────────────────────────────────────────────────────────────────────
# Summary stats
# ─────────────────────────────────────────────────────────────────────────────
def stats(lst):
    return statistics.mean(lst), ci95(lst), len(lst)

RA  = {"en": stats(ra_en),  "cpu": stats(ra_cpu)}
LK  = {"en": stats(lk_en),  "cpu": stats(lk_cpu)}
ZH  = {"en": stats(zh_en),  "cpu": stats(zh_cpu)}

schemes = ["Revised-\nAnonymity", "LAAKA", "Zhou"]
data    = [RA, LK, ZH]

# ─────────────────────────────────────────────────────────────────────────────
# Figure: 1 row × 2 panels
# ─────────────────────────────────────────────────────────────────────────────
def _apply_axes_style(ax, ylabel, xlabel=None):
    ax.set_ylabel(ylabel, labelpad=8)
    if xlabel:
        ax.set_xlabel(xlabel, labelpad=8)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")

CI_PATCH = mpatches.Patch(facecolor="none", edgecolor="#888888",
                           linewidth=1.0, label="Error bars = 95% CI")

x = np.arange(len(schemes))
w = 0.45

with plt.rc_context(_CHART_STYLE):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 7))
    fig.patch.set_facecolor("white")
    fig.suptitle(
        "Per-Device Mean Total Cost — All 3 Phases\n"
        "(Enrollment + Authentication + Key Exchange)   |   COOJA Simulation",
        color="#222222", y=1.02,
    )

    def draw_panel(ax, metric, ylabel, unit, decimals=2, note=None):
        vals = [d[metric][0] for d in data]
        cis  = [d[metric][1] for d in data]
        ns   = [d[metric][2] for d in data]

        bars = ax.bar(x, vals, width=w, color=COLORS,
                      edgecolor="white", linewidth=0.8, alpha=0.88)
        ax.errorbar(x, vals, yerr=cis, fmt="none", capsize=4,
                    elinewidth=1.2, ecolor="#888888")

        top = max(v + c for v, c in zip(vals, cis))
        ax.set_ylim(0, top * 1.42)

        fmt = f"{{:.{decimals}f}}"
        for bar, v, ci_v in zip(bars, vals, cis):
            cx = bar.get_x() + bar.get_width() / 2
            base = bar.get_height() + ci_v + top * 0.03
            ax.text(cx, base,
                    fmt.format(v) + f" {unit}",
                    ha="center", va="bottom", fontsize=10.5,
                    fontweight="bold", color="#222222")
            ax.text(cx, base + top * 0.045,
                    f"± {fmt.format(ci_v)} {unit}",
                    ha="center", va="bottom", fontsize=8.5, color="#555555")

        ax.set_xticks(x)
        ax.set_xticklabels(schemes)
        _apply_axes_style(ax, ylabel)

        if note:
            ax.text(0.5, -0.12, note, transform=ax.transAxes,
                    ha="center", fontsize=8, color="#666666", style="italic")

    draw_panel(ax1, "en",  "Per-Device Mean Total Energy (mJ)", "mJ", decimals=2,
               note="Zhou: Enrollment + Auth energy  (Key Exchange is included in Auth)")
    draw_panel(ax2, "cpu", "Per-Device Mean Total CPU Time (s)", "s", decimals=4,
               note="Zhou CPU: Enrollment + Auth  (Key Exchange included in Auth phase)")

    scheme_handles = [mpatches.Patch(color=c, alpha=0.88, label=s.replace("\n", "-"))
                      for c, s in zip(COLORS, schemes)]
    scheme_handles.append(CI_PATCH)
    fig.legend(handles=scheme_handles,
               loc="lower center", bbox_to_anchor=(0.5, -0.07),
               ncol=len(scheme_handles),
               frameon=True, framealpha=0.92, edgecolor="#dddddd")

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "18_total_all_phases.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved: 18_total_all_phases.png")

# ─────────────────────────────────────────────────────────────────────────────
# Console summary
# ─────────────────────────────────────────────────────────────────────────────
print()
print("="*65)
print("TOTAL COST — All 3 Phases  (mean ± 95% CI)")
print("="*65)
print(f"{'Scheme':<22} {'Energy (mJ)':>14}  {'± CI':>8}   {'CPU (s)':>10}  {'± CI':>8}   n")
print("-"*65)
for name, d in zip(["Revised-Anonymity", "LAAKA", "Zhou"], data):
    em, ec, en = d["en"]
    cm, cc, cn = d["cpu"]
    print(f"  {name:<20} {em:>14.2f}  {ec:>8.2f}   {cm:>10.4f}  {cc:>8.4f}   {en}")
print()
print("  * LAAKA n=20: all 20 devices completed auth")
print("  * Zhou CPU excludes enrollment (not separately recorded)")
print(f"\nSaved to: {OUT_DIR}")
