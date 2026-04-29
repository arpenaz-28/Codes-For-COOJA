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
import numpy as np

BASE      = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
OUT_DIR   = os.path.join(BASE, "Results", "Charts", "Revised-vs-LAAKA-vs-Zhou")
NUM_NODES = 20

os.makedirs(OUT_DIR, exist_ok=True)

# ── Palette (consistent with energy charts) ───────────────────────────────────
C_ENROLL = "#42A5F5"
C_AUTH   = "#FFA726"
C_KEYEX  = "#66BB6A"

RA = "Revised-Anonymity"
LK = "LAAKA"
ZH = "Zhou"
SCHEME_LABELS  = [RA, LK, ZH]
SCHEME_COLORS  = {RA: "#1565C0", LK: "#E65100", ZH: "#2E7D32"}
SCHEME_SHORT   = {RA: "Revised-\nAnonymity", LK: "LAAKA", ZH: "Zhou"}

# ── Loaders ───────────────────────────────────────────────────────────────────
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

# ── Load all schemes ──────────────────────────────────────────────────────────
RA_DIR = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
ra_enr   = load(os.path.join(RA_DIR, "enroll-results.csv"), "Device","CPU_s","Energy_J")
ra_auth  = load(os.path.join(RA_DIR, "auth-results.csv"),   "Device","CPU_s","Energy_J")
ra_keyex = load(os.path.join(RA_DIR, "keyex-results.csv"),  "Device","CPU_s","Energy_J")

LK_DIR = os.path.join(BASE, "Results", "CSV-Data", "LAAKA")
lk_enr   = load(os.path.join(LK_DIR, "enroll-results.csv"), "Device_ID","CPU_Time_s","Energy_J")
lk_auth  = load(os.path.join(LK_DIR, "auth-results.csv"),   "Device_ID","CPU_Time_s","Energy_J")
lk_keyex = load(os.path.join(LK_DIR, "keyex-results.csv"),  "Device_ID","CPU_Time_s","Energy_J")

zh_raw = {}
with open(os.path.join(BASE, "Zhou-Scheme", "zhou-auth-results.csv"), newline="") as f:
    for r in csv.DictReader(f):
        try:
            zh_raw[int(r["Device_ID"])] = {"cpu_auth": float(r["Avg_CPU_s"])}
        except (ValueError, KeyError):
            pass
zh_enr   = {k: {"cpu": 0,              "en": 0} for k in zh_raw}   # Zhou enroll cpu not recorded
zh_auth  = {k: {"cpu": v["cpu_auth"],  "en": 0} for k, v in zh_raw.items()}
zh_keyex = {}

# ── Per-device avg CPU (seconds) ─────────────────────────────────────────────
avg_s = {
    RA: {"enroll": avg_cpu(ra_enr),  "auth": avg_cpu(ra_auth),  "keyex": avg_cpu(ra_keyex)},
    LK: {"enroll": avg_cpu(lk_enr),  "auth": avg_cpu(lk_auth),  "keyex": avg_cpu(lk_keyex)},
    ZH: {"enroll": 0,                "auth": avg_cpu(zh_auth),  "keyex": 0},
}
for s in SCHEME_LABELS:
    avg_s[s]["combined"] = sum(avg_s[s].values())

# ── All-nodes total CPU = avg x NUM_NODES ─────────────────────────────────────
total_s = {s: {k: v * NUM_NODES for k, v in avg_s[s].items()} for s in SCHEME_LABELS}

# ── Per-device combined CPU for line chart ────────────────────────────────────
ra_ids = sorted(set(ra_enr) & set(ra_auth) & set(ra_keyex))
ra_cpu_dev = [ra_enr[i]["cpu"] + ra_auth[i]["cpu"] + ra_keyex[i]["cpu"] for i in ra_ids]

lk_ids = sorted(set(lk_enr) & set(lk_auth) & set(lk_keyex))
lk_cpu_dev = [lk_enr[i]["cpu"] + lk_auth[i]["cpu"] + lk_keyex[i]["cpu"] for i in lk_ids]

zh_ids = sorted(zh_auth.keys())
zh_cpu_dev = [zh_auth[i]["cpu"] for i in zh_ids]   # only auth available for Zhou

# ── Print summary ─────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("COMBINED CPU TIME — ALL 3 PHASES (per-device avg, seconds)")
print("="*80)
print(f"{'Scheme':<22} {'Enrollment':>12} {'Auth(Rd1)':>12} {'KeyEx(Rd2)':>12} {'TOTAL':>12}")
print("-"*72)
for s in SCHEME_LABELS:
    kx = f"{avg_s[s]['keyex']:>12.4f}" if avg_s[s]["keyex"] > 0 else f"{'(in auth)':>12}"
    en = f"{avg_s[s]['enroll']:>12.4f}" if avg_s[s]["enroll"] > 0 else f"{'(N/A)':>12}"
    print(f"  {s:<20} {en} {avg_s[s]['auth']:>12.4f} {kx} {avg_s[s]['combined']:>12.4f}")

