"""
compare_revised_laaka_zhou.py
Compare Revised-Anonymity (two-round) vs LAAKA vs Zhou across 3 phases.
Generates bar charts and a printed summary table.
"""
import csv, os, math, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE     = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
OUT_DIR  = os.path.join(BASE, "Results", "Charts", "Revised-vs-LAAKA-vs-Zhou")
os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────────────
def load_simple(path, id_col="Device", cpu_col="CPU_s", en_col="Energy_J"):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"id": int(r[id_col]),
                             "cpu": float(r[cpu_col]),
                             "energy": float(r[en_col])})
            except (ValueError, KeyError):
                pass
    return rows

def load_laaka(path, id_col="Device_ID", cpu_col="CPU_Time_s", en_col="Energy_J"):
    return load_simple(path, id_col, cpu_col, en_col)

def load_zhou(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"id":       int(r["Device_ID"]),
                             "cpu_auth": float(r["Avg_CPU_s"]),
                             "en_auth":  float(r["Avg_Energy_J"]),
                             "en_enroll":float(r["Enroll_Energy_J"])})
            except (ValueError, KeyError):
                pass
    return rows

def avg(lst):  return statistics.mean(lst) if lst else 0
def stddev(lst): return statistics.stdev(lst) if len(lst) > 1 else 0

# ─────────────────────────────────────────────────────────────────────────────
# Load Revised-Anonymity
# ─────────────────────────────────────────────────────────────────────────────
RA_DIR = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
ra_enroll = load_simple(os.path.join(RA_DIR, "enroll-results.csv"))
ra_auth   = load_simple(os.path.join(RA_DIR, "auth-results.csv"))
ra_keyex  = load_simple(os.path.join(RA_DIR, "keyex-results.csv"))

ra_en_enroll  = [r["energy"] for r in ra_enroll]
ra_en_auth    = [r["energy"] for r in ra_auth]
ra_en_keyex   = [r["energy"] for r in ra_keyex]
ra_en_total   = [a + k for a, k in zip(ra_en_auth, ra_en_keyex)]  # auth+keyex

ra_cpu_enroll = [r["cpu"]    for r in ra_enroll]
ra_cpu_auth   = [r["cpu"]    for r in ra_auth]
ra_cpu_keyex  = [r["cpu"]    for r in ra_keyex]
ra_cpu_total  = [a + k for a, k in zip(ra_cpu_auth, ra_cpu_keyex)]

# ─────────────────────────────────────────────────────────────────────────────
# Load LAAKA
# ─────────────────────────────────────────────────────────────────────────────
LAAKA_DIR = os.path.join(BASE, "Results", "CSV-Data", "LAAKA")
lk_enroll = load_laaka(os.path.join(LAAKA_DIR, "enroll-results.csv"))
lk_auth   = load_laaka(os.path.join(LAAKA_DIR, "auth-results.csv"))
lk_keyex  = load_laaka(os.path.join(LAAKA_DIR, "keyex-results.csv"))

lk_en_enroll = [r["energy"] for r in lk_enroll]
lk_en_auth   = [r["energy"] for r in lk_auth]
lk_en_keyex  = [r["energy"] for r in lk_keyex]
lk_en_total  = [a + k for a, k in zip(
    sorted([r["energy"] for r in lk_auth],   key=lambda _: 1),
    sorted([r["energy"] for r in lk_keyex],  key=lambda _: 1))]

lk_cpu_enroll = [r["cpu"] for r in lk_enroll]
lk_cpu_auth   = [r["cpu"] for r in lk_auth]
lk_cpu_keyex  = [r["cpu"] for r in lk_keyex]

# Match LAAKA auth+keyex per-device (same IDs)
lk_auth_map  = {r["id"]: r for r in lk_auth}
lk_keyex_map = {r["id"]: r for r in lk_keyex}
common_ids = sorted(set(lk_auth_map) & set(lk_keyex_map))
lk_en_total  = [lk_auth_map[i]["energy"] + lk_keyex_map[i]["energy"] for i in common_ids]
lk_cpu_total = [lk_auth_map[i]["cpu"]    + lk_keyex_map[i]["cpu"]    for i in common_ids]

