"""
plot_comparison.py — Compare Base-Scheme vs LAAKA vs Proposed (Anonymity-Extended)

Reads simulation-results.csv from all three scheme folders and generates:
  1. Per-device CPU time comparison bar chart
  2. Per-device Energy comparison bar chart
  3. Average summary bar chart with % improvement labels
"""
import csv
import os
import numpy as np

# ---------- Try matplotlib; graceful fallback to text-only ----------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ---------- Paths ----------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

BASE_CSV     = os.path.join(BASE_DIR, "simulation-results.csv")
LAAKA_CSV    = os.path.join(PARENT_DIR, "LAAKA", "simulation-results.csv")
PROPOSED_CSV = os.path.join(PARENT_DIR, "Anonymity-Extended-Base-Scheme", "simulation-results.csv")

# ---------- Read helper ----------
def read_results(path, id_col="Device", cpu_col="CPU_s", energy_col="Energy_J",
                 alt_id="Device_ID", alt_cpu="CPU_Time_s"):
    data = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        headers = [h.strip().strip('"') for h in reader.fieldnames]
        # Normalise header names
        id_key = id_col if id_col in headers else alt_id
        cpu_key = cpu_col if cpu_col in headers else alt_cpu
        energy_key = energy_col

        f.seek(0)
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k.strip().strip('"'): v.strip().strip('"') for k, v in row.items()}
            did = int(clean[id_key])
            data[did] = {
                "cpu": float(clean[cpu_key]),
                "energy": float(clean[energy_key]),
            }
    return data

# ---------- Load data ----------
base     = read_results(BASE_CSV)
laaka    = read_results(LAAKA_CSV, id_col="Device_ID", cpu_col="CPU_Time_s")
proposed = read_results(PROPOSED_CSV)

devices = sorted(set(base) & set(laaka) & set(proposed))

base_cpu     = [base[d]["cpu"]     for d in devices]
base_energy  = [base[d]["energy"]  for d in devices]
laaka_cpu    = [laaka[d]["cpu"]    for d in devices]
laaka_energy = [laaka[d]["energy"] for d in devices]
prop_cpu     = [proposed[d]["cpu"]     for d in devices]
prop_energy  = [proposed[d]["energy"]  for d in devices]

# ---------- Summary statistics ----------
avg_base_cpu  = np.mean(base_cpu)
avg_base_e    = np.mean(base_energy)
avg_laaka_cpu = np.mean(laaka_cpu)
avg_laaka_e   = np.mean(laaka_energy)
avg_prop_cpu  = np.mean(prop_cpu)
avg_prop_e    = np.mean(prop_energy)

print("=" * 72)
print("           100-Node Simulation — Authentication Phase Results")
print("=" * 72)
print(f"{'':>10}{'Base Scheme':>16}{'LAAKA':>16}{'Proposed':>16}")
print("-" * 72)

for d, bc, be, lc, le, pc, pe in zip(devices, base_cpu, base_energy,
                                      laaka_cpu, laaka_energy,
                                      prop_cpu, prop_energy):
    print(f"Dev {d:>3}   CPU {bc:.4f}s  E {be:.5f}J | "
          f"CPU {lc:.4f}s  E {le:.5f}J | "
          f"CPU {pc:.4f}s  E {pe:.5f}J")

print("-" * 72)
print(f"{'Average':>10}  CPU {avg_base_cpu:.4f}s  E {avg_base_e:.5f}J | "
      f"CPU {avg_laaka_cpu:.4f}s  E {avg_laaka_e:.5f}J | "
      f"CPU {avg_prop_cpu:.4f}s  E {avg_prop_e:.5f}J")

# Improvement of Proposed over LAAKA
imp_cpu_laaka = (avg_laaka_cpu - avg_prop_cpu) / avg_laaka_cpu * 100
imp_e_laaka   = (avg_laaka_e - avg_prop_e) / avg_laaka_e * 100

# Comparison of Proposed vs Base (positive = proposed is worse/higher)
diff_cpu_base = (avg_prop_cpu - avg_base_cpu) / avg_base_cpu * 100
diff_e_base   = (avg_prop_e - avg_base_e) / avg_base_e * 100

print()
print("Proposed vs LAAKA:")
print(f"  CPU improvement:    {imp_cpu_laaka:+.2f}%")
print(f"  Energy improvement: {imp_e_laaka:+.2f}%")
print()
print("Proposed vs Base Scheme:")
print(f"  CPU overhead:       {diff_cpu_base:+.2f}%")
print(f"  Energy overhead:    {diff_e_base:+.2f}%")
print("=" * 72)

