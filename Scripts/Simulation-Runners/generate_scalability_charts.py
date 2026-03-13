#!/usr/bin/env python3
"""Generate scalability comparison charts (1, 5, 20 devices) with theoretical analysis."""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch

# ── paths ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "..", "Results", "CSV-Data", "scalability-results.csv")
OUT_DIR  = os.path.join(BASE_DIR, "..", "..", "Results", "Charts", "Scalability")
os.makedirs(OUT_DIR, exist_ok=True)

# ── style ──
SCHEME_COLORS = {
    "Base-Scheme":     "#2196F3",
    "LAAKA":           "#FF9800",
    "Proposed-Scheme": "#4CAF50",
}
SCHEME_LABELS = {
    "Base-Scheme":     "Base Scheme",
    "LAAKA":           "LAAKA",
    "Proposed-Scheme": "Proposed Scheme",
}
SCHEMES = ["Base-Scheme", "LAAKA", "Proposed-Scheme"]
NODE_COUNTS = [1, 5, 20]
PHASES = ["Enrollment", "Authentication", "Key Exchange"]

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "figure.dpi": 150,
})


# ── load data ──
def load_data():
    data = {}
    with open(CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["Scheme"], int(row["Num_Devices"]), row["Phase"])
            data[key] = {
                "samples":   int(row["Num_Samples"]),
                "cpu_s":     float(row["Avg_CPU_s"]),
                "cpu_std":   float(row["StdDev_CPU_s"]),
                "energy_j":  float(row["Avg_Energy_J"]),
                "energy_std":float(row["StdDev_Energy_J"]),
                "cpu_only_j":float(row["Avg_CPU_Only_Energy_J"]),
            }
    return data


def get_val(data, scheme, nodes, phase, metric, default=0.0):
    key = (scheme, nodes, phase)
    if key in data:
        return data[key].get(metric, default)
    return default


