#!/usr/bin/env python3
"""
compare_schemes.py  —  LAAKA vs Revised-Anonymity hardware metrics comparison.

Reads:
  LAAKA/results/hw_metrics_clean.csv
  Revised-Anonymity/results/hw_metrics_clean.csv  (detailed table format)

Produces (in Hardware/comparison/):
  summary_table.csv
  fig1_bytes_per_phase.png
  fig2_energy_per_phase.png
  fig3_cpu_time_per_phase.png
  fig4_data_packet_overhead.png
  fig5_total_overhead.png
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import csv

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
OUT  = BASE / "comparison"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Hard-coded metrics (extracted from both result files)
# ---------------------------------------------------------------------------

# ------ Revised-Anonymity (real RPi hardware, 3-second data interval) ------
RA = {
    "enroll":  dict(cpu_s=0.002674, tx=184,  rx=143,  total_b=327,  energy_j=0.007339),
    "auth":    dict(cpu_s=0.000322, tx=162,  rx=38,   total_b=200,  energy_j=0.001205),
    "keyex":   dict(cpu_s=0.000265, tx=99,   rx=93,   total_b=192,  energy_j=0.001047),
    "data10":  dict(cpu_s=0.006866, tx=1240, rx=0,    total_b=1240, energy_j=0.019645),
    "total":   dict(cpu_s=0.010127, tx=1685, rx=274,  total_b=1959, energy_j=0.029235),
}
RA["auth_kex"] = dict(
    cpu_s   = RA["auth"]["cpu_s"]   + RA["keyex"]["cpu_s"],
    tx      = RA["auth"]["tx"]      + RA["keyex"]["tx"],
    rx      = RA["auth"]["rx"]      + RA["keyex"]["rx"],
    total_b = RA["auth"]["total_b"] + RA["keyex"]["total_b"],
    energy_j= RA["auth"]["energy_j"]+ RA["keyex"]["energy_j"],
)
RA["per_pkt"] = dict(
    cpu_s   = RA["data10"]["cpu_s"]   / 10,
    tx      = RA["data10"]["tx"]      // 10,
    rx      = 0,
    total_b = RA["data10"]["total_b"] // 10,
    energy_j= RA["data10"]["energy_j"]/ 10,
)

# ------ LAAKA (localhost simulation, 1-second data interval) ---------------
LK = {
    "register": dict(cpu_s=0.0, tx=91,   rx=187, total_b=278,  energy_j=0.000556),
    "auth":     dict(cpu_s=0.0, tx=194,  rx=196, total_b=390,  energy_j=0.000780),
    "ack":      dict(cpu_s=0.0, tx=107,  rx=0,   total_b=107,  energy_j=0.000214),
    "data10":   dict(cpu_s=0.0, tx=1000, rx=0,   total_b=1000, energy_j=0.002000),
    "total":    dict(cpu_s=0.0, tx=1392, rx=383, total_b=1775, energy_j=0.003550),
}
LK["auth_ack"] = dict(
    cpu_s   = LK["auth"]["cpu_s"] + LK["ack"]["cpu_s"],
    tx      = LK["auth"]["tx"]    + LK["ack"]["tx"],
    rx      = LK["auth"]["rx"]    + LK["ack"]["rx"],
    total_b = LK["auth"]["total_b"]+ LK["ack"]["total_b"],
    energy_j= LK["auth"]["energy_j"]+LK["ack"]["energy_j"],
)
LK["per_pkt"] = dict(
    cpu_s   = 0.0,
    tx      = LK["data10"]["tx"]      // 10,
    rx      = 0,
    total_b = LK["data10"]["total_b"] // 10,
    energy_j= LK["data10"]["energy_j"]/ 10,
)

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family":     "DejaVu Sans",
    "font.size":       11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid":       True,
    "grid.color":      "#e0e0e0",
    "grid.linewidth":  0.8,
    "figure.dpi":      150,
})

C_RA = "#2563EB"   # blue  — Revised-Anonymity
C_LK = "#16A34A"   # green — LAAKA

def save(fig, name):
    path = OUT / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path.name}")

# ---------------------------------------------------------------------------
# Fig 1  —  Communication bytes per phase
# ---------------------------------------------------------------------------
phases_bytes = ["Registration /\nEnrollment", "Authentication\n(Auth+KeyEx / Auth+Ack)", "Per Data\nPacket", "Total\n(excl. data interval)"]
ra_bytes = [
    RA["enroll"]["total_b"],
    RA["auth_kex"]["total_b"],
    RA["per_pkt"]["total_b"],
    RA["total"]["total_b"],
]
lk_bytes = [
    LK["register"]["total_b"],
    LK["auth_ack"]["total_b"],
    LK["per_pkt"]["total_b"],
    LK["total"]["total_b"],
]

x  = np.arange(len(phases_bytes))
w  = 0.35
fig, ax = plt.subplots(figsize=(10, 5))
b1 = ax.bar(x - w/2, ra_bytes, w, label="Revised-Anonymity", color=C_RA, zorder=3)
b2 = ax.bar(x + w/2, lk_bytes, w, label="LAAKA",             color=C_LK, zorder=3)

for rect, val in zip(b1, ra_bytes):
    ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 8,
            f"{val}", ha="center", va="bottom", fontsize=9, color=C_RA, fontweight="bold")
for rect, val in zip(b2, lk_bytes):
    ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 8,
            f"{val}", ha="center", va="bottom", fontsize=9, color=C_LK, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(phases_bytes, fontsize=10)
ax.set_ylabel("Total Bytes (Tx + Rx)")
ax.set_title("Communication Overhead per Phase\nRevised-Anonymity vs LAAKA", fontweight="bold", pad=12)
ax.legend(framealpha=0.9)
ax.set_ylim(0, max(max(ra_bytes), max(lk_bytes)) * 1.18)
save(fig, "fig1_bytes_per_phase.png")

# ---------------------------------------------------------------------------
# Fig 2  —  Network energy per phase  (bytes × 2e-6 J/byte — fair for both)
# NET_J = 0.000002 J/byte
# ---------------------------------------------------------------------------
NET_J = 0.000002
phases_e = ["Registration /\nEnrollment", "Authentication\n(Auth+KeyEx / Auth+Ack)", "Per Data\nPacket", "Total"]
ra_net_e = [
    RA["enroll"]["total_b"]    * NET_J * 1e3,
    RA["auth_kex"]["total_b"]  * NET_J * 1e3,
    RA["per_pkt"]["total_b"]   * NET_J * 1e3,
    RA["total"]["total_b"]     * NET_J * 1e3,
]
lk_net_e = [
    LK["register"]["total_b"]  * NET_J * 1e3,
    LK["auth_ack"]["total_b"]  * NET_J * 1e3,
    LK["per_pkt"]["total_b"]   * NET_J * 1e3,
    LK["total"]["total_b"]     * NET_J * 1e3,
]

fig, ax = plt.subplots(figsize=(10, 5))
b1 = ax.bar(x - w/2, ra_net_e, w, label="Revised-Anonymity", color=C_RA, zorder=3)
b2 = ax.bar(x + w/2, lk_net_e, w, label="LAAKA",             color=C_LK, zorder=3)

for rect, val in zip(b1, ra_net_e):
    ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.002,
            f"{val:.4f}", ha="center", va="bottom", fontsize=9, color=C_RA, fontweight="bold")
for rect, val in zip(b2, lk_net_e):
    ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.002,
            f"{val:.4f}", ha="center", va="bottom", fontsize=9, color=C_LK, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(phases_e, fontsize=10)
ax.set_ylabel("Network Energy (mJ)  [bytes x 2e-6 J/byte]")
ax.set_title("Network Communication Energy per Phase\nRevised-Anonymity vs LAAKA\n"
             "(CPU energy excluded — proportional to bytes, same model for both)",
             fontweight="bold", pad=12)
ax.legend(framealpha=0.9)
ax.set_ylim(0, max(max(ra_net_e), max(lk_net_e)) * 1.22)
save(fig, "fig2_energy_per_phase.png")

# ---------------------------------------------------------------------------
# Fig 3  —  CPU computation time per phase  (RA only — LAAKA=0 on local sim)
# ---------------------------------------------------------------------------
phases_cpu = ["Enrollment", "Auth", "KeyEx", "Data (10 pkts)", "Total"]
ra_cpu_ms = [
    RA["enroll"]["cpu_s"]  * 1e3,
    RA["auth"]["cpu_s"]    * 1e3,
    RA["keyex"]["cpu_s"]   * 1e3,
    RA["data10"]["cpu_s"]  * 1e3,
    RA["total"]["cpu_s"]   * 1e3,
]
lk_phases_cpu = ["Register", "Auth", "Ack", "Data (10 pkts)", "Total"]
lk_cpu_ms = [
    LK["register"]["cpu_s"] * 1e3,
    LK["auth"]["cpu_s"]     * 1e3,
    LK["ack"]["cpu_s"]      * 1e3,
    LK["data10"]["cpu_s"]   * 1e3,
    LK["total"]["cpu_s"]    * 1e3,
]

x5 = np.arange(len(phases_cpu))
fig, ax = plt.subplots(figsize=(11, 5))
b1 = ax.bar(x5 - w/2, ra_cpu_ms, w, label="Revised-Anonymity (RPi)", color=C_RA, zorder=3)
b2 = ax.bar(x5 + w/2, lk_cpu_ms, w, label="LAAKA (local sim — undercount)", color=C_LK,
            zorder=3, hatch="//", edgecolor="white")

for rect, val in zip(b1, ra_cpu_ms):
    if val > 0:
        ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.02,
                f"{val:.3f}", ha="center", va="bottom", fontsize=9, color=C_RA, fontweight="bold")

ax.set_xticks(x5)
ax.set_xticklabels([f"{a}\n({b})" for a, b in zip(phases_cpu, lk_phases_cpu)], fontsize=9)
ax.set_ylabel("CPU Time (ms)")
ax.set_title("CPU Computation Time per Phase\n(LAAKA=0 ms: local sim has no resolution — network bytes dominate energy)",
             fontweight="bold", pad=12)
ax.legend(framealpha=0.9)
ax.set_ylim(0, max(ra_cpu_ms) * 1.25)
save(fig, "fig3_cpu_time_per_phase.png")

# ---------------------------------------------------------------------------
# Fig 4  —  Tx/Rx breakdown per phase (stacked)
# ---------------------------------------------------------------------------
phases4 = ["Enroll /\nRegister", "Auth +\nKeyEx / Ack", "Per Pkt\nData", "Total"]
ra_tx4 = [RA["enroll"]["tx"], RA["auth_kex"]["tx"], RA["per_pkt"]["tx"], RA["total"]["tx"]]
ra_rx4 = [RA["enroll"]["rx"], RA["auth_kex"]["rx"], RA["per_pkt"]["rx"], RA["total"]["rx"]]
lk_tx4 = [LK["register"]["tx"], LK["auth_ack"]["tx"], LK["per_pkt"]["tx"], LK["total"]["tx"]]
lk_rx4 = [LK["register"]["rx"], LK["auth_ack"]["rx"], LK["per_pkt"]["rx"], LK["total"]["rx"]]

x4 = np.arange(len(phases4))
w4 = 0.32
fig, ax = plt.subplots(figsize=(10, 5))

# RA bars
ax.bar(x4 - w4/2, ra_tx4, w4, label="RA  Tx", color=C_RA, zorder=3)
ax.bar(x4 - w4/2, ra_rx4, w4, bottom=ra_tx4, label="RA  Rx", color=C_RA, alpha=0.45, zorder=3)
# LK bars
ax.bar(x4 + w4/2, lk_tx4, w4, label="LAAKA Tx", color=C_LK, zorder=3)
ax.bar(x4 + w4/2, lk_rx4, w4, bottom=lk_tx4, label="LAAKA Rx", color=C_LK, alpha=0.45, zorder=3)

# Totals on top
for i, (rt, rr, lt, lr) in enumerate(zip(ra_tx4, ra_rx4, lk_tx4, lk_rx4)):
    ax.text(i - w4/2, rt + rr + 5, str(rt + rr), ha="center", va="bottom", fontsize=8,
            color=C_RA, fontweight="bold")
    ax.text(i + w4/2, lt + lr + 5, str(lt + lr), ha="center", va="bottom", fontsize=8,
            color=C_LK, fontweight="bold")

ax.set_xticks(x4)
ax.set_xticklabels(phases4, fontsize=10)
ax.set_ylabel("Bytes")
ax.set_title("Tx / Rx Byte Breakdown per Phase\nRevised-Anonymity vs LAAKA", fontweight="bold", pad=12)
ax.legend(ncol=2, framealpha=0.9, fontsize=9)
ax.set_ylim(0, max(max(r+x for r,x in zip(ra_tx4,ra_rx4)),
                   max(l+y for l,y in zip(lk_tx4,lk_rx4))) * 1.2)
save(fig, "fig4_tx_rx_breakdown.png")

# ---------------------------------------------------------------------------
# Fig 5  —  Per-packet data overhead  (focused)
# ---------------------------------------------------------------------------
labels5 = ["Payload\nsize (B)", "Energy\n(mJ)"]
ra_vals5 = [RA["per_pkt"]["total_b"], RA["per_pkt"]["energy_j"] * 1e3]
lk_vals5 = [LK["per_pkt"]["total_b"], LK["per_pkt"]["energy_j"] * 1e3]

x5b = np.arange(len(labels5))
w5 = 0.3
fig, axes = plt.subplots(1, 2, figsize=(9, 4))
axes = axes.flatten()

for ax, lbl, rv, lv, unit in zip(
    axes,
    ["Per-Packet Communication (bytes)", "Per-Packet Energy (mJ)"],
    [RA["per_pkt"]["total_b"], RA["per_pkt"]["energy_j"] * 1e3],
    [LK["per_pkt"]["total_b"], LK["per_pkt"]["energy_j"] * 1e3],
    ["B", "mJ"],
):
    b1 = ax.bar(0 - 0.18, rv, 0.32, label="Revised-Anonymity", color=C_RA, zorder=3)
    b2 = ax.bar(0 + 0.18, lv, 0.32, label="LAAKA",             color=C_LK, zorder=3)
    ax.text(-0.18, rv + rv * 0.03, f"{rv:.4g} {unit}", ha="center", va="bottom",
            fontsize=11, color=C_RA, fontweight="bold")
    ax.text(+0.18, lv + lv * 0.03, f"{lv:.4g} {unit}", ha="center", va="bottom",
            fontsize=11, color=C_LK, fontweight="bold")
    savings = (rv - lv) / rv * 100
    ax.set_title(f"{lbl}\n(LAAKA saves {savings:.1f}%)", fontweight="bold", fontsize=10)
    ax.set_xlim(-0.5, 0.5)
    ax.set_xticks([])
    ax.set_ylim(0, max(rv, lv) * 1.28)
    ax.legend(fontsize=9)

fig.suptitle("Per Data Packet Overhead\nRevised-Anonymity vs LAAKA", fontweight="bold", fontsize=12)
fig.tight_layout()
save(fig, "fig5_per_packet_overhead.png")

# ---------------------------------------------------------------------------
# Summary table  —  CSV
# ---------------------------------------------------------------------------
rows = [
    ["Metric", "Phase", "Revised-Anonymity", "LAAKA", "Saving (%)"],
    # Bytes
    ["Comm. bytes (B)",   "Registration / Enrollment",    RA["enroll"]["total_b"],    LK["register"]["total_b"],  f"{(RA['enroll']['total_b']-LK['register']['total_b'])/RA['enroll']['total_b']*100:.1f}%"],
    ["Comm. bytes (B)",   "Authentication (Auth+KEx/Ack)", RA["auth_kex"]["total_b"], LK["auth_ack"]["total_b"],  f"{(RA['auth_kex']['total_b']-LK['auth_ack']['total_b'])/RA['auth_kex']['total_b']*100:.1f}%"],
    ["Comm. bytes (B)",   "Per data packet",              RA["per_pkt"]["total_b"],   LK["per_pkt"]["total_b"],   f"{(RA['per_pkt']['total_b']-LK['per_pkt']['total_b'])/RA['per_pkt']['total_b']*100:.1f}%"],
    ["Comm. bytes (B)",   "Total",                        RA["total"]["total_b"],     LK["total"]["total_b"],     f"{(RA['total']['total_b']-LK['total']['total_b'])/RA['total']['total_b']*100:.1f}%"],
    # Network energy (bytes-based, fair comparison)
    ["Net Energy (mJ)",   "Registration / Enrollment",    f"{RA['enroll']['total_b']*NET_J*1e3:.4f}",    f"{LK['register']['total_b']*NET_J*1e3:.4f}",   f"{(RA['enroll']['total_b']-LK['register']['total_b'])/RA['enroll']['total_b']*100:.1f}%"],
    ["Net Energy (mJ)",   "Authentication (Auth+KEx/Ack)", f"{RA['auth_kex']['total_b']*NET_J*1e3:.4f}", f"{LK['auth_ack']['total_b']*NET_J*1e3:.4f}",   f"{(RA['auth_kex']['total_b']-LK['auth_ack']['total_b'])/RA['auth_kex']['total_b']*100:.1f}%"],
    ["Net Energy (mJ)",   "Per data packet",              f"{RA['per_pkt']['total_b']*NET_J*1e3:.4f}",   f"{LK['per_pkt']['total_b']*NET_J*1e3:.4f}",    f"{(RA['per_pkt']['total_b']-LK['per_pkt']['total_b'])/RA['per_pkt']['total_b']*100:.1f}%"],
    ["Net Energy (mJ)",   "Total",                        f"{RA['total']['total_b']*NET_J*1e3:.4f}",     f"{LK['total']['total_b']*NET_J*1e3:.4f}",      f"{(RA['total']['total_b']-LK['total']['total_b'])/RA['total']['total_b']*100:.1f}%"],
    # CPU time (RA only)
    ["CPU time (ms)",     "Enrollment",                   f"{RA['enroll']['cpu_s']*1e3:.4f}",       "N/A (local sim)",   "—"],
    ["CPU time (ms)",     "Auth + KeyEx / Auth + Ack",    f"{RA['auth_kex']['cpu_s']*1e3:.4f}",     "N/A (local sim)",   "—"],
    ["CPU time (ms)",     "Data (10 pkts)",               f"{RA['data10']['cpu_s']*1e3:.4f}",       "N/A (local sim)",   "—"],
    ["CPU time (ms)",     "Total",                        f"{RA['total']['cpu_s']*1e3:.4f}",        "N/A (local sim)",   "—"],
]

csv_path = OUT / "summary_table.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(rows)
print(f"  Saved {csv_path.name}")

# ---------------------------------------------------------------------------
# Print table to console
# ---------------------------------------------------------------------------
print("\n" + "=" * 75)
print(f"{'Metric':<22} {'Phase':<35} {'Rev-Anon':>12} {'LAAKA':>10} {'Saving':>8}")
print("=" * 75)
for r in rows[1:]:
    print(f"{r[0]:<22} {r[1]:<35} {str(r[2]):>12} {str(r[3]):>10} {str(r[4]):>8}")
    if r == rows[4] or r == rows[8]:
        print("-" * 75)
print("=" * 75)
print(f"\nAll outputs saved to: {OUT}/")
