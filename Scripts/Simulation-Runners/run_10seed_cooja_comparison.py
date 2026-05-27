"""
run_10seed_cooja_comparison.py

Run COOJA simulations for all 3 schemes (Proposed/RA, LAAKA, Zhou) across 10 seeds.
100-mote topology, 20 device nodes (IDs 81–100) per scheme.

Proposed (RA) uses a custom project-conf.h so devices map to the correct AS IDs
in the same 100-mote topology as LAAKA.  Zhou has its own CSC with 4 mote types.

Outputs → Results/COOJA-Simulation/10-Seed-Comparison/{Proposed,LAAKA,Zhou}/
  logs/testlog_seed<N>.txt   — raw COOJA testlog per seed
  seed_results.csv           — per-device, per-seed energy+CPU
  summary.csv                — per-device mean ± 95% CI across 10 seeds

Usage:
  python3 run_10seed_cooja_comparison.py
  python3 run_10seed_cooja_comparison.py --scheme Proposed LAAKA
  python3 run_10seed_cooja_comparison.py --seeds 123456 234567
"""

import argparse, csv, math, os, re, shutil, statistics, subprocess, time

REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI   = "/home/apex/contiki-ng"
COOJA_DIR = os.path.join(CONTIKI, "tools", "cooja")
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")
TESTLOG   = os.path.join(COOJA_DIR, "COOJA.testlog")
OUT_ROOT  = os.path.join(REPO, "Results", "COOJA-Simulation", "10-Seed-Comparison")

DEFAULT_SEEDS = [123456, 234567, 345678, 456789, 567890,
                 678901, 789012, 890123, 901234, 112345]

DEVICE_IDS = list(range(81, 101))   # same for all 3 schemes


# ── Custom project-conf.h for Proposed (RA) in the 100-mote LAAKA topology ───
RA_PROJECT_CONF = """\
#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* 100-mote comparison topology (matches LAAKA CSC):
 *   Node 1        = GW  (RPL root + Registration Authority)
 *   Nodes 2-80   = AS motes (79 total; only nodes 2 & 3 are active)
 *   Nodes 81-100 = Device nodes (20 IoT devices)
 *
 *   Assignment: AS = AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 *   Devices 81-90  -> AS 2
 *   Devices 91-100 -> AS 3
 */
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define NUM_AS           2
#define FIRST_DEVICE_ID  81

#define ENERGEST_CONF_ON 1

#define COAP_MAX_CHUNK_SIZE   128
#define REST_MAX_CHUNK_SIZE   128

#define RPL_ENABLED           1
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE

#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
"""

RA_LAAKA_MAKEFILE = """\
CONTIKI_PROJECT = device-node as-node gw-node
all: $(CONTIKI_PROJECT)
CONTIKI = {contiki}
PROJECT_SOURCEFILES += aes.c sha256.c
MODULES += os/net/app-layer/coap
CFLAGS += -Wno-error=unused-function -Wno-error=unused-variable
CFLAGS += -Wno-error=unused-result -Wno-error=unused-but-set-variable
include $(CONTIKI)/Makefile.include
""".format(contiki=CONTIKI)

ZHOU_MAKEFILE = """\
CONTIKI_PROJECT = user-node gw-server sn-node gw-node
all: $(CONTIKI_PROJECT)
CONTIKI = {contiki}
PROJECT_SOURCEFILES += aes.c sha256.c
MODULES += os/net/app-layer/coap
CFLAGS += -Wno-error=unused-function -Wno-error=unused-variable
CFLAGS += -Wno-error=unused-result -Wno-error=unused-but-set-variable
include $(CONTIKI)/Makefile.include
""".format(contiki=CONTIKI)

# ── Custom project-conf.h for Zhou — 2 active GW-servers, balanced 10/10 ─────
ZHOU_PROJECT_CONF = """\
#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* 100-mote comparison topology — Zhou scheme, 2 active GW-servers (balanced):
 *   Node 1        = GW  (RPL root, data receiver)
 *   Nodes 2-3    = GW-Servers (both active, 10 users + 10 SNs each)
 *   Nodes 4-23   = Sensor Nodes (20 SNs; SN_id = user_id - 77)
 *   Nodes 24-80  = Filler motes (inactive)
 *   Nodes 81-100 = User devices (20 users)
 *
 *   GW_USER_SPLIT=90  → users 81-90 → GW_SERVER_ID=2, users 91-100 → GW_SERVER_ID2=3
 *   GW_SN_SPLIT=13    → SNs  4-13  → GW_SERVER_ID=2, SNs  14-23  → GW_SERVER_ID2=3
 *   Matches LAAKA: AS2 handles 10 devices, AS3 handles 10 devices (parity).
 */
#define GW_NODE_ID       1
#define GW_SERVER_ID     2
#define GW_SERVER_ID2    3
#define FIRST_SN_ID      4
#define LAST_SN_ID       23
#define FIRST_USER_ID    81

#define SN_USER_OFFSET    77
#define GW_USER_SPLIT     90   /* users 81-90 → GW_SERVER_ID=2, 91-100 → GW_SERVER_ID2=3 */
#define GW_SN_SPLIT       13   /* SNs  4-13   → GW_SERVER_ID=2, 14-23  → GW_SERVER_ID2=3 */

#define ENERGEST_CONF_ON 1

#define COAP_MAX_CHUNK_SIZE   160
#define REST_MAX_CHUNK_SIZE   160

#define RPL_ENABLED           1
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE

#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
"""


