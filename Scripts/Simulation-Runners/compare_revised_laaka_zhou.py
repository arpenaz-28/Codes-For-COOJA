"""
compare_revised_laaka_zhou.py
Compare Revised-Anonymity (two-round) vs LAAKA vs Zhou across 3 phases.
Error bars = 95% Confidence Interval (1.96 * std / sqrt(n))
"""
import csv, os, math, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
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
                rows.append({"id":        int(r["Device_ID"]),
                             "cpu_auth":  float(r["Avg_CPU_s"]),
                             "en_auth":   float(r["Avg_Energy_J"]),
                             "en_enroll": float(r["Enroll_Energy_J"])})
            except (ValueError, KeyError):
                pass
    return rows

def avg(lst):    return statistics.mean(lst) if lst else 0
def stddev(lst): return statistics.stdev(lst) if len(lst) > 1 else 0
def ci95(lst):
    """95% Confidence Interval half-width = 1.96 * std / sqrt(n)"""
    n = len(lst)
    if n < 2: return 0
    return 1.96 * statistics.stdev(lst) / math.sqrt(n)

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
ra_en_total   = [a + k for a, k in zip(ra_en_auth, ra_en_keyex)]

ra_cpu_enroll = [r["cpu"] for r in ra_enroll]
ra_cpu_auth   = [r["cpu"] for r in ra_auth]
ra_cpu_keyex  = [r["cpu"] for r in ra_keyex]
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

lk_auth_map  = {r["id"]: r for r in lk_auth}
lk_keyex_map = {r["id"]: r for r in lk_keyex}
common_ids   = sorted(set(lk_auth_map) & set(lk_keyex_map))
lk_en_total  = [lk_auth_map[i]["energy"] + lk_keyex_map[i]["energy"] for i in common_ids]
lk_cpu_total = [lk_auth_map[i]["cpu"]    + lk_keyex_map[i]["cpu"]    for i in common_ids]

lk_cpu_enroll = [r["cpu"] for r in lk_enroll]
lk_cpu_auth   = [r["cpu"] for r in lk_auth]
lk_cpu_keyex  = [r["cpu"] for r in lk_keyex]

# ─────────────────────────────────────────────────────────────────────────────
# Load Zhou
# ─────────────────────────────────────────────────────────────────────────────
zhou_raw      = load_zhou(os.path.join(BASE, "Zhou-Scheme", "zhou-auth-results.csv"))
zhou_en_auth  = [r["en_auth"]   for r in zhou_raw]
zhou_en_enroll= [r["en_enroll"] for r in zhou_raw]
zhou_cpu_auth = [r["cpu_auth"]  for r in zhou_raw]

