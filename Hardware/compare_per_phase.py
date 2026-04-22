#!/usr/bin/env python3
"""
compare_per_phase.py  —  Per-phase metric comparison: Revised-Anonymity vs LAAKA.

Sources:
  COOJA simulation  — CPU time + energy from raw per-device CSVs
  Hardware          — communication bytes from hw_metrics_clean.csv files

Outputs (Hardware/comparison/):
  phase_table_simulation.csv
  phase_table_hardware.csv
  fig_sim_energy.png
  fig_sim_cpu.png
  fig_hw_bytes.png
  fig_hw_bytes_txrx.png
"""

from pathlib import Path
import csv
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
OUT  = BASE / "comparison"
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "axes.grid.axis":    "y",
    "grid.color":        "#e0e0e0",
    "grid.linewidth":    0.8,
    "figure.dpi":        150,
})

C_RA = "#2563EB"   # blue  — Revised-Anonymity
C_LK = "#16A34A"   # green — LAAKA
W    = 0.32        # bar width

def save(fig, name):
    p = OUT / name
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {p.name}")

def avg(lst):  return statistics.mean(lst)
def std(lst):  return statistics.stdev(lst) if len(lst) > 1 else 0.0

# ---------------------------------------------------------------------------
# Raw per-device data
# ---------------------------------------------------------------------------

# -- Revised-Anonymity --
RA = {
    "enroll": {
        "cpu": [0.340368,0.335368,0.344368,0.337368,0.300368,0.340368,0.344368,
                0.547624,0.469624,0.446624,0.339368,0.334368,0.320368,0.312368,
                0.388624,0.465624,0.465624,0.381624,0.340624,0.413624],
        "ej":  [0.020960,0.020675,0.021231,0.020798,0.018512,0.020984,0.021231,
                0.033792,0.028972,0.027550,0.020922,0.020613,0.019748,0.019253,
                0.023966,0.028724,0.028724,0.023533,0.020999,0.025511],
    },
    "auth": {
        "cpu": [0.236112,0.222112,0.216112,0.258224,0.211112,0.223112,0.299112,
                0.230368,0.315368,0.266368,0.247112,0.261112,0.222112,0.290112,
                0.273368,0.314368,0.310368,0.324368,0.191368,0.334368],
        "ej":  [0.014549,0.013684,0.013313,0.015916,0.013004,0.013746,0.018443,
                0.014194,0.019447,0.016419,0.015229,0.016094,0.013671,0.017886,
                0.016852,0.019385,0.019138,0.020003,0.011784,0.020621],
    },
    "keyex": {
        "cpu": [0.186072,0.189144,0.219072,0.150072,0.193072,0.213072,0.294072,
                0.191328,0.252328,0.161328,0.142072,0.117072,0.179072,0.145072,
                0.235328,0.280328,0.201328,0.290328,0.206328,0.273328],
        "ej":  [0.011473,0.011663,0.013513,0.009249,0.011906,0.013142,0.018148,
                0.011798,0.015568,0.009944,0.008754,0.007209,0.011041,0.008940,
                0.014517,0.017298,0.012416,0.017916,0.012725,0.016866],
    },
}

# -- LAAKA --
LK = {
    "enroll": {
        "cpu": [0.1696,0.1346,0.1776,0.1666,0.205664,0.1846,0.1516,0.235856,
                0.273856,0.271856,0.1596,0.1366,0.1836,0.1016,0.223856,
                0.221856,0.313856,0.367856,0.269856,0.228856],
        "ej":  [0.010451,0.008288,0.010946,0.010266,0.01268,0.011378,0.009339,
                0.014546,0.016894,0.016771,0.009833,0.008412,0.011316,0.006249,
                0.013804,0.013681,0.019366,0.022703,0.016647,0.014113],
    },
    "auth": {
        "cpu": [0.61008,0.63416,0.61308,0.71108,0.69808,0.920336,0.941336,
                0.766672,0.51016,0.69008,0.759336,0.804336,0.62008],
        "ej":  [0.037601,0.039089,0.037786,0.043843,0.043039,0.056775,0.058073,
                0.047278,0.031426,0.042545,0.046825,0.049606,0.038219],
    },
    "keyex": {
        "cpu": [0.451112,0.526112,0.422112,0.519112,0.594112,0.748368,0.637368,
                0.581368,0.375112,0.525112,0.528368,0.591368,0.551112],
        "ej":  [0.027803,0.032438,0.026011,0.032005,0.03664,0.046173,0.039314,
                0.035853,0.023106,0.032376,0.032577,0.036471,0.033983],
    },
}

