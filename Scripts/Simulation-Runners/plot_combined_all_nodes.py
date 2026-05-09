"""
plot_combined_all_nodes.py
Two sets of charts:
  A) Combined cost of all 3 phases per scheme  (stacked bar, per-device avg)
  B) All-nodes total cost per scheme           (sum across 20 nodes)

Schemes: Revised-Anonymity  |  LAAKA  |  Zhou
Phases:  Enrollment  |  Authentication (Rd 1)  |  Key Exchange (Rd 2)

Note: Zhou has no separate keyex phase.
      "All-nodes" figures use avg-per-device x 20 for fair comparison.
"""
import csv, os, statistics, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OUT_DIR = os.path.join(BASE, "Results", "Charts", "Revised-vs-LAAKA-vs-Zhou")
os.makedirs(OUT_DIR, exist_ok=True)

NUM_NODES = 20

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

SCHEME_COLORS = {
    "Revised-Anonymity": "#2C6FAC",
    "LAAKA":             "#B85C2C",
    "Zhou":              "#3A7D44",
}

# Muted phase colors matching network variation palette
C_ENROLL = "#90CAF9"   # light blue
C_AUTH   = "#FFB74D"   # light orange
C_KEYEX  = "#A5D6A7"   # light green

# ─────────────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────────────
def load(path, id_col, cpu_col, en_col):
    rows = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows[int(r[id_col])] = {
                    "cpu": float(r[cpu_col]),
                    "en":  float(r[en_col])
                }
            except (ValueError, KeyError):
                pass
    return rows

def avg_en(d):  return statistics.mean(v["en"]  for v in d.values()) if d else 0
def avg_cpu(d): return statistics.mean(v["cpu"] for v in d.values()) if d else 0

RA = "Revised-Anonymity"
LK = "LAAKA"
ZH = "Zhou"

RA_DIR   = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
ra_enr   = load(os.path.join(RA_DIR, "enroll-results.csv"), "Device",    "CPU_s",      "Energy_J")
ra_auth  = load(os.path.join(RA_DIR, "auth-results.csv"),   "Device",    "CPU_s",      "Energy_J")
ra_keyex = load(os.path.join(RA_DIR, "keyex-results.csv"),  "Device",    "CPU_s",      "Energy_J")

LK_DIR   = os.path.join(BASE, "Results", "CSV-Data", "LAAKA")
lk_enr   = load(os.path.join(LK_DIR, "enroll-results.csv"), "Device_ID", "CPU_Time_s", "Energy_J")
lk_auth  = load(os.path.join(LK_DIR, "auth-results.csv"),   "Device_ID", "CPU_Time_s", "Energy_J")
lk_keyex = load(os.path.join(LK_DIR, "keyex-results.csv"),  "Device_ID", "CPU_Time_s", "Energy_J")

zh_raw = {}
with open(os.path.join(BASE, "Zhou-Scheme", "zhou-auth-results.csv"), newline="") as f:
    for r in csv.DictReader(f, skipinitialspace=True):
        try:
            zh_raw[int(r["Device_ID"])] = {
                "en_auth":   float(r["Avg_Energy_J"]),
                "en_enroll": float(r["Enroll_Energy_J"]),
                "cpu_auth":  float(r["Avg_CPU_s"])
            }
        except (ValueError, KeyError):
            pass

zh_enr   = {k: {"en": v["en_enroll"], "cpu": 0} for k, v in zh_raw.items()}
zh_auth  = {k: {"en": v["en_auth"],   "cpu": v["cpu_auth"]} for k, v in zh_raw.items()}
zh_keyex = {}

# ─────────────────────────────────────────────────────────────────────────────
# Per-device averages (mJ)
# ─────────────────────────────────────────────────────────────────────────────
avg_mj = {
    RA: {"enroll": avg_en(ra_enr)*1000, "auth": avg_en(ra_auth)*1000, "keyex": avg_en(ra_keyex)*1000},
    LK: {"enroll": avg_en(lk_enr)*1000, "auth": avg_en(lk_auth)*1000, "keyex": avg_en(lk_keyex)*1000},
    ZH: {"enroll": avg_en(zh_enr)*1000, "auth": avg_en(zh_auth)*1000, "keyex": 0},
}
for s in [RA, LK, ZH]:
    avg_mj[s]["combined"] = sum(avg_mj[s].values())

