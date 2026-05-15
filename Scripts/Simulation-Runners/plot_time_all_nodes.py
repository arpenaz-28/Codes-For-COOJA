"""
plot_time_all_nodes.py
CPU time charts — combined all 3 phases, all nodes.
Mirrors plot_combined_all_nodes.py but for CPU time (seconds).

Charts:
  13 — Stacked bar: combined CPU time per device (avg)
  14 — Stacked bar: all-nodes total CPU time (20 x avg)
  15 — Per-device combined CPU time line chart
  16 — Grouped bar: per-phase + combined
  17 — All-nodes combined simple bar with savings
"""
import csv, os, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
OUT_DIR   = os.path.join(BASE, "Results", "Charts", "Revised-vs-LAAKA-vs-Zhou")
NUM_NODES = 20

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

# Muted phase colors matching network variation palette
C_ENROLL = "#90CAF9"
C_AUTH   = "#FFB74D"
C_KEYEX  = "#A5D6A7"

RA = "Revised-Anonymity"
LK = "LAAKA"
ZH = "Zhou"
SCHEME_LABELS = [RA, LK, ZH]
SCHEME_COLORS = {
    RA: "#2C6FAC",
    LK: "#B85C2C",
    ZH: "#3A7D44",
}
SCHEME_SHORT = {RA: "Revised-\nAnonymity", LK: "LAAKA", ZH: "Zhou"}

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

def avg_cpu(d): return statistics.mean(v["cpu"] for v in d.values()) if d else 0

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
            zh_raw[int(r["Device_ID"])] = {"cpu_auth": float(r["Avg_CPU_s"])}
        except (ValueError, KeyError):
            pass
zh_enr   = {k: {"cpu": 0,             "en": 0} for k in zh_raw}
zh_auth  = {k: {"cpu": v["cpu_auth"], "en": 0} for k, v in zh_raw.items()}
zh_keyex = {}

avg_s = {
    RA: {"enroll": avg_cpu(ra_enr),  "auth": avg_cpu(ra_auth),  "keyex": avg_cpu(ra_keyex)},
    LK: {"enroll": avg_cpu(lk_enr),  "auth": avg_cpu(lk_auth),  "keyex": avg_cpu(lk_keyex)},
    ZH: {"enroll": 0,                "auth": avg_cpu(zh_auth),  "keyex": 0},
}
for s in SCHEME_LABELS:
    avg_s[s]["combined"] = sum(avg_s[s].values())

total_s = {s: {k: v * NUM_NODES for k, v in avg_s[s].items()} for s in SCHEME_LABELS}

ra_ids = sorted(set(ra_enr) & set(ra_auth) & set(ra_keyex))
ra_cpu_dev = [ra_enr[i]["cpu"] + ra_auth[i]["cpu"] + ra_keyex[i]["cpu"] for i in ra_ids]

lk_ids = sorted(set(lk_enr) & set(lk_auth) & set(lk_keyex))
lk_cpu_dev = [lk_enr[i]["cpu"] + lk_auth[i]["cpu"] + lk_keyex[i]["cpu"] for i in lk_ids]

zh_ids = sorted(zh_auth.keys())
zh_cpu_dev = [zh_auth[i]["cpu"] for i in zh_ids]

