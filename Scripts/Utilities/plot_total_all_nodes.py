import csv, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))

def tot(rows, keys):
    for k in keys:
        if k in rows[0]:
            return sum(float(r[k]) for r in rows)
    raise KeyError(keys)

def s20(rows, keys):
    n = len(rows)
    return tot(rows, keys) * (20.0 / n)

# Column name variants
EC = ['Energy_J', 'Avg_Energy_J', 'energy_j']
CC = ['CPU_Time_s', 'CPU_s', 'Avg_CPU_s', 'cpu_s']

p_auth = load('/mnt/schemes/Results/CSV-Data/Proposed-Scheme-Original/auth-results.csv')
p_enr  = load('/mnt/schemes/Results/CSV-Data/Proposed-Scheme-Original/enroll-results.csv')
p_kex  = load('/mnt/schemes/Results/CSV-Data/Proposed-Scheme-Original/keyex-results.csv')
l_auth = load('/mnt/schemes/Results/CSV-Data/LAAKA/auth-results.csv')
l_enr  = load('/mnt/schemes/Results/CSV-Data/LAAKA/enroll-results.csv')
l_kex  = load('/mnt/schemes/Results/CSV-Data/LAAKA/keyex-results.csv')
z      = load('/mnt/schemes/Zhou-Scheme/zhou-auth-results.csv')

cpu_enr  = [s20(p_enr,CC)*1e3,  s20(l_enr,CC)*1e3,  0]
cpu_auth = [s20(p_auth,CC)*1e3, s20(l_auth,CC)*1e3, tot(z,CC)*1e3]
cpu_kex  = [s20(p_kex,CC)*1e3,  s20(l_kex,CC)*1e3,  0]
ej_enr   = [s20(p_enr,EC)*1e3,  s20(l_enr,EC)*1e3,  0]
ej_auth  = [s20(p_auth,EC)*1e3, s20(l_auth,EC)*1e3, tot(z,EC)*1e3]
ej_kex   = [s20(p_kex,EC)*1e3,  s20(l_kex,EC)*1e3,  0]

totals_cpu = [e+a+k for e,a,k in zip(cpu_enr, cpu_auth, cpu_kex)]
totals_ej  = [e+a+k for e,a,k in zip(ej_enr,  ej_auth,  ej_kex)]

schemes  = ['Proposed\n(Ours)', 'LAAKA', 'Zhou et al.*']
clr_main = ['#1E88E5', '#FB8C00', '#E53935']
x = np.arange(len(schemes))
w = 0.52

fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))
fig.suptitle('Total Cost Across All 20 Devices — One Auth Session\nProposed vs LAAKA vs Zhou et al.',
             fontsize=14, fontweight='bold')

for ax, (enr, auth, kex, totals, ylabel, title, unit) in zip(axes, [
    (cpu_enr, cpu_auth, cpu_kex, totals_cpu, 'Total CPU Time (ms)', 'Total CPU Time', 'ms'),
    (ej_enr,  ej_auth,  ej_kex,  totals_ej,  'Total Energy (mJ)',   'Total Energy',   'mJ'),
]):
    ax.bar(x, enr, w, color='#90CAF9', edgecolor='#1565C0', linewidth=0.5)
    ax.bar(x, auth, w, bottom=enr, color=clr_main, edgecolor='white', linewidth=0.4)
    btm = [e+a for e,a in zip(enr, auth)]
    ax.bar(x, kex, w, bottom=btm, color='#1A237E', edgecolor='white', linewidth=0.4, alpha=0.7)

    ymax = max(totals)
    for i, tv in enumerate(totals):
        ax.text(x[i], tv + ymax*0.013,
                '{:,.0f} {}'.format(tv, unit),
                ha='center', va='bottom', fontsize=11, fontweight='bold', color=clr_main[i])

    for i in range(1, 3):
        if totals[i] > 0:
            pct = (totals[i] - totals[0]) / totals[0] * 100
            ax.text(x[i], totals[i] * 0.48,
                    '{:+.0f}%\nvs ours'.format(pct),
                    ha='center', va='center', fontsize=9,
                    color='white', fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(schemes, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_ylim(0, ymax * 1.2)
    ax.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

enr_p  = mpatches.Patch(color='#90CAF9', label='Enrollment')
auth_p = mpatches.Patch(color='#9E9E9E', label='Authentication')
kex_p  = mpatches.Patch(color='#1A237E', alpha=0.7, label='Key Exchange')
fig.legend(handles=[enr_p, auth_p, kex_p], loc='lower center',
           ncol=3, fontsize=10, frameon=True, bbox_to_anchor=(0.5, -0.04))
fig.text(0.5, -0.09,
         '* Zhou et al.: combined 4-msg auth round (M1-M4) only; enroll/keyex not separately measured.',
         ha='center', fontsize=8, color='gray', style='italic')

plt.tight_layout()
out = '/mnt/schemes/Results/Charts/03-Zhou-vs-LAAKA-vs-Proposed-Final/05-Total-All-Nodes-Cost.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print('Saved: ' + out)

print()
print('{:<12} {:>12} {:>12} {:>12}   {:>10} {:>10} {:>10}'.format(
      'Scheme','CPU-Enr(ms)','CPU-Auth(ms)','CPU-Kex(ms)','Ej-Enr(mJ)','Ej-Auth(mJ)','Ej-Kex(mJ)'))
for i, s in enumerate(['Proposed','LAAKA','Zhou']):
    print('{:<12} {:>12.1f} {:>12.1f} {:>12.1f}   {:>10.1f} {:>10.1f} {:>10.1f}  total {:.0f}ms / {:.1f}mJ'.format(
        s, cpu_enr[i], cpu_auth[i], cpu_kex[i],
        ej_enr[i], ej_auth[i], ej_kex[i],
        totals_cpu[i], totals_ej[i]))