total_mj = {s: {k: v * NUM_NODES for k, v in avg_mj[s].items()} for s in [RA, LK, ZH]}

ra_ids = sorted(set(ra_enr) & set(ra_auth) & set(ra_keyex))
ra_combined_per_dev = [(ra_enr[i]["en"] + ra_auth[i]["en"] + ra_keyex[i]["en"]) * 1000
                       for i in ra_ids]

lk_ids = sorted(set(lk_enr) & set(lk_auth) & set(lk_keyex))
lk_combined_per_dev = [(lk_enr[i]["en"] + lk_auth[i]["en"] + lk_keyex[i]["en"]) * 1000
                       for i in lk_ids]

zh_ids = sorted(set(zh_enr) & set(zh_auth))
zh_combined_per_dev = [(zh_enr[i]["en"] + zh_auth[i]["en"]) * 1000
                       for i in zh_ids]

# ─────────────────────────────────────────────────────────────────────────────
# Print summary
# ─────────────────────────────────────────────────────────────────────────────
SCHEMES = [RA, LK, ZH]
print("\n" + "="*80)
print("COMBINED COST — ALL 3 PHASES (per-device avg, mJ)")
print("="*80)
print(f"{'Scheme':<22} {'Enrollment':>12} {'Auth(Rd1)':>12} {'KeyEx(Rd2)':>12} {'TOTAL':>12}")
print("-"*72)
for s in SCHEMES:
    kx = f"{avg_mj[s]['keyex']:>12.3f}" if avg_mj[s]['keyex'] > 0 else f"{'(in auth)':>12}"
    print(f"  {s:<20} {avg_mj[s]['enroll']:>12.3f} {avg_mj[s]['auth']:>12.3f} {kx} {avg_mj[s]['combined']:>12.3f}")

# ─────────────────────────────────────────────────────────────────────────────
# Style helpers
# ─────────────────────────────────────────────────────────────────────────────
SCHEME_LABELS = [RA, LK, ZH]
x_pos = np.arange(len(SCHEME_LABELS))

def scheme_short(s):
    return {"Revised-Anonymity": "Revised-\nAnonymity", "LAAKA": "LAAKA", "Zhou": "Zhou"}[s]

def _apply_axes_style(ax, title, ylabel, xlabel=None):
    ax.set_title(title, pad=14, color="#222222")
    ax.set_ylabel(ylabel, labelpad=8)
    if xlabel:
        ax.set_xlabel(xlabel, labelpad=8)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")

