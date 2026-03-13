"""
Re-run only the Extended (Proposed) Scheme with 5 seeds after PUF model update.
Then merge with existing Base-Scheme and LAAKA multi-seed results.
"""
import subprocess, os, re, csv, time, math

BASE = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CONTAINER = "cooja-sim"
PROJECT_DIR = "/opt/contiki-ng/examples/myproject"
COOJA_DIR = "/opt/contiki-ng/tools/cooja"
SEEDS = [123456, 234567, 345678, 456789, 567890]

SCHEME_PATH = os.path.join(BASE, "Anonymity-Extended-Base-Scheme")
CSC_FILE = "test-sim-100.csc"
SOURCES = ["aes.c", "aes.h", "sha256.c", "sha256.h",
           "as-node.c", "device-node.c", "gw-node.c",
           "project-conf.h", "Makefile"]

def docker_exec(cmd, timeout=600):
    full = f'docker exec {CONTAINER} bash -c "{cmd}"'
    r = subprocess.run(full, capture_output=True, text=True, shell=True, timeout=timeout)
    return r.stdout + r.stderr, r.returncode

def docker_cp(src, dst):
    cmd = f'docker cp "{src}" {CONTAINER}:{dst}'
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
    return r.returncode == 0

def deploy_and_build():
    print("Deploying Extended Scheme...")
    docker_exec(f"cd {PROJECT_DIR} && rm -f *.c *.h Makefile && rm -rf build")
    for src in SOURCES:
        src_path = os.path.join(SCHEME_PATH, src)
        if not docker_cp(src_path, f"{PROJECT_DIR}/{src}"):
            print(f"  FAILED to copy {src}")
            return False
    print("Building...")
    out, rc = docker_exec(f"cd {PROJECT_DIR} && make TARGET=cooja", timeout=120)
    if rc != 0:
        print(f"BUILD FAILED:\n{out[-500:]}")
        return False
    out2, _ = docker_exec(f"ls {PROJECT_DIR}/build/cooja/*.cooja")
    n = len([l for l in out2.strip().split('\n') if l.strip().endswith('.cooja')])
    print(f"  Built {n} firmware files")
    return n >= 3

def modify_csc_seed(seed):
    csc_path = os.path.join(SCHEME_PATH, CSC_FILE)
    with open(csc_path, "r") as f:
        content = f.read()
    content = re.sub(r'<randomseed>\d+</randomseed>', f'<randomseed>{seed}</randomseed>', content)
    content = re.sub(r'examples/[^/"]+/', 'examples/myproject/', content)
    tmp = os.path.join(BASE, f"_tmp_seed_{seed}.csc")
    with open(tmp, "w") as f:
        f.write(content)
    return tmp

def run_sim(csc_container_path):
    cmd = (f"cd {COOJA_DIR} && ./gradlew --no-watch-fs run "
           f"--args='--no-gui --contiki=/opt/contiki-ng "
           f"--autostart {csc_container_path}'")
    t0 = time.time()
    out, rc = docker_exec(cmd, timeout=900)
    elapsed = time.time() - t0
    success = "TEST OK" in out
    return success, elapsed

def save_testlog(dest):
    out, rc = docker_exec(f"cat {COOJA_DIR}/COOJA.testlog")
    if rc == 0 and out.strip():
        with open(dest, "w", encoding="utf-8") as f:
            f.write(out)
        return True
    return False

