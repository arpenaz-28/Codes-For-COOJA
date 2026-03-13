"""
Generate comprehensive comparison charts from multi-seed results.
Charts: grouped bars, stacked bars, CPU-only comparison, error bars.
"""
import csv, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE = r"c:\ANUP\MTP\Proposing\Codes For COOJA"

# Read summary data
summary = {}  # summary[scheme][phase] = {cpu, std_cpu, energy, std_energy, cpu_only}
with open(os.path.join(BASE, "multi-seed-summary.csv")) as f:
    reader = csv.DictReader(f)
    for row in reader:
        scheme = row["Scheme"]
        phase = row["Phase"]
        if scheme not in summary:
            summary[scheme] = {}
        summary[scheme][phase] = {
            "cpu": float(row["Avg_CPU_s"]),
            "std_cpu": float(row["StdDev_CPU_s"]),
            "energy": float(row["Avg_Energy_J"]),
            "std_energy": float(row["StdDev_Energy_J"]),
            "cpu_only": float(row["Avg_CPU_Only_Energy_J"]),
        }

schemes = ["Base-Scheme", "LAAKA", "Proposed-Scheme"]
scheme_labels = ["Base Scheme", "LAAKA", "Proposed Scheme"]
phases = ["Enrollment", "Authentication", "Key Exchange"]
colors = ['#2196F3', '#FF9800', '#4CAF50']

# =========================================================================
# Chart 1: Total Energy with Error Bars (grouped bar)
# =========================================================================
fig, axes = plt.subplots(1, 2, figsize=(15, 6))

x = np.arange(len(phases))
width = 0.25

for i, (scheme, label) in enumerate(zip(schemes, scheme_labels)):
    vals = [summary[scheme][p]["energy"] for p in phases]
    errs = [summary[scheme][p]["std_energy"] for p in phases]
    axes[0].bar(x + i*width, vals, width, label=label, color=colors[i],
                yerr=errs, capsize=3, edgecolor='black', linewidth=0.5)

axes[0].set_xlabel('Phase', fontsize=12)
axes[0].set_ylabel('Average Energy (J)', fontsize=12)
axes[0].set_title('Total Energy Consumption (5-seed avg ± σ)', fontsize=13)
axes[0].set_xticks(x + width)
axes[0].set_xticklabels(phases)
axes[0].legend(fontsize=10)
axes[0].grid(axis='y', alpha=0.3)

# CPU Time with Error Bars
for i, (scheme, label) in enumerate(zip(schemes, scheme_labels)):
    vals = [summary[scheme][p]["cpu"] for p in phases]
    errs = [summary[scheme][p]["std_cpu"] for p in phases]
    axes[1].bar(x + i*width, vals, width, label=label, color=colors[i],
                yerr=errs, capsize=3, edgecolor='black', linewidth=0.5)

axes[1].set_xlabel('Phase', fontsize=12)
axes[1].set_ylabel('Average CPU Time (s)', fontsize=12)
axes[1].set_title('CPU Time (5-seed avg ± σ)', fontsize=13)
axes[1].set_xticks(x + width)
axes[1].set_xticklabels(phases)
axes[1].legend(fontsize=10)
axes[1].grid(axis='y', alpha=0.3)

plt.tight_layout()
fig.savefig(os.path.join(BASE, "chart1-energy-cpu-errorbars.png"), dpi=150)
print("Saved: chart1-energy-cpu-errorbars.png")

# =========================================================================
# Chart 2: CPU-Only Energy (computation cost, no radio)
# =========================================================================
fig2, ax2 = plt.subplots(figsize=(10, 6))

for i, (scheme, label) in enumerate(zip(schemes, scheme_labels)):
    vals = [summary[scheme][p]["cpu_only"] * 1000 for p in phases]  # convert to mJ
    ax2.bar(x + i*width, vals, width, label=label, color=colors[i],
            edgecolor='black', linewidth=0.5)

ax2.set_xlabel('Phase', fontsize=12)
ax2.set_ylabel('CPU-Only Energy (mJ)', fontsize=12)
ax2.set_title('Computation-Only Energy (CPU × 1.8mA × 3V, excludes radio)', fontsize=13)
ax2.set_xticks(x + width)
ax2.set_xticklabels(phases)
ax2.legend(fontsize=10)
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
fig2.savefig(os.path.join(BASE, "chart2-cpu-only-energy.png"), dpi=150)
print("Saved: chart2-cpu-only-energy.png")

# =========================================================================
# Chart 3: Stacked Total (all phases combined per scheme)
# =========================================================================
fig3, axes3 = plt.subplots(1, 2, figsize=(14, 5))

