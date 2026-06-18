"""
plot_theoretical_tables.py

Reproduce the paper's four theoretical-analysis tables and add Banerjee et al. as
an additional comparison row.

Reference timings (avg. 100 iterations, Pycrypto / Windows — same as paper):
  T_rand = 0.0018 ms   T_puf  = 0.0522 ms
  T_hash = 0.0353 ms   T_aes  = 0.0867 ms
  T_fe   = 4.45  ms    (fuzzy extractor — estimated by scaling Banerjee et al.'s
                        measured T_fe/T_h ratio (63.075/0.5 ≈ 126×) to our T_hash)

Communication normalisation (same as paper):
  IDs / timestamps = 32 bits
  Hashes / nonces / challenges / ciphertexts = 256 bits

Existing rows (exactly as in Paper/paper_revised_anonymity.tex):
  Tab. A (Enrol comp):  LAAKA, Zhou, DAuth, Proposed
  Tab. B (Auth comp):   LAAKA, Zhou, DAuth, Proposed
  Tab. C (Enrol comm):  LAAKA, Zhou, DAuth, Proposed
  Tab. D (Auth comm):   LAAKA, Zhou, DAuth, Proposed

Banerjee row derived from:
  IEEE Access 2019, Table II — Auth: 31T_h + 2T_fe (U: 17T_h+T_fe; SD: 6T_h+T_fe; GWN: 8T_h)
  Enrol: GWN 8T_h + U 2T_h = 10T_h (no T_fe or T_puf in enrolment)
  Comm:  Normalised from their 2048-bit (160-bit hash) layout → 256-bit hash basis

Writes:
  Results/COOJA-Simulation/Banerjee-Comparison/theoretical_tables.png
  (LaTeX table snippets also printed to stdout)
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ── Reference timings ─────────────────────────────────────────────────────────
T = dict(rand=0.0018, puf=0.0522, h=0.0353, aes=0.0867, fe=4.45)

def cost(*pairs):
    """Sum: cost('h',11, 'aes',2, 'rand',1)"""
    it = iter(pairs)
    return round(sum(T[k]*n for k, n in zip(it, it)), 2)

# ── Table A: Computational Cost — Enrolment ───────────────────────────────────
# Paper rows: LAAKA 0.11, Zhou 0.13, DAuth 0.15, Proposed 0.18
# Banerjee enrol: GWN 8T_h + U 2T_h = 10T_h (no T_puf/T_fe in enrol phase)
#   cost = 10 × 0.0353 = 0.35 ms

COMP_ENROLL = [
    # (scheme,  operations LaTeX,                                          cost ms)
    ("LAAKA",
     r"$3T_\mathsf{hash}$",
     cost('h',3)),
    ("Zhou et al.",
     r"$T_\mathsf{puf}+2T_\mathsf{hash}+3T_\mathsf{rand}$",
     cost('puf',1,'h',2,'rand',3)),
    ("DAuth",
     r"$2T_\mathsf{puf}+1T_\mathsf{hash}+4T_\mathsf{rand}$",
     cost('puf',2,'h',1,'rand',4)),
    ("Proposed",
     r"$2T_\mathsf{puf}+2T_\mathsf{hash}+4T_\mathsf{rand}$",
     cost('puf',2,'h',2,'rand',4)),
    ("Banerjee et al.",
     r"$10T_\mathsf{hash}$",
     cost('h',10)),
]

# ── Table B: Computational Cost — Auth & Key Exchange ─────────────────────────
# Paper rows: LAAKA 0.56, Zhou 0.53, DAuth 0.56, Proposed 0.67
# Banerjee auth: 31T_h + 2T_fe (total all entities)
#   U: 17T_h + T_fe; SD: 6T_h + T_fe; GWN: 8T_h (during auth round? No — GWN not active in auth)
#   Auth-round total (U+SD only): 23T_h + 2T_fe + [GWN 8T_h at enrol, not per-round]
#   Paper counts enrol & auth separately, so per-round auth = 23T_h + 2T_fe for active entities
#   But Banerjee paper cites 31T_h + 2T_fe total — includes GWN's one-time enrol hashes
#   We follow the paper's convention: use their cited per-round auth total = 31T_h + 2T_fe

COMP_AUTH = [
    ("LAAKA",
     r"$16T_\mathsf{hash}$",
     cost('h',16)),
    ("Zhou et al.",
     r"$15T_\mathsf{hash}$",
     cost('h',15)),
    ("DAuth",
     r"$2T_\mathsf{puf}+8T_\mathsf{hash}+2T_\mathsf{aes}+T_\mathsf{rand}$",
     cost('puf',2,'h',8,'aes',2,'rand',1)),
    ("Proposed",
     r"$2T_\mathsf{puf}+11T_\mathsf{hash}+2T_\mathsf{aes}+T_\mathsf{rand}$",
     cost('puf',2,'h',11,'aes',2,'rand',1)),
    ("Banerjee et al.",
     r"$31T_\mathsf{hash}+2T_\mathsf{fe}$",
     cost('h',31,'fe',2)),
]

# ── Table C: Communication Cost — Enrolment ───────────────────────────────────
# Paper: IDs/timestamps = 32b; hashes/nonces/challenges/ciphertexts = 256b
# Paper rows: LAAKA 2592, Zhou 1344, DAuth 1312, Proposed 1312
#
# Banerjee enrol messages (from paper protocol, normalised):
#   Msg 1  U→GWN:  ID_U(32) + H1(256) + r_U_PUF(256) + T1(32)   = 576 b
#   Msg 2  GWN→U:  PID_0(256) + A_U(256) + B_U(256)              = 768 b
#   Msg 3  GWN→SD: ID_U(32) + PID_0(256) + A_U(256) + B_U(256)  = 800 b
#   Total: 3 messages, 576+768+800 = 2144 b

COMM_ENROLL = [
    ("LAAKA",       3, 2592),
    ("Zhou et al.", 5, 1344),
    ("DAuth",       3, 1312),
    ("Proposed",    3, 1312),
    ("Banerjee et al.", 3, 2144),
]

# ── Table D: Communication Cost — Auth & Key Exchange ─────────────────────────
# Paper rows: LAAKA 2400, Zhou 2464, DAuth 928, Proposed 1376
#
# Banerjee auth messages (from paper protocol, normalised to 256b hashes):
#   Msg 1  U→SD:  PID_0(256)+M1(256)+M2(256)+M3(256)+M4(256)+T2(32)  = 1312 b
#   Msg 2  SD→U:  N1(256)+N2(256)+T3(32)                              =  544 b
#   Msg 3  U→SD:  ACK_val(256)+PID_new(256)                           =  512 b
#   Total: 3 messages, 2368 b
#
# (Cross-check: paper uses 160-bit SHA-1 → 2048 b; proportionally 2048×(256/160)=3277 b.
#  Our figure 2368 b comes from counting fields directly in the protocol messages;
#  we use the field-count method for consistency with all other rows in this table.)

COMM_AUTH = [
    ("LAAKA",       3, 2400),
    ("Zhou et al.", 4, 2464),
    ("DAuth",       3,  928),
    ("Proposed",    3, 1376),
    ("Banerjee et al.", 3, 2368),
]

# ── LaTeX output ──────────────────────────────────────────────────────────────
TIMING_NOTE = (r"$T_\mathsf{rand}$=0.0018\,ms, $T_\mathsf{puf}$=0.0522\,ms, "
               r"$T_\mathsf{hash}$=0.0353\,ms, $T_\mathsf{aes}$=0.0867\,ms, "
               r"$T_\mathsf{fe}$=4.45\,ms (est.).")
COMM_NOTE   = r"IDs/timestamps = 32\,b; hashes/nonces/challenges/ciphertexts = 256\,b."

def print_latex():
    sep = "=" * 70

    print(f"\n{sep}\nLaTeX — Table A: Computational Cost (Enrolment)\n{sep}")
    print(r"""\begin{table}[!t]
  \centering
  \caption{Computational Cost Comparison: Enrolment Phase.}
  \label{tab:comp_enroll}
  \scriptsize
  \setlength{\tabcolsep}{3pt}
  \begin{tabular}{lll}
    \toprule
    Scheme & Operations & Cost (ms) \\
    \midrule""")
    for scheme, ops, c in COMP_ENROLL:
        bold = (scheme == "Proposed")
        row = f"    {scheme} & {ops} & {c:.2f} \\\\"
        if bold:
            row = row.replace(scheme, f"\\textbf{{{scheme}}}")
            row = row.replace(f"{c:.2f}", f"\\textbf{{{c:.2f}}}")
        print(row)
    print(r"""    \bottomrule
  \end{tabular}\\[3pt]
  \scriptsize
  Benchmark (avg.\ 100 iterations): """ + TIMING_NOTE + r"""