# ─────────────────────────────────────────────────────────────────────────────
# Summary statistics  (mean, 95% CI)
# ─────────────────────────────────────────────────────────────────────────────
stats = {
    "Revised-Anonymity": {
        "enroll_en":  (avg(ra_en_enroll)*1000,  ci95(ra_en_enroll)*1000,  len(ra_en_enroll)),
        "auth_en":    (avg(ra_en_auth)*1000,    ci95(ra_en_auth)*1000,    len(ra_en_auth)),
        "keyex_en":   (avg(ra_en_keyex)*1000,   ci95(ra_en_keyex)*1000,   len(ra_en_keyex)),
        "total_en":   (avg(ra_en_total)*1000,   ci95(ra_en_total)*1000,   len(ra_en_total)),
        "enroll_cpu": (avg(ra_cpu_enroll),      ci95(ra_cpu_enroll),      len(ra_cpu_enroll)),
        "auth_cpu":   (avg(ra_cpu_auth),        ci95(ra_cpu_auth),        len(ra_cpu_auth)),
        "keyex_cpu":  (avg(ra_cpu_keyex),       ci95(ra_cpu_keyex),       len(ra_cpu_keyex)),
        "total_cpu":  (avg(ra_cpu_total),       ci95(ra_cpu_total),       len(ra_cpu_total)),
    },
    "LAAKA": {
        "enroll_en":  (avg(lk_en_enroll)*1000,  ci95(lk_en_enroll)*1000,  len(lk_en_enroll)),
        "auth_en":    (avg(lk_en_auth)*1000,    ci95(lk_en_auth)*1000,    len(lk_en_auth)),
        "keyex_en":   (avg(lk_en_keyex)*1000,   ci95(lk_en_keyex)*1000,   len(lk_en_keyex)),
        "total_en":   (avg(lk_en_total)*1000,   ci95(lk_en_total)*1000,   len(lk_en_total)),
        "enroll_cpu": (avg(lk_cpu_enroll),      ci95(lk_cpu_enroll),      len(lk_cpu_enroll)),
        "auth_cpu":   (avg(lk_cpu_auth),        ci95(lk_cpu_auth),        len(lk_cpu_auth)),
        "keyex_cpu":  (avg(lk_cpu_keyex),       ci95(lk_cpu_keyex),       len(lk_cpu_keyex)),
        "total_cpu":  (avg(lk_cpu_total),       ci95(lk_cpu_total),       len(lk_cpu_total)),
    },
    "Zhou": {
        "enroll_en":  (avg(zhou_en_enroll)*1000, ci95(zhou_en_enroll)*1000, len(zhou_en_enroll)),
        "auth_en":    (avg(zhou_en_auth)*1000,   ci95(zhou_en_auth)*1000,   len(zhou_en_auth)),
        "keyex_en":   (0, 0, 0),
        "total_en":   (avg(zhou_en_auth)*1000,   ci95(zhou_en_auth)*1000,   len(zhou_en_auth)),
        "enroll_cpu": (0, 0, 0),
        "auth_cpu":   (avg(zhou_cpu_auth),       ci95(zhou_cpu_auth),       len(zhou_cpu_auth)),
        "keyex_cpu":  (0, 0, 0),
        "total_cpu":  (avg(zhou_cpu_auth),       ci95(zhou_cpu_auth),       len(zhou_cpu_auth)),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Print summary table
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*100)
print("COMPARISON: Revised-Anonymity vs LAAKA vs Zhou  (mean ± 95% CI)")
print("="*100)
print(f"\n{'Phase':<20} {'Scheme':<22} {'Mean Energy (mJ)':>18} {'95% CI (mJ)':>12} "
      f"{'Mean CPU (s)':>14} {'95% CI (s)':>11} {'n':>4}")
print("-"*100)

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
        en_m, en_ci, en_n   = stats[scheme][en_key]
        cpu_m, cpu_ci, cpu_n = stats[scheme][cpu_key]
        label = phase_name if first else ""
        note  = " (combined)" if scheme == "Zhou" and phase_name == "Key Exchange" else ""
        print(f"  {label:<18} {scheme+note:<22} {en_m:>18.3f} {en_ci:>12.3f} "
              f"{cpu_m:>14.4f} {cpu_ci:>11.4f} {en_n:>4}")
        first = False
    print()

# ─────────────────────────────────────────────────────────────────────────────
# Style constants
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    "Revised-Anonymity": "#1565C0",
    "LAAKA":             "#E65100",
    "Zhou":              "#2E7D32",
}
CI_PATCH = mpatches.Patch(facecolor="none", edgecolor="black",
                           linewidth=1.2, label="Error bars = 95% Confidence Interval")

