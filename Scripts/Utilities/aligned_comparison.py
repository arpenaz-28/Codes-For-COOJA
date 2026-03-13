"""
aligned_comparison.py — Fair Aligned Comparison of All 3 Schemes

Generates TWO comparison sets:

  Option 1 — Total Protocol Cost (Auth + KeyEx + Data):
    Base Scheme:  Auth + KeyEx  (approximates auth+keyex; data is excluded
                   from both, so this still slightly favours Base. The
                   modified Base-Scheme-Aligned code fixes this for future runs.)
    Proposed:     Auth phase    (already includes auth + key exchange + data)
    LAAKA:        Auth phase    (already includes auth + ack + data)

  Option 2 — Protocol-Only Cost (No Data CoAP):
    Base Scheme:  Auth + KeyEx  (auth CoAP + session key + DH keyex CoAP — no data)
    Proposed:     KeyEx phase   (auth CoAP only, includes built-in key exchange — no data)
    LAAKA:        KeyEx phase   (auth CoAP + ack CoAP — no data)

Charts saved to: Results/Charts/Aligned-Comparison/
"""
import csv, os, sys
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("WARNING: matplotlib not available — text output only")

# ---------- Paths ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
CSV_DIR = os.path.join(ROOT, "Results", "CSV-Data")
CHART_DIR = os.path.join(ROOT, "Results", "Charts", "Aligned-Comparison")
os.makedirs(CHART_DIR, exist_ok=True)

# ---------- Read CSV helper ----------
def read_csv(filename, id_col="Device_ID", cpu_col="CPU_Time_s", energy_col="Energy_J"):
    path = os.path.join(CSV_DIR, filename)
    if not os.path.exists(path):
        print(f"WARNING: {path} not found")
        return {}
    data = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        headers = [h.strip().strip('"') for h in reader.fieldnames]
        # Normalise column names
        id_key = id_col if id_col in headers else "Device"
        cpu_key = cpu_col if cpu_col in headers else "CPU_s"
        en_key = energy_col if energy_col in headers else "Energy_J"
        f.seek(0)
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k.strip().strip('"'): v.strip().strip('"') for k, v in row.items()}
            did = int(clean[id_key])
            data[did] = {"cpu": float(clean[cpu_key]), "energy": float(clean[en_key])}
    return data

# ---------- Load per-device data ----------
base_auth  = read_csv("Base-Scheme-auth-results.csv")
base_keyex = read_csv("Base-Scheme-keyex-results.csv")
base_enroll = read_csv("Base-Scheme-enroll-results.csv")

laaka_auth   = read_csv("LAAKA-auth-results.csv")
laaka_keyex  = read_csv("LAAKA-keyex-results.csv")
laaka_enroll = read_csv("LAAKA-enroll-results.csv")

prop_auth   = read_csv("Proposed-Scheme-auth-results.csv")
prop_keyex  = read_csv("Proposed-Scheme-keyex-results.csv")
prop_enroll = read_csv("Proposed-Scheme-enroll-results.csv")

# ---------- Multi-seed summary (5-seed averages) ----------
multi_seed = {}
ms_path = os.path.join(CSV_DIR, "all-schemes-comparison.csv")
if os.path.exists(ms_path):
    with open(ms_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["Scheme"].strip(), row["Phase"].strip())
            multi_seed[key] = {
                "cpu": float(row["Avg_CPU_s"]),
                "energy": float(row["Avg_Energy_J"]),
                "std_cpu": float(row["StdDev_CPU_s"]),
                "std_energy": float(row["StdDev_Energy_J"]),
            }

# ==========================================================================
# OPTION 1: Total Protocol Cost (Auth + KeyEx for Base vs Auth for others)
# ==========================================================================
print("\n" + "=" * 80)
print("OPTION 1: Total Protocol Cost Comparison")
print("  Base = Auth + KeyEx (auth CoAP + session key + DH keyex CoAP)")
print("  Proposed = Auth     (auth CoAP + key exchange + data CoAP)")
print("  LAAKA = Auth        (auth CoAP + ack + data CoAP)")
print("=" * 80)

