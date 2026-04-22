#!/usr/bin/env python3
"""
compare_hw_schemes.py
=====================
Hardware comparison: Revised-Anonymity vs LAAKA vs Zhou
All three ran on the same 2-RPi + laptop topology.

Comparison axis: the *primary authenticated device* in each scheme
  - Revised-Anonymity : NODE  (Device ID 81, RPi #2)
  - LAAKA             : NODE  (Device ID 81, RPi #2)
  - Zhou              : USER  (Device ID 81, RPi #2)
                        + SN  (Device ID 4,  RPi #1) shown separately

Four protocol phases (aligned across schemes):
  Enroll   → Registration / Enrollment
  Auth     → Authentication message exchange
  KeyEx    → Key Exchange / final ack
  Data     → 10 data packets (3 s each = 30 s total; CPU cost only)
"""

import csv
import pathlib
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT    = pathlib.Path(r"c:\ANUP\MTP\Proposing\Codes For COOJA")
OUT_DIR = ROOT / "Hardware" / "comparison"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RA_CSV   = ROOT / "Hardware" / "Revised-Anonymity" / "results" / "hw_metrics.csv"
LK_CSV   = ROOT / "Hardware" / "LAAKA"             / "results" / "hw_metrics.csv"
ZH_USER  = ROOT / "Hardware" / "Zhou"              / "results" / "hw_metrics_user.csv"
ZH_SN    = ROOT / "Hardware" / "Zhou"              / "results" / "hw_metrics_sn.csv"

# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_row(path: pathlib.Path, role_filter: str = None) -> dict:
    """Return first row (optionally matching Role column)."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    rows = [{k.strip(): v.strip() for k, v in r.items()} for r in rows]
    if role_filter:
        rows = [r for r in rows if r.get("Role", "").upper() == role_filter.upper()]
    return rows[0]

def f(row: dict, col: str) -> float:
    """Strip spaces and return float; 0.0 on missing/blank."""
    v = row.get(col, "0").strip()
    try:
        return float(v)
    except ValueError:
        return 0.0

# Load primary device rows
ra   = load_row(RA_CSV,  "NODE")
lk   = load_row(LK_CSV,  "NODE")
zh_u = load_row(ZH_USER, "USER")
zh_s = load_row(ZH_SN,   "SN")

# ---------------------------------------------------------------------------
# Build unified phase dict for each scheme (primary device perspective)
#
# Phases are deliberately aligned:
#   Enroll  = Enroll / Register
#   Auth    = Auth round
#   KeyEx   = KeyEx / Ack round
#   Data    = Data loop (CPU only — wall_s dominated by sleep interval)
# ---------------------------------------------------------------------------

PHASES = ["Enroll", "Auth", "KeyEx", "Data"]

def build(row: dict, prefix_map: dict) -> dict:
    """
    prefix_map: { 'Enroll': 'Enroll', 'Auth': 'Auth', 'KeyEx': 'Ack', 'Data': 'Data' }
    Returns dict of phase → {cpu_ms, energy_mj, comm_B, wall_ms}
    """
    out = {}
    for phase, col_prefix in prefix_map.items():
        # column names in CSV may use _Bytes or _B suffix
        tx_key = next((k for k in row if k.startswith(col_prefix + "_Tx")), None)
        rx_key = next((k for k in row if k.startswith(col_prefix + "_Rx")), None)
        out[phase] = {
            "cpu_ms":    f(row, col_prefix + "_CPU_s")    * 1000,
            "energy_mj": f(row, col_prefix + "_Energy_J") * 1000,
            "comm_B":    (f(row, tx_key) if tx_key else 0) +
                         (f(row, rx_key) if rx_key else 0),
            "wall_ms":   f(row, col_prefix + "_Wall_s")   * 1000,
        }
    return out

# Revised-Anonymity: column prefixes match phase names
ra_data  = build(ra, {"Enroll": "Enroll", "Auth": "Auth",
                       "KeyEx":  "KeyEx",  "Data": "Data"})

# LAAKA: Register → Enroll, Auth → Auth, Ack → KeyEx, Data → Data
lk_data  = build(lk, {"Enroll": "Register", "Auth": "Auth",
                       "KeyEx":  "Ack",      "Data": "Data"})

# Zhou USER: Enroll → Enroll, Auth → Auth, KeyEx → KeyEx, Data → Data
zh_data  = build(zh_u, {"Enroll": "Enroll", "Auth": "Auth",
                         "KeyEx":  "KeyEx",  "Data": "Data"})

# Zhou SN: only Enroll and Auth phases exist
zh_sn_data = build(zh_s, {"Enroll": "Enroll", "Auth": "Auth",
                            "KeyEx":  "Enroll",  "Data": "Enroll"})  # placeholder
zh_sn_data["KeyEx"] = {"cpu_ms": 0, "energy_mj": 0, "comm_B": 0, "wall_ms": 0}
zh_sn_data["Data"]  = {"cpu_ms": 0, "energy_mj": 0, "comm_B": 0, "wall_ms": 0}

# ---------------------------------------------------------------------------
# Colours and style
# ---------------------------------------------------------------------------
matplotlib.rcParams.update({
    "font.family":  "DejaVu Sans",
    "font.size":    11,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          True,
    "axes.grid.axis":     "y",
    "grid.alpha":         0.4,
    "grid.linestyle":     "--",
})

C_RA  = "#2196F3"   # blue   — Revised-Anonymity
C_LK  = "#FF9800"   # orange — LAAKA
C_ZU  = "#E53935"   # red    — Zhou USER
C_ZS  = "#F48FB1"   # pink   — Zhou SN (supplementary)

SCHEMES = ["Rev-Anon", "LAAKA", "Zhou-User", "Zhou-SN"]
COLORS  = [C_RA, C_LK, C_ZU, C_ZS]

# ---------------------------------------------------------------------------
# Helper: grouped bar chart
# ---------------------------------------------------------------------------

def grouped_bars(ax, groups, values_per_group, labels, colors,
                 ylabel, title, yformat="{:.2f}", legend_loc="upper right"):
    """
    groups: list of group names (x-axis)
    values_per_group: list-of-lists  [values_for_label0, values_for_label1, ...]
    labels: legend labels
    """
    n_groups = len(groups)
    n_bars   = len(labels)
    width    = 0.18
    x        = np.arange(n_groups)
    offsets  = np.linspace(-(n_bars-1)/2, (n_bars-1)/2, n_bars) * width

    for idx, (vals, lbl, col, off) in enumerate(zip(values_per_group, labels, colors, offsets)):
        bars = ax.bar(x + off, vals, width, label=lbl, color=col, zorder=3,
                      edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + ax.get_ylim()[1] * 0.01,
                        yformat.format(val),
                        ha="center", va="bottom", fontsize=7.5, rotation=45)

    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold", pad=10)
    ax.legend(loc=legend_loc, framealpha=0.9, fontsize=9)
    ax.set_xlim(-0.5, n_groups - 0.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: yformat.format(v)))


# ===========================================================================
# FIGURE 1 — CPU Time per phase  (ms)
# ===========================================================================
fig1, axes = plt.subplots(1, 4, figsize=(16, 5), sharey=False)
fig1.suptitle(
    "Zhou vs LAAKA vs Revised-Anonymity — CPU Time per Phase (Real RPi Hardware)",
    fontweight="bold", fontsize=13, y=1.01)

for ax, phase in zip(axes, PHASES):
    vals = [
        ra_data[phase]["cpu_ms"],
        lk_data[phase]["cpu_ms"],
        zh_data[phase]["cpu_ms"],
        zh_sn_data[phase]["cpu_ms"],
    ]
    bars = ax.bar(SCHEMES, vals, color=COLORS, zorder=3,
                  edgecolor="white", linewidth=0.5)
    for bar, v in zip(bars, vals):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.03,
                    f"{v:.3f}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold")
    ax.set_title(phase, fontweight="bold")
    ax.set_ylabel("CPU time (ms)")
    ax.tick_params(axis="x", rotation=30)
    ax.set_ylim(bottom=0)

plt.tight_layout()
fig1.savefig(OUT_DIR / "zhou_hw_cpu_per_phase.png", dpi=150, bbox_inches="tight")
plt.close(fig1)
print("Saved: zhou_hw_cpu_per_phase.png")

# ===========================================================================
# FIGURE 2 — Energy per phase  (mJ)
# ===========================================================================
fig2, axes = plt.subplots(1, 4, figsize=(16, 5), sharey=False)
fig2.suptitle(
    "Zhou vs LAAKA vs Revised-Anonymity — Energy per Phase (Real RPi Hardware)",
    fontweight="bold", fontsize=13, y=1.01)

for ax, phase in zip(axes, PHASES):
    vals = [
        ra_data[phase]["energy_mj"],
        lk_data[phase]["energy_mj"],
        zh_data[phase]["energy_mj"],
        zh_sn_data[phase]["energy_mj"],
    ]
    bars = ax.bar(SCHEMES, vals, color=COLORS, zorder=3,
                  edgecolor="white", linewidth=0.5)
    for bar, v in zip(bars, vals):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.03,
                    f"{v:.3f}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold")
    ax.set_title(phase, fontweight="bold")
    ax.set_ylabel("Energy (mJ)")
    ax.tick_params(axis="x", rotation=30)
    ax.set_ylim(bottom=0)

plt.tight_layout()
fig2.savefig(OUT_DIR / "zhou_hw_energy_per_phase.png", dpi=150, bbox_inches="tight")
plt.close(fig2)
print("Saved: zhou_hw_energy_per_phase.png")

# ===========================================================================
# FIGURE 3 — Communication Bytes per phase
# ===========================================================================
fig3, axes = plt.subplots(1, 4, figsize=(16, 5), sharey=False)
fig3.suptitle(
    "Zhou vs LAAKA vs Revised-Anonymity — Communication Overhead per Phase",
    fontweight="bold", fontsize=13, y=1.01)

for ax, phase in zip(axes, PHASES):
    vals = [
        ra_data[phase]["comm_B"],
        lk_data[phase]["comm_B"],
        zh_data[phase]["comm_B"],
        zh_sn_data[phase]["comm_B"],
    ]
    bars = ax.bar(SCHEMES, vals, color=COLORS, zorder=3,
                  edgecolor="white", linewidth=0.5)
    for bar, v in zip(bars, vals):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.03,
                    f"{int(v)}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold")
    ax.set_title(phase, fontweight="bold")
    ax.set_ylabel("Bytes (Tx + Rx)")
    ax.tick_params(axis="x", rotation=30)
    ax.set_ylim(bottom=0)

plt.tight_layout()
fig3.savefig(OUT_DIR / "zhou_hw_comm_per_phase.png", dpi=150, bbox_inches="tight")
plt.close(fig3)
print("Saved: zhou_hw_comm_per_phase.png")

# ===========================================================================
# FIGURE 4 — Wall-clock latency for Auth + KeyEx  (ms)
#            This is the real end-to-end latency a user/sensor feels
# ===========================================================================
fig4, ax = plt.subplots(figsize=(9, 5))

schemes_3  = ["Rev-Anon\n(NODE)", "LAAKA\n(NODE)", "Zhou\n(USER)", "Zhou\n(SN)"]
auth_wall  = [ra_data["Auth"]["wall_ms"],   lk_data["Auth"]["wall_ms"],
              zh_data["Auth"]["wall_ms"],   zh_sn_data["Auth"]["wall_ms"]]
keyex_wall = [ra_data["KeyEx"]["wall_ms"],  lk_data["KeyEx"]["wall_ms"],
              zh_data["KeyEx"]["wall_ms"],  zh_sn_data["KeyEx"]["wall_ms"]]

x     = np.arange(len(schemes_3))
width = 0.35

b1 = ax.bar(x - width/2, auth_wall,  width, label="Auth",  color="#42A5F5", zorder=3)
b2 = ax.bar(x + width/2, keyex_wall, width, label="KeyEx", color="#26A69A", zorder=3)

for bars in [b1, b2]:
    for bar in bars:
        v = bar.get_height()
        if v > 0:
            ax.text(bar.get_x() + bar.get_width()/2,
                    v + 0.3, f"{v:.1f}",
                    ha="center", va="bottom", fontsize=9, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(schemes_3)
ax.set_ylabel("Wall-clock latency (ms)")
ax.set_title("Auth + KeyEx Wall-Clock Latency (Real Hardware, RPi 3B+)",
             fontweight="bold", pad=10)
ax.legend(framealpha=0.9)
ax.set_ylim(bottom=0)
plt.tight_layout()
fig4.savefig(OUT_DIR / "zhou_hw_auth_latency.png", dpi=150, bbox_inches="tight")
plt.close(fig4)
print("Saved: zhou_hw_auth_latency.png")

# ===========================================================================
# FIGURE 5 — Total comparison (grouped: CPU, Energy, Comm)
# ===========================================================================
fig5, axes = plt.subplots(1, 3, figsize=(15, 5))
fig5.suptitle(
    "Total Protocol Cost — Zhou vs LAAKA vs Revised-Anonymity (Real RPi Hardware)",
    fontweight="bold", fontsize=13, y=1.01)

metrics = ["cpu_ms", "energy_mj", "comm_B"]
ylabels = ["Total CPU time (ms)", "Total Energy (mJ)", "Total Comm. Bytes (Tx+Rx)"]
yformats = ["{:.2f}", "{:.2f}", "{:.0f}"]
titles   = ["Total CPU Time", "Total Energy", "Total Communication"]

# Sum all phases for total
def total(d, key):
    return sum(d[ph][key] for ph in PHASES)

for ax, metric, ylabel, yformat, title in zip(axes, metrics, ylabels, yformats, titles):
    vals_4 = [
        total(ra_data,     metric),
        total(lk_data,     metric),
        total(zh_data,     metric),   # Zhou USER
        total(zh_sn_data,  metric),   # Zhou SN
    ]
    # Also show Zhou combined (USER + SN)
    zh_combined = total(zh_data, metric) + total(zh_sn_data, metric)

    schemes_ext = ["Rev-Anon\n(NODE)", "LAAKA\n(NODE)",
                   "Zhou\n(USER)", "Zhou\n(SN)", "Zhou\n(USER+SN)"]
    vals_ext = vals_4 + [zh_combined]
    colors_ext = [C_RA, C_LK, C_ZU, C_ZS, "#B71C1C"]

    bars = ax.bar(schemes_ext, vals_ext, color=colors_ext, zorder=3,
                  edgecolor="white", linewidth=0.5)
    for bar, v in zip(bars, vals_ext):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() * 1.03,
                    yformat.format(v), ha="center", va="bottom",
                    fontsize=8.5, fontweight="bold")
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    ax.set_ylim(bottom=0)

plt.tight_layout()
fig5.savefig(OUT_DIR / "zhou_hw_total_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig5)
print("Saved: zhou_hw_total_comparison.png")

# ===========================================================================
# FIGURE 6 — Stacked bar: Energy breakdown per phase
# ===========================================================================
fig6, axes = plt.subplots(1, 3, figsize=(14, 5))
fig6.suptitle(
    "Energy Breakdown by Phase — Real RPi Hardware",
    fontweight="bold", fontsize=13, y=1.01)

scheme_labels = ["Rev-Anon", "LAAKA", "Zhou-User", "Zhou-SN"]
colors_stacked = ["#1976D2", "#FF8F00", "#EF5350", "#8BC34A"]
phase_colors   = {"Enroll": "#42A5F5", "Auth": "#66BB6A",
                  "KeyEx": "#FFA726", "Data": "#EF5350"}

all_data = [ra_data, lk_data, zh_data, zh_sn_data]

for ax, scheme_label, data_dict, bar_color in zip(
        axes[:], scheme_labels[:3], [ra_data, lk_data, zh_data], [C_RA, C_LK, C_ZU]):
    ph_vals  = [data_dict[ph]["energy_mj"] for ph in PHASES]
    bottoms  = np.zeros(1)
    x        = np.array([0])
    for ph, pv, pc in zip(PHASES, ph_vals, [phase_colors[p] for p in PHASES]):
        ax.bar(x, [pv], bottom=bottoms, color=pc, label=ph, zorder=3,
               edgecolor="white", linewidth=0.5, width=0.5)
        if pv > 0.01:
            ax.text(0, bottoms[0] + pv/2, f"{ph}\n{pv:.3f} mJ",
                    ha="center", va="center", fontsize=8, color="white",
                    fontweight="bold")
        bottoms += pv
    total_e = sum(ph_vals)
    ax.text(0, total_e * 1.03, f"Total\n{total_e:.3f} mJ",
            ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xlim(-0.5, 0.5)
    ax.set_xticks([])
    ax.set_title(scheme_label, fontweight="bold", color=bar_color)
    ax.set_ylabel("Energy (mJ)")
    ax.set_ylim(bottom=0)
    if scheme_label == "Rev-Anon":
        ax.legend(loc="upper right", fontsize=8)

plt.tight_layout()
fig6.savefig(OUT_DIR / "zhou_hw_energy_stacked.png", dpi=150, bbox_inches="tight")
plt.close(fig6)
print("Saved: zhou_hw_energy_stacked.png")

# ===========================================================================
# SUMMARY CSV
# ===========================================================================

def pct(new, ref):
    if ref == 0:
        return "N/A"
    return f"{((new - ref) / ref * 100):+.1f}%"

summary_rows = []
for phase in PHASES + ["TOTAL"]:
    for metric, col in [("CPU (ms)", "cpu_ms"),
                        ("Energy (mJ)", "energy_mj"),
                        ("Comm (B)", "comm_B")]:
        if phase == "TOTAL":
            ra_v  = total(ra_data, col)
            lk_v  = total(lk_data, col)
            zh_v  = total(zh_data, col)
            zhs_v = total(zh_sn_data, col)
        else:
            ra_v  = ra_data[phase][col]
            lk_v  = lk_data[phase][col]
            zh_v  = zh_data[phase][col]
            zhs_v = zh_sn_data[phase][col]

        summary_rows.append({
            "Phase":           phase,
            "Metric":          metric,
            "Rev-Anon":        f"{ra_v:.4f}",
            "LAAKA":           f"{lk_v:.4f}",
            "Zhou-User":       f"{zh_v:.4f}",
            "Zhou-SN":         f"{zhs_v:.4f}",
            "Zhou-Combined":   f"{zh_v + zhs_v:.4f}",
            "Zhou-vs-RA (%)":  pct(zh_v, ra_v),
            "Zhou-vs-LK (%)":  pct(zh_v, lk_v),
        })

import csv as _csv
with open(OUT_DIR / "zhou_hw_comparison_summary.csv", "w", newline="") as f:
    w = _csv.DictWriter(f, fieldnames=summary_rows[0].keys())
    w.writeheader(); w.writerows(summary_rows)
print("Saved: zhou_hw_comparison_summary.csv")

print("\nAll 6 figures + summary CSV written to:", OUT_DIR)