# ── Scheme configurations ─────────────────────────────────────────────────────
SCHEMES = {
    "Proposed": {
        "source_dir":   os.path.join(REPO, "Revised-Anonymity", "Src-20AS-79Dev"),
        "source_files": ["gw-node.c", "as-node.c", "device-node.c",
                         "aes.c", "aes.h", "sha256.c", "sha256.h"],
        "csc_src":      os.path.join(REPO, "LAAKA", "test-sim-100.csc"),
        "makefile":     RA_LAAKA_MAKEFILE,
        "custom_conf":  RA_PROJECT_CONF,
        "has_keyex":    True,
        "build_targets": ["gw-node.cooja", "as-node.cooja", "device-node.cooja"],
    },
    "LAAKA": {
        "source_dir":   os.path.join(REPO, "LAAKA"),
        "source_files": ["gw-node.c", "as-node.c", "device-node.c",
                         "aes.c", "aes.h", "sha256.c", "sha256.h",
                         "project-conf.h"],
        "csc_src":      os.path.join(REPO, "LAAKA", "test-sim-100.csc"),
        "makefile":     RA_LAAKA_MAKEFILE,
        "custom_conf":  None,
        "has_keyex":    True,
        "build_targets": ["gw-node.cooja", "as-node.cooja", "device-node.cooja"],
    },
    "Zhou": {
        "source_dir":   os.path.join(REPO, "Zhou-Scheme"),
        "source_files": ["gw-node.c", "gw-server.c", "sn-node.c", "user-node.c",
                         "aes.c", "aes.h", "sha256.c", "sha256.h",
                         "project-conf.h"],
        "csc_src":      os.path.join(REPO, "Zhou-Scheme", "test-sim-100.csc"),
        "makefile":     ZHOU_MAKEFILE,
        "custom_conf":  ZHOU_PROJECT_CONF,
        "has_keyex":    False,
        "build_targets": ["gw-node.cooja", "gw-server.cooja",
                          "sn-node.cooja", "user-node.cooja"],
    },
}


# ── Log parsing ───────────────────────────────────────────────────────────────
# RA AUTH_ENERGY has extra cpu_ticks/energy_ticks fields; use an optional group
_PAT_ENROLL = re.compile(
    r'ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')
_PAT_AUTH = re.compile(
    r'AUTH_ENERGY\|(\d+)\|(?:cpu_ticks=[\d.eE+\-]+\|energy_ticks=[\d.eE+\-]+\|)?'
    r'cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')
_PAT_KEYEX = re.compile(
    r'KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')


def parse_log(log_path, has_keyex):
    """
    Return dict: device_id → {enroll, auth, keyex} each = (cpu_s, energy_j).
    AUTH may appear multiple times per device (Zhou multiple rounds) → averaged.
    """
    enroll, auth_list, keyex = {}, {}, {}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    for m in _PAT_ENROLL.finditer(text):
        nid = int(m.group(1))
        if nid in DEVICE_IDS:
            enroll[nid] = (float(m.group(2)), float(m.group(3)))

    for m in _PAT_AUTH.finditer(text):
        nid = int(m.group(1))
        if nid in DEVICE_IDS:
            auth_list.setdefault(nid, []).append(
                (float(m.group(2)), float(m.group(3))))

    if has_keyex:
        for m in _PAT_KEYEX.finditer(text):
            nid = int(m.group(1))
            if nid in DEVICE_IDS:
                keyex[nid] = (float(m.group(2)), float(m.group(3)))

    result = {}
    for nid in DEVICE_IDS:
        if nid not in enroll and nid not in auth_list:
            continue
        e_cpu, e_ej = enroll.get(nid, (0.0, 0.0))
        if auth_list.get(nid):
            rounds = auth_list[nid]
            a_cpu = statistics.mean(r[0] for r in rounds)
            a_ej  = statistics.mean(r[1] for r in rounds)
        else:
            a_cpu, a_ej = 0.0, 0.0
        k_cpu, k_ej = keyex.get(nid, (0.0, 0.0))
        result[nid] = {
            "enroll": (e_cpu, e_ej),
            "auth":   (a_cpu, a_ej),
            "keyex":  (k_cpu, k_ej),
        }
    return result


