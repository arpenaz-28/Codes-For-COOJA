#!/usr/bin/env python3
"""
build_table.py — fresh same-session MIRACL end-to-end run of all four schemes
(Proposed, Fair-DAuth, LAAKA, Zhou), aggregating per-phase Energy + Time for
Enrollment, Auth, and KeyExch. Uses the self-contained MIRACLE/<scheme> folders.

Phase mapping (KeyExch column):
  Proposed / Fair-DAuth : KeyEx  (ke_s / ke_energy_j)
  LAAKA                 : Ack    (ack_s / ack_energy_j)   [second half of key agreement]
  Zhou                  : none   (M1->M4 is a combined auth+key step)

Usage:  python build_table.py [n_runs]   (default 5)
"""
import os, sys, json, subprocess
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))

# label -> (folder, orchestrator, auth_keys, key_keys_or_None)
SCHEMES = [
    ("Proposed",   "Proposed", "run_simulation.py", ("auth_s","auth_energy_j"), ("ke_s","ke_energy_j")),
    ("Fair-DAuth", "DAuth",    "run_simulation.py", ("auth_s","auth_energy_j"), ("ke_s","ke_energy_j")),
    ("LAAKA",      "LAAKA",    "run_simulation.py", ("auth_s","auth_energy_j"), ("ack_s","ack_energy_j")),
    ("Zhou",       "Zhou",     "run_simulation.py", ("auth_s","auth_energy_j"), None),
]


def run_scheme(folder, orch, n):
    runs = []
    for i in range(1, n + 1):
        env = os.environ.copy()
        env.update(USE_MIRACL="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        subprocess.run([sys.executable, orch, str(i)], cwd=os.path.join(HERE, folder),
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        p = os.path.join(HERE, folder, "results", f"run_{i:02d}.json")
        if os.path.exists(p):
            try:
                runs.append(json.load(open(p)))
            except Exception:
                pass
    return runs


def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    return st.mean(xs), (st.stdev(xs) if len(xs) > 1 else 0.0)


def agg(runs, auth_keys, key_keys):
    en_e = mean_sd([r["enrollment"]["energy_j"] for r in runs])
    en_t = mean_sd([r["enrollment"]["wall_s"]   for r in runs])
    au_e, au_t, ke_e, ke_t = [], [], [], []
    for r in runs:
        rounds = r["rounds"]
        if not rounds:
            continue
        au_e.append(st.mean(rr[auth_keys[1]] for rr in rounds))
        au_t.append(st.mean(rr[auth_keys[0]] for rr in rounds))
        if key_keys:
            ke_e.append(st.mean(rr[key_keys[1]] for rr in rounds))
            ke_t.append(st.mean(rr[key_keys[0]] for rr in rounds))
    return {
        "enroll": (en_e, en_t),
        "auth":   (mean_sd(au_e), mean_sd(au_t)),
        "key":    (mean_sd(ke_e), mean_sd(ke_t)) if key_keys else (( None,None),(None,None)),
        "n": len(runs),
    }


def fmt(ms):
    m, s = ms
    return "—" if m is None else f"{m:.4f}"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"=== Fresh same-session MIRACL end-to-end: {n} runs x 4 schemes ===\n")
    out = {}
    for label, folder, orch, ak, kk in SCHEMES:
        print(f"[run] {label} ...", flush=True)
        runs = run_scheme(folder, orch, n)
        if not runs:
            print(f"  {label}: NO DATA")
            continue
        out[label] = agg(runs, ak, kk)
        print(f"  {label}: {out[label]['n']} runs collected")

    # save
    js = {lbl: {
        "n": d["n"],
        "enroll_energy_j": d["enroll"][0][0], "enroll_time_s": d["enroll"][1][0],
        "auth_energy_j":   d["auth"][0][0],   "auth_time_s":   d["auth"][1][0],
        "keyex_energy_j":  d["key"][0][0],    "keyex_time_s":  d["key"][1][0],
    } for lbl, d in out.items()}
    json.dump(js, open(os.path.join(HERE, "table_e2e_miracl.json"), "w"), indent=2)

    # markdown table
    print("\n\n### End-to-end (MIRACL) per-phase Energy / Time — mean of "
          f"{n} runs (Fair-DAuth)\n")
    print("| Scheme | Enroll E (J) | Enroll T (s) | Auth E (J) | Auth T (s) | KeyExch E (J) | KeyExch T (s) |")
    print("|---|---|---|---|---|---|---|")
    for label, *_ in SCHEMES:
        if label not in out:
            continue
        d = out[label]
        print(f"| {label} | {fmt(d['enroll'][0])} | {fmt(d['enroll'][1])} | "
              f"{fmt(d['auth'][0])} | {fmt(d['auth'][1])} | "
              f"{fmt(d['key'][0])} | {fmt(d['key'][1])} |")
    print("\nNotes: Auth/KeyExch are per-round means; Enrollment is one-time. "
          "LAAKA KeyExch = Ack phase; Zhou has no separate KeyExch (M1->M4 combined in Auth).")


if __name__ == "__main__":
    main()