print("\n" + "="*80)
print(f"ALL-NODES TOTAL CPU TIME ({NUM_NODES} nodes x avg, seconds)")
print("="*80)
print(f"{'Scheme':<22} {'Enrollment':>12} {'Auth(Rd1)':>12} {'KeyEx(Rd2)':>12} {'TOTAL':>12}")
print("-"*72)
for s in SCHEME_LABELS:
    kx = f"{total_s[s]['keyex']:>12.4f}" if total_s[s]["keyex"] > 0 else f"{'(in auth)':>12}"
    en = f"{total_s[s]['enroll']:>12.4f}" if total_s[s]["enroll"] > 0 else f"{'(N/A)':>12}"
    print(f"  {s:<20} {en} {total_s[s]['auth']:>12.4f} {kx} {total_s[s]['combined']:>12.4f}")

x_pos = np.arange(len(SCHEME_LABELS))

# ── Chart helpers ─────────────────────────────────────────────────────────────
def apply_style(ax, title, ylabel, xlabel=None):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_ylabel(ylabel, fontsize=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45, color="#aaaaaa")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=11)

def save(fig, name):
    p = os.path.join(OUT_DIR, name)
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {name}")

# ── Chart 13 — Stacked bar: per-device avg combined CPU ───────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
W = 0.52

enr_v   = [avg_s[s]["enroll"] for s in SCHEME_LABELS]
auth_v  = [avg_s[s]["auth"]   for s in SCHEME_LABELS]
keyex_v = [avg_s[s]["keyex"]  for s in SCHEME_LABELS]
bot_ak  = [e + a for e, a in zip(enr_v, auth_v)]

ax.bar(x_pos, enr_v,  W, label="Enrollment",                color=C_ENROLL, edgecolor="white", linewidth=0.5)
ax.bar(x_pos, auth_v, W, bottom=enr_v,                      label="Authentication (Round 1)", color=C_AUTH,   edgecolor="white", linewidth=0.5)
ax.bar(x_pos, keyex_v,W, bottom=bot_ak,
       label="Key Exchange (Round 2)  [included in Auth for Zhou]", color=C_KEYEX, edgecolor="white", linewidth=0.5)

for i, s in enumerate(SCHEME_LABELS):
    tot = avg_s[s]["combined"]
    ax.text(i, tot + avg_s[ZH]["combined"] * 0.02,
            f"{tot:.3f} s", ha="center", va="bottom", fontsize=10, fontweight="bold")

ax.set_xticks(x_pos)
ax.set_xticklabels([SCHEME_SHORT[s] for s in SCHEME_LABELS], fontsize=12)
ax.set_ylim(0, max(avg_s[s]["combined"] for s in SCHEME_LABELS) * 1.20)
ax.legend(fontsize=10, framealpha=0.9, loc="upper right")
apply_style(ax, "Combined CPU Computation Time — All 3 Phases (Per-Device Average)\n"
               "COOJA Simulation, 20 TelosB Motes", "Mean CPU Time per Device (s)")
plt.tight_layout()
save(fig, "13_time_combined_per_device_stacked.png")

# ── Chart 14 — Stacked bar: all-nodes total CPU ───────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))

t_enr   = [total_s[s]["enroll"] for s in SCHEME_LABELS]
t_auth  = [total_s[s]["auth"]   for s in SCHEME_LABELS]
t_keyex = [total_s[s]["keyex"]  for s in SCHEME_LABELS]
t_bot   = [e + a for e, a in zip(t_enr, t_auth)]

ax.bar(x_pos, t_enr,  W, label="Enrollment",                color=C_ENROLL, edgecolor="white", linewidth=0.5)
ax.bar(x_pos, t_auth, W, bottom=t_enr,                      label="Authentication (Round 1)", color=C_AUTH,   edgecolor="white", linewidth=0.5)
ax.bar(x_pos, t_keyex,W, bottom=t_bot,
       label="Key Exchange (Round 2)  [included in Auth for Zhou]", color=C_KEYEX, edgecolor="white", linewidth=0.5)

for i, s in enumerate(SCHEME_LABELS):
    tot = total_s[s]["combined"]
    ax.text(i, tot + total_s[ZH]["combined"] * 0.02,
            f"{tot:.2f} s", ha="center", va="bottom", fontsize=10, fontweight="bold")

ax.set_xticks(x_pos)
ax.set_xticklabels([SCHEME_SHORT[s] for s in SCHEME_LABELS], fontsize=12)
ax.set_ylim(0, max(total_s[s]["combined"] for s in SCHEME_LABELS) * 1.18)
ax.legend(fontsize=10, framealpha=0.9, loc="upper right")
apply_style(ax,
    f"All-Nodes Combined CPU Time — All 3 Phases ({NUM_NODES} Devices)\n"
    "COOJA Simulation, TelosB Motes",
    f"Total CPU Time — All {NUM_NODES} Nodes (s)")
