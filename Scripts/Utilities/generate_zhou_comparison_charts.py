"""
Generate comparison charts: Proposed (Ours) vs LAAKA vs Zhou et al.
Uses fixed Zhou simulation results (AUTH_ENERGY per-round, differential GW measurement).
Replaces charts in:
  - Results/Charts/03-Zhou-vs-LAAKA-vs-Proposed-Final/
  - Results/Charts/Zhou-vs-LAAKA-vs-Proposed/
  - Results/Charts/02-Final-Three-Scheme-Comparison/ (Final-* files)
"""
import csv, statistics, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE   = r'c:\ANUP\MTP\Proposing\Codes For COOJA'
DATA   = os.path.join(BASE, 'Results', 'CSV-Data')
CHART3 = os.path.join(BASE, 'Results', 'Charts', '03-Zhou-vs-LAAKA-vs-Proposed-Final')
CHARTZ = os.path.join(BASE, 'Results', 'Charts', 'Zhou-vs-LAAKA-vs-Proposed')
CHART2 = os.path.join(BASE, 'Results', 'Charts', '02-Final-Three-Scheme-Comparison')
os.makedirs(CHART3, exist_ok=True)
os.makedirs(CHARTZ, exist_ok=True)

# ── helpers ────────────────────────────────────────────────
def load(path, cpu_col, eng_col):
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            rows.append((float(r[cpu_col]), float(r[eng_col])))
    return rows

def avg(lst): return statistics.mean(lst)
def std(lst): return statistics.stdev(lst) if len(lst) > 1 else 0.0

# ── load Proposed Scheme ───────────────────────────────────
p_auth   = load(os.path.join(DATA,'Proposed-Scheme-Original','auth-results.csv'),   'CPU_s','Energy_J')
p_enroll = load(os.path.join(DATA,'Proposed-Scheme-Original','enroll-results.csv'), 'CPU_s','Energy_J')
p_keyex  = load(os.path.join(DATA,'Proposed-Scheme-Original','keyex-results.csv'),  'CPU_s','Energy_J')
N_prop   = min(len(p_auth), len(p_keyex), len(p_enroll))
p_cpu_auth = [p_auth[i][0]+p_keyex[i][0] for i in range(N_prop)]
p_ej_auth  = [p_auth[i][1]+p_keyex[i][1] for i in range(N_prop)]
p_ej_enr   = [p_enroll[i][1]             for i in range(N_prop)]

# ── load LAAKA ─────────────────────────────────────────────
l_auth   = load(os.path.join(DATA,'LAAKA','auth-results.csv'),   'CPU_Time_s','Energy_J')
l_enroll = load(os.path.join(DATA,'LAAKA','enroll-results.csv'), 'CPU_Time_s','Energy_J')
l_keyex  = load(os.path.join(DATA,'LAAKA','keyex-results.csv'),  'CPU_Time_s','Energy_J')
N_laaka  = min(len(l_auth), len(l_keyex))
l_cpu_auth = [l_auth[i][0]+l_keyex[i][0] for i in range(N_laaka)]
l_ej_auth  = [l_auth[i][1]+l_keyex[i][1] for i in range(N_laaka)]
l_ej_enr   = [l_enroll[i][1]             for i in range(N_laaka)]

# ── load Zhou (fixed simulation) ──────────────────────────
z_rows = []
with open(os.path.join(BASE,'Zhou-Scheme','zhou-auth-results.csv'), newline='') as f:
    for r in csv.DictReader(f):
        z_rows.append((float(r['Avg_CPU_s']), float(r['Avg_Energy_J']), float(r['Enroll_Energy_J'])))
N_zhou     = len(z_rows)
z_cpu_auth = [r[0] for r in z_rows]
z_ej_auth  = [r[1] for r in z_rows]
z_ej_enr   = [r[2] for r in z_rows]

# ── scheme metadata ────────────────────────────────────────
LABELS  = ['Proposed\n(Ours)', 'LAAKA', 'Zhou\net al.']
COLORS  = ['#1565C0',          '#EF6C00', '#B71C1C']
HATCHES = ['',                 '//',       'xx']
X       = np.arange(3)
W       = 0.5