# Per-device: combine Base auth + keyex for common devices
common_opt1 = sorted(set(base_auth) & set(base_keyex) & set(laaka_auth) & set(prop_auth))
opt1 = {"Base": {}, "Proposed": {}, "LAAKA": {}}
for d in common_opt1:
    opt1["Base"][d] = {
        "cpu": base_auth[d]["cpu"] + base_keyex[d]["cpu"],
        "energy": base_auth[d]["energy"] + base_keyex[d]["energy"],
    }
    opt1["Proposed"][d] = prop_auth[d]
    opt1["LAAKA"][d] = laaka_auth[d]

# Multi-seed averages for Option 1
ms_opt1 = {}
if ("Base Scheme", "Authentication") in multi_seed and ("Base Scheme", "Key Exchange") in multi_seed:
    ba = multi_seed[("Base Scheme", "Authentication")]
    bk = multi_seed[("Base Scheme", "Key Exchange")]
    ms_opt1["Base"] = {
        "cpu": ba["cpu"] + bk["cpu"],
        "energy": ba["energy"] + bk["energy"],
        "std_cpu": (ba["std_cpu"]**2 + bk["std_cpu"]**2)**0.5,
        "std_energy": (ba["std_energy"]**2 + bk["std_energy"]**2)**0.5,
    }
if ("LAAKA", "Authentication") in multi_seed:
    ms_opt1["LAAKA"] = multi_seed[("LAAKA", "Authentication")]
if ("Proposed Scheme", "Authentication") in multi_seed:
    ms_opt1["Proposed"] = multi_seed[("Proposed Scheme", "Authentication")]

print(f"\n{'Scheme':<12s} {'Avg CPU (s)':>12s} {'±StdDev':>10s} {'Avg Energy (J)':>16s} {'±StdDev':>10s}")
print("-" * 65)
for name in ["Base", "Proposed", "LAAKA"]:
    if name in ms_opt1:
        d = ms_opt1[name]
        print(f"{name:<12s} {d['cpu']:>12.6f} {d['std_cpu']:>10.6f} {d['energy']:>16.6f} {d['std_energy']:>10.6f}")

# Improvements
if "Base" in ms_opt1 and "Proposed" in ms_opt1:
    b, p = ms_opt1["Base"], ms_opt1["Proposed"]
    print(f"\nProposed vs Base (Opt1):  CPU {'+'if p['cpu']>b['cpu'] else ''}{(p['cpu']-b['cpu'])/b['cpu']*100:.2f}%  |  Energy {'+'if p['energy']>b['energy'] else ''}{(p['energy']-b['energy'])/b['energy']*100:.2f}%")
if "LAAKA" in ms_opt1 and "Proposed" in ms_opt1:
    l, p = ms_opt1["LAAKA"], ms_opt1["Proposed"]
    print(f"Proposed vs LAAKA (Opt1): CPU {(l['cpu']-p['cpu'])/l['cpu']*100:+.2f}% improvement  |  Energy {(l['energy']-p['energy'])/l['energy']*100:+.2f}% improvement")

# ==========================================================================
# OPTION 2: Protocol-Only Cost (No data CoAP)
# ==========================================================================
print("\n" + "=" * 80)
print("OPTION 2: Protocol-Only Cost (Excluding Data CoAP)")
print("  Base = Auth + KeyEx (auth CoAP + session key + DH keyex, no data)")
print("  Proposed = KeyEx    (auth CoAP only, includes built-in key exchange, no data)")
print("  LAAKA = KeyEx       (auth CoAP + ack CoAP, no data)")
print("=" * 80)

common_opt2 = sorted(set(base_auth) & set(base_keyex) & set(laaka_keyex) & set(prop_keyex))
opt2 = {"Base": {}, "Proposed": {}, "LAAKA": {}}
for d in common_opt2:
    opt2["Base"][d] = {
        "cpu": base_auth[d]["cpu"] + base_keyex[d]["cpu"],
        "energy": base_auth[d]["energy"] + base_keyex[d]["energy"],
    }
    opt2["Proposed"][d] = prop_keyex[d]
    opt2["LAAKA"][d] = laaka_keyex[d]

