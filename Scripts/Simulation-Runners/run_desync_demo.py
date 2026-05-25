"""
run_desync_demo.py
Run COOJA desync demonstration simulations for:
  - Proposed scheme (Revised-Anonymity/Src-DesyncDemo) — dual-state recovery
  - Base scheme    (Base-Scheme/Src-DesyncDemo)         — no recovery, re-enrol

Topology (both): 1 GW (node 1) + 1 AS (node 2) + 3 device nodes (3,4,5)

For each scheme and each seed:
  1. Copy source files to /home/apex/contiki-ng/examples/myproject/
  2. Build firmware
  3. Generate CSC, run COOJA headless
  4. Save log to Results/Desync-Demo/<Scheme>/logs/testlog_seed<N>.txt
  5. Parse log → CSV

Outputs:
  Results/Desync-Demo/Proposed/logs/   testlog_seed*.txt
  Results/Desync-Demo/Proposed/        desync_results.csv
  Results/Desync-Demo/Base/logs/       testlog_seed*.txt
  Results/Desync-Demo/Base/            desync_results.csv

Usage:
  python3 run_desync_demo.py
  python3 run_desync_demo.py --seeds 123456 234567 345678
  python3 run_desync_demo.py --scheme Proposed
"""

import subprocess, os, re, csv, time, shutil, argparse, sys

REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI   = "/home/apex/contiki-ng"
COOJA_DIR = os.path.join(CONTIKI, "tools", "cooja")
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")
RESULTS   = os.path.join(REPO, "Results", "Desync-Demo")

SCHEMES = {
    "Proposed": {
        "source_dir": os.path.join(REPO, "Revised-Anonymity", "Src-DesyncDemo"),
        "files": ["gw-node.c", "as-node.c", "device-node.c",
                  "aes.c", "aes.h", "sha256.c", "sha256.h"],
    },
    "Base": {
        "source_dir": os.path.join(REPO, "Base-Scheme", "Src-DesyncDemo"),
        "files": ["gw-node.c", "as-node.c", "device-node.c",
                  "aes.c", "aes.h", "sha256.c", "sha256.h"],
    },
}

DEFAULT_SEEDS = [123456, 234567, 345678, 456789, 567890]
TIMEOUT_MS    = 600_000      # 10 min per simulation
N_DEVICES     = 3            # nodes 3, 4, 5


# ── Makefile ──────────────────────────────────────────────────────────────────
MAKEFILE = """\
CONTIKI_PROJECT = gw-node as-node device-node
all: $(CONTIKI_PROJECT)
MODULES += os/net/app-layer/coap
PROJECT_SOURCEFILES += aes.c sha256.c
CONTIKI = {contiki}
include $(CONTIKI)/Makefile.include
""".format(contiki=CONTIKI)


# ── CSC template ─────────────────────────────────────────────────────────────
MOTE_IFACES = """\
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

def mote_xml(node_id, x, y):
    return f"""\
      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="{x}" y="{y}" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>{node_id}</id>
        </interface_config>
      </mote>"""

def generate_csc(seed):
    gw_mote  = mote_xml(1,  0.0,  0.0)
    as_mote  = mote_xml(2, 10.0,  0.0)
    dev_motes = "\n".join(
        mote_xml(3 + i, 20.0 + i * 10, 0.0)
        for i in range(N_DEVICES)
    )
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<simconf version="2022112801">
  <simulation>
    <title>Desync Demo</title>
    <randomseed>{seed}</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
      org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>150.0</transmitting_range>
      <interference_range>200.0</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>1.0</success_ratio_rx>
    </radiomedium>
    <events><logoutput>40000</logoutput></events>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>GW Node</description>
      <source>[CONTIKI_DIR]/examples/myproject/gw-node.c</source>
      <commands>$(MAKE) TARGET=cooja clean
$(MAKE) -j$(CPUS) gw-node.cooja TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/gw-node.cooja</firmware>
{MOTE_IFACES}
{gw_mote}
    </motetype>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>AS Node</description>
      <source>[CONTIKI_DIR]/examples/myproject/as-node.c</source>
      <commands>$(MAKE) TARGET=cooja clean
$(MAKE) -j$(CPUS) as-node.cooja TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/as-node.cooja</firmware>
{MOTE_IFACES}
{as_mote}
    </motetype>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>Device Node</description>
      <source>[CONTIKI_DIR]/examples/myproject/device-node.c</source>
      <commands>$(MAKE) TARGET=cooja clean
$(MAKE) -j$(CPUS) device-node.cooja TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/device-node.cooja</firmware>
{MOTE_IFACES}
{dev_motes}
    </motetype>
  </simulation>
  <plugin>
    org.contikios.cooja.plugins.ScriptRunner
    <plugin_config>
      <script>
TIMEOUT({TIMEOUT_MS}, log.testOK());
while(true) {{
  log.log(time + " " + id + " " + msg + "\\n");
  YIELD();
}}
      </script>
      <active>true</active>
    </plugin_config>
    <bounds x="0" y="0" height="300" width="600" z="1" />
  </plugin>
</simconf>"""


# ── Log parser ────────────────────────────────────────────────────────────────
ROUNDS = ["ENROLL", "ROUND1", "ROUND2", "ROUND3", "ROUND4"]
PAT = re.compile(
    r"DESYNC_(\w+)_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)"
)

