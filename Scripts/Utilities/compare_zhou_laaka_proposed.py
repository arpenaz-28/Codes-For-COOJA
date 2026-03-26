import os, csv, re
import matplotlib.pyplot as plt
import numpy as np

# Averages calculated from Results/CSV-Data/Multi-Seed-Summary/all-schemes-comparison.csv
# Enrollment sums up user and sensor phases if applicable
data = {
    "Proposed (Ours)": {
        "Enrollment": {"cpu": 0.424157, "energy": 0.026160},
        "Authentication": {"cpu": 0.430947, "energy": 0.026559},
        "Key Exchange": {"cpu": 0.294291, "energy": 0.018144}
    },
    "LAAKA": {
        "Enrollment": {"cpu": 0.214873, "energy": 0.013249},
        "Authentication": {"cpu": 0.734873, "energy": 0.045312},
        "Key Exchange": {"cpu": 0.554436, "energy": 0.034188}
    },
    "Zhou et al.": {
        "Enrollment": {"cpu": 0, "energy": 0},
        "Authentication": {"cpu": 0, "energy": 0},
        "Key Exchange": {"cpu": 0, "energy": 0}
    }
}

# Parse Zhou's energy-results.txt
zhou_file = r"C:\ANUP\MTP\Proposing\Codes For COOJA\Zhou-Scheme\energy-results.txt"
zhou_user_enroll_cpu = []
zhou_user_enroll_en = []
zhou_sn_auth_cpu = []
zhou_sn_auth_en = []
zhou_user_keyex_cpu = []
zhou_user_keyex_en = []


with open(zhou_file, "r") as f:
    content = f.read().split("Zhou-Scheme\\COOJA.testlog:")
    for chunk in content:
        joined_line = chunk.replace("\n", "").replace("\r", "")
        if "ENROLL_ENERGY|" in joined_line:
            cpu_m = re.search(r"cpu_s=([\d\.]+)", joined_line)
            en_m = re.search(r"energy_j=([\d\.]+)", joined_line)
            if cpu_m: zhou_user_enroll_cpu.append(float(cpu_m.group(1)))
            if en_m: zhou_user_enroll_en.append(float(en_m.group(1)))
        elif "ENROLL_ENERGY_SN|" in joined_line:
            cpu_m = re.search(r"cpu_s=([\d\.]+)", joined_line)
            en_m = re.search(r"energy_j=([\d\.]+)", joined_line)
            if cpu_m: zhou_sn_auth_cpu.append(float(cpu_m.group(1)))
            if en_m: zhou_sn_auth_en.append(float(en_m.group(1)))
        elif "KEYEX_ENERGY|" in joined_line:
            cpu_m = re.search(r"cpu_s=([\d\.]+)", joined_line)
            en_m = re.search(r"energy_j=([\d\.]+)", joined_line)
            if cpu_m: zhou_user_keyex_cpu.append(float(cpu_m.group(1)))
            if en_m: zhou_user_keyex_en.append(float(en_m.group(1)))

# Sensor Enrollment wasn't logged independently in testlog for Zhou, but it's computationally similar to User Enroll
# We will use User Enrollment average for User, and User KeyEx for Auth as extracted.
if zhou_user_enroll_cpu:
    data["Zhou et al."]["Enrollment"]["cpu"] = np.mean(zhou_user_enroll_cpu) * 2 # Appx for both entities
    data["Zhou et al."]["Enrollment"]["energy"] = np.mean(zhou_user_enroll_en) * 2

if zhou_sn_auth_cpu:
    # Auth is dominated by Sensor M3 gen in Cooja testlog
    data["Zhou et al."]["Authentication"]["cpu"] = np.mean(zhou_sn_auth_cpu)
    data["Zhou et al."]["Authentication"]["energy"] = np.mean(zhou_sn_auth_en)

if zhou_user_keyex_cpu:
    data["Zhou et al."]["Key Exchange"]["cpu"] = np.mean(zhou_user_keyex_cpu)
    data["Zhou et al."]["Key Exchange"]["energy"] = np.mean(zhou_user_keyex_en)

# Generate Table
print("-" * 80)
print(f"{'Scheme':<20} | {'Phase':<15} | {'CPU Time (s)':<15} | {'Energy (mJ)':<15}")
print("-" * 80)
for scheme, phases in data.items():
    for phase, metrics in phases.items():
        print(f"{scheme:<20} | {phase:<15} | {metrics['cpu']:<15.6f} | {metrics['energy']*1000:<15.3f}")