# Derived combined phase
for D in (RA, LK):
    D["auth_kex"] = {
        "cpu": [a + k for a, k in zip(D["auth"]["cpu"], D["keyex"]["cpu"])],
        "ej":  [a + k for a, k in zip(D["auth"]["ej"],  D["keyex"]["ej"])],
    }

# ---------------------------------------------------------------------------
# Aggregated stats
# ---------------------------------------------------------------------------
SIM_PHASES   = ["enroll", "auth", "keyex", "auth_kex"]
SIM_LABELS   = ["Enrollment", "Authentication", "Key Exchange", "Auth + Key Exchange\n(combined)"]
SIM_LABELS_S = ["Enrollment", "Authentication", "Key Exchange", "Auth+KeyEx"]

def stats(D, phase, metric):
    vals = D[phase][metric]
    return avg(vals), std(vals)

# ---------------------------------------------------------------------------
# Fig 1  —  Simulation Energy per phase
# ---------------------------------------------------------------------------
ra_e_avg = [stats(RA, p, "ej")[0]*1e3 for p in SIM_PHASES]
ra_e_std = [stats(RA, p, "ej")[1]*1e3 for p in SIM_PHASES]
lk_e_avg = [stats(LK, p, "ej")[0]*1e3 for p in SIM_PHASES]
lk_e_std = [stats(LK, p, "ej")[1]*1e3 for p in SIM_PHASES]

x = np.arange(len(SIM_PHASES))
fig, ax = plt.subplots(figsize=(11, 5.5))

b1 = ax.bar(x - W/2, ra_e_avg, W, yerr=ra_e_std, capsize=4,
            label="Revised-Anonymity", color=C_RA, zorder=3, error_kw={"ecolor":"#1e3a8a","lw":1.5})
b2 = ax.bar(x + W/2, lk_e_avg, W, yerr=lk_e_std, capsize=4,
            label="LAAKA",             color=C_LK, zorder=3, error_kw={"ecolor":"#14532d","lw":1.5})

for rect, val, sd in zip(b1, ra_e_avg, ra_e_std):
    ax.text(rect.get_x() + rect.get_width()/2, val + sd + 0.6,
            f"{val:.2f}", ha="center", va="bottom", fontsize=9, color=C_RA, fontweight="bold")
for rect, val, sd in zip(b2, lk_e_avg, lk_e_std):
    ax.text(rect.get_x() + rect.get_width()/2, val + sd + 0.6,
            f"{val:.2f}", ha="center", va="bottom", fontsize=9, color=C_LK, fontweight="bold")

# ratio annotations
for i, (r, l) in enumerate(zip(ra_e_avg, lk_e_avg)):
    ratio = l / r if r < l else r / l
    winner = "RA" if r < l else "LK"
    color = C_RA if winner == "RA" else C_LK
    top = max(r, l) + max(ra_e_std[i], lk_e_std[i]) + 3.5
    ax.text(i, top, f"{ratio:.2f}×", ha="center", fontsize=9,
            color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=0.8))

ax.set_xticks(x)
ax.set_xticklabels(SIM_LABELS, fontsize=10)
ax.set_ylabel("Energy (mJ)", fontsize=11)
ax.set_title("COOJA Simulation — Energy per Phase\nRevised-Anonymity vs LAAKA  (mean ± std, 20 devices RA / 13–20 devices LAAKA)",
             fontweight="bold", pad=12)
ax.legend(framealpha=0.9, fontsize=10)
ax.set_ylim(0, max(max(lk_e_avg), max(ra_e_avg)) + max(lk_e_std) + 16)
save(fig, "fig_sim_energy.png")