def parse_log(log_path):
    """Return {node_id: {round_label: (cpu_s, energy_j)}}"""
    records = {}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PAT.search(line)
            if m:
                label, nid, cpu, ej = m.group(1), int(m.group(2)), float(m.group(3)), float(m.group(4))
                records.setdefault(nid, {})[label] = (cpu, ej * 1000)  # J → mJ
    return records


# ── Runner ────────────────────────────────────────────────────────────────────
def setup_myproject(scheme_cfg):
    os.makedirs(MYPROJECT, exist_ok=True)
    build = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build):
        shutil.rmtree(build)
    src = scheme_cfg["source_dir"]
    for fname in scheme_cfg["files"]:
        sp = os.path.join(src, fname)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(MYPROJECT, fname))
    # project-conf.h
    shutil.copy2(os.path.join(src, "project-conf.h"),
                 os.path.join(MYPROJECT, "project-conf.h"))
    with open(os.path.join(MYPROJECT, "Makefile"), "w") as f:
        f.write(MAKEFILE)


def build_firmware():
    r = subprocess.run(
        ["make", "-j4", "gw-node.cooja", "as-node.cooja", "device-node.cooja",
         "TARGET=cooja"],
        cwd=MYPROJECT, capture_output=True, text=True, timeout=300
    )
    if r.returncode != 0:
        print("Build FAILED:\n", r.stderr[-3000:])
        return False
    fw_dir = os.path.join(MYPROJECT, "build", "cooja")
    if not any(f.endswith(".cooja") for f in os.listdir(fw_dir)):
        print("No .cooja firmware found after build")
        return False
    return True


TESTLOG = os.path.join(COOJA_DIR, "COOJA.testlog")

def run_seed(seed, scheme, log_dir):
    log_dest = os.path.join(log_dir, f"testlog_seed{seed}.txt")
    if os.path.isfile(log_dest):
        print(f"    [cached] seed {seed}")
        return log_dest

    csc = generate_csc(seed)
    csc_path = os.path.join(MYPROJECT, f"desync_{scheme}_s{seed}.csc")
    with open(csc_path, "w") as f:
        f.write(csc)

    if os.path.isfile(TESTLOG):
        os.remove(TESTLOG)

    t0 = time.time()
    r = subprocess.run(
        ["./gradlew", "--no-watch-fs", "run",
         f"--args=--no-gui --contiki={CONTIKI} --autostart {csc_path}"],
        cwd=COOJA_DIR, capture_output=True, text=True, timeout=TIMEOUT_MS // 1000 + 60
    )
    elapsed = time.time() - t0

    combined = r.stdout + r.stderr
    if os.path.isfile(TESTLOG):
        shutil.copy2(TESTLOG, log_dest)
        print(f"    seed {seed}: OK ({elapsed:.0f}s)")
    else:
        log_dest_fail = log_dest.replace(".txt", "_FAIL.txt")
        with open(log_dest_fail, "w") as f:
            f.write(combined[-50000:])
        print(f"    seed {seed}: FAILED ({elapsed:.0f}s) — see {log_dest_fail}")
        log_dest = None

    try:
        os.remove(csc_path)
    except OSError:
        pass
    return log_dest


def run_scheme(scheme, seeds):
    cfg = SCHEMES[scheme]
    log_dir = os.path.join(RESULTS, scheme, "logs")
    os.makedirs(log_dir, exist_ok=True)

    print(f"\n=== {scheme} scheme ===")
    print("  Setting up myproject...")
    setup_myproject(cfg)
    print("  Building firmware...")
    if not build_firmware():
        print(f"  SKIPPING {scheme} — build failed")
        return

    all_records = {}   # seed → {nid → {round → (cpu,ej)}}
    for seed in seeds:
        print(f"  Running seed {seed}...")
        log_path = run_seed(seed, scheme, log_dir)
        if log_path and os.path.isfile(log_path):
            all_records[seed] = parse_log(log_path)

    # Write per-scheme CSV
    csv_path = os.path.join(RESULTS, scheme, "desync_results.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Seed", "Node", "Round", "CPU_s", "Energy_mJ"])
        for seed, rec in all_records.items():
            for nid, rounds in rec.items():
                for rnd, (cpu, ej) in rounds.items():
                    w.writerow([seed, nid, rnd, f"{cpu:.6f}", f"{ej:.4f}"])
    print(f"  CSV → {csv_path}")

    # Print quick summary
    import statistics
    print(f"\n  Per-round mean energy (mJ) across all devices & seeds:")
    combined = {}
    for rec in all_records.values():
        for rounds in rec.values():
            for rnd, (_, ej) in rounds.items():
                combined.setdefault(rnd, []).append(ej)
    for rnd in ROUNDS:
        vals = combined.get(rnd, [])
        if vals:
            print(f"    {rnd:10s}: mean={statistics.mean(vals):.2f}  "
                  f"n={len(vals)}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheme", nargs="+", choices=["Proposed", "Base"],
                    default=["Proposed", "Base"])
    ap.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    for scheme in args.scheme:
        run_scheme(scheme, args.seeds)

    print(f"\nAll outputs → {RESULTS}")


if __name__ == "__main__":
    main()
