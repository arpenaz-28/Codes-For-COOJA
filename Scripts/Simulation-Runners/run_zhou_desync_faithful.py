"""
run_zhou_desync_faithful.py
Faithful Zhou desynchronisation-recovery sweep on the real 4-firmware,
100-node topology (separate User / GW-server / Sensor / GW-router motes),
reusing Zhou-Scheme/test-sim-100.csc.

Scenario (M4 loss at the device):
  R1 normal · R2 device drops M4 (GW+SN advance) · R3 stale auth fails at the
  sensor beta-check -> full re-registration + sensor re-bind + retry (recovery)
  · R4 normal.  Per-round ENERGEST logged as DESYNC_{ENROLL,ROUND1..4}_ENERGY.

Unlike the earlier combined GW+SN demo, this uses the real Zhou operations
(fuzzy extractor, PUF, XOR masks) and a real on-wire gateway<->sensor M2/M3
sub-exchange.

Results → Zhou-Scheme/Simulation-Results/Desync-100-Faithful/{csv,logs}/

Usage:
  python3 run_zhou_desync_faithful.py            # 5 seeds
  python3 run_zhou_desync_faithful.py --seeds 1
"""

import subprocess, os, re, csv, time, math, shutil, argparse

REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI   = "/home/apex/contiki-ng"
COOJA_DIR = os.path.join(CONTIKI, "tools", "cooja")
TESTLOG   = os.path.join(COOJA_DIR, "COOJA.testlog")
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")

SEEDS = [123456, 234567, 345678, 456789, 567890]

FIRST_USER_ID = 81
NUM_USERS     = 20

SOURCE_DIR  = os.path.join(REPO, "Zhou-Scheme", "Src-DesyncDemo-Faithful")
CSC_SRC     = os.path.join(REPO, "Zhou-Scheme", "test-sim-100.csc")
RESULTS_DIR = os.path.join(REPO, "Zhou-Scheme", "Simulation-Results", "Desync-100-Faithful")

SOURCES = ["user-node.c", "gw-server.c", "sn-node.c", "gw-node.c",
           "aes.c", "aes.h", "sha256.c", "sha256.h", "project-conf.h"]
BUILD_TARGETS = ["user-node.cooja", "gw-server.cooja", "sn-node.cooja", "gw-node.cooja"]

MAKEFILE = f"""CONTIKI_PROJECT = user-node gw-server sn-node gw-node
all: $(CONTIKI_PROJECT)

CONTIKI = {CONTIKI}
PROJECT_SOURCEFILES += aes.c sha256.c
MODULES += os/net/app-layer/coap

CFLAGS += -Wno-error=unused-function
CFLAGS += -Wno-error=unused-variable
CFLAGS += -Wno-error=unused-result
CFLAGS += -Wno-error=unused-but-set-variable

include $(CONTIKI)/Makefile.include
"""

# Early-exit ScriptRunner: stop once all NUM_USERS users emit ROUND4 marker.
# NOTE: keep this XML-text-safe — no '&' (so no '&&'); use nested ifs.
EXIT_SCRIPT = f"""
var completed = {{}};
var nExpected = {NUM_USERS};
var firstId   = {FIRST_USER_ID};
TIMEOUT(1800000, log.testOK());
while(true) {{
  log.log(time + " " + id + " " + msg + "\\n");
  if (msg.indexOf("DESYNC_ROUND4_ENERGY") !== -1) {{
    if (id >= firstId) {{
      completed[id] = 1;
      var count = 0; for (var k in completed) {{ count++; }}
      if (count >= nExpected) {{ log.log("EARLY EXIT: all done\\n"); log.testOK(); }}
    }}
  }}
  YIELD();
}}
"""


def setup_myproject():
    os.makedirs(MYPROJECT, exist_ok=True)
    build = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build):
        shutil.rmtree(build)
    for f in SOURCES:
        sp = os.path.join(SOURCE_DIR, f)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(MYPROJECT, f))
        else:
            print(f"  WARNING missing source: {sp}")
    with open(os.path.join(MYPROJECT, "Makefile"), "w") as fh:
        fh.write(MAKEFILE)


def build_firmware():
    print("  Building 4 firmwares...")
    r = subprocess.run(["make", f"-j{os.cpu_count() or 4}"] + BUILD_TARGETS + ["TARGET=cooja"],
                       cwd=MYPROJECT, capture_output=True, text=True, timeout=420)
    if r.returncode != 0:
        print("  BUILD FAILED:\n", r.stderr[-3000:])
        return False
    built = [f for f in os.listdir(os.path.join(MYPROJECT, "build", "cooja")) if f.endswith(".cooja")]
    print(f"  Built: {built}")
    return len(built) >= len(BUILD_TARGETS)


def patch_csc(seed, out_path):
    with open(CSC_SRC, encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'\$\(MAKE\) TARGET=cooja clean\n', '', content)
    content = re.sub(r'<randomseed>\d+</randomseed>', f'<randomseed>{seed}</randomseed>', content)
    # Replace the embedded test script with the early-exit one.
    # Use a function replacement so backslashes in the JS (e.g. "\n") are NOT
    # processed as regex escapes.
    content = re.sub(r'<script>.*?</script>',
                     lambda m: '<script>' + EXIT_SCRIPT + '</script>',
                     content, flags=re.DOTALL)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)