# ---------------------------------------------------------------------------
# Fig 2  —  Simulation CPU time per phase
# ---------------------------------------------------------------------------
ra_c_avg = [stats(RA, p, "cpu")[0]*1e3 for p in SIM_PHASES]
ra_c_std = [stats(RA, p, "cpu")[1]*1e3 for p in SIM_PHASES]
lk_c_avg = [stats(LK, p, "cpu")[0]*1e3 for p in SIM_PHASES]
lk_c_std = [stats(LK, p, "cpu")[1]*1e3 for p in SIM_PHASES]

fig, ax = plt.subplots(figsize=(11, 5.5))
b1 = ax.bar(x - W/2, ra_c_avg, W, yerr=ra_c_std, capsize=4,
            label="Revised-Anonymity", color=C_RA, zorder=3, error_kw={"ecolor":"#1e3a8a","lw":1.5})
b2 = ax.bar(x + W/2, lk_c_avg, W, yerr=lk_c_std, capsize=4,
            label="LAAKA",             color=C_LK, zorder=3, error_kw={"ecolor":"#14532d","lw":1.5})

for rect, val, sd in zip(b1, ra_c_avg, ra_c_std):
    ax.text(rect.get_x() + rect.get_width()/2, val + sd + 4,
            f"{val:.1f}", ha="center", va="bottom", fontsize=9, color=C_RA, fontweight="bold")
for rect, val, sd in zip(b2, lk_c_avg, lk_c_std):
    ax.text(rect.get_x() + rect.get_width()/2, val + sd + 4,
            f"{val:.1f}", ha="center", va="bottom", fontsize=9, color=C_LK, fontweight="bold")

for i, (r, l) in enumerate(zip(ra_c_avg, lk_c_avg)):
    ratio = l / r if r < l else r / l
    winner = "RA" if r < l else "LK"
    color = C_RA if winner == "RA" else C_LK
    top = max(r, l) + max(ra_c_std[i], lk_c_std[i]) + 25
    ax.text(i, top, f"{ratio:.2f}×", ha="center", fontsize=9,
            color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=0.8))

ax.set_xticks(x)
ax.set_xticklabels(SIM_LABELS, fontsize=10)
ax.set_ylabel("CPU Time (ms)", fontsize=11)
ax.set_title("COOJA Simulation — CPU Computation Time per Phase\nRevised-Anonymity vs LAAKA  (mean ± std)",
             fontweight="bold", pad=12)
ax.legend(framealpha=0.9, fontsize=10)
ax.set_ylim(0, max(max(lk_c_avg), max(ra_c_avg)) + max(lk_c_std) + 100)
save(fig, "fig_sim_cpu.png")

# ---------------------------------------------------------------------------
# Fig 3  —  Hardware bytes per phase  (Tx + Rx stacked)
# ---------------------------------------------------------------------------
HW_PHASES  = ["Registration /\nEnrollment", "Authentication\nAuth+KeyEx / Auth+Ack",
               "Per Data\nPacket", "Total"]
ra_tx = [184, 261, 124, 1685]
ra_rx = [143, 131,   0,  274]
lk_tx = [ 91, 301, 100, 1392]
lk_rx = [187, 196,   0,  383]
ra_tot = [t + r for t, r in zip(ra_tx, ra_rx)]
lk_tot = [t + r for t, r in zip(lk_tx, lk_rx)]

x4 = np.arange(len(HW_PHASES))
W4 = 0.30
fig, ax = plt.subplots(figsize=(11, 5.5))

ax.bar(x4 - W4/2, ra_tx, W4, label="Rev-Anon  Tx", color=C_RA,        zorder=3)
ax.bar(x4 - W4/2, ra_rx, W4, bottom=ra_tx, label="Rev-Anon  Rx",
       color=C_RA, alpha=0.40, zorder=3)
ax.bar(x4 + W4/2, lk_tx, W4, label="LAAKA  Tx", color=C_LK,           zorder=3)
ax.bar(x4 + W4/2, lk_rx, W4, bottom=lk_tx, label="LAAKA  Rx",
       color=C_LK, alpha=0.40, zorder=3)

for i, (rt, lr) in enumerate(zip(ra_tot, lk_tot)):
    ax.text(i - W4/2, rt + 8, str(rt), ha="center", va="bottom",
            fontsize=9, color=C_RA, fontweight="bold")
    ax.text(i + W4/2, lr + 8, str(lr), ha="center", va="bottom",
            fontsize=9, color=C_LK, fontweight="bold")

