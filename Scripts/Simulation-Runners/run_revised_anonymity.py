"""
run_revised_anonymity.py
Run Revised-Anonymity (two-round, bug-fixed) in COOJA via Docker.
5 seeds, extracts ENROLL_ENERGY / AUTH_ENERGY / KEYEX_ENERGY per device.
"""
import subprocess, os, re, csv, time, math, sys

BASE        = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CONTAINER   = "cooja-sim"
PROJECT_DIR = "/home/user/contiki-ng/examples/myproject"
COOJA_DIR   = "/home/user/contiki-ng/tools/cooja"
SEEDS       = [123456, 234567, 345678, 456789, 567890]

SCHEME_PATH = os.path.join(BASE, "Revised-Anonymity")
CSC_SRC     = os.path.join(BASE, "Anonymity-Extended-Base-Scheme", "test-sim-100.csc")
SOURCES     = ["aes.c","aes.h","sha256.c","sha256.h",
               "as-node.c","device-node.c","gw-node.c",
               "project-conf.h","Makefile"]

OUTPUT_DIR  = os.path.join(BASE, "Results", "CSV-Data", "Revised-Anonymity")
TESTLOG_DIR = os.path.join(BASE, "Results", "Testlogs", "Revised-Anonymity")
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
    print("Deploying Revised-Anonymity scheme...")
    docker_exec(f"mkdir -p {PROJECT_DIR} && cd {PROJECT_DIR} && "
                f"rm -f *.c *.h Makefile && rm -rf build")
    for src in SOURCES:
        path = os.path.join(SCHEME_PATH, src)
        if not os.path.exists(path):
            print(f"  MISSING: {path}"); return False
        if not docker_cp(path, f"{PROJECT_DIR}/{src}"):
            print(f"  COPY FAILED: {src}"); return False
    print("  Building firmware...")
    out, rc = docker_exec(f"cd {PROJECT_DIR} && make TARGET=cooja", timeout=180)
    if rc != 0:
        print(f"  BUILD FAILED:\n{out[-800:]}"); return False
    out2, _ = docker_exec(f"ls {PROJECT_DIR}/build/cooja/*.cooja")
    built = [l for l in out2.strip().splitlines() if l.strip().endswith(".cooja")]
    print(f"  Built: {[os.path.basename(b) for b in built]}")
    return len(built) >= 3

def make_csc(seed):
    with open(CSC_SRC) as f: content = f.read()
    content = re.sub(r'<randomseed>\d+</randomseed>',
                     f'<randomseed>{seed}</randomseed>', content)
    content = re.sub(r'examples/[^/"]+/', 'examples/myproject/', content)
    tmp = os.path.join(BASE, f"_tmp_ra_{seed}.csc")
    with open(tmp, "w") as f: f.write(content)
    return tmp

def run_sim(csc_path_container):
    cmd = (f"cd {COOJA_DIR} && ./gradlew --no-watch-fs run "
           f"--args='--no-gui --contiki=/home/user/contiki-ng "
           f"--autostart {csc_path_container}'")
    t0 = time.time()
    out, rc = docker_exec(cmd, timeout=900)
    return "TEST OK" in out, time.time() - t0, out

def fetch_testlog(seed):
    raw, rc = docker_exec(f"cat {COOJA_DIR}/COOJA.testlog")
    if rc == 0 and raw.strip():
        path = os.path.join(TESTLOG_DIR, f"testlog_seed{seed}.txt")
        with open(path, "w", encoding="utf-8") as f: f.write(raw)
        return path
    return None