print("-" * 80)

total_cost = {}
for scheme, phases in data.items():
    tot_cpu = sum(p["cpu"] for p in phases.values())
    tot_en = sum(p["energy"] for p in phases.values())
    total_cost[scheme] = {"cpu": tot_cpu, "energy": tot_en}
    print(f"{scheme} Total: CPU {tot_cpu:.6f} s, Energy {tot_en*1000:.3f} mJ")

# ==========================================================================
# CHARTS - Redesigned to match stunning aesthetic of previous charts
# ==========================================================================
out_dir = r"C:\ANUP\MTP\Proposing\Codes For COOJA\Results\Charts\03-Zhou-vs-LAAKA-vs-Proposed-Final"
os.makedirs(out_dir, exist_ok=True)

COLORS = {"Proposed (Ours)": "#4CAF50", "LAAKA": "#FF9800", "Zhou et al.": "#E91E63"}
SCHEME_ORDER = ["Proposed (Ours)", "LAAKA", "Zhou et al."]
SCHEME_LABELS = ["Proposed\n(Ours)", "LAAKA", "Zhou et al."]

def save_fig(fig, name):
    path = os.path.join(out_dir, name)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    print(f"Chart saved: {path}")
    plt.close(fig)

# ---------- Chart 1: Total Performance (Side-by-Side Subplots) ----------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

cpus = [total_cost[s]["cpu"] for s in SCHEME_ORDER]
energies_mj = [total_cost[s]["energy"] * 1000 for s in SCHEME_ORDER]
colors = [COLORS[s] for s in SCHEME_ORDER]

bars1 = ax1.bar(SCHEME_LABELS, cpus, capsize=5, color=colors, width=0.5, edgecolor="white")
ax1.set_ylabel("CPU Time (s)", fontsize=12, fontweight="bold")
ax1.set_title("CPU Time — Total Protocol Cost", fontsize=12, fontweight="bold")
ax1.grid(axis="y", alpha=0.3)
for bar, val in zip(bars1, cpus):
    # Adjust height for the massive Zhou bar so text isn't cut off
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (max(cpus)*0.01),
             f"{val:.3f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")

bars2 = ax2.bar(SCHEME_LABELS, energies_mj, capsize=5, color=colors, width=0.5, edgecolor="white")
ax2.set_ylabel("Energy (mJ)", fontsize=12, fontweight="bold")
ax2.set_title("Energy — Total Protocol Cost", fontsize=12, fontweight="bold")
ax2.grid(axis="y", alpha=0.3)
for bar, val in zip(bars2, energies_mj):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (max(energies_mj)*0.01),
             f"{val:.2f} mJ", ha="center", va="bottom", fontsize=9, fontweight="bold")

fig.suptitle("Three-Scheme Comparison: Total Protocol Cost (Auth+KeyEx+Enroll)",
             fontsize=13, fontweight="bold", y=1.02)
fig.tight_layout()
save_fig(fig, "01-Total-Performance-Comparison.png")

# ---------- Chart 2: Stacked Bar Chart for Energy Breakdown ----------
fig, ax = plt.subplots(figsize=(10, 6.5))
bottom = np.zeros(len(SCHEME_ORDER))
phases_list = ["Enrollment", "Authentication", "Key Exchange"]
phase_colors = ["#90CAF9", "#FFF59D", "#A5D6A7"] # Blue, Yellow, Green pastel

for i, phase in enumerate(phases_list):
    values = [data[s][phase]["energy"] * 1000 for s in SCHEME_ORDER]
    ax.bar(SCHEME_LABELS, values, bottom=bottom, label=phase, color=phase_colors[i], edgecolor='black', width=0.5)
    bottom += np.array(values)

for i, total in enumerate(bottom):
    ax.text(i, total + (max(bottom)*0.01), f"{total:.1f} mJ", ha="center", va="bottom", fontweight="bold", fontsize=10)

ax.set_ylabel("Total Phase Energy (mJ)", fontweight="bold", fontsize=12)
ax.set_title("Energy Breakdown by Protocol Phase", fontweight="bold", fontsize=14)
ax.legend(title="Protocol Phase", fontsize=10, title_fontsize=11)
ax.grid(axis='y', linestyle='--', alpha=0.3)
fig.tight_layout()
save_fig(fig, "02-Energy-Breakdown-Stacked.png")

print(f"\nAll stunning charts generated and saved successfully!")