cpu_vals = [avg(p_cpu_auth)*1000, avg(l_cpu_auth)*1000, avg(z_cpu_auth)*1000]
cpu_errs = [std(p_cpu_auth)*1000, std(l_cpu_auth)*1000, std(z_cpu_auth)*1000]
ej_vals  = [avg(p_ej_auth)*1000,  avg(l_ej_auth)*1000,  avg(z_ej_auth)*1000]
ej_errs  = [std(p_ej_auth)*1000,  std(l_ej_auth)*1000,  std(z_ej_auth)*1000]
enr_vals = [avg(p_ej_enr)*1000,   avg(l_ej_enr)*1000,   avg(z_ej_enr)*1000]

print(f"Proposed — CPU: {cpu_vals[0]:.2f}ms  Auth Energy: {ej_vals[0]:.3f}mJ  Enroll: {enr_vals[0]:.3f}mJ")
print(f"LAAKA    — CPU: {cpu_vals[1]:.2f}ms  Auth Energy: {ej_vals[1]:.3f}mJ  Enroll: {enr_vals[1]:.3f}mJ")
print(f"Zhou     — CPU: {cpu_vals[2]:.2f}ms  Auth Energy: {ej_vals[2]:.3f}mJ  Enroll: {enr_vals[2]:.3f}mJ")

# ═══════════════════════════════════════════════════════════
# CHART 1  —  Total Auth Performance (CPU + Energy side-by-side)
# ═══════════════════════════════════════════════════════════
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
fig.suptitle('Authentication Performance: Proposed vs LAAKA vs Zhou et al.',
             fontsize=14, fontweight='bold')

for ax, vals, errs, ylabel, title, fmt in [
    (ax1, cpu_vals, cpu_errs, 'CPU Time (ms)',  'Avg Auth+KeyEx CPU Time', '{:.1f}ms'),
    (ax2, ej_vals,  ej_errs,  'Energy (mJ)',    'Avg Auth+KeyEx Energy',   '{:.2f}mJ'),
]:
    bars = ax.bar(X, vals, W, color=COLORS, hatch=HATCHES,
                  yerr=errs, capsize=5, edgecolor='white', linewidth=0.5,
                  error_kw=dict(ecolor='#555', lw=1.5))
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_xticks(X); ax.set_xticklabels(LABELS, fontsize=10)
    ax.yaxis.grid(True, linestyle='--', alpha=0.55); ax.set_axisbelow(True)
    for bar, v, e in zip(bars, vals, errs):
        ax.text(bar.get_x()+bar.get_width()/2, v+e+max(errs)*0.06,
                fmt.format(v), ha='center', va='bottom', fontsize=9, fontweight='bold')

patches = [mpatches.Patch(color=c, label=l.replace('\n',' '))
           for c, l in zip(COLORS, LABELS)]
fig.legend(handles=patches, loc='lower center', ncol=3, fontsize=10,
           bbox_to_anchor=(0.5, -0.04), frameon=True)
plt.tight_layout()
for p in [CHART3+'/01-Total-Performance-Comparison.png',
          CHARTZ+'/Total_Performance_Comparison.png',
          CHART2+'/Final-01-Energy-Comparison.png']:
    plt.savefig(p, dpi=150, bbox_inches='tight'); print('Saved:', os.path.basename(p))
plt.close()

# ═══════════════════════════════════════════════════════════
# CHART 2  —  Stacked Energy Breakdown (Enroll + Auth+KeyEx)
# ═══════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 6))
ax.set_title('Total Protocol Energy Breakdown\n(Enrollment + Authentication + Key Exchange)',
             fontsize=13, fontweight='bold')

b1 = ax.bar(X, enr_vals, W, label='Enrollment',
            color='#90CAF9', edgecolor='#1A237E', linewidth=1.2, hatch='')
b2 = ax.bar(X, ej_vals,  W, label='Auth + Key Exchange',
            color=COLORS,   edgecolor='white',   linewidth=0.5, hatch=HATCHES,
            bottom=enr_vals)

ax.set_ylabel('Energy (mJ)', fontsize=12)
ax.set_xticks(X); ax.set_xticklabels(LABELS, fontsize=11)
ax.yaxis.grid(True, linestyle='--', alpha=0.55); ax.set_axisbelow(True)
ax.legend(fontsize=10, loc='upper left')

