#!/usr/bin/env python3
"""
batch_e2e.py — drive the end-to-end hardware sims for all four schemes in BOTH
crypto modes (MIRACL .so vs Python baseline), interleaved in one session so the
two modes see the same network conditions (network latency dominates and varies
between sessions). Harvests each per-device run JSON into:

    Hardware/MIRACLE/e2e/<scheme>/<mode>/run_<NN>.json

Usage:  python batch_e2e.py [n_runs]   (default 5)
"""
import os, sys, json, shutil, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
HW   = os.path.dirname(HERE)
OUT  = os.path.join(HERE, "e2e")

# scheme -> (dir, orchestrator, result json basename produced in <dir>/results/)
SCHEMES = {
    "Proposed": ("Proposed", "run_simulation.py"),
    "LAAKA":    ("LAAKA",    "run_simulation.py"),
    "Zhou":     ("Zhou",     "run_simulation.py"),
    "DAuth":    ("DAuth",    "run_dauth_simulation.py"),
}

def run_one(scheme, mode, run_idx):
    sub, orch = SCHEMES[scheme]
    sdir = os.path.join(HW, sub)
    env = os.environ.copy()
    env["USE_MIRACL"] = "1" if mode == "miracl" else "0"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # run number passed to orchestrator (overwrites <dir>/results/run_<N>.json)
    rn = run_idx
    p = subprocess.run([sys.executable, orch, str(rn)], cwd=sdir, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    src = os.path.join(sdir, "results", f"run_{rn:02d}.json")
    dst_dir = os.path.join(OUT, scheme, mode)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"run_{run_idx:02d}.json")
    ok = os.path.exists(src)
    if ok:
        shutil.copy(src, dst)
        with open(src) as f:
            s = json.load(f).get("summary", {})
        # pick whichever per-round avg key exists
        e = next((s[k] for k in ("avg_ak_energy_j","avg_aa_energy_j","avg_auth_energy_j") if k in s), None)
        t = next((s[k] for k in ("avg_ak_time_s","avg_aa_time_s","avg_auth_time_s") if k in s), None)
        print(f"  [{scheme:8} {mode:6} #{run_idx}]  {e:.6f} J  {t:.4f} s")
    else:
        tail = (p.stdout or "")[-400:] + (p.stderr or "")[-400:]
        print(f"  [{scheme:8} {mode:6} #{run_idx}]  FAILED (no json). tail:\n{tail}")
    return ok

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"=== Batch end-to-end: {n} runs x 4 schemes x 2 modes ===")
    summary = {}
    for run_idx in range(1, n + 1):
        for mode in ("miracl", "python"):
            for scheme in SCHEMES:
                ok = run_one(scheme, mode, run_idx)
                summary.setdefault((scheme, mode), 0)
                summary[(scheme, mode)] += int(ok)
                time.sleep(1.0)
    print("\n=== completed runs ===")
    for (scheme, mode), c in sorted(summary.items()):
        print(f"  {scheme:8} {mode:6}: {c}/{n}")

if __name__ == "__main__":
    main()