plt.rcParams.update({
    "font.family":  "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

def apply_style(ax, title, ylabel, xlabel=None):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel(ylabel, fontsize=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, color="#cccccc")
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", labelsize=11)

def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {name}")

def n_label(n): return f"n={n}" if n > 0 else ""

# ─────────────────────────────────────────────────────────────────────────────
# Helper — single-phase bar chart (3 schemes)
# ─────────────────────────────────────────────────────────────────────────────
def bar_chart(title, ylabel, data, filename, note=None):
    """data = list of (scheme_name, display_label, mean, ci, n)"""
    fig, ax = plt.subplots(figsize=(8, 5.5))

    labels = [d[1] for d in data]
    vals   = [d[2] for d in data]
    cis    = [d[3] for d in data]
    ns     = [d[4] for d in data]
    colors = [COLORS.get(d[0], "#9E9E9E") for d in data]
    x = np.arange(len(labels))

    bars = ax.bar(x, vals, width=0.5, color=colors, edgecolor="black",
                  linewidth=0.9, yerr=cis, capsize=6,
                  error_kw={"elinewidth": 1.5, "ecolor": "#333333"})

    # Value label above bar, n= label inside bar
    top = max(v + ci for v, ci in zip(vals, cis))
    for bar, v, ci_v, n in zip(bars, vals, cis, ns):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + ci_v + top * 0.03,
                f"{v:.2f} mJ", ha="center", va="bottom", fontsize=9.5, fontweight="bold")
        if n > 0:
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() / 2,
                    n_label(n), ha="center", va="center",
                    fontsize=9, color="white", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    # Extra headroom: value label height (~fontsize pts) + CI + note line below
    ax.set_ylim(0, top * 1.35)
    # Legend in upper right — safe because ylim gives space above bars
    ax.legend(handles=[CI_PATCH], fontsize=9, loc="upper right",
              framealpha=0.9, edgecolor="#aaaaaa")
    apply_style(ax, title, ylabel)
    plt.tight_layout()
    # Note goes below the chart as a figure-level caption
    if note:
        fig.text(0.5, -0.02, note, ha="center", va="top",
                 fontsize=8, color="#555555", style="italic")
    save(fig, filename)

# ─────────────────────────────────────────────────────────────────────────────
# Helper — grouped bar chart (multiple phases × multiple schemes)
# ─────────────────────────────────────────────────────────────────────────────
def grouped_bar(title, ylabel, groups, group_labels, scheme_labels, filename, note=None):
    """groups = {scheme: [(mean, ci, n) per group]}"""
    n_groups  = len(group_labels)
    n_schemes = len(scheme_labels)
    width     = 0.22
    x         = np.arange(n_groups)

    fig, ax = plt.subplots(figsize=(12, 6.5))
    all_tops = []
    for i, scheme in enumerate(scheme_labels):
        vals = [groups[scheme][j][0] for j in range(n_groups)]
        cis  = [groups[scheme][j][1] for j in range(n_groups)]
        all_tops.extend(v + c for v, c in zip(vals, cis))
        offset = (i - n_schemes / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=scheme,
               color=COLORS[scheme], edgecolor="black", linewidth=0.7,
               yerr=cis, capsize=4,
               error_kw={"elinewidth": 1.2, "ecolor": "#333333"})

    # Set ylim with enough headroom so error bar caps never clip
    ax.set_ylim(0, max(all_tops) * 1.30)
    ax.set_xticks(x)
    ax.set_xticklabels(group_labels, fontsize=11)

    # Legend placed below the chart, outside the axes, so it never overlaps bars
    legend_handles = [mpatches.Patch(color=COLORS[s], label=s) for s in scheme_labels]
    legend_handles.append(CI_PATCH)
    ax.legend(handles=legend_handles, fontsize=9,
              loc="upper center", bbox_to_anchor=(0.5, -0.14),
              ncol=len(legend_handles), framealpha=0.9, edgecolor="#aaaaaa")

    apply_style(ax, title, ylabel)
    plt.tight_layout()
    # Note below legend
    if note:
        fig.text(0.5, -0.06, note, ha="center", va="top",
                 fontsize=8, color="#555555", style="italic")
    save(fig, filename)

# ─────────────────────────────────────────────────────────────────────────────
# Generate charts 01–06
# ─────────────────────────────────────────────────────────────────────────────
print("\nGenerating charts...")

# 1. Enrollment energy
bar_chart(
    "Enrollment Phase — Energy Consumption\n(COOJA Simulation, TelosB Motes)",
    "Mean Energy (mJ)",
    [("Revised-Anonymity", "Revised-\nAnonymity", *stats["Revised-Anonymity"]["enroll_en"]),
     ("LAAKA",             "LAAKA",               *stats["LAAKA"]["enroll_en"]),
     ("Zhou",              "Zhou",                *stats["Zhou"]["enroll_en"])],
    "01_enrollment_energy.png",
    note="* Zhou enrollment energy measured from COOJA simulation logs"
)

# 2. Authentication Round 1 energy
bar_chart(
    "Authentication Phase — Energy Consumption\n(COOJA Simulation, TelosB Motes)",
    "Mean Energy (mJ)",
    [("Revised-Anonymity", "Revised-\nAnonymity",  *stats["Revised-Anonymity"]["auth_en"]),
     ("LAAKA",             "LAAKA",                *stats["LAAKA"]["auth_en"]),
     ("Zhou",              "Zhou\n(Auth+KeyEx\ncombined)", *stats["Zhou"]["auth_en"])],
    "02_auth_energy.png",
    note="* Zhou performs Auth and Key Exchange in a single round"
)

# 3. Key Exchange energy (RA and LAAKA only)
bar_chart(
    "Key Exchange Phase — Energy Consumption\n(COOJA Simulation, TelosB Motes)",
    "Mean Energy (mJ)",
    [("Revised-Anonymity", "Revised-\nAnonymity", *stats["Revised-Anonymity"]["keyex_en"]),
     ("LAAKA",             "LAAKA",               *stats["LAAKA"]["keyex_en"])],
    "03_keyex_energy.png",
    note="* Zhou has no separate Key Exchange phase (included in Authentication)"
)

# 4. Combined Auth+KeyEx energy — apples-to-apples
bar_chart(
    "Auth + Key Exchange (Combined) — Energy Consumption\n(COOJA Simulation, TelosB Motes)",
    "Mean Energy (mJ)",
    [("Revised-Anonymity", "Revised-\nAnonymity", *stats["Revised-Anonymity"]["total_en"]),
     ("LAAKA",             "LAAKA",               *stats["LAAKA"]["total_en"]),
     ("Zhou",              "Zhou",                *stats["Zhou"]["total_en"])],
    "04_total_authkeyex_energy.png",
    note="* All schemes compared on total cost of completing authentication + session key establishment"
)

# 5. Grouped: all phases energy
grouped_bar(
    "Energy Consumption per Phase — All Schemes\n(COOJA Simulation, 20 TelosB Motes)",
    "Mean Energy (mJ)",
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
                               (0, 0, 0),
                               stats["Zhou"]["total_en"]],
    },
    group_labels=["Enrollment", "Authentication\n(Round 1)", "Key Exchange\n(Round 2)",
                  "Auth + Key Exchange\n(Combined)"],
    scheme_labels=["Revised-Anonymity", "LAAKA", "Zhou"],
    filename="05_grouped_energy_all_phases.png",
    note="* Zhou Key Exchange is included in its Authentication phase (single-round design)"
)

