"""
run_two_round.py — Run the Proposed-Scheme-Two-Round in COOJA via Docker.

Runs 5 seeds (same as other schemes), extracts AUTH_ENERGY and KEYEX_ENERGY
separately, writes per-device CSVs and a comparison summary.

Usage:
    python Scripts/Simulation-Runners/run_two_round.py

Requires Docker container 'cooja-sim' to be running.
"""
import subprocess, os, re, csv, time, math, sys

BASE       = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CONTAINER  = "cooja-sim"
PROJECT_DIR= "/home/user/contiki-ng/examples/myproject"
COOJA_DIR  = "/home/user/contiki-ng/tools/cooja"
SEEDS      = [123456, 234567, 345678, 456789, 567890]

SCHEME_NAME = "Two-Round-Proposed-Scheme"
SCHEME_PATH = os.path.join(BASE, "Proposed-Scheme-Two-Round")
CSC_SRC     = os.path.join(BASE, "Anonymity-Extended-Base-Scheme", "test-sim-100.csc")

SOURCES = ["aes.c","aes.h","sha256.c","sha256.h",
           "as-node.c","device-node.c","gw-node.c",
           "project-conf.h","Makefile"]

OUTPUT_DIR = os.path.join(BASE, "Results", "CSV-Data", "Two-Round")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
def docker_exec(cmd, timeout=900):
    full = f'docker exec {CONTAINER} bash -c "{cmd}"'
    r = subprocess.run(full, capture_output=True, text=True, shell=True, timeout=timeout)
    return r.stdout + r.stderr, r.returncode

def docker_cp(src, dst):
    cmd = f'docker cp "{src}" {CONTAINER}:{dst}'
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
    return r.returncode == 0

# ─────────────────────────────────────────────────────────────────────────────
def deploy_and_build():
    print("Deploying Two-Round Proposed Scheme...")
    docker_exec(f"mkdir -p {PROJECT_DIR} && cd {PROJECT_DIR} && rm -f *.c *.h Makefile && rm -rf build")
    for src in SOURCES:
        src_path = os.path.join(SCHEME_PATH, src)
        if not os.path.exists(src_path):
            print(f"  MISSING: {src_path}")
            return False
        if not docker_cp(src_path, f"{PROJECT_DIR}/{src}"):
            print(f"  FAILED to copy {src}")
            return False
    print("Building firmware...")
    out, rc = docker_exec(f"cd {PROJECT_DIR} && make TARGET=cooja", timeout=120)
    if rc != 0:
        print(f"BUILD FAILED:\n{out[-800:]}")
        return False
    out2, _ = docker_exec(f"ls {PROJECT_DIR}/build/cooja/*.cooja")
    built = [l for l in out2.strip().split('\n') if l.strip().endswith('.cooja')]
    print(f"  Built: {built}")
    return len(built) >= 3

def make_csc(seed):
    with open(CSC_SRC, "r") as f:
        content = f.read()
    content = re.sub(r'<randomseed>\d+</randomseed>', f'<randomseed>{seed}</randomseed>', content)
    content = re.sub(r'examples/[^/"]+/', 'examples/myproject/', content)
    tmp = os.path.join(BASE, f"_tmp_two_round_{seed}.csc")
    with open(tmp, "w") as f:
        f.write(content)
    return tmp

def run_sim(csc_container):
    cmd = (f"cd {COOJA_DIR} && ./gradlew --no-watch-fs run "
           f"--args='--no-gui --contiki=/home/user/contiki-ng "
           f"--autostart {csc_container}'")
    t0 = time.time()
    out, rc = docker_exec(cmd, timeout=900)
    elapsed = time.time() - t0
    success = "TEST OK" in out
    return success, elapsed, out

def save_testlog(seed, full_out):
    log_path = os.path.join(SCHEME_PATH, f"testlog_seed{seed}.txt")
    try:
        raw, rc = docker_exec(f"cat {COOJA_DIR}/COOJA.testlog")
        if rc == 0 and raw.strip():
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(raw)
            return log_path
    except Exception:
        pass
    # Fallback: save the subprocess output
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(full_out)
    return log_path