# ── Build helpers ─────────────────────────────────────────────────────────────
def setup_myproject(cfg):
    """Copy scheme source files and write Makefile + project-conf.h to myproject."""
    os.makedirs(MYPROJECT, exist_ok=True)
    build_dir = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)

    src = cfg["source_dir"]
    for fname in cfg["source_files"]:
        sp = os.path.join(src, fname)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(MYPROJECT, fname))
        else:
            print(f"  WARNING: source file missing: {sp}")

    # Write Makefile
    with open(os.path.join(MYPROJECT, "Makefile"), "w") as f:
        f.write(cfg["makefile"])

    # Write project-conf.h (custom overrides existing if provided)
    if cfg["custom_conf"]:
        with open(os.path.join(MYPROJECT, "project-conf.h"), "w") as f:
            f.write(cfg["custom_conf"])
    elif "project-conf.h" not in cfg["source_files"]:
        sp = os.path.join(src, "project-conf.h")
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(MYPROJECT, "project-conf.h"))


def build_firmware(cfg):
    """Pre-build all firmware targets.  Returns True on success."""
    targets = cfg["build_targets"]
    r = subprocess.run(
        ["make", f"-j{os.cpu_count() or 4}"] + targets + ["TARGET=cooja"],
        cwd=MYPROJECT, capture_output=True, text=True, timeout=360
    )
    if r.returncode != 0:
        print("  BUILD FAILED:\n", r.stderr[-3000:])
        return False
    fw_dir = os.path.join(MYPROJECT, "build", "cooja")
    built = [f for f in os.listdir(fw_dir) if f.endswith(".cooja")]
    print(f"  Built: {built}")
    return len(built) >= len(targets)


def patch_csc(csc_src, seed, out_path):
    """Write a seed-patched CSC.  Strips 'make clean' so pre-built firmware is reused."""
    with open(csc_src, encoding="utf-8") as f:
        content = f.read()
    # Remove the clean step so COOJA reuses our pre-built firmware
    content = re.sub(r'\$\(MAKE\) TARGET=cooja clean\n', '', content)
    content = re.sub(r'<randomseed>\d+</randomseed>',
                     f'<randomseed>{seed}</randomseed>', content)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)


# ── Per-seed runner ───────────────────────────────────────────────────────────
def run_seed(scheme, seed, log_dir, csc_src):
    log_dest = os.path.join(log_dir, f"testlog_seed{seed}.txt")
    if os.path.isfile(log_dest):
        print(f"    [cached] seed {seed}")
        return log_dest

    csc_path = os.path.join(MYPROJECT, f"_cmp_{scheme}_s{seed}.csc")
    patch_csc(csc_src, seed, csc_path)

    if os.path.isfile(TESTLOG):
        os.remove(TESTLOG)

    t0 = time.time()
    r = subprocess.run(
        ["./gradlew", "--no-watch-fs", "run",
         f"--args=--no-gui --contiki={CONTIKI} --autostart {csc_path}"],
        cwd=COOJA_DIR, capture_output=True, text=True, timeout=2400
    )
    elapsed = time.time() - t0

    try:
        os.remove(csc_path)
    except OSError:
        pass

    if os.path.isfile(TESTLOG):
        shutil.copy2(TESTLOG, log_dest)
        print(f"    seed {seed}: OK  ({elapsed:.0f}s)")
        return log_dest

    fail_path = log_dest.replace(".txt", "_FAIL.txt")
    with open(fail_path, "w") as f:
        f.write((r.stdout + r.stderr)[-60000:])
    print(f"    seed {seed}: FAILED ({elapsed:.0f}s) — see {os.path.basename(fail_path)}")
    return None