# ─────────────────────────────────────────────────────────────────────────────
# Load Zhou
# ─────────────────────────────────────────────────────────────────────────────
zhou_raw     = load_zhou(os.path.join(BASE, "Zhou-Scheme", "zhou-auth-results.csv"))
zhou_en_auth = [r["en_auth"]   for r in zhou_raw]
zhou_en_enroll=[r["en_enroll"] for r in zhou_raw]
zhou_cpu_auth= [r["cpu_auth"]  for r in zhou_raw]
# Zhou has no separate keyex phase (combined in auth)

# ─────────────────────────────────────────────────────────────────────────────
# Summary statistics
# ─────────────────────────────────────────────────────────────────────────────
stats = {
    "Revised-Anonymity": {
        "enroll_en":   (avg(ra_en_enroll)*1000,   stddev(ra_en_enroll)*1000),
        "auth_en":     (avg(ra_en_auth)*1000,     stddev(ra_en_auth)*1000),
        "keyex_en":    (avg(ra_en_keyex)*1000,    stddev(ra_en_keyex)*1000),
        "total_en":    (avg(ra_en_total)*1000,    stddev(ra_en_total)*1000),
        "enroll_cpu":  (avg(ra_cpu_enroll),       stddev(ra_cpu_enroll)),
        "auth_cpu":    (avg(ra_cpu_auth),         stddev(ra_cpu_auth)),
        "keyex_cpu":   (avg(ra_cpu_keyex),        stddev(ra_cpu_keyex)),
        "total_cpu":   (avg(ra_cpu_total),        stddev(ra_cpu_total)),
    },
    "LAAKA": {
        "enroll_en":   (avg(lk_en_enroll)*1000,   stddev(lk_en_enroll)*1000),
        "auth_en":     (avg(lk_en_auth)*1000,     stddev(lk_en_auth)*1000),
        "keyex_en":    (avg(lk_en_keyex)*1000,    stddev(lk_en_keyex)*1000),
        "total_en":    (avg(lk_en_total)*1000,    stddev(lk_en_total)*1000),
        "enroll_cpu":  (avg(lk_cpu_enroll),       stddev(lk_cpu_enroll)),
        "auth_cpu":    (avg(lk_cpu_auth),         stddev(lk_cpu_auth)),
        "keyex_cpu":   (avg(lk_cpu_keyex),        stddev(lk_cpu_keyex)),
        "total_cpu":   (avg(lk_cpu_total),        stddev(lk_cpu_total)),
    },
    "Zhou": {
        "enroll_en":   (avg(zhou_en_enroll)*1000,  stddev(zhou_en_enroll)*1000),
        "auth_en":     (avg(zhou_en_auth)*1000,    stddev(zhou_en_auth)*1000),
        "keyex_en":    (0, 0),           # Zhou has no separate keyex measurement
        "total_en":    (avg(zhou_en_auth)*1000,    stddev(zhou_en_auth)*1000),
        "enroll_cpu":  (0, 0),
        "auth_cpu":    (avg(zhou_cpu_auth),        stddev(zhou_cpu_auth)),
        "keyex_cpu":   (0, 0),
        "total_cpu":   (avg(zhou_cpu_auth),        stddev(zhou_cpu_auth)),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Print summary table
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*90)
print("COMPARISON: Revised-Anonymity vs LAAKA vs Zhou")
print("="*90)
print(f"\n{'Phase':<20} {'Scheme':<22} {'Avg Energy (mJ)':>16} {'Std (mJ)':>10} {'Avg CPU (s)':>12} {'Std (s)':>9}")
print("-"*90)

phases = [
    ("Enrollment",     "enroll_en", "enroll_cpu"),
    ("Authentication", "auth_en",   "auth_cpu"),
    ("Key Exchange",   "keyex_en",  "keyex_cpu"),
    ("Auth+KeyEx",     "total_en",  "total_cpu"),
]
schemes = ["Revised-Anonymity", "LAAKA", "Zhou"]

for phase_name, en_key, cpu_key in phases:
    first = True
    for scheme in schemes:
        en_avg, en_std   = stats[scheme][en_key]
        cpu_avg, cpu_std = stats[scheme][cpu_key]
        label = phase_name if first else ""
        note = " (combined)" if scheme == "Zhou" and phase_name == "Key Exchange" else ""
        print(f"  {label:<18} {scheme+note:<22} {en_avg:>16.3f} {en_std:>10.3f} {cpu_avg:>12.4f} {cpu_std:>9.4f}")
        first = False
    print()

# ─────────────────────────────────────────────────────────────────────────────
# Chart helpers
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    "Revised-Anonymity": "#2196F3",
    "LAAKA":             "#FF9800",
    "Zhou":              "#4CAF50",
}

