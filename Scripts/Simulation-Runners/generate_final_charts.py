"""
Generate publication-quality comparison charts for MTP thesis.
3 schemes × 3 phases, multi-seed averaged with error bars.
"""
import csv, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CHARTS = os.path.join(BASE, "Results", "Charts")
DATA = os.path.join(BASE, "Results", "CSV-Data", "multi-seed-summary.csv")

# Read data
summary = {}
with open(DATA) as f:
    for row in csv.DictReader(f):
        s, p = row["Scheme"], row["Phase"]
        if s not in summary: summary[s] = {}
        summary[s][p] = {
            "cpu": float(row["Avg_CPU_s"]),
            "std_cpu": float(row["StdDev_CPU_s"]),
            "energy": float(row["Avg_Energy_J"]),
            "std_energy": float(row["StdDev_Energy_J"]),
            "cpu_only": float(row["Avg_CPU_Only_Energy_J"]),
        }

schemes = ["Base-Scheme", "LAAKA", "Proposed-Scheme"]
labels = ["Base Scheme\n(Ding et al.)", "LAAKA\n(Gope et al.)", "Proposed\nScheme"]
phases = ["Enrollment", "Authentication", "Key Exchange"]
colors = ['#1565C0', '#E65100', '#2E7D32']  # deep blue, deep orange, deep green

plt.rcParams.update({
    'font.size': 11, 'font.family': 'serif',
    'axes.titlesize': 13, 'axes.labelsize': 12,
    'legend.fontsize': 10, 'figure.dpi': 200,
    'axes.grid': True, 'grid.alpha': 0.25,
    'axes.spines.top': False, 'axes.spines.right': False,
})

x = np.arange(len(phases))
w = 0.24

# =========================================================================
# CHART 1: Total Energy per Phase (grouped bar + error bars)
# =========================================================================
fig1, ax1 = plt.subplots(figsize=(9, 5.5))
for i, (s, lbl) in enumerate(zip(schemes, labels)):
    vals = [summary[s][p]["energy"] * 1000 for p in phases]  # mJ
    errs = [summary[s][p]["std_energy"] * 1000 for p in phases]
    bars = ax1.bar(x + i*w, vals, w, label=lbl.replace('\n',' '), color=colors[i],
                   yerr=errs, capsize=4, edgecolor='black', linewidth=0.6, alpha=0.88)
    for bar, val in zip(bars, vals):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(errs)*0.3,
                 f'{val:.1f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

ax1.set_xlabel('Protocol Phase')
ax1.set_ylabel('Average Energy Consumption (mJ)')
ax1.set_title('Energy Consumption Comparison — All Phases\n(5-seed average, 20 devices per seed, ±1σ)')
ax1.set_xticks(x + w)
ax1.set_xticklabels(phases)
ax1.legend(loc='upper left')
ax1.set_ylim(0, ax1.get_ylim()[1] * 1.15)
fig1.tight_layout()
fig1.savefig(os.path.join(CHARTS, "Final-01-Energy-Comparison.png"))
print("Saved: Final-01-Energy-Comparison.png")

# =========================================================================
# CHART 2: CPU Time per Phase (grouped bar + error bars)
# =========================================================================
fig2, ax2 = plt.subplots(figsize=(9, 5.5))
for i, (s, lbl) in enumerate(zip(schemes, labels)):
    vals = [summary[s][p]["cpu"] * 1000 for p in phases]  # ms
    errs = [summary[s][p]["std_cpu"] * 1000 for p in phases]
    bars = ax2.bar(x + i*w, vals, w, label=lbl.replace('\n',' '), color=colors[i],
                   yerr=errs, capsize=4, edgecolor='black', linewidth=0.6, alpha=0.88)
    for bar, val in zip(bars, vals):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(errs)*0.3,
                 f'{val:.0f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

ax2.set_xlabel('Protocol Phase')
ax2.set_ylabel('Average CPU Time (ms)')
ax2.set_title('CPU Time Comparison — All Phases\n(5-seed average, 20 devices per seed, ±1σ)')
ax2.set_xticks(x + w)
ax2.set_xticklabels(phases)
ax2.legend(loc='upper left')
ax2.set_ylim(0, ax2.get_ylim()[1] * 1.15)
fig2.tight_layout()
fig2.savefig(os.path.join(CHARTS, "Final-02-CPU-Time-Comparison.png"))
print("Saved: Final-02-CPU-Time-Comparison.png")

# =========================================================================
# CHART 3: Total Protocol Cost (all phases stacked per scheme)
# =========================================================================
fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(12, 5.5))
phase_colors = ['#42A5F5', '#FFA726', '#66BB6A']

for ax, metric, unit, mult, fmt in [
    (ax3a, "energy", "Energy (mJ)", 1000, '{:.1f}'),
    (ax3b, "cpu", "CPU Time (ms)", 1000, '{:.0f}')
]:
    bottom = np.zeros(len(schemes))
    totals = np.zeros(len(schemes))
    for j, phase in enumerate(phases):
        vals = np.array([summary[s][phase][metric] * mult for s in schemes])
        ax.bar(labels, vals, bottom=bottom, label=phase,
               color=phase_colors[j], edgecolor='black', linewidth=0.5, alpha=0.85)
        # Label each segment
        for k, (v, b) in enumerate(zip(vals, bottom)):
            if v > 2:
                ax.text(k, b + v/2, fmt.format(v), ha='center', va='center', fontsize=8)
        bottom += vals
        totals += vals
    # Total label on top
    for k, t in enumerate(totals):
        ax.text(k, t + t*0.02, f'Total: {fmt.format(t)}', ha='center', va='bottom',
                fontsize=9, fontweight='bold')
    ax.set_ylabel(f'Total {unit}')
    ax.set_title(f'Total {unit} (All Phases)')
    ax.legend(loc='upper left', fontsize=9)
    ax.set_ylim(0, max(totals) * 1.18)

