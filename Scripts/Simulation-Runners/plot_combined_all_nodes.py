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
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE    = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
OUT_DIR = os.path.join(BASE, "Results", "Charts", "Revised-vs-LAAKA-vs-Zhou")
os.makedirs(OUT_DIR, exist_ok=True)

NUM_NODES = 20   # total devices in topology

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
    return rows   # dict: device_id -> {cpu, en}

def avg_en(d):  return statistics.mean(v["en"]  for v in d.values()) if d else 0
def avg_cpu(d): return statistics.mean(v["cpu"] for v in d.values()) if d else 0
def total_en(d): return sum(v["en"] for v in d.values())

plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})

RA = "Revised-Anonymity"
LK = "LAAKA"
ZH = "Zhou"

# ── Revised-Anonymity ───────────────────────────────────────────────────────
RA_DIR   = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
ra_enr   = load(os.path.join(RA_DIR, "enroll-results.csv"), "Device","CPU_s","Energy_J")
ra_auth  = load(os.path.join(RA_DIR, "auth-results.csv"),   "Device","CPU_s","Energy_J")
ra_keyex = load(os.path.join(RA_DIR, "keyex-results.csv"),  "Device","CPU_s","Energy_J")

# ── LAAKA ───────────────────────────────────────────────────────────────────
LK_DIR   = os.path.join(BASE, "Results", "CSV-Data", "LAAKA")
lk_enr   = load(os.path.join(LK_DIR, "enroll-results.csv"), "Device_ID","CPU_Time_s","Energy_J")
lk_auth  = load(os.path.join(LK_DIR, "auth-results.csv"),   "Device_ID","CPU_Time_s","Energy_J")
lk_keyex = load(os.path.join(LK_DIR, "keyex-results.csv"),  "Device_ID","CPU_Time_s","Energy_J")

# ── Zhou ─────────────────────────────────────────────────────────────────────
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
zh_keyex = {}   # Zhou has no separate keyex measurement

# ─────────────────────────────────────────────────────────────────────────────
# Per-device averages (mJ)
# ─────────────────────────────────────────────────────────────────────────────
avg_mj = {
    RA: {
        "enroll": avg_en(ra_enr)   * 1000,
        "auth":   avg_en(ra_auth)  * 1000,
        "keyex":  avg_en(ra_keyex) * 1000,
    },
    LK: {
        "enroll": avg_en(lk_enr)   * 1000,
        "auth":   avg_en(lk_auth)  * 1000,
        "keyex":  avg_en(lk_keyex) * 1000,
    },
    ZH: {
        "enroll": avg_en(zh_enr)   * 1000,
        "auth":   avg_en(zh_auth)  * 1000,
        "keyex":  0,                           # included in auth for Zhou
    },
}

# Combined per-device
for s in [RA, LK, ZH]:
    avg_mj[s]["combined"] = sum(avg_mj[s].values())

# All-nodes total = avg × NUM_NODES  (fair comparison regardless of missing devices)
total_mj = {s: {k: v * NUM_NODES for k, v in avg_mj[s].items()} for s in [RA, LK, ZH]}

# ─────────────────────────────────────────────────────────────────────────────
# Per-device combined cost: per device for all schemes
# (only devices present in ALL phases of a scheme)
# ─────────────────────────────────────────────────────────────────────────────
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

print("\n" + "="*80)
print(f"ALL-NODES TOTAL COST  ({NUM_NODES} nodes x avg, mJ)")
print("="*80)
print(f"{'Scheme':<22} {'Enrollment':>12} {'Auth(Rd1)':>12} {'KeyEx(Rd2)':>12} {'TOTAL':>12}")
print("-"*72)
for s in SCHEMES:
    kx = f"{total_mj[s]['keyex']:>12.3f}" if total_mj[s]['keyex'] > 0 else f"{'(in auth)':>12}"
    print(f"  {s:<20} {total_mj[s]['enroll']:>12.3f} {total_mj[s]['auth']:>12.3f} {kx} {total_mj[s]['combined']:>12.3f}")

# ─────────────────────────────────────────────────────────────────────────────
# Colors & style
# ─────────────────────────────────────────────────────────────────────────────
C_ENROLL = "#42A5F5"   # blue
C_AUTH   = "#FFA726"   # orange
C_KEYEX  = "#66BB6A"   # green

SCHEME_COLORS = {RA: "#1565C0", LK: "#E65100", ZH: "#2E7D32"}
SCHEME_LABELS = [RA, LK, ZH]
x_pos = np.arange(len(SCHEME_LABELS))

def scheme_short(s):
    return {"Revised-Anonymity": "Revised-\nAnonymity", "LAAKA": "LAAKA", "Zhou": "Zhou"}[s]

# ─────────────────────────────────────────────────────────────────────────────
# Chart 1 — Stacked bar: per-device avg combined cost
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
width = 0.5