def bar_chart(title, ylabel, data, filename):
    """data = list of (label, value, err)"""
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [d[0] for d in data]
    vals   = [d[1] for d in data]
    errs   = [d[2] for d in data]
    colors = [COLORS.get(l.split("\n")[0], "#9E9E9E") for l in labels]
    x = np.arange(len(labels))
    bars = ax.bar(x, vals, width=0.55, color=colors, edgecolor="black",
                  linewidth=0.8, yerr=errs, capsize=5, error_kw={"elinewidth":1.2})
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(errs)*0.05,
                f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, filename)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {os.path.basename(path)}")
    return path

def grouped_bar(title, ylabel, groups, group_labels, scheme_labels, filename):
    """groups = {scheme: [val_per_group]}"""
    n_groups  = len(group_labels)
    n_schemes = len(scheme_labels)
    width     = 0.25
    x         = np.arange(n_groups)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, scheme in enumerate(scheme_labels):
        vals = [groups[scheme][j][0] for j in range(n_groups)]
        errs = [groups[scheme][j][1] for j in range(n_groups)]
        offset = (i - n_schemes / 2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width, label=scheme,
                      color=COLORS[scheme], edgecolor="black",
                      linewidth=0.8, yerr=errs, capsize=4,
                      error_kw={"elinewidth":1.0})
    ax.set_xticks(x)
    ax.set_xticklabels(group_labels, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, filename)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {os.path.basename(path)}")
    return path

# ─────────────────────────────────────────────────────────────────────────────
# Generate charts
# ─────────────────────────────────────────────────────────────────────────────
print("\nGenerating charts...")

# 1. Enrollment energy comparison
bar_chart(
    "Enrollment Phase — Energy Consumption",
    "Energy (mJ)",
    [("Revised-\nAnonymity", *stats["Revised-Anonymity"]["enroll_en"]),
     ("LAAKA",               *stats["LAAKA"]["enroll_en"]),
     ("Zhou",                *stats["Zhou"]["enroll_en"])],
    "01_enrollment_energy.png"
)

# 2. Authentication (Round 1) energy
bar_chart(
    "Authentication Phase (Round 1) — Energy Consumption",
    "Energy (mJ)",
    [("Revised-\nAnonymity", *stats["Revised-Anonymity"]["auth_en"]),
     ("LAAKA",               *stats["LAAKA"]["auth_en"]),
     ("Zhou\n(Auth+KeyEx)", *stats["Zhou"]["auth_en"])],
    "02_auth_energy.png"
)

# 3. Key Exchange (Round 2) energy — only RA and LAAKA have separate keyex
bar_chart(
    "Key Exchange Phase (Round 2) — Energy Consumption",
    "Energy (mJ)",
    [("Revised-\nAnonymity", *stats["Revised-Anonymity"]["keyex_en"]),
     ("LAAKA",               *stats["LAAKA"]["keyex_en"])],
    "03_keyex_energy.png"
)

# 4. Combined Auth+KeyEx energy (all 3 schemes — apples-to-apples)
bar_chart(
    "Auth + Key Exchange (Combined) — Energy Consumption",
    "Energy (mJ)",
    [("Revised-\nAnonymity", *stats["Revised-Anonymity"]["total_en"]),
     ("LAAKA",               *stats["LAAKA"]["total_en"]),
     ("Zhou",                *stats["Zhou"]["total_en"])],
    "04_total_authkeyex_energy.png"
)

# 5. Grouped: all phases energy side-by-side
grouped_bar(
    "Energy Consumption by Phase — All Schemes",
    "Energy (mJ)",
    groups={
        "Revised-Anonymity": [stats["Revised-Anonymity"]["enroll_en"],
                              stats["Revised-Anonymity"]["auth_en"],
                              stats["Revised-Anonymity"]["keyex_en"],
                              stats["Revised-Anonymity"]["total_en"]],
        "LAAKA":             [stats["LAAKA"]["enroll_en"],
                              stats["LAAKA"]["auth_en"],
                              stats["LAAKA"]["keyex_en"],
                              stats["LAAKA"]["total_en"]],
        "Zhou":              [stats["Zhou"]["enroll_en"],
                              stats["Zhou"]["auth_en"],
                              (0, 0),
                              stats["Zhou"]["total_en"]],
    },
    group_labels=["Enrollment", "Auth\n(Round 1)", "Key Exchange\n(Round 2)", "Auth+KeyEx\n(Total)"],
    scheme_labels=["Revised-Anonymity", "LAAKA", "Zhou"],
    filename="05_grouped_energy_all_phases.png"
)

