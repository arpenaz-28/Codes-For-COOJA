"""
run_laaka_sim.py
Run the fixed LAAKA scheme in COOJA via Docker (5 seeds).
Extracts ENROLL_ENERGY / AUTH_ENERGY / KEYEX_ENERGY per device.
"""
import subprocess, os, re, csv, time, math, sys

BASE        = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CONTAINER   = "cooja-sim"
PROJECT_DIR = "/home/user/contiki-ng/examples/myproject"
COOJA_DIR   = "/home/user/contiki-ng/tools/cooja"
SEEDS       = [123456, 234567, 345678, 456789, 567890]

SCHEME_PATH = os.path.join(BASE, "LAAKA")
CSC_SRC     = os.path.join(BASE, "LAAKA", "test-sim-100.csc")
SOURCES     = ["aes.c", "aes.h", "sha256.c", "sha256.h",
               "as-node.c", "device-node.c", "gw-node.c",
               "project-conf.h", "Makefile"]

OUTPUT_DIR  = os.path.join(BASE, "Results", "CSV-Data", "LAAKA")
TESTLOG_DIR = os.path.join(BASE, "Results", "Testlogs", "LAAKA")
os.makedirs(OUTPUT_DIR,  exist_ok=True)
os.makedirs(TESTLOG_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
def docker_exec(cmd, timeout=900):
    full = f'docker exec {CONTAINER} bash -c "{cmd}"'
    r = subprocess.run(full, capture_output=True, text=True, shell=True, timeout=timeout)
    return r.stdout + r.stderr, r.returncode

def docker_cp(src, dst):
    r = subprocess.run(f'docker cp "{src}" {CONTAINER}:{dst}',
                       capture_output=True, text=True, shell=True, timeout=30)
    return r.returncode == 0

# ─────────────────────────────────────────────────────────────────────────────
def deploy_and_build():
    print("Deploying fixed LAAKA source to container...")
    docker_exec(f"mkdir -p {PROJECT_DIR} && cd {PROJECT_DIR} && "
                f"rm -f *.c *.h Makefile && rm -rf build")
    for src in SOURCES:
        path = os.path.join(SCHEME_PATH, src)
        if not os.path.exists(path):
            print(f"  MISSING: {path}"); return False
        if not docker_cp(path, f"{PROJECT_DIR}/{src}"):
            print(f"  COPY FAILED: {src}"); return False
        print(f"  Copied {src}")
    print("  Building firmware (TARGET=cooja)...")
    out, rc = docker_exec(f"cd {PROJECT_DIR} && make TARGET=cooja CONTIKI=/home/user/contiki-ng 2>&1", timeout=300)
    if rc != 0:
        print(f"  BUILD FAILED:\n{out[-1200:]}"); return False
    out2, _ = docker_exec(f"ls {PROJECT_DIR}/build/cooja/*.cooja 2>/dev/null")
    built = [l.strip() for l in out2.strip().splitlines() if l.strip().endswith(".cooja")]
    print(f"  Built firmware: {[os.path.basename(b) for b in built]}")
    return len(built) >= 3

def make_csc(seed):
    with open(CSC_SRC, encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'<randomseed>\d+</randomseed>',
                     f'<randomseed>{seed}</randomseed>', content)
    content = re.sub(r'examples/[^/"]+/', 'examples/myproject/', content)
    tmp = os.path.join(BASE, f"_tmp_laaka_{seed}.csc")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    return tmp

def run_sim(csc_container_path):
    cmd = (f"cd {COOJA_DIR} && ./gradlew --no-watch-fs run "
           f"--args='--no-gui --contiki=/home/user/contiki-ng "
           f"--autostart {csc_container_path}' 2>&1")
    t0 = time.time()
    out, rc = docker_exec(cmd, timeout=900)
    elapsed = time.time() - t0
    ok = "TEST OK" in out
    return ok, elapsed, out

def fetch_testlog(seed):
    raw, rc = docker_exec(f"cat {COOJA_DIR}/COOJA.testlog 2>/dev/null")
    if rc == 0 and raw.strip():
        path = os.path.join(TESTLOG_DIR, f"testlog_seed{seed}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw)
        return path
    return None

# ─────────────────────────────────────────────────────────────────────────────
# Patterns for the three measurement phases
PAT_E = re.compile(r"ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_A = re.compile(r"AUTH_ENERGY\|(\d+)\|(?:cpu_ticks=\d+\|energy_ticks=\d+\|)?cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_K = re.compile(r"KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")

def extract_first(logfile):
    """Return first AUTH/ENROLL/KEYEX per device (initial cycle only)."""
    enroll, auth, keyex = {}, {}, {}
    with open(logfile, encoding="utf-8", errors="replace") as f:
        for line in f:
            for pat, dct in [(PAT_E, enroll), (PAT_A, auth), (PAT_K, keyex)]:
                m = pat.search(line)
                if m:
                    did = int(m.group(1))
                    if did not in dct:
                        dct[did] = {"id": did,
                                    "cpu": float(m.group(2)),
                                    "energy": float(m.group(3))}
    return list(enroll.values()), list(auth.values()), list(keyex.values())

def avg(lst): return sum(lst) / len(lst) if lst else 0.0
def std(lst):
    if len(lst) < 2: return 0.0
    a = avg(lst)
    return math.sqrt(sum((x - a) ** 2 for x in lst) / len(lst))
def ci95(lst):
    if len(lst) < 2: return 0.0
    return 1.96 * std(lst) / math.sqrt(len(lst))

def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Device_ID", "CPU_Time_s", "Energy_J"])
        for r in sorted(rows, key=lambda x: x["id"]):
            w.writerow([r["id"], f"{r['cpu']:.6f}", f"{r['energy']:.6f}"])

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("LAAKA (Fixed) — 5-Seed COOJA Simulation via Docker")
    print("=" * 70)

    # Build once
    if not deploy_and_build():
        print("Build failed — aborting."); sys.exit(1)

    # Copy CSC to container (will be modified per seed below)
    docker_cp(CSC_SRC, f"{PROJECT_DIR}/test-sim-100.csc")

    all_seeds = {}
    for seed in SEEDS:
        print(f"\n{'-'*50}  Seed {seed}")
        # Prepare seed-specific CSC
        tmp = make_csc(seed)
        docker_cp(tmp, f"{PROJECT_DIR}/test-sim.csc")
        try: os.remove(tmp)
        except: pass

        ok, elapsed, simout = run_sim(f"{PROJECT_DIR}/test-sim.csc")
        status = "TEST OK" if ok else "TIMEOUT/FAILED"
        print(f"  Sim result : {status}  ({elapsed:.0f}s)")

        log = fetch_testlog(seed)
        if not log:
            print("  Could not retrieve testlog"); continue

        enroll, auth, keyex = extract_first(log)
        all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
        print(f"  Devices: Enroll={len(enroll)}  Auth={len(auth)}  KeyEx={len(keyex)}")

        # Show per-seed stale/TIDd failures so we can verify the fix
        fail_lines = [l for l in simout.splitlines()
                      if "stale timestamp" in l or "TIDd not found" in l]
        if fail_lines:
            print(f"  Auth failures ({len(fail_lines)} events):")
            for l in fail_lines[:5]:
                print(f"    {l.strip()}")
        else:
            print("  No auth failures — all devices authenticated!")

    if not all_seeds:
        print("No results — aborting."); sys.exit(1)

    # ── Per-device CSVs: average across all seeds for each device ───────────
    def avg_across_seeds(phase_key):
        """For each device, average cpu and energy across all seeds that saw it."""
        acc = {}   # device_id -> {cpu_sum, energy_sum, count}
        for sd in SEEDS:
            if sd not in all_seeds: continue
            for r in all_seeds[sd][phase_key]:
                did = r["id"]
                if did not in acc:
                    acc[did] = {"id": did, "cpu": 0.0, "energy": 0.0, "n": 0}
                acc[did]["cpu"]    += r["cpu"]
                acc[did]["energy"] += r["energy"]
                acc[did]["n"]      += 1
        return [{"id": did, "cpu": v["cpu"]/v["n"], "energy": v["energy"]/v["n"]}
                for did, v in acc.items()]

    print(f"\nWriting per-device CSVs averaged across {len(all_seeds)} seeds...")
    write_csv(avg_across_seeds("enroll"),
              os.path.join(OUTPUT_DIR, "enroll-results.csv"))
    write_csv(avg_across_seeds("auth"),
              os.path.join(OUTPUT_DIR, "auth-results.csv"))
    write_csv(avg_across_seeds("keyex"),
              os.path.join(OUTPUT_DIR, "keyex-results.csv"))

    # ── Multi-seed summary ───────────────────────────────────────────────────
    phases = [("enroll", "Enrollment"),
              ("auth",   "Authentication"),
              ("keyex",  "Key Exchange")]

    print(f"\n{'='*80}")
    print("LAAKA — Results Summary (5-seed average)")
    print(f"{'='*80}")
    print(f"{'Phase':<18} {'n':>4} {'Avg CPU(ms)':>12} {'±std':>8}"
          f"  {'Avg E(mJ)':>12} {'±std':>8}")
    print("-" * 70)

    summary_path = os.path.join(OUTPUT_DIR, "summary.csv")
    summary_rows = []
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Phase", "Seeds", "n_devices",
                    "Avg_CPU_s", "Std_CPU_s", "CI95_CPU_s",
                    "Avg_Energy_mJ", "Std_Energy_mJ", "CI95_Energy_mJ"])
        for key, name in phases:
            per_seed_cpu, per_seed_energy, ns = [], [], []
            for sd in SEEDS:
                if sd not in all_seeds: continue
                rows = all_seeds[sd][key]
                if not rows: continue
                cpus = [r["cpu"] for r in rows]
                ens  = [r["energy"] for r in rows]
                per_seed_cpu.append(avg(cpus))
                per_seed_energy.append(avg(ens))
                ns.append(len(rows))
            if not per_seed_cpu:
                print(f"{name:<18}  {'N/A':>4}"); continue
            n_avg = int(round(avg(ns)))
            ac, ae = avg(per_seed_cpu), avg(per_seed_energy)
            sc, se = std(per_seed_cpu), std(per_seed_energy)
            cc, ce = ci95(per_seed_cpu), ci95(per_seed_energy)
            w.writerow([name, len(per_seed_cpu), n_avg,
                        f"{ac:.6f}", f"{sc:.6f}", f"{cc:.6f}",
                        f"{ae*1000:.4f}", f"{se*1000:.4f}", f"{ce*1000:.4f}"])
            summary_rows.append((name, n_avg, ac, sc, ae, se))
            print(f"{name:<18} {n_avg:>4} {ac*1000:>12.1f} {sc*1000:>8.1f}"
                  f"  {ae*1000:>12.2f} {se*1000:>8.2f}")

    # Auth+KeyEx combined
    e_rows = {s: {r["id"]: r for r in all_seeds[s]["auth"]}  for s in all_seeds}
    k_rows = {s: {r["id"]: r for r in all_seeds[s]["keyex"]} for s in all_seeds}
    combined_cpu, combined_e = [], []
    for sd in all_seeds:
        both_ids = set(e_rows[sd]) & set(k_rows[sd])
        if not both_ids: continue
        cpus = [e_rows[sd][i]["cpu"] + k_rows[sd][i]["cpu"] for i in both_ids]
        ens  = [e_rows[sd][i]["energy"] + k_rows[sd][i]["energy"] for i in both_ids]
        combined_cpu.append(avg(cpus))
        combined_e.append(avg(ens))
    if combined_cpu:
        ac, ae = avg(combined_cpu), avg(combined_e)
        sc, se = std(combined_cpu), std(combined_e)
        print(f"{'Auth+KeyEx':<18} {'':>4} {ac*1000:>12.1f} {sc*1000:>8.1f}"
              f"  {ae*1000:>12.2f} {se*1000:>8.2f}")

    print(f"\nCSVs  -> {OUTPUT_DIR}")
    print(f"Logs  -> {TESTLOG_DIR}")
    print("Done!")