\end{table}""")

    print(f"\n{sep}\nLaTeX — Table B: Computational Cost (Auth + Key Exchange)\n{sep}")
    print(r"""\begin{table}[!t]
  \centering
  \caption{Computational Cost Comparison: Authentication \& Key Exchange Phase.}
  \label{tab:comp_auth}
  \scriptsize
  \setlength{\tabcolsep}{3pt}
  \begin{tabular}{lll}
    \toprule
    Scheme & Operations & Cost (ms) \\
    \midrule""")
    for scheme, ops, c in COMP_AUTH:
        bold = (scheme == "Proposed")
        row = f"    {scheme} & {ops} & {c:.2f} \\\\"
        if bold:
            row = row.replace(scheme, f"\\textbf{{{scheme}}}")
            row = row.replace(f"{c:.2f}", f"\\textbf{{{c:.2f}}}")
        print(row)
    print(r"""    \bottomrule
  \end{tabular}\\[3pt]
  \scriptsize
  Benchmark (avg.\ 100 iterations): """ + TIMING_NOTE + r"""
\end{table}""")

    print(f"\n{sep}\nLaTeX — Table C: Communication Cost (Enrolment)\n{sep}")
    print(r"""\begin{table}[!t]
  \centering
  \caption{Communication Cost Comparison: Enrolment Phase.}
  \label{tab:comm_enroll}
  \scriptsize
  \setlength{\tabcolsep}{3pt}
  \begin{tabular}{lcc}
    \toprule
    Scheme & \# Messages & Cost (bits) \\
    \midrule""")
    for scheme, msgs, bits in COMM_ENROLL:
        bold = (scheme == "Proposed")
        row = f"    {scheme} & {msgs} & {bits} \\\\"
        if bold:
            row = row.replace(scheme, f"\\textbf{{{scheme}}}")
            row = row.replace(str(bits), f"\\textbf{{{bits}}}")
        print(row)
    print(r"""    \bottomrule
  \end{tabular}\\[3pt]
  \scriptsize
  """ + COMM_NOTE + r"""
