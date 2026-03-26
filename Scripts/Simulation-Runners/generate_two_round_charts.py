"""
generate_two_round_charts.py
Comparison charts: Base Scheme vs Two-Round Proposed vs LAAKA

Charts produced:
  01 — Per-phase grouped bar: Energy (mJ)  with ±1σ
  02 — Per-phase grouped bar: CPU Time (s) with ±1σ
  03 — Total stacked bar:   Energy   (Enroll + Auth + KeyEx)
  04 — Total stacked bar:   CPU Time (Enroll + Auth + KeyEx)
  05 — Side-by-side (energy + CPU) 2×2 grid
  06 — Per-device scatter/line: Auth energy    (all 3 schemes)
  07 — Per-device scatter/line: KeyEx energy   (all 3 schemes)
  08 — Per-device scatter/line: Auth CPU       (all 3 schemes)
  09 — Per-device scatter/line: KeyEx CPU      (all 3 schemes)
  10 — Percentage improvement table figure

All saved to: Results/Charts/Two-Round-Comparison/
"""
import csv, os, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ─────────────────────────────────────────────────────────────────
BASE   = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CSV    = os.path.join(BASE, "Results", "CSV-Data")
OUT    = os.path.join(BASE, "Results", "Charts", "Two-Round-Comparison")
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────────────────────────────────────────────
# Helper to read per-device CSV (Device, CPU_s, Energy_J)
def read_pd(fname):
    path = os.path.join(CSV, fname)
    rows = {}
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found")
        return rows
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            clean = {k.strip().strip('"'): v.strip().strip('"') for k,v in row.items()}
            # try common key names
            dev_key   = next((k for k in clean if k in ("Device","Device_ID")), None)
            cpu_key   = next((k for k in clean if k.startswith("CPU")), None)
            en_key    = next((k for k in clean if k.startswith("Energy")), None)
            if dev_key and cpu_key and en_key:
                rows[int(clean[dev_key])] = {"cpu": float(clean[cpu_key]),
                                              "energy": float(clean[en_key])}
    return rows

# ─────────────────────────────────────────────────────────────────
# Load 5-seed summary CSVs
def load_summary(path):
    d = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            clean = {k.strip(): v.strip() for k,v in row.items()}
            # support both formats: (Scheme,Phase,...) and (Phase,...)
            if "Scheme" in clean:
                key = (clean["Scheme"], clean["Phase"])
            else:
                key = clean["Phase"]
            d[key] = {
                "cpu":    float(clean.get("Avg_CPU_s", 0)),
                "sc":     float(clean.get("StdDev_CPU_s", 0)),
                "energy": float(clean.get("Avg_Energy_J", 0)),
                "se":     float(clean.get("StdDev_Energy_J", 0)),
            }
    return d

# Load multi-seed summary (Base + LAAKA)
ms = load_summary(os.path.join(CSV, "multi-seed-summary.csv"))
# Load Two-Round summary
tr = load_summary(os.path.join(CSV, "Two-Round", "two-round-summary.csv"))

PHASES   = ["Enrollment", "Authentication", "Key Exchange"]
SCHEMES  = ["Base-Scheme", "Two-Round", "LAAKA"]
LABELS   = ["Base Scheme", "Two-Round\n(Ours)", "LAAKA"]
COLORS   = ["#1565C0", "#2E7D32", "#E65100"]   # deep blue, deep green, deep orange
PCOLORS  = ["#64B5F6", "#81C784", "#FFB74D"]   # light variants for stacked

plt.rcParams.update({
    'font.size': 11, 'font.family': 'serif',
    'axes.titlesize': 12, 'axes.labelsize': 11,
    'legend.fontsize': 9,  'figure.dpi': 200,
    'axes.grid': True,     'grid.alpha': 0.25,
    'axes.spines.top': False, 'axes.spines.right': False,
})

def get(scheme, phase, key):
    """Get a value from the right summary dict."""
    if scheme == "Two-Round":
        return tr.get(phase, {}).get(key, 0)
    else:
        return ms.get((scheme, phase), {}).get(key, 0)

def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {name}")

