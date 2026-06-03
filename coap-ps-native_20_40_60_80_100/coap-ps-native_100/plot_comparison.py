"""
plot_comparison.py
Per-device Auth+KeyEx comparison: Base Scheme (1 seed) vs Proposed Scheme (mean ± CI, 10 seeds).
"""

import csv, os, statistics
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"

BASE_CSV     = os.path.join(os.path.dirname(__file__), "results", "base_scheme_100node.csv")
PROPOSED_CSV = os.path.join(REPO, "Results", "COOJA-Simulation",
                            "10-Seed-Comparison", "Proposed", "seed_results.csv")
OUT_DIR      = os.path.join(os.path.dirname(__file__), "results")

DEVICES = list(range(81, 101))

# ── Load base scheme (single seed, auth+keyex combined) ─────────────────────
base_energy = {}   # device → mJ
base_cpu    = {}   # device → s

with open(BASE_CSV) as f:
    for row in csv.DictReader(f):
        dev = int(row["Device"])
        base_energy[dev] = float(row["Auth_Energy_mJ"])
        base_cpu[dev]    = float(row["Auth_CPU_s"])

# ── Load proposed scheme (10 seeds, auth+keyex = Auth + Keyex columns) ───────
prop_energy_per_dev = {d: [] for d in DEVICES}
prop_cpu_per_dev    = {d: [] for d in DEVICES}

with open(PROPOSED_CSV) as f:
    for row in csv.DictReader(f):
        dev = int(row["Device"])
        if dev not in prop_energy_per_dev:
            continue
        ak_energy = float(row["Auth_Energy_mJ"]) + float(row["Keyex_Energy_mJ"])
        ak_cpu    = float(row["Auth_CPU_s"])    + float(row["Keyex_CPU_s"])
        prop_energy_per_dev[dev].append(ak_energy)
        prop_cpu_per_dev[dev].append(ak_cpu)

# Compute mean and 95% CI (t * std/sqrt(n), t≈2.262 for n=10, df=9)
T95 = 2.262

def mean_ci(vals):
    if len(vals) < 2:
        return np.mean(vals), 0.0
    m = statistics.mean(vals)
    s = statistics.stdev(vals)
    ci = T95 * s / (len(vals) ** 0.5)
    return m, ci

prop_energy_mean = {}
prop_energy_ci   = {}
prop_cpu_mean    = {}
prop_cpu_ci      = {}

for dev in DEVICES:
    prop_energy_mean[dev], prop_energy_ci[dev] = mean_ci(prop_energy_per_dev[dev])
    prop_cpu_mean[dev],    prop_cpu_ci[dev]    = mean_ci(prop_cpu_per_dev[dev])

# ── Plot ─────────────────────────────────────────────────────────────────────
x      = np.arange(len(DEVICES))
width  = 0.38
labels = [str(d) for d in DEVICES]

fig, (ax_e, ax_c) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
fig.suptitle("Auth + Key Exchange Phase: Base Scheme vs Proposed\n(100-node network, devices 81–100)",
             fontsize=13, fontweight="bold")

# ── Energy panel ─────────────────────────────────────────────────────────────
b_e = [base_energy[d] for d in DEVICES]
p_e = [prop_energy_mean[d] for d in DEVICES]
p_e_ci = [prop_energy_ci[d] for d in DEVICES]

bars1 = ax_e.bar(x - width/2, b_e, width, label="Base Scheme (1 seed)",
                 color="#4C72B0", alpha=0.88)
bars2 = ax_e.bar(x + width/2, p_e, width, label="Proposed (mean, 10 seeds)",
                 color="#DD8452", alpha=0.88,
                 yerr=p_e_ci, capsize=3, error_kw=dict(elinewidth=1.2, ecolor="black"))

ax_e.set_ylabel("Energy (mJ)", fontsize=11)
ax_e.set_title("Auth + Key Exchange Energy per Device", fontsize=11)
ax_e.legend(fontsize=10)
ax_e.yaxis.set_minor_locator(mticker.AutoMinorLocator())
ax_e.grid(axis="y", linestyle="--", alpha=0.5)
ax_e.set_ylim(0, max(max(b_e), max(p_e)) * 1.25)

# Annotate mean lines
ax_e.axhline(np.mean(b_e), color="#4C72B0", linestyle=":", linewidth=1.2,
             label=f"Base mean: {np.mean(b_e):.2f} mJ")
ax_e.axhline(np.mean(p_e), color="#DD8452", linestyle=":", linewidth=1.2,
             label=f"Proposed mean: {np.mean(p_e):.2f} mJ")
ax_e.legend(fontsize=9, loc="upper left")

# ── CPU time panel ────────────────────────────────────────────────────────────
b_c = [base_cpu[d] for d in DEVICES]
p_c = [prop_cpu_mean[d] for d in DEVICES]
p_c_ci = [prop_cpu_ci[d] for d in DEVICES]

ax_c.bar(x - width/2, b_c, width, label="Base Scheme (1 seed)",
         color="#4C72B0", alpha=0.88)
ax_c.bar(x + width/2, p_c, width, label="Proposed (mean, 10 seeds)",
         color="#DD8452", alpha=0.88,
         yerr=p_c_ci, capsize=3, error_kw=dict(elinewidth=1.2, ecolor="black"))

ax_c.set_ylabel("CPU Time (s)", fontsize=11)
ax_c.set_title("Auth + Key Exchange CPU Time per Device", fontsize=11)
ax_c.set_xticks(x)
ax_c.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
ax_c.set_xlabel("Device ID", fontsize=11)
ax_c.yaxis.set_minor_locator(mticker.AutoMinorLocator())
ax_c.grid(axis="y", linestyle="--", alpha=0.5)
ax_c.set_ylim(0, max(max(b_c), max(p_c)) * 1.25)

ax_c.axhline(np.mean(b_c), color="#4C72B0", linestyle=":", linewidth=1.2,
             label=f"Base mean: {np.mean(b_c):.4f} s")
ax_c.axhline(np.mean(p_c), color="#DD8452", linestyle=":", linewidth=1.2,
             label=f"Proposed mean: {np.mean(p_c):.4f} s")
ax_c.legend(fontsize=9, loc="upper left")

plt.tight_layout()
out_path = os.path.join(OUT_DIR, "auth_keyex_comparison.png")
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Saved: {out_path}")

# ── Console summary ───────────────────────────────────────────────────────────
print(f"\n{'Device':>8}  {'Base E (mJ)':>12}  {'Prop E (mJ)':>12}  {'Base CPU (s)':>13}  {'Prop CPU (s)':>13}")
print("-" * 65)
for dev in DEVICES:
    print(f"{dev:>8}  {base_energy[dev]:>12.4f}  {prop_energy_mean[dev]:>12.4f}"
          f"  {base_cpu[dev]:>13.6f}  {prop_cpu_mean[dev]:>13.6f}")
print("-" * 65)
print(f"{'Mean':>8}  {np.mean(b_e):>12.4f}  {np.mean(p_e):>12.4f}"
      f"  {np.mean(b_c):>13.6f}  {np.mean(p_c):>13.6f}")
overhead_e = (np.mean(p_e) - np.mean(b_e)) / np.mean(b_e) * 100
overhead_c = (np.mean(p_c) - np.mean(b_c)) / np.mean(b_c) * 100
print(f"\nProposed overhead vs Base (auth+keyex only):")
print(f"  Energy : {overhead_e:+.1f}%")
print(f"  CPU    : {overhead_c:+.1f}%")
