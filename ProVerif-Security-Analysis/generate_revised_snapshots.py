"""
generate_revised_snapshots.py
Generate ProVerif Security Analysis Snapshots for the Revised-Anonymity Scheme
and comparison against the Anonymity-Extended-Base Scheme.

Outputs (in ProVerif-Security-Analysis/):
  1. revised_scheme_proverif_results.png   — Full 19-query verification table
  2. extended_vs_revised_comparison.png    — Side-by-side comparison table
  3. revised_security_coverage.png         — Coverage bar chart (3 schemes)
  4. revised_query_distribution.png        — Pie / donut breakdown

Run:
  python ProVerif-Security-Analysis/generate_revised_snapshots.py
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ===================== COLOUR PALETTE =====================
DARK_BLUE   = '#1A3C6E'
MED_BLUE    = '#2E5FA1'
LIGHT_BLUE  = '#E8EEF6'
GREEN       = '#27AE60'
GREEN_BG    = '#E8F8F0'
PURPLE      = '#6C3483'
PURPLE_BG   = '#F4ECF7'
ORANGE      = '#D35400'
WHITE       = '#FFFFFF'
GRAY_BG     = '#F5F5F5'

# =====================================================================
# FIGURE 1 — Revised Scheme: Full 19-query verification table
# =====================================================================
fig1, ax1 = plt.subplots(figsize=(16, 13))
ax1.axis('off')
ax1.set_title(
    'ProVerif Formal Verification — Revised-Anonymity Scheme\n'
    'PUF-based IoT Authentication: Explicit Two-Round Auth + Key Exchange\n'
    'with Dual-State Desync Recovery, AND-Accumulator & Pseudonym Rotation',
    fontsize=13, fontweight='bold', color=DARK_BLUE, pad=18)

# (QueryID, ProVerif query (abbreviated), Security property, Category, Result)
revised_data = [
    # --- Authentication Correspondence ---
    ['Q1',  'inj-event(DeviceEnrolled(D,AS))\n  ==> inj-event(DeviceEnrollmentStarts(D,AS))',
     'Enrollment Integrity (Device)',                'Auth', 'TRUE'],
    ['Q2',  'inj-event(ASEnrollmentCompletes(AS,D))\n  ==> inj-event(ASEnrollmentStarts(AS,D))',
     'Enrollment Integrity (AS)',                    'Auth', 'TRUE'],
    ['Q3',  'inj-event(DeviceAuthRound1Done(D,AS))\n  ==> inj-event(DeviceAuthStarts(D,AS))',
     'Round-1 Auth Correspondence (Device)',         'Auth', 'TRUE'],
    ['Q4',  'inj-event(ASAuthCompletes(AS,D))\n  ==> inj-event(ASAuthStarts(AS,D))',
     'Round-1 Auth Correspondence (AS)',             'Auth', 'TRUE'],
    ['Q5',  'inj-event(DeviceKeyExDone(D,AS))\n  ==> inj-event(DeviceKeyExStarts(D,AS))',
     'Round-2 Key-Ex Correspondence (Device)',       'Auth', 'TRUE'],
    ['Q6',  'inj-event(ASKeyExCompletes(AS,D))\n  ==> inj-event(ASKeyExStarts(AS,D))',
     'Round-2 Key-Ex Correspondence (AS)',           'Auth', 'TRUE'],
    ['Q7',  'inj-event(AuthRound2Full(D,AS,R,m))\n  ==> inj-event(AuthRound1Full(D,AS,R,m))',
     'Cross-Round Binding (R_D & m_D)',              'Auth', 'TRUE'],
    ['Q8',  'inj-event(GWTokenReceived(pid,AS))\n  ==> inj-event(ASTokenSent(pid,AS))',
     'Token Forwarding Integrity',                   'Auth', 'TRUE'],
    ['Q9',  'event(GWDataAccepted(pid,D))\n  ==> event(DeviceDataSent(pid,D))',
     'End-to-End Data Authenticity',                 'Auth', 'TRUE'],
    # --- Secrecy ---
    ['Q10', 'not attacker(SecretK_GW_D_Device)',
     'Session Key Secrecy — Device view',            'Secrecy', 'TRUE'],
    ['Q11', 'not attacker(SecretK_GW_D_AS)',
     'Session Key Secrecy — AS view',                'Secrecy', 'TRUE'],
    ['Q12', 'not attacker(SecretK_GW_D_GW)',
     'Session Key Secrecy — GW view',                'Secrecy', 'TRUE'],
    ['Q13', 'not attacker(SecretM_New)',
     'Rotated Seed Secrecy (Forward Secrecy)',        'Secrecy', 'TRUE'],
    ['Q14', 'not attacker(SecretR_D)',
     'PUF Response Secrecy (Unclonability)',          'Secrecy', 'TRUE'],
    ['Q15', 'not attacker(SecretID_D)',
     'Device Anonymity (Identity Secrecy)',           'Secrecy', 'TRUE'],
    ['Q16', 'not attacker(SecretTs2)',
     'AS Nonce Secrecy (ts_2 freshness)',             'Secrecy', 'TRUE'],
    # --- Weak Secrecy ---
    ['Q17', 'weaksecret SecretK_GW_D_Device',
     'Offline Guessing Resistance — Device Key',     'Weak Secrecy', 'TRUE'],
    ['Q18', 'weaksecret SecretK_GW_D_AS',
     'Offline Guessing Resistance — AS Key',         'Weak Secrecy', 'TRUE'],
    ['Q19', 'weaksecret SecretK_GW_D_GW',
     'Offline Guessing Resistance — GW Key',         'Weak Secrecy', 'TRUE'],
]

CAT_COLORS = {
    'Auth':         '#EAF3FB',
    'Secrecy':      '#E8F8F0',
    'Weak Secrecy': '#F4ECF7',
}

col_labels  = ['#', 'ProVerif Query', 'Security Property', 'Category', 'Result']
col_widths  = [0.035, 0.42, 0.25, 0.12, 0.065]

table1 = ax1.table(
    cellText   = [[r[0], r[1], r[2], r[3], r[4]] for r in revised_data],
    colLabels  = col_labels,
    colWidths  = col_widths,
    loc        = 'center',
    cellLoc    = 'center')
table1.auto_set_font_size(False)
table1.set_fontsize(7.5)
table1.scale(1.0, 2.05)

for j in range(len(col_labels)):
    c = table1[0, j]
    c.set_facecolor(DARK_BLUE)
    c.set_text_props(color=WHITE, fontweight='bold', fontsize=9)
    c.set_edgecolor(WHITE)

for i, row in enumerate(revised_data, start=1):
    cat_bg = CAT_COLORS[row[3]]
    for j in range(len(col_labels)):
        cell = table1[i, j]
        cell.set_edgecolor('#CCCCCC')
        if j == 4:
            cell.set_facecolor(GREEN_BG)
            cell.set_text_props(color=GREEN, fontweight='bold', fontsize=9)
        elif j == 1:
            cell.set_facecolor(cat_bg)
            cell.set_text_props(fontsize=6.5, family='monospace', ha='left')
        elif j == 3:
            cell.set_facecolor(cat_bg)
            cell.set_text_props(fontsize=7.5, fontstyle='italic')
        else:
            cell.set_facecolor(cat_bg)

# Legend patches
legend_patches = [
    mpatches.Patch(facecolor='#EAF3FB',  edgecolor='#AAAAAA', label='Authentication Correspondence (Q1–Q9)'),
    mpatches.Patch(facecolor='#E8F8F0',  edgecolor='#AAAAAA', label='Secrecy / Confidentiality (Q10–Q16)'),
    mpatches.Patch(facecolor='#F4ECF7',  edgecolor='#AAAAAA', label='Weak Secrecy / Offline Guessing (Q17–Q19)'),
    mpatches.Patch(facecolor=GREEN_BG,   edgecolor=GREEN,      label='All Queries: VERIFIED TRUE'),
]
ax1.legend(handles=legend_patches, loc='lower center', ncol=2, fontsize=8,
           framealpha=0.9, bbox_to_anchor=(0.5, -0.02))

fig1.tight_layout()
out1 = os.path.join(OUT_DIR, 'revised_scheme_proverif_results.png')
fig1.savefig(out1, dpi=200, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
plt.close(fig1)
print(f"[1/4] Saved: {out1}")


# =====================================================================
# FIGURE 2 — Comparison: Base Scheme vs Proposed (Revised-Anonymity) Scheme
# =====================================================================
fig2, ax2 = plt.subplots(figsize=(17, 14))
ax2.axis('off')
ax2.set_title(
    'ProVerif Security Analysis Comparison\n'
    'Base Scheme  vs.  Proposed Scheme (Revised-Anonymity)',
    fontsize=13, fontweight='bold', color=DARK_BLUE, pad=18)

comp_data = [
    # Authentication
    ['Enrollment Integrity (Device)',
     'TRUE\n(NodeEnrolled ==> NodeEnrollmentStarts)',
     'TRUE  Q1\n(DeviceEnrolled ==> DeviceEnrollmentStarts)'],
    ['Enrollment Integrity (AS)',
     '—\n(Not verified)',
     'TRUE  Q2\n(ASEnrollmentCompletes ==> ASEnrollmentStarts)'],
    ['Device Auth Correspondence',
     'TRUE\n(NodeAuthenticated ==> NodeAuthenticationStarts)',
     'TRUE  Q3\n(DeviceAuthRound1Done ==> DeviceAuthStarts)'],
    ['AS Auth Correspondence',
     'TRUE\n(AuthenticatorEnds ==> AuthenticatorStarts)',
     'TRUE  Q4\n(ASAuthCompletes ==> ASAuthStarts)'],
    ['Device Key-Exchange\nCorrespondence',
     '—\n(Not verified)',
     'TRUE  Q5\n(DeviceKeyExDone ==> DeviceKeyExStarts)'],
    ['AS Key-Exchange\nCorrespondence',
     '—\n(Not verified)',
     'TRUE  Q6\n(ASKeyExCompletes ==> ASKeyExStarts)'],
    ['Full Auth + Cross-Round\nBinding (Replay Resistance)',
     'TRUE\n(AuthEndsFull ==> AuthStartsFull)',
     'TRUE  Q7\n(AuthRound2Full ==> AuthRound1Full)\n+ R_D & m_D cross-round bound'],
    ['Token Forwarding Integrity',
     '—\n(Not verified)',
     'TRUE  Q8\n(GWTokenReceived ==> ASTokenSent)'],
    ['End-to-End Data Authenticity',
     '—\n(Not verified)',
     'TRUE  Q9\n(GWDataAccepted ==> DeviceDataSent)'],
    # Secrecy
    ['Session Key Secrecy (Device)',
     'TRUE\n(SecretK_GW\'_N_N)',
     'TRUE  Q10\n(SecretK_GW_D_Device)'],
    ['Session Key Secrecy (AS)',
     'TRUE\n(SecretK_GW\'_N_Ath)',
     'TRUE  Q11\n(SecretK_GW_D_AS)'],
    ['Session Key Secrecy (GW)',
     '—\n(Not verified separately)',
     'TRUE  Q12\n(SecretK_GW_D_GW)'],
    ['Rotated Seed Secrecy\n(Forward Secrecy)',
     '—\n(Not verified)',
     'TRUE  Q13\n(SecretM_New)'],
    ['PUF Response Secrecy',
     '—\n(Not verified)',
     'TRUE  Q14\n(SecretR_D)'],
    ['Device Anonymity\n(Identity Secrecy)',
     '—\n(Not verified)',
     'TRUE  Q15\n(SecretID_D)'],
    ['AS Nonce Secrecy (ts_2)',
     '—\n(Not modelled)',
     'TRUE  Q16\n(SecretTs2)'],
    # Weak Secrecy
    ['Offline Guessing (Device Key)',
     'TRUE\n(weaksecret SecretK_GW\'_N_N)',
     'TRUE  Q17\n(weaksecret SecretK_GW_D_Device)'],
    ['Offline Guessing (AS Key)',
     'TRUE\n(weaksecret SecretK_GW\'_N_Ath)',
     'TRUE  Q18\n(weaksecret SecretK_GW_D_AS)'],
    ['Offline Guessing (GW Key)',
     '—\n(Not verified)',
     'TRUE  Q19\n(weaksecret SecretK_GW_D_GW)'],
]

comp_cols   = ['Security Property',
               'Base Scheme  (8 queries)',
               'Proposed Scheme — Revised-Anonymity  (19 queries)']
comp_widths = [0.23, 0.32, 0.36]

table2 = ax2.table(
    cellText   = comp_data,
    colLabels  = comp_cols,
    colWidths  = comp_widths,
    loc        = 'center',
    cellLoc    = 'center')
table2.auto_set_font_size(False)
table2.set_fontsize(7.5)
table2.scale(1.0, 2.1)

for j in range(len(comp_cols)):
    c = table2[0, j]
    c.set_facecolor(DARK_BLUE)
    c.set_text_props(color=WHITE, fontweight='bold', fontsize=9)
    c.set_edgecolor(WHITE)

for i, row in enumerate(comp_data, start=1):
    alt_bg = WHITE if i % 2 == 1 else LIGHT_BLUE
    for j in range(len(comp_cols)):
        cell = table2[i, j]
        cell.set_edgecolor('#CCCCCC')
        txt  = row[j]
        if j == 0:
            cell.set_facecolor(alt_bg)
            cell.set_text_props(fontweight='bold', fontsize=7.5)
        elif txt.startswith('TRUE'):
            bg = GREEN_BG if j == 2 else '#F0F9F4'
            cell.set_facecolor(bg)
            cell.set_text_props(color=GREEN if j == 2 else '#1E8449', fontsize=7)
        elif txt.startswith('—'):
            cell.set_facecolor('#FFF8F0' if j == 1 else GRAY_BG)
            cell.set_text_props(color='#999999', fontsize=7, fontstyle='italic')
        else:
            cell.set_facecolor(alt_bg)

fig2.tight_layout()
out2 = os.path.join(OUT_DIR, 'base_vs_proposed_comparison.png')
fig2.savefig(out2, dpi=200, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
plt.close(fig2)
print(f"[2/4] Saved: {out2}")


# =====================================================================
# FIGURE 3 — Security Property Coverage Bar Chart (Base vs Proposed)
# =====================================================================
fig3, ax3 = plt.subplots(figsize=(12, 7))

categories = [
    'Enrollment\nIntegrity',
    'Auth\nCorrespondence',
    'Replay /\nBinding',
    'Key-Ex\nCorrespondence',
    'Token & Data\nIntegrity',
    'Session Key\nSecrecy',
    'PUF / Seed\nSecrecy',
    'Device\nAnonymity',
    'AS Nonce\nSecrecy',
    'Offline Guessing\n(Weak Secrecy)',
]

# Counts per scheme
base_counts    = [1, 2, 1, 0, 0, 2, 0, 0, 0, 3]   # Base Scheme (8 Q)
proposed_counts= [2, 2, 1, 2, 2, 3, 2, 1, 1, 3]   # Proposed Scheme (19 Q)

x     = np.arange(len(categories))
width = 0.35

bars1 = ax3.bar(x - width/2, base_counts,     width,
                label='Base Scheme  (8 queries)',
                color=MED_BLUE, edgecolor=DARK_BLUE, linewidth=0.8, alpha=0.88)
bars2 = ax3.bar(x + width/2, proposed_counts, width,
                label='Proposed Scheme — Revised-Anonymity  (19 queries)',
                color=PURPLE, edgecolor='#4A235A', linewidth=0.8, alpha=0.88)

for bars, col in [(bars1, DARK_BLUE), (bars2, '#4A235A')]:
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax3.text(bar.get_x() + bar.get_width() / 2., h + 0.07,
                     str(int(h)), ha='center', va='bottom',
                     fontsize=9, fontweight='bold', color=col)

ax3.set_ylabel('Verified Security Properties', fontsize=11, fontweight='bold')
ax3.set_title(
    'Security Property Coverage — Formal ProVerif Verification\n'
    'Base Scheme vs. Proposed Scheme (Revised-Anonymity)',
    fontsize=13, fontweight='bold', color=DARK_BLUE)
ax3.set_xticks(x)
ax3.set_xticklabels(categories, fontsize=8.5)
ax3.set_ylim(0, 4.5)
ax3.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
ax3.legend(fontsize=10, loc='upper right')
ax3.grid(axis='y', alpha=0.3, linestyle='--')

fig3.tight_layout()
out3 = os.path.join(OUT_DIR, 'revised_security_coverage.png')
fig3.savefig(out3, dpi=200, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
plt.close(fig3)
print(f"[3/4] Saved: {out3}")


# =====================================================================
# FIGURE 4 — Query Distribution (Pie charts, 2-panel: Base vs Proposed)
# =====================================================================
fig4, axes = plt.subplots(1, 2, figsize=(12, 6))

def draw_pie(ax, sizes, labels, colors, title, total):
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct='%1.0f%%', startangle=90,
        textprops={'fontsize': 10},
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5})
    for at in autotexts:
        at.set_fontsize(9.5)
        at.set_fontweight('bold')
    ax.set_title(f'{title}\n{total} Queries — All TRUE',
                 fontsize=12, fontweight='bold', color=DARK_BLUE, pad=12)

draw_pie(axes[0],
         [3, 2, 3],
         ['Auth (3)', 'Secrecy (2)', 'Weak Sec (3)'],
         [MED_BLUE, '#5DADE2', '#AED6F1'],
         'Base Scheme', 8)

draw_pie(axes[1],
         [9, 7, 3],
         ['Auth (9)', 'Secrecy (7)', 'Weak Sec (3)'],
         [PURPLE, '#A569BD', '#D7BDE2'],
         'Proposed Scheme\n(Revised-Anonymity)', 19)

fig4.suptitle(
    'ProVerif Query Distribution & Results\n'
    'All Verified TRUE under Dolev-Yao Active Attacker Model',
    fontsize=13, fontweight='bold', color=DARK_BLUE, y=1.02)
fig4.tight_layout()
out4 = os.path.join(OUT_DIR, 'revised_query_distribution.png')
fig4.savefig(out4, dpi=200, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
plt.close(fig4)
print(f"[4/4] Saved: {out4}")

print("\nAll 4 snapshots generated.")
print(f"Output directory: {OUT_DIR}")
