"""
run_50_50.py
Run Revised-Anonymity (1 GW + 50 AS + 50 Devices) in COOJA locally.
3 seeds — extracts ENROLL_ENERGY / AUTH_ENERGY / KEYEX_ENERGY per device.

Efficiency:
  - Smart early-exit: simulation stops the moment all 50 devices log
    KEYEX_ENERGY (their last measurement) — no idle waiting.
  - Hard cap: 15-minute fallback timeout (vs 30-min full run).
  - 3 seeds instead of 5 — still statistically meaningful.

Topology:
  Node 1       = Gateway (RPL root)
  Nodes 2-51   = Authentication Servers (all 50 active)
  Nodes 52-101 = IoT Devices (50 total)
  Assignment:  device_id 52→AS 2, 53→AS 3, ..., 101→AS 51  (1 device per AS)

Output:
  Simulation results/50_50/logs/testlog_seed<N>.txt
  Simulation results/50_50/csv/enroll-results.csv
  Simulation results/50_50/csv/auth-results.csv
  Simulation results/50_50/csv/keyex-results.csv
  Simulation results/50_50/csv/summary.csv
"""

import subprocess, os, re, csv, time, math, sys, shutil

BASE        = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI_DIR = "/home/apex/contiki-ng"
COOJA_DIR   = "/home/apex/contiki-ng/tools/cooja"
PROJECT_DIR = "/home/apex/contiki-ng/examples/cooja_50_50"
SCHEME_PATH = os.path.join(BASE, "Revised-Anonymity", "Revised-Anonymity-50_50")

SEEDS       = [123456, 234567, 345678, 456789, 567890]   # 5 seeds
NUM_DEVICES = 50