for i, (ev, av) in enumerate(zip(enr_vals, ej_vals)):
    total = ev+av
    ax.text(i, total+0.5, f'{total:.2f}mJ', ha='center', va='bottom',
            fontsize=9, fontweight='bold')
    ax.text(i, ev/2,    f'{ev:.2f}',  ha='center', va='center', fontsize=8, color='#0D47A1')
    ax.text(i, ev+av/2, f'{av:.2f}',  ha='center', va='center', fontsize=8,
            color='white', fontweight='bold')

plt.tight_layout()
for p in [CHART3+'/02-Energy-Breakdown-Stacked.png',
          CHARTZ+'/Total_Energy_Stacked.png',
          CHART2+'/Final-03-Total-Cost.png']:
    plt.savefig(p, dpi=150, bbox_inches='tight'); print('Saved:', os.path.basename(p))
plt.close()

# ═══════════════════════════════════════════════════════════
# CHART 3  —  CPU Time bar (standalone for Final-02)
# ═══════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(8, 5))
ax.set_title('Authentication + Key Exchange CPU Time Comparison', fontsize=13, fontweight='bold')
bars = ax.bar(X, cpu_vals, W, color=COLORS, hatch=HATCHES,
              yerr=cpu_errs, capsize=6, edgecolor='white', linewidth=0.5,
              error_kw=dict(ecolor='#555', lw=1.5))
ax.set_ylabel('CPU Time (ms)', fontsize=12)
ax.set_xticks(X); ax.set_xticklabels(LABELS, fontsize=11)
ax.yaxis.grid(True, linestyle='--', alpha=0.55); ax.set_axisbelow(True)
for bar, v, e in zip(bars, cpu_vals, cpu_errs):
    ax.text(bar.get_x()+bar.get_width()/2, v+e+max(cpu_errs)*0.06,
            f'{v:.1f}ms', ha='center', va='bottom', fontsize=9, fontweight='bold')
patches = [mpatches.Patch(color=c, label=l.replace('\n',' ')) for c, l in zip(COLORS, LABELS)]
ax.legend(handles=patches, fontsize=10)
plt.tight_layout()
p = CHART2+'/Final-02-CPU-Comparison.png'
plt.savefig(p, dpi=150, bbox_inches='tight'); print('Saved:', os.path.basename(p))
plt.close()

# ═══════════════════════════════════════════════════════════
# CHART 4  —  Per-Device Auth+KeyEx Energy (line plot)
# ═══════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(14, 5))
ax.set_title('Per-Device Authentication + Key Exchange Energy', fontsize=13, fontweight='bold')

ax.plot(range(1, N_prop+1),  [v*1000 for v in p_ej_auth], 'o-',
        color='#1565C0', label='Proposed (Ours)', lw=2, ms=5)
ax.plot(range(1, N_laaka+1), [v*1000 for v in l_ej_auth], 's--',
        color='#EF6C00', label='LAAKA', lw=2, ms=5)
ax.plot(range(1, N_zhou+1),  [v*1000 for v in z_ej_auth], '^:',
        color='#B71C1C', label='Zhou et al.', lw=2, ms=5)

for vals, color in [(p_ej_auth,'#1565C0'),(l_ej_auth,'#EF6C00'),(z_ej_auth,'#B71C1C')]:
    ax.axhline(avg(vals)*1000, color=color, linestyle='-.', alpha=0.45, lw=1)

ax.set_xlabel('Device Index', fontsize=11)
ax.set_ylabel('Energy (mJ)', fontsize=11)
ax.legend(fontsize=10, loc='upper left')
ax.yaxis.grid(True, linestyle='--', alpha=0.45); ax.set_axisbelow(True)
plt.tight_layout()
p = CHART3+'/03-Per-Device-Auth-Energy.png'
plt.savefig(p, dpi=150, bbox_inches='tight'); print('Saved:', os.path.basename(p))
plt.close()

# ═══════════════════════════════════════════════════════════
# CHART 5  —  Improvement % (Proposed vs LAAKA and Zhou)
# ═══════════════════════════════════════════════════════════
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle('Proposed Scheme: Improvement over Competitors', fontsize=13, fontweight='bold')

comp_labels = ['vs LAAKA', 'vs Zhou et al.']
cpu_impr = [(avg(l_cpu_auth)-avg(p_cpu_auth))/avg(l_cpu_auth)*100,
            (avg(z_cpu_auth)-avg(p_cpu_auth))/avg(z_cpu_auth)*100]
