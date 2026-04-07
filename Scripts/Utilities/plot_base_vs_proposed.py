"""
plot_base_vs_proposed.py — Base Scheme vs Proposed Extended Scheme comparison charts

Generates 4 charts:
  1. CPU Time per Phase (grouped bar with error bars)
  2. Energy per Phase (grouped bar with error bars)
  3. Per-device Auth CPU Time comparison
  4. Per-device Auth Energy comparison

Output: Results/Charts/06-Base-vs-Proposed/
"""
import os
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
MULTI_SEED_CSV = os.path.join(ROOT, "Results", "CSV-Data", "Multi-Seed-Summary", "multi-seed-summary.csv")
PER_DEVICE_CSV = os.path.join(ROOT, "Results", "Charts", "Aligned-Comparison", "Option1-per-device.csv")
CHART_DIR = os.path.join(ROOT, "Results", "Charts", "06-Base-vs-Proposed")
os.makedirs(CHART_DIR, exist_ok=True)

COLORS = {"Base": "#2196F3", "Proposed": "#4CAF50"}
PHASES = ["Enrollment", "Authentication", "Key Exchange"]
PHASE_LABELS = ["Enrollment", "Auth", "Key Exch"]

# --- Load multi-seed summary ---
data = {}  # data[scheme][phase] = {avg_cpu, std_cpu, avg_energy, std_energy}
with open(MULTI_SEED_CSV, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        scheme = row["Scheme"].strip()
        phase = row["Phase"].strip()
        if scheme not in ("Base-Scheme", "Proposed-Scheme"):
            continue
        key = "Base" if scheme == "Base-Scheme" else "Proposed"
        if key not in data:
            data[key] = {}
        data[key][phase] = {
            "avg_cpu":    float(row["Avg_CPU_s"]),
            "std_cpu":    float(row["StdDev_CPU_s"]),
            "avg_energy": float(row["Avg_Energy_J"]),
            "std_energy": float(row["StdDev_Energy_J"]),
        }

# --- Build arrays for phase charts ---
base_cpu    = [data["Base"][p]["avg_cpu"]    for p in PHASES]
base_cpu_e  = [data["Base"][p]["std_cpu"]    for p in PHASES]
prop_cpu    = [data["Proposed"][p]["avg_cpu"]    for p in PHASES]
prop_cpu_e  = [data["Proposed"][p]["std_cpu"]    for p in PHASES]

base_eng    = [data["Base"][p]["avg_energy"]    for p in PHASES]
base_eng_e  = [data["Base"][p]["std_energy"]    for p in PHASES]
prop_eng    = [data["Proposed"][p]["avg_energy"]    for p in PHASES]
prop_eng_e  = [data["Proposed"][p]["std_energy"]    for p in PHASES]

x = np.arange(len(PHASES))
W = 0.32


# ─────────────────────────────────────────────
# Chart 1: CPU Time per Phase
# ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
bars_b = ax.bar(x - W/2, base_cpu, W, yerr=base_cpu_e, capsize=5,
                label="Base Scheme", color=COLORS["Base"], alpha=0.9)
bars_p = ax.bar(x + W/2, prop_cpu, W, yerr=prop_cpu_e, capsize=5,
                label="Proposed (Ours)", color=COLORS["Proposed"], alpha=0.9)

# Value labels on bars
for bar in bars_b:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.004, f"{h:.3f}",
            ha="center", va="bottom", fontsize=8.5, color="#1565C0")
for bar in bars_p:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.004, f"{h:.3f}",
            ha="center", va="bottom", fontsize=8.5, color="#2E7D32")

ax.set_xticks(x)
ax.set_xticklabels(PHASE_LABELS, fontsize=12)
ax.set_xlabel("Protocol Phase", fontsize=12)
ax.set_ylabel("Avg CPU Time (s)", fontsize=12)
ax.set_title("CPU Time: Base Scheme vs Proposed Scheme\n(5-seed average, 20 devices per seed)",
             fontsize=13, fontweight="bold")
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
ax.set_ylim(0, max(max(base_cpu), max(prop_cpu)) * 1.22)
fig.tight_layout()
out1 = os.path.join(CHART_DIR, "01-CPU-Time-Per-Phase.png")
fig.savefig(out1, dpi=200)
plt.close(fig)
print(f"Saved: {out1}")