# ─────────────────────────────────────────────────────────────────────────────
# Print summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("COMBINED CPU TIME — ALL 3 PHASES (per-device avg, seconds)")
print("="*80)
print(f"{'Scheme':<22} {'Enrollment':>12} {'Auth(Rd1)':>12} {'KeyEx(Rd2)':>12} {'TOTAL':>12}")
print("-"*72)
for s in SCHEME_LABELS:
    kx = f"{avg_s[s]['keyex']:>12.4f}" if avg_s[s]["keyex"] > 0 else f"{'(in auth)':>12}"
    en = f"{avg_s[s]['enroll']:>12.4f}" if avg_s[s]["enroll"] > 0 else f"{'(N/A)':>12}"
    print(f"  {s:<20} {en} {avg_s[s]['auth']:>12.4f} {kx} {avg_s[s]['combined']:>12.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# Style helpers
# ─────────────────────────────────────────────────────────────────────────────
x_pos = np.arange(len(SCHEME_LABELS))

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
# Chart 13 — Stacked bar: per-device avg combined CPU
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor("white")
    W = 0.52

    enr_v   = [avg_s[s]["enroll"] for s in SCHEME_LABELS]
    auth_v  = [avg_s[s]["auth"]   for s in SCHEME_LABELS]
    keyex_v = [avg_s[s]["keyex"]  for s in SCHEME_LABELS]
    bot_ak  = [e + a for e, a in zip(enr_v, auth_v)]

    ax.bar(x_pos, enr_v,  W, label="Enrollment",
           color=C_ENROLL, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, auth_v, W, bottom=enr_v,
           label="Authentication (Round 1)", color=C_AUTH, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, keyex_v, W, bottom=bot_ak,
           label="Key Exchange (Round 2)  [included in Auth for Zhou]",
           color=C_KEYEX, edgecolor="white", linewidth=0.5)

    max_comb = max(avg_s[s]["combined"] for s in SCHEME_LABELS)
    for i, s in enumerate(SCHEME_LABELS):
        tot = avg_s[s]["combined"]
        ax.text(i, tot + max_comb * 0.015,
                f"{tot:.3f} s", ha="center", va="bottom", fontsize=7.5, color="#555555")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([SCHEME_SHORT[s] for s in SCHEME_LABELS])
    ax.set_ylim(0, max_comb * 1.18)
    ax.legend(loc="upper right", frameon=True, framealpha=0.92, edgecolor="#dddddd")
    _apply_axes_style(ax,
        "Combined CPU Computation Time — All 3 Phases (Per-Device Average)\n"
        "COOJA Simulation, 20 TelosB Motes",
        "Mean CPU Time per Device (s)")
    fig.tight_layout()
    save(fig, "13_time_combined_per_device_stacked.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 14 — Stacked bar: all-nodes total CPU
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor("white")
    W = 0.52

    t_enr   = [total_s[s]["enroll"] for s in SCHEME_LABELS]
    t_auth  = [total_s[s]["auth"]   for s in SCHEME_LABELS]
    t_keyex = [total_s[s]["keyex"]  for s in SCHEME_LABELS]
    t_bot   = [e + a for e, a in zip(t_enr, t_auth)]

    ax.bar(x_pos, t_enr,  W, label="Enrollment",
           color=C_ENROLL, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, t_auth, W, bottom=t_enr,
           label="Authentication (Round 1)", color=C_AUTH, edgecolor="white", linewidth=0.5)
    ax.bar(x_pos, t_keyex, W, bottom=t_bot,
           label="Key Exchange (Round 2)  [included in Auth for Zhou]",
           color=C_KEYEX, edgecolor="white", linewidth=0.5)

    max_tot = max(total_s[s]["combined"] for s in SCHEME_LABELS)
    for i, s in enumerate(SCHEME_LABELS):
        tot = total_s[s]["combined"]
        ax.text(i, tot + max_tot * 0.015,
                f"{tot:.2f} s", ha="center", va="bottom", fontsize=7.5, color="#555555")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([SCHEME_SHORT[s] for s in SCHEME_LABELS])
    ax.set_ylim(0, max_tot * 1.18)
    ax.legend(loc="upper right", frameon=True, framealpha=0.92, edgecolor="#dddddd")
    _apply_axes_style(ax,
        f"All-Nodes Combined CPU Time — All 3 Phases ({NUM_NODES} Devices)\n"
        "COOJA Simulation, TelosB Motes",
        f"Total CPU Time — All {NUM_NODES} Nodes (s)")
    fig.tight_layout()
    save(fig, "14_time_combined_all_nodes_stacked.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 15 — Per-device combined CPU line chart
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("white")

    ax.plot(ra_ids, ra_cpu_dev, "o-",
            color=SCHEME_COLORS[RA], label=RA, linewidth=2, markersize=6, alpha=0.9)
    ax.plot(lk_ids, lk_cpu_dev, "s--",
            color=SCHEME_COLORS[LK], label=LK, linewidth=2, markersize=6, alpha=0.9)
    ax.plot(zh_ids, zh_cpu_dev, "^:",
            color=SCHEME_COLORS[ZH], label=f"{ZH}  (Auth only — KeyEx included)",
            linewidth=2, markersize=6, alpha=0.9)

    for s, vals in [(RA, ra_cpu_dev), (LK, lk_cpu_dev), (ZH, zh_cpu_dev)]:
        ax.axhline(statistics.mean(vals), color=SCHEME_COLORS[s],
                   linestyle=":", alpha=0.55, linewidth=1.2)

    ax.legend(loc="upper left", frameon=True, framealpha=0.92, edgecolor="#dddddd",
              handlelength=1.4)
    ax.text(0.01, 0.01, "Dotted horizontal lines = per-scheme mean",
            transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
    _apply_axes_style(ax,
        "Per-Device Combined CPU Time (Enrollment + Auth + Key Exchange)\n"
        "COOJA Simulation, TelosB Motes",
        "CPU Time (s)",
        xlabel="Device ID")
    fig.tight_layout()
    save(fig, "15_time_per_device_combined_line.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 16 — Grouped bar: per-phase + combined
# ─────────────────────────────────────────────────────────────────────────────
phases_labels = ["Enrollment", "Auth\n(Round 1)", "Key Exchange\n(Round 2)", "Combined\n(All Phases)"]
phase_keys    = ["enroll", "auth", "keyex", "combined"]

with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("white")

    ph_pos  = np.arange(len(phases_labels))
    w       = 0.22
    offsets = np.array([-w, 0, w])

    all_vals = []
    for i, s in enumerate(SCHEME_LABELS):
        vals = [avg_s[s][k] for k in phase_keys]
        all_vals.extend(vals)
        bars = ax.bar(ph_pos + offsets[i], vals, w,
                      label=s, color=SCHEME_COLORS[s],
                      edgecolor="white", linewidth=0.8, alpha=0.88)
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(all_vals + [0.001]) * 0.012,
                        f"{v:.3f}", ha="center", va="bottom",
                        fontsize=7, color="#555555", rotation=90)

    ax.set_xticks(ph_pos)
    ax.set_xticklabels(phases_labels)
    ax.set_ylim(0, max(all_vals) * 1.28)
    ax.legend(loc="upper left", frameon=True, framealpha=0.92, edgecolor="#dddddd",
              handlelength=1.4)
    ax.text(0.01, 0.98,
            "* Zhou enrollment CPU not separately recorded; Key Exchange included in Auth",
            transform=ax.transAxes, fontsize=8, va="top", color="#555555", style="italic")
    _apply_axes_style(ax,
        "CPU Computation Time per Phase — All Schemes (Per-Device Average)\n"
        "COOJA Simulation, 20 TelosB Motes",
        "Mean CPU Time per Device (s)")
    fig.tight_layout()
    save(fig, "16_time_grouped_per_phase_and_combined.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 17 — All-nodes combined simple bar
# ─────────────────────────────────────────────────────────────────────────────
with plt.rc_context(_CHART_STYLE):
    fig, ax = plt.subplots(figsize=(8, 5.5))
    fig.patch.set_facecolor("white")

    totals = [total_s[s]["combined"] for s in SCHEME_LABELS]
    max_tot = max(totals)
    bars = ax.bar([SCHEME_SHORT[s] for s in SCHEME_LABELS], totals, width=0.50,
                  color=[SCHEME_COLORS[s] for s in SCHEME_LABELS],
                  edgecolor="white", linewidth=0.8, alpha=0.88)

    for bar, v in zip(bars, totals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max_tot * 0.012,
                f"{v:.2f} s", ha="center", va="bottom", fontsize=7.5, color="#555555")

    ra_tot = total_s[RA]["combined"]
    for s in [LK, ZH]:
        saving = (total_s[s]["combined"] - ra_tot) / ra_tot * 100
        idx = SCHEME_LABELS.index(s)
        ax.text(idx, totals[idx] * 0.45,
                f"RA saves\n{saving:.0f}%",
                ha="center", fontsize=8.5, color="white")

    ax.set_ylim(0, max_tot * 1.20)
    ax.legend(handles=[mpatches.Patch(color=SCHEME_COLORS[s], alpha=0.88, label=s)
                        for s in SCHEME_LABELS],
              loc="upper left", frameon=True, framealpha=0.92, edgecolor="#dddddd")
    _apply_axes_style(ax,
        f"Total CPU Computation Time — All Phases ({NUM_NODES} Devices)\n"
        "COOJA Simulation, TelosB Motes",
        f"Total CPU Time — All {NUM_NODES} Nodes (s)")
    fig.tight_layout()
    save(fig, "17_time_all_nodes_combined_bar.png")

print(f"\nAll time charts -> {OUT_DIR}")
print("Done!")