# 6. Grouped: CPU time comparison
grouped_bar(
    "CPU Time by Phase — All Schemes",
    "CPU Time (s)",
    groups={
        "Revised-Anonymity": [stats["Revised-Anonymity"]["enroll_cpu"],
                              stats["Revised-Anonymity"]["auth_cpu"],
                              stats["Revised-Anonymity"]["keyex_cpu"],
                              stats["Revised-Anonymity"]["total_cpu"]],
        "LAAKA":             [stats["LAAKA"]["enroll_cpu"],
                              stats["LAAKA"]["auth_cpu"],
                              stats["LAAKA"]["keyex_cpu"],
                              stats["LAAKA"]["total_cpu"]],
        "Zhou":              [stats["Zhou"]["enroll_cpu"],
                              stats["Zhou"]["auth_cpu"],
                              (0, 0),
                              stats["Zhou"]["total_cpu"]],
    },
    group_labels=["Enrollment", "Auth\n(Round 1)", "Key Exchange\n(Round 2)", "Auth+KeyEx\n(Total)"],
    scheme_labels=["Revised-Anonymity", "LAAKA", "Zhou"],
    filename="06_grouped_cpu_all_phases.png"
)

# 7. Per-device scatter: Auth+KeyEx energy (RA vs LAAKA)
fig, ax = plt.subplots(figsize=(10, 5))
ra_ids = [r["id"] for r in ra_auth]
ax.plot(ra_ids,
        [a+k for a, k in zip([r["energy"]*1000 for r in ra_auth],
                              [r["energy"]*1000 for r in ra_keyex])],
        "o-", color=COLORS["Revised-Anonymity"], label="Revised-Anonymity (Auth+KeyEx)",
        markersize=5, linewidth=1.5)
ax.plot(sorted(common_ids),
        [lk_en_total[i] * 1000 for i in range(len(common_ids))],
        "s--", color=COLORS["LAAKA"], label="LAAKA (Auth+KeyEx)",
        markersize=5, linewidth=1.5)
ax.plot([r["id"] for r in zhou_raw],
        [r["en_auth"]*1000 for r in zhou_raw],
        "^:", color=COLORS["Zhou"], label="Zhou (Auth, combined)",
        markersize=5, linewidth=1.5)
ax.set_xlabel("Device ID", fontsize=11)
ax.set_ylabel("Energy (mJ)", fontsize=11)
ax.set_title("Per-Device Auth+KeyEx Energy — Revised-Anonymity vs LAAKA vs Zhou",
             fontsize=12, fontweight="bold")
ax.legend(fontsize=10)
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()
path = os.path.join(OUT_DIR, "07_per_device_authkeyex_energy.png")
plt.savefig(path, dpi=150)
plt.close()
print(f"  Saved: {os.path.basename(path)}")

print(f"\nAll charts saved to: {OUT_DIR}")

# ─────────────────────────────────────────────────────────────────────────────
# Save comparison CSV
# ─────────────────────────────────────────────────────────────────────────────
cmp_path = os.path.join(OUT_DIR, "comparison_summary.csv")
with open(cmp_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Scheme","Phase","Avg_Energy_mJ","Std_Energy_mJ","Avg_CPU_s","Std_CPU_s"])
    for scheme in ["Revised-Anonymity","LAAKA","Zhou"]:
        for phase_name, en_key, cpu_key in phases:
            en_a, en_s   = stats[scheme][en_key]
            cpu_a, cpu_s = stats[scheme][cpu_key]
            w.writerow([scheme, phase_name,
                        f"{en_a:.4f}", f"{en_s:.4f}",
                        f"{cpu_a:.6f}", f"{cpu_s:.6f}"])
print(f"Comparison CSV: {cmp_path}")
print("\nDone!")
