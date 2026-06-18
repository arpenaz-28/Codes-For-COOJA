"""
plot_comparison_kim_rpi.py

4-scheme computational-cost comparison (LAAKA, Zhou, DAuth, Proposed) using the
Kim et al. (Electronics 2025, Table 3) RPi 4B reference unit costs, EXCLUDING
random-number generation (T_rand) entirely.

Kim et al. RPi 4B (ARM Cortex-A72 @ 1.5 GHz, MIRACL Core):
  T_hash = 0.009 ms   T_aes = 0.004 ms   T_puf = 0.0063 ms   T_fe = T_M = 2.353 ms
  (fuzzy extractor is ECC-based: SHA-256 -> scalar, one P-256 point mult = T_M)

Operation counts (per scheme's original protocol, all entities; T_rand dropped):
  LAAKA     enrol 3h            ; auth 16h                       -> 19h
  Zhou      enrol 1puf+2h+1fe   ; auth 1puf+15h+1fe              -> 17h, 2puf, 2fe
  DAuth     enrol 2puf+1h       ; auth 2puf+8h+2aes              -> 9h, 2aes, 4puf
  Proposed  enrol 2puf+2h       ; auth 2puf+11h+2aes             -> 13h, 2aes, 4puf
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Kim et al. RPi 4B unit costs (ms) -- T_rand excluded
T = dict(h=0.009, aes=0.004, puf=0.0063, fe=2.353)

# (name, hash, aes, puf, fe)
SCHEMES = [
    ("LAAKA",        19, 0, 0, 0),
    ("Zhou et al.",  17, 0, 2, 2),
    ("DAuth",         9, 2, 4, 0),
    ("Proposed",     13, 2, 4, 0),
]

def total(h, aes, puf, fe):
    return round(h*T['h'] + aes*T['aes'] + puf*T['puf'] + fe*T['fe'], 4)

ROWS = [(n, h, aes, puf, fe, total(h, aes, puf, fe)) for (n, h, aes, puf, fe) in SCHEMES]

def print_latex():
    print("="*70)
    print("LaTeX -- Computation Cost (Kim et al. RPi 4B values, T_rand excluded)")
    print("="*70)
    print(r"""\begin{table}[!t]
  \centering
  \caption{Total Computational Cost on RPi 4B (Kim et al.\ \cite{kim2025puf} unit
           costs; random generation excluded).}
  \label{tab:comp_kim}
  \scriptsize
  \setlength{\tabcolsep}{4pt}
  \begin{tabular}{lccccc}
    \toprule
    Scheme & $T_\mathsf{hash}$ & $T_\mathsf{aes}$ & $T_\mathsf{puf}$ & $T_\mathsf{fe}$ & Total (ms) \\
    \midrule""")
    for (n, h, aes, puf, fe, tot) in ROWS:
        nm  = f"\\textbf{{{n}}}" if n == "Proposed" else n
        val = f"\\textbf{{{tot:.3f}}}" if n == "Proposed" else f"{tot:.3f}"
        cells = " & ".join(str(x) if x else "--" for x in (h, aes, puf, fe))
        print(f"    {nm} & {cells} & {val} \\\\")
    print(r"""    \bottomrule
  \end{tabular}\\[3pt]
  \scriptsize
  RPi 4B unit costs \cite{kim2025puf}: $T_\mathsf{hash}$=0.009, $T_\mathsf{aes}$=0.004,
  $T_\mathsf{puf}$=0.0063, $T_\mathsf{fe}$=$T_M$=2.353\,ms. FE is ECC-based
  (one P-256 scalar multiplication); present only in Zhou et al.
\end{table}""")

# ── figure ──────────────────────────────────────────────────────────────────
C_HDR, C_HDR_TXT = "#2C6FAC", "white"
C_PROP, C_ODD, C_EVN = "#e8f0fa", "#f5f8fc", "white"

def make_fig(out):
    fig = plt.figure(figsize=(8.6, 3.0)); fig.patch.set_facecolor("white")
    ax = fig.add_axes([0.02, 0.10, 0.96, 0.80]); ax.axis("off")
    ax.set_title("Computational Cost on RPi 4B — Kim et al. unit costs ($T_{rand}$ excluded)",
                 fontsize=11, fontweight="bold", loc="left", pad=8)
    headers = ["Scheme", "$T_{hash}$", "$T_{aes}$", "$T_{puf}$", "$T_{fe}$", "Total (ms)"]
    cw = [2.2, 1.0, 1.0, 1.0, 1.0, 1.3]; tw = sum(cw); cw = [w/tw for w in cw]
    xs = [sum(cw[:i]) for i in range(len(cw))]
    n = len(ROWS); RH = 1.0/(n+1)
    def cell(x, y, w, h, txt, bg, fg="black", bold=False, align="center"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0",
                     linewidth=0.35, edgecolor="#aaaaaa", facecolor=bg,
                     transform=ax.transAxes, clip_on=False))
        ha = "left" if align == "left" else "center"
        tx = x+0.012 if align == "left" else x+w/2
        ax.text(tx, y+h/2, txt, ha=ha, va="center", fontsize=9.5,
                fontweight="bold" if bold else "normal", color=fg, transform=ax.transAxes)
    y = 1.0-RH
    for hdr, x, w in zip(headers, xs, cw):
        cell(x, y, w, RH, hdr, C_HDR, C_HDR_TXT, bold=True,
             align="left" if hdr == "Scheme" else "center")
    totals = [r[-1] for r in ROWS]
    for ri, (nm, h, aes, puf, fe, tot) in enumerate(ROWS):
        y = 1.0-RH*(ri+2)
        prop = (nm == "Proposed")
        bg = C_PROP if prop else (C_ODD if ri % 2 == 0 else C_EVN)
        cell(xs[0], y, cw[0], RH, nm, bg, bold=prop, align="left")
        for v, x, w in zip([h, aes, puf, fe], xs[1:5], cw[1:5]):
            cell(x, y, w, RH, (str(v) if v else "–"), bg, bold=prop)
        fg = "#1a6e1a" if tot == min(totals) else ("#aa1111" if tot == max(totals) else "black")
        cell(xs[5], y, cw[5], RH, f"{tot:.3f}", bg, fg=fg, bold=prop)
    fig.text(0.5, 0.02,
             "RPi 4B unit costs (Kim et al., MIRACL): $T_{hash}$=0.009  $T_{aes}$=0.004  "
             "$T_{puf}$=0.0063  $T_{fe}$=$T_M$=2.353 ms  |  FE = ECC P-256 mult (Zhou only)",
             ha="center", fontsize=7.2, color="#444", style="italic")
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    print(f"\nFigure saved -> {out}")

def main():
    print_latex()
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = os.path.join(REPO, "Results", "COOJA-Simulation", "Theoretical-Comparison")
    os.makedirs(out_dir, exist_ok=True)
    make_fig(os.path.join(out_dir, "comparison_kim_rpi.png"))
    print("\nTotals (ms):")
    for (nm, h, aes, puf, fe, tot) in ROWS:
        print(f"  {nm:14s} hash={h:2d} aes={aes} puf={puf} fe={fe}  -> {tot:.3f} ms")

if __name__ == "__main__":
    main()