# ─────────────────────────────────────────────────────────────────────────────
PAT_E = re.compile(r"ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_A = re.compile(r"AUTH_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_K = re.compile(r"KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")

def extract(logfile):
    enroll, auth, keyex = [], [], []
    with open(logfile, encoding="utf-8", errors="replace") as f:
        for line in f:
            for pat, lst in [(PAT_E, enroll),(PAT_A, auth),(PAT_K, keyex)]:
                m = pat.search(line)
                if m:
                    lst.append({"id": int(m.group(1)),
                                "cpu": float(m.group(2)),
                                "energy": float(m.group(3))})
    return enroll, auth, keyex

def avg(lst): return sum(lst)/len(lst) if lst else 0
def std(lst):
    if len(lst) < 2: return 0
    a = avg(lst)
    return math.sqrt(sum((x-a)**2 for x in lst)/len(lst))

def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device","CPU_s","Energy_J"])
        for r in sorted(rows, key=lambda x: x["id"]):
            w.writerow([r["id"], f"{r['cpu']:.6f}", f"{r['energy']:.6f}"])

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*70)
    print("Revised-Anonymity — 5-Seed COOJA Simulation")
    print("="*70)

    if not deploy_and_build():
        print("Aborting."); sys.exit(1)

    all_seeds = {}
    for seed in SEEDS:
        print(f"\n{'-'*50}  Seed {seed}")
        tmp = make_csc(seed)
        docker_cp(tmp, f"{PROJECT_DIR}/test-sim.csc")
        os.remove(tmp)

        ok, elapsed, _ = run_sim(f"{PROJECT_DIR}/test-sim.csc")
        print(f"  {'OK' if ok else 'FAILED'}  ({elapsed:.0f}s)")

        log = fetch_testlog(seed)
        if not log:
            print("  Could not retrieve testlog"); continue

        enroll, auth, keyex = extract(log)
        all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
        print(f"  Enroll={len(enroll)}  Auth={len(auth)}  KeyEx={len(keyex)}")

    if not all_seeds:
        print("No results - aborting."); sys.exit(1)

    # Use last seed for per-device CSVs
    last = SEEDS[-1] if SEEDS[-1] in all_seeds else list(all_seeds)[-1]
    write_csv(all_seeds[last]["enroll"], os.path.join(OUTPUT_DIR, "enroll-results.csv"))
    write_csv(all_seeds[last]["auth"],   os.path.join(OUTPUT_DIR, "auth-results.csv"))
    write_csv(all_seeds[last]["keyex"],  os.path.join(OUTPUT_DIR, "keyex-results.csv"))

    # Multi-seed summary
    summary = os.path.join(OUTPUT_DIR, "summary.csv")
    phases  = [("enroll","Enrollment"), ("auth","Authentication"),
               ("keyex","Key Exchange")]

    print(f"\n{'='*80}")
    print("REVISED-ANONYMITY -- RESULTS (5-seed average per device)")
    print(f"{'='*80}")
    print(f"{'Phase':<18} {'Avg CPU(s)':>12} {'+-s(s)':>8} {'Avg Energy(mJ)':>15} {'+-s(mJ)':>9}")
    print("-"*65)

    with open(summary, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Phase","Seeds","Avg_CPU_s","Std_CPU_s",
                    "Avg_Energy_J","Std_Energy_J"])
        for key, name in phases:
            cpus, ens = [], []
            for sd in SEEDS:
                if sd not in all_seeds: continue
                d = all_seeds[sd][key]
                if not d: continue
                cpus.append(avg([x["cpu"]    for x in d]))
                ens.append( avg([x["energy"] for x in d]))
            if not cpus:
                print(f"{name:<18} {'N/A':>12}"); continue
            ac, ae = avg(cpus), avg(ens)
            sc, se = std(cpus), std(ens)
            w.writerow([name, len(cpus), f"{ac:.6f}", f"{sc:.6f}",
                        f"{ae:.6f}", f"{se:.6f}"])
            print(f"{name:<18} {ac:>12.4f} {sc:>8.4f} {ae*1000:>15.4f} {se*1000:>9.4f}")

    print(f"\nCSVs → {OUTPUT_DIR}")
    print(f"Logs → {TESTLOG_DIR}")
    print("Done!")
