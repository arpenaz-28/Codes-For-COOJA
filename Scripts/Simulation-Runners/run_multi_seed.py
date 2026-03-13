"""
Multi-seed simulation runner for all 3 schemes.
Handles: copy files to container, build, modify seed in CSC, run, save logs, extract.
"""
import subprocess, os, re, csv, sys, time

BASE = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CONTAINER = "cooja-sim"
PROJECT_DIR = "/opt/contiki-ng/examples/myproject"
COOJA_DIR = "/opt/contiki-ng/tools/cooja"
SEEDS = [123456, 234567, 345678, 456789, 567890]

SCHEMES = {
    "Base-Scheme": {
        "path": os.path.join(BASE, "Base-Scheme"),
        "csc": "test-sim-100.csc",
        "makefile_src": "Makefile.unified",  # needs renaming
        "sources": ["aes.c", "aes.h", "sha256.c", "sha256.h",
                     "as-node.c", "device-node.c", "gw-node.c",
                     "project-conf.h"],
    },
    "LAAKA": {
        "path": os.path.join(BASE, "LAAKA"),
        "csc": "test-sim-100-fixed.csc",
        "makefile_src": "Makefile",
        "sources": ["aes.c", "aes.h", "sha256.c", "sha256.h",
                     "as-node.c", "device-node.c", "gw-node.c",
                     "project-conf.h"],
    },
    "Proposed-Scheme": {
        "path": os.path.join(BASE, "Anonymity-Extended-Base-Scheme"),
        "csc": "test-sim-100.csc",
        "makefile_src": "Makefile",
        "sources": ["aes.c", "aes.h", "sha256.c", "sha256.h",
                     "as-node.c", "device-node.c", "gw-node.c",
                     "project-conf.h"],
    },
}

def docker_exec(cmd, timeout=600):
    full = f'docker exec {CONTAINER} bash -c "{cmd}"'
    r = subprocess.run(full, capture_output=True, text=True, shell=True, timeout=timeout)
    return r.stdout + r.stderr, r.returncode

def docker_cp(src, dst):
    cmd = f'docker cp "{src}" {CONTAINER}:{dst}'
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
    return r.returncode == 0

def clean_project():
    """Remove old source files from container project dir."""
    docker_exec(f"cd {PROJECT_DIR} && rm -f *.c *.h Makefile && rm -rf build")

def deploy_scheme(scheme_name, scheme_info):
    """Copy source files and Makefile to container, then build."""
    print(f"  Deploying {scheme_name}...")
    clean_project()
    
    path = scheme_info["path"]
    for src in scheme_info["sources"]:
        src_path = os.path.join(path, src)
        if not os.path.exists(src_path):
            print(f"    WARNING: {src} not found at {src_path}")
            continue
        ok = docker_cp(src_path, f"{PROJECT_DIR}/{src}")
        if not ok:
            print(f"    FAILED to copy {src}")
            return False

    # Copy Makefile (may need renaming)
    makefile_src = os.path.join(path, scheme_info["makefile_src"])
    ok = docker_cp(makefile_src, f"{PROJECT_DIR}/Makefile")
    if not ok:
        print(f"    FAILED to copy Makefile")
        return False

    # Build
    print(f"  Building {scheme_name}...")
    out, rc = docker_exec(f"cd {PROJECT_DIR} && rm -rf build && make TARGET=cooja", timeout=120)
    if rc != 0:
        print(f"  BUILD FAILED:\n{out[-500:]}")
        return False
    
    # Verify firmware
    out2, _ = docker_exec(f"ls {PROJECT_DIR}/build/cooja/*.cooja")
    cooja_files = [l.strip() for l in out2.strip().split('\n') if l.strip().endswith('.cooja')]
    print(f"  Built {len(cooja_files)} firmware files")
    return len(cooja_files) >= 3