plt.tight_layout()
save(fig, "14_time_combined_all_nodes_stacked.png")

# ── Chart 15 — Per-device combined CPU line chart ─────────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))

ax.plot(ra_ids, ra_cpu_dev, "o-",
        color=SCHEME_COLORS[RA], label=RA, linewidth=2, markersize=6)
ax.plot(lk_ids, lk_cpu_dev, "s--",
        color=SCHEME_COLORS[LK], label=LK, linewidth=2, markersize=6)
ax.plot(zh_ids, zh_cpu_dev, "^:",
        color=SCHEME_COLORS[ZH], label=f"{ZH}  (Auth only — KeyEx included)",
        linewidth=2, markersize=6)

for s, vals in [(RA, ra_cpu_dev), (LK, lk_cpu_dev), (ZH, zh_cpu_dev)]:
    ax.axhline(statistics.mean(vals), color=SCHEME_COLORS[s],
               linestyle=":", alpha=0.55, linewidth=1.2)

ax.set_xlabel("Device ID", fontsize=12)
apply_style(ax,
    "Per-Device Combined CPU Time (Enrollment + Auth + Key Exchange)\n"
    "COOJA Simulation, TelosB Motes",
    "CPU Time (s)",
    xlabel="Device ID")
ax.legend(fontsize=10, framealpha=0.9)
plt.tight_layout()
save(fig, "15_time_per_device_combined_line.png")

# ── Chart 16 — Grouped bar: per-phase + combined ─────────────────────────────
phases_labels = ["Enrollment", "Auth\n(Round 1)", "Key Exchange\n(Round 2)", "Combined\n(All Phases)"]
phase_keys    = ["enroll", "auth", "keyex", "combined"]

fig, ax = plt.subplots(figsize=(12, 6))
ph_pos  = np.arange(len(phases_labels))
w       = 0.22
offsets = np.array([-w, 0, w])

for i, s in enumerate(SCHEME_LABELS):
    vals = [avg_s[s][k] for k in phase_keys]
    bars = ax.bar(ph_pos + offsets[i], vals, w,
                  label=s, color=SCHEME_COLORS[s],
                  edgecolor="white", linewidth=0.5)
    for bar, v in zip(bars, vals):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.005,
                    f"{v:.3f}", ha="center", va="bottom",
                    fontsize=7.5, rotation=90)

ax.set_xticks(ph_pos)
ax.set_xticklabels(phases_labels, fontsize=11)
ax.legend(fontsize=10, framealpha=0.9)
ax.text(0.01, 0.98,
        "* Zhou enrollment CPU not separately recorded; Key Exchange included in Auth",
        transform=ax.transAxes, fontsize=8, va="top", color="#555555")
apply_style(ax,
    "CPU Computation Time per Phase — All Schemes (Per-Device Average)\n"
    "COOJA Simulation, 20 TelosB Motes",
    "Mean CPU Time per Device (s)")
plt.tight_layout()
save(fig, "16_time_grouped_per_phase_and_combined.png")

# ── Chart 17 — All-nodes combined simple bar ─────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))

totals = [total_s[s]["combined"] for s in SCHEME_LABELS]
bars = ax.bar([SCHEME_SHORT[s] for s in SCHEME_LABELS], totals, width=0.50,
              color=[SCHEME_COLORS[s] for s in SCHEME_LABELS],
              edgecolor="black", linewidth=0.9)

for bar, v in zip(bars, totals):
    ax.text(bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(totals) * 0.01,
            f"{v:.2f} s", ha="center", va="bottom",
            fontsize=11, fontweight="bold")

ra_tot = total_s[RA]["combined"]
for s, xoff, yoff in [(LK, 1, 0.55), (ZH, 2, 0.55)]:
    saving = (total_s[s]["combined"] - ra_tot) / ra_tot * 100
    ax.annotate(f"RA saves\n{saving:.0f}%",
                xy=(0, ra_tot * 0.5), xytext=(xoff, totals[xoff] * yoff),
                arrowprops=dict(arrowstyle="->", color="#333333", lw=1.2),
                fontsize=8.5, ha="center", color="#333333")

ax.set_ylim(0, max(totals) * 1.22)
apply_style(ax,
    f"Total CPU Computation Time — All Phases ({NUM_NODES} Devices)\n"
    "COOJA Simulation, TelosB Motes",
    f"Total CPU Time — All {NUM_NODES} Nodes (s)")
plt.tight_layout()
save(fig, "17_time_all_nodes_combined_bar.png")

print(f"\nAll time charts -> {OUT_DIR}")
print("Done!")