# Multi-seed averages for Option 2
ms_opt2 = {}
if ("Base Scheme", "Authentication") in multi_seed and ("Base Scheme", "Key Exchange") in multi_seed:
    ba = multi_seed[("Base Scheme", "Authentication")]
    bk = multi_seed[("Base Scheme", "Key Exchange")]
    ms_opt2["Base"] = {
        "cpu": ba["cpu"] + bk["cpu"],
        "energy": ba["energy"] + bk["energy"],
        "std_cpu": (ba["std_cpu"]**2 + bk["std_cpu"]**2)**0.5,
        "std_energy": (ba["std_energy"]**2 + bk["std_energy"]**2)**0.5,
    }
if ("LAAKA", "Key Exchange") in multi_seed:
    ms_opt2["LAAKA"] = multi_seed[("LAAKA", "Key Exchange")]
if ("Proposed Scheme", "Key Exchange") in multi_seed:
    ms_opt2["Proposed"] = multi_seed[("Proposed Scheme", "Key Exchange")]

print(f"\n{'Scheme':<12s} {'Avg CPU (s)':>12s} {'±StdDev':>10s} {'Avg Energy (J)':>16s} {'±StdDev':>10s}")
print("-" * 65)
for name in ["Base", "Proposed", "LAAKA"]:
    if name in ms_opt2:
        d = ms_opt2[name]
        print(f"{name:<12s} {d['cpu']:>12.6f} {d['std_cpu']:>10.6f} {d['energy']:>16.6f} {d['std_energy']:>10.6f}")

if "Base" in ms_opt2 and "Proposed" in ms_opt2:
    b, p = ms_opt2["Base"], ms_opt2["Proposed"]
    print(f"\nProposed vs Base (Opt2):  CPU {(b['cpu']-p['cpu'])/b['cpu']*100:+.2f}% improvement  |  Energy {(b['energy']-p['energy'])/b['energy']*100:+.2f}% improvement")
if "LAAKA" in ms_opt2 and "Proposed" in ms_opt2:
    l, p = ms_opt2["LAAKA"], ms_opt2["Proposed"]
    print(f"Proposed vs LAAKA (Opt2): CPU {(l['cpu']-p['cpu'])/l['cpu']*100:+.2f}% improvement  |  Energy {(l['energy']-p['energy'])/l['energy']*100:+.2f}% improvement")

# ==========================================================================
# ENROLLMENT Comparison (already aligned — single-tick in all schemes)
# ==========================================================================
ms_enroll = {}
for scheme, label in [("Base Scheme", "Base"), ("LAAKA", "LAAKA"), ("Proposed Scheme", "Proposed")]:
    if (scheme, "Enrollment") in multi_seed:
        ms_enroll[label] = multi_seed[(scheme, "Enrollment")]

# ==========================================================================
# Write comparison CSVs
# ==========================================================================
for opt_name, ms_data, desc in [
    ("Option1-Total-Protocol-Cost", ms_opt1, "Total Protocol (Auth+KeyEx for Base, Auth for others)"),
    ("Option2-Protocol-Only", ms_opt2, "Protocol-Only (Auth+KeyEx for Base, KeyEx for others)"),
]:
    csv_path = os.path.join(CHART_DIR, f"{opt_name}-summary.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comparison", "Scheme", "Avg_CPU_s", "StdDev_CPU_s", "Avg_Energy_J", "StdDev_Energy_J"])
        for name in ["Base", "Proposed", "LAAKA"]:
            if name in ms_data:
                d = ms_data[name]
                w.writerow([desc, name, f"{d['cpu']:.6f}", f"{d['std_cpu']:.6f}",
                           f"{d['energy']:.6f}", f"{d['std_energy']:.6f}"])
    print(f"\nSaved: {csv_path}")