# ─────────────────────────────────────────────
# Chart 2: Energy per Phase
# ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
bars_b = ax.bar(x - W/2, base_eng, W, yerr=base_eng_e, capsize=5,
                label="Base Scheme", color=COLORS["Base"], alpha=0.9)
bars_p = ax.bar(x + W/2, prop_eng, W, yerr=prop_eng_e, capsize=5,
                label="Proposed (Ours)", color=COLORS["Proposed"], alpha=0.9)

for bar in bars_b:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.0002, f"{h:.4f}",
            ha="center", va="bottom", fontsize=8.5, color="#1565C0")
for bar in bars_p:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.0002, f"{h:.4f}",
            ha="center", va="bottom", fontsize=8.5, color="#2E7D32")

ax.set_xticks(x)
ax.set_xticklabels(PHASE_LABELS, fontsize=12)
ax.set_xlabel("Protocol Phase", fontsize=12)
ax.set_ylabel("Avg Energy (J)", fontsize=12)
ax.set_title("Energy Consumption: Base Scheme vs Proposed Scheme\n(5-seed average, 20 devices per seed)",
             fontsize=13, fontweight="bold")
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
ax.set_ylim(0, max(max(base_eng), max(prop_eng)) * 1.22)
fig.tight_layout()
out2 = os.path.join(CHART_DIR, "02-Energy-Per-Phase.png")
fig.savefig(out2, dpi=200)
plt.close(fig)
print(f"Saved: {out2}")


# ─────────────────────────────────────────────
# Chart 3 & 4: Per-device Auth+KeyEx comparison
# Load raw CSVs directly so both schemes use auth+keyex combined
# ─────────────────────────────────────────────
CSV_DATA = os.path.join(ROOT, "Results", "CSV-Data")

def load_per_device(csv_path, id_col, cpu_col, energy_col):
    result = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip().strip('"'): v.strip().strip('"') for k, v in row.items()}
            did = int(float(row[id_col]))
            result[did] = {"cpu": float(row[cpu_col]), "energy": float(row[energy_col])}
    return result

base_auth_dev  = load_per_device(os.path.join(CSV_DATA, "Base-Scheme", "auth-results.csv"),
                                  "Device_ID", "CPU_Time_s", "Energy_J")
base_keyex_dev = load_per_device(os.path.join(CSV_DATA, "Base-Scheme", "keyex-results.csv"),
                                  "Device_ID", "CPU_Time_s", "Energy_J")
prop_auth_dev  = load_per_device(os.path.join(CSV_DATA, "Proposed-Scheme-Original", "auth-results.csv"),
                                  "Device", "CPU_s", "Energy_J")
prop_keyex_dev = load_per_device(os.path.join(CSV_DATA, "Proposed-Scheme-Original", "keyex-results.csv"),
                                  "Device", "CPU_s", "Energy_J")

# Only common devices across all four files
common_devs = sorted(set(base_auth_dev) & set(base_keyex_dev) & set(prop_auth_dev) & set(prop_keyex_dev))

devices      = [str(d) for d in common_devs]
base_cpu_dev = [base_auth_dev[d]["cpu"]    + base_keyex_dev[d]["cpu"]    for d in common_devs]
base_eng_dev = [base_auth_dev[d]["energy"] + base_keyex_dev[d]["energy"] for d in common_devs]
prop_cpu_dev = [prop_auth_dev[d]["cpu"]    + prop_keyex_dev[d]["cpu"]    for d in common_devs]
prop_eng_dev = [prop_auth_dev[d]["energy"] + prop_keyex_dev[d]["energy"] for d in common_devs]

xd = np.arange(len(devices))
Wd = 0.35