# 6. Grouped: CPU time
grouped_bar(
    "CPU Computation Time per Phase — All Schemes\n(COOJA Simulation, 20 TelosB Motes)",
    "Mean CPU Time (s)",
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
                               (0, 0, 0),
                               stats["Zhou"]["total_cpu"]],
    },
    group_labels=["Enrollment", "Authentication\n(Round 1)", "Key Exchange\n(Round 2)",
                  "Auth + Key Exchange\n(Combined)"],
    scheme_labels=["Revised-Anonymity", "LAAKA", "Zhou"],
    filename="06_grouped_cpu_all_phases.png",
    note="* Zhou enrollment CPU not separately recorded; Key Exchange included in Authentication"
)

# ─────────────────────────────────────────────────────────────────────────────
# Chart 07 — Per-device scatter: Auth+KeyEx energy
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 5.5))

ra_ids     = [r["id"] for r in ra_auth]
ra_ak_vals = [(a + k) * 1000 for a, k in
              zip([r["energy"] for r in ra_auth], [r["energy"] for r in ra_keyex])]
lk_ak_vals = [v * 1000 for v in lk_en_total]
zh_vals    = [r["en_auth"] * 1000 for r in zhou_raw]
zh_ids     = [r["id"] for r in zhou_raw]

ax.plot(ra_ids, ra_ak_vals, "o-",
        color=COLORS["Revised-Anonymity"], label="Revised-Anonymity  (Auth + Key Exchange)",
        markersize=6, linewidth=1.8)