# ═══════════════════════════════════════════════════════════════════
# CHART 01 — Per-phase grouped bar: Energy
# ═══════════════════════════════════════════════════════════════════
def chart_01():
    x   = np.arange(len(PHASES))
    w   = 0.24
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for i, (sch, lbl, col) in enumerate(zip(SCHEMES, LABELS, COLORS)):
        vals = [get(sch, p, "energy") * 1000 for p in PHASES]
        errs = [get(sch, p, "se")     * 1000 for p in PHASES]
        bars = ax.bar(x + i*w, vals, w, label=lbl.replace('\n',' '),
                      color=col, yerr=errs, capsize=4,
                      edgecolor='black', linewidth=0.5, alpha=0.88)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5,
                    f'{val:.1f}', ha='center', va='bottom', fontsize=7.5, fontweight='bold')
    ax.set_xlabel('Protocol Phase')
    ax.set_ylabel('Energy (mJ)')
    ax.set_title('Per-Phase Energy Comparison — Base vs Two-Round vs LAAKA\n'
                 '(5-seed avg, 20 devices, ±1σ | Auth & KeyEx are independently measured)')
    ax.set_xticks(x + w); ax.set_xticklabels(PHASES)
    ax.legend(loc='upper left')
    ax.set_ylim(0, ax.get_ylim()[1] * 1.18)
    fig.tight_layout()
    save(fig, "01-Per-Phase-Energy.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 02 — Per-phase grouped bar: CPU Time
# ═══════════════════════════════════════════════════════════════════
def chart_02():
    x = np.arange(len(PHASES)); w = 0.24
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for i, (sch, lbl, col) in enumerate(zip(SCHEMES, LABELS, COLORS)):
        vals = [get(sch, p, "cpu") * 1000 for p in PHASES]
        errs = [get(sch, p, "sc")  * 1000 for p in PHASES]
        bars = ax.bar(x + i*w, vals, w, label=lbl.replace('\n',' '),
                      color=col, yerr=errs, capsize=4,
                      edgecolor='black', linewidth=0.5, alpha=0.88)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+4,
                    f'{val:.0f}', ha='center', va='bottom', fontsize=7.5, fontweight='bold')
    ax.set_xlabel('Protocol Phase')
    ax.set_ylabel('CPU Time (ms)')
    ax.set_title('Per-Phase CPU Time Comparison — Base vs Two-Round vs LAAKA\n'
                 '(5-seed avg, 20 devices, ±1σ | Auth & KeyEx independently measured)')
    ax.set_xticks(x + w); ax.set_xticklabels(PHASES)
    ax.legend(loc='upper left')
    ax.set_ylim(0, ax.get_ylim()[1] * 1.18)
    fig.tight_layout()
    save(fig, "02-Per-Phase-CPU-Time.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 03 — Total stacked bar: Energy
# ═══════════════════════════════════════════════════════════════════
def chart_03():
    fig, ax = plt.subplots(figsize=(8, 5.5))
    phase_colors = ['#42A5F5', '#66BB6A', '#FFA726']
    bottoms = np.zeros(3)
    totals  = np.zeros(3)
    for j, p in enumerate(PHASES):
        vals = np.array([get(s, p, "energy")*1000 for s in SCHEMES])
        ax.bar(LABELS, vals, bottom=bottoms, label=p,
               color=phase_colors[j], edgecolor='black', linewidth=0.5, alpha=0.88)
        for k, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 1:
                ax.text(k, b + v/2, f'{v:.1f}', ha='center', va='center', fontsize=8.5)
        bottoms += vals; totals += vals
    for k, t in enumerate(totals):
        ax.text(k, t + t*0.02, f'Total\n{t:.1f} mJ', ha='center', va='bottom',
                fontsize=9, fontweight='bold')
    ax.set_ylabel('Total Energy (mJ)')
    ax.set_title('Total Protocol Energy — Stacked by Phase\n'
                 '(Enroll + Auth + KeyEx  |  Two-Round: all phases independently measured)')
    ax.legend(loc='upper left', fontsize=9)
    ax.set_ylim(0, max(totals)*1.22)
    fig.tight_layout()
    save(fig, "03-Total-Energy-Stacked.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 04 — Total stacked bar: CPU Time
# ═══════════════════════════════════════════════════════════════════
def chart_04():
    fig, ax = plt.subplots(figsize=(8, 5.5))
    phase_colors = ['#42A5F5', '#66BB6A', '#FFA726']
    bottoms = np.zeros(3); totals = np.zeros(3)
    for j, p in enumerate(PHASES):
        vals = np.array([get(s, p, "cpu")*1000 for s in SCHEMES])
        ax.bar(LABELS, vals, bottom=bottoms, label=p,
               color=phase_colors[j], edgecolor='black', linewidth=0.5, alpha=0.88)
        for k, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 5:
                ax.text(k, b + v/2, f'{v:.0f}', ha='center', va='center', fontsize=8.5)
        bottoms += vals; totals += vals
    for k, t in enumerate(totals):
        ax.text(k, t + t*0.02, f'Total\n{t:.0f} ms', ha='center', va='bottom',
                fontsize=9, fontweight='bold')
    ax.set_ylabel('Total CPU Time (ms)')
    ax.set_title('Total Protocol CPU Time — Stacked by Phase\n'
                 '(Enroll + Auth + KeyEx  |  Two-Round: all phases independently measured)')
    ax.legend(loc='upper left', fontsize=9)
    ax.set_ylim(0, max(totals)*1.22)
    fig.tight_layout()
    save(fig, "04-Total-CPU-Stacked.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 05 — Side-by-side 2×2: per-phase energy + cpu
# ═══════════════════════════════════════════════════════════════════
def chart_05():
    fig, axes = plt.subplots(2, 1, figsize=(11, 10))
    x = np.arange(len(PHASES)); w = 0.24
    for row, (metric, unit, mult, fmt) in enumerate([
        ("energy", "Energy (mJ)", 1000, "{:.1f}"),
        ("cpu",    "CPU Time (ms)", 1000, "{:.0f}"),
    ]):
        ax = axes[row]
        for i, (sch, lbl, col) in enumerate(zip(SCHEMES, LABELS, COLORS)):
            vals = [get(sch, p, metric) * mult for p in PHASES]
            errs = [get(sch, p, "se" if metric=="energy" else "sc") * mult for p in PHASES]
            bars = ax.bar(x + i*w, vals, w, label=lbl.replace('\n',' '),
                          color=col, yerr=errs, capsize=4,
                          edgecolor='black', linewidth=0.5, alpha=0.88)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x()+bar.get_width()/2,
                        bar.get_height() + (0.5 if metric=="energy" else 5),
                        fmt.format(val), ha='center', va='bottom',
                        fontsize=7.5, fontweight='bold')
        ax.set_xlabel('Protocol Phase')
        ax.set_ylabel(unit)
        ax.set_xticks(x + w); ax.set_xticklabels(PHASES)
        ax.legend(loc='upper left')
        ax.set_ylim(0, ax.get_ylim()[1]*1.2)
    fig.suptitle('Base Scheme vs Two-Round Proposed vs LAAKA\n'
                 'Per-Phase Energy & CPU Time (5-seed avg, ±1σ)', fontsize=13, fontweight='bold', y=1.01)
    fig.tight_layout()
    save(fig, "05-Side-by-Side-Energy-CPU.png")

# ═══════════════════════════════════════════════════════════════════
# Per-device data
# ═══════════════════════════════════════════════════════════════════
base_auth  = read_pd("Base-Scheme-auth-results.csv")
base_keyex = read_pd("Base-Scheme-keyex-results.csv")
laaka_auth  = read_pd("LAAKA-auth-results.csv")
laaka_keyex = read_pd("LAAKA-keyex-results.csv")
tr_auth  = read_pd(os.path.join("Two-Round", "auth-results.csv"))
tr_keyex = read_pd(os.path.join("Two-Round", "keyex-results.csv"))

def pd_lines(ax, data, color, label, metric):
    devs = sorted(data.keys())
    vals = [data[d][metric]*1000 for d in devs]
    ax.plot(devs, vals, 'o-', color=color, label=label, linewidth=1.5, markersize=4, alpha=0.85)
    return devs, vals

# ═══════════════════════════════════════════════════════════════════
# CHART 06 — Per-device Auth Energy
# ═══════════════════════════════════════════════════════════════════
def chart_06():
    fig, ax = plt.subplots(figsize=(13, 5))
    pd_lines(ax, base_auth,  COLORS[0], "Base Scheme", "energy")
    pd_lines(ax, tr_auth,    COLORS[1], "Two-Round (Ours)", "energy")
    pd_lines(ax, laaka_auth, COLORS[2], "LAAKA", "energy")
    ax.set_xlabel("Device ID"); ax.set_ylabel("Auth Energy (mJ)")
    ax.set_title("Per-Device Authentication Energy — Base vs Two-Round vs LAAKA\n"
                 "(Auth CoAP only | same definition across all schemes)")
    ax.legend(fontsize=9); ax.grid(axis='y', alpha=0.3)
    means = {
        "Base": sum(v["energy"] for v in base_auth.values())/len(base_auth)*1000 if base_auth else 0,
        "TwoR": sum(v["energy"] for v in tr_auth.values())/len(tr_auth)*1000 if tr_auth else 0,
        "LAAKA": sum(v["energy"] for v in laaka_auth.values())/len(laaka_auth)*1000 if laaka_auth else 0,
    }
    ax.axhline(means["Base"],  color=COLORS[0], linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(means["TwoR"],  color=COLORS[1], linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(means["LAAKA"], color=COLORS[2], linestyle="--", linewidth=1, alpha=0.6)
    for name, val, col in zip(["Base","Two-Round","LAAKA"], means.values(), COLORS):
        ax.text(ax.get_xlim()[1], val, f' avg {val:.1f}mJ', color=col, va='center', fontsize=8)
    fig.tight_layout()
    save(fig, "06-Per-Device-Auth-Energy.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 07 — Per-device KeyEx Energy
# ═══════════════════════════════════════════════════════════════════
def chart_07():
    fig, ax = plt.subplots(figsize=(13, 5))
    pd_lines(ax, base_keyex,  COLORS[0], "Base Scheme", "energy")
    pd_lines(ax, tr_keyex,    COLORS[1], "Two-Round (Ours)", "energy")
    pd_lines(ax, laaka_keyex, COLORS[2], "LAAKA", "energy")
    ax.set_xlabel("Device ID"); ax.set_ylabel("KeyEx Energy (mJ)")
    ax.set_title("Per-Device Key Exchange Energy — Base vs Two-Round vs LAAKA\n"
                 "(KeyEx CoAP only | same definition across all schemes)")
    ax.legend(fontsize=9); ax.grid(axis='y', alpha=0.3)
    means = {
        "Base": sum(v["energy"] for v in base_keyex.values())/len(base_keyex)*1000 if base_keyex else 0,
        "TwoR": sum(v["energy"] for v in tr_keyex.values())/len(tr_keyex)*1000 if tr_keyex else 0,
        "LAAKA": sum(v["energy"] for v in laaka_keyex.values())/len(laaka_keyex)*1000 if laaka_keyex else 0,
    }
    ax.axhline(means["Base"],  color=COLORS[0], linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(means["TwoR"],  color=COLORS[1], linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(means["LAAKA"], color=COLORS[2], linestyle="--", linewidth=1, alpha=0.6)
    for name, val, col in zip(["Base","Two-Round","LAAKA"], means.values(), COLORS):
        ax.text(ax.get_xlim()[1], val, f' avg {val:.1f}mJ', color=col, va='center', fontsize=8)
    fig.tight_layout()
    save(fig, "07-Per-Device-KeyEx-Energy.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 08 — Per-device Auth CPU
# ═══════════════════════════════════════════════════════════════════
def chart_08():
    fig, ax = plt.subplots(figsize=(13, 5))
    pd_lines(ax, base_auth,  COLORS[0], "Base Scheme", "cpu")
    pd_lines(ax, tr_auth,    COLORS[1], "Two-Round (Ours)", "cpu")
    pd_lines(ax, laaka_auth, COLORS[2], "LAAKA", "cpu")
    ax.set_xlabel("Device ID"); ax.set_ylabel("Auth CPU Time (ms)")
    ax.set_title("Per-Device Authentication CPU Time — Base vs Two-Round vs LAAKA")
    ax.legend(fontsize=9); ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    save(fig, "08-Per-Device-Auth-CPU.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 09 — Per-device KeyEx CPU
# ═══════════════════════════════════════════════════════════════════
def chart_09():
    fig, ax = plt.subplots(figsize=(13, 5))
    pd_lines(ax, base_keyex,  COLORS[0], "Base Scheme", "cpu")
    pd_lines(ax, tr_keyex,    COLORS[1], "Two-Round (Ours)", "cpu")
    pd_lines(ax, laaka_keyex, COLORS[2], "LAAKA", "cpu")
    ax.set_xlabel("Device ID"); ax.set_ylabel("KeyEx CPU Time (ms)")
    ax.set_title("Per-Device Key Exchange CPU Time — Base vs Two-Round vs LAAKA")
    ax.legend(fontsize=9); ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    save(fig, "09-Per-Device-KeyEx-CPU.png")

# ═══════════════════════════════════════════════════════════════════
# CHART 10 — Percentage Improvement Table Figure
# ═══════════════════════════════════════════════════════════════════
def chart_10():
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.axis('off')

    rows = []
    for p in PHASES:
        be = get("Base-Scheme", p, "energy") * 1000
        le = get("LAAKA",       p, "energy") * 1000
        te = get("Two-Round",   p, "energy") * 1000
        bc = get("Base-Scheme", p, "cpu")    * 1000
        lc = get("LAAKA",       p, "cpu")    * 1000
        tc = get("Two-Round",   p, "cpu")    * 1000

        def pct(ours, other):
            if other == 0: return "N/A"
            v = (ours - other) / other * 100
            return f"{v:+.1f}%"

        rows.append([
            p,
            f"{be:.2f}", f"{le:.2f}", f"{te:.2f}",
            pct(te, be), pct(te, le),
            f"{bc:.1f}", f"{lc:.1f}", f"{tc:.1f}",
            pct(tc, bc), pct(tc, lc),
        ])

    # Totals row
    total = {}
    for sch in SCHEMES + ["Base-Scheme", "LAAKA"]:
        total[sch] = {"energy": sum(get(sch, p, "energy")*1000 for p in PHASES),
                      "cpu":    sum(get(sch, p, "cpu")*1000    for p in PHASES)}
    def pct(ours, other): return f"{(ours-other)/other*100:+.1f}%" if other else "N/A"
    rows.append([
        "TOTAL",
        f"{total['Base-Scheme']['energy']:.2f}",
        f"{total['LAAKA']['energy']:.2f}",
        f"{total['Two-Round']['energy']:.2f}",
        pct(total['Two-Round']['energy'], total['Base-Scheme']['energy']),
        pct(total['Two-Round']['energy'], total['LAAKA']['energy']),
        f"{total['Base-Scheme']['cpu']:.1f}",
        f"{total['LAAKA']['cpu']:.1f}",
        f"{total['Two-Round']['cpu']:.1f}",
        pct(total['Two-Round']['cpu'], total['Base-Scheme']['cpu']),
        pct(total['Two-Round']['cpu'], total['LAAKA']['cpu']),
    ])

    cols = ["Phase",
            "Base\nEnergy(mJ)", "LAAKA\nEnergy(mJ)", "Ours\nEnergy(mJ)",
            "vs Base\nEnergy", "vs LAAKA\nEnergy",
            "Base\nCPU(ms)", "LAAKA\nCPU(ms)", "Ours\nCPU(ms)",
            "vs Base\nCPU", "vs LAAKA\nCPU"]

    tbl = ax.table(cellText=rows, colLabels=cols, loc='center', cellLoc='center')
    tbl.auto_set_font_size(False); tbl.set_fontsize(8.5); tbl.scale(1, 1.9)

    # Header row
    for j in range(len(cols)):
        tbl[0, j].set_facecolor('#1A3C6E')
        tbl[0, j].set_text_props(color='white', fontweight='bold')
    # Highlight our column
    for i in range(1, len(rows)+1):
        tbl[i, 3].set_facecolor('#E8F5E9')
        tbl[i, 8].set_facecolor('#E8F5E9')
    # Total row
    for j in range(len(cols)):
        tbl[len(rows), j].set_facecolor('#E3F2FD')
        tbl[len(rows), j].set_text_props(fontweight='bold')
    # Colour vs-LAAKA cells
    for i in range(1, len(rows)+1):
        for col_idx in [5, 10]:
            v = rows[i-1][col_idx]
            if isinstance(v, str) and v.startswith('-'):
                tbl[i, col_idx].set_facecolor('#C8E6C9')  # green = we are cheaper
            elif isinstance(v, str) and v.startswith('+'):
                tbl[i, col_idx].set_facecolor('#FFCDD2')  # red = we are more expensive

    ax.set_title('Two-Round Proposed Scheme vs Base Scheme vs LAAKA\n'
                 '(5-seed avg, 20 IoT devices | green = Two-Round is cheaper)',
                 fontsize=11, fontweight='bold', pad=20)
    fig.tight_layout()
    save(fig, "10-Comparison-Table.png")

# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("Generating Two-Round comparison charts...")
    print(f"Output: {OUT}")
    print(f"{'='*60}")
    chart_01()
    chart_02()
    chart_03()
    chart_04()
    chart_05()
    chart_06()
    chart_07()
    chart_08()
    chart_09()
    chart_10()
    print(f"\n✓ All 10 charts saved to:\n  {OUT}")