enr_vals   = [avg_mj[s]["enroll"] for s in SCHEME_LABELS]
auth_vals  = [avg_mj[s]["auth"]   for s in SCHEME_LABELS]
keyex_vals = [avg_mj[s]["keyex"]  for s in SCHEME_LABELS]

b1 = ax.bar(x_pos, enr_vals,  width, label="Enrollment",          color=C_ENROLL, edgecolor="black", linewidth=0.8)
b2 = ax.bar(x_pos, auth_vals, width, bottom=enr_vals,             label="Authentication (Round 1)", color=C_AUTH,   edgecolor="black", linewidth=0.8)
b3 = ax.bar(x_pos, keyex_vals,width, bottom=[e+a for e,a in zip(enr_vals,auth_vals)],
            label="Key Exchange (Round 2)\n[in Auth for Zhou]",    color=C_KEYEX,  edgecolor="black", linewidth=0.8)

# Annotate total on top
for i, s in enumerate(SCHEME_LABELS):
    total = avg_mj[s]["combined"]
    ax.text(i, total + 0.5, f"{total:.1f} mJ", ha="center", va="bottom", fontsize=10, fontweight="bold")

ax.set_xticks(x_pos)
ax.set_xticklabels([scheme_short(s) for s in SCHEME_LABELS], fontsize=12)
ax.set_ylabel("Mean Energy per Device (mJ)", fontsize=12)
ax.set_title("Combined Energy Cost — All 3 Phases (Per-Device Average)\n"
             "COOJA Simulation, 20 TelosB Motes", fontsize=13, fontweight="bold")
ax.legend(fontsize=10, loc="upper right", framealpha=0.88, edgecolor="#aaaaaa")
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
ax.set_axisbelow(True)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.set_ylim(0, max(avg_mj[s]["combined"] for s in SCHEME_LABELS) * 1.20)
ax.text(0.01, 0.01, "* Zhou Key Exchange cost is included in its Authentication phase",
        transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
plt.tight_layout()
p = os.path.join(OUT_DIR, "08_combined_cost_per_device_stacked.png")
plt.savefig(p, dpi=150); plt.close()
print(f"\nSaved: 08_combined_cost_per_device_stacked.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 2 — Stacked bar: all-nodes total combined cost
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))

t_enr   = [total_mj[s]["enroll"] for s in SCHEME_LABELS]
t_auth  = [total_mj[s]["auth"]   for s in SCHEME_LABELS]
t_keyex = [total_mj[s]["keyex"]  for s in SCHEME_LABELS]

ax.bar(x_pos, t_enr,  width, label="Enrollment",          color=C_ENROLL, edgecolor="black", linewidth=0.8)
ax.bar(x_pos, t_auth, width, bottom=t_enr,                label="Authentication (Round 1)", color=C_AUTH,   edgecolor="black", linewidth=0.8)
ax.bar(x_pos, t_keyex,width, bottom=[e+a for e,a in zip(t_enr,t_auth)],
            label="Key Exchange (Round 2)\n[in Auth for Zhou]",    color=C_KEYEX,  edgecolor="black", linewidth=0.8)

for i, s in enumerate(SCHEME_LABELS):
    total = total_mj[s]["combined"]
    ax.text(i, total + 8, f"{total:.1f} mJ", ha="center", va="bottom", fontsize=10, fontweight="bold")

ax.set_xticks(x_pos)
ax.set_xticklabels([scheme_short(s) for s in SCHEME_LABELS], fontsize=12)
ax.set_ylabel(f"Total Energy — All {NUM_NODES} Nodes (mJ)", fontsize=12)
ax.set_title(f"All-Nodes Combined Energy Cost — All 3 Phases ({NUM_NODES} Devices)\n"
             "COOJA Simulation, TelosB Motes", fontsize=13, fontweight="bold")