fig3.suptitle('Total Protocol Cost — Stacked by Phase', fontsize=14, fontweight='bold', y=1.01)
fig3.tight_layout()
fig3.savefig(os.path.join(CHARTS, "Final-03-Total-Protocol-Cost.png"), bbox_inches='tight')
print("Saved: Final-03-Total-Protocol-Cost.png")

# =========================================================================
# CHART 4: Computation-Only Energy (isolates crypto cost from radio)
# =========================================================================
fig4, ax4 = plt.subplots(figsize=(9, 5.5))
for i, (s, lbl) in enumerate(zip(schemes, labels)):
    vals = [summary[s][p]["cpu_only"] * 1000 for p in phases]  # mJ
    bars = ax4.bar(x + i*w, vals, w, label=lbl.replace('\n',' '), color=colors[i],
                   edgecolor='black', linewidth=0.6, alpha=0.88)
    for bar, val in zip(bars, vals):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.03,
                 f'{val:.2f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

ax4.set_xlabel('Protocol Phase')
ax4.set_ylabel('Computation-Only Energy (mJ)')
ax4.set_title('Computation-Only Energy (CPU × 1.8mA × 3V)\n(Excludes radio TX/RX/LPM overhead)')
ax4.set_xticks(x + w)
ax4.set_xticklabels(phases)
ax4.legend(loc='upper left')
ax4.set_ylim(0, ax4.get_ylim()[1] * 1.2)
fig4.tight_layout()
fig4.savefig(os.path.join(CHARTS, "Final-04-Computation-Only-Energy.png"))
print("Saved: Final-04-Computation-Only-Energy.png")

# =========================================================================
# CHART 5: Percentage improvement table as a figure
# =========================================================================
fig5, ax5 = plt.subplots(figsize=(10, 4))
ax5.axis('off')

# Build table data
col_headers = ['Phase', 'Base Scheme\nEnergy (mJ)', 'LAAKA\nEnergy (mJ)',
               'Proposed\nEnergy (mJ)', 'vs Base\n(%)', 'vs LAAKA\n(%)']
table_data = []
for p in phases:
    base_e = summary["Base-Scheme"][p]["energy"] * 1000
    laaka_e = summary["LAAKA"][p]["energy"] * 1000
    prop_e = summary["Proposed-Scheme"][p]["energy"] * 1000
    vs_base = ((prop_e - base_e) / base_e) * 100
    vs_laaka = ((prop_e - laaka_e) / laaka_e) * 100
    table_data.append([
        p,
        f'{base_e:.2f}',
        f'{laaka_e:.2f}',
        f'{prop_e:.2f}',
        f'{vs_base:+.1f}%',
        f'{vs_laaka:+.1f}%',
    ])

# Totals
base_t = sum(summary["Base-Scheme"][p]["energy"] for p in phases) * 1000
laaka_t = sum(summary["LAAKA"][p]["energy"] for p in phases) * 1000
prop_t = sum(summary["Proposed-Scheme"][p]["energy"] for p in phases) * 1000
table_data.append([
    'TOTAL',
    f'{base_t:.2f}',
    f'{laaka_t:.2f}',
    f'{prop_t:.2f}',
    f'{((prop_t - base_t)/base_t)*100:+.1f}%',
    f'{((prop_t - laaka_t)/laaka_t)*100:+.1f}%',
])

table = ax5.table(cellText=table_data, colLabels=col_headers,
                  loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.0, 1.8)

# Style header
for j in range(len(col_headers)):
    cell = table[0, j]
    cell.set_facecolor('#1A3C6E')
    cell.set_text_props(color='white', fontweight='bold')

# Style total row
for j in range(len(col_headers)):
    cell = table[len(table_data), j]
    cell.set_facecolor('#E3F2FD')
    cell.set_text_props(fontweight='bold')

# Highlight proposed column
for i in range(1, len(table_data) + 1):
    table[i, 3].set_facecolor('#E8F5E9')

ax5.set_title('Energy Consumption Summary — Proposed Scheme vs Existing Schemes\n'
              '(5-seed average, 20 IoT devices, COOJA/Contiki-NG simulation)',
              fontsize=12, fontweight='bold', pad=20)
fig5.tight_layout()
fig5.savefig(os.path.join(CHARTS, "Final-05-Comparison-Table.png"), bbox_inches='tight')
print("Saved: Final-05-Comparison-Table.png")

# =========================================================================
# Print summary for email
# =========================================================================
print(f"\n{'='*70}")
print("SUMMARY FOR EMAIL")
print(f"{'='*70}")
print(f"Base Scheme total:     {base_t:.2f} mJ  ({base_t/1000:.4f} J)")
print(f"LAAKA total:           {laaka_t:.2f} mJ  ({laaka_t/1000:.4f} J)")
print(f"Proposed Scheme total: {prop_t:.2f} mJ  ({prop_t/1000:.4f} J)")
print(f"Proposed vs Base:      {((prop_t-base_t)/base_t)*100:+.1f}%")
print(f"Proposed vs LAAKA:     {((prop_t-laaka_t)/laaka_t)*100:+.1f}%")
print(f"\nAll 5 charts saved to: {CHARTS}")
