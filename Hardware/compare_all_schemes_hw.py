#!/usr/bin/env python3
"""
compare_all_schemes_hw.py

Reads real hardware CSV results for all 3 schemes and generates:
  - Hardware/comparison/hw_phase_comparison.csv  (per-phase table)
  - Hardware/comparison/hw_wall_time.png
  - Hardware/comparison/hw_cpu_time_ms.png
  - Hardware/comparison/hw_comm_bytes.png
  - Hardware/comparison/hw_energy_mJ.png

Phase mapping (device/node perspective):
  Unified         LAAKA (NODE)   Revised-Anon (NODE)   Zhou (USER)
  Registration    Register       Enroll                Enroll
  Authentication  Auth           Auth                  Auth
  Key Exchange    Ack            KeyEx                 KeyEx
  Data            Data           Data                  Data
"""

import csv
import sys
from pathlib import Path

HERE       = Path(__file__).resolve().parent          # Hardware/
COMP_DIR   = HERE / "comparison"
COMP_DIR.mkdir(exist_ok=True)

LAAKA_CSV  = HERE / "LAAKA"             / "results" / "hw_metrics.csv"
RA_CSV     = HERE / "Revised-Anonymity" / "results" / "hw_metrics.csv"
ZHOU_CSV   = HERE / "Zhou"              / "results" / "hw_metrics.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv_rows(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


def find_row(rows: list[dict], role: str) -> dict:
    for r in rows:
        if r.get("Role", "").strip().upper() == role.upper():
            return r
    raise KeyError(f"Role '{role}' not found in CSV")


def fv(row: dict, key: str) -> float:
    """Safe float from dict, trying key variants."""
    for k in (key, key.replace("_Bytes", "_B"), key.replace("_B", "_Bytes")):
        if k in row:
            try:
                return float(row[k])
            except (ValueError, TypeError):
                return 0.0
    return 0.0


# ---------------------------------------------------------------------------
# Load device-perspective rows
# ---------------------------------------------------------------------------

laaka_rows = read_csv_rows(LAAKA_CSV)
ra_rows    = read_csv_rows(RA_CSV)
zhou_rows  = read_csv_rows(ZHOU_CSV)

laaka = find_row(laaka_rows, "NODE")
ra    = find_row(ra_rows,    "NODE")
zhou  = find_row(zhou_rows,  "USER")

# ---------------------------------------------------------------------------
# Extract per-phase metrics
# ---------------------------------------------------------------------------
# Structure: {scheme: {phase: {metric: value}}}

PHASES = ["Registration", "Authentication", "Key_Exchange", "Data"]

