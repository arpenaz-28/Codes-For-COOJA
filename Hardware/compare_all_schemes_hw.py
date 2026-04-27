#!/usr/bin/env python3
"""
compare_all_schemes_hw.py  —  3-scheme per-phase hardware comparison.

Writes to Hardware/comparison/:
  comparison_table.csv   — all metrics, all phases, all schemes
  chart_wall_time.png    — wall-clock time  (auth phases, ms)
  chart_cpu_time.png     — CPU time         (auth phases, ms)
  chart_comm_bytes.png   — comm bytes Tx+Rx (all phases)
  chart_energy.png       — energy mJ        (all phases)

Phase structure  (what each scheme actually does):
  Phase | LAAKA (NODE)           | Revised-Anon (NODE)         | Zhou (USER)
  ------+------------------------+-----------------------------+------------------------------
  P1    | Registration (1 RTT)   | Enrollment (2 RTTs + PUF)   | Enrollment (4 exchanges)
  P2    | Authentication (1 RTT, | Auth Round-1 (1 RTT,        | Auth M1 (1 RTT,
        |  SK derived here)      |  identity only, no key yet) |  identity only, no key yet)
  P3    | Acknowledgement        | Key Exchange Round-2        | Key Exchange
        |  (send-only, 0 rx,     |  (1 RTT, SK derived here)   |  (wait for GW to push M4,
        |  SK already set)       |                             |  SK derived here; includes
        |                        |                             |  full M2->M3->M4 pipeline)
  P4    | Data (10 pkts -> Fog)  | Data (10 pkts -> GW)        | Data (10 pkts -> GW_Router)
"""

import csv
import shutil
import sys
from pathlib import Path

HERE     = Path(__file__).resolve().parent
COMP_DIR = HERE / "comparison"
COMP_DIR.mkdir(exist_ok=True)

LAAKA_CSV = HERE / "LAAKA"             / "results" / "hw_metrics.csv"
RA_CSV    = HERE / "Revised-Anonymity" / "results" / "hw_metrics.csv"
ZHOU_CSV  = HERE / "Zhou"              / "results" / "hw_metrics.csv"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_role(path: Path, role: str) -> dict:
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            r = {k.strip(): v.strip() for k, v in row.items()}
            if r.get("Role", "").strip().upper() == role.upper():
                return r
    raise KeyError(f"Role '{role}' not found in {path.name}")


def fv(row: dict, *keys: str) -> float:
    for k in keys:
        if k in row:
            try:
                return float(row[k])
            except (ValueError, TypeError):
                return 0.0
    return 0.0


laaka = load_role(LAAKA_CSV, "NODE")
ra    = load_role(RA_CSV,    "NODE")
zhou  = load_role(ZHOU_CSV,  "USER")

# ---------------------------------------------------------------------------
# Raw per-phase data  (using each scheme's actual phase names)
# ---------------------------------------------------------------------------
#
#  Each entry: wall_s, cpu_s, tx_B, rx_B, energy_J
#
#  Note on Zhou KeyEx wall_s (122 ms):
#    This includes the time the User waits for GW to complete the
#    M2->SN->M3->M4 pipeline and push M4 back.  It is NOT just computation.
#    Revised-Anon and LAAKA P3 are local request-reply, hence much faster.

SCHEMES = ["LAAKA", "Revised-Anon", "Zhou"]

# Phase labels kept scheme-accurate
P_LABELS = {
    "LAAKA":        ["Registration",    "Authentication\n(SK derived here)",   "Acknowledgement\n(send-only, no Rx)", "Data"],
    "Revised-Anon": ["Enrollment\n(2 RTTs + PUF)", "Auth Round-1\n(identity only)", "Key Exchange\n(SK derived here)", "Data"],
    "Zhou":         ["Enrollment\n(4 exchanges)",  "Auth M1\n(identity only)", "Key Exchange\n(wait for M4 push)",  "Data"],
}

