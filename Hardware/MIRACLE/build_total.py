#!/usr/bin/env python3
"""
build_total.py — fresh same-session MIRACL end-to-end TOTAL cost per scheme,
summing the FULL set of phases each respective paper defines:

  Proposed / DAuth : Device Enrollment + Authentication + Key Exchange
  LAAKA                 : IoT-device Registration + Fog-server Registration
                          + Mutual Authentication & Key Exchange (Auth + Ack)
  Zhou                  : User Registration + Sensor-Node Registration
                          + Authentication & Key Exchange (M1->M4)

Registrations are one-time; Auth/KeyExch is one session (per-round mean).
Energy = wall_time x 3.8 W (3800 mW). All crypto via MIRACL Core on the RPi nodes.

Usage:  python build_total.py [n_runs]   (default 5)
"""
import os, sys, json, subprocess
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))


def clean_results(folder):
    import glob
    for p in glob.glob(os.path.join(HERE, folder, "results", "run_*.json")) \
           + glob.glob(os.path.join(HERE, folder, "results", "fogreg_*.json")) \
           + glob.glob(os.path.join(HERE, folder, "results", "snreg_*.json")):
        try:
            os.remove(p)
        except OSError:
            pass


def run_folder(folder, orch, n):
    clean_results(folder)
    for i in range(1, n + 1):
        env = os.environ.copy()
        env.update(USE_MIRACL="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        subprocess.run([sys.executable, orch, str(i)], cwd=os.path.join(HERE, folder),
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


def load(folder, name):
    p = os.path.join(HERE, folder, "results", name)
    return json.load(open(p)) if os.path.exists(p) else None


def round_mean(rounds, ekey, tkey):
    return (st.mean(r[ekey] for r in rounds), st.mean(r[tkey] for r in rounds))


def per_run_total(folder, i, scheme):
    """Return (total_energy_j, total_time_s, breakdown dict) for run i, or None."""
    r = load(folder, f"run_{i:02d}.json")
    if r is None:
        return None
    e = t = 0.0
    bd = {}

    # registration phase(s)
    en = r["enrollment"]
    e += en["energy_j"]; t += en["wall_s"]; bd["reg1"] = (en["energy_j"], en["wall_s"])

    if scheme == "LAAKA":
        fr = load(folder, f"fogreg_{i:02d}.json")
        if fr is None:
            return None
        e += fr["energy_j"]; t += fr["wall_s"]; bd["reg2(fog)"] = (fr["energy_j"], fr["wall_s"])
    elif scheme == "Zhou":
        sr = load(folder, f"snreg_{i:02d}.json")
        if sr is None:
            return None
        e += sr["energy_j"]; t += sr["wall_s"]; bd["reg2(sn)"] = (sr["energy_j"], sr["wall_s"])

    # authentication + key exchange (one session = per-round mean)
    rounds = r["rounds"]
    ae, at = round_mean(rounds, "auth_energy_j", "auth_s")
    e += ae; t += at; bd["auth"] = (ae, at)
    if scheme == "LAAKA":
        # LAAKA's key agreement = Auth + Ack (mutual authentication & key exchange)
        ke, kt = round_mean(rounds, "ack_energy_j", "ack_s")
        e += ke; t += kt; bd["keyex(ack)"] = (ke, kt)
    # Proposed / DAuth: session key is established WITHIN the Auth (D<->AS)
    #   exchange; the separate D<->GW key-confirmation handshake and the Data
    #   phase are NOT counted in the Enrollment+Auth+KeyExch total.
    # Zhou: M1->M4 is a single combined auth+key step, already counted in auth.

    return e, t, bd


SCHEMES = [
    ("Proposed",   "Proposed", "run_simulation.py"),
    ("DAuth", "DAuth",    "run_simulation.py"),
    ("LAAKA",      "LAAKA",    "run_simulation.py"),
    ("Zhou",       "Zhou",     "run_simulation.py"),
]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"=== Fresh same-session MIRACL end-to-end TOTAL: {n} runs x 4 schemes ===\n")
    results = {}
    for label, folder, orch in SCHEMES:
        print(f"[run] {label} ...", flush=True)
        run_folder(folder, orch, n)
        tot_e, tot_t, last_bd = [], [], {}
        for i in range(1, n + 1):
            pr = per_run_total(folder, i, label)
            if pr:
                tot_e.append(pr[0]); tot_t.append(pr[1]); last_bd = pr[2]
        if not tot_e:
            print(f"  {label}: NO DATA"); continue
        results[label] = {
            "n": len(tot_e),
            "total_energy_j_median": st.median(tot_e),
            "total_energy_j_mean": st.mean(tot_e),
            "total_energy_sd": st.stdev(tot_e) if len(tot_e) > 1 else 0.0,
            "total_time_s_median": st.median(tot_t),
            "total_time_s_mean": st.mean(tot_t),
            "total_time_sd": st.stdev(tot_t) if len(tot_t) > 1 else 0.0,
            "breakdown_last_run": last_bd,
        }
        print(f"  {label}: {results[label]['n']} runs, "
              f"median total = {results[label]['total_energy_j_median']:.4f} J / "
              f"{results[label]['total_time_s_median']:.4f} s")

    json.dump(results, open(os.path.join(HERE, "table_total_miracl.json"), "w"), indent=2)

    print("\n\n### End-to-end TOTAL scheme cost (MIRACL, per respective paper) — "
          f"median of {n} runs (mean in parens)\n")
    print("| Scheme | Phases summed | Total Energy (J) | Total Time (s) |")
    print("|---|---|---|---|")
    phase_txt = {
        "Proposed":   "Enroll + Auth + KeyEx",
        "DAuth": "Enroll + Auth + KeyEx",
        "LAAKA":      "DevReg + FogReg + Auth + Ack",
        "Zhou":       "UserReg + SNReg + Auth&KeyEx",
    }
    for label, *_ in SCHEMES:
        if label not in results:
            continue
        d = results[label]
        print(f"| {label} | {phase_txt[label]} | "
              f"{d['total_energy_j_median']:.4f} (mean {d['total_energy_j_mean']:.4f}) | "
              f"{d['total_time_s_median']:.4f} (mean {d['total_time_s_mean']:.4f}) |")

    print("\nPer-run phase breakdown (last run, Energy J / Time s):")
    for label, *_ in SCHEMES:
        if label not in results:
            continue
        bd = results[label]["breakdown_last_run"]
        parts = "  ".join(f"{k}={v[0]:.4f}J/{v[1]:.4f}s" for k, v in bd.items())
        print(f"  {label:11}: {parts}")


if __name__ == "__main__":
    main()