data = {
    "LAAKA": {
        "Registration":  {
            "wall_s":   fv(laaka, "Register_Wall_s"),
            "cpu_s":    fv(laaka, "Register_CPU_s"),
            "tx_B":     fv(laaka, "Register_Tx_Bytes"),
            "rx_B":     fv(laaka, "Register_Rx_Bytes"),
            "energy_J": fv(laaka, "Register_Energy_J"),
        },
        "Authentication": {
            "wall_s":   fv(laaka, "Auth_Wall_s"),
            "cpu_s":    fv(laaka, "Auth_CPU_s"),
            "tx_B":     fv(laaka, "Auth_Tx_Bytes"),
            "rx_B":     fv(laaka, "Auth_Rx_Bytes"),
            "energy_J": fv(laaka, "Auth_Energy_J"),
        },
        "Key_Exchange": {
            "wall_s":   fv(laaka, "Ack_Wall_s"),
            "cpu_s":    fv(laaka, "Ack_CPU_s"),
            "tx_B":     fv(laaka, "Ack_Tx_Bytes"),
            "rx_B":     fv(laaka, "Ack_Rx_Bytes"),
            "energy_J": fv(laaka, "Ack_Energy_J"),
        },
        "Data": {
            "wall_s":   fv(laaka, "Data_Wall_s"),
            "cpu_s":    fv(laaka, "Data_CPU_s"),
            "tx_B":     fv(laaka, "Data_Tx_Bytes"),
            "rx_B":     fv(laaka, "Data_Rx_Bytes"),
            "energy_J": fv(laaka, "Data_Energy_J"),
        },
    },
    "Revised-Anon": {
        "Registration": {
            "wall_s":   fv(ra, "Enroll_Wall_s"),
            "cpu_s":    fv(ra, "Enroll_CPU_s"),
            "tx_B":     fv(ra, "Enroll_Tx_Bytes"),
            "rx_B":     fv(ra, "Enroll_Rx_Bytes"),
            "energy_J": fv(ra, "Enroll_Energy_J"),
        },
        "Authentication": {
            "wall_s":   fv(ra, "Auth_Wall_s"),
            "cpu_s":    fv(ra, "Auth_CPU_s"),
            "tx_B":     fv(ra, "Auth_Tx_Bytes"),
            "rx_B":     fv(ra, "Auth_Rx_Bytes"),
            "energy_J": fv(ra, "Auth_Energy_J"),
        },
        "Key_Exchange": {
            "wall_s":   fv(ra, "KeyEx_Wall_s"),
            "cpu_s":    fv(ra, "KeyEx_CPU_s"),
            "tx_B":     fv(ra, "KeyEx_Tx_Bytes"),
            "rx_B":     fv(ra, "KeyEx_Rx_Bytes"),
            "energy_J": fv(ra, "KeyEx_Energy_J"),
        },
        "Data": {
            "wall_s":   fv(ra, "Data_Wall_s"),
            "cpu_s":    fv(ra, "Data_CPU_s"),
            "tx_B":     fv(ra, "Data_Tx_Bytes"),
            "rx_B":     fv(ra, "Data_Rx_Bytes"),
            "energy_J": fv(ra, "Data_Energy_J"),
        },
    },
    "Zhou": {
        "Registration": {
            "wall_s":   fv(zhou, "Enroll_Wall_s"),
            "cpu_s":    fv(zhou, "Enroll_CPU_s"),
            "tx_B":     fv(zhou, "Enroll_Tx_B"),
            "rx_B":     fv(zhou, "Enroll_Rx_B"),
            "energy_J": fv(zhou, "Enroll_Energy_J"),
        },
        "Authentication": {
            "wall_s":   fv(zhou, "Auth_Wall_s"),
            "cpu_s":    fv(zhou, "Auth_CPU_s"),
            "tx_B":     fv(zhou, "Auth_Tx_B"),
            "rx_B":     fv(zhou, "Auth_Rx_B"),
            "energy_J": fv(zhou, "Auth_Energy_J"),
        },
        "Key_Exchange": {
            "wall_s":   fv(zhou, "KeyEx_Wall_s"),
            "cpu_s":    fv(zhou, "KeyEx_CPU_s"),
            "tx_B":     fv(zhou, "KeyEx_Tx_B"),
            "rx_B":     fv(zhou, "KeyEx_Rx_B"),
            "energy_J": fv(zhou, "KeyEx_Energy_J"),
        },
        "Data": {
            "wall_s":   fv(zhou, "Data_Wall_s"),
            "cpu_s":    fv(zhou, "Data_CPU_s"),
            "tx_B":     fv(zhou, "Data_Tx_B"),
            "rx_B":     fv(zhou, "Data_Rx_B"),
            "energy_J": fv(zhou, "Data_Energy_J"),
        },
    },
}

SCHEMES = ["LAAKA", "Revised-Anon", "Zhou"]

# ---------------------------------------------------------------------------
# Write comparison CSV
# ---------------------------------------------------------------------------

