"""
plot_option1_per_device.py — Plots per-device total CPU time and energy (Option 1)

- Reads Option1-per-device.csv
- Plots grouped bar charts for all available devices (Base, Proposed, LAAKA)
- Saves charts to Results/Charts/Aligned-Comparison/
"""
import os
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
CSV_PATH = os.path.join(ROOT, "Results", "Charts", "Aligned-Comparison", "Option1-per-device.csv")
CHART_DIR = os.path.join(ROOT, "Results", "Charts", "Aligned-Comparison")
os.makedirs(CHART_DIR, exist_ok=True)

# Read CSV
devices = []
base_cpu = []
base_energy = []
prop_cpu = []
prop_energy = []
laaka_cpu = []
laaka_energy = []

with open(CSV_PATH, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        devices.append(str(row["Device_ID"]))
        base_cpu.append(float(row["Base_CPU_s"]))
        base_energy.append(float(row["Base_Energy_J"]))
        prop_cpu.append(float(row["Proposed_CPU_s"]))
        prop_energy.append(float(row["Proposed_Energy_J"]))
        laaka_cpu.append(float(row["LAAKA_CPU_s"]))
        laaka_energy.append(float(row["LAAKA_Energy_J"]))

x = np.arange(len(devices))
W = 0.25

COLORS = {"Base": "#2196F3", "Proposed": "#4CAF50", "LAAKA": "#FF9800"}

# --- Plot CPU Time ---
fig, ax = plt.subplots(figsize=(14, 6))
ax.bar(x - W, base_cpu, W, label="Base", color=COLORS["Base"])
ax.bar(x,     prop_cpu, W, label="Proposed", color=COLORS["Proposed"])
ax.bar(x + W, laaka_cpu, W, label="LAAKA", color=COLORS["LAAKA"])
ax.set_xlabel("Device ID", fontsize=12)
ax.set_ylabel("Total CPU Time (s)", fontsize=12)
ax.set_title("Total CPU Time per Device (Option 1)", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(devices, fontsize=10, rotation=45)
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "Option1-per-device-CPU.png"), dpi=200)
plt.close(fig)

# --- Plot Energy ---
fig, ax = plt.subplots(figsize=(14, 6))
ax.bar(x - W, base_energy, W, label="Base", color=COLORS["Base"])
ax.bar(x,     prop_energy, W, label="Proposed", color=COLORS["Proposed"])
ax.bar(x + W, laaka_energy, W, label="LAAKA", color=COLORS["LAAKA"])
ax.set_xlabel("Device ID", fontsize=12)
ax.set_ylabel("Total Energy (J)", fontsize=12)
ax.set_title("Total Energy per Device (Option 1)", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(devices, fontsize=10, rotation=45)
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(CHART_DIR, "Option1-per-device-Energy.png"), dpi=200)
plt.close(fig)

print("Charts saved to:", CHART_DIR)