# ─────────────────────────────────────────────────────────────────────────────
def extract_metrics(logfile):
    """Returns (enroll_list, auth_list, keyex_list) each as list of dicts."""
    enroll, auth, keyex = [], [], []
    pat_e = re.compile(r"ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
    pat_a = re.compile(r"AUTH_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
    pat_k = re.compile(r"KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
    with open(logfile, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pat_e.search(line)
            if m: enroll.append({"id": int(m.group(1)), "cpu": float(m.group(2)), "energy": float(m.group(3))}); continue
            m = pat_a.search(line)
            if m: auth.append({"id": int(m.group(1)), "cpu": float(m.group(2)), "energy": float(m.group(3))}); continue
            m = pat_k.search(line)
            if m: keyex.append({"id": int(m.group(1)), "cpu": float(m.group(2)), "energy": float(m.group(3))}); continue
    return enroll, auth, keyex

def write_per_device_csv(data, path, phase):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device", "CPU_s", "Energy_J"])
        for d in sorted(data, key=lambda x: x["id"]):
            w.writerow([d["id"], f"{d['cpu']:.6f}", f"{d['energy']:.6f}"])
    print(f"  Saved {len(data)} {phase} entries → {os.path.basename(path)}")

def avg(lst): return sum(lst)/len(lst) if lst else 0
def std(lst):
    if len(lst) < 2: return 0
    a = avg(lst)
    return math.sqrt(sum((x-a)**2 for x in lst)/len(lst))

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("Two-Round Proposed Scheme — 5-Seed COOJA Simulation")
    print("=" * 70)

    if not deploy_and_build():
        print("Aborting — build failed.")
        sys.exit(1)

    all_seeds = {}
    for seed in SEEDS:
        print(f"\n{'─'*50}")
        print(f"Seed {seed}")
        tmp = make_csc(seed)
        docker_cp(tmp, f"{PROJECT_DIR}/test-sim.csc")
        os.remove(tmp)

        success, elapsed, full_out = run_sim(f"{PROJECT_DIR}/test-sim.csc")
        status = "✓ OK" if success else "✗ FAILED"
        print(f"  {status}  ({elapsed:.0f}s)")

        log = save_testlog(seed, full_out)
        enroll, auth, keyex = extract_metrics(log)
        all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
        print(f"  Enrolled={len(enroll)}  Auth={len(auth)}  KeyEx={len(keyex)}")

        # Per-device CSVs for last seed (representative)
        if seed == SEEDS[-1]:
            write_per_device_csv(enroll, os.path.join(OUTPUT_DIR, "enroll-results.csv"), "enroll")
            write_per_device_csv(auth,   os.path.join(OUTPUT_DIR, "auth-results.csv"),   "auth")
            write_per_device_csv(keyex,  os.path.join(OUTPUT_DIR, "keyex-results.csv"),  "keyex")

    # ── Multi-seed summary ──────────────────────────────────────────────────
    summary_path = os.path.join(OUTPUT_DIR, "two-round-summary.csv")
    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Phase","Num_Seeds","Num_Devices",
                    "Avg_CPU_s","StdDev_CPU_s","Avg_Energy_J","StdDev_Energy_J","Avg_CPU_Only_mJ"])
        for phase_key, phase_name in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]:
            per_seed_cpu, per_seed_en = [], []
            for seed in SEEDS:
                if seed not in all_seeds: continue
                d = all_seeds[seed][phase_key]
                if not d: continue
                per_seed_cpu.append(avg([x["cpu"] for x in d]))
                per_seed_en.append(avg([x["energy"] for x in d]))
            if not per_seed_cpu: continue
            ac, ae = avg(per_seed_cpu), avg(per_seed_en)
            sc, se = std(per_seed_cpu), std(per_seed_en)
            w.writerow([phase_name, len(per_seed_cpu), 20,
                        f"{ac:.6f}", f"{sc:.6f}", f"{ae:.6f}", f"{se:.6f}", f"{ac*5.4:.4f}"])

    # ── Print final table ───────────────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print("TWO-ROUND PROPOSED SCHEME — RESULTS SUMMARY (5-seed avg)")
    print(f"{'='*80}")
    print(f"{'Phase':<18} {'Avg CPU (s)':>12} {'±σ':>8} {'Avg Energy(mJ)':>15} {'±σ(mJ)':>9}")
    print("─" * 70)

    for phase_key, phase_name in [("enroll","Enrollment"),("auth","Authentication"),("keyex","Key Exchange")]:
        per_seed_cpu, per_seed_en = [], []
        for seed in SEEDS:
            if seed not in all_seeds: continue
            d = all_seeds[seed][phase_key]
            if not d: continue
            per_seed_cpu.append(avg([x["cpu"] for x in d]))
            per_seed_en.append(avg([x["energy"] for x in d]))
        if not per_seed_cpu:
            print(f"{phase_name:<18} {'N/A':>12}")
            continue
        ac, ae = avg(per_seed_cpu)*1000, avg(per_seed_en)*1000
        sc, se = std(per_seed_cpu)*1000, std(per_seed_en)*1000
        print(f"{phase_name:<18} {ac/1000:>12.4f} {sc/1000:>8.4f} {ae:>15.4f} {se:>9.4f}")

    print(f"\nPer-device CSVs → {OUTPUT_DIR}")
    print(f"Summary CSV     → {summary_path}")
    print("\nDone!")
