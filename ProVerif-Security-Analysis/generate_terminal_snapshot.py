"""
generate_terminal_snapshot.py
Generates a terminal-style ProVerif output snapshot for the Revised-Anonymity
Scheme — suitable for direct inclusion in a research paper (like Fig. 4 style).

Output: ProVerif-Security-Analysis/revised_terminal_output.png
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Terminal colour palette ──────────────────────────────────────────────────
BG     = '#1E1E1E'   # dark background
FG     = '#D4D4D4'   # default text
GREEN  = '#4EC94E'   # "true"
CYAN   = '#569CD6'   # "Query / Weak secret"
YELLOW = '#DCDCAA'   # event / secret names
PURPLE = '#C586C0'   # header
WHITE  = '#FFFFFF'

# ── Content: (prefix_kw, query_text, suffix, result)  ────────────────────────
# For blank separator rows just use None.
ENTRIES = [
    # (keyword,        main query text,                                                           result_word)
    ('header',  'Verification summary:',                                                          None),
    None,
    ('Query ', 'inj-event(DeviceEnrolled(id_D_3,id_AS_3)) ==>\n'
               '      inj-event(DeviceEnrollmentStarts(id_D_3,id_AS_3)) is',                     'true.'),
    None,
    ('Query ', 'inj-event(ASEnrollmentCompletes(id_AS_3,id_D_3)) ==>\n'
               '      inj-event(ASEnrollmentStarts(id_AS_3,id_D_3)) is',                         'true.'),
    None,
    ('Query ', 'inj-event(DeviceAuthRound1Done(id_D_3,id_AS_3)) ==>\n'
               '      inj-event(DeviceAuthStarts(id_D_3,id_AS_3)) is',                           'true.'),
    None,
    ('Query ', 'inj-event(ASAuthCompletes(id_AS_3,id_D_3)) ==>\n'
               '      inj-event(ASAuthStarts(id_AS_3,id_D_3)) is',                               'true.'),
    None,
    ('Query ', 'inj-event(DeviceKeyExDone(id_D_3,id_AS_3)) ==>\n'
               '      inj-event(DeviceKeyExStarts(id_D_3,id_AS_3)) is',                          'true.'),
    None,
    ('Query ', 'inj-event(ASKeyExCompletes(id_AS_3,id_D_3)) ==>\n'
               '      inj-event(ASKeyExStarts(id_AS_3,id_D_3)) is',                              'true.'),
    None,
    ('Query ', 'inj-event(AuthRound2Full(id_D_3,id_AS_3,R_D_4,m_D_2)) ==>\n'
               '      inj-event(AuthRound1Full(id_D_3,id_AS_3,R_D_4,m_D_2)) is',                'true.'),
    None,
    ('Query ', 'inj-event(GWTokenReceived(pid_1,id_AS_3)) ==>\n'
               '      inj-event(ASTokenSent(pid_1,id_AS_3)) is',                                 'true.'),
    None,
    ('Query ', 'event(GWDataAccepted(pid_1,id_D_3)) ==>\n'
               '      event(DeviceDataSent(pid_1,id_D_3)) is',                                   'true.'),
    None,
    ('Query ', 'not attacker(SecretK_GW_D_Device[]) is',                                         'true.'),
    None,
    ('Query ', 'not attacker(SecretK_GW_D_AS[]) is',                                             'true.'),
    None,
    ('Query ', 'not attacker(SecretK_GW_D_GW[]) is',                                             'true.'),
    None,
    ('Query ', 'not attacker(SecretM_New[]) is',                                                  'true.'),
    None,
    ('Query ', 'not attacker(SecretR_D[]) is',                                                    'true.'),
    None,
    ('Query ', 'not attacker(SecretID_D[]) is',                                                   'true.'),
    None,
    ('Query ', 'not attacker(SecretTs2[]) is',                                                    'true.'),
    None,
    ('Weak secret ', 'SecretK_GW_D_Device is',                                                   'true.'),
    None,
    ('Weak secret ', 'SecretK_GW_D_AS is',                                                       'true.'),
    None,
    ('Weak secret ', 'SecretK_GW_D_GW is',                                                       'true.'),
]

# ── Pre-process into display lines ──────────────────────────────────────────
# Each display line is one of:
#   ('blank',)
#   ('header', text)
#   ('result', kw, body_line, result_or_None)
#   ('cont',   text)          ← continuation lines (indented, no keyword)

display_lines = []
for entry in ENTRIES:
    if entry is None:
        display_lines.append(('blank',))
        continue
    kw, body, result = entry
    if kw == 'header':
        display_lines.append(('header', body))
        continue
    lines = body.split('\n')
    first = lines[0]
    rest  = lines[1:]
    display_lines.append(('result', kw, first, result if not rest else None))
    for i, cont in enumerate(rest):
        is_last = (i == len(rest) - 1)
        display_lines.append(('cont', cont, result if is_last else None))

# ── Figure geometry ──────────────────────────────────────────────────────────
FONT_PT   = 9.2      # points
LINE_PTS  = 14.5     # leading in points
PAD_L     = 12       # left padding in points
PAD_T     = 32       # top padding (title bar) in points
PAD_B     = 10

fig_w_in  = 11.0
DPI       = 200

total_lines = len(display_lines)
fig_h_in  = (PAD_T + PAD_B + total_lines * LINE_PTS) / 72.0   # 72 pt per inch
fig_h_in  = max(fig_h_in, 3.5)

fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_axis_off()

# We'll work in figure-points via transform=fig.transFigure after converting
# to figure fractions.
W_pt = fig_w_in * 72
H_pt = fig_h_in * 72

def frac_x(pt):  return pt / W_pt
def frac_y(pt):  return pt / H_pt

# ── Title bar ────────────────────────────────────────────────────────────────
title_y_pt = H_pt - PAD_T / 2
for xi_pt, col in [(16, '#FF5F57'), (28, '#FEBC2E'), (40, '#28C840')]:
    ax.plot(frac_x(xi_pt), frac_y(title_y_pt), 'o',
            color=col, markersize=5,
            transform=fig.transFigure, clip_on=False)

ax.text(0.5, frac_y(title_y_pt),
        'ProVerif  —  Revised-Anonymity Scheme  (19 queries verified)',
        color='#AAAAAA', fontsize=7.5, ha='center', va='center',
        fontfamily='monospace', transform=fig.transFigure)

# Separator line below title bar
sep_y = frac_y(H_pt - PAD_T)
fig.add_artist(plt.Line2D([0.01, 0.99], [sep_y, sep_y],
               color='#444444', linewidth=0.8,
               transform=fig.transFigure, clip_on=False))

# ── Render content lines ──────────────────────────────────────────────────────
cursor_y_pt = H_pt - PAD_T - LINE_PTS   # top of first content line

def place(x_pt, y_pt, text, color, bold=False):
    weight = 'bold' if bold else 'normal'
    ax.text(frac_x(x_pt), frac_y(y_pt), text,
            color=color, fontsize=FONT_PT, fontfamily='monospace',
            fontweight=weight, va='center',
            transform=fig.transFigure, clip_on=False)

# Measure character width (monospace — all chars same width)
# We approximate: at FONT_PT pt with monospace, ~0.60× pt per char is typical.
CHAR_W = FONT_PT * 0.602   # points per character

for dl in display_lines:
    cy = cursor_y_pt
    kind = dl[0]

    if kind == 'blank':
        cursor_y_pt -= LINE_PTS * 0.55   # half-height blank
        continue

    if kind == 'header':
        place(PAD_L, cy, dl[1], PURPLE, bold=True)

    elif kind == 'result':
        _, kw, body, result = dl
        x = PAD_L
        place(x, cy, kw, CYAN)
        x += len(kw) * CHAR_W
        place(x, cy, body, FG)
        if result is not None:
            x += len(body) * CHAR_W + CHAR_W
            place(x, cy, result, GREEN)

    elif kind == 'cont':
        _, body, result = dl
        x = PAD_L
        place(x, cy, body, FG)
        if result is not None:
            x += len(body) * CHAR_W + CHAR_W
            place(x, cy, result, GREEN)

    cursor_y_pt -= LINE_PTS

# Outer border
border = mpatches.FancyBboxPatch(
    (0.005, 0.005), 0.990, 0.990,
    boxstyle='round,pad=0.005',
    linewidth=1.0, edgecolor='#555555',
    facecolor='none', transform=fig.transFigure, clip_on=False)
fig.add_artist(border)

# ── Save ─────────────────────────────────────────────────────────────────────
out = os.path.join(OUT_DIR, 'revised_terminal_output.png')
fig.savefig(out, dpi=DPI, bbox_inches='tight', pad_inches=0.05,
            facecolor=BG, edgecolor='none')
plt.close(fig)
print(f"Saved: {out}")
