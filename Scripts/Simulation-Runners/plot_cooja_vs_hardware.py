"""
plot_cooja_vs_hardware.py

Compare COOJA simulation results vs Hardware (RPi 3B+) implementation results
for all 3 schemes (Proposed, LAAKA, Zhou).

Metric: per-device mean total cost (Enroll + Auth + Key Exchange).

COOJA data  → Results/COOJA-Simulation/10-Seed-Comparison/{scheme}/seed_results.csv
Hardware    → Results/Hardware-Implementation/CSV-Data/{RA/LAAKA/Zhou}/...

Outputs → Results/COOJA-Simulation/10-Seed-Comparison/Charts/
  cooja_vs_hw_01_energy.png
  cooja_vs_hw_02_cpu.png
"""

import csv, math, os, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

REPO     = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
COOJA_DIR = os.path.join(REPO, "Results", "COOJA-Simulation", "10-Seed-Comparison")
HW_DIR    = os.path.join(REPO, "Results", "Hardware-Implementation", "CSV-Data")
OUT_DIR   = os.path.join(COOJA_DIR, "Charts")
os.makedirs(OUT_DIR, exist_ok=True)

_STYLE = {
    "font.family":       "Liberation Sans",
    "font.size":         14,
    "axes.titlesize":    17,
    "axes.titleweight":  "bold",
    "axes.labelsize":    16,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.7,
    "xtick.labelsize":   13,
    "ytick.labelsize":   13,
    "xtick.major.size":  0,
    "legend.fontsize":   12,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#cccccc",
    "grid.color":        "#e5e5e5",
    "grid.linewidth":    0.6,
}

C_COOJA = "#2C6FAC"   # blue
C_HW    = "#B85C2C"   # orange
H_COOJA = "///"
H_HW    = "\\\\\\"

SCHEME_ORDER  = ["Proposed", "LAAKA", "Zhou"]
SCHEME_LABELS = {"Proposed": "Proposed\n(This Work)", "LAAKA": "LAAKA", "Zhou": "Zhou"}


# ── COOJA loader ──────────────────────────────────────────────────────────────
def load_cooja_perdev(scheme):
    """Per-device mean energy+CPU per seed → list of seed-level per-device means."""
    path = os.path.join(COOJA_DIR, scheme, "seed_results.csv")
    if not os.path.isfile(path):
        return [], []
    seed_data = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seed = int(row["Seed"])
            seed_data.setdefault(seed, []).append(
                (float(row["Total_Energy_mJ"]), float(row["Total_CPU_s"]))
            )
    e_means, c_means = [], []
    for seed in sorted(seed_data):
        vals = seed_data[seed]
        e_means.append(statistics.mean(v[0] for v in vals))
        c_means.append(statistics.mean(v[1] for v in vals))
    return e_means, c_means


# ── Hardware loaders ──────────────────────────────────────────────────────────
def _read_hw_csv(path):
    """Read a hardware phase CSV.  Handles both column-name conventions:
      RA:    Device, CPU_s, Energy_J
      LAAKA: Device_ID, CPU_Time_s, Energy_J
    """
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    energy = [float(r["Energy_J"]) * 1000 for r in rows]
    # CPU column varies by scheme
    cpu_key = "CPU_s" if "CPU_s" in rows[0] else "CPU_Time_s"
    cpu = [float(r[cpu_key]) for r in rows]
    return energy, cpu


def load_hw_proposed():
    base = os.path.join(HW_DIR, "Revised-Anonymity")
    e_en, c_en = _read_hw_csv(os.path.join(base, "enroll-results.csv"))
    e_au, c_au = _read_hw_csv(os.path.join(base, "auth-results.csv"))
    e_kx, c_kx = _read_hw_csv(os.path.join(base, "keyex-results.csv"))
    n = len(e_en)
    totals_e = [e_en[i] + e_au[i] + e_kx[i] for i in range(n)]
    totals_c = [c_en[i] + c_au[i] + c_kx[i] for i in range(n)]
    return totals_e, totals_c


def load_hw_laaka():
    base = os.path.join(HW_DIR, "LAAKA")
    e_en, c_en = _read_hw_csv(os.path.join(base, "enroll-results.csv"))
    e_au, c_au = _read_hw_csv(os.path.join(base, "auth-results.csv"))
    e_kx, c_kx = _read_hw_csv(os.path.join(base, "keyex-results.csv"))
    n = len(e_en)
    totals_e = [e_en[i] + e_au[i] + e_kx[i] for i in range(n)]
    totals_c = [c_en[i] + c_au[i] + c_kx[i] for i in range(n)]
    return totals_e, totals_c