# ── Chart 1: Per-Phase Energy vs Node Count ──
def chart_per_phase_energy(data):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=False)
    fig.suptitle("Energy Consumption vs. Number of Devices (Per Phase)", fontweight="bold", y=1.02)

    for ax, phase in zip(axes, PHASES):
        x = np.arange(len(NODE_COUNTS))
        width = 0.25
        for i, scheme in enumerate(SCHEMES):
            vals = [get_val(data, scheme, n, phase, "energy_j") * 1000 for n in NODE_COUNTS]
            stds = [get_val(data, scheme, n, phase, "energy_std") * 1000 for n in NODE_COUNTS]
            # Mark missing data
            colors = []
            for v in vals:
                colors.append(SCHEME_COLORS[scheme] if v > 0 else "#CCCCCC")
            bars = ax.bar(x + (i - 1) * width, vals, width, yerr=stds,
                          label=SCHEME_LABELS[scheme], color=colors,
                          edgecolor="white", linewidth=0.5, capsize=3)
            # Annotate missing
            for j, v in enumerate(vals):
                if v == 0:
                    ax.annotate("N/A", (x[j] + (i - 1) * width, 0.5),
                                ha="center", va="bottom", fontsize=8, color="red", fontweight="bold")
        ax.set_title(phase, fontweight="bold")
        ax.set_xlabel("Number of Devices")
        ax.set_ylabel("Energy (mJ)" if ax == axes[0] else "")
        ax.set_xticks(x)
        ax.set_xticklabels([str(n) for n in NODE_COUNTS])
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)

    axes[0].legend(loc="upper left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "Scalability-01-Energy-Per-Phase.png"),
                bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("  [1] Energy per phase chart saved.")


# ── Chart 2: Per-Phase CPU Time vs Node Count ──
def chart_per_phase_cpu(data):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=False)
    fig.suptitle("CPU Time vs. Number of Devices (Per Phase)", fontweight="bold", y=1.02)

    for ax, phase in zip(axes, PHASES):
        x = np.arange(len(NODE_COUNTS))
        width = 0.25
        for i, scheme in enumerate(SCHEMES):
            vals = [get_val(data, scheme, n, phase, "cpu_s") * 1000 for n in NODE_COUNTS]
            stds = [get_val(data, scheme, n, phase, "cpu_std") * 1000 for n in NODE_COUNTS]
            colors = [SCHEME_COLORS[scheme] if v > 0 else "#CCCCCC" for v in vals]
            bars = ax.bar(x + (i - 1) * width, vals, width, yerr=stds,
                          label=SCHEME_LABELS[scheme], color=colors,
                          edgecolor="white", linewidth=0.5, capsize=3)
            for j, v in enumerate(vals):
                if v == 0:
                    ax.annotate("N/A", (x[j] + (i - 1) * width, 0.5),
                                ha="center", va="bottom", fontsize=8, color="red", fontweight="bold")
        ax.set_title(phase, fontweight="bold")
        ax.set_xlabel("Number of Devices")
        ax.set_ylabel("CPU Time (ms)" if ax == axes[0] else "")
        ax.set_xticks(x)
        ax.set_xticklabels([str(n) for n in NODE_COUNTS])
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)

    axes[0].legend(loc="upper left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "Scalability-02-CPU-Time-Per-Phase.png"),
                bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("  [2] CPU time per phase chart saved.")


# ── Chart 3: Total Protocol Cost (stacked) vs Node Count ──
def chart_total_stacked(data):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Total Protocol Energy by Phase (Stacked) vs. Number of Devices",
                 fontweight="bold", y=1.02)

    phase_colors = {"Enrollment": "#1565C0", "Authentication": "#43A047", "Key Exchange": "#FB8C00"}

    for ax, scheme in zip(axes, SCHEMES):
        x = np.arange(len(NODE_COUNTS))
        bottom = np.zeros(len(NODE_COUNTS))
        for phase in PHASES:
            vals = np.array([get_val(data, scheme, n, phase, "energy_j") * 1000
                             for n in NODE_COUNTS])
            ax.bar(x, vals, 0.5, bottom=bottom, label=phase,
                   color=phase_colors[phase], edgecolor="white", linewidth=0.5)
            # Value labels
            for j in range(len(NODE_COUNTS)):
                if vals[j] > 0:
                    ax.text(x[j], bottom[j] + vals[j] / 2, f"{vals[j]:.1f}",
                            ha="center", va="center", fontsize=7, color="white", fontweight="bold")
            bottom += vals

        # Total labels on top
        for j in range(len(NODE_COUNTS)):
            ax.text(x[j], bottom[j] + 1, f"{bottom[j]:.1f}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold")

        ax.set_title(SCHEME_LABELS[scheme], fontweight="bold")
        ax.set_xlabel("Number of Devices")
        ax.set_ylabel("Total Energy (mJ)" if ax == axes[0] else "")
        ax.set_xticks(x)
        ax.set_xticklabels([str(n) for n in NODE_COUNTS])
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)

    axes[0].legend(loc="upper left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "Scalability-03-Total-Stacked-Energy.png"),
                bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("  [3] Total stacked energy chart saved.")


# ── Chart 4: CPU Time with Theoretical Analysis ──
def chart_cpu_with_theory(data):
    """CPU time comparison + theoretical computation analysis table below."""

    fig = plt.figure(figsize=(16, 14))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.1, 1], hspace=0.35)

    # ── Top: CPU Time grouped bar for Auth+KeyEx (most interesting) ──
    ax_top = fig.add_subplot(gs[0])

    # Show Auth+KeyEx combined CPU time across node counts
    x = np.arange(len(NODE_COUNTS))
    width = 0.25
    for i, scheme in enumerate(SCHEMES):
        auth_vals = [get_val(data, scheme, n, "Authentication", "cpu_s") * 1000 for n in NODE_COUNTS]
        kex_vals  = [get_val(data, scheme, n, "Key Exchange", "cpu_s") * 1000 for n in NODE_COUNTS]
        combined  = [a + k for a, k in zip(auth_vals, kex_vals)]
        bars = ax_top.bar(x + (i - 1) * width, combined, width,
                          label=SCHEME_LABELS[scheme], color=SCHEME_COLORS[scheme],
                          edgecolor="white", linewidth=0.5)
        for j, v in enumerate(combined):
            if v > 0:
                ax_top.text(x[j] + (i - 1) * width, v + 2, f"{v:.1f}",
                            ha="center", va="bottom", fontsize=8, fontweight="bold")
            else:
                ax_top.annotate("N/A", (x[j] + (i - 1) * width, 2),
                                ha="center", va="bottom", fontsize=9, color="red", fontweight="bold")

    ax_top.set_title("Authentication + Key Exchange: CPU Time vs. Number of Devices",
                     fontweight="bold", fontsize=14)
    ax_top.set_xlabel("Number of Devices")
    ax_top.set_ylabel("CPU Time (ms)")
    ax_top.set_xticks(x)
    ax_top.set_xticklabels([str(n) for n in NODE_COUNTS])
    ax_top.legend(loc="upper left", framealpha=0.9)
    ax_top.grid(axis="y", alpha=0.3)
    ax_top.set_axisbelow(True)

    # ── Bottom: Theoretical Computation Cost Table ──
    ax_bot = fig.add_subplot(gs[1])
    ax_bot.axis("off")
    ax_bot.set_title("Theoretical Computation Cost Analysis (Device Side, Per Protocol Run)",
                     fontweight="bold", fontsize=13, pad=15)

    # Table data
    col_labels = ["Operation", "Base Scheme", "LAAKA", "Proposed Scheme"]
    table_data = [
        # Enrollment
        ["── Enrollment ──", "", "", ""],
        ["AES-128 Encrypt",      "2", "2", "4"],
        ["AES-128 Decrypt",      "1", "5", "0"],
        ["SHA-256 Hash",         "0", "0", "1"],
        ["PUF Operations",       "2", "0", "2"],
        ["CoAP Round-Trips",     "2", "1", "2"],
        # Auth + Key Exchange
        ["── Auth + Key Exchange ──", "", "", ""],
        ["AES-128 Encrypt",      "0", "1", "1"],
        ["AES-128 Decrypt",      "0", "0", "0"],
        ["SHA-256 Hash",         "5", "8", "6"],
        ["PUF Operations",       "2", "0", "2"],
        ["XOR (16+ byte blocks)","2", "2", "2"],
        ["CoAP Messages",        "1", "3", "2"],
        # Totals
        ["── Total Operations ──", "", "", ""],
        ["Total AES",            "3", "8", "5"],
        ["Total SHA-256",        "5", "8", "7"],
        ["Total PUF",            "4", "0", "4"],
        ["Total CoAP",           "3", "4", "4"],
    ]

    table = ax_bot.table(cellText=table_data, colLabels=col_labels,
                         loc="center", cellLoc="center",
                         colWidths=[0.30, 0.20, 0.20, 0.25])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.55)

    # Style header
    header_color = "#1A3C6E"
    for j in range(len(col_labels)):
        cell = table[0, j]
        cell.set_facecolor(header_color)
        cell.set_text_props(color="white", fontweight="bold")

    # Style section headers
    section_rows = [1, 7, 14]  # 0-indexed in table_data (add 1 for header)
    for r in section_rows:
        for j in range(len(col_labels)):
            cell = table[r + 1, j]
            cell.set_facecolor("#E3F2FD")
            cell.set_text_props(fontweight="bold")
            if j == 0:
                cell.set_text_props(fontweight="bold", ha="left")

    # Proposed scheme column highlight
    for r in range(len(table_data)):
        cell = table[r + 1, 3]
        if r not in section_rows:
            cell.set_facecolor("#E8F5E9")

    # Add notes below table
    note_text = (
        "Notes: AES-128 ≈ 0.005 ms/block, SHA-256 ≈ 0.008 ms/block, PUF ≈ 0.003 ms (simulated) on Cooja mote.\n"
        "LAAKA: No PUF operations; relies on 8 SHA-256 hashes + 8 AES blocks for stronger symmetric security.\n"
        "Proposed: Adds anonymity via extra AES + SHA-256 while maintaining PUF-based device binding.\n"
        "Enrollment CPU time (~10s) dominated by RPL network formation + CoAP setup, not crypto (crypto < 1ms)."
    )
    ax_bot.text(0.5, -0.05, note_text, transform=ax_bot.transAxes,
                ha="center", va="top", fontsize=9, style="italic",
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFF8E1", alpha=0.8))

    fig.savefig(os.path.join(OUT_DIR, "Scalability-04-CPU-Time-Theoretical-Analysis.png"),
                bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("  [4] CPU time + theoretical analysis chart saved.")


# ── Chart 5: Computation-Only Energy (no radio) ──
def chart_computation_energy(data):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=False)
    fig.suptitle("Computation-Only Energy vs. Number of Devices (Excluding Radio)",
                 fontweight="bold", y=1.02)

    for ax, phase in zip(axes, PHASES):
        x = np.arange(len(NODE_COUNTS))
        width = 0.25
        for i, scheme in enumerate(SCHEMES):
            vals = [get_val(data, scheme, n, phase, "cpu_only_j") * 1000 for n in NODE_COUNTS]
            colors = [SCHEME_COLORS[scheme] if v > 0 else "#CCCCCC" for v in vals]
            bars = ax.bar(x + (i - 1) * width, vals, width,
                          label=SCHEME_LABELS[scheme], color=colors,
                          edgecolor="white", linewidth=0.5)
            for j, v in enumerate(vals):
                if v > 0:
                    ax.text(x[j] + (i - 1) * width, v + 0.001, f"{v:.3f}",
                            ha="center", va="bottom", fontsize=7, rotation=45)
                else:
                    ax.annotate("N/A", (x[j] + (i - 1) * width, 0.001),
                                ha="center", va="bottom", fontsize=8, color="red", fontweight="bold")

        ax.set_title(phase, fontweight="bold")
        ax.set_xlabel("Number of Devices")
        ax.set_ylabel("CPU-Only Energy (mJ)" if ax == axes[0] else "")
        ax.set_xticks(x)
        ax.set_xticklabels([str(n) for n in NODE_COUNTS])
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)

    axes[0].legend(loc="upper left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "Scalability-05-Computation-Only-Energy.png"),
                bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("  [5] Computation-only energy chart saved.")


# ── Chart 6: Scalability summary table ──
def chart_summary_table(data):
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.axis("off")
    ax.set_title("Scalability Comparison Summary — All Schemes, All Phases",
                 fontweight="bold", fontsize=14, pad=20)

    col_labels = ["Scheme", "Devices", "Enroll (mJ)", "Auth (mJ)", "KeyEx (mJ)",
                  "Total (mJ)", "Enroll CPU (ms)", "Auth CPU (ms)", "KeyEx CPU (ms)"]

    rows = []
    for scheme in SCHEMES:
        for n in NODE_COUNTS:
            e_enr = get_val(data, scheme, n, "Enrollment", "energy_j") * 1000
            e_auth = get_val(data, scheme, n, "Authentication", "energy_j") * 1000
            e_kex = get_val(data, scheme, n, "Key Exchange", "energy_j") * 1000
            total = e_enr + e_auth + e_kex
            c_enr = get_val(data, scheme, n, "Enrollment", "cpu_s") * 1000
            c_auth = get_val(data, scheme, n, "Authentication", "cpu_s") * 1000
            c_kex = get_val(data, scheme, n, "Key Exchange", "cpu_s") * 1000

            def fmt(v):
                return f"{v:.2f}" if v > 0 else "N/A"

            rows.append([
                SCHEME_LABELS[scheme], str(n),
                fmt(e_enr), fmt(e_auth), fmt(e_kex), fmt(total),
                fmt(c_enr), fmt(c_auth), fmt(c_kex),
            ])

    table = ax.table(cellText=rows, colLabels=col_labels,
                     loc="center", cellLoc="center",
                     colWidths=[0.14, 0.07, 0.10, 0.10, 0.10, 0.10, 0.11, 0.11, 0.11])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.6)

    # Header style
    header_color = "#1A3C6E"
    for j in range(len(col_labels)):
        cell = table[0, j]
        cell.set_facecolor(header_color)
        cell.set_text_props(color="white", fontweight="bold")

    # Row coloring
    for r in range(len(rows)):
        scheme_name = rows[r][0]
        if scheme_name == "Proposed Scheme":
            bg = "#E8F5E9"
        elif scheme_name == "Base Scheme":
            bg = "#E3F2FD"
        else:
            bg = "#FFF3E0"
        for j in range(len(col_labels)):
            table[r + 1, j].set_facecolor(bg)
        # Highlight N/A
        for j in range(len(col_labels)):
            if rows[r][j] == "N/A":
                table[r + 1, j].set_text_props(color="red", fontweight="bold")

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "Scalability-06-Summary-Table.png"),
                bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("  [6] Summary table chart saved.")


# ── Main ──
if __name__ == "__main__":
    print(f"Loading data from: {CSV_PATH}")
    data = load_data()
    print(f"  Loaded {len(data)} rows.\n")
    print("Generating charts...")
    chart_per_phase_energy(data)
    chart_per_phase_cpu(data)
    chart_total_stacked(data)
    chart_cpu_with_theory(data)
    chart_computation_energy(data)
    chart_summary_table(data)
    print(f"\nAll charts saved to: {OUT_DIR}")