for i, (r, l) in enumerate(zip(ra_tot, lk_tot)):
    ratio = l / r if r < l else r / l
    winner = "RA" if r < l else "LK"
    color = C_RA if winner == "RA" else C_LK
    ax.text(i, max(r, l) + 50, f"{ratio:.2f}×", ha="center", fontsize=9,
            color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=0.8))

ax.set_xticks(x4)
ax.set_xticklabels(HW_PHASES, fontsize=10)
ax.set_ylabel("Bytes (Tx + Rx)", fontsize=11)
ax.set_title("Hardware Simulation — Communication Bytes per Phase\nRevised-Anonymity vs LAAKA  (Tx = solid, Rx = faded)",
             fontweight="bold", pad=12)
ax.legend(ncol=2, framealpha=0.9, fontsize=9)
ax.set_ylim(0, max(max(ra_tot), max(lk_tot)) * 1.20)
save(fig, "fig_hw_bytes.png")

# ---------------------------------------------------------------------------
# Fig 4  —  Combined 2×2 summary panel
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
fig.suptitle("Per-Phase Metric Comparison: Revised-Anonymity vs LAAKA",
             fontweight="bold", fontsize=14, y=1.01)

panel_data = [
    # (ax, title, x_labels, ra_vals, ra_err, lk_vals, lk_err, ylabel, annotate_top_offset)
    (axes[0, 0],
     "COOJA — Energy (mJ)", SIM_LABELS_S,
     ra_e_avg, ra_e_std, lk_e_avg, lk_e_std, "Energy (mJ)", 4),
    (axes[0, 1],
     "COOJA — CPU Time (ms)", SIM_LABELS_S,
     ra_c_avg, ra_c_std, lk_c_avg, lk_c_std, "CPU Time (ms)", 30),
]

for ax, title, xlbls, ra_v, ra_s, lk_v, lk_s, ylabel, off in panel_data:
    xi = np.arange(len(xlbls))
    ax.bar(xi - W/2, ra_v, W, yerr=ra_s, capsize=3,
           label="Revised-Anonymity", color=C_RA, zorder=3,
           error_kw={"ecolor":"#1e3a8a","lw":1.2})
    ax.bar(xi + W/2, lk_v, W, yerr=lk_s, capsize=3,
           label="LAAKA",             color=C_LK, zorder=3,
           error_kw={"ecolor":"#14532d","lw":1.2})
    for i, (r, l, rs, ls) in enumerate(zip(ra_v, lk_v, ra_s, lk_s)):
        ratio = l / r if r < l else r / l
        color = C_RA if r < l else C_LK
        ax.text(i, max(r,l) + max(rs,ls) + off, f"{ratio:.2f}×",
                ha="center", fontsize=8, color=color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, lw=0.7))
    ax.set_xticks(xi); ax.set_xticklabels(xlbls, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=9); ax.set_title(title, fontweight="bold", fontsize=10)
    ax.legend(fontsize=8, framealpha=0.9)
    ax.grid(axis="y", color="#e0e0e0"); ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.set_ylim(0, max(max(lk_v), max(ra_v)) + max(lk_s) + off * 5)

# Bottom-left: HW bytes (stacked)
ax = axes[1, 0]
xi = np.arange(len(HW_PHASES))
ax.bar(xi - W4/2, ra_tx, W4, label="Rev-Anon Tx",  color=C_RA,        zorder=3)
ax.bar(xi - W4/2, ra_rx, W4, bottom=ra_tx, label="Rev-Anon Rx", color=C_RA, alpha=0.4, zorder=3)
ax.bar(xi + W4/2, lk_tx, W4, label="LAAKA Tx",     color=C_LK,        zorder=3)
ax.bar(xi + W4/2, lk_rx, W4, bottom=lk_tx, label="LAAKA Rx",   color=C_LK, alpha=0.4, zorder=3)
for i, (rt, lr) in enumerate(zip(ra_tot, lk_tot)):
    ax.text(i-W4/2, rt+8, str(rt), ha="center", fontsize=7, color=C_RA, fontweight="bold")
    ax.text(i+W4/2, lr+8, str(lr), ha="center", fontsize=7, color=C_LK, fontweight="bold")
    ratio = max(rt,lr)/min(rt,lr)
    color = C_RA if rt < lr else C_LK
    ax.text(i, max(rt,lr)+60, f"{ratio:.2f}×", ha="center", fontsize=8,
            color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, lw=0.7))