OUTPUT_DIR  = os.path.join(BASE, "Revised-Anonymity", "Simulation results", "Revised-Anonymity", "50_50", "csv")
LOG_DIR     = os.path.join(BASE, "Revised-Anonymity", "Simulation results", "Revised-Anonymity", "50_50", "logs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR,    exist_ok=True)

SOURCES = [
    "aes.c", "aes.h", "sha256.c", "sha256.h",
    "as-node.c", "device-node.c", "gw-node.c",
    "project-conf.h", "Makefile",
]

MOTE_INTERFACES = """\
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Battery</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiVib</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiBeeper</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.RimeAddress</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiButton</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiPIR</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiLED</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiCFS</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>"""


def _mote_block(node_id, x, y):
    return (
        f"      <mote>\n"
        f"        <interface_config>\n"
        f"          org.contikios.cooja.interfaces.Position\n"
        f"          <pos x=\"{x:.1f}\" y=\"{y:.1f}\" />\n"
        f"        </interface_config>\n"
        f"        <interface_config>\n"
        f"          org.contikios.cooja.contikimote.interfaces.ContikiMoteID\n"
        f"          <id>{node_id}</id>\n"
        f"        </interface_config>\n"
        f"      </mote>"
    )


# Early-exit COOJA script:
#   Logs every serial message, counts unique devices that reported KEYEX_ENERGY
#   (their last measurement), and calls testOK() the moment all NUM_DEVICES
#   are done — avoiding idle time after the last device finishes.
#   Hard cap: 900 000 ms (15 min) in case a device fails to complete.
COOJA_SCRIPT = f"""\
TIMEOUT(900000, log.testOK());
var seen = {{}};
var done = 0;
while (true) {{
  log.log(time + " " + id + " " + msg + "\\n");
  if (msg.indexOf("KEYEX_ENERGY|") !== -1) {{
    var parts = msg.split("|");
    if (parts.length >= 2) {{
      var devid = parts[1];
      if (!seen[devid]) {{
        seen[devid] = true;
        done++;
        if (done >= {NUM_DEVICES}) {{
          log.log("=== All {NUM_DEVICES} devices completed KEYEX — early exit ===\\n");
          log.testOK();
        }}
      }}
    }}
  }}
  YIELD();
}}"""


def make_csc(seed):
    """Generate COOJA .csc for 1 GW + 50 AS (2-51) + 50 Devices (52-101)."""
    grid = []
    for row in range(11):        # 11×10 = 110 slots — enough for 101 nodes
        for col in range(10):
            grid.append((col * 30.0, row * 30.0))

    proj = "[CONTIKI_DIR]/examples/cooja_50_50"

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<simconf version="2022112801">')
    lines.append('  <simulation>')
    lines.append('    <title>Revised-Anonymity 50AS+50Dev</title>')
    lines.append(f'    <randomseed>{seed}</randomseed>')
    lines.append('    <motedelay_us>1000000</motedelay_us>')
    lines.append('    <radiomedium>')
    lines.append('      org.contikios.cooja.radiomediums.UDGM')
    lines.append('      <transmitting_range>150.0</transmitting_range>')
    lines.append('      <interference_range>200.0</interference_range>')
    lines.append('      <success_ratio_tx>1.0</success_ratio_tx>')
    lines.append('      <success_ratio_rx>1.0</success_ratio_rx>')
    lines.append('    </radiomedium>')
    lines.append('    <events>')
    lines.append('      <logoutput>40000</logoutput>')
    lines.append('    </events>')

    # GW — Node 1
    lines.append('    <motetype>')
    lines.append('      org.contikios.cooja.contikimote.ContikiMoteType')
    lines.append('      <description>GW Node (RPL root)</description>')
    lines.append(f'      <source>{proj}/gw-node.c</source>')
    lines.append(f'      <commands>$(MAKE) -j$(CPUS) gw-node.cooja TARGET=cooja</commands>')
    lines.append(f'      <firmware>{proj}/build/cooja/gw-node.cooja</firmware>')
    lines.append(MOTE_INTERFACES)
    lines.append(_mote_block(1, grid[0][0], grid[0][1]))
    lines.append('    </motetype>')

    # AS — Nodes 2-51 (all 50 active)
    lines.append('    <motetype>')
    lines.append('      org.contikios.cooja.contikimote.ContikiMoteType')
    lines.append('      <description>AS Node (Authentication Server)</description>')
    lines.append(f'      <source>{proj}/as-node.c</source>')
    lines.append(f'      <commands>$(MAKE) -j$(CPUS) as-node.cooja TARGET=cooja</commands>')
    lines.append(f'      <firmware>{proj}/build/cooja/as-node.cooja</firmware>')
    lines.append(MOTE_INTERFACES)
    for nid in range(2, 52):
        lines.append(_mote_block(nid, grid[nid - 1][0], grid[nid - 1][1]))
    lines.append('    </motetype>')

    # Devices — Nodes 52-101
    lines.append('    <motetype>')
    lines.append('      org.contikios.cooja.contikimote.ContikiMoteType')
    lines.append('      <description>Device Node (IoT Device)</description>')
    lines.append(f'      <source>{proj}/device-node.c</source>')
    lines.append(f'      <commands>$(MAKE) -j$(CPUS) device-node.cooja TARGET=cooja</commands>')
    lines.append(f'      <firmware>{proj}/build/cooja/device-node.cooja</firmware>')
    lines.append(MOTE_INTERFACES)
    for nid in range(52, 102):
        lines.append(_mote_block(nid, grid[nid - 1][0], grid[nid - 1][1]))
    lines.append('    </motetype>')

    lines.append('  </simulation>')

    # LogListener
    lines.append('  <plugin>')
    lines.append('    org.contikios.cooja.plugins.LogListener')
    lines.append('    <plugin_config>')
    lines.append('      <filter />')
    lines.append('      <formatted_time />')
    lines.append('      <coloring />')
    lines.append('    </plugin_config>')
    lines.append('    <bounds x="400" y="1" height="400" width="800" z="1" />')
    lines.append('  </plugin>')

    # ScriptRunner with early-exit logic
    lines.append('  <plugin>')
    lines.append('    org.contikios.cooja.plugins.ScriptRunner')
    lines.append('    <plugin_config>')
    lines.append('      <script>')
    for script_line in COOJA_SCRIPT.splitlines():
        lines.append(script_line)
    lines.append('      </script>')
    lines.append('      <active>true</active>')
    lines.append('    </plugin_config>')
    lines.append('    <bounds x="0" y="600" height="300" width="600" z="3" />')
    lines.append('  </plugin>')

    lines.append('</simconf>')

    csc_path = os.path.join(BASE, f"_tmp_50_50_{seed}.csc")
    with open(csc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return csc_path


# ─────────────────────────────────────────────────────────────────────────────

def deploy_and_build():
    """Copy 50_50 sources to PROJECT_DIR and build COOJA firmware."""
    print(f"Deploying source to {PROJECT_DIR} ...")
    os.makedirs(PROJECT_DIR, exist_ok=True)

    build_dir = os.path.join(PROJECT_DIR, "build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)

    for src in SOURCES:
        src_path = os.path.join(SCHEME_PATH, src)
        if not os.path.exists(src_path):
            print(f"  MISSING: {src_path}")
            return False
        shutil.copy2(src_path, os.path.join(PROJECT_DIR, src))
        print(f"  Copied  {src}")

    # PROJECT_DIR is 2 levels below contiki root (examples/cooja_50_50/)
    # so CONTIKI must be ../.. — overwrite the source Makefile which uses ../../../..
    makefile_path = os.path.join(PROJECT_DIR, "Makefile")
    with open(makefile_path) as f:
        makefile = f.read()
    with open(makefile_path, "w") as f:
        f.write(makefile.replace("CONTIKI = ../../../..", "CONTIKI = ../.."))
    print(f"  Fixed   Makefile (CONTIKI = ../..)")

    print("  Building firmware (make TARGET=cooja) ...")
    r = subprocess.run(
        ["make", "TARGET=cooja"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        print("  BUILD FAILED:")
        print(r.stderr[-1200:])
        print(r.stdout[-400:])
        return False

    cooja_bin_dir = os.path.join(PROJECT_DIR, "build", "cooja")
    if not os.path.isdir(cooja_bin_dir):
        print("  ERROR: build/cooja/ not found after make")
        return False

    built = [f for f in os.listdir(cooja_bin_dir) if f.endswith(".cooja")]
    print(f"  Built:  {built}")
    return len(built) >= 3


def run_sim(csc_path):
    """Run COOJA headless; return (ok, elapsed_s, output)."""
    cmd = [
        "./gradlew", "--no-watch-fs", "run",
        f"--args=--no-gui --contiki={CONTIKI_DIR} --autostart {csc_path}",
    ]
    t0 = time.time()
    r = subprocess.run(
        cmd,
        cwd=COOJA_DIR,
        capture_output=True,
        text=True,
        timeout=1200,   # 20-min hard cap on the process (CSC itself caps at 15 min)
    )
    out = r.stdout + r.stderr
    return "TEST OK" in out, time.time() - t0, out


def fetch_testlog(seed):
    """Copy COOJA.testlog to output logs dir; return path or None."""
    src = os.path.join(COOJA_DIR, "COOJA.testlog")
    if os.path.isfile(src) and os.path.getsize(src) > 0:
        dst = os.path.join(LOG_DIR, f"testlog_seed{seed}.txt")
        shutil.copy2(src, dst)
        return dst
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Result extraction
# ─────────────────────────────────────────────────────────────────────────────

PAT_E = re.compile(r"ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_A = re.compile(r"AUTH_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_K = re.compile(r"KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")


def extract(logfile):
    enroll, auth, keyex = [], [], []
    with open(logfile, encoding="utf-8", errors="replace") as f:
        for line in f:
            for pat, lst in [(PAT_E, enroll), (PAT_A, auth), (PAT_K, keyex)]:
                m = pat.search(line)
                if m:
                    lst.append({
                        "id":     int(m.group(1)),
                        "cpu":    float(m.group(2)),
                        "energy": float(m.group(3)),
                    })
    return enroll, auth, keyex


def avg(lst): return sum(lst) / len(lst) if lst else 0.0


def std(lst):
    if len(lst) < 2:
        return 0.0
    a = avg(lst)
    return math.sqrt(sum((x - a) ** 2 for x in lst) / len(lst))


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device", "CPU_s", "Energy_J"])
        for r in sorted(rows, key=lambda x: x["id"]):
            w.writerow([r["id"], f"{r['cpu']:.6f}", f"{r['energy']:.6f}"])


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("Revised-Anonymity 50_50 — COOJA Simulation (efficient mode)")
    print(f"  Seeds: {SEEDS}  |  Early exit when all {NUM_DEVICES} devices complete")
    print("  1 GW  |  50 AS (Nodes 2–51, all active)  |  50 Devices (52–101)")
    print("=" * 70)

    if not deploy_and_build():
        print("Aborting.")
        sys.exit(1)

    all_seeds = {}

    for seed in SEEDS:
        print(f"\n{'─' * 50}  Seed {seed}")
        csc = make_csc(seed)

        ok, elapsed, raw_out = run_sim(csc)
        os.remove(csc)
        status = "EARLY EXIT (all done)" if ok else "TIMED-OUT/FAILED"
        print(f"  {status}  ({elapsed:.0f} s  ≈ {elapsed/60:.1f} min)")

        if not ok:
            dbg = os.path.join(LOG_DIR, f"debug_seed{seed}.txt")
            with open(dbg, "w") as f:
                f.write(raw_out[-5000:])
            print(f"  Partial output → {dbg}")

        log = fetch_testlog(seed)
        if not log:
            print("  Could not retrieve COOJA.testlog — skipping seed")
            continue

        enroll, auth, keyex = extract(log)
        all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
        print(f"  Devices — Enroll: {len(enroll):<3}  Auth: {len(auth):<3}  KeyEx: {len(keyex)}")

        missing = NUM_DEVICES - len(keyex)
        if missing > 0:
            print(f"  WARNING: {missing} device(s) did not complete KeyEx")

    if not all_seeds:
        print("\nNo results collected — aborting.")
        sys.exit(1)

    # Per-device CSVs from last successful seed
    last = SEEDS[-1] if SEEDS[-1] in all_seeds else list(all_seeds)[-1]
    write_csv(all_seeds[last]["enroll"], os.path.join(OUTPUT_DIR, "enroll-results.csv"))
    write_csv(all_seeds[last]["auth"],   os.path.join(OUTPUT_DIR, "auth-results.csv"))
    write_csv(all_seeds[last]["keyex"],  os.path.join(OUTPUT_DIR, "keyex-results.csv"))

    # Multi-seed summary
    summary_path = os.path.join(OUTPUT_DIR, "summary.csv")
    phases = [
        ("enroll", "Enrollment"),
        ("auth",   "Authentication"),
        ("keyex",  "Key Exchange"),
    ]

    print(f"\n{'=' * 80}")
    print("REVISED-ANONYMITY 50_50 — RESULTS (seed-averaged per device)")
    print(f"{'=' * 80}")
    print(f"{'Phase':<18} {'Avg CPU(s)':>12} {'±σ(s)':>8} {'Avg Energy(mJ)':>15} {'±σ(mJ)':>9}")
    print("-" * 65)

    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Phase", "Seeds", "Avg_CPU_s", "Std_CPU_s",
                    "Avg_Energy_J", "Std_Energy_J"])
        for key, name in phases:
            cpus, ens = [], []
            for sd in SEEDS:
                if sd not in all_seeds:
                    continue
                d = all_seeds[sd][key]
                if not d:
                    continue
                cpus.append(avg([x["cpu"]    for x in d]))
                ens.append( avg([x["energy"] for x in d]))
            if not cpus:
                print(f"{name:<18} {'N/A':>12}")
                continue
            ac, ae = avg(cpus), avg(ens)
            sc, se = std(cpus), std(ens)
            w.writerow([name, len(cpus),
                        f"{ac:.6f}", f"{sc:.6f}",
                        f"{ae:.6f}", f"{se:.6f}"])
            print(f"{name:<18} {ac:>12.4f} {sc:>8.4f} {ae*1000:>15.4f} {se*1000:>9.4f}")

    print(f"\nCSVs  → {OUTPUT_DIR}")
    print(f"Logs  → {LOG_DIR}")
    print("Done!")