for ax, metric, unit in [(axes3[0], "energy", "Energy (J)"),
                          (axes3[1], "cpu", "CPU Time (s)")]:
    bottom = np.zeros(len(schemes))
    for phase in phases:
        vals = [summary[s][phase][metric] for s in schemes]
        ax.bar(scheme_labels, vals, bottom=bottom, label=phase,
               edgecolor='black', linewidth=0.5)
        bottom += np.array(vals)
    ax.set_ylabel(f'Total {unit}', fontsize=12)
    ax.set_title(f'Total {unit} (All Phases Stacked)', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
fig3.savefig(os.path.join(BASE, "chart3-stacked-total.png"), dpi=150)
print("Saved: chart3-stacked-total.png")

# =========================================================================
# Chart 4: Radio vs Computation breakdown
# =========================================================================
fig4, ax4 = plt.subplots(figsize=(12, 6))

x2 = np.arange(len(schemes))
width2 = 0.12
positions = []

for phase_idx, phase in enumerate(phases):
    for scheme_idx, (scheme, label) in enumerate(zip(schemes, scheme_labels)):
        total_e = summary[scheme][phase]["energy"]
        cpu_e = summary[scheme][phase]["cpu_only"]
        radio_e = total_e - cpu_e
        pos = phase_idx * (len(schemes) + 1) * width2 + scheme_idx * width2
        positions.append(pos)
        ax4.bar(pos, cpu_e * 1000, width2, color=colors[scheme_idx], edgecolor='black', linewidth=0.5)
        ax4.bar(pos, radio_e * 1000, width2, bottom=cpu_e * 1000, 
                color=colors[scheme_idx], alpha=0.4, edgecolor='black', linewidth=0.5)

# Custom legend
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=colors[i], label=scheme_labels[i]) for i in range(3)]
legend_elements.append(Patch(facecolor='gray', alpha=1.0, label='Computation'))
legend_elements.append(Patch(facecolor='gray', alpha=0.4, label='Radio (TX/RX/LPM)'))
ax4.legend(handles=legend_elements, fontsize=9)

# Phase labels
phase_centers = []
for phase_idx in range(len(phases)):
    center = phase_idx * (len(schemes) + 1) * width2 + width2
    phase_centers.append(center)
ax4.set_xticks(phase_centers)
ax4.set_xticklabels(phases)
ax4.set_ylabel('Energy (mJ)', fontsize=12)
ax4.set_title('Energy Breakdown: Computation vs Radio', fontsize=13)
ax4.grid(axis='y', alpha=0.3)

plt.tight_layout()
fig4.savefig(os.path.join(BASE, "chart4-radio-vs-computation.png"), dpi=150)
print("Saved: chart4-radio-vs-computation.png")

# =========================================================================
# Print comprehensive summary table
# =========================================================================
print("\n" + "=" * 110)
print("COMPREHENSIVE COMPARISON — 5-SEED AVERAGE (seeds: 123456, 234567, 345678, 456789, 567890)")
print("=" * 110)
print(f"{'Scheme':<20s} {'Phase':<16s} {'CPU (s)':>12s} {'±σ':>8s} {'Energy (J)':>12s} {'±σ':>8s} {'CPU-only (mJ)':>14s} {'Radio (mJ)':>12s}")
print("-" * 110)
for scheme, label in zip(schemes, scheme_labels):
    total_cpu = 0
    total_en = 0
    total_cpu_only = 0
    for phase in phases:
        d = summary[scheme][phase]
        radio = (d["energy"] - d["cpu_only"]) * 1000
        print(f"{label:<20s} {phase:<16s} {d['cpu']:>12.4f} {d['std_cpu']:>8.4f} "
              f"{d['energy']:>12.4f} {d['std_energy']:>8.4f} {d['cpu_only']*1000:>14.4f} {radio:>12.4f}")
        total_cpu += d['cpu']
        total_en += d['energy']
        total_cpu_only += d['cpu_only']
    total_radio = (total_en - total_cpu_only) * 1000
    print(f"{label:<20s} {'** TOTAL **':<16s} {total_cpu:>12.4f} {'':>8s} "
          f"{total_en:>12.4f} {'':>8s} {total_cpu_only*1000:>14.4f} {total_radio:>12.4f}")
    print("-" * 110)

# =========================================================================
# Same-seed comparison table  
# =========================================================================
detail = {}
with open(os.path.join(BASE, "multi-seed-results.csv")) as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (row["Scheme"], int(row["Seed"]), row["Phase"])
        detail[key] = {
            "cpu": float(row["Avg_CPU_s"]),
            "energy": float(row["Avg_Energy_J"]),
            "cpu_only": float(row["Avg_CPU_Only_Energy_J"]),
        }

print("\n" + "=" * 90)
print("SAME-SEED COMPARISON (seed=123456) — Fair Network Conditions")
print("=" * 90)
print(f"{'Scheme':<20s} {'Phase':<16s} {'CPU (s)':>10s} {'Energy (J)':>12s} {'CPU-only (mJ)':>14s}")
print("-" * 90)
for scheme, label in zip(schemes, scheme_labels):
    for phase in phases:
        key = (scheme, 123456, phase)
        if key in detail:
            d = detail[key]
            print(f"{label:<20s} {phase:<16s} {d['cpu']:>10.4f} {d['energy']:>12.4f} {d['cpu_only']*1000:>14.4f}")
    print("-" * 90)

# Update the all-schemes-comparison.csv with multi-seed averages
out_csv = os.path.join(BASE, "all-schemes-comparison.csv")
with open(out_csv, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Scheme", "Phase", "Avg_CPU_s", "StdDev_CPU_s", 
                "Avg_Energy_J", "StdDev_Energy_J", "CPU_Only_Energy_J",
                "Num_Seeds", "Method"])
    for scheme, label in zip(schemes, scheme_labels):
        for phase in phases:
            d = summary[scheme][phase]
            w.writerow([label, phase, 
                       f"{d['cpu']:.6f}", f"{d['std_cpu']:.6f}",
                       f"{d['energy']:.6f}", f"{d['std_energy']:.6f}",
                       f"{d['cpu_only']:.8f}",
                       5, "5-seed average"])
print(f"\nUpdated: {out_csv}")
print("All charts and CSVs generated successfully!")