# Convert energy to mJ for chart readability
base_energy_mj  = [e * 1000 for e in base_energy]
laaka_energy_mj = [e * 1000 for e in laaka_energy]
prop_energy_mj  = [e * 1000 for e in prop_energy]

if not HAS_MPL:
    print("\nmatplotlib not available — skipping chart generation.")
    print("Install with: pip install matplotlib")
    exit(0)

# ---------- Chart styling ----------
BAR_WIDTH = 0.25
x = np.arange(len(devices))
labels = [str(d) for d in devices]

COLORS = {
    "base":     "#2196F3",  # Blue
    "laaka":    "#FF9800",  # Orange
    "proposed": "#4CAF50",  # Green
}

def style_ax(ax, title, ylabel):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_xlabel("Device ID", fontsize=11)
    ax.set_xticks(x + BAR_WIDTH)
    ax.set_xticklabels(labels, fontsize=8, rotation=45)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)

# ---- Chart 1: CPU Time ----
fig1, ax1 = plt.subplots(figsize=(14, 5))
ax1.bar(x,                base_cpu,  BAR_WIDTH, label="Base Scheme",     color=COLORS["base"])
ax1.bar(x + BAR_WIDTH,    laaka_cpu, BAR_WIDTH, label="LAAKA",           color=COLORS["laaka"])
ax1.bar(x + 2*BAR_WIDTH,  prop_cpu,  BAR_WIDTH, label="Proposed (Ours)", color=COLORS["proposed"])
style_ax(ax1, "Per-Device CPU Time — Auth Phase (100-Node Simulation)", "CPU Time (s)")
fig1.tight_layout()
fig1.savefig(os.path.join(BASE_DIR, "chart1_cpu_comparison.png"), dpi=150)
print("Saved chart1_cpu_comparison.png")

# ---- Chart 2: Energy ----
fig2, ax2 = plt.subplots(figsize=(14, 5))
ax2.bar(x,                base_energy_mj,  BAR_WIDTH, label="Base Scheme",     color=COLORS["base"])
ax2.bar(x + BAR_WIDTH,    laaka_energy_mj, BAR_WIDTH, label="LAAKA",           color=COLORS["laaka"])
ax2.bar(x + 2*BAR_WIDTH,  prop_energy_mj,  BAR_WIDTH, label="Proposed (Ours)", color=COLORS["proposed"])
style_ax(ax2, "Per-Device Energy Consumption — Auth Phase (100-Node Simulation)", "Energy (mJ)")
fig2.tight_layout()
fig2.savefig(os.path.join(BASE_DIR, "chart2_energy_comparison.png"), dpi=150)
print("Saved chart2_energy_comparison.png")

# ---- Chart 3: Average Summary ----
fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(12, 5))

schemes = ["Base Scheme", "LAAKA", "Proposed\n(Ours)"]
avg_cpus = [avg_base_cpu, avg_laaka_cpu, avg_prop_cpu]
avg_energies = [avg_base_e * 1000, avg_laaka_e * 1000, avg_prop_e * 1000]
colors3 = [COLORS["base"], COLORS["laaka"], COLORS["proposed"]]

bars_cpu = ax3a.bar(schemes, avg_cpus, color=colors3, width=0.5, edgecolor="white")
ax3a.set_title("Average CPU Time", fontsize=12, fontweight="bold")
ax3a.set_ylabel("CPU Time (s)")
ax3a.grid(axis="y", alpha=0.3)
for bar, val in zip(bars_cpu, avg_cpus):
    ax3a.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
              f"{val:.4f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")

bars_e = ax3b.bar(schemes, avg_energies, color=colors3, width=0.5, edgecolor="white")
ax3b.set_title("Average Energy Consumption", fontsize=12, fontweight="bold")
ax3b.set_ylabel("Energy (mJ)")
ax3b.grid(axis="y", alpha=0.3)
for bar, val in zip(bars_e, avg_energies):
    ax3b.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
              f"{val:.2f} mJ", ha="center", va="bottom", fontsize=9, fontweight="bold")

fig3.suptitle("Average Authentication Cost Comparison (100-Node Network)",
              fontsize=13, fontweight="bold", y=1.02)
fig3.tight_layout()
fig3.savefig(os.path.join(BASE_DIR, "chart3_average_summary.png"), dpi=150, bbox_inches="tight")
print("Saved chart3_average_summary.png")

plt.close("all")
print("\nAll charts generated successfully.")
