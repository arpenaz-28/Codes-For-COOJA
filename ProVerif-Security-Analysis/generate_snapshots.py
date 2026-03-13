"""
Generate ProVerif Security Analysis Snapshots & Comparison
- Extended Scheme results table
- Base vs Extended comparison table
- Security property coverage chart
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ===================== COLOR PALETTE =====================
DARK_BLUE = '#1A3C6E'
MED_BLUE  = '#2E5FA1'
LIGHT_BLUE = '#E8EEF6'
GREEN     = '#27AE60'
GREEN_BG  = '#E8F8F0'
WHITE     = '#FFFFFF'
GRAY_BG   = '#F5F5F5'
RED       = '#E74C3C'

# ===================== FIGURE 1: EXTENDED SCHEME VERIFICATION SUMMARY =====================
fig1, ax1 = plt.subplots(figsize=(14, 10))
ax1.axis('off')
ax1.set_title('ProVerif Verification Summary — Anonymity-Extended-Base-Scheme\n(PUF-based IoT Authentication with Dual-State Storage)',
              fontsize=14, fontweight='bold', color=DARK_BLUE, pad=20)

ext_data = [
    ['Q1',  'inj-event(DeviceEnrolled) ==>\ninj-event(DeviceEnrollmentStarts)',    'Enrollment Integrity\n(Device)',         'TRUE'],
    ['Q2',  'inj-event(ASEnrollmentCompletes) ==>\ninj-event(ASEnrollmentStarts)',  'Enrollment Integrity\n(AS)',             'TRUE'],
    ['Q3',  'inj-event(DeviceAuthenticated) ==>\ninj-event(DeviceAuthStarts)',      'Device Authentication\nCorrespondence',  'TRUE'],
    ['Q4',  'inj-event(ASAuthCompletes) ==>\ninj-event(ASAuthStarts)',              'AS Authentication\nCorrespondence',      'TRUE'],
    ['Q5',  'inj-event(AuthEndsFull) ==>\ninj-event(AuthStartsFull)',               'Full Auth + Crypto Binding\n(Replay Resistance)', 'TRUE'],
    ['Q6',  'inj-event(GWTokenReceived) ==>\ninj-event(ASTokenSent)',               'Token Forwarding\nIntegrity',            'TRUE'],
    ['Q7',  'event(GWDataAccepted) ==>\nevent(DeviceDataSent)',                     'End-to-End Data\nAuthenticity',          'TRUE'],
    ['Q8',  'not attacker(SecretK_GW_D_Device)',                                   'Session Key Secrecy\n(Device)',          'TRUE'],
    ['Q9',  'not attacker(SecretK_GW_D_AS)',                                       'Session Key Secrecy\n(AS)',              'TRUE'],
    ['Q10', 'not attacker(SecretK_GW_D_GW)',                                       'Session Key Secrecy\n(GW)',              'TRUE'],
    ['Q11', 'not attacker(SecretM_New)',                                            'Session Seed\nSecrecy',                 'TRUE'],
    ['Q12', 'not attacker(SecretR_D)',                                              'PUF Response\nSecrecy',                 'TRUE'],
    ['Q13', 'not attacker(SecretID_D)',                                             'Device Anonymity\n(Identity Secrecy)',   'TRUE'],
    ['Q14', 'weaksecret SecretK_GW_D_Device',                                      'Offline Guessing\n(Device Key)',         'TRUE'],
    ['Q15', 'weaksecret SecretK_GW_D_AS',                                          'Offline Guessing\n(AS Key)',             'TRUE'],
    ['Q16', 'weaksecret SecretK_GW_D_GW',                                          'Offline Guessing\n(GW Key)',             'TRUE'],
]

col_labels = ['#', 'ProVerif Query', 'Security Property', 'Result']
col_widths = [0.04, 0.44, 0.18, 0.07]

table1 = ax1.table(cellText=ext_data, colLabels=col_labels, colWidths=col_widths,
                   loc='center', cellLoc='center')
table1.auto_set_font_size(False)
table1.set_fontsize(7.5)
table1.scale(1.0, 2.2)

# Style header
for j in range(len(col_labels)):
    cell = table1[0, j]
    cell.set_facecolor(DARK_BLUE)
    cell.set_text_props(color=WHITE, fontweight='bold', fontsize=9)
    cell.set_edgecolor(WHITE)

# Style data rows
for i in range(1, len(ext_data) + 1):
    bg = WHITE if i % 2 == 1 else LIGHT_BLUE
    for j in range(len(col_labels)):
        cell = table1[i, j]
        cell.set_facecolor(bg)
        cell.set_edgecolor('#CCCCCC')
        if j == 3:  # Result column
            cell.set_text_props(color=GREEN, fontweight='bold', fontsize=9)
        elif j == 1:
            cell.set_text_props(fontsize=7, family='monospace')

fig1.tight_layout()
fig1.savefig(os.path.join(OUT_DIR, 'extended_scheme_proverif_results.png'), dpi=200, bbox_inches='tight',
             facecolor=WHITE, edgecolor='none')
plt.close(fig1)
print("[1/4] Saved: extended_scheme_proverif_results.png")


# ===================== FIGURE 2: BASE VS EXTENDED COMPARISON TABLE =====================
fig2, ax2 = plt.subplots(figsize=(15, 12))
ax2.axis('off')
ax2.set_title('ProVerif Security Analysis — Base Scheme vs. Extended Scheme Comparison',
              fontsize=14, fontweight='bold', color=DARK_BLUE, pad=20)

# Comparison data: Security Property | Base Scheme | Extended Scheme
comp_data = [
    # -- Authentication Correspondence --
    ['Enrollment Integrity (Device)',             'TRUE\n(NodeEnrolled ==> NodeEnrollmentStarts)',          'TRUE\n(DeviceEnrolled ==> DeviceEnrollmentStarts)'],
    ['Enrollment Integrity (AS)',                 '--\n(Not verified)',                                    'TRUE\n(ASEnrollmentCompletes ==> ASEnrollmentStarts)'],
    ['Device Auth Correspondence',                'TRUE\n(NodeAuthenticated ==> NodeAuthenticationStarts)', 'TRUE\n(DeviceAuthenticated ==> DeviceAuthStarts)'],
    ['AS Auth Correspondence',                    'TRUE\n(AuthenticatorEnds ==> AuthenticatorStarts)',      'TRUE\n(ASAuthCompletes ==> ASAuthStarts)'],
    ['Full Auth + Crypto Binding\n(Replay Resistance)', 'TRUE\n(AuthEndsFull ==> AuthStartsFull)',          'TRUE\n(AuthEndsFull ==> AuthStartsFull)'],
    # -- Token & End-to-End --
    ['Token Forwarding Integrity',                '--\n(Not verified)',                                    'TRUE\n(GWTokenReceived ==> ASTokenSent)'],
    ['End-to-End Data Authenticity',              '--\n(Not verified)',                                    'TRUE\n(GWDataAccepted ==> DeviceDataSent)'],
    # -- Key Exchange --
    ['Key Exchange Correspondence',               'TRUE\n(KeyUpdateEnds ==> KeyUpdateStarts)',             '--\n(Implicit via token + data)'],
    # -- Secrecy --
    ['Session Key Secrecy (Device)',              'TRUE\n(SecretK_GW\'_N_N)',                              'TRUE\n(SecretK_GW_D_Device)'],
    ['Session Key Secrecy (AS)',                  'TRUE\n(SecretK_GW\'_N_Ath)',                             'TRUE\n(SecretK_GW_D_AS)'],
    ['Session Key Secrecy (GW)',                  '--\n(Not verified separately)',                          'TRUE\n(SecretK_GW_D_GW)'],
    ['Updated Key Secrecy',                       'TRUE\n(SecretK_GW\'_N_Update)',                         '--\n(No DH update; key derived\nfreshly each session)'],
    ['Session Seed (m_new) Secrecy',              '--\n(Not verified)',                                    'TRUE\n(SecretM_New)'],
    ['PUF Response Secrecy',                      '--\n(Not verified)',                                    'TRUE\n(SecretR_D)'],
    ['Device Anonymity\n(Identity Secrecy)',       '--\n(Not verified)',                                    'TRUE\n(SecretID_D)'],
    # -- Weak Secrecy --
    ['Weak Secrecy (Device Key)',                 'TRUE\n(SecretK_GW\'_N_N)',                              'TRUE\n(SecretK_GW_D_Device)'],
    ['Weak Secrecy (AS Key)',                     'TRUE\n(SecretK_GW\'_N_Ath)',                             'TRUE\n(SecretK_GW_D_AS)'],
    ['Weak Secrecy (GW/Updated Key)',             'TRUE\n(SecretK_GW\'_N_Update)',                         'TRUE\n(SecretK_GW_D_GW)'],
]

comp_col_labels = ['Security Property', 'Base Scheme (8+3 queries)', 'Extended Scheme (13+3 queries)']
comp_col_widths = [0.22, 0.32, 0.32]

table2 = ax2.table(cellText=comp_data, colLabels=comp_col_labels, colWidths=comp_col_widths,
                   loc='center', cellLoc='center')
table2.auto_set_font_size(False)
table2.set_fontsize(7.5)
table2.scale(1.0, 2.2)

# Style header
for j in range(len(comp_col_labels)):
    cell = table2[0, j]
    cell.set_facecolor(DARK_BLUE)
    cell.set_text_props(color=WHITE, fontweight='bold', fontsize=9)
    cell.set_edgecolor(WHITE)

# Style data rows
for i in range(1, len(comp_data) + 1):
    bg = WHITE if i % 2 == 1 else LIGHT_BLUE
    for j in range(len(comp_col_labels)):
        cell = table2[i, j]
        cell.set_edgecolor('#CCCCCC')
        txt = comp_data[i-1][j]
        if j == 0:
            cell.set_facecolor(bg)
            cell.set_text_props(fontweight='bold', fontsize=7.5)
        elif 'TRUE' in txt:
            cell.set_facecolor(GREEN_BG if j == 2 else bg)
            cell.set_text_props(color=GREEN, fontsize=7)
        elif txt.startswith('--'):
            cell.set_facecolor('#FFF5F5' if j == 1 else GRAY_BG)
            cell.set_text_props(color='#999999', fontsize=7, fontstyle='italic')

fig2.tight_layout()
fig2.savefig(os.path.join(OUT_DIR, 'base_vs_extended_comparison.png'), dpi=200, bbox_inches='tight',
             facecolor=WHITE, edgecolor='none')
plt.close(fig2)
print("[2/4] Saved: base_vs_extended_comparison.png")


# ===================== FIGURE 3: SECURITY PROPERTY COVERAGE BAR CHART =====================
fig3, ax3 = plt.subplots(figsize=(10, 6))

categories = [
    'Enrollment\nIntegrity',
    'Authentication\nCorrespondence',
    'Replay\nResistance',
    'Token/Data\nIntegrity',
    'Session Key\nSecrecy',
    'PUF/Seed\nSecrecy',
    'Device\nAnonymity',
    'Weak Secrecy\n(Guessing)',
]

base_counts    = [1, 3, 1, 0, 2, 0, 0, 3]   # Base scheme verified counts
ext_counts     = [2, 2, 1, 2, 3, 2, 1, 3]   # Extended scheme verified counts

x = np.arange(len(categories))
width = 0.35

bars1 = ax3.bar(x - width/2, base_counts, width, label='Base Scheme (11 queries)',
                color=MED_BLUE, edgecolor=DARK_BLUE, linewidth=0.8)
bars2 = ax3.bar(x + width/2, ext_counts, width, label='Extended Scheme (16 queries)',
                color=GREEN, edgecolor='#1E8449', linewidth=0.8)

ax3.set_ylabel('Number of Verified Properties', fontsize=11, fontweight='bold')
ax3.set_title('Security Property Coverage — Base vs. Extended Scheme',
              fontsize=13, fontweight='bold', color=DARK_BLUE)
ax3.set_xticks(x)
ax3.set_xticklabels(categories, fontsize=8.5)
ax3.set_ylim(0, 4.5)
ax3.legend(fontsize=10, loc='upper right')
ax3.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
ax3.grid(axis='y', alpha=0.3)

# Add value labels
for bar in bars1:
    h = bar.get_height()
    if h > 0:
        ax3.text(bar.get_x() + bar.get_width()/2., h + 0.08, str(int(h)),
                 ha='center', va='bottom', fontsize=9, fontweight='bold', color=DARK_BLUE)
for bar in bars2:
    h = bar.get_height()
    if h > 0:
        ax3.text(bar.get_x() + bar.get_width()/2., h + 0.08, str(int(h)),
                 ha='center', va='bottom', fontsize=9, fontweight='bold', color='#1E8449')

fig3.tight_layout()
fig3.savefig(os.path.join(OUT_DIR, 'security_coverage_comparison.png'), dpi=200, bbox_inches='tight',
             facecolor=WHITE, edgecolor='none')
plt.close(fig3)
print("[3/4] Saved: security_coverage_comparison.png")


# ===================== FIGURE 4: TOTAL QUERIES SUMMARY (PIE + COUNTS) =====================
fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(12, 5))

# Base scheme
base_labels = ['Authentication\n(5)', 'Secrecy\n(3)', 'Weak Secrecy\n(3)']
base_sizes  = [5, 3, 3]
base_colors = [MED_BLUE, '#5DADE2', '#AED6F1']
ax4a.pie(base_sizes, labels=base_labels, colors=base_colors, autopct='%1.0f%%',
         startangle=90, textprops={'fontsize': 10})
ax4a.set_title('Base Scheme\n11 Queries — All TRUE', fontsize=12, fontweight='bold', color=DARK_BLUE)

# Extended scheme
ext_labels = ['Authentication\n(7)', 'Secrecy\n(6)', 'Weak Secrecy\n(3)']
ext_sizes  = [7, 6, 3]
ext_colors = [GREEN, '#58D68D', '#ABEBC6']
ax4b.pie(ext_sizes, labels=ext_labels, colors=ext_colors, autopct='%1.0f%%',
         startangle=90, textprops={'fontsize': 10})
ax4b.set_title('Extended Scheme\n16 Queries — All TRUE', fontsize=12, fontweight='bold', color='#1E8449')

fig4.suptitle('ProVerif Query Distribution & Results', fontsize=14, fontweight='bold', color=DARK_BLUE, y=1.02)
fig4.tight_layout()
fig4.savefig(os.path.join(OUT_DIR, 'query_distribution.png'), dpi=200, bbox_inches='tight',
             facecolor=WHITE, edgecolor='none')
plt.close(fig4)
print("[4/4] Saved: query_distribution.png")

print("\nAll 4 snapshots generated successfully!")
print(f"Output directory: {OUT_DIR}")