csv_out = COMP_DIR / "hw_phase_comparison.csv"
with open(csv_out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    header = ["Phase"]
    for s in SCHEMES:
        header += [
            f"{s}_Wall_s", f"{s}_CPU_ms",
            f"{s}_Tx_B",   f"{s}_Rx_B",
            f"{s}_Total_B", f"{s}_Energy_mJ",
        ]
    w.writerow(header)

    for ph in PHASES:
        row = [ph.replace("_", " ")]
        for s in SCHEMES:
            d = data[s][ph]
            row += [
                f"{d['wall_s']:.6f}",
                f"{d['cpu_s']*1000:.4f}",
                f"{int(d['tx_B'])}",
                f"{int(d['rx_B'])}",
                f"{int(d['tx_B'] + d['rx_B'])}",
                f"{d['energy_J']*1000:.6f}",
            ]
        w.writerow(row)

print(f"CSV written: {csv_out}")

# ---------------------------------------------------------------------------
# Print console table
# ---------------------------------------------------------------------------

METRICS = [
    ("Wall time (ms)",  lambda d: d["wall_s"] * 1000,    ".3f"),
    ("CPU time (ms)",   lambda d: d["cpu_s"] * 1000,     ".4f"),
    ("Tx bytes",        lambda d: d["tx_B"],              ".0f"),
    ("Rx bytes",        lambda d: d["rx_B"],              ".0f"),
    ("Total bytes",     lambda d: d["tx_B"] + d["rx_B"], ".0f"),
    ("Energy (mJ)",     lambda d: d["energy_J"] * 1000,  ".6f"),
]

phase_labels = [p.replace("_", " ") for p in PHASES]

col = 18
print()
for metric_name, extractor, fmt in METRICS:
    print(f"=== {metric_name} ===")
    hdr = f"{'Phase':<20}" + "".join(f"{s:>{col}}" for s in SCHEMES)
    print(hdr)
    print("-" * (20 + col * len(SCHEMES)))
    for ph, ph_label in zip(PHASES, phase_labels):
        vals = [format(extractor(data[s][ph]), fmt) for s in SCHEMES]
        print(f"{ph_label:<20}" + "".join(f"{v:>{col}}" for v in vals))
    print()

# ---------------------------------------------------------------------------
# Bar charts
# ---------------------------------------------------------------------------

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("[charts] matplotlib not available — skipping plots")
    sys.exit(0)

COLORS = {"LAAKA": "#2196F3", "Revised-Anon": "#4CAF50", "Zhou": "#FF5722"}

def grouped_bar(title: str, ylabel: str, extractor, fmt_pct: bool,
                out_path: Path, multiply: float = 1.0) -> None:
    n_phases  = len(PHASES)
    n_schemes = len(SCHEMES)
    x         = np.arange(n_phases)
    width     = 0.22
    offsets   = np.linspace(-(n_schemes - 1) / 2, (n_schemes - 1) / 2, n_schemes) * width

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, scheme in enumerate(SCHEMES):
        vals = [extractor(data[scheme][ph]) * multiply for ph in PHASES]
        bars = ax.bar(x + offsets[i], vals, width, label=scheme,
                      color=COLORS[scheme], edgecolor="black", linewidth=0.5)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() * 1.02,
                        f"{val:.3g}", ha="center", va="bottom", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("_", "\n") for p in PHASES], fontsize=10)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Chart saved: {out_path}")


grouped_bar(
    title    = "Per-Phase Wall-Clock Time (device perspective)",
    ylabel   = "Wall time (ms)",
    extractor= lambda d: d["wall_s"] * 1000,
    fmt_pct  = False,
    out_path = COMP_DIR / "hw_wall_time.png",
)

grouped_bar(
    title    = "Per-Phase CPU Time (device perspective)",
    ylabel   = "CPU time (ms)",
    extractor= lambda d: d["cpu_s"] * 1000,
    fmt_pct  = False,
    out_path = COMP_DIR / "hw_cpu_time_ms.png",
)

grouped_bar(
    title    = "Per-Phase Communication Bytes (device, Tx+Rx)",
    ylabel   = "Bytes",
    extractor= lambda d: d["tx_B"] + d["rx_B"],
    fmt_pct  = False,
    out_path = COMP_DIR / "hw_comm_bytes.png",
)

grouped_bar(
    title    = "Per-Phase Energy Consumption (device perspective)",
    ylabel   = "Energy (mJ)",
    extractor= lambda d: d["energy_J"] * 1000,
    fmt_pct  = False,
    out_path = COMP_DIR / "hw_energy_mJ.png",
)

print(f"\nAll outputs in: {COMP_DIR}")