def modify_csc_seed(csc_path, seed):
    """Read CSC, change seed, ensure paths point to myproject/, write temp file."""
    with open(csc_path, "r") as f:
        content = f.read()
    content = re.sub(r'<randomseed>\d+</randomseed>', f'<randomseed>{seed}</randomseed>', content)
    # Ensure all paths point to examples/myproject/ (some CSCs use scheme-specific dirs)
    content = re.sub(r'examples/[^/"]+/', 'examples/myproject/', content)
    tmp = os.path.join(os.path.dirname(csc_path), f"_tmp_seed_{seed}.csc")
    with open(tmp, "w") as f:
        f.write(content)
    return tmp

def run_simulation(csc_container_path):
    """Run COOJA simulation, return (success, duration)."""
    cmd = (f"cd {COOJA_DIR} && ./gradlew --no-watch-fs run "
           f"--args='--no-gui --contiki=/opt/contiki-ng "
           f"--autostart {csc_container_path}'")
    t0 = time.time()
    out, rc = docker_exec(cmd, timeout=900)
    elapsed = time.time() - t0
    success = "TEST OK" in out
    if not success:
        # Print last few lines for debugging
        lines = out.strip().split('\n')
        print(f"    SIM FAILED (rc={rc}, {elapsed:.0f}s):")
        for l in lines[-5:]:
            print(f"      {l}")
    return success, elapsed

def save_testlog(dest_path):
    """Copy COOJA.testlog from container to host."""
    out, rc = docker_exec(f"cat {COOJA_DIR}/COOJA.testlog")
    if rc == 0 and out.strip():
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(out)
        return True
    return False