# Chart 3: Per-device CPU Time
fig, ax = plt.subplots(figsize=(13, 6))
ax.bar(xd - Wd/2, base_cpu_dev, Wd, label="Base Scheme",   color=COLORS["Base"],     alpha=0.9)
ax.bar(xd + Wd/2, prop_cpu_dev, Wd, label="Proposed (Ours)", color=COLORS["Proposed"], alpha=0.9)
ax.set_xticks(xd)
ax.set_xticklabels(devices, fontsize=9, rotation=45)
ax.set_xlabel("Device ID", fontsize=12)
ax.set_ylabel("Total CPU Time (s)", fontsize=12)
ax.set_title("Per-Device CPU Time: Base Scheme vs Proposed Scheme\n(Auth + Key Exchange combined)",
             fontsize=13, fontweight="bold")
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
out3 = os.path.join(CHART_DIR, "03-Per-Device-CPU-Time.png")
fig.savefig(out3, dpi=200)
plt.close(fig)
print(f"Saved: {out3}")

# Chart 4: Per-device Energy
fig, ax = plt.subplots(figsize=(13, 6))
ax.bar(xd - Wd/2, base_eng_dev, Wd, label="Base Scheme",   color=COLORS["Base"],     alpha=0.9)
ax.bar(xd + Wd/2, prop_eng_dev, Wd, label="Proposed (Ours)", color=COLORS["Proposed"], alpha=0.9)
ax.set_xticks(xd)
ax.set_xticklabels(devices, fontsize=9, rotation=45)
ax.set_xlabel("Device ID", fontsize=12)
ax.set_ylabel("Total Energy (J)", fontsize=12)
ax.set_title("Per-Device Energy: Base Scheme vs Proposed Scheme\n(Auth + Key Exchange combined)",
             fontsize=13, fontweight="bold")
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
out4 = os.path.join(CHART_DIR, "04-Per-Device-Energy.png")
fig.savefig(out4, dpi=200)
plt.close(fig)
print(f"Saved: {out4}")


# ─────────────────────────────────────────────
# Chart 5: Side-by-side summary (Total across phases)
# ─────────────────────────────────────────────
total_base_cpu = sum(base_cpu)
total_prop_cpu = sum(prop_cpu)
total_base_eng = sum(base_eng)
total_prop_eng = sum(prop_eng)

fig, axes = plt.subplots(1, 2, figsize=(10, 6))

# CPU total
ax = axes[0]
bars = ax.bar(["Base Scheme", "Proposed (Ours)"],
              [total_base_cpu, total_prop_cpu],
              color=[COLORS["Base"], COLORS["Proposed"]], width=0.45, alpha=0.9)
for bar in bars:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.005, f"{h:.3f}s",
            ha="center", va="bottom", fontsize=11, fontweight="bold")
pct = (total_prop_cpu - total_base_cpu) / total_base_cpu * 100
sign = "+" if pct > 0 else ""
ax.set_title(f"Total CPU Time\n({sign}{pct:.1f}% vs Base)", fontsize=12, fontweight="bold")
ax.set_ylabel("Total CPU Time (s)", fontsize=11)
ax.set_ylim(0, max(total_base_cpu, total_prop_cpu) * 1.2)
ax.grid(axis="y", alpha=0.3)

# Energy total
ax = axes[1]
bars = ax.bar(["Base Scheme", "Proposed (Ours)"],
              [total_base_eng, total_prop_eng],
              color=[COLORS["Base"], COLORS["Proposed"]], width=0.45, alpha=0.9)
for bar in bars:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.0003, f"{h:.4f}J",
            ha="center", va="bottom", fontsize=11, fontweight="bold")
pct = (total_prop_eng - total_base_eng) / total_base_eng * 100
sign = "+" if pct > 0 else ""
ax.set_title(f"Total Energy\n({sign}{pct:.1f}% vs Base)", fontsize=12, fontweight="bold")
ax.set_ylabel("Total Energy (J)", fontsize=11)
ax.set_ylim(0, max(total_base_eng, total_prop_eng) * 1.2)
ax.grid(axis="y", alpha=0.3)

fig.suptitle("Overall Protocol Cost: Base Scheme vs Proposed Scheme\n(Sum of all phases, 5-seed avg)",
             fontsize=13, fontweight="bold")
fig.tight_layout()
out5 = os.path.join(CHART_DIR, "05-Total-Overall-Cost.png")
fig.savefig(out5, dpi=200)
plt.close(fig)
print(f"Saved: {out5}")

print("\nAll done. Charts in:", CHART_DIR)