raw = {
    "LAAKA": [
        dict(wall=fv(laaka,"Register_Wall_s"), cpu=fv(laaka,"Register_CPU_s"), tx=fv(laaka,"Register_Tx_Bytes"), rx=fv(laaka,"Register_Rx_Bytes"), energy=fv(laaka,"Register_Energy_J")),
        dict(wall=fv(laaka,"Auth_Wall_s"),     cpu=fv(laaka,"Auth_CPU_s"),     tx=fv(laaka,"Auth_Tx_Bytes"),     rx=fv(laaka,"Auth_Rx_Bytes"),     energy=fv(laaka,"Auth_Energy_J")),
        dict(wall=fv(laaka,"Ack_Wall_s"),      cpu=fv(laaka,"Ack_CPU_s"),      tx=fv(laaka,"Ack_Tx_Bytes"),      rx=fv(laaka,"Ack_Rx_Bytes"),      energy=fv(laaka,"Ack_Energy_J")),
        dict(wall=fv(laaka,"Data_Wall_s"),     cpu=fv(laaka,"Data_CPU_s"),     tx=fv(laaka,"Data_Tx_Bytes"),     rx=fv(laaka,"Data_Rx_Bytes"),     energy=fv(laaka,"Data_Energy_J")),
    ],
    "Revised-Anon": [
        dict(wall=fv(ra,"Enroll_Wall_s"), cpu=fv(ra,"Enroll_CPU_s"), tx=fv(ra,"Enroll_Tx_Bytes"), rx=fv(ra,"Enroll_Rx_Bytes"), energy=fv(ra,"Enroll_Energy_J")),
        dict(wall=fv(ra,"Auth_Wall_s"),   cpu=fv(ra,"Auth_CPU_s"),   tx=fv(ra,"Auth_Tx_Bytes"),   rx=fv(ra,"Auth_Rx_Bytes"),   energy=fv(ra,"Auth_Energy_J")),
        dict(wall=fv(ra,"KeyEx_Wall_s"),  cpu=fv(ra,"KeyEx_CPU_s"),  tx=fv(ra,"KeyEx_Tx_Bytes"),  rx=fv(ra,"KeyEx_Rx_Bytes"),  energy=fv(ra,"KeyEx_Energy_J")),
        dict(wall=fv(ra,"Data_Wall_s"),   cpu=fv(ra,"Data_CPU_s"),   tx=fv(ra,"Data_Tx_Bytes"),   rx=fv(ra,"Data_Rx_Bytes"),   energy=fv(ra,"Data_Energy_J")),
    ],
    "Zhou": [
        dict(wall=fv(zhou,"Enroll_Wall_s"), cpu=fv(zhou,"Enroll_CPU_s"), tx=fv(zhou,"Enroll_Tx_B"),  rx=fv(zhou,"Enroll_Rx_B"),  energy=fv(zhou,"Enroll_Energy_J")),
        dict(wall=fv(zhou,"Auth_Wall_s"),   cpu=fv(zhou,"Auth_CPU_s"),   tx=fv(zhou,"Auth_Tx_B"),    rx=fv(zhou,"Auth_Rx_B"),    energy=fv(zhou,"Auth_Energy_J")),
        dict(wall=fv(zhou,"KeyEx_Wall_s"),  cpu=fv(zhou,"KeyEx_CPU_s"),  tx=fv(zhou,"KeyEx_Tx_B"),   rx=fv(zhou,"KeyEx_Rx_B"),   energy=fv(zhou,"KeyEx_Energy_J")),
        dict(wall=fv(zhou,"Data_Wall_s"),   cpu=fv(zhou,"Data_CPU_s"),   tx=fv(zhou,"Data_Tx_B"),    rx=fv(zhou,"Data_Rx_B"),    energy=fv(zhou,"Data_Energy_J")),
    ],
}

PHASE_NAMES = ["P1: Registration/\nEnrollment", "P2: Authentication", "P3: Ack / Key\nExchange", "P4: Data"]
PHASE_NAMES_SHORT = ["P1", "P2", "P3", "P4"]

# ---------------------------------------------------------------------------
# Write comparison_table.csv
# ---------------------------------------------------------------------------

csv_path = COMP_DIR / "comparison_table.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow([
        "Phase",
        "LAAKA Phase Name",        "Revised-Anon Phase Name",    "Zhou Phase Name",
        "LAAKA Wall (ms)",         "Revised-Anon Wall (ms)",      "Zhou Wall (ms)",
        "LAAKA CPU (ms)",          "Revised-Anon CPU (ms)",       "Zhou CPU (ms)",
        "LAAKA Tx+Rx (bytes)",     "Revised-Anon Tx+Rx (bytes)",  "Zhou Tx+Rx (bytes)",
        "LAAKA Energy (mJ)",       "Revised-Anon Energy (mJ)",    "Zhou Energy (mJ)",
    ])
    actual_names = {
        "LAAKA":        ["Registration", "Authentication", "Acknowledgement", "Data"],
        "Revised-Anon": ["Enrollment",   "Auth Round-1",  "Key Exchange",     "Data"],
        "Zhou":         ["Enrollment",   "Auth M1",       "Key Exchange (M4 push)", "Data"],
    }
    for i, ph_label in enumerate(["P1", "P2", "P3", "P4"]):
        row = [ph_label]
        for s in SCHEMES:
            row.append(actual_names[s][i])
        for s in SCHEMES:
            row.append(f"{raw[s][i]['wall']*1000:.3f}")
        for s in SCHEMES:
            row.append(f"{raw[s][i]['cpu']*1000:.4f}")
        for s in SCHEMES:
            row.append(str(int(raw[s][i]['tx'] + raw[s][i]['rx'])))
        for s in SCHEMES:
            row.append(f"{raw[s][i]['energy']*1000:.4f}")
        w.writerow(row)

