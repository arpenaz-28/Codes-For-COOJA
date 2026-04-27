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

BASE    = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
OUT_DIR = os.path.join(BASE, "Results", "Charts", "Revised-vs-LAAKA-vs-Zhou")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
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

# ── Load data ─────────────────────────────────────────────────────────────────
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
    for r in csv.DictReader(f):
        try:
            zh_raw[int(r["Device_ID"])] = {
                "cpu":        float(r["Avg_CPU_s"]),
                "enroll_cpu": float(r.get("Enroll_CPU_s", 0)),
                "en":         float(r["Avg_Energy_J"]) + float(r["Enroll_Energy_J"])
            }
        except (ValueError, KeyError):
            pass

# ── Per-device totals (only devices present in ALL phases of that scheme) ─────
ra_ids = sorted(set(ra_enr) & set(ra_auth) & set(ra_keyex))
ra_en  = [(ra_enr[i]["en"] + ra_auth[i]["en"] + ra_keyex[i]["en"]) * 1000 for i in ra_ids]
ra_cpu = [ ra_enr[i]["cpu"] + ra_auth[i]["cpu"] + ra_keyex[i]["cpu"]       for i in ra_ids]

lk_ids = sorted(set(lk_enr) & set(lk_auth) & set(lk_keyex))
lk_en  = [(lk_enr[i]["en"] + lk_auth[i]["en"] + lk_keyex[i]["en"]) * 1000 for i in lk_ids]
lk_cpu = [ lk_enr[i]["cpu"] + lk_auth[i]["cpu"] + lk_keyex[i]["cpu"]       for i in lk_ids]

zh_ids = sorted(zh_raw)
zh_en  = [zh_raw[i]["en"]  * 1000 for i in zh_ids]   # enroll + auth energy combined
zh_cpu = [zh_raw[i]["cpu"] + zh_raw[i]["enroll_cpu"] for i in zh_ids]  # enroll + auth CPU

# ── Summary stats ─────────────────────────────────────────────────────────────
def stats(lst):
    return statistics.mean(lst), ci95(lst), len(lst)

RA  = {"en": stats(ra_en),  "cpu": stats(ra_cpu)}
LK  = {"en": stats(lk_en),  "cpu": stats(lk_cpu)}
ZH  = {"en": stats(zh_en),  "cpu": stats(zh_cpu)}

schemes = ["Revised-\nAnonymity", "LAAKA", "Zhou"]
colors  = ["#1565C0", "#E65100", "#2E7D32"]
data    = [RA, LK, ZH]

# ── Figure: 1 row × 2 panels ──────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 7))
fig.suptitle(
    "Per-Device Mean Total Cost — All 3 Phases\n"
    "(Enrollment + Authentication + Key Exchange)   |   COOJA Simulation, 20 TelosB Motes",
    fontsize=13, fontweight="bold", y=1.02
)

x = np.arange(len(schemes))
w = 0.45
CI_PATCH = mpatches.Patch(facecolor="none", edgecolor="#333",
                           linewidth=1.2, label="Error bars = 95% CI")

def draw_panel(ax, metric, ylabel, unit, decimals=2, note=None):
    vals = [d[metric][0] for d in data]
    cis  = [d[metric][1] for d in data]
    ns   = [d[metric][2] for d in data]

    bars = ax.bar(x, vals, width=w, color=colors, edgecolor="black",
                  linewidth=0.9, yerr=cis, capsize=8,
                  error_kw={"elinewidth": 2.0, "ecolor": "#111111"})

    top = max(v + c for v, c in zip(vals, cis))
    ax.set_ylim(0, top * 1.45)

    fmt = f"{{:.{decimals}f}}"

    # Mean value bold above bar
    for bar, v, ci_v in zip(bars, vals, cis):
        cx = bar.get_x() + bar.get_width() / 2
        base = bar.get_height() + ci_v + top * 0.03
        ax.text(cx, base,
                fmt.format(v) + f" {unit}",
                ha="center", va="bottom", fontsize=10.5, fontweight="bold", color="#111")
        # ±CI value in smaller text just below mean label
        ax.text(cx, base - top * 0.001,
                f"± {fmt.format(ci_v)} {unit}",
                ha="center", va="top", fontsize=8.5, color="#444")

    # n= inside bar
    for bar, v, n in zip(bars, vals, ns):
        ax.text(bar.get_x() + bar.get_width() / 2,
                v / 2,
                f"n = {n}", ha="center", va="center",
                fontsize=9.5, color="white", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(schemes, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45, color="#cccccc")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=10)

    if note:
        ax.text(0.5, -0.12, note, transform=ax.transAxes,
                ha="center", fontsize=8, color="#666", style="italic")

draw_panel(ax1, "en",  "Per-Device Mean Total Energy (mJ)", "mJ", decimals=2,
           note="Zhou: Enrollment + Auth energy  (Key Exchange is included in Auth)")
draw_panel(ax2, "cpu", "Per-Device Mean Total CPU Time (s)", "s", decimals=4,
           note="Zhou CPU: Enrollment + Auth  (Key Exchange included in Auth phase)")

# Single legend below both panels
scheme_handles = [mpatches.Patch(color=c, label=s.replace("\n", "-"))
                  for c, s in zip(colors, schemes)]
scheme_handles.append(CI_PATCH)
fig.legend(handles=scheme_handles,
           loc="lower center", bbox_to_anchor=(0.5, -0.07),
           ncol=len(scheme_handles), fontsize=10,
           framealpha=0.95, edgecolor="#aaaaaa")

plt.tight_layout()
out = os.path.join(OUT_DIR, "18_total_all_phases.png")
fig.savefig(out, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved: 18_total_all_phases.png")

# ── Console summary ───────────────────────────────────────────────────────────
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
