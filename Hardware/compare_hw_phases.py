"""
Per-phase hardware comparison: Revised-Anonymity vs LAAKA
Metrics: wall time, CPU time, communication bytes, energy (network + CPU)
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "comparison")
os.makedirs(OUT, exist_ok=True)

# ── Revised-Anonymity hardware (from hw_metrics_clean.csv, device 81) ─────────
RA = {
    # phase: (wall_s, cpu_s, bytes, energy_J)
    "Enrollment":   (0.133361, 0.002674, 327,  0.007339),
    "Auth+KeyEx":   (0.007073, 0.000587, 392,  0.002252),
    "Data/packet":  (3.000776, 0.000687, 124,  0.001965),
    "Total":        (30.148192, 0.010127, 1959, 0.029235),
}

# ── LAAKA hardware (from hw_metrics_clean.csv, device 81) ─────────────────────
# CPU time = 0 (not captured in local sim; energy = network only)
LK_raw = {
    # phase: (wall_s, cpu_s, tx_bytes, rx_bytes)
    "Register":  (0.003007, 0.0,  91,  187),
    "Auth":      (0.001133, 0.0, 194,  196),
    "Ack":       (0.000049, 0.0, 107,    0),
    "Data/pkt":  (1.000767, 0.0, 100,    0),   # per-packet (10 total)
}
NET_J = 2e-6   # J per byte (same model as RA)

def lk_energy(tx, rx): return (tx + rx) * NET_J

LK = {
    "Registration": (LK_raw["Register"][0],
                     LK_raw["Register"][1],
                     LK_raw["Register"][2] + LK_raw["Register"][3],
                     lk_energy(LK_raw["Register"][2], LK_raw["Register"][3])),
    "Auth+Ack":     (LK_raw["Auth"][0] + LK_raw["Ack"][0],
                     0.0,
                     sum(LK_raw["Auth"][2:4]) + LK_raw["Ack"][2],
                     lk_energy(LK_raw["Auth"][2] + LK_raw["Ack"][2],
                                LK_raw["Auth"][3] + LK_raw["Ack"][3])),
    "Data/packet":  (LK_raw["Data/pkt"][0],
                     0.0,
                     LK_raw["Data/pkt"][2] + LK_raw["Data/pkt"][3],
                     lk_energy(LK_raw["Data/pkt"][2], LK_raw["Data/pkt"][3])),
    "Total":        (10.011855, 0.0, 1775, 0.00355),
}

# ── Shared phases for side-by-side comparison ──────────────────────────────────
phases    = ["Enrollment/\nRegistration", "Auth\n(Auth+KeyEx\nvs Auth+Ack)", "Data\n(per packet)"]
ra_wall   = [RA["Enrollment"][0],   RA["Auth+KeyEx"][0],  RA["Data/packet"][0]]
lk_wall   = [LK["Registration"][0], LK["Auth+Ack"][0],    LK["Data/packet"][0]]
ra_cpu    = [RA["Enrollment"][1],   RA["Auth+KeyEx"][1],  RA["Data/packet"][1]]
lk_cpu    = [LK["Registration"][1], LK["Auth+Ack"][1],    LK["Data/packet"][1]]
ra_bytes  = [RA["Enrollment"][2],   RA["Auth+KeyEx"][2],  RA["Data/packet"][2]]
lk_bytes  = [LK["Registration"][2], LK["Auth+Ack"][2],    LK["Data/packet"][2]]
ra_energy = [RA["Enrollment"][3],   RA["Auth+KeyEx"][3],  RA["Data/packet"][3]]
lk_energy_list = [LK["Registration"][3], LK["Auth+Ack"][3], LK["Data/packet"][3]]

# ── RA energy split: CPU vs network ───────────────────────────────────────────
ra_net_e  = [b * NET_J for b in ra_bytes]
ra_cpu_e  = [e - n for e, n in zip(ra_energy, ra_net_e)]

# ── Helpers ────────────────────────────────────────────────────────────────────
CLR_RA  = "#2196F3"   # blue  – Revised-Anonymity
CLR_LK  = "#FF9800"   # orange – LAAKA
CLR_RA2 = "#90CAF9"   # light blue (CPU component)
CLR_LK2 = "#FFE0B2"   # light orange

def annotate_ratio(ax, x1, x2, h1, h2, ratio_label, offset_frac=0.08):
    """Draw a small ratio label between two bars."""
    ymax = max(h1, h2)
    dy   = ymax * offset_frac
    ax.annotate(ratio_label, xy=((x1 + x2) / 2, ymax + dy),
                ha="center", va="bottom", fontsize=8, color="#555555",
                fontweight="bold")

def ratio_str(a, b):
    if b == 0: return "—"
    r = a / b
    winner = "RA" if r > 1 else "LK"
    return f"{max(r,1/r):.2f}x ({winner})"

def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {name}")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 1 – Wall Clock Time per Phase
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(phases))
w = 0.35
b1 = ax.bar(x - w/2, ra_wall, w, label="Revised-Anonymity", color=CLR_RA)
b2 = ax.bar(x + w/2, lk_wall, w, label="LAAKA",             color=CLR_LK)
ax.set_yscale("log")
ax.set_ylabel("Wall Clock Time (s)  [log scale]")
ax.set_title("Hardware — Wall Clock Time per Phase\n(Revised-Anonymity vs LAAKA)")
ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=9)
ax.legend()
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
# ratio labels
for i in range(len(phases)):
    h1, h2 = ra_wall[i], lk_wall[i]
    if h1 > 0 and h2 > 0:
        r = h1/h2
        lbl = f"RA {r:.1f}x slower" if r > 1 else f"LK {1/r:.1f}x slower"
        ax.text(x[i], max(h1, h2) * 1.5, lbl, ha="center", fontsize=7.5, color="#333")
fig.tight_layout()
save(fig, "hw_wall_time.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 2 – CPU Computation Time per Phase  (RA only; LAAKA = 0 — note shown)
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 4.5))
b1 = ax.bar(x - w/2, [t*1000 for t in ra_cpu], w, label="Revised-Anonymity", color=CLR_RA)
b2 = ax.bar(x + w/2, [t*1000 for t in lk_cpu], w, label="LAAKA (local sim — CPU=0 not captured)",
            color=CLR_LK, alpha=0.45, hatch="//")
ax.set_ylabel("CPU Computation Time (ms)")
ax.set_title("Hardware — CPU Computation Time per Phase\n"
             "(LAAKA CPU=0: process_time() resolution limit in local sim)")
ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=9)
ax.legend(fontsize=8)
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
for bar in b1:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.01, f"{h:.3f}ms",
            ha="center", va="bottom", fontsize=7.5)
ax.text(0.5, 0.92,
        "Note: LAAKA CPU time not captured — real RPi deployment would show non-zero values",
        transform=ax.transAxes, ha="center", fontsize=7.5,
        color="red", style="italic",
        bbox=dict(boxstyle="round,pad=0.3", fc="#FFF9C4", ec="orange", alpha=0.8))
fig.tight_layout()
save(fig, "hw_cpu_time.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 3 – Communication Bytes per Phase
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
b1 = ax.bar(x - w/2, ra_bytes, w, label="Revised-Anonymity", color=CLR_RA)
b2 = ax.bar(x + w/2, lk_bytes, w, label="LAAKA",             color=CLR_LK)
ax.set_ylabel("Total Bytes (Tx + Rx)")
ax.set_title("Hardware — Communication Overhead per Phase\n(Revised-Anonymity vs LAAKA)")
ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=9)
ax.legend()
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
for bar, val in zip(list(b1)+list(b2),
                    list(ra_bytes)+list(lk_bytes)):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 4, str(val),
            ha="center", va="bottom", fontsize=8)
for i in range(len(phases)):
    h1, h2 = ra_bytes[i], lk_bytes[i]
    r = h1/h2
    lbl = f"RA {r:.2f}x" if r > 1 else f"LK {1/r:.2f}x"
    ax.text(x[i], max(h1, h2) * 1.06, lbl, ha="center", fontsize=8, color="#333",
            fontweight="bold")
fig.tight_layout()
save(fig, "hw_bytes.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 4 – Energy per Phase  (stacked: CPU energy + Network energy)
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
# RA stacked bars
ax.bar(x - w/2, [e*1000 for e in ra_net_e], w,
       label="RA — Network energy", color=CLR_RA)
ax.bar(x - w/2, [e*1000 for e in ra_cpu_e], w,
       bottom=[e*1000 for e in ra_net_e],
       label="RA — CPU energy", color=CLR_RA2)
# LAAKA bars (network only)
ax.bar(x + w/2, [e*1000 for e in lk_energy_list], w,
       label="LAAKA — Network energy only (CPU not captured)", color=CLR_LK)

ax.set_ylabel("Energy (mJ)")
ax.set_title("Hardware — Energy per Phase\n"
             "(RA = CPU + Network;  LAAKA = Network only — CPU not captured)")
ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=9)
ax.legend(fontsize=8, loc="upper right")
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
# value labels
for i in range(len(phases)):
    ax.text(x[i] - w/2, ra_energy[i]*1000 + 0.05,
            f"{ra_energy[i]*1000:.3f}", ha="center", va="bottom", fontsize=7.5)
    ax.text(x[i] + w/2, lk_energy_list[i]*1000 + 0.05,
            f"{lk_energy_list[i]*1000:.3f}", ha="center", va="bottom", fontsize=7.5)
ax.text(0.5, 0.92,
        "Fair comparison requires LAAKA CPU time from real RPi; network energy is comparable",
        transform=ax.transAxes, ha="center", fontsize=7.5,
        color="red", style="italic",
        bbox=dict(boxstyle="round,pad=0.3", fc="#FFF9C4", ec="orange", alpha=0.8))
fig.tight_layout()
save(fig, "hw_energy.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 5 – Network Energy only (fair for both)
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
ra_net_mj = [e*1000 for e in ra_net_e]
lk_net_mj = [e*1000 for e in lk_energy_list]
b1 = ax.bar(x - w/2, ra_net_mj, w, label="Revised-Anonymity", color=CLR_RA)
b2 = ax.bar(x + w/2, lk_net_mj, w, label="LAAKA",             color=CLR_LK)
ax.set_ylabel("Network Energy (mJ)")
ax.set_title("Hardware — Network Energy per Phase (Fair Comparison)\n"
             "Energy = Total Bytes × 2×10⁻⁶ J/byte")
ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=9)
ax.legend()
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
for bar, val in zip(list(b1)+list(b2),
                    list(ra_net_mj)+list(lk_net_mj)):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
            f"{val:.3f}", ha="center", va="bottom", fontsize=7.5)
for i in range(len(phases)):
    h1, h2 = ra_net_mj[i], lk_net_mj[i]
    r = h1/h2
    winner = "LK" if r > 1 else "RA"
    lbl = f"{max(r,1/r):.2f}x ({winner} wins)"
    ax.text(x[i], max(h1, h2) * 1.07, lbl, ha="center", fontsize=8,
            color="#1B5E20" if winner == "RA" else "#E65100", fontweight="bold")
fig.tight_layout()
save(fig, "hw_net_energy.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 6 – 2×2 combined panel
# ══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Hardware Per-Phase Comparison: Revised-Anonymity vs LAAKA", fontsize=13, y=1.01)

def mini_bar(ax, ra_vals, lk_vals, ylabel, title, ylog=False, fmt=".3f"):
    b1 = ax.bar(x - w/2, ra_vals, w, label="Revised-Anonymity", color=CLR_RA)
    b2 = ax.bar(x + w/2, lk_vals, w, label="LAAKA",             color=CLR_LK)
    if ylog: ax.set_yscale("log")
    ax.set_ylabel(ylabel, fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(phases, fontsize=7.5)
    ax.legend(fontsize=7)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    for bar, v in zip(list(b1)+list(b2), list(ra_vals)+list(lk_vals)):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()*1.03,
                format(v, fmt), ha="center", va="bottom", fontsize=6.5)

mini_bar(axes[0,0], ra_wall,  lk_wall,
         "Wall Time (s) [log]", "Wall Clock Time", ylog=True, fmt=".4f")
mini_bar(axes[0,1], [t*1000 for t in ra_cpu], [t*1000 for t in lk_cpu],
         "CPU Time (ms)", "CPU Computation Time\n(LAAKA = 0 not captured)", fmt=".3f")
mini_bar(axes[1,0], ra_bytes, lk_bytes,
         "Bytes (Tx+Rx)", "Communication Overhead", fmt=".0f")
mini_bar(axes[1,1], [e*1000 for e in ra_net_e], lk_net_mj,
         "Network Energy (mJ)", "Network Energy (Fair)", fmt=".3f")

fig.tight_layout()
save(fig, "hw_combined_panel.png")

# ══════════════════════════════════════════════════════════════════════════════
# CSV summary table
# ══════════════════════════════════════════════════════════════════════════════
import csv
rows = []
labels = ["Enrollment/Registration", "Auth (Auth+KeyEx vs Auth+Ack)", "Data (per packet)"]
for i, ph in enumerate(labels):
    rows.append({
        "Phase":           ph,
        "RA_Wall_s":       f"{ra_wall[i]:.6f}",
        "LK_Wall_s":       f"{lk_wall[i]:.6f}",
        "Wall_Winner":     "LAAKA" if lk_wall[i] < ra_wall[i] else "Rev-Anon",
        "Wall_Factor":     f"{max(ra_wall[i], lk_wall[i]) / min(ra_wall[i], lk_wall[i]):.2f}x",
        "RA_CPU_ms":       f"{ra_cpu[i]*1000:.3f}",
        "LK_CPU_ms":       "0 (not captured)",
        "RA_Bytes":        ra_bytes[i],
        "LK_Bytes":        lk_bytes[i],
        "Bytes_Winner":    "LAAKA" if lk_bytes[i] < ra_bytes[i] else "Rev-Anon",
        "Bytes_Factor":    f"{max(ra_bytes[i], lk_bytes[i]) / min(ra_bytes[i], lk_bytes[i]):.2f}x",
        "RA_NetEnergy_mJ": f"{ra_net_e[i]*1000:.4f}",
        "LK_NetEnergy_mJ": f"{lk_energy_list[i]*1000:.4f}",
        "NetEnergy_Winner":"LAAKA" if lk_energy_list[i] < ra_net_e[i] else "Rev-Anon",
        "NetEnergy_Factor":f"{max(ra_net_e[i], lk_energy_list[i]) / min(ra_net_e[i], lk_energy_list[i]):.2f}x",
        "RA_TotalEnergy_mJ": f"{ra_energy[i]*1000:.4f}",
        "LK_TotalEnergy_mJ": f"{lk_energy_list[i]*1000:.4f} (net only)",
    })

csv_path = os.path.join(OUT, "hw_phase_comparison.csv")
with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
print("  Saved hw_phase_comparison.csv")

# ══════════════════════════════════════════════════════════════════════════════
# Console summary
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 80)
print("HARDWARE Per-Phase Summary: Revised-Anonymity vs LAAKA")
print("=" * 80)
hdr = f"{'Phase':<30} {'RA Wall':>10} {'LK Wall':>10} {'Winner':>10} {'Factor':>8}"
print(hdr)
print("-" * 72)
for i, ph in enumerate(labels):
    h1, h2 = ra_wall[i], lk_wall[i]
    w_win = "LAAKA" if h2 < h1 else "Rev-Anon"
    fac = max(h1,h2)/min(h1,h2)
    print(f"  {ph:<28} {h1:>10.4f}s {h2:>9.4f}s {w_win:>10}  {fac:.2f}x")

print()
hdr = f"{'Phase':<30} {'RA Bytes':>10} {'LK Bytes':>10} {'Winner':>10} {'Factor':>8}"
print(hdr)
print("-" * 72)
for i, ph in enumerate(labels):
    h1, h2 = ra_bytes[i], lk_bytes[i]
    b_win = "LAAKA" if h2 < h1 else "Rev-Anon"
    fac = max(h1,h2)/min(h1,h2)
    print(f"  {ph:<28} {h1:>10}B  {h2:>9}B  {b_win:>10}  {fac:.2f}x")

print()
hdr = f"{'Phase':<30} {'RA NetE':>12} {'LK NetE':>12} {'Winner':>10} {'Factor':>8}"
print(hdr)
print("-" * 72)
for i, ph in enumerate(labels):
    h1, h2 = ra_net_e[i]*1000, lk_energy_list[i]*1000
    e_win = "LAAKA" if h2 < h1 else "Rev-Anon"
    fac = max(h1,h2)/min(h1,h2)
    print(f"  {ph:<28} {h1:>10.4f}mJ {h2:>10.4f}mJ {e_win:>10}  {fac:.2f}x")

print()
print("NOTE: LAAKA CPU time = 0 (process_time() resolution limit in local sim).")
print("      RA total energy includes CPU component; LAAKA shows network energy only.")
print(f"\nAll files saved to: {OUT}/")