print(f"Table: {csv_path.name}")

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
print()
print("=" * 78)
print(f"  {'':22}  {'LAAKA':>16}  {'Revised-Anon':>16}  {'Zhou':>16}")
print("=" * 78)
labels_console = ["P1 Registration/Enroll", "P2 Authentication", "P3 Ack/KeyExchange", "P4 Data"]
for metric, extract, fmt in [
    ("Wall time (ms)",   lambda d: d["wall"] * 1000,    ".2f"),
    ("CPU time (ms)",    lambda d: d["cpu"]  * 1000,    ".4f"),
    ("Bytes (Tx+Rx)",    lambda d: d["tx"] + d["rx"],   ".0f"),
    ("Energy (mJ)",      lambda d: d["energy"] * 1000,  ".3f"),
]:
    print(f"\n  [{metric}]")
    for i, lbl in enumerate(labels_console):
        vals = [format(extract(raw[s][i]), fmt) for s in SCHEMES]
        print(f"  {lbl:<25}  {vals[0]:>16}  {vals[1]:>16}  {vals[2]:>16}")
print()
print("  Note: Zhou P3 wall time (122 ms) = waiting for GW to complete")
print("        M2->SN->M3->M4 pipeline and push M4, NOT just local computation.")
print()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import numpy as np
except ImportError:
    print("matplotlib not available — skipping charts")
    sys.exit(0)

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "font.size":        10,
    "axes.titlesize":   12,
    "axes.titleweight": "bold",
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "axes.grid":        True,
    "grid.linestyle":   "--",
    "grid.alpha":       0.35,
})

COLORS  = ["#1565C0", "#2E7D32", "#B71C1C"]   # blue, green, red
HATCHES = ["", "//", "xx"]
BAR_W   = 0.22


def make_chart(out_name: str, title: str, ylabel: str,
               x_labels: list, datasets: dict,
               value_fmt: str = ".1f",
               footnote: str = "") -> None:
    """
    datasets: {scheme_name: [v0, v1, v2, ...]}  — same length as x_labels
    """
    n  = len(x_labels)
    ns = len(SCHEMES)
    x  = np.arange(n)
    offsets = np.linspace(-(ns-1)/2, (ns-1)/2, ns) * BAR_W

    fig, ax = plt.subplots(figsize=(10, 5.5))

    for i, scheme in enumerate(SCHEMES):
        vals = datasets[scheme]
        bars = ax.bar(x + offsets[i], vals, BAR_W,
                      label=scheme,
                      color=COLORS[i], hatch=HATCHES[i],
                      edgecolor="white", linewidth=0.7, alpha=0.9)
        y_max = max(max(v for vv in datasets.values() for v in vv), 1)
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + y_max * 0.015,
                        format(v, value_fmt),
                        ha="center", va="bottom", fontsize=8, rotation=0)

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, pad=10)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%g"))
    if footnote:
        fig.text(0.5, -0.02, footnote, ha="center", fontsize=8,
                 style="italic", color="#555555")
    fig.tight_layout(pad=1.8)
    out_path = COMP_DIR / out_name
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Chart: {out_name}")


# Auth phases only (P1, P2, P3) — Data excluded (all ~30000 ms, adds no info)
AUTH_IDX   = [0, 1, 2]
AUTH_LBLS  = [
    "P1\nRegistration / Enrollment",
    "P2\nAuthentication",
    "P3\nAck / Key Exchange",
]

make_chart(
    "chart_wall_time.png",
    "Wall-Clock Time per Phase  [P1–P3, Data excluded as all ~30 s]",
    "Time (ms)",
    AUTH_LBLS,
    {s: [raw[s][i]["wall"]*1000 for i in AUTH_IDX] for s in SCHEMES},
    value_fmt=".1f",
    footnote=(
        "LAAKA P3 = Ack (send-only, 0 Rx).  "
        "Zhou P3 = wait for GW to push M4 (includes M2->SN->M3->M4 pipeline latency).  "
        "Revised-Anon P1 = 2 RTTs (REG0+REG1)."
    ),
)

make_chart(
    "chart_cpu_time.png",
    "CPU Computation Time per Phase  [P1–P3]",
    "CPU time (ms)",
    AUTH_LBLS,
    {s: [raw[s][i]["cpu"]*1000 for i in AUTH_IDX] for s in SCHEMES},
    value_fmt=".3f",
    footnote=(
        "CPU time excludes network wait. Zhou P1 (Enrollment) highest because it runs "
        "4 AES+SHA256 operations across 4 message exchanges."
    ),
)

