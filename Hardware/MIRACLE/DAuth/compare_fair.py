#!/usr/bin/env python3
"""
compare_fair.py — run Proposed and DAuth end-to-end interleaved in ONE
session (same network conditions) with MIRACL, and compare per-round Auth+KeyEx
energy/time and the KeyEx phase specifically.

Usage:  python compare_fair.py [n_runs]   (default 6)
"""
import os, sys, json, subprocess, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
HW   = os.path.dirname(os.path.dirname(HERE))   # .../Hardware

TARGETS = {
    "Proposed":  (os.path.join(HW, "Proposed"),      "run_simulation.py", "results"),
    "DAuth": (HERE,                              "run_simulation.py", "results"),
}

def run(name, idx):
    sdir, orch, resdir = TARGETS[name]
    env = os.environ.copy()
    env.update(USE_MIRACL="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, orch, str(idx)], cwd=sdir, env=env,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    p = os.path.join(sdir, resdir, f"run_{idx:02d}.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    ak_e = d["summary"].get("avg_ak_energy_j")
    ak_t = d["summary"].get("avg_ak_time_s")
    ke = [r["ke_s"] for r in d["rounds"] if "ke_s" in r]
    au = [r["auth_s"] for r in d["rounds"] if "auth_s" in r]
    return ak_e, ak_t, st.mean(ke) if ke else None, st.mean(au) if au else None

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    acc = {k: {"ak_e": [], "ak_t": [], "ke": [], "au": []} for k in TARGETS}
    for i in range(1, n + 1):
        for name in TARGETS:
            r = run(name, i)
            if r is None:
                print(f"  [{name} #{i}] FAILED"); continue
            ak_e, ak_t, ke, au = r
            acc[name]["ak_e"].append(ak_e); acc[name]["ak_t"].append(ak_t)
            acc[name]["ke"].append(ke);     acc[name]["au"].append(au)
            print(f"  [{name:9} #{i}]  AK={ak_e:.4f} J  auth={au*1000:5.1f} ms  keyex={ke*1000:5.1f} ms")
    print("\n=== means over runs (MIRACL, same session) ===")
    print(f"{'scheme':10} {'AK energy J':>12} {'AK time s':>10} {'auth ms':>9} {'keyex ms':>9}")
    out = {}
    for name in TARGETS:
        a = acc[name]
        if not a["ak_e"]:
            continue
        row = dict(ak_energy_j=round(st.mean(a["ak_e"]),6),
                   ak_time_s=round(st.mean(a["ak_t"]),6),
                   auth_ms=round(st.mean(a["au"])*1000,2),
                   keyex_ms=round(st.mean(a["ke"])*1000,2),
                   n=len(a["ak_e"]))
        out[name] = row
        print(f"{name:10} {row['ak_energy_j']:>12.6f} {row['ak_time_s']:>10.4f} "
              f"{row['auth_ms']:>9.1f} {row['keyex_ms']:>9.1f}")
    json.dump(out, open(os.path.join(HERE, "compare_fair_result.json"), "w"), indent=2)
    print("\nSaved:", os.path.join(HERE, "compare_fair_result.json"))

if __name__ == "__main__":
    main()