# Per-device CSVs
for opt_name, opt_data, devices in [
    ("Option1-per-device", opt1, common_opt1),
    ("Option2-per-device", opt2, common_opt2),
]:
    csv_path = os.path.join(CHART_DIR, f"{opt_name}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device_ID",
                     "Base_CPU_s", "Base_Energy_J",
                     "Proposed_CPU_s", "Proposed_Energy_J",
                     "LAAKA_CPU_s", "LAAKA_Energy_J",
                     "Proposed_vs_Base_CPU_pct", "Proposed_vs_LAAKA_CPU_pct",
                     "Proposed_vs_Base_Energy_pct", "Proposed_vs_LAAKA_Energy_pct"])
        for d in devices:
            bc, be = opt_data["Base"][d]["cpu"], opt_data["Base"][d]["energy"]
            pc, pe = opt_data["Proposed"][d]["cpu"], opt_data["Proposed"][d]["energy"]
            lc, le = opt_data["LAAKA"][d]["cpu"], opt_data["LAAKA"][d]["energy"]
            w.writerow([d, f"{bc:.6f}", f"{be:.6f}",
                       f"{pc:.6f}", f"{pe:.6f}",
                       f"{lc:.6f}", f"{le:.6f}",
                       f"{(bc-pc)/bc*100:.2f}" if bc else "N/A",
                       f"{(lc-pc)/lc*100:.2f}" if lc else "N/A",
                       f"{(be-pe)/be*100:.2f}" if be else "N/A",
                       f"{(le-pe)/le*100:.2f}" if le else "N/A"])
    print(f"Saved: {csv_path}")

# ==========================================================================
# CHARTS
# ==========================================================================
if not HAS_MPL:
    print("\nSkipping charts (matplotlib not available)")
    sys.exit(0)

COLORS = {"Base": "#2196F3", "Proposed": "#4CAF50", "LAAKA": "#FF9800"}
SCHEME_ORDER = ["Base", "Proposed", "LAAKA"]
SCHEME_LABELS = ["Base Scheme", "Proposed\n(Ours)", "LAAKA"]

def save_fig(fig, name):
    path = os.path.join(CHART_DIR, name)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    print(f"Chart: {path}")
    plt.close(fig)


