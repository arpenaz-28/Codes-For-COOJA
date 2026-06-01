"""
run_desync_comparison_100.py
Run desync recovery comparison on a 100-node realistic multi-hop topology.

Topology: 1 GW (node 1) + 1 AS (node 2) + 78 router nodes (3–80)
          + 20 device nodes (81–100)

Bar 1 — Normal:   Enrollment + Round 1 (clean auth+keyex, no packet loss)
Bar 2 — Recovery: Enrollment + Round 1 + Round 2 (desync trigger)
                  + Round 3 (recovery auth+keyex)

Schemes:
  Base     (Base-Scheme/Src-DesyncDemo-100)
    Recovery = failed auth → full re-enrollment → retry auth  (high cost)
  Proposed (Revised-Anonymity/Src-DesyncDemo-100)
    Recovery = re-auth via PID_old → direct key exchange       (low cost)

Results saved to:
  Base-Scheme/Simulation-Results/Desync-100/{csv,logs}/
  Revised-Anonymity/Simulation-Results/Desync-100/{csv,logs}/

Usage:
  python3 run_desync_comparison_100.py              # both schemes, 5 seeds
  python3 run_desync_comparison_100.py --scheme Base
  python3 run_desync_comparison_100.py --seeds 3
"""

import subprocess, os, re, csv, time, math, sys, shutil, argparse

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI   = "/home/apex/contiki-ng"
COOJA_DIR = os.path.join(CONTIKI, "tools", "cooja")
TESTLOG   = os.path.join(COOJA_DIR, "COOJA.testlog")
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")

SEEDS = [123456, 234567, 345678, 456789, 567890]

# 100-node topology constants
GW_NODE_ID      = 1
AS_NODE_ID      = 2
FIRST_DEVICE_ID = 81
NUM_DEVICES     = 20

# ─────────────────────────────────────────────────────────────────────────────
# Scheme catalogue
# ─────────────────────────────────────────────────────────────────────────────
SCHEMES = {
    "Base": {
        "source_dir":  os.path.join(REPO, "Base-Scheme",         "Src-DesyncDemo-100"),
        "results_dir": os.path.join(REPO, "Base-Scheme",         "Simulation-Results", "Desync-100"),
        "label":       "Base Scheme (Das & Khatua)",
    },
    "Proposed": {
        "source_dir":  os.path.join(REPO, "Revised-Anonymity",   "Src-DesyncDemo-100"),
        "results_dir": os.path.join(REPO, "Revised-Anonymity",   "Simulation-Results", "Desync-100"),
        "label":       "Proposed (Revised-Anonymity)",
    },
}

SOURCES = [
    "gw-node.c", "as-node.c", "router-node.c", "device-node.c",
    "aes.c", "aes.h", "sha256.c", "sha256.h", "project-conf.h",
]

MAKEFILE_DESYNC = f"""CONTIKI_PROJECT = gw-node as-node router-node device-node
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

# ─────────────────────────────────────────────────────────────────────────────
# CSC topology helpers
# ─────────────────────────────────────────────────────────────────────────────
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


def _mote_entry(x, y, node_id):
    return f"""      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="{x}" y="{y}" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>{node_id}</id>
        </interface_config>
      </mote>"""


def _motetype_block(description, src_name, fw_name, motes_xml):
    return f"""    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>{description}</description>
      <source>[CONTIKI_DIR]/examples/myproject/{src_name}</source>
      <commands>$(MAKE) TARGET=cooja clean