ax.plot(sorted(common_ids), lk_ak_vals, "s--",
        color=COLORS["LAAKA"], label="LAAKA  (Auth + Key Exchange)",
        markersize=6, linewidth=1.8)
ax.plot(zh_ids, zh_vals, "^:",
        color=COLORS["Zhou"], label="Zhou  (Auth, combined with Key Exchange)",
        markersize=6, linewidth=1.8)

# Average reference lines
for scheme, vals, ids in [("Revised-Anonymity", ra_ak_vals, ra_ids),
                           ("LAAKA", lk_ak_vals, common_ids),
                           ("Zhou", zh_vals, zh_ids)]:
    m = statistics.mean(vals)
    ax.axhline(m, color=COLORS[scheme], linestyle=":", alpha=0.55, linewidth=1.2)
    ax.text(max(ids) + 0.3, m, f"avg={m:.1f}", fontsize=7.5,
            color=COLORS[scheme], va="center")

apply_style(ax,
    "Per-Device Auth + Key Exchange Energy — All Schemes\n(COOJA Simulation, TelosB Motes)",
    "Energy (mJ)",
    xlabel="Device ID")
ax.legend(fontsize=10, loc="upper left", framealpha=0.88, edgecolor="#aaaaaa")
ax.text(0.01, 0.01,
        "Dotted horizontal lines = per-scheme mean",
        transform=ax.transAxes, fontsize=8, va="bottom", color="#555555", style="italic")
plt.tight_layout()
save(fig, "07_per_device_authkeyex_energy.png")

# ─────────────────────────────────────────────────────────────────────────────
# Save comparison CSV  (now stores mean + 95% CI + n)
# ─────────────────────────────────────────────────────────────────────────────
cmp_path = os.path.join(OUT_DIR, "comparison_summary.csv")
with open(cmp_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Scheme", "Phase",
                "Avg_Energy_mJ", "Std_Energy_mJ",
                "CI95_Energy_mJ",
                "Avg_CPU_s", "Std_CPU_s", "CI95_CPU_s", "n"])
    for scheme in ["Revised-Anonymity", "LAAKA", "Zhou"]:
        for phase_name, en_key, cpu_key in phases:
            en_m,  en_ci,  en_n  = stats[scheme][en_key]
            cpu_m, cpu_ci, cpu_n = stats[scheme][cpu_key]
            # recompute std for CSV record
            en_lists  = {"Revised-Anonymity": {"enroll_en": ra_en_enroll, "auth_en": ra_en_auth,
                                                "keyex_en": ra_en_keyex,  "total_en": ra_en_total,
                                                "enroll_cpu": ra_cpu_enroll,"auth_cpu": ra_cpu_auth,
                                                "keyex_cpu": ra_cpu_keyex, "total_cpu": ra_cpu_total},
                         "LAAKA":             {"enroll_en": lk_en_enroll, "auth_en": lk_en_auth,
                                                "keyex_en": lk_en_keyex,  "total_en": lk_en_total,
                                                "enroll_cpu": lk_cpu_enroll,"auth_cpu": lk_cpu_auth,
                                                "keyex_cpu": lk_cpu_keyex, "total_cpu": lk_cpu_total},
                         "Zhou":              {"enroll_en": zhou_en_enroll, "auth_en": zhou_en_auth,
                                                "keyex_en": [], "total_en": zhou_en_auth,
                                                "enroll_cpu": [], "auth_cpu": zhou_cpu_auth,
                                                "keyex_cpu": [], "total_cpu": zhou_cpu_auth}}
            en_std  = stddev(en_lists[scheme][en_key])  * 1000
            cpu_std = stddev(en_lists[scheme][cpu_key])
            w.writerow([scheme, phase_name,
                        f"{en_m:.4f}",  f"{en_std:.4f}",  f"{en_ci:.4f}",
                        f"{cpu_m:.6f}", f"{cpu_std:.6f}", f"{cpu_ci:.6f}", en_n])

print(f"\nComparison CSV saved: {cmp_path}")
print(f"All charts saved to:  {OUT_DIR}")
print("Done!")