# ---------- Chart 1: Option 1 — Average summary bars ----------
if ms_opt1:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    cpus = [ms_opt1[s]["cpu"] for s in SCHEME_ORDER]
    cpu_err = [ms_opt1[s]["std_cpu"] for s in SCHEME_ORDER]
    energies_mj = [ms_opt1[s]["energy"] * 1000 for s in SCHEME_ORDER]
    energy_err_mj = [ms_opt1[s]["std_energy"] * 1000 for s in SCHEME_ORDER]
    colors = [COLORS[s] for s in SCHEME_ORDER]

    bars1 = ax1.bar(SCHEME_LABELS, cpus, yerr=cpu_err, capsize=5,
                    color=colors, width=0.5, edgecolor="white")
    ax1.set_ylabel("CPU Time (s)", fontsize=12, fontweight="bold")
    ax1.set_title("CPU Time — Total Protocol Cost", fontsize=12, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars1, cpus):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f"{val:.3f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")

    bars2 = ax2.bar(SCHEME_LABELS, energies_mj, yerr=energy_err_mj, capsize=5,
                    color=colors, width=0.5, edgecolor="white")
    ax2.set_ylabel("Energy (mJ)", fontsize=12, fontweight="bold")
    ax2.set_title("Energy — Total Protocol Cost", fontsize=12, fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars2, energies_mj):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{val:.2f} mJ", ha="center", va="bottom", fontsize=9, fontweight="bold")

    fig.suptitle("Option 1: Total Protocol Cost (Auth+KeyEx+Data Equivalent)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_fig(fig, "01-Option1-Total-Protocol-Cost.png")

# ---------- Chart 2: Option 2 — Protocol-Only bars ----------
if ms_opt2:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    cpus = [ms_opt2[s]["cpu"] for s in SCHEME_ORDER]
    cpu_err = [ms_opt2[s]["std_cpu"] for s in SCHEME_ORDER]
    energies_mj = [ms_opt2[s]["energy"] * 1000 for s in SCHEME_ORDER]
    energy_err_mj = [ms_opt2[s]["std_energy"] * 1000 for s in SCHEME_ORDER]
    colors = [COLORS[s] for s in SCHEME_ORDER]

    bars1 = ax1.bar(SCHEME_LABELS, cpus, yerr=cpu_err, capsize=5,
                    color=colors, width=0.5, edgecolor="white")
    ax1.set_ylabel("CPU Time (s)", fontsize=12, fontweight="bold")
    ax1.set_title("CPU Time — Protocol-Only (No Data)", fontsize=12, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars1, cpus):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f"{val:.3f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")

    bars2 = ax2.bar(SCHEME_LABELS, energies_mj, yerr=energy_err_mj, capsize=5,
                    color=colors, width=0.5, edgecolor="white")
    ax2.set_ylabel("Energy (mJ)", fontsize=12, fontweight="bold")
    ax2.set_title("Energy — Protocol-Only (No Data)", fontsize=12, fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars2, energies_mj):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{val:.2f} mJ", ha="center", va="bottom", fontsize=9, fontweight="bold")

    fig.suptitle("Option 2: Protocol-Only Cost (Excluding Data Transmission)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_fig(fig, "02-Option2-Protocol-Only-Cost.png")

# ---------- Chart 3: Per-device CPU comparison (Option 1) ----------
if common_opt1:
    devices = common_opt1
    x = np.arange(len(devices))
    labels = [str(d) for d in devices]
    W = 0.25

    fig, ax = plt.subplots(figsize=(14, 5.5))
    ax.bar(x - W, [opt1["Base"][d]["cpu"] for d in devices], W,
           label="Base (Auth+KeyEx)", color=COLORS["Base"])
    ax.bar(x,     [opt1["Proposed"][d]["cpu"] for d in devices], W,
           label="Proposed (Auth)", color=COLORS["Proposed"])
    ax.bar(x + W, [opt1["LAAKA"][d]["cpu"] for d in devices], W,
           label="LAAKA (Auth)", color=COLORS["LAAKA"])
    ax.set_xlabel("Device ID", fontsize=11)
    ax.set_ylabel("CPU Time (s)", fontsize=11)
    ax.set_title("Option 1: Per-Device CPU Time — Total Protocol Cost", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=45)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    save_fig(fig, "03-Option1-Per-Device-CPU.png")

# ---------- Chart 4: Per-device Energy comparison (Option 1) ----------
if common_opt1:
    fig, ax = plt.subplots(figsize=(14, 5.5))
    ax.bar(x - W, [opt1["Base"][d]["energy"]*1000 for d in devices], W,
           label="Base (Auth+KeyEx)", color=COLORS["Base"])
    ax.bar(x,     [opt1["Proposed"][d]["energy"]*1000 for d in devices], W,
           label="Proposed (Auth)", color=COLORS["Proposed"])
    ax.bar(x + W, [opt1["LAAKA"][d]["energy"]*1000 for d in devices], W,
           label="LAAKA (Auth)", color=COLORS["LAAKA"])
    ax.set_xlabel("Device ID", fontsize=11)
    ax.set_ylabel("Energy (mJ)", fontsize=11)
    ax.set_title("Option 1: Per-Device Energy — Total Protocol Cost", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=45)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    save_fig(fig, "04-Option1-Per-Device-Energy.png")

# ---------- Chart 5: Per-device CPU comparison (Option 2) ----------
if common_opt2:
    devices2 = common_opt2
    x2 = np.arange(len(devices2))
    labels2 = [str(d) for d in devices2]

    fig, ax = plt.subplots(figsize=(14, 5.5))
    ax.bar(x2 - W, [opt2["Base"][d]["cpu"] for d in devices2], W,
           label="Base (Auth+KeyEx)", color=COLORS["Base"])
    ax.bar(x2,     [opt2["Proposed"][d]["cpu"] for d in devices2], W,
           label="Proposed (KeyEx)", color=COLORS["Proposed"])
    ax.bar(x2 + W, [opt2["LAAKA"][d]["cpu"] for d in devices2], W,
           label="LAAKA (KeyEx)", color=COLORS["LAAKA"])
    ax.set_xlabel("Device ID", fontsize=11)
    ax.set_ylabel("CPU Time (s)", fontsize=11)
    ax.set_title("Option 2: Per-Device CPU Time — Protocol-Only (No Data)", fontsize=12, fontweight="bold")
    ax.set_xticks(x2)
    ax.set_xticklabels(labels2, fontsize=8, rotation=45)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    save_fig(fig, "05-Option2-Per-Device-CPU.png")

# ---------- Chart 6: Per-device Energy comparison (Option 2) ----------
if common_opt2:
    fig, ax = plt.subplots(figsize=(14, 5.5))
    ax.bar(x2 - W, [opt2["Base"][d]["energy"]*1000 for d in devices2], W,
           label="Base (Auth+KeyEx)", color=COLORS["Base"])
    ax.bar(x2,     [opt2["Proposed"][d]["energy"]*1000 for d in devices2], W,
           label="Proposed (KeyEx)", color=COLORS["Proposed"])
    ax.bar(x2 + W, [opt2["LAAKA"][d]["energy"]*1000 for d in devices2], W,
           label="LAAKA (KeyEx)", color=COLORS["LAAKA"])
    ax.set_xlabel("Device ID", fontsize=11)
    ax.set_ylabel("Energy (mJ)", fontsize=11)
    ax.set_title("Option 2: Per-Device Energy — Protocol-Only (No Data)", fontsize=12, fontweight="bold")
    ax.set_xticks(x2)
    ax.set_xticklabels(labels2, fontsize=8, rotation=45)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    save_fig(fig, "06-Option2-Per-Device-Energy.png")

# ---------- Chart 7: Side-by-side Option 1 vs Option 2 comparison ----------
if ms_opt1 and ms_opt2:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # Row 1: CPU comparison
    for col, (opt_data, title_tag) in enumerate([
        (ms_opt1, "Option 1: Total Protocol"),
        (ms_opt2, "Option 2: Protocol-Only"),
    ]):
        ax = axes[0][col]
        cpus = [opt_data[s]["cpu"] for s in SCHEME_ORDER]
        errs = [opt_data[s]["std_cpu"] for s in SCHEME_ORDER]
        bars = ax.bar(SCHEME_LABELS, cpus, yerr=errs, capsize=5,
                      color=[COLORS[s] for s in SCHEME_ORDER], width=0.5)
        ax.set_ylabel("CPU Time (s)", fontweight="bold")
        ax.set_title(f"{title_tag}\nCPU Time", fontsize=11, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, cpus):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.008,
                    f"{val:.3f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Row 2: Energy comparison
    for col, (opt_data, title_tag) in enumerate([
        (ms_opt1, "Option 1: Total Protocol"),
        (ms_opt2, "Option 2: Protocol-Only"),
    ]):
        ax = axes[1][col]
        ens = [opt_data[s]["energy"]*1000 for s in SCHEME_ORDER]
        errs = [opt_data[s]["std_energy"]*1000 for s in SCHEME_ORDER]
        bars = ax.bar(SCHEME_LABELS, ens, yerr=errs, capsize=5,
                      color=[COLORS[s] for s in SCHEME_ORDER], width=0.5)
        ax.set_ylabel("Energy (mJ)", fontweight="bold")
        ax.set_title(f"{title_tag}\nEnergy Consumption", fontsize=11, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, ens):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                    f"{val:.2f} mJ", ha="center", va="bottom", fontsize=9, fontweight="bold")

    fig.suptitle("Fair Aligned Comparison: Option 1 (Total) vs Option 2 (Protocol-Only)",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    save_fig(fig, "07-Side-by-Side-Comparison.png")

# ---------- Chart 8: Full 3-phase stacked bar (Enrollment + Auth/Protocol) ----------
if ms_enroll and ms_opt2:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))

    for ax, metric, unit_label, scale in [(ax1, "cpu", "CPU Time (s)", 1),
                                           (ax2, "energy", "Energy (mJ)", 1000)]:
        bottom = np.zeros(3)
        # Enrollment
        enroll_vals = [ms_enroll[s][metric] * scale if s in ms_enroll else 0 for s in SCHEME_ORDER]
        ax.bar(SCHEME_LABELS, enroll_vals, width=0.5, label="Enrollment",
               color="#64B5F6", edgecolor="white")
        bottom = np.array(enroll_vals)

        # Protocol-Only (auth + key exchange, no data)
        proto_vals = [ms_opt2[s][metric] * scale if s in ms_opt2 else 0 for s in SCHEME_ORDER]
        ax.bar(SCHEME_LABELS, proto_vals, width=0.5, bottom=bottom,
               label="Auth + Key Exchange", color="#EF5350", edgecolor="white")
        bottom += np.array(proto_vals)

        # Total on top
        for i, s in enumerate(SCHEME_ORDER):
            total = enroll_vals[i] + proto_vals[i]
            ax.text(i, total + (0.005 if scale == 1 else 0.3),
                    f"{total:.3f}" if scale == 1 else f"{total:.2f}",
                    ha="center", va="bottom", fontsize=9, fontweight="bold")

        ax.set_ylabel(unit_label, fontweight="bold", fontsize=11)
        ax.set_title(f"Total {unit_label.split('(')[0].strip()}\n(Enrollment + Protocol-Only)",
                     fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Full Protocol Cost: Enrollment + Auth&KeyExchange (No Data)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_fig(fig, "08-Full-Protocol-Stacked.png")

# ---------- Chart 9: Improvement percentage chart ----------
if ms_opt1 and ms_opt2:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    metrics = ["CPU Time", "Energy"]
    for ax, metric_key, title in [(ax1, "cpu", "CPU Time Improvement"),
                                   (ax2, "energy", "Energy Improvement")]:
        # Option 1 improvements
        opt1_vs_base = (ms_opt1["Base"][metric_key] - ms_opt1["Proposed"][metric_key]) / ms_opt1["Base"][metric_key] * 100
        opt1_vs_laaka = (ms_opt1["LAAKA"][metric_key] - ms_opt1["Proposed"][metric_key]) / ms_opt1["LAAKA"][metric_key] * 100

        # Option 2 improvements
        opt2_vs_base = (ms_opt2["Base"][metric_key] - ms_opt2["Proposed"][metric_key]) / ms_opt2["Base"][metric_key] * 100
        opt2_vs_laaka = (ms_opt2["LAAKA"][metric_key] - ms_opt2["Proposed"][metric_key]) / ms_opt2["LAAKA"][metric_key] * 100

        x_pos = np.arange(2)
        w = 0.3
        bars1 = ax.bar(x_pos - w/2, [opt1_vs_base, opt1_vs_laaka], w,
                       label="Option 1 (Total)", color="#1976D2")
        bars2 = ax.bar(x_pos + w/2, [opt2_vs_base, opt2_vs_laaka], w,
                       label="Option 2 (Protocol-Only)", color="#388E3C")

        ax.set_xticks(x_pos)
        ax.set_xticklabels(["vs Base Scheme", "vs LAAKA"], fontsize=10)
        ax.set_ylabel("Improvement (%)", fontweight="bold")
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.axhline(y=0, color="black", linewidth=0.8)
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.3)

        for bars in [bars1, bars2]:
            for bar in bars:
                val = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2,
                        bar.get_height() + (1 if val >= 0 else -3),
                        f"{val:+.1f}%", ha="center", va="bottom" if val >= 0 else "top",
                        fontsize=9, fontweight="bold")

    fig.suptitle("Proposed Scheme Improvement Over Others (Positive = Proposed is Better)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_fig(fig, "09-Improvement-Percentages.png")

# ---------- Final summary table ----------
print("\n" + "=" * 90)
print("FINAL ALIGNED COMPARISON TABLE (5-seed averages)")
print("=" * 90)
print(f"{'':>42s} | {'Option 1: Total Protocol':>25s} | {'Option 2: Protocol-Only':>25s}")
print(f"{'Scheme':<15s} {'Metric':<10s} | {'Value':>12s} {'vs Proposed':>12s} | {'Value':>12s} {'vs Proposed':>12s}")
print("-" * 90)
for name in ["Base", "Proposed", "LAAKA"]:
    for mk, ml in [("cpu", "CPU(s)"), ("energy", "Energy(J)")]:
        v1 = ms_opt1[name][mk] if name in ms_opt1 else 0
        v2 = ms_opt2[name][mk] if name in ms_opt2 else 0
        pv1 = ms_opt1["Proposed"][mk] if "Proposed" in ms_opt1 else 0
        pv2 = ms_opt2["Proposed"][mk] if "Proposed" in ms_opt2 else 0
        if name == "Proposed":
            p1_str, p2_str = "—", "—"
        else:
            p1_str = f"{(v1-pv1)/v1*100:+.1f}%" if v1 else "N/A"
            p2_str = f"{(v2-pv2)/v2*100:+.1f}%" if v2 else "N/A"
        print(f"{name:<15s} {ml:<10s} | {v1:>12.6f} {p1_str:>12s} | {v2:>12.6f} {p2_str:>12s}")
    print("-" * 90)

print("\nPositive % = Proposed is cheaper/better")
print("Negative % = Proposed is more expensive")
print("\nDone! All charts saved to:", CHART_DIR)