ej_impr  = [(avg(l_ej_auth)-avg(p_ej_auth))/avg(l_ej_auth)*100,
            (avg(z_ej_auth)-avg(p_ej_auth))/avg(z_ej_auth)*100]
xi       = np.arange(2)
ci       = ['#EF6C00', '#B71C1C']

for ax, vals, title, ylabel in [
    (ax1, cpu_impr, 'CPU Time Reduction (%)', 'Improvement (%)'),
    (ax2, ej_impr,  'Energy Reduction (%)',   'Improvement (%)'),
]:
    bars = ax.bar(xi, vals, 0.5, color=ci, edgecolor='white')
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticks(xi); ax.set_xticklabels(comp_labels, fontsize=10)
    ax.yaxis.grid(True, linestyle='--', alpha=0.55); ax.set_axisbelow(True)
    ax.axhline(0, color='black', lw=0.8)
    for bar, v in zip(bars, vals):
        ypos = bar.get_height() + (0.5 if v >= 0 else -2)
        ax.text(bar.get_x()+bar.get_width()/2, ypos,
                f'{v:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')

plt.tight_layout()
p = CHART3+'/04-Improvement-over-competitors.png'
plt.savefig(p, dpi=150, bbox_inches='tight'); print('Saved:', os.path.basename(p))
plt.close()

# ═══════════════════════════════════════════════════════════
# CHART 6  —  Summary Comparison Table (Final-05)
# ═══════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(13, 4))
ax.axis('off')
ax.set_title('Performance Summary: Proposed vs LAAKA vs Zhou et al.',
             fontsize=13, fontweight='bold', pad=16)

col_headers = ['Metric', 'Proposed (Ours)', 'LAAKA', 'Zhou et al.']
table_rows  = [
    ['Devices measured',             str(N_prop),   str(N_laaka),  str(N_zhou)],
    ['Auth+KeyEx CPU time (ms)',
     f'{cpu_vals[0]:.2f} ± {cpu_errs[0]:.2f}',
     f'{cpu_vals[1]:.2f} ± {cpu_errs[1]:.2f}',
     f'{cpu_vals[2]:.2f} ± {cpu_errs[2]:.2f}'],
    ['Auth+KeyEx Energy (mJ)',
     f'{ej_vals[0]:.3f} ± {ej_errs[0]:.3f}',
     f'{ej_vals[1]:.3f} ± {ej_errs[1]:.3f}',
     f'{ej_vals[2]:.3f} ± {ej_errs[2]:.3f}'],
    ['Enrollment Energy (mJ)',
     f'{enr_vals[0]:.3f}', f'{enr_vals[1]:.3f}', f'{enr_vals[2]:.3f}'],
    ['Total Protocol Energy (mJ)',
     f'{enr_vals[0]+ej_vals[0]:.3f}',
     f'{enr_vals[1]+ej_vals[1]:.3f}',
     f'{enr_vals[2]+ej_vals[2]:.3f}'],
    ['Hash ops (auth phase)',         '8',          '19',           '14 (4+7+3)'],
    ['Auth messages',                 '3',          '3',            '4 (M1–M4)'],
    ['CPU improvement over scheme',
     'Baseline',
     f'+{(cpu_vals[1]-cpu_vals[0])/cpu_vals[0]*100:.1f}% higher',
     f'+{(cpu_vals[2]-cpu_vals[0])/cpu_vals[0]*100:.1f}% higher'],
]

tbl = ax.table(cellText=table_rows, colLabels=col_headers,
               cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
tbl.auto_set_font_size(False); tbl.set_fontsize(9.5)

row_colors = ['#E3F2FD', '#FFF3E0', '#FFEBEE']
for j in range(4):
    tbl[0, j].set_facecolor('#1A3C6E')
    tbl[0, j].set_text_props(color='white', fontweight='bold')
for i in range(1, len(table_rows)+1):
    for j in range(4):
        tbl[i, j].set_facecolor(row_colors[j-1] if j > 0 else '#F5F5F5')
        tbl[i, j].set_edgecolor('#CCCCCC')

tbl.auto_set_column_width(list(range(4)))
plt.tight_layout()
p = CHART2+'/Final-05-Comparison-Table.png'
plt.savefig(p, dpi=150, bbox_inches='tight'); print('Saved:', os.path.basename(p))
plt.close()

print('\nDone. All 6 chart sets generated and old charts replaced.')