def extract_metrics(logfile):
    enroll, auth, keyex = [], [], []
    with open(logfile, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.search(r"ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)", line)
            if m:
                enroll.append({"id": int(m.group(1)), "cpu": float(m.group(2)), "energy": float(m.group(3))})
                continue
            m = re.search(r"KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)", line)
            if m:
                keyex.append({"id": int(m.group(1)), "cpu": float(m.group(2)), "energy": float(m.group(3))})
                continue
            m = re.search(r"AUTH_ENERGY\|(\d+)\|.*cpu_s=([\d.]+)\|energy_j=([\d.]+)", line)
            if m:
                auth.append({"id": int(m.group(1)), "cpu": float(m.group(2)), "energy": float(m.group(3))})
                continue
            m = re.search(r"authentication \d+ for client (\d+) are ([\d.]+) and ([\d.]+)", line)
            if m:
                auth.append({"id": int(m.group(1)), "cpu": float(m.group(2)), "energy": float(m.group(3))})
    return enroll, auth, keyex

# =============================================================================
if __name__ == "__main__":
    if not deploy_and_build():
        sys.exit(1)

    seed_results = {}
    for seed in SEEDS:
        print(f"\n--- Seed {seed} ---")
        tmp_csc = modify_csc_seed(seed)
        docker_cp(tmp_csc, f"{PROJECT_DIR}/test-sim.csc")
        os.remove(tmp_csc)

        success, elapsed = run_sim(f"{PROJECT_DIR}/test-sim.csc")
        print(f"  {'OK' if success else 'FAILED'} in {elapsed:.0f}s")
        if not success:
            continue

        log_path = os.path.join(SCHEME_PATH, f"testlog_seed{seed}.txt")
        if not save_testlog(log_path):
            print("  Failed to save testlog")
            continue

        enroll, auth, keyex = extract_metrics(log_path)
        seed_results[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
        print(f"  E={len(enroll)} A={len(auth)} K={len(keyex)}")

    # =========================================================================
    # Write Extended Scheme per-seed results
    # =========================================================================
    ext_csv = os.path.join(BASE, "extended-seed-results.csv")
    with open(ext_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scheme","Seed","Phase","Num_Devices",
                     "Avg_CPU_s","Avg_Energy_J","Avg_CPU_Only_Energy_J",
                     "Min_CPU_s","Max_CPU_s","Min_Energy_J","Max_Energy_J"])
        for seed in SEEDS:
            if seed not in seed_results:
                continue
            r = seed_results[seed]
            for phase_name, phase_data in [("Enrollment", r["enroll"]),
                                            ("Authentication", r["auth"]),
                                            ("Key Exchange", r["keyex"])]:
                if not phase_data:
                    continue
                cpus = [d["cpu"] for d in phase_data]
                ens = [d["energy"] for d in phase_data]
                n = len(phase_data)
                avg_cpu = sum(cpus) / n
                avg_en = sum(ens) / n
                w.writerow(["Proposed-Scheme", seed, phase_name, n,
                           f"{avg_cpu:.6f}", f"{avg_en:.6f}", f"{avg_cpu * 0.0054:.8f}",
                           f"{min(cpus):.6f}", f"{max(cpus):.6f}",
                           f"{min(ens):.6f}", f"{max(ens):.6f}"])

    # =========================================================================
    # Merge with existing Base-Scheme and LAAKA results, then write combined CSVs
    # =========================================================================
    old_results = os.path.join(BASE, "multi-seed-results.csv")
    merged_rows = []

    # Read existing Base-Scheme and LAAKA rows
    if os.path.exists(old_results):
        with open(old_results) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Scheme"] in ("Base-Scheme", "LAAKA"):
                    merged_rows.append(row)

    # Add new Extended rows
    with open(ext_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            merged_rows.append(row)

    # Write merged per-seed CSV
    with open(old_results, "w", newline="") as f:
        fields = ["Scheme","Seed","Phase","Num_Devices",
                  "Avg_CPU_s","Avg_Energy_J","Avg_CPU_Only_Energy_J",
                  "Min_CPU_s","Max_CPU_s","Min_Energy_J","Max_Energy_J"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in merged_rows:
            w.writerow(row)

    # =========================================================================
    # Compute summary (averages + stddev across seeds)
    # =========================================================================
    summary_csv = os.path.join(BASE, "multi-seed-summary.csv")
    schemes = ["Base-Scheme", "LAAKA", "Proposed-Scheme"]
    phases = ["Enrollment", "Authentication", "Key Exchange"]

    # Group by (scheme, phase) -> list of per-seed averages
    grouped = {}
    for row in merged_rows:
        key = (row["Scheme"], row["Phase"])
        if key not in grouped:
            grouped[key] = {"cpus": [], "ens": [], "ns": []}
        grouped[key]["cpus"].append(float(row["Avg_CPU_s"]))
        grouped[key]["ens"].append(float(row["Avg_Energy_J"]))
        grouped[key]["ns"].append(int(row["Num_Devices"]))

    with open(summary_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scheme","Phase","Num_Seeds","Num_Devices_Per_Seed",
                     "Avg_CPU_s","StdDev_CPU_s","Avg_Energy_J","StdDev_Energy_J",
                     "Avg_CPU_Only_Energy_J"])
        for scheme in schemes:
            for phase in phases:
                key = (scheme, phase)
                if key not in grouped:
                    continue
                g = grouped[key]
                n_seeds = len(g["cpus"])
                n_dev = int(sum(g["ns"]) / n_seeds) if n_seeds else 0
                avg_cpu = sum(g["cpus"]) / n_seeds
                avg_en = sum(g["ens"]) / n_seeds
                std_cpu = math.sqrt(sum((x - avg_cpu)**2 for x in g["cpus"]) / n_seeds)
                std_en = math.sqrt(sum((x - avg_en)**2 for x in g["ens"]) / n_seeds)
                cpu_only = avg_cpu * 0.0054
                w.writerow([scheme, phase, n_seeds, n_dev,
                           f"{avg_cpu:.6f}", f"{std_cpu:.6f}",
                           f"{avg_en:.6f}", f"{std_en:.6f}",
                           f"{cpu_only:.8f}"])

    # =========================================================================
    # Print summary
    # =========================================================================
    print(f"\n\n{'='*90}")
    print("UPDATED COMPARISON — 5-SEED AVERAGE")
    print(f"{'='*90}")
    print(f"{'Scheme':<20s} {'Phase':<16s} {'CPU (s)':>10s} {'±σ':>8s} {'Energy (J)':>12s} {'±σ':>8s} {'CPU-only(mJ)':>13s}")
    print("-" * 90)
    for scheme in schemes:
        for phase in phases:
            key = (scheme, phase)
            if key not in grouped:
                continue
            g = grouped[key]
            n = len(g["cpus"])
            ac = sum(g["cpus"]) / n
            ae = sum(g["ens"]) / n
            sc = math.sqrt(sum((x - ac)**2 for x in g["cpus"]) / n)
            se = math.sqrt(sum((x - ae)**2 for x in g["ens"]) / n)
            print(f"{scheme:<20s} {phase:<16s} {ac:>10.4f} {sc:>8.4f} {ae:>12.4f} {se:>8.4f} {ac*5.4:>13.4f}")
        print("-" * 90)

    print(f"\nCSVs updated: {old_results}, {summary_csv}")
    print("Done!")