# ── Per-scheme orchestration ──────────────────────────────────────────────────
def run_scheme(scheme, seeds):
    cfg = SCHEMES[scheme]
    out_dir = os.path.join(OUT_ROOT, scheme)
    log_dir = os.path.join(out_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Scheme: {scheme}")
    print(f"{'='*60}")

    # Build once
    print("  Setting up myproject and building firmware...")
    setup_myproject(cfg)
    if not build_firmware(cfg):
        print(f"  SKIPPING {scheme} — build failed")
        return

    # Run seeds
    all_records = {}   # seed → {device_id → {enroll, auth, keyex}}
    for seed in seeds:
        print(f"  Running seed {seed}...")
        log_path = run_seed(scheme, seed, log_dir, cfg["csc_src"])
        if log_path:
            rec = parse_log(log_path, cfg["has_keyex"])
            if rec:
                all_records[seed] = rec
                found = len(rec)
                print(f"    parsed {found}/{len(DEVICE_IDS)} devices")
            else:
                print(f"    WARNING: no device energy records found in log")

    if not all_records:
        print(f"  No data collected for {scheme}")
        return

    # Write seed_results.csv
    seed_csv = os.path.join(out_dir, "seed_results.csv")
    with open(seed_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Seed", "Device",
                    "Enroll_Energy_mJ", "Enroll_CPU_s",
                    "Auth_Energy_mJ",   "Auth_CPU_s",
                    "Keyex_Energy_mJ",  "Keyex_CPU_s",
                    "Total_Energy_mJ",  "Total_CPU_s"])
        for seed, rec in sorted(all_records.items()):
            for dev in sorted(rec):
                en_cpu, en_ej = rec[dev]["enroll"]
                au_cpu, au_ej = rec[dev]["auth"]
                kx_cpu, kx_ej = rec[dev]["keyex"]
                tot_ej  = (en_ej + au_ej + kx_ej) * 1000   # J → mJ
                tot_cpu = en_cpu + au_cpu + kx_cpu
                w.writerow([seed, dev,
                            f"{en_ej*1000:.4f}", f"{en_cpu:.6f}",
                            f"{au_ej*1000:.4f}", f"{au_cpu:.6f}",
                            f"{kx_ej*1000:.4f}", f"{kx_cpu:.6f}",
                            f"{tot_ej:.4f}",     f"{tot_cpu:.6f}"])
    print(f"  seed_results.csv → {seed_csv}")

    # Compute summary: per-device means across seeds, then overall mean ± CI
    dev_means = {}  # device → [per-seed total_energy_mJ, ...]
    dev_cpu   = {}
    for seed, rec in all_records.items():
        for dev in sorted(rec):
            en_cpu, en_ej = rec[dev]["enroll"]
            au_cpu, au_ej = rec[dev]["auth"]
            kx_cpu, kx_ej = rec[dev]["keyex"]
            tot_ej  = (en_ej + au_ej + kx_ej) * 1000
            tot_cpu = en_cpu + au_cpu + kx_cpu
            dev_means.setdefault(dev, []).append(tot_ej)
            dev_cpu.setdefault(dev, []).append(tot_cpu)

    summary_csv = os.path.join(out_dir, "summary.csv")
    with open(summary_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device", "Mean_Total_Energy_mJ", "CI_Energy_mJ",
                    "Mean_Total_CPU_s", "CI_CPU_s", "Num_Seeds"])
        for dev in sorted(dev_means):
            evals = dev_means[dev]
            cvals = dev_cpu[dev]
            n = len(evals)
            e_mean = statistics.mean(evals)
            c_mean = statistics.mean(cvals)
            e_ci = 1.96 * statistics.stdev(evals) / math.sqrt(n) if n > 1 else 0.0
            c_ci = 1.96 * statistics.stdev(cvals) / math.sqrt(n) if n > 1 else 0.0
            w.writerow([dev, f"{e_mean:.4f}", f"{e_ci:.4f}",
                        f"{c_mean:.6f}", f"{c_ci:.6f}", n])
    print(f"  summary.csv      → {summary_csv}")

    # Quick console summary
    all_e = [v for vals in dev_means.values() for v in vals]
    all_c = [v for vals in dev_cpu.values() for v in vals]
    print(f"\n  Device-level mean energy : {statistics.mean(all_e):.2f} mJ  "
          f"(n={len(all_e)})")
    print(f"  Device-level mean CPU    : {statistics.mean(all_c):.4f} s")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="10-seed COOJA comparison: Proposed/LAAKA/Zhou")
    ap.add_argument("--scheme", nargs="+",
                    choices=["Proposed", "LAAKA", "Zhou"],
                    default=["Proposed", "LAAKA", "Zhou"])
    ap.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    args = ap.parse_args()

    os.makedirs(OUT_ROOT, exist_ok=True)
    print(f"Output root: {OUT_ROOT}")
    print(f"Seeds ({len(args.seeds)}): {args.seeds}")
    print(f"Schemes: {args.scheme}")

    for scheme in args.scheme:
        run_scheme(scheme, args.seeds)

    print(f"\nDone.  Outputs → {OUT_ROOT}")


if __name__ == "__main__":
    main()