ax.legend(fontsize=10, loc="upper right", framealpha=0.88, edgecolor="#aaaaaa")
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
ax.set_axisbelow(True)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.set_ylim(0, max(total_mj[s]["combined"] for s in SCHEME_LABELS) * 1.18)
ax.text(0.01, 0.01, "* All-nodes total = per-device average × 20 (fair comparison across schemes)",
        transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
plt.tight_layout()
p = os.path.join(OUT_DIR, "09_combined_cost_all_nodes_stacked.png")
plt.savefig(p, dpi=150); plt.close()
print(f"Saved: 09_combined_cost_all_nodes_stacked.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 3 — Per-device combined cost line chart (scatter+line per scheme)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))

ax.plot(ra_ids, ra_combined_per_dev, "o-",
        color=SCHEME_COLORS[RA], label=RA, linewidth=1.8, markersize=6)
ax.plot(lk_ids, lk_combined_per_dev, "s--",
        color=SCHEME_COLORS[LK], label=LK, linewidth=1.8, markersize=6)
ax.plot(zh_ids, zh_combined_per_dev, "^:",
        color=SCHEME_COLORS[ZH], label=f"{ZH} (Enroll+Auth combined)",
        linewidth=1.8, markersize=6)

# Horizontal average lines
ax.axhline(avg_mj[RA]["combined"], color=SCHEME_COLORS[RA], linestyle=":", alpha=0.6, linewidth=1.2)
ax.axhline(avg_mj[LK]["combined"], color=SCHEME_COLORS[LK], linestyle=":", alpha=0.6, linewidth=1.2)
ax.axhline(avg_mj[ZH]["combined"], color=SCHEME_COLORS[ZH], linestyle=":", alpha=0.6, linewidth=1.2)

ax.set_xlabel("Device ID", fontsize=12)
ax.set_ylabel("Total Energy (mJ)", fontsize=12)
ax.set_title("Per-Device Combined Energy Cost (Enrollment + Auth + Key Exchange)\n"
             "COOJA Simulation, TelosB Motes", fontsize=12, fontweight="bold")
ax.legend(fontsize=10, framealpha=0.88, edgecolor="#aaaaaa")
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
ax.set_axisbelow(True)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.text(0.01, 0.01, "Dotted horizontal lines = per-scheme mean",
        transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
plt.tight_layout()
p = os.path.join(OUT_DIR, "10_per_device_combined_cost_line.png")
plt.savefig(p, dpi=150); plt.close()
print(f"Saved: 10_per_device_combined_cost_line.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 4 — Grouped bar: per-phase + combined side by side for all schemes
# ─────────────────────────────────────────────────────────────────────────────
phases_labels = ["Enrollment", "Auth\n(Round 1)", "Key Exchange\n(Round 2)", "Combined\n(All Phases)"]
phase_keys    = ["enroll", "auth", "keyex", "combined"]

fig, ax = plt.subplots(figsize=(12, 6))
n_phases  = len(phases_labels)
w = 0.22
ph_pos  = np.arange(n_phases)
offsets = np.array([-w, 0, w])

for i, s in enumerate(SCHEME_LABELS):
    vals = [avg_mj[s][k] for k in phase_keys]
    bars = ax.bar(ph_pos + offsets[i], vals, w,
                  label=s, color=SCHEME_COLORS[s],
                  edgecolor="black", linewidth=0.7)
    for bar, v in zip(bars, vals):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    f"{v:.1f}", ha="center", va="bottom", fontsize=7.5, rotation=90)

ax.set_xticks(ph_pos)
ax.set_xticklabels(phases_labels, fontsize=11)
ax.set_ylabel("Mean Energy per Device (mJ)", fontsize=12)
ax.set_title("Energy Consumption per Phase — All Schemes (Per-Device Average)\n"
             "COOJA Simulation, 20 TelosB Motes", fontsize=12, fontweight="bold")
ax.legend(fontsize=10, framealpha=0.88, edgecolor="#aaaaaa")
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
ax.set_axisbelow(True)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.text(0.01, 0.99, "* Zhou Key Exchange cost is included in its Authentication phase",
        transform=ax.transAxes, fontsize=8, verticalalignment="top", color="#555555", style="italic")
plt.tight_layout()
p = os.path.join(OUT_DIR, "11_grouped_per_phase_and_combined.png")
plt.savefig(p, dpi=150); plt.close()
print(f"Saved: 11_grouped_per_phase_and_combined.png")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 5 — All-nodes total simple bar (just combined, no stacking)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))
totals = [total_mj[s]["combined"] for s in SCHEME_LABELS]
bars = ax.bar([scheme_short(s) for s in SCHEME_LABELS], totals, width=0.5,
              color=[SCHEME_COLORS[s] for s in SCHEME_LABELS],
              edgecolor="black", linewidth=0.9)
for bar, v in zip(bars, totals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
            f"{v:.1f} mJ", ha="center", va="bottom", fontsize=11, fontweight="bold")

# Savings annotations
ra_total = total_mj[RA]["combined"]
for i, s in enumerate([LK, ZH]):
    saving = ((total_mj[s]["combined"] - ra_total) / ra_total) * 100
    ax.text(0, totals[0] * 0.45, f"RA saves\n{saving:.0f}% vs {s}",
            ha="center", fontsize=8.5, color="white", fontweight="bold")

ax.set_ylabel(f"Total Energy — All {NUM_NODES} Nodes (mJ)", fontsize=12)
ax.set_title(f"Total Network Energy Cost (Enrollment + Auth + Key Exchange)\n"
             f"{NUM_NODES} Devices — COOJA Simulation", fontsize=12, fontweight="bold")
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
ax.set_axisbelow(True)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.set_ylim(0, max(totals) * 1.22)
ax.text(0.01, 0.01, "* Total = per-device average × 20 nodes",
        transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
plt.tight_layout()
p = os.path.join(OUT_DIR, "12_all_nodes_combined_bar.png")
plt.savefig(p, dpi=150); plt.close()
print(f"Saved: 12_all_nodes_combined_bar.png")

print(f"\nAll charts -> {OUT_DIR}")
print("Done!")