def run_simulation(seed):
    csc_path = os.path.join(MYPROJECT, f"_zdf_s{seed}.csc")
    patch_csc(seed, csc_path)
    if os.path.isfile(TESTLOG):
        os.remove(TESTLOG)
    t0 = time.time()
    r = subprocess.run(["./gradlew", "--no-watch-fs", "run",
                        f"--args=--no-gui --contiki={CONTIKI} --autostart {csc_path}"],
                       cwd=COOJA_DIR, capture_output=True, text=True, timeout=3600)
    elapsed = time.time() - t0
    out = r.stdout + r.stderr
    log_tmp = None
    if os.path.isfile(TESTLOG):
        log_tmp = f"/tmp/zdf_testlog_s{seed}.txt"
        shutil.copy2(TESTLOG, log_tmp)
    ok = "TEST OK" in out or (log_tmp and "TEST OK" in open(log_tmp, errors="replace").read())
    try:
        os.remove(csc_path)
    except OSError:
        pass
    return ok, elapsed, log_tmp


# ── Parsing (same markers/format as run_zhou_desync_100.py) ────────────────────
ROUND_KEYS = ["DESYNC_ENROLL_ENERGY", "DESYNC_ROUND1_ENERGY", "DESYNC_ROUND2_ENERGY",
              "DESYNC_ROUND3_ENERGY", "DESYNC_ROUND4_ENERGY"]
ROUND_LABELS = ["Enrollment", "Round 1", "Round 2", "Round 3", "Round 4"]
PAT = re.compile(r"(DESYNC_(?:ENROLL|ROUND[1-4])_ENERGY)\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)")


def extract_first(logfile):
    data = {k: {} for k in ROUND_KEYS}
    with open(logfile, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PAT.search(line)
            if m:
                marker, uid, cpu, energy = m.group(1), int(m.group(2)), float(m.group(3)), float(m.group(4))
                if marker in data and uid not in data[marker]:
                    data[marker][uid] = {"cpu": cpu, "energy": energy}
    return data


def _avg(l): return sum(l) / len(l) if l else 0.0
def _std(l):
    if len(l) < 2: return 0.0
    a = _avg(l); return math.sqrt(sum((x - a) ** 2 for x in l) / len(l))


def run(seeds):
    out_dir = os.path.join(RESULTS_DIR, "csv")
    log_dir = os.path.join(RESULTS_DIR, "logs")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    all_seeds = {}
    for seed in seeds:
        lp = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        if os.path.isfile(lp):
            all_seeds[seed] = extract_first(lp)
            print(f"  seed {seed} [cached]")

    todo = [s for s in seeds if s not in all_seeds]
    if todo:
        setup_myproject()
        if not build_firmware():
            print("  build failed — aborting new seeds")
            todo = []

    for seed in todo:
        print(f"  --- seed {seed}")
        ok, elapsed, log_tmp = run_simulation(seed)
        print(f"    {'TEST OK' if ok else 'TIMEOUT/FAIL'} ({elapsed:.0f}s)")
        if not log_tmp:
            print("    no testlog — skip"); continue
        lp = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        shutil.copy2(log_tmp, lp); os.remove(log_tmp)
        data = extract_first(lp)
        all_seeds[seed] = data
        print("    counts:", {k.replace('DESYNC_', '').replace('_ENERGY', ''): len(v) for k, v in data.items()})

    if not all_seeds:
        print("  no results"); return None

    # summary.csv (per-round averages across seeds)
    summary_path = os.path.join(out_dir, "summary.csv")
    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Round", "Seeds", "Avg_Users", "Avg_CPU_s", "Std_CPU_s", "Avg_Energy_mJ", "Std_Energy_mJ"])
        for key, label in zip(ROUND_KEYS, ROUND_LABELS):
            pe, pc, nu = [], [], []
            for data in all_seeds.values():
                devs = list(data[key].values())
                if devs:
                    pe.append(_avg([d["energy"] for d in devs]))
                    pc.append(_avg([d["cpu"] for d in devs]))
                    nu.append(len(devs))
            if not pe: continue
            w.writerow([label, len(pe), f"{_avg(nu):.1f}", f"{_avg(pc):.6f}", f"{_std(pc):.6f}",
                        f"{_avg(pe) * 1000:.4f}", f"{_std(pe) * 1000:.4f}"])
    print(f"\n  Summary: {summary_path}")

    # quick overhead print
    rows = {r[0]: r for r in csv.reader(open(summary_path))}
    try:
        r1 = float(rows["Round 1"][5]); r3 = float(rows["Round 3"][5])
        print(f"  Round1 = {r1:.2f} mJ  Round3 = {r3:.2f} mJ  overhead = {(r3 - r1) / r1 * 100:+.1f}%")
    except (KeyError, ValueError, ZeroDivisionError):
        pass
    return summary_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=len(SEEDS))
    args = ap.parse_args()
    seeds = SEEDS[:args.seeds]
    print("Faithful Zhou Desync sweep (4-firmware, 100-node)")
    print(f"  seeds={seeds}  source={SOURCE_DIR}")
    run(seeds)


if __name__ == "__main__":
    main()
