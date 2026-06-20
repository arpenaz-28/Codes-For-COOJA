#!/usr/bin/env python3
"""
aggregate_e2e.py — aggregate the end-to-end MIRACL vs Python runs harvested by
batch_e2e.py and produce a comparison table + grouped-bar chart.

Reads:  Hardware/MIRACLE/e2e/<scheme>/<mode>/run_*.json
Writes: Hardware/MIRACLE/e2e_aggregate.json
        Hardware/MIRACLE/hw_e2e_miracl_vs_python.png
        Hardware/MIRACLE/hw_e2e_miracl.png   (MIRACL-only, paper-style)

Per-round = the recurring Auth(+KeyEx/Ack) cost reported by each device driver.
Energy model: wall_time x 3.8 W (unchanged from the existing hardware charts).
"""
import os, glob, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
E2E  = os.path.join(HERE, "e2e")
SCHEMES = ["Proposed", "DAuth", "LAAKA", "Zhou"]
MODES   = ["miracl", "python"]

E_KEYS = ("avg_ak_energy_j", "avg_aa_energy_j", "avg_auth_energy_j")
T_KEYS = ("avg_ak_time_s",   "avg_aa_time_s",   "avg_auth_time_s")

COLORS  = {"Proposed": "#2C6FAC", "DAuth": "#7E5BA6", "LAAKA": "#B85C2C", "Zhou": "#3A7D44"}
HATCHES = {"Proposed": "///", "DAuth": "...", "LAAKA": "\\\\", "Zhou": "xxx"}


def _pick(summary, keys):
    for k in keys:
        if k in summary:
            return summary[k]
    return None


def load():
    data = {s: {m: {"e": [], "t": []} for m in MODES} for s in SCHEMES}
    for s in SCHEMES:
        for m in MODES:
            for f in sorted(glob.glob(os.path.join(E2E, s, m, "run_*.json"))):
                with open(f) as fh:
                    summ = json.load(fh).get("summary", {})
                e = _pick(summ, E_KEYS); t = _pick(summ, T_KEYS)
                if e is not None: data[s][m]["e"].append(e)
                if t is not None: data[s][m]["t"].append(t)
    return data


def agg(data):
    out = {}
    for s in SCHEMES:
        out[s] = {}
        for m in MODES:
            e = np.array(data[s][m]["e"]); t = np.array(data[s][m]["t"])
            out[s][m] = {
                "n": int(len(e)),
                "e_mean": float(e.mean()) if len(e) else None,
                "e_std":  float(e.std(ddof=1)) if len(e) > 1 else 0.0,
                "t_mean": float(t.mean()) if len(t) else None,
                "t_std":  float(t.std(ddof=1)) if len(t) > 1 else 0.0,
            }
    return out


def table(a):
    print("\nPer-round Auth(+KeyEx/Ack) — mean over runs  (energy = wall x 3.8 W)")
    print(f"{'Scheme':<10} {'MIRACL J':>12} {'Python J':>12} {'dJ %':>8} "
          f"{'MIRACL s':>11} {'Python s':>11} {'n':>4}")
    for s in SCHEMES:
        mi, py = a[s]["miracl"], a[s]["python"]
        if mi["e_mean"] is None or py["e_mean"] is None:
            print(f"{s:<10} (incomplete)"); continue
        d = 100 * (mi["e_mean"] - py["e_mean"]) / py["e_mean"]
        print(f"{s:<10} {mi['e_mean']:>12.6f} {py['e_mean']:>12.6f} {d:>8.1f} "
              f"{mi['t_mean']:>11.4f} {py['t_mean']:>11.4f} {mi['n']:>4}")


def chart_compare(a):
    x = np.arange(len(SCHEMES)); w = 0.38
    fig, (axe, axt) = plt.subplots(1, 2, figsize=(12, 5))
    for ax, key, sd, lab in [(axe, "e_mean", "e_std", "Energy per round (J)"),
                             (axt, "t_mean", "t_std", "Time per round (s)")]:
        mi = [a[s]["miracl"][key] or 0 for s in SCHEMES]
        py = [a[s]["python"][key] or 0 for s in SCHEMES]
        mie = [a[s]["miracl"][sd] for s in SCHEMES]
        pye = [a[s]["python"][sd] for s in SCHEMES]
        ax.bar(x - w/2, mi, w, yerr=mie, capsize=3, label="MIRACL",
               color="#2C6FAC", edgecolor="black", linewidth=0.6)
        ax.bar(x + w/2, py, w, yerr=pye, capsize=3, label="Python",
               color="#B85C2C", edgecolor="black", linewidth=0.6, alpha=0.85)
        ax.set_xticks(x); ax.set_xticklabels(SCHEMES)
        ax.set_ylabel(lab, fontweight="bold")
        ax.yaxis.grid(True, ls="--", lw=0.5, color="#ddd"); ax.set_axisbelow(True)
        ax.legend()
    fig.suptitle("End-to-end per round: MIRACL vs Python crypto (real TCP, RPi 4B)",
                 fontweight="bold")
    fig.tight_layout()
    out = os.path.join(HERE, "hw_e2e_miracl_vs_python.png")
    fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    print("Saved:", out)


def chart_miracl(a):
    """MIRACL-only, dual panel in the existing paper chart style."""
    x = np.arange(len(SCHEMES))
    fig, (axe, axt) = plt.subplots(1, 2, figsize=(11, 5))
    for ax, key, sd, lab, ttl in [(axe, "e_mean", "e_std", "Energy (J)", "(a)"),
                                  (axt, "t_mean", "t_std", "Time (s)", "(b)")]:
        vals = [a[s]["miracl"][key] or 0 for s in SCHEMES]
        errs = [a[s]["miracl"][sd] for s in SCHEMES]
        for i, s in enumerate(SCHEMES):
            ax.bar(i, vals[i], 0.45, facecolor="none", edgecolor=COLORS[s],
                   hatch=HATCHES[s], linewidth=1.5)
            ax.errorbar(i, vals[i], yerr=errs[i], fmt="none", ecolor="#555", capsize=3)
            ax.text(i, vals[i] + max(vals)*0.02, f"{vals[i]:.3f}", ha="center",
                    va="bottom", fontsize=11, fontweight="bold", color=COLORS[s])
        ax.set_xticks(x); ax.set_xticklabels(SCHEMES)
        ax.set_ylabel(lab, fontweight="bold"); ax.set_title(ttl, fontweight="bold")
        ax.yaxis.grid(True, ls="--", lw=0.5, color="#ddd"); ax.set_axisbelow(True)
        ax.set_ylim(0, max(vals)*1.25)
    fig.suptitle("End-to-end per-round cost — MIRACL crypto over real TCP (RPi 4B)",
                 fontweight="bold", y=1.02)
    fig.tight_layout()
    out = os.path.join(HERE, "hw_e2e_miracl.png")
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    print("Saved:", out)


def main():
    data = load()
    a = agg(data)
    with open(os.path.join(HERE, "e2e_aggregate.json"), "w") as f:
        json.dump(a, f, indent=2)
    table(a)
    chart_compare(a)
    chart_miracl(a)


if __name__ == "__main__":
    main()
