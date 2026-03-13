"""Compare all 3 schemes across 3 phases: Enrollment, Authentication, Key Exchange.
Generates comparison CSV and bar charts.
"""
import csv, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE = r"c:\ANUP\MTP\Proposing\Codes For COOJA"

schemes = {
    "Base Scheme":     os.path.join(BASE, "Base-Scheme"),
    "LAAKA":           os.path.join(BASE, "LAAKA"),
    "Proposed Scheme": os.path.join(BASE, "Anonymity-Extended-Base-Scheme"),
}

phases = ["enroll", "auth", "keyex"]
phase_labels = {"enroll": "Enrollment", "auth": "Authentication", "keyex": "Key Exchange"}

# Read averages
data = {}  # data[scheme][phase] = {"cpu": avg, "energy": avg, "count": n}
for scheme, path in schemes.items():
    data[scheme] = {}
    for phase in phases:
        csv_path = os.path.join(path, f"{phase}-results.csv")
        if not os.path.exists(csv_path):
            print(f"WARNING: {csv_path} not found")
            data[scheme][phase] = {"cpu": 0, "energy": 0, "count": 0}
            continue
        rows = []
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        n = len(rows)
        # Handle different column names across schemes
        cpu_key = "CPU_Time_s" if "CPU_Time_s" in rows[0] else "CPU_s" if n else "CPU_Time_s"
        avg_cpu = sum(float(r[cpu_key]) for r in rows) / n if n else 0
        avg_energy = sum(float(r["Energy_J"]) for r in rows) / n if n else 0
        data[scheme][phase] = {"cpu": avg_cpu, "energy": avg_energy, "count": n}
        print(f"{scheme} | {phase_labels[phase]:15s} | n={n:3d} | CPU={avg_cpu:.4f}s | Energy={avg_energy:.4f}J")

# Write comparison CSV
out_csv = os.path.join(BASE, "all-schemes-comparison.csv")
with open(out_csv, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Scheme", "Phase", "Num_Devices", "Avg_CPU_Time_s", "Avg_Energy_J"])
    for scheme in schemes:
        for phase in phases:
            d = data[scheme][phase]
            w.writerow([scheme, phase_labels[phase], d["count"], f"{d['cpu']:.6f}", f"{d['energy']:.6f}"])
print(f"\nComparison CSV: {out_csv}")

# --- Charts ---
scheme_names = list(schemes.keys())
colors = ['#2196F3', '#FF9800', '#4CAF50']  # Blue, Orange, Green

# Chart 1: CPU Time comparison (grouped bar)
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

x = np.arange(len(phases))
width = 0.25

for i, scheme in enumerate(scheme_names):
    cpu_vals = [data[scheme][p]["cpu"] for p in phases]
    axes[0].bar(x + i * width, cpu_vals, width, label=scheme, color=colors[i])

axes[0].set_xlabel('Phase')
axes[0].set_ylabel('Average CPU Time (s)')
axes[0].set_title('CPU Time Comparison Across Schemes')
axes[0].set_xticks(x + width)
axes[0].set_xticklabels([phase_labels[p] for p in phases])
axes[0].legend()
axes[0].grid(axis='y', alpha=0.3)

# Chart 2: Energy comparison (grouped bar)
for i, scheme in enumerate(scheme_names):
    energy_vals = [data[scheme][p]["energy"] for p in phases]
    axes[1].bar(x + i * width, energy_vals, width, label=scheme, color=colors[i])

axes[1].set_xlabel('Phase')
axes[1].set_ylabel('Average Energy (J)')
axes[1].set_title('Energy Consumption Comparison Across Schemes')
axes[1].set_xticks(x + width)
axes[1].set_xticklabels([phase_labels[p] for p in phases])
axes[1].legend()
axes[1].grid(axis='y', alpha=0.3)

plt.tight_layout()
fig.savefig(os.path.join(BASE, "comparison-cpu-energy.png"), dpi=150)
print(f"Chart saved: comparison-cpu-energy.png")

# Chart 3: Total cost per scheme (stacked bar)
fig2, axes2 = plt.subplots(1, 2, figsize=(12, 5))

for ax, metric, label in [(axes2[0], "cpu", "CPU Time (s)"), (axes2[1], "energy", "Energy (J)")]:
    bottom = np.zeros(len(scheme_names))
    for phase in phases:
        vals = [data[s][phase][metric] for s in scheme_names]
        ax.bar(scheme_names, vals, bottom=bottom, label=phase_labels[phase])
        bottom += np.array(vals)
    ax.set_ylabel(f'Total {label}')
    ax.set_title(f'Total {label} (All Phases)')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
fig2.savefig(os.path.join(BASE, "comparison-total-stacked.png"), dpi=150)
print(f"Chart saved: comparison-total-stacked.png")

# Print summary table
print("\n" + "=" * 80)
print(f"{'Scheme':<20s} {'Phase':<16s} {'CPU Time (s)':>14s} {'Energy (J)':>14s}")
print("-" * 80)
for scheme in scheme_names:
    total_cpu = 0
    total_energy = 0
    for phase in phases:
        d = data[scheme][phase]
        print(f"{scheme:<20s} {phase_labels[phase]:<16s} {d['cpu']:>14.4f} {d['energy']:>14.4f}")
        total_cpu += d['cpu']
        total_energy += d['energy']
    print(f"{scheme:<20s} {'TOTAL':<16s} {total_cpu:>14.4f} {total_energy:>14.4f}")
    print("-" * 80)
print("=" * 80)
