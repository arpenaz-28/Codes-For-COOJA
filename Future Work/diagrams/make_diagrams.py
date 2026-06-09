# -*- coding: utf-8 -*-
"""
Generate Visio-style sequence diagrams for the AS-Anonymity (Future Work)
scheme, matching the look of the existing scheme diagrams:
  - actor circles on top, vertical lifelines
  - white computation boxes attached to lifelines
  - labelled message arrows (white label box on the arrow)
  - upright serif text with proper subscripts/superscripts

Outputs (into this folder):
  fig_future_enrollment.png
  fig_future_auth.png
  fig_future_keyex.png
  fig_future_notation.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Rectangle, FancyArrowPatch

plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "cm"
plt.rcParams["mathtext.rm"] = "serif"

# ---------- reusable LaTeX (mathtext) fragments -----------------------------
H      = r"\mathrm{H}"
IDD    = r"\mathrm{ID_D}"
IDAS   = r"\mathrm{ID_{AS}}"
RD     = r"\mathrm{R_D}"
RDp    = r"\mathrm{R'_D}"
RASD   = r"\mathrm{R_{AS-D}}"
PHIASD = r"\Phi_{\mathrm{AS-D}}"
PUFD   = r"\mathrm{PUF_D}"
PUFAS  = r"\mathrm{PUF_{AS}}"
yD     = r"\mathrm{y_D}"
YD     = r"\mathrm{Y_D}"
cD     = r"\mathrm{c_D}"
cASD   = r"\mathrm{c_{AS-D}}"
mD     = r"\mathrm{m_D}"
mcurr  = r"\mathrm{m_{curr}}"
mold   = r"\mathrm{m_{old}}"
mnew   = r"\mathrm{m_{new}}"
mused  = r"\mathrm{m_{used}}"
PID    = r"\mathrm{PID}"
PIDcurr= r"\mathrm{PID_{curr}}"
PIDold = r"\mathrm{PID_{old}}"
PIDnew = r"\mathrm{PID_{new}}"
TAcc   = r"\mathrm{T_{Acc}}"
YDH    = r"\mathrm{Y^{H}_D}"
YASDH  = r"\mathrm{Y^{H}_{AS-D}}"
mH     = r"\mathrm{m^{H}}"
KGWD   = r"\mathrm{K_{GW-D}}"
KGWAS  = r"\mathrm{K_{GW-AS}}"
ts1    = r"\mathrm{ts_1}"
ts2    = r"\mathrm{ts_2}"
tsa    = r"\mathrm{ts_{auth}}"
SE     = r"\mathrm{SE}"
SD     = r"\mathrm{SD}"
n1     = r"\mathrm{n_1}"
eps    = r"\varepsilon"
oxor   = r"\oplus"
PP     = r"\,\|\,"
AMP    = r"\ \&\ "
PIDASc = r"\mathrm{PID^{curr}_{AS}}"
PIDASo = r"\mathrm{PID^{old}_{AS}}"
PIDASn = r"\mathrm{PID^{next}_{AS}}"
PIDASu = r"\mathrm{PID^{used}_{AS}}"
etac   = r"\eta_{\mathrm{curr}}"
etao   = r"\eta_{\mathrm{old}}"
Psi    = r"\Psi"
atok   = r"\mathrm{auth\_token_D}"


def M(*parts):
    return "$" + "".join(parts) + "$"


# ---------- low-level drawing primitives ------------------------------------
LH   = 0.66      # line height (data units)
PAD  = 0.30      # box inner padding
GAP  = 0.55      # vertical gap between stacked elements
FS   = 11        # text font size
SCALE = 0.46     # inches per data unit (controls final pixel size)

NEW_FILL = "#fff6cc"  # pale yellow highlight for new/changed steps


class Diagram:
    def __init__(self, actors, width=14.0):
        # actors: dict name -> x
        self.actors = actors
        self.width = width
        self.ops = []          # deferred draw operations
        self.y = 0.0           # cursor (set after header)
        self.min_y = 0.0
        self.top = 0.0

    # --- layout helpers (compute y, store op) ---
    def box(self, x0, x1, lines, y_top=None, fill="white"):
        if y_top is None:
            y_top = self.y
        h = 2 * PAD + len(lines) * LH
        y_bot = y_top - h
        self.ops.append(("box", x0, x1, y_top, y_bot, lines, fill))
        self.min_y = min(self.min_y, y_bot)
        self.y = y_bot - GAP
        return y_bot

    def msg(self, src, dst, label, width, y=None, fill="white",
            note=None, note_below=None):
        if y is None:
            y = self.y - 0.45
        xs, xd = self.actors[src], self.actors[dst]
        self.ops.append(("msg", xs, xd, y, label, width, fill, note, note_below))
        self.min_y = min(self.min_y, y - 0.55)
        self.y = y - 1.5
        return y

    def gap(self, amt):
        self.y -= amt

    # --- render ---
    def render(self, fname, title=None):
        bottom = self.min_y - 0.7
        self.top = 0.0
        fig_h = (self.top - bottom + 2.0)
        fig = plt.figure(figsize=(self.width * SCALE, fig_h * SCALE))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(-0.3, self.width + 0.3)
        ax.set_ylim(bottom - 0.3, 2.0)
        ax.set_aspect("equal")
        ax.axis("off")

        # actor circles + lifelines (drawn first, behind boxes)
        r = 0.72
        cy = 1.0
        for name, x in self.actors.items():
            ax.add_patch(Ellipse((x, cy), 2 * r, 2 * r,
                                  fill=False, lw=1.4, zorder=3))
            ax.text(x, cy, name, ha="center", va="center",
                    fontsize=15, zorder=4)
            ax.plot([x, x], [cy - r, bottom + 0.2], color="black",
                    lw=1.0, zorder=1)

        # deferred ops
        for op in self.ops:
            if op[0] == "box":
                _, x0, x1, yt, yb, lines, fill = op
                ax.add_patch(Rectangle((x0, yb), x1 - x0, yt - yb,
                                       facecolor=fill, edgecolor="black",
                                       lw=1.2, zorder=5))
                txt = "\n".join(lines)
                ax.text(x0 + PAD, yt - PAD, txt, ha="left", va="top",
                        fontsize=FS, zorder=6, linespacing=1.45)
            elif op[0] == "msg":
                _, xs, xd, y, label, w, fill, note, note_below = op
                # arrow
                arr = FancyArrowPatch((xs, y), (xd, y),
                                      arrowstyle="-|>", mutation_scale=16,
                                      lw=1.3, color="black", zorder=4,
                                      shrinkA=0, shrinkB=0)
                ax.add_patch(arr)
                # label box centred
                xc = (xs + xd) / 2.0
                ax.add_patch(Rectangle((xc - w / 2, y - 0.42), w, 0.84,
                                       facecolor=fill, edgecolor="black",
                                       lw=1.1, zorder=5))
                ax.text(xc, y, label, ha="center", va="center",
                        fontsize=FS, zorder=6)
                if note:
                    ax.text(xc, y + 0.72, note, ha="center", va="center",
                            fontsize=FS - 1.5, style="italic", zorder=6)
                if note_below:
                    ax.text(xc, y - 0.72, note_below, ha="center", va="center",
                            fontsize=FS - 1.5, style="italic", zorder=6)

        if title:
            ax.text(self.width / 2, 1.85, title, ha="center", va="center",
                    fontsize=13, fontweight="bold")

        fig.savefig(fname, dpi=200, bbox_inches="tight",
                    facecolor="white", pad_inches=0.12)
        plt.close(fig)
        print("wrote", fname)


# ===========================================================================
# DIAGRAM 1 — Modified Enrollment Phase  (GW, AS, D)
# ===========================================================================
def enrollment():
    d = Diagram({"GW": 1.9, "AS": 7.3, "D": 12.6}, width=14.4)
    d.y = -0.4

    # GW generates AS pseudonym (NEW)
    d.box(0.15, 9.2, [
        "Generate epoch nonce: " + M(etac),
        M(PIDASc, " = ", H, "(", IDAS, PP, etac, ")"),
        M(PIDASo, " = ", eps),
        "Store {" + M(IDAS) + ", " + M(KGWAS) + ", " + M(PIDASc) + ", "
            + M(PIDASo) + ",",
        "          " + M(etac) + ", " + M(etao, "=", eps) + "}",
    ], fill=NEW_FILL)

    # GW -> AS : AS pseudonym setup (NEW)
    d.msg("GW", "AS", M("(", PIDASc, ")"), width=3.0, fill=NEW_FILL,
          note="AS pseudonym setup")

    d.box(2.6, 9.2, [
        "Store " + M(PIDASc) + ", " + M(PIDASo, "=", eps),
    ], fill=NEW_FILL)

    # D -> AS : registration
    d.msg("D", "AS", "(Registration Request, " + M(IDD) + ")", width=5.6)

    d.box(0.15, 9.2, [
        "Check for the existence of " + M(IDD),
        "Generate challenge: " + M(cD) + "; session-based random: " + M(mD),
    ])

    # AS -> D : challenge + AS pseudonym (CHANGED: PID_AS^curr instead of ID_AS)
    d.msg("AS", "D", M("(", cD, ", ", mD, ", ", PIDASc, ")"), width=3.4,
          fill=NEW_FILL, note_below=r"$\mathrm{PID^{curr}_{AS}}$ replaces $\mathrm{ID_{AS}}$")

    d.box(5.6, 13.0, [
        M(RD, " = ", PUFD, "(", cD, ")"),
        "Generate secret: " + M(yD) + "; challenge: " + M(cASD),
        "Store " + M(yD) + ", " + M(cD) + ", " + M(mcurr, " = ", mD)
            + ", " + M(PIDASc),
    ])

    # D -> AS : commitments
    d.msg("D", "AS", M("(", yD, ", ", RD, ", ", cASD, ")"), width=3.4)

    d.box(0.15, 9.6, [
        M(YD, " = ", H, "(", yD, ")"),
        M(TAcc) + " = " + M(TAcc) + " & " + M(YD),
        M(RASD, " = ", PUFAS, "(", cASD, ")"),
        M(PHIASD, " = ", RASD, oxor, RD),
        "Dual state init: " + M(mold, "=", eps) + ", " + M(mcurr, " = ", mD),
        M(PIDcurr, " = ", H, "(", IDD, PP, mcurr, ")"),
        M(PIDold, " = ", eps),
        "Store " + M(TAcc) + ", {" + M(IDD) + ", " + M(PHIASD) + ", "
            + M(cASD) + ", " + M(mold) + ",",
        "          " + M(mcurr) + ", " + M(PIDold) + ", " + M(PIDcurr) + "}",
    ])

    d.render("fig_future_enrollment.png")


# ===========================================================================
# DIAGRAM 2 — Modified Authentication Phase  (AS, D)
# ===========================================================================
def authentication():
    d = Diagram({"AS": 2.4, "D": 11.8}, width=14.4)
    d.y = -0.4

    d.box(7.2, 13.4, [
        "Read from storage:",
        "  " + M(yD) + ", " + M(cD) + ", " + M(mcurr) + ", " + M(PIDASc),
    ])

    d.box(5.2, 14.2, [
        M(RD, " = ", PUFD, "(", cD, ")"),
        "Generate current timestamp: " + M(ts1),
        M(YDH, " = ", H, "(", yD, ")"),
        M(PID, " = ", H, "(", IDD, PP, mcurr, ")"),
        M(YASDH, " = ", YDH, oxor, H, "(", RD, PP, mcurr, PP, PID, PP,
          PIDASc, PP, ts1, ")"),
    ], fill=NEW_FILL)

    d.msg("D", "AS", M("(", PID, ", ", YASDH, ", ", ts1, ")"), width=3.6,
          note_below=r"$\mathrm{PID^{curr}_{AS}}$ now inside the mask")

    d.box(0.15, 11.0, [
        "Check the freshness of message by " + M(ts1),
        "Lookup device by " + M(PIDold) + " or " + M(PIDcurr),
        "Read " + M(TAcc) + ", {" + M(IDD) + ", " + M(PHIASD) + ", "
            + M(cASD) + ", " + M(mold) + ", " + M(mcurr) + ",",
        "          " + M(PIDold) + ", " + M(PIDcurr) + "}",
        M(RASD, " = ", PUFAS, "(", cASD, ")"),
        M(RD, " = ", PHIASD, oxor, RASD),
        "Try " + M(r"(m,\,PID_{AS})") + " over the four dual-state pairs:",
        "    " + M(r"(", mcurr, ",", PIDASc, r"),\ (", mcurr, ",", PIDASo, "),"),
        "    " + M(r"(", mold, ",", PIDASc, r"),\ (", mold, ",", PIDASo, ")"),
        M(YDH, " = ", YASDH, oxor, H, "(", RD, PP, r"m", PP, PID, PP,
          r"\mathrm{PID_{AS}}", PP, ts1, ")"),
        "If " + M(TAcc) + " & " + M(YDH) + " = " + M(TAcc) + ":  Node Authenticated",
        "      record " + M(mused) + ", " + M(PIDASu),
        "Else:  Not Authenticated",
    ], fill=NEW_FILL)

    d.render("fig_future_auth.png")


# ===========================================================================
# DIAGRAM 3 — Modified Key Exchange Phase  (GW, AS, D)
# ===========================================================================
def keyexchange():
    d = Diagram({"GW": 1.9, "AS": 7.6, "D": 13.0}, width=15.0)
    d.y = -0.4

    d.box(5.6, 9.8, [
        "Read from storage: " + M(KGWAS) + ", " + M(PIDASc),
    ])

    d.box(2.4, 14.6, [
        "Generate random: " + M(n1) + ", timestamps: " + M(ts2) + ", " + M(tsa),
        M(mnew, " = ", H, "(", n1, ")"),
        M(mH, " = ", mnew, oxor, H, "(", YDH, PP, mused, PP, RDp, PP,
          PIDASu, PP, PIDcurr, PP, ts2, ")"),
        M(KGWD, " = ", H, "(", RDp, PP, mnew, ")"),
        M(PIDnew, " = ", H, "(", IDD, PP, mnew, ")"),
        M(Psi, " = ", PIDASc, oxor, H, "(", KGWD, PP, ts2, ")")
            + "      (new)",
        M(atok, " = ", SE, "(", KGWAS, ", (", KGWD, PP, PIDnew, PP, tsa, "))"),
        "Update: " + M(mold, "=", mcurr) + ", " + M(mcurr, "=", mnew)
            + ", " + M(PIDold, "=", PIDcurr) + ", " + M(PIDcurr, "=", PIDnew),
    ], fill=NEW_FILL)

    # two messages branching from AS at the same level
    y_msg = d.y - 0.45
    d.msg("AS", "GW", M("(", PIDnew, ", ", PIDASc, ", ", atok, ")"),
          width=4.8, y=y_msg, fill=NEW_FILL,
          note_below=r"$\mathrm{PID^{curr}_{AS}}$ replaces $\mathrm{ID_{AS}}$")
    d.msg("AS", "D", M("(", mH, ", ", Psi, ", ", ts2, ")"),
          width=3.0, y=y_msg, fill=NEW_FILL, note=r"$\Psi$ is new")
    d.y = y_msg - 1.6

    # GW box (left) and D box (right) at the same starting y
    y_split = d.y
    gw_bot = d.box(0.15, 7.2, [
        "Dual-state AS lookup: find AS with",
        "    received " + M(r"\mathrm{PID_{AS}}") + " in "
            + M(r"\{", PIDASc, r",\ ", PIDASo, r"\}"),
        M(r"\Rightarrow") + " obtain " + M(KGWAS) + ", " + M(IDAS),
        M("(", KGWD, ", ", PIDnew, ", ", tsa, ")"),
        "      " + M("= ", SD, "(", KGWAS, ", ", atok, ")"),
        "Check freshness by " + M(tsa),
        "Store {" + M(PIDold) + ", " + M(PIDcurr) + ", " + M(KGWD)
            + ", " + M(tsa) + "}",
    ], y_top=y_split, fill=NEW_FILL)

    d.box(7.7, 15.2, [
        "Check the freshness of message by " + M(ts2),
        M(mnew, " = ", mH, oxor, H, "(", YDH, PP, mcurr, PP, RD, PP,
          PIDASc, PP, PID, PP, ts2, ")"),
        M(KGWD, " = ", H, "(", RD, PP, mnew, ")"),
        M(PIDASn, " = ", Psi, oxor, H, "(", KGWD, PP, ts2, ")")
            + "   (new)",
        M(PID, " = ", H, "(", IDD, PP, mcurr, ")"),
        "Update: " + M(mcurr, "=", mnew) + ", " + M(PIDcurr, "=", PIDnew) + ",",
        "          " + M(PIDASc, " = ", PIDASn),
        "Store " + M(KGWD),
    ], y_top=y_split, fill=NEW_FILL)

    d.render("fig_future_keyex.png")


# ===========================================================================
# DIAGRAM 4 — Notation Table (simple language)
# ===========================================================================
def notation():
    rows = [
        (M(IDD), "Real identity of the device (kept secret, never sent on air)", False),
        (M(IDAS), "Real identity of the Authentication Server (kept secret, never sent)", True),
        (M(PID) + " = " + M(H, "(", IDD, PP, mcurr, ")"),
         "Device pseudonym: a disposable alias used on air in place of the real device ID", False),
        (M(PIDcurr) + ", " + M(PIDold),
         "Current and previous device pseudonyms (the pair lets a lost packet be recovered)", False),
        (M(PIDASc) + ", " + M(PIDASo),
         "Current and previous AS pseudonyms: disposable alias for the AS (NEW)", True),
        (M(etac) + ", " + M(etao),
         "Secret random numbers the gateway uses to build the AS pseudonym each epoch (NEW)", True),
        (M(Psi),
         "Hidden update that quietly tells the device the AS's new pseudonym (NEW)", True),
        (M(mcurr) + ", " + M(mold) + ", " + M(mnew),
         "Session random numbers; they refresh the pseudonyms after each round", False),
        (M(RD),
         "Device PUF response: a hardware secret regenerated on the fly, never stored", False),
        (M(yD) + ", " + M(PHIASD),
         "Device secret and its PUF-masked form held at the AS", False),
        (M(TAcc),
         "One-way accumulator the AS uses to check group membership", False),
        (M(KGWD),
         "Session key shared between the gateway and the device", False),
        (M(KGWAS),
         "Long-term key shared between the gateway and the AS", False),
        (M(atok),
         "Encrypted token the AS gives the gateway to hand over the device's session", False),
        (M(SE) + ", " + M(SD),
         "Symmetric-key encryption and decryption", False),
        (M(ts1) + ", " + M(ts2) + ", " + M(tsa),
         "Timestamps used to check that a message is fresh (not replayed)", False),
        (M(H, r"(\cdot)") + ",  " + M(oxor) + ",  " + M(r"\|"),
         "One-way hash function, bitwise XOR, and concatenation", False),
    ]

    n = len(rows)
    row_h = 0.62
    fig_w = 15.8
    fig_h = (n + 2) * row_h
    fig = plt.figure(figsize=(fig_w * 0.62, fig_h * 0.62))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    x_sym = 0.25
    x_div = 4.2
    x_txt = 4.45
    top = fig_h - 0.3

    # title
    ax.text(fig_w / 2, top + 0.0, "Notation used in the AS-Anonymity Scheme",
            ha="center", va="top", fontsize=14, fontweight="bold")
    y = top - 0.8

    # header
    ax.add_patch(Rectangle((x_sym - 0.15, y - row_h + 0.12),
                           fig_w - 0.2, row_h,
                           facecolor="#d9d9d9", edgecolor="black", lw=1.0))
    ax.text(x_sym, y - row_h / 2 + 0.12, "Symbol", ha="left", va="center",
            fontsize=12, fontweight="bold")
    ax.text(x_txt, y - row_h / 2 + 0.12, "Meaning (plain language)",
            ha="left", va="center", fontsize=12, fontweight="bold")
    y -= row_h

    for sym, meaning, is_new in rows:
        fill = NEW_FILL if is_new else "white"
        ax.add_patch(Rectangle((x_sym - 0.15, y - row_h + 0.12),
                               fig_w - 0.2, row_h,
                               facecolor=fill, edgecolor="#999999", lw=0.7))
        ax.text(x_sym, y - row_h / 2 + 0.12, sym, ha="left", va="center",
                fontsize=11)
        ax.text(x_txt, y - row_h / 2 + 0.12, meaning, ha="left", va="center",
                fontsize=10.5)
        y -= row_h

    # outer border + vertical divider
    ax.add_patch(Rectangle((x_sym - 0.15, y + 0.12),
                           fig_w - 0.2, top - 0.8 - y,
                           facecolor="none", edgecolor="black", lw=1.3))
    ax.plot([x_div, x_div], [y + 0.12, top - 0.8 + 0.12],
            color="black", lw=1.0)

    ax.text(fig_w / 2, y - 0.15,
            "Shaded rows are new elements introduced for AS anonymity.",
            ha="center", va="top", fontsize=9.5, style="italic")

    fig.savefig("fig_future_notation.png", dpi=200, bbox_inches="tight",
                facecolor="white", pad_inches=0.15)
    plt.close(fig)
    print("wrote fig_future_notation.png")


if __name__ == "__main__":
    enrollment()
    authentication()
    keyexchange()
    notation()