def extract_metrics(logfile):
    """Extract enrollment, auth, keyex metrics from a log file."""
    enroll, auth, keyex = [], [], []
    if not os.path.exists(logfile):
        return enroll, auth, keyex
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
# MAIN
# =============================================================================
if __name__ == "__main__":
    results = {}  # results[scheme][seed] = {enroll: [...], auth: [...], keyex: [...]}

    for scheme_name, scheme_info in SCHEMES.items():
        print(f"\n{'='*60}")
        print(f"SCHEME: {scheme_name}")
        print(f"{'='*60}")
        
        results[scheme_name] = {}

        # Deploy and build
        if not deploy_scheme(scheme_name, scheme_info):
            print(f"SKIPPING {scheme_name} — build failed")
            continue

        csc_path = os.path.join(scheme_info["path"], scheme_info["csc"])

        for seed in SEEDS:
            print(f"\n  Seed {seed}:")
            
            # Modify CSC with this seed
            tmp_csc = modify_csc_seed(csc_path, seed)
            
            # Copy CSC to container
            ok = docker_cp(tmp_csc, f"{PROJECT_DIR}/test-sim.csc")
            os.remove(tmp_csc)  # cleanup temp
            if not ok:
                print(f"    Failed to copy CSC")
                continue

            # Run simulation
            success, elapsed = run_simulation(f"{PROJECT_DIR}/test-sim.csc")
            print(f"    {'OK' if success else 'FAILED'} in {elapsed:.0f}s")

            if not success:
                continue

            # Save testlog
            log_path = os.path.join(scheme_info["path"], f"testlog_seed{seed}.txt")
            if not save_testlog(log_path):
                print(f"    Failed to save testlog")
                continue

            # Extract metrics
            enroll, auth, keyex = extract_metrics(log_path)
            results[scheme_name][seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
            print(f"    Extracted: E={len(enroll)} A={len(auth)} K={len(keyex)}")

    # ==========================================================================
    # ANALYSIS
    # ==========================================================================
    print(f"\n\n{'='*80}")
    print("ANALYSIS RESULTS")
    print(f"{'='*80}")

    # Per-seed comparison CSV
    out_csv = os.path.join(BASE, "multi-seed-results.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "Seed", "Phase", "Num_Devices",
                     "Avg_CPU_s", "Avg_Energy_J", "Avg_CPU_Only_Energy_J",
                     "Min_CPU_s", "Max_CPU_s", "Min_Energy_J", "Max_Energy_J"])
        
        for scheme_name in SCHEMES:
            for seed in SEEDS:
                if seed not in results.get(scheme_name, {}):
                    continue
                r = results[scheme_name][seed]
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
                    # CPU-only energy: cpu_s * CURRENT_CPU * VOLTAGE = cpu_s * 0.0054
                    avg_cpu_energy = avg_cpu * 0.0054
                    w.writerow([scheme_name, seed, phase_name, n,
                               f"{avg_cpu:.6f}", f"{avg_en:.6f}", f"{avg_cpu_energy:.8f}",
                               f"{min(cpus):.6f}", f"{max(cpus):.6f}",
                               f"{min(ens):.6f}", f"{max(ens):.6f}"])

    print(f"\nDetailed CSV: {out_csv}")

    # Summary: average across all seeds
    summary_csv = os.path.join(BASE, "multi-seed-summary.csv")
    with open(summary_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "Phase", "Num_Seeds", "Num_Devices_Per_Seed",
                     "Avg_CPU_s", "StdDev_CPU_s",
                     "Avg_Energy_J", "StdDev_Energy_J",
                     "Avg_CPU_Only_Energy_J"])

        for scheme_name in SCHEMES:
            for phase_key, phase_label in [("enroll", "Enrollment"),
                                            ("auth", "Authentication"),
                                            ("keyex", "Key Exchange")]:
                all_cpus = []
                all_ens = []
                seed_count = 0
                n_per_seed = 0
                for seed in SEEDS:
                    if seed not in results.get(scheme_name, {}):
                        continue
                    data = results[scheme_name][seed][phase_key]
                    if not data:
                        continue
                    seed_count += 1
                    n_per_seed = len(data)
                    # Average per seed, then collect seed averages
                    avg_c = sum(d["cpu"] for d in data) / len(data)
                    avg_e = sum(d["energy"] for d in data) / len(data)
                    all_cpus.append(avg_c)
                    all_ens.append(avg_e)

                if not all_cpus:
                    continue
                import statistics
                mean_cpu = statistics.mean(all_cpus)
                std_cpu = statistics.stdev(all_cpus) if len(all_cpus) > 1 else 0
                mean_en = statistics.mean(all_ens)
                std_en = statistics.stdev(all_ens) if len(all_ens) > 1 else 0
                cpu_only_en = mean_cpu * 0.0054

                w.writerow([scheme_name, phase_label, seed_count, n_per_seed,
                           f"{mean_cpu:.6f}", f"{std_cpu:.6f}",
                           f"{mean_en:.6f}", f"{std_en:.6f}",
                           f"{cpu_only_en:.8f}"])

                print(f"{scheme_name:20s} {phase_label:16s} "
                      f"CPU={mean_cpu:.4f}±{std_cpu:.4f}s  "
                      f"Energy={mean_en:.4f}±{std_en:.4f}J  "
                      f"CPU-only={cpu_only_en:.6f}J  "
                      f"(n_seeds={seed_count})")

    print(f"\nSummary CSV: {summary_csv}")

    # Print same-seed comparison table
    print(f"\n{'='*80}")
    print("SAME-SEED COMPARISON (seed=123456)")
    print(f"{'='*80}")
    print(f"{'Scheme':<20s} {'Phase':<16s} {'CPU (s)':>10s} {'Energy (J)':>12s} {'CPU-only E (J)':>16s}")
    print("-" * 80)
    for scheme_name in SCHEMES:
        seed = 123456
        if seed not in results.get(scheme_name, {}):
            print(f"{scheme_name}: no data for seed {seed}")
            continue
        r = results[scheme_name][seed]
        for phase_name, phase_data in [("Enrollment", r["enroll"]),
                                        ("Authentication", r["auth"]),
                                        ("Key Exchange", r["keyex"])]:
            if not phase_data:
                continue
            avg_cpu = sum(d["cpu"] for d in phase_data) / len(phase_data)
            avg_en = sum(d["energy"] for d in phase_data) / len(phase_data)
            cpu_only = avg_cpu * 0.0054
            print(f"{scheme_name:<20s} {phase_name:<16s} {avg_cpu:>10.4f} {avg_en:>12.4f} {cpu_only:>16.6f}")
    print("=" * 80)

    print("\nDone! All results saved.")
