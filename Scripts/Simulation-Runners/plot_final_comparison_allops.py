"""
plot_final_comparison_allops.py

Consolidated theoretical computation-cost table for the FOUR main schemes
(LAAKA, Zhou, DAuth, Proposed), counting EVERY cryptographic primitive
explicitly: hash, AES (enc/dec), PUF, fuzzy extractor (FE), random.

Same benchmark timings + methodology as the paper (avg. 100 iterations,
Windows / pycryptodome). T_fe is DIRECTLY MEASURED on this platform for Zhou's
biometric fuzzy extractor (concatenated repetition+BCH code-offset, 15% error
rate, Gen ~= Rep ~= 0.021 ms) -- see bench_fuzzy_extractor_zhou.py:
  T_rand = 0.0018 ms   T_puf  = 0.0522 ms   T_hash = 0.0353 ms
  T_aes  = 0.0867 ms   T_fe   = 0.021  ms  (per Gen or Rep invocation)

Primitive attribution (per each scheme's ORIGINAL paper):
  LAAKA  -- hash + XOR only (LAAKA paper: "uses only secure hash function and
            bitwise XOR"). No PUF / AES / FE.
  Zhou   -- PUF + hash + rand, plus a BIOMETRIC fuzzy extractor: Gen() at
            registration and Rep() at authentication => +1 T_fe each phase.
            (Zhou's own cost section counted hashes only and silently dropped
            the FE; here we charge it.)
  DAuth  -- PUF + hash + AES + rand. PUF modelled directly as T_puf (no
            separate biometric FE step in the protocol).
  Proposed -- PUF + hash + AES + rand. Same PUF model as DAuth.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

T = dict(rand=0.0018, puf=0.0522, h=0.0353, aes=0.0867, fe=0.021)

# Per-scheme TOTAL operation counts = Enrolment + Authentication & Key Exchange.
#   (hash, aes, puf, fe, rand)
# Counts derived directly from each scheme's ORIGINAL protocol (all entities),
# now including random generations (and a Zhou auth-phase PUF) that earlier
# hash-only accounting omitted. AES is NOT a protocol primitive in LAAKA/Zhou
# (both are hash+XOR; LAAKA abstract: "hash function and bitwise XOR"; Zhou
# counts "only hashing operations") -- the AES in their COOJA ports is
# transport/channel encryption, so it is excluded from the theoretical table.
# DAuth/Proposed genuinely use AES (gateway-token enc/dec), so it is counted.
#
# Enrol / Auth breakdown:
#   LAAKA   enrol 3h+2r(r2,r1)         ; auth 16h+2r(r_d,r_f)
#   Zhou    enrol 1puf+2h+3r+1fe(Gen)  ; auth 1puf+15h+3r(b_i^new,b_n^new,SK)+1fe(Rep)
#           (Zhou auth PUF = sensor R_n<-PUF(C_n); 3 fresh randoms at U and GW)
#   DAuth   enrol 2puf+1h+4r           ; auth 2puf+8h+2aes+1r
#   Proposed enrol 2puf+2h+4r          ; auth 2puf+11h+2aes+1r
SCHEMES = [
    # name,        hash, aes, puf, fe, rand
    ("LAAKA",        19,   0,   0,  0,  4),
    ("Zhou et al.",  17,   0,   2,  2,  6),
    ("DAuth",         9,   2,   4,  0,  5),
    ("Proposed",     13,   2,   4,  0,  5),
]

def total_ms(h, aes, puf, fe, rand):
    return round(h*T['h'] + aes*T['aes'] + puf*T['puf'] + fe*T['fe'] + rand*T['rand'], 2)

ROWS = [(n, h, aes, puf, fe, r, total_ms(h, aes, puf, fe, r))
        for (n, h, aes, puf, fe, r) in SCHEMES]

# ── LaTeX ─────────────────────────────────────────────────────────────────────
def print_latex():
    print("="*72)
    print("LaTeX -- Consolidated Computation Cost (all primitives)")
    print("="*72)
    print(r"""\begin{table}[!t]
  \centering
  \caption{Total Computational Cost (Enrolment + Authentication \& Key Exchange),
           all cryptographic primitives accounted.}
  \label{tab:comp_total}
  \scriptsize
  \setlength{\tabcolsep}{4pt}
  \begin{tabular}{lcccccc}
    \toprule
    Scheme & $T_\mathsf{hash}$ & $T_\mathsf{aes}$ & $T_\mathsf{puf}$ & $T_\mathsf{fe}$ & $T_\mathsf{rand}$ & Total (ms) \\
    \midrule""")
    for (n, h, aes, puf, fe, r, tot) in ROWS:
        nm = f"\\textbf{{{n}}}" if n == "Proposed" else n
        val = f"\\textbf{{{tot:.2f}}}" if n == "Proposed" else f"{tot:.2f}"
        # show 0 counts as dash for readability
        cells = " & ".join(str(x) if x else "--" for x in (h, aes, puf, fe, r))
        print(f"    {nm} & {cells} & {val} \\\\")
    print(r"""    \bottomrule
  \end{tabular}\\[3pt]
  \scriptsize
  $T_\mathsf{rand}$=0.0018, $T_\mathsf{puf}$=0.0522, $T_\mathsf{hash}$=0.0353,
  $T_\mathsf{aes}$=0.0867, $T_\mathsf{fe}$=0.021\,ms (avg.\ 100 iterations).
  $T_\mathsf{aes}$ counts both encryption and decryption; FE is the biometric
  fuzzy extractor (Gen/Rep) present only in Zhou et al.