def save(fig, name):
    p = os.path.join(OUT_DIR, name)
    fig.savefig(p, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved: {name}")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 08 — Stacked bar: per-device avg combined cost
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor("white")
    width = 0.5

    enr_vals   = [avg_mj[s]["enroll"] for s in SCHEME_LABELS]
    auth_vals  = [avg_mj[s]["auth"]   for s in SCHEME_LABELS]
    keyex_vals = [avg_mj[s]["keyex"]  for s in SCHEME_LABELS]

    ax.bar(x_pos, enr_vals,  width, label="Enrollment",
           color=C_ENROLL, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, auth_vals, width, bottom=enr_vals,
           label="Authentication (Round 1)", color=C_AUTH, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, keyex_vals, width,
           bottom=[e + a for e, a in zip(enr_vals, auth_vals)],
           label="Key Exchange (Round 2)\n[in Auth for Zhou]",
           color=C_KEYEX, edgecolor="white", linewidth=0.5)

    for i, s in enumerate(SCHEME_LABELS):
        total = avg_mj[s]["combined"]
        ax.text(i, total + max(avg_mj[s2]["combined"] for s2 in SCHEME_LABELS) * 0.015,
                f"{total:.1f} mJ", ha="center", va="bottom", fontsize=7.5, color="#555555")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([scheme_short(s) for s in SCHEME_LABELS])
    ax.set_ylim(0, max(avg_mj[s]["combined"] for s in SCHEME_LABELS) * 1.18)
    ax.legend(loc="upper right", frameon=True, framealpha=0.92, edgecolor="#dddddd")
    ax.text(0.01, 0.01, "* Zhou Key Exchange cost is included in its Authentication phase",
            transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
    _apply_axes_style(ax,
        "Combined Energy Cost — All 3 Phases (Per-Device Average)\n"
        "COOJA Simulation, 20 TelosB Motes",
        "Mean Energy per Device (mJ)")
    fig.tight_layout()
    save(fig, "08_combined_cost_per_device_stacked.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 09 — Stacked bar: all-nodes total combined cost
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor("white")
    width = 0.5

    t_enr   = [total_mj[s]["enroll"] for s in SCHEME_LABELS]
    t_auth  = [total_mj[s]["auth"]   for s in SCHEME_LABELS]
    t_keyex = [total_mj[s]["keyex"]  for s in SCHEME_LABELS]

    ax.bar(x_pos, t_enr,  width, label="Enrollment",
           color=C_ENROLL, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, t_auth, width, bottom=t_enr,
           label="Authentication (Round 1)", color=C_AUTH, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, t_keyex, width,
           bottom=[e + a for e, a in zip(t_enr, t_auth)],
           label="Key Exchange (Round 2)\n[in Auth for Zhou]",
           color=C_KEYEX, edgecolor="white", linewidth=0.5)

    max_tot = max(total_mj[s]["combined"] for s in SCHEME_LABELS)
    for i, s in enumerate(SCHEME_LABELS):
        total = total_mj[s]["combined"]
        ax.text(i, total + max_tot * 0.015,
                f"{total:.1f} mJ", ha="center", va="bottom", fontsize=7.5, color="#555555")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([scheme_short(s) for s in SCHEME_LABELS])
    ax.set_ylim(0, max_tot * 1.18)
    ax.legend(loc="upper right", frameon=True, framealpha=0.92, edgecolor="#dddddd")
    ax.text(0.01, 0.01,
            "* All-nodes total = per-device average × 20 (fair comparison across schemes)",
            transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
    _apply_axes_style(ax,
        f"All-Nodes Combined Energy Cost — All 3 Phases ({NUM_NODES} Devices)\n"
        "COOJA Simulation, TelosB Motes",
        f"Total Energy — All {NUM_NODES} Nodes (mJ)")
    fig.tight_layout()
    save(fig, "09_combined_cost_all_nodes_stacked.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 10 — Per-device combined cost line chart
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("white")

    ax.plot(ra_ids, ra_combined_per_dev, "o-",
            color=SCHEME_COLORS[RA], label=RA, linewidth=1.8, markersize=6, alpha=0.9)
    ax.plot(lk_ids, lk_combined_per_dev, "s--",
            color=SCHEME_COLORS[LK], label=LK, linewidth=1.8, markersize=6, alpha=0.9)
    ax.plot(zh_ids, zh_combined_per_dev, "^:",
            color=SCHEME_COLORS[ZH], label=f"{ZH} (Enroll+Auth combined)",
            linewidth=1.8, markersize=6, alpha=0.9)

    for s, vals, ids in [(RA, ra_combined_per_dev, ra_ids),
                         (LK, lk_combined_per_dev, lk_ids),
                         (ZH, zh_combined_per_dev, zh_ids)]:
        ax.axhline(avg_mj[s]["combined"], color=SCHEME_COLORS[s],
                   linestyle=":", alpha=0.55, linewidth=1.2)

    ax.legend(loc="upper left", frameon=True, framealpha=0.92, edgecolor="#dddddd",
              handlelength=1.4)
    ax.text(0.01, 0.01, "Dotted horizontal lines = per-scheme mean",
            transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
    _apply_axes_style(ax,
        "Per-Device Combined Energy Cost (Enrollment + Auth + Key Exchange)\n"
        "COOJA Simulation, TelosB Motes",
        "Total Energy (mJ)",
        xlabel="Device ID")
    fig.tight_layout()
    save(fig, "10_per_device_combined_cost_line.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 11 — Grouped bar: per-phase + combined
# ─────────────────────────────────────────────────────────────────────────────
phases_labels = ["Enrollment", "Auth\n(Round 1)", "Key Exchange\n(Round 2)", "Combined\n(All Phases)"]
phase_keys    = ["enroll", "auth", "keyex", "combined"]

with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("white")

    ph_pos  = np.arange(len(phases_labels))
    w = 0.22
    offsets = np.array([-w, 0, w])

    all_vals = []
    for i, s in enumerate(SCHEME_LABELS):
        vals = [avg_mj[s][k] for k in phase_keys]
        all_vals.extend(vals)
        bars = ax.bar(ph_pos + offsets[i], vals, w,
                      label=s, color=SCHEME_COLORS[s],
                      edgecolor="white", linewidth=0.8, alpha=0.88)
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(all_vals + [1]) * 0.012,
                        f"{v:.1f}", ha="center", va="bottom",
                        fontsize=7, color="#555555", rotation=90)

    ax.set_xticks(ph_pos)
    ax.set_xticklabels(phases_labels)
    ax.set_ylim(0, max(all_vals) * 1.28)
    ax.legend(loc="upper left", frameon=True, framealpha=0.92, edgecolor="#dddddd",
              handlelength=1.4)
    ax.text(0.01, 0.99, "* Zhou Key Exchange cost is included in its Authentication phase",
            transform=ax.transAxes, fontsize=8, verticalalignment="top",
            color="#555555", style="italic")
    _apply_axes_style(ax,
        "Energy Consumption per Phase — All Schemes (Per-Device Average)\n"
        "COOJA Simulation, 20 TelosB Motes",
        "Mean Energy per Device (mJ)")
    fig.tight_layout()
    save(fig, "11_grouped_per_phase_and_combined.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 12 — All-nodes combined simple bar
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(8, 5.5))
    fig.patch.set_facecolor("white")

    totals = [total_mj[s]["combined"] for s in SCHEME_LABELS]
    bars = ax.bar([scheme_short(s) for s in SCHEME_LABELS], totals, width=0.5,
                  color=[SCHEME_COLORS[s] for s in SCHEME_LABELS],
                  edgecolor="white", linewidth=0.8, alpha=0.88)

    max_tot = max(totals)
    for bar, v in zip(bars, totals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max_tot * 0.012,
                f"{v:.1f} mJ", ha="center", va="bottom", fontsize=7.5, color="#555555")

    ra_total = total_mj[RA]["combined"]
    for s in [LK, ZH]:
        saving = ((total_mj[s]["combined"] - ra_total) / ra_total) * 100
        idx = SCHEME_LABELS.index(s)
        ax.text(idx, totals[idx] * 0.45,
                f"RA saves\n{saving:.0f}% vs {s}",
                ha="center", fontsize=8, color="white")

    ax.set_ylim(0, max_tot * 1.20)
    ax.legend(handles=[mpatches.Patch(color=SCHEME_COLORS[s], alpha=0.88, label=s)
                        for s in SCHEME_LABELS],
              loc="upper left", frameon=True, framealpha=0.92, edgecolor="#dddddd")
    ax.text(0.01, 0.01, "* Total = per-device average × 20 nodes",
            transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
    _apply_axes_style(ax,
        f"Total Network Energy Cost (Enrollment + Auth + Key Exchange)\n"
        f"{NUM_NODES} Devices — COOJA Simulation",
        f"Total Energy — All {NUM_NODES} Nodes (mJ)")
    fig.tight_layout()
    save(fig, "12_all_nodes_combined_bar.png")

print(f"\nAll charts -> {OUT_DIR}")
print("Done!")