def load_hw_zhou():
    path = os.path.join(HW_DIR, "Zhou", "zhou-auth-results.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    totals_e, totals_c = [], []
    for r in rows:
        e_en = float(r[" Enroll_Energy_J"].strip()) * 1000
        e_au = float(r[" Avg_Energy_J"].strip())    * 1000
        c_en = float(r[" Enroll_CPU_s"].strip())
        c_au = float(r[" Avg_CPU_s"].strip())
        totals_e.append(e_en + e_au)
        totals_c.append(c_en + c_au)
    return totals_e, totals_c


HW_LOADERS = {
    "Proposed": load_hw_proposed,
    "LAAKA":    load_hw_laaka,
    "Zhou":     load_hw_zhou,
}


# ── Stats helper ──────────────────────────────────────────────────────────────
def agg(vals):
    n  = len(vals)
    mu = statistics.mean(vals)
    ci = 1.96 * statistics.stdev(vals) / math.sqrt(n) if n > 1 else 0.0
    return mu, ci


# ── Chart builder ─────────────────────────────────────────────────────────────
def make_chart(metric, ylabel, title, filename, fmt):
    """
    Grouped bar chart: for each scheme, one COOJA bar and one Hardware bar.
    Groups spaced by 0.5 units; bars within a group separated by 0.05.
    """
    group_width = 2.0   # distance between group centres
    bar_w       = 0.7

    cooja_vals, hw_vals = [], []    # (scheme, mu, ci)
    for scheme in SCHEME_ORDER:
        c_e, c_c = load_cooja_perdev(scheme)
        vals_c = c_e if metric == "energy" else c_c
        if vals_c:
            mu_c, ci_c = agg(vals_c)
        else:
            mu_c, ci_c = 0.0, 0.0
            print(f"  WARNING: no COOJA data for {scheme}")

        hw_e, hw_c = HW_LOADERS[scheme]()
        vals_h = hw_e if metric == "energy" else hw_c
        mu_h, ci_h = agg(vals_h)

        cooja_vals.append((scheme, mu_c, ci_c))
        hw_vals.append((scheme, mu_h, ci_h))

    # Build positions: group centre at 0, group_width, 2*group_width
    # COOJA bar left of centre, HW bar right
    group_centres = [i * group_width for i in range(len(SCHEME_ORDER))]
    offset = bar_w * 0.52
    pos_cooja = [c - offset for c in group_centres]
    pos_hw    = [c + offset for c in group_centres]

    all_vals = (
        [mu + ci for _, mu, ci in cooja_vals] +
        [mu + ci for _, mu, ci in hw_vals]
    )
    max_val = max(all_vals)

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(12, 8))
        fig.patch.set_facecolor("white")

        for i, (scheme, mu, ci) in enumerate(cooja_vals):
            ax.bar(pos_cooja[i], mu, bar_w,
                   facecolor="none", edgecolor=C_COOJA,
                   hatch=H_COOJA, linewidth=1.5,
                   yerr=ci, capsize=6,
                   error_kw={"linewidth": 1.5, "ecolor": C_COOJA})
            ax.text(pos_cooja[i], mu + ci + max_val * 0.015,
                    f"{mu:{fmt}}",
                    ha="center", va="bottom",
                    fontsize=13, fontweight="bold", color=C_COOJA)

        for i, (scheme, mu, ci) in enumerate(hw_vals):
            ax.bar(pos_hw[i], mu, bar_w,
                   facecolor="none", edgecolor=C_HW,
                   hatch=H_HW, linewidth=1.5,
                   yerr=ci, capsize=6,
                   error_kw={"linewidth": 1.5, "ecolor": C_HW})
            ax.text(pos_hw[i], mu + ci + max_val * 0.015,
                    f"{mu:{fmt}}",
                    ha="center", va="bottom",
                    fontsize=13, fontweight="bold", color=C_HW)

        # Group x-tick labels
        ax.set_xticks(group_centres)
        ax.set_xticklabels(
            [SCHEME_LABELS[s] for s in SCHEME_ORDER],
            fontsize=14, ha="center"
        )

        ax.set_ylabel(ylabel, labelpad=14, fontsize=16, fontweight="bold")
        ax.set_title(title, fontsize=17, fontweight="bold", pad=14, color="#222222")
        ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        ax.set_ylim(0, max_val * 1.28)

        # Seeds note
        cooja_seeds = {}
        for scheme in SCHEME_ORDER:
            path = os.path.join(COOJA_DIR, scheme, "seed_results.csv")
            if os.path.isfile(path):
                seeds = set()
                with open(path, newline="") as f:
                    for row in csv.DictReader(f):
                        seeds.add(row["Seed"])
                cooja_seeds[scheme] = len(seeds)
            else:
                cooja_seeds[scheme] = 0
        seed_note = ", ".join(
            f"{s}: {cooja_seeds[s]}s" for s in SCHEME_ORDER
        )

        unit = "mJ" if metric == "energy" else "s"
        legend_handles = [
            mpatches.Patch(facecolor="none", edgecolor=C_COOJA,
                           hatch=H_COOJA, linewidth=1.5,
                           label=f"COOJA Simulation ({seed_note})"),
            mpatches.Patch(facecolor="none", edgecolor=C_HW,
                           hatch=H_HW, linewidth=1.5,
                           label="Hardware (Raspberry Pi 3B+, n=20 devices)"),
        ]
        ax.legend(handles=legend_handles, loc="upper right",
                  fontsize=12, framealpha=0.9,
                  edgecolor="#dddddd", handlelength=2.2, handleheight=1.4)

        fig.tight_layout()
        out = os.path.join(OUT_DIR, filename)
        fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    print(f"  Saved: {filename}")


def main():
    make_chart(
        "energy",
        "Mean Energy per Device (mJ)\nEnroll + Auth + Key Exchange",
        "COOJA Simulation vs Hardware Implementation\nPer-Device Mean Energy Cost — All Phases",
        "cooja_vs_hw_01_energy.png",
        ".1f",
    )
    make_chart(
        "cpu",
        "Mean CPU Time per Device (s)\nEnroll + Auth + Key Exchange",
        "COOJA Simulation vs Hardware Implementation\nPer-Device Mean CPU Time — All Phases",
        "cooja_vs_hw_02_cpu.png",
        ".3f",
    )
    print(f"\nOutputs → {OUT_DIR}")


if __name__ == "__main__":
    main()