\end{table}""")

# ── Figure ──────────────────────────────────────────────────────────────────
C_HDR, C_HDR_TXT = "#2C6FAC", "white"
C_PROP = "#e8f0fa"
C_ODD, C_EVN = "#f5f8fc", "white"

def make_fig(out):
    fig = plt.figure(figsize=(9, 3.0)); fig.patch.set_facecolor("white")
    ax = fig.add_axes([0.02, 0.10, 0.96, 0.80]); ax.axis("off")
    ax.set_title("Total Computational Cost — All Primitives (Enrolment + Auth & Key Exchange)",
                 fontsize=11, fontweight="bold", loc="left", pad=8)

    headers = ["Scheme", "$T_{hash}$", "$T_{aes}$", "$T_{puf}$", "$T_{fe}$", "$T_{rand}$", "Total (ms)"]
    cw = [2.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.2]
    tot_w = sum(cw); cw = [w/tot_w for w in cw]
    xs = [sum(cw[:i]) for i in range(len(cw))]
    n_rows = len(ROWS); ROW_H = 1.0/(n_rows+1)

    def cell(x, y, w, h, txt, bg, fg="black", bold=False, align="center"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0",
                     linewidth=0.35, edgecolor="#aaaaaa", facecolor=bg,
                     transform=ax.transAxes, clip_on=False))
        ha = "left" if align == "left" else "center"
        tx = x+0.012 if align == "left" else x+w/2
        ax.text(tx, y+h/2, txt, ha=ha, va="center", fontsize=9,
                fontweight="bold" if bold else "normal", color=fg,
                transform=ax.transAxes)

    y = 1.0-ROW_H
    for hdr, x, w in zip(headers, xs, cw):
        cell(x, y, w, ROW_H, hdr, C_HDR, C_HDR_TXT, bold=True,
             align="left" if hdr == "Scheme" else "center")

    totals = [r[-1] for r in ROWS]
    for ri, (n, h, aes, puf, fe, r, tot) in enumerate(ROWS):
        y = 1.0-ROW_H*(ri+2)
        is_prop = (n == "Proposed")
        bg = C_PROP if is_prop else (C_ODD if ri % 2 == 0 else C_EVN)
        cell(xs[0], y, cw[0], ROW_H, n, bg, bold=is_prop, align="left")
        vals = [h, aes, puf, fe, r]
        for ci, (v, x, w) in enumerate(zip(vals, xs[1:6], cw[1:6]), 1):
            cell(x, y, w, ROW_H, (str(v) if v else "–"), bg, bold=is_prop)
        fg = "#1a6e1a" if tot == min(totals) else ("#aa1111" if tot == max(totals) else "black")
        cell(xs[6], y, cw[6], ROW_H, f"{tot:.2f}", bg, fg=fg, bold=is_prop)

    fig.text(0.5, 0.02,
             "$T_{rand}$=0.0018  $T_{puf}$=0.0522  $T_{hash}$=0.0353  "
             "$T_{aes}$=0.0867  $T_{fe}$=0.021 ms (avg. 100 iter.)  |  "
             "$T_{aes}$ = enc/dec;  FE (biometric Gen/Rep) only in Zhou",
             ha="center", fontsize=7.2, color="#444", style="italic")
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    print(f"\nFigure saved -> {out}")

def main():
    print_latex()
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = os.path.join(REPO, "Results", "COOJA-Simulation", "Theoretical-Comparison")
    os.makedirs(out_dir, exist_ok=True)
    make_fig(os.path.join(out_dir, "total_computation_allops.png"))
    print("\nTotals (ms):")
    for (n, h, aes, puf, fe, r, tot) in ROWS:
        print(f"  {n:14s} hash={h:2d} aes={aes} puf={puf} fe={fe} rand={r}  -> {tot:.2f} ms")

if __name__ == "__main__":
    main()