\end{table}""")

    print(f"\n{sep}\nLaTeX — Table D: Communication Cost (Auth + Key Exchange)\n{sep}")
    print(r"""\begin{table}[!t]
  \centering
  \caption{Communication Cost Comparison: Auth.\ \& Key Exchange Phase.}
  \label{tab:comm_auth}
  \scriptsize
  \setlength{\tabcolsep}{3pt}
  \begin{tabular}{lcc}
    \toprule
    Scheme & \# Messages & Cost (bits) \\
    \midrule""")
    for scheme, msgs, bits in COMM_AUTH:
        bold = (scheme == "Proposed")
        row = f"    {scheme} & {msgs} & {bits} \\\\"
        if bold:
            row = row.replace(scheme, f"\\textbf{{{scheme}}}")
            row = row.replace(str(bits), f"\\textbf{{{bits}}}")
        print(row)
    print(r"""    \bottomrule
  \end{tabular}\\[3pt]
  \scriptsize
  """ + COMM_NOTE + r"""
\end{table}""")

# ── Matplotlib figure ─────────────────────────────────────────────────────────
C_PROPOSED  = "#1a5c96"   # dark blue header for Proposed rows
C_BANERJEE  = "#8b1a1a"   # dark red header for Banerjee rows
C_HDR       = "#2C6FAC"   # general header blue
C_HDR_TXT   = "white"
C_SEC_HDR   = "#dde8f4"   # section subheader
C_ODD       = "#f5f8fc"
C_EVN       = "white"
C_TOTAL     = "#e8f0fa"   # totals / subtotals

def make_table(ax, rows, col_headers, title, col_widths=None):
    """Draw a table inside ax using FancyBboxPatch cells."""
    ax.axis("off")
    ax.set_title(title, fontsize=10, fontweight="bold", pad=6, loc="left")

    n_cols = len(col_headers)
    n_rows = len(rows)

    if col_widths is None:
        col_widths = [1.0 / n_cols] * n_cols
    total_w = sum(col_widths)
    col_widths = [w / total_w for w in col_widths]

    xs    = [sum(col_widths[:i]) for i in range(n_cols)]
    ROW_H = 1.0 / (n_rows + 1)   # +1 for header

    def cell(x, y, w, h, text, bg, fg="black", fs=8.2, bold=False, align="left"):
        rect = FancyBboxPatch((x, y), w, h,
                              boxstyle="square,pad=0",
                              linewidth=0.35, edgecolor="#aaaaaa",
                              facecolor=bg, zorder=2,
                              transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)
        ha = "center" if align == "center" else "left"
        tx = x + 0.012 if align == "left" else x + w / 2
        ax.text(tx, y + h / 2, text,
                ha=ha, va="center", fontsize=fs,
                fontweight="bold" if bold else "normal",
                color=fg, transform=ax.transAxes, clip_on=False)

    # Header row
    y_hdr = 1.0 - ROW_H
    for ci, (hdr, x, w) in enumerate(zip(col_headers, xs, col_widths)):
        cell(x, y_hdr, w, ROW_H, hdr, C_HDR, C_HDR_TXT,
             bold=True, align="center")

    # Data rows
    for ri, row in enumerate(rows):
        label = row[0]
        vals  = row[1:]
        y     = 1.0 - ROW_H * (ri + 2)

        is_proposed  = (label == "Proposed")
        is_banerjee  = (label == "Banerjee et al.")
        bg_row = (C_TOTAL  if is_proposed else
                  C_SEC_HDR if is_banerjee else
                  C_ODD    if ri % 2 == 0 else C_EVN)

        cell(xs[0], y, col_widths[0], ROW_H, label, bg_row,
             bold=(is_proposed or is_banerjee), fs=8.2)

        for ci, (val, x, w) in enumerate(zip(vals, xs[1:], col_widths[1:]), 1):
            # colour the cost column: green = better (lower), red = worse (higher)
            fg = "black"
            if ci == len(col_headers) - 1:   # last col = cost/bits
                try:
                    v = float(str(val).replace(",", ""))
                    # find min across data rows (skip header)
                    all_vals = [float(str(r[-1]).replace(",","")) for r in rows]
                    if v == min(all_vals):
                        fg = "#1a6e1a"
                    elif v == max(all_vals):
                        fg = "#aa1111"
                except ValueError:
                    pass
            cell(x, y, w, ROW_H, str(val), bg_row, fg=fg,
                 bold=(is_proposed or is_banerjee), align="center")

def main():
    print_latex()

    REPO    = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
    OUT_DIR = os.path.join(REPO, "Results", "COOJA-Simulation", "Banerjee-Comparison")
    os.makedirs(OUT_DIR, exist_ok=True)

    fig = plt.figure(figsize=(14, 16))
    fig.patch.set_facecolor("white")

    # Lay out four table panels (two rows of two)
    panels = [
        (COMP_ENROLL,
         ["Scheme", "Operations", "Cost (ms)"],
         "Table A — Computational Cost: Enrolment",
         [3.5, 4.5, 1.0]),
        (COMP_AUTH,
         ["Scheme", "Operations", "Cost (ms)"],
         "Table B — Computational Cost: Authentication & Key Exchange",
         [3.5, 4.5, 1.0]),
        (COMM_ENROLL,
         ["Scheme", "# Messages", "Cost (bits)"],
         "Table C — Communication Cost: Enrolment",
         [4.0, 1.5, 1.5]),
        (COMM_AUTH,
         ["Scheme", "# Messages", "Cost (bits)"],
         "Table D — Communication Cost: Authentication & Key Exchange",
         [4.0, 1.5, 1.5]),
    ]

    positions = [
        [0.03, 0.52, 0.44, 0.46],   # Table A — top left
        [0.53, 0.52, 0.44, 0.46],   # Table B — top right
        [0.03, 0.04, 0.44, 0.46],   # Table C — bottom left
        [0.53, 0.04, 0.44, 0.46],   # Table D — bottom right
    ]

    for (rows, hdrs, title, cw), pos in zip(panels, positions):
        ax = fig.add_axes(pos)
        make_table(ax, rows, hdrs, title, col_widths=cw)

    # Legend note at bottom
    fig.text(0.5, 0.01,
             "Benchmark: $T_{rand}$=0.0018 ms,  $T_{puf}$=0.0522 ms,  "
             "$T_{hash}$=0.0353 ms,  $T_{aes}$=0.0867 ms,  "
             "$T_{fe}$=4.45 ms (est.)  |  "
             "Comm: IDs/timestamps=32 b; hashes/nonces=256 b",
             ha="center", va="bottom", fontsize=7.5, color="#444444",
             style="italic")

    out = os.path.join(OUT_DIR, "theoretical_tables.png")
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    print(f"\nFigure saved → {out}")

    # Summary to stdout
    print("\n── Computed values ─────────────────────────────────────────────")
    print(f"  T_hash={T['h']}, T_puf={T['puf']}, T_aes={T['aes']}, "
          f"T_rand={T['rand']}, T_fe={T['fe']}")
    print("\n  Computational cost (ms):")
    for s, ops, c in COMP_ENROLL:
        print(f"    Enrol  {s:20s}  {c:.2f} ms")
    for s, ops, c in COMP_AUTH:
        print(f"    Auth   {s:20s}  {c:.2f} ms")
    print("\n  Communication cost (bits):")
    for s, m, b in COMM_ENROLL:
        print(f"    Enrol  {s:20s}  {m} msgs  {b} bits")
    for s, m, b in COMM_AUTH:
        print(f"    Auth   {s:20s}  {m} msgs  {b} bits")

if __name__ == "__main__":
    main()