$(MAKE) -j$(CPUS) {fw_name} TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/{fw_name}</firmware>
{MOTE_IFACES}
{motes_xml}
    </motetype>"""


def _build_router_motes():
    """Build 78 router node mote entries (IDs 3–80) in a 10×8 grid matching test-sim-100.csc."""
    lines = []
    nid = 3
    for row_y in range(30, 250, 30):    # y = 30,60,...,240 (8 rows)
        for col_x in range(0, 300, 30): # x = 0,30,...,270 (10 cols)
            if nid > 80:
                break
            lines.append(_mote_entry(col_x, row_y, nid))
            nid += 1
        if nid > 80:
            break
    return "\n".join(lines)


def _build_device_motes():
    """Build 20 device mote entries (IDs 81–100) matching test-sim-100.csc positions."""
    positions = [
        (60, 300), (90, 300), (120, 300), (150, 300), (180, 300),
        (60, 330), (90, 330), (120, 330), (150, 330), (180, 330),
        (60, 360), (90, 360), (120, 360), (150, 360), (180, 360),
        (60, 390), (90, 390), (120, 390), (150, 390), (180, 390),
    ]
    lines = []
    for i, (x, y) in enumerate(positions):
        lines.append(_mote_entry(x, y, FIRST_DEVICE_ID + i))
    return "\n".join(lines)


def generate_csc(scheme, seed):
    gw_mote     = _mote_entry(0, 0, GW_NODE_ID)
    as_mote     = _mote_entry(0, 30, AS_NODE_ID)
    router_motes = _build_router_motes()
    device_motes = _build_device_motes()

    gw_block     = _motetype_block("GW Node",     "gw-node.c",     "gw-node.cooja",     gw_mote)
    as_block     = _motetype_block("AS Node",     "as-node.c",     "as-node.cooja",     as_mote)
    router_block = _motetype_block("Router Node", "router-node.c", "router-node.cooja", router_motes)
    device_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", device_motes)

    # ScriptRunner: wait for all NUM_DEVICES devices (IDs 81–100) to log DESYNC_ROUND4_ENERGY.
    # Nested-if instead of && to avoid bare & in XML.
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<simconf version="2022112801">
  <simulation>
    <title>{scheme} Desync Demo 100-node seed={seed}</title>
    <randomseed>{seed}</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
      org.contikios.cooja.radiomediums.UDGM
      <transmitting_range>150.0</transmitting_range>
      <interference_range>200.0</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>1.0</success_ratio_rx>
    </radiomedium>
    <events>
      <logoutput>40000</logoutput>
    </events>
{gw_block}
{as_block}
{router_block}
{device_block}
  </simulation>
  <plugin>
    org.contikios.cooja.plugins.LogListener
    <plugin_config>
      <filter />
      <formatted_time />
      <coloring />
    </plugin_config>
    <bounds x="400" y="1" height="400" width="800" z="1" />
  </plugin>
  <plugin>
    org.contikios.cooja.plugins.ScriptRunner
    <plugin_config>
      <script>
var completed = {{}};
var nExpected = {NUM_DEVICES};
var firstId   = {FIRST_DEVICE_ID};
TIMEOUT(1800000, log.testOK());
while(true) {{
  log.log(time + " " + id + " " + msg + "\\n");
  if (msg.indexOf("DESYNC_ROUND4_ENERGY") !== -1) {{
    if (id >= firstId) {{
      completed[id] = 1;
      var count = 0;
      for (var k in completed) {{ count++; }}
      if (count >= nExpected) {{
        log.log("EARLY EXIT: all " + nExpected + " devices done\\n");
        log.testOK();
      }}
    }}
  }}
  YIELD();
}}
      </script>
      <active>true</active>
    </plugin_config>
    <bounds x="0" y="600" height="300" width="600" z="3" />
  </plugin>
</simconf>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Build helpers
# ─────────────────────────────────────────────────────────────────────────────

def prepare_build(scheme):
    src = SCHEMES[scheme]["source_dir"]
    os.makedirs(MYPROJECT, exist_ok=True)

    build_cooja = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build_cooja):
        shutil.rmtree(build_cooja)

    for fname in SOURCES:
        src_path = os.path.join(src, fname)
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(MYPROJECT, fname))

    with open(os.path.join(MYPROJECT, "Makefile"), "w") as f:
        f.write(MAKEFILE_DESYNC)

    print(f"  Prepared build: {scheme}")


def build_firmware():
    print("  Building firmware (TARGET=cooja)...")
    r = subprocess.run(
        ["make", f"CONTIKI={CONTIKI}", "TARGET=cooja"],
        cwd=MYPROJECT, capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        print(f"  BUILD FAILED:\n{(r.stdout + r.stderr)[-2000:]}")
        return False
    fw = [f for f in os.listdir(os.path.join(MYPROJECT, "build", "cooja"))
          if f.endswith(".cooja")]
    print(f"  Firmware: {fw}")
    return len(fw) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# Simulation runner
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(scheme, seed):
    csc_content = generate_csc(scheme, seed)
    csc_path = os.path.join(MYPROJECT, f"desync100_{scheme}_s{seed}.csc")
    with open(csc_path, "w", encoding="utf-8") as f:
        f.write(csc_content)

    if os.path.isfile(TESTLOG):
        os.remove(TESTLOG)

    cmd = [
        "./gradlew", "--no-watch-fs", "run",
        f"--args=--no-gui --contiki={CONTIKI} --autostart {csc_path}",
    ]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=COOJA_DIR, capture_output=True, text=True, timeout=3600)
    elapsed = time.time() - t0
    output = r.stdout + r.stderr

    log_dest = None
    if os.path.isfile(TESTLOG):
        log_dest = f"/tmp/desync100_testlog_{scheme}_s{seed}.txt"
        shutil.copy2(TESTLOG, log_dest)

    ok = "TEST OK" in output or (
        log_dest and "TEST OK" in open(log_dest, errors="replace").read()
    )

    try:
        os.remove(csc_path)
    except OSError:
        pass

    return ok, elapsed, log_dest


# ─────────────────────────────────────────────────────────────────────────────
# Result extraction
# ─────────────────────────────────────────────────────────────────────────────
ROUND_KEYS = [
    "DESYNC_ENROLL_ENERGY",
    "DESYNC_ROUND1_ENERGY",
    "DESYNC_ROUND2_ENERGY",
    "DESYNC_ROUND3_ENERGY",
    "DESYNC_ROUND4_ENERGY",
]
ROUND_LABELS = ["Enrollment", "Round 1", "Round 2", "Round 3", "Round 4"]

PAT_DESYNC = re.compile(
    r"(DESYNC_(?:ENROLL|ROUND[1-4])_ENERGY)\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)"
)


def extract_first(logfile):
    """Return {marker: {device_id: {cpu, energy}}} — first occurrence per (marker, device)."""
    data = {k: {} for k in ROUND_KEYS}
    with open(logfile, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PAT_DESYNC.search(line)
            if m:
                marker = m.group(1)
                did    = int(m.group(2))
                cpu    = float(m.group(3))
                energy = float(m.group(4))
                if marker in data and did not in data[marker]:
                    data[marker][did] = {"cpu": cpu, "energy": energy}
    return data


def _avg(lst): return sum(lst) / len(lst) if lst else 0.0

def _std(lst):
    if len(lst) < 2:
        return 0.0
    a = _avg(lst)
    return math.sqrt(sum((x - a) ** 2 for x in lst) / len(lst))


# ─────────────────────────────────────────────────────────────────────────────
# Per-scheme runner
# ─────────────────────────────────────────────────────────────────────────────

def run_scheme(scheme, seeds):
    cfg     = SCHEMES[scheme]
    out_dir = os.path.join(cfg["results_dir"], "csv")
    log_dir = os.path.join(cfg["results_dir"], "logs")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  {scheme}  —  {cfg['label']}")
    print(f"{'='*70}")

    all_seeds = {}

    # Load pre-existing logs
    for seed in seeds:
        log_path = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        if os.path.isfile(log_path):
            data = extract_first(log_path)
            all_seeds[seed] = data
            counts = {k.replace("DESYNC_", "").replace("_ENERGY", ""): len(v)
                      for k, v in data.items()}
            print(f"  --- Seed {seed}  [loaded]  {counts}")

    new_seeds = [s for s in seeds if s not in all_seeds]
    if new_seeds:
        prepare_build(scheme)
        if not build_firmware():
            print("  Skipping new seeds — build failed.")
            new_seeds = []

    for seed in new_seeds:
        print(f"\n  --- Seed {seed}")
        ok, elapsed, log_tmp = run_simulation(scheme, seed)
        status = "TEST OK" if ok else "TIMEOUT/FAILED"
        print(f"  Result: {status}  ({elapsed:.0f}s)")

        if not log_tmp or not os.path.isfile(log_tmp):
            print("  No testlog — skipping seed.")
            continue

        log_path = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        shutil.copy2(log_tmp, log_path)
        os.remove(log_tmp)

        data = extract_first(log_path)
        all_seeds[seed] = data
        counts = {k.replace("DESYNC_", "").replace("_ENERGY", ""): len(v)
                  for k, v in data.items()}
        print(f"  Parsed: {counts}")

    if not all_seeds:
        print(f"  No results for {scheme}.")
        return None

    # Per-seed raw CSVs
    col_names = [k.replace("DESYNC_", "").replace("_ENERGY", "") for k in ROUND_KEYS]
    for seed, data in all_seeds.items():
        seed_path = os.path.join(out_dir, f"raw_seed{seed}.csv")
        with open(seed_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Device_ID"]
                       + [f"{c}_cpu_s"    for c in col_names]
                       + [f"{c}_energy_j" for c in col_names])
            devices = sorted(set().union(*[v.keys() for v in data.values()]))
            for did in devices:
                row = [did]
                for k in ROUND_KEYS:
                    row.append(f"{data[k].get(did, {}).get('cpu', float('nan')):.8f}")
                for k in ROUND_KEYS:
                    row.append(f"{data[k].get(did, {}).get('energy', float('nan')):.8f}")
                w.writerow(row)

    # Summary: per-round averages (energy + cpu) across seeds and devices
    summary_path = os.path.join(out_dir, "summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Round", "Seeds", "Avg_Devices",
                    "Avg_CPU_s", "Std_CPU_s",
                    "Avg_Energy_mJ", "Std_Energy_mJ"])
        for key, label in zip(ROUND_KEYS, ROUND_LABELS):
            per_seed_energy, per_seed_cpu, n_devs = [], [], []
            for data in all_seeds.values():
                devs = list(data[key].values())
                if devs:
                    per_seed_energy.append(_avg([d["energy"] for d in devs]))
                    per_seed_cpu.append(   _avg([d["cpu"]    for d in devs]))
                    n_devs.append(len(devs))
            if not per_seed_energy:
                continue
            w.writerow([
                label,
                len(per_seed_energy),
                f"{_avg(n_devs):.1f}",
                f"{_avg(per_seed_cpu):.6f}",
                f"{_std(per_seed_cpu):.6f}",
                f"{_avg(per_seed_energy) * 1000:.4f}",
                f"{_std(per_seed_energy) * 1000:.4f}",
            ])

    # Bar summary: Normal (Enroll+R1) and Recovery (Enroll+R1+R2+R3)
    bar_path = os.path.join(out_dir, "bar_summary.csv")
    with open(bar_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Bar", "Seeds", "Avg_Devices",
                    "Avg_CPU_s", "Std_CPU_s",
                    "Avg_Energy_mJ", "Std_Energy_mJ"])

        normal_keys   = ["DESYNC_ENROLL_ENERGY", "DESYNC_ROUND1_ENERGY"]
        recovery_keys = ["DESYNC_ENROLL_ENERGY", "DESYNC_ROUND1_ENERGY",
                         "DESYNC_ROUND2_ENERGY", "DESYNC_ROUND3_ENERGY"]

        for bar_label, keys in [("Normal", normal_keys), ("Recovery", recovery_keys)]:
            per_seed_e, per_seed_c, n_devs = [], [], []
            for data in all_seeds.values():
                # Sum across rounds for each device that has all required keys
                devices_all = None
                for k in keys:
                    d_set = set(data[k].keys())
                    devices_all = d_set if devices_all is None else devices_all & d_set
                if not devices_all:
                    continue
                energy_vals = [sum(data[k][did]["energy"] for k in keys) for did in devices_all]
                cpu_vals    = [sum(data[k][did]["cpu"]    for k in keys) for did in devices_all]
                per_seed_e.append(_avg(energy_vals))
                per_seed_c.append(_avg(cpu_vals))
                n_devs.append(len(devices_all))

            if not per_seed_e:
                continue
            w.writerow([
                bar_label,
                len(per_seed_e),
                f"{_avg(n_devs):.1f}",
                f"{_avg(per_seed_c):.6f}",
                f"{_std(per_seed_c):.6f}",
                f"{_avg(per_seed_e) * 1000:.4f}",
                f"{_std(per_seed_e) * 1000:.4f}",
            ])

    print(f"  Summary: {summary_path}")
    print(f"  Bar summary: {bar_path}")
    return bar_path


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Desync comparison 100-node (Base vs Proposed)")
    parser.add_argument("--scheme", choices=list(SCHEMES.keys()), nargs="+",
                        default=list(SCHEMES.keys()))
    parser.add_argument("--seeds", type=int, default=len(SEEDS),
                        help=f"Number of seeds to use (default: {len(SEEDS)})")
    args = parser.parse_args()

    seeds   = SEEDS[: args.seeds]
    schemes = args.scheme

    print("Desync Comparison Runner — 100-node topology")
    print(f"  Schemes    : {schemes}")
    print(f"  Seeds      : {seeds}")
    print(f"  Topology   : 1 GW + 1 AS + 78 routers + {NUM_DEVICES} devices (IDs {FIRST_DEVICE_ID}–{FIRST_DEVICE_ID+NUM_DEVICES-1})")
    print(f"  COOJA      : {COOJA_DIR}")

    results = {}
    for scheme in schemes:
        bar_path = run_scheme(scheme, seeds)
        if bar_path:
            results[scheme] = bar_path

    print(f"\n{'='*70}")
    print("  DONE")
    for scheme, path in results.items():
        print(f"  {scheme}: {path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