ax.set_xticks(xi); ax.set_xticklabels(HW_PHASES, fontsize=8)
ax.set_ylabel("Bytes", fontsize=9)
ax.set_title("Hardware — Comm. Bytes (Tx solid, Rx faded)", fontweight="bold", fontsize=10)
ax.legend(ncol=2, fontsize=7, framealpha=0.9)
ax.grid(axis="y", color="#e0e0e0"); ax.set_axisbelow(True)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.set_ylim(0, max(max(ra_tot), max(lk_tot)) * 1.22)

# Bottom-right: winner summary table as text
ax = axes[1, 1]
ax.axis("off")
table_data = [
    ["Phase", "Metric", "Rev-Anon", "LAAKA", "Winner", "Factor"],
    ["Enrollment",    "Energy",    "23.33 mJ", "12.88 mJ", "LAAKA",    "1.81×"],
    ["Enrollment",    "CPU time",  "378 ms",   "209 ms",   "LAAKA",    "1.81×"],
    ["Enrollment",    "HW bytes",  "327 B",    "278 B",    "LAAKA",    "1.18×"],
    ["Auth",          "Energy",    "16.17 mJ", "44.01 mJ", "Rev-Anon", "2.72×"],
    ["Auth",          "CPU time",  "262 ms",   "714 ms",   "Rev-Anon", "2.72×"],
    ["Key Exchange",  "Energy",    "12.70 mJ", "33.44 mJ", "Rev-Anon", "2.63×"],
    ["Key Exchange",  "CPU time",  "206 ms",   "542 ms",   "Rev-Anon", "2.63×"],
    ["Auth+KeyEx",    "HW bytes",  "392 B",    "497 B",    "Rev-Anon", "1.27×"],
    ["Per data pkt",  "HW bytes",  "124 B",    "100 B",    "LAAKA",    "1.24×"],
    ["TOTAL",         "Energy",    "52.21 mJ", "90.33 mJ", "Rev-Anon", "1.73×"],
    ["TOTAL",         "HW bytes",  "1959 B",   "1775 B",   "LAAKA",    "1.10×"],
]

col_colors = []
for row in table_data[1:]:
    winner = row[4]
    c = C_RA if winner == "Rev-Anon" else C_LK
    col_colors.append(["#f0f0f0", "#f0f0f0", "#f0f0f0", "#f0f0f0",
                        c + "33" if c == C_RA else "#16A34A22", "#f8f8f8"])