ALL_LBLS = ["P1\nReg / Enroll", "P2\nAuth", "P3\nAck / KeyEx", "P4\nData (10 pkts)"]

make_chart(
    "chart_comm_bytes.png",
    "Communication Bytes per Phase  (Tx + Rx, device side)",
    "Bytes",
    ALL_LBLS,
    {s: [raw[s][i]["tx"] + raw[s][i]["rx"] for i in range(4)] for s in SCHEMES},
    value_fmt=".0f",
    footnote=(
        "LAAKA P3 Ack = 107 B Tx, 0 B Rx (send-only).  "
        "Zhou P3 KeyEx = 0 B Tx, 287 B Rx (GW pushes M4 to User, User only receives)."
    ),
)

make_chart(
    "chart_energy.png",
    "Energy Consumption per Phase  (device side, mJ)",
    "Energy (mJ)",
    ALL_LBLS,
    {s: [raw[s][i]["energy"]*1000 for i in range(4)] for s in SCHEMES},
    value_fmt=".2f",
    footnote=(
        "Energy = cpu_s x 2.5 W  +  total_bytes x 0.000002 J/byte.  "
        "Zhou P1 highest due to largest byte count (446 B) across 4 message exchanges."
    ),
)

# ---------------------------------------------------------------------------
# Chart 5 — Total across ALL phases (P1+P2+P3+P4) per metric
# ---------------------------------------------------------------------------
metrics_total = [
    ("cpu",    "Total CPU Time (all 4 phases)",    "CPU time (ms)",   ".2f",
     lambda d: sum(d[i]["cpu"]    for i in range(4)) * 1000),
    ("energy", "Total Energy (all 4 phases)",       "Energy (mJ)",     ".2f",
     lambda d: sum(d[i]["energy"] for i in range(4)) * 1000),
    ("comm",   "Total Communication (all 4 phases)", "Bytes (Tx+Rx)",  ".0f",
     lambda d: sum(d[i]["tx"] + d[i]["rx"] for i in range(4))),
]

fig_t, axes_t = plt.subplots(1, 3, figsize=(13, 5))
fig_t.suptitle(
    "Total Protocol Cost — All 4 Phases  (Real RPi Hardware)",
    fontweight="bold", fontsize=13)

for ax, (key, title, ylabel, vfmt, extract) in zip(axes_t, metrics_total):
    vals = [extract(raw[s]) for s in SCHEMES]
    bar_colors = COLORS[:len(SCHEMES)]
    bars = ax.bar(SCHEMES, vals, color=bar_colors, zorder=3,
                  edgecolor="white", linewidth=0.7, alpha=0.9)
    y_max = max(vals) if max(vals) > 0 else 1
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                v + y_max * 0.015,
                format(v, vfmt),
                ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_title(title, fontweight="bold", pad=8)
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    ax.tick_params(axis="x", rotation=15)

fig_t.tight_layout(pad=1.8)
fig_t.savefig(COMP_DIR / "chart_total_all_phases.png", dpi=150, bbox_inches="tight")
plt.close(fig_t)
print("Chart: chart_total_all_phases.png")

# Chart 6 — Total auth phases only (P1+P2+P3, no Data)
fig_a, axes_a = plt.subplots(1, 3, figsize=(13, 5))
fig_a.suptitle(
    "Total Auth-Phase Cost — P1+P2+P3 (Enrollment + Auth + KeyEx, excl. Data)",
    fontweight="bold", fontsize=12)

for ax, (key, title, ylabel, vfmt, _) in zip(axes_a, metrics_total):
    if key == "cpu":
        extract_a = lambda d: sum(d[i]["cpu"]    for i in [0,1,2]) * 1000
    elif key == "energy":
        extract_a = lambda d: sum(d[i]["energy"] for i in [0,1,2]) * 1000
    else:
        extract_a = lambda d: sum(d[i]["tx"] + d[i]["rx"] for i in [0,1,2])
    vals = [extract_a(raw[s]) for s in SCHEMES]
    bars = ax.bar(SCHEMES, vals, color=COLORS[:len(SCHEMES)], zorder=3,
                  edgecolor="white", linewidth=0.7, alpha=0.9)
    y_max = max(vals) if max(vals) > 0 else 1
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                v + y_max * 0.015,
                format(v, vfmt),
                ha="center", va="bottom", fontsize=9, fontweight="bold")
    title_a = title.replace("all 4 phases", "P1+P2+P3")
    ax.set_title(title_a, fontweight="bold", pad=8)
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    ax.tick_params(axis="x", rotation=15)

fig_a.tight_layout(pad=1.8)
fig_a.savefig(COMP_DIR / "chart_total_auth_phases.png", dpi=150, bbox_inches="tight")
plt.close(fig_a)
print("Chart: chart_total_auth_phases.png")

print(f"\nAll outputs in: {COMP_DIR}")