tbl = ax.table(
    cellText=table_data[1:],
    colLabels=table_data[0],
    cellLoc="center",
    loc="center",
    bbox=[0, 0, 1, 1],
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
for (row, col), cell in tbl.get_celld().items():
    cell.set_edgecolor("#cccccc")
    if row == 0:
        cell.set_facecolor("#374151")
        cell.set_text_props(color="white", fontweight="bold")
    elif col == 4:
        txt = table_data[row][4]
        cell.set_facecolor("#dbeafe" if txt == "Rev-Anon" else "#dcfce7")
        cell.set_text_props(fontweight="bold",
                            color=C_RA if txt == "Rev-Anon" else C_LK)
    elif col == 5:
        cell.set_facecolor("#f9fafb")
        cell.set_text_props(fontweight="bold")
    else:
        cell.set_facecolor("#ffffff" if row % 2 == 0 else "#f9fafb")

ax.set_title("Summary Table — All Phases", fontweight="bold", fontsize=10, pad=8)

fig.tight_layout()
save(fig, "fig_combined_panel.png")

# ---------------------------------------------------------------------------
# Write CSV tables
# ---------------------------------------------------------------------------
sim_rows = [
    ["Phase", "n_devices",
     "RA_Avg_Energy_mJ", "RA_Std_Energy_mJ", "RA_Avg_CPU_ms", "RA_Std_CPU_ms",
     "LK_Avg_Energy_mJ", "LK_Std_Energy_mJ", "LK_Avg_CPU_ms", "LK_Std_CPU_ms",
     "Energy_Winner", "Energy_Factor", "CPU_Winner", "CPU_Factor"],
]
for ph, lbl in zip(SIM_PHASES, SIM_LABELS_S):
    n_ra = len(RA[ph]["cpu"]); n_lk = len(LK[ph]["cpu"])
    re = avg(RA[ph]["ej"])*1e3; rs = std(RA[ph]["ej"])*1e3
    rc = avg(RA[ph]["cpu"])*1e3; rcs = std(RA[ph]["cpu"])*1e3
    le = avg(LK[ph]["ej"])*1e3; ls = std(LK[ph]["ej"])*1e3
    lc = avg(LK[ph]["cpu"])*1e3; lcs = std(LK[ph]["cpu"])*1e3
    ew = "Rev-Anon" if re < le else "LAAKA"; ef = f"{max(re,le)/min(re,le):.2f}x"
    cw = "Rev-Anon" if rc < lc else "LAAKA"; cf = f"{max(rc,lc)/min(rc,lc):.2f}x"
    sim_rows.append([lbl, f"{n_ra}/{n_lk}",
                     f"{re:.4f}", f"{rs:.4f}", f"{rc:.4f}", f"{rcs:.4f}",
                     f"{le:.4f}", f"{ls:.4f}", f"{lc:.4f}", f"{lcs:.4f}",
                     ew, ef, cw, cf])

with open(OUT / "phase_table_simulation.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(sim_rows)
print(f"  Saved phase_table_simulation.csv")

hw_rows = [
    ["Phase", "RA_Tx_B", "RA_Rx_B", "RA_Total_B", "LK_Tx_B", "LK_Rx_B", "LK_Total_B",
     "Winner", "Factor", "RA_better_pct"],
    ["Registration/Enrollment", 184, 143, 327, 91, 187, 278,
     "LAAKA", "1.18x", "-15.0%"],
    ["Authentication (Auth+KeyEx / Auth+Ack)", 261, 131, 392, 301, 196, 497,
     "Rev-Anon", "1.27x", "+26.8%"],
    ["Per Data Packet", 124, 0, 124, 100, 0, 100,
     "LAAKA", "1.24x", "-19.4%"],
    ["Total", 1685, 274, 1959, 1392, 383, 1775,
     "LAAKA", "1.10x", "-9.4%"],
]
with open(OUT / "phase_table_hardware.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(hw_rows)
print(f"  Saved phase_table_hardware.csv")

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
print()
print("=" * 78)
print("SIMULATION (COOJA) — Per-Phase Summary")
print("=" * 78)
print(f"{'Phase':<22} {'RA Energy':>12} {'LK Energy':>12} {'Winner':>10} {'Factor':>8}")
print("-" * 78)
for ph, lbl in zip(SIM_PHASES, SIM_LABELS_S):
    re = avg(RA[ph]["ej"])*1e3; le = avg(LK[ph]["ej"])*1e3
    w = "Rev-Anon" if re < le else "LAAKA"
    f = f"{max(re,le)/min(re,le):.2f}x"
    print(f"  {lbl:<20} {re:>10.3f}mJ {le:>10.3f}mJ {w:>10} {f:>8}")

print()
print(f"{'Phase':<22} {'RA CPU':>12} {'LK CPU':>12} {'Winner':>10} {'Factor':>8}")
print("-" * 78)
for ph, lbl in zip(SIM_PHASES, SIM_LABELS_S):
    rc = avg(RA[ph]["cpu"])*1e3; lc = avg(LK[ph]["cpu"])*1e3
    w = "Rev-Anon" if rc < lc else "LAAKA"
    f = f"{max(rc,lc)/min(rc,lc):.2f}x"
    print(f"  {lbl:<20} {rc:>11.1f}ms {lc:>11.1f}ms {w:>10} {f:>8}")

print()
print("=" * 78)
print("HARDWARE — Per-Phase Communication Bytes")
print("=" * 78)
print(f"{'Phase':<38} {'RA Bytes':>10} {'LK Bytes':>10} {'Winner':>10} {'Factor':>8}")
print("-" * 78)
for r in hw_rows[1:]:
    w = r[7]; fac = r[8]
    print(f"  {r[0]:<36} {r[3]:>10} {r[6]:>10} {w:>10} {fac:>8}")
print()
print(f"All files saved to: {OUT}/")
