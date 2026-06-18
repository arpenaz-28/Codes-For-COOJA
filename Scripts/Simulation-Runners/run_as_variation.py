"""
run_as_variation.py
Run RA and LAAKA schemes across 4 active-AS counts (2, 5, 10, 15).

Fixed topology for all variants:
  1 GW (node 1) + 79 AS/Fog nodes (nodes 2–80) + 20 devices (nodes 81–100)
  = 100 nodes total

The active AS count controls how many of the 79 fog/AS nodes actually serve
authentication requests.  Devices are distributed round-robin across active AS.

Usage:
  python3 run_as_variation.py                          # both schemes, all 4 counts
  python3 run_as_variation.py --scheme RA              # only Revised-Anonymity
  python3 run_as_variation.py --scheme LAAKA --count 2 5
  python3 run_as_variation.py --seeds 3                # 3 seeds instead of 10
"""

import subprocess, os, re, csv, time, math, sys, shutil, argparse

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI   = "/home/apex/contiki-ng"
COOJA_DIR = os.path.join(CONTIKI, "tools", "cooja")
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")
TESTLOG   = os.path.join(COOJA_DIR, "COOJA.testlog")

SEEDS = [123456, 234567, 345678, 456789, 567890,
         678901, 789012, 890123, 901234, 112345]

# Active-AS counts to evaluate
AS_COUNTS = [2, 5, 10, 15]

# Fixed topology: 1 GW + 79 AS (nodes 2–80) + 20 devices (nodes 81–100)
N_TOTAL        = 100
N_AS_TOTAL     = 79   # all AS/fog nodes present in the simulation
N_DEVICES      = 20
FIRST_DEV_ID   = 81   # nodes 81–100 are devices

# ─────────────────────────────────────────────────────────────────────────────
# Scheme configuration
# ─────────────────────────────────────────────────────────────────────────────
SCHEME_CFG = {
    "RA": {
        "base_source_dir":    os.path.join(REPO, "Revised-Anonymity", "Src-ASVariation"),
        "variant_source_dir": os.path.join(REPO, "Revised-Anonymity", "AS-Variation"),
        "conf_dirs": {
            n: os.path.join(REPO, "Revised-Anonymity", "AS-Variation", f"N{n}")
            for n in AS_COUNTS
        },
        "results_base": os.path.join(REPO, "Revised-Anonymity", "Simulation results", "as-variation"),
        "variant_files": ["device-node.c"],           # files overridden from variant_source_dir
        "as_label": "AS",
    },
    "LAAKA": {
        "base_source_dir":    os.path.join(REPO, "LAAKA"),
        "variant_source_dir": os.path.join(REPO, "LAAKA", "AS-Variation"),
        "conf_dirs": {
            n: os.path.join(REPO, "LAAKA", "AS-Variation", f"N{n}")
            for n in AS_COUNTS
        },
        "results_base": os.path.join(REPO, "LAAKA", "Simulation results", "as-variation"),
        "variant_files": ["device-node.c", "gw-node.c"],  # gw-node also modified
        "as_label": "Fog",
    },
    "Banerjee": {
        "base_source_dir":    os.path.join(REPO, "Banerjee-Scheme"),
        "variant_source_dir": os.path.join(REPO, "Banerjee-Scheme", "AS-Variation"),
        "conf_dirs": {
            n: os.path.join(REPO, "Banerjee-Scheme", "AS-Variation", f"N{n}")
            for n in [2, 5, 10]
        },
        "results_base": os.path.join(REPO, "Banerjee-Scheme", "Simulation results", "as-variation"),
        "variant_files": ["device-node.c", "gw-node.c"],
        "as_label": "SD",
    },
}

RA_SOURCES = ["gw-node.c", "as-node.c", "device-node.c",
              "aes.c", "aes.h", "sha256.c", "sha256.h", "project-conf.h"]

MAKEFILE_RA = f"""CONTIKI_PROJECT = device-node as-node gw-node
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
# CSC generator — fixed 100-node topology
# ─────────────────────────────────────────────────────────────────────────────
MOTE_IFACES = """      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
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
          <pos x="{x:.1f}" y="{y:.1f}" />
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


def grid_positions(n, cols=10, spacing=30.0, x_off=0.0, y_off=0.0):
    return [(x_off + (i % cols) * spacing, y_off + (i // cols) * spacing)
            for i in range(n)]


def generate_csc(scheme, n_as_count, seed):
    """
    Generate CSC for fixed 100-node topology.
    All 79 AS/fog nodes are present; only n_as_count are configured active in firmware.
    """
    # GW — node 1, centre
    gw_motes = _mote_entry(150.0, 150.0, 1)

    # AS/Fog nodes — IDs 2 to 80
    as_positions = grid_positions(N_AS_TOTAL, cols=10, spacing=30.0, x_off=0.0, y_off=60.0)
    as_motes = "\n".join(_mote_entry(px, py, 2 + i)
                         for i, (px, py) in enumerate(as_positions))

    # Device nodes — IDs 81 to 100, row below AS grid
    n_rows_as = math.ceil(N_AS_TOTAL / 10)
    dev_y_off = 60.0 + n_rows_as * 30.0 + 30.0
    dev_positions = grid_positions(N_DEVICES, cols=10, spacing=30.0,
                                   x_off=0.0, y_off=dev_y_off)
    dev_motes = "\n".join(_mote_entry(px, py, FIRST_DEV_ID + i)
                          for i, (px, py) in enumerate(dev_positions))

    if scheme == "RA":
        as_block  = _motetype_block("AS Node", "as-node.c", "as-node.cooja", as_motes)
        dev_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", dev_motes)
    elif scheme == "Banerjee":
        as_block  = _motetype_block("SD (Sensing Device)", "as-node.c", "as-node.cooja", as_motes)
        dev_block = _motetype_block("U (User)", "device-node.c", "device-node.cooja", dev_motes)
    else:  # LAAKA
        as_block  = _motetype_block("Fog AS Node", "as-node.c", "as-node.cooja", as_motes)
        dev_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", dev_motes)

    gw_block = _motetype_block("GW Node", "gw-node.c", "gw-node.cooja", gw_motes)

    timeout_ms = 1800000  # 30 min

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<simconf version="2022112801">
  <simulation>
    <title>{scheme} AS={n_as_count} Authenticator Variation</title>
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
{dev_block}
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
TIMEOUT({timeout_ms}, log.testOK());
while(true) {{
  log.log(time + " " + id + " " + msg + "\\n");
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
def prepare_build(scheme, n_as_count):
    """
    Copy source files into MYPROJECT:
      1. Base sources from base_source_dir
      2. Variant-specific overrides from variant_source_dir
      3. project-conf.h from the per-count conf_dir
    """
    cfg = SCHEME_CFG[scheme]

    os.makedirs(MYPROJECT, exist_ok=True)
    build_cooja = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build_cooja):
        shutil.rmtree(build_cooja)

    # Step 1: copy base source files
    for fname in RA_SOURCES:
        src_path = os.path.join(cfg["base_source_dir"], fname)
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(MYPROJECT, fname))

    # Step 2: override with variant-specific modified files
    for fname in cfg["variant_files"]:
        override = os.path.join(cfg["variant_source_dir"], fname)
        if os.path.exists(override):
            shutil.copy2(override, os.path.join(MYPROJECT, fname))

    # Step 3: write Makefile
    with open(os.path.join(MYPROJECT, "Makefile"), "w") as f:
        f.write(MAKEFILE_RA)

    # Step 4: copy variant project-conf.h
    conf_h = os.path.join(cfg["conf_dirs"][n_as_count], "project-conf.h")
    if not os.path.exists(conf_h):
        raise FileNotFoundError(f"Missing: {conf_h}")
    shutil.copy2(conf_h, os.path.join(MYPROJECT, "project-conf.h"))

    print(f"  Prepared source: {scheme} AS={n_as_count}")


def build_firmware():
    print("  Building firmware (TARGET=cooja)...")
    r = subprocess.run(
        ["make", f"CONTIKI={CONTIKI}", "TARGET=cooja"],
        cwd=MYPROJECT, capture_output=True, text=True, timeout=300
    )
    if r.returncode != 0:
        print(f"  BUILD FAILED:\n{(r.stdout + r.stderr)[-1500:]}")
        return False
    fw = [f for f in os.listdir(os.path.join(MYPROJECT, "build", "cooja"))
          if f.endswith(".cooja")]
    print(f"  Firmware built: {fw}")
    return len(fw) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# Simulation runner
# ─────────────────────────────────────────────────────────────────────────────
def run_simulation(scheme, n_as_count, seed):
    csc_content = generate_csc(scheme, n_as_count, seed)
    csc_path = os.path.join(MYPROJECT, f"asvar_{scheme}_AS{n_as_count}_s{seed}.csc")
    with open(csc_path, "w", encoding="utf-8") as f:
        f.write(csc_content)

    if os.path.isfile(TESTLOG):
        os.remove(TESTLOG)

    cmd = [
        "./gradlew", "--no-watch-fs", "run",
        f"--args=--no-gui --contiki={CONTIKI} --autostart {csc_path}"
    ]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=COOJA_DIR, capture_output=True, text=True, timeout=2100)
    elapsed = time.time() - t0
    output = r.stdout + r.stderr

    log_dest = None
    if os.path.isfile(TESTLOG):
        log_dest = f"/tmp/asvar_testlog_{scheme}_AS{n_as_count}_s{seed}.txt"
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
PAT_E = re.compile(r"ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_A = re.compile(r"AUTH_ENERGY\|(\d+)\|(?:cpu_ticks=\d+\|energy_ticks=\d+\|)?cpu_s=([\d.]+)\|energy_j=([\d.]+)")
PAT_K = re.compile(r"KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)")


def extract_first(logfile):
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


def write_per_device_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Device_ID", "CPU_Time_s", "Energy_J"])
        for r in sorted(rows, key=lambda x: x["id"]):
            w.writerow([r["id"], f"{r['cpu']:.6f}", f"{r['energy']:.6f}"])


def avg_across_seeds(all_seeds, phase_key):
    acc = {}
    for data in all_seeds.values():
        for r in data[phase_key]:
            did = r["id"]
            if did not in acc:
                acc[did] = {"id": did, "cpu": 0.0, "energy": 0.0, "n": 0}
            acc[did]["cpu"]    += r["cpu"]
            acc[did]["energy"] += r["energy"]
            acc[did]["n"]      += 1
    return [{"id": did, "cpu": v["cpu"] / v["n"], "energy": v["energy"] / v["n"]}
            for did, v in acc.items()]


def write_summary(all_seeds, out_dir, n_seeds_used):
    phases = [("enroll", "Enrollment"),
              ("auth",   "Authentication"),
              ("keyex",  "Key Exchange")]

    summary_path = os.path.join(out_dir, "summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Phase", "Seeds", "n_devices",
                    "Avg_CPU_s", "Std_CPU_s", "CI95_CPU_s",
                    "Avg_Energy_mJ", "Std_Energy_mJ", "CI95_Energy_mJ"])
        for key, name in phases:
            per_seed_cpu, per_seed_energy, ns = [], [], []
            for sd, data in all_seeds.items():
                rows = data[key]
                if not rows:
                    continue
                per_seed_cpu.append(avg([r["cpu"] for r in rows]))
                per_seed_energy.append(avg([r["energy"] for r in rows]))
                ns.append(len(rows))
            if not per_seed_cpu:
                continue
            n_avg = int(round(avg(ns)))
            ac, ae = avg(per_seed_cpu), avg(per_seed_energy)
            sc, se = std(per_seed_cpu), std(per_seed_energy)
            cc, ce = ci95(per_seed_cpu), ci95(per_seed_energy)
            w.writerow([name, n_seeds_used, n_avg,
                        f"{ac:.6f}", f"{sc:.6f}", f"{cc:.6f}",
                        f"{ae * 1000:.4f}", f"{se * 1000:.4f}", f"{ce * 1000:.4f}"])
    return summary_path


# ─────────────────────────────────────────────────────────────────────────────
# Main variant loop
# ─────────────────────────────────────────────────────────────────────────────
def run_variant(scheme, n_as_count, seeds):
    cfg = SCHEME_CFG[scheme]
    out_dir = os.path.join(cfg["results_base"], f"N{n_as_count}", "csv")
    log_dir = os.path.join(cfg["results_base"], f"N{n_as_count}", "logs")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    print(f"\n{'=' * 70}")
    print(f"  {scheme}  active_{cfg['as_label']}={n_as_count}  ({N_DEVICES} devices)")
    print(f"{'=' * 70}")

    # Load existing logs first
    all_seeds = {}
    for seed in seeds:
        log_dest = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        if os.path.isfile(log_dest):
            enroll, auth, keyex = extract_first(log_dest)
            all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
            print(f"  --- Seed {seed}  [loaded from existing log]")
            print(f"  Devices: E={len(enroll)}  A={len(auth)}  K={len(keyex)}")

    new_seeds = [s for s in seeds if s not in all_seeds]
    if new_seeds:
        prepare_build(scheme, n_as_count)
        if not build_firmware():
            print("  Skipping new seeds — build failed.")
            new_seeds = []

    for seed in new_seeds:
        print(f"\n  --- Seed {seed}")
        ok, elapsed, log_tmp = run_simulation(scheme, n_as_count, seed)
        status = "TEST OK" if ok else "TIMEOUT/FAILED"
        print(f"  Result : {status}  ({elapsed:.0f}s)")

        if not log_tmp or not os.path.isfile(log_tmp):
            print("  No testlog — skipping seed.")
            continue

        log_dest = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        shutil.copy2(log_tmp, log_dest)
        os.remove(log_tmp)

        enroll, auth, keyex = extract_first(log_dest)
        all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
        print(f"  Devices: E={len(enroll)}  A={len(auth)}  K={len(keyex)}")

    if not all_seeds:
        print("  No results collected.")
        return

    write_per_device_csv(avg_across_seeds(all_seeds, "enroll"),
                         os.path.join(out_dir, "enroll-results.csv"))
    write_per_device_csv(avg_across_seeds(all_seeds, "auth"),
                         os.path.join(out_dir, "auth-results.csv"))
    write_per_device_csv(avg_across_seeds(all_seeds, "keyex"),
                         os.path.join(out_dir, "keyex-results.csv"))

    summary = write_summary(all_seeds, out_dir, len(all_seeds))
    print(f"\n  Summary → {summary}")
    print(f"  Logs    → {log_dir}")


def main():
    parser = argparse.ArgumentParser(description="Authenticator-variation simulations")
    parser.add_argument("--scheme", nargs="+", choices=["RA", "LAAKA", "Banerjee"],
                        default=["RA", "LAAKA"],
                        help="Schemes to run (default: RA LAAKA)")
    parser.add_argument("--count", nargs="+", type=int, choices=[2, 5, 10, 15],
                        default=[2, 5, 10, 15],
                        help="Active-AS counts (default: 2 5 10 15)")
    parser.add_argument("--seeds", type=int, default=10,
                        help="Number of random seeds (1–10, default: 10)")
    args = parser.parse_args()

    seeds = SEEDS[:args.seeds]

    print("Authenticator Variation Simulation Runner")
    print(f"  Schemes  : {args.scheme}")
    print(f"  AS counts: {args.count}")
    print(f"  Seeds    : {seeds}")
    print(f"  Topology : 1 GW + {N_AS_TOTAL} AS/Fog + {N_DEVICES} devices = {N_TOTAL} nodes")
    print(f"  COOJA    : {COOJA_DIR}")
    print(f"  Build    : {MYPROJECT}")

    for scheme in args.scheme:
        valid_counts = sorted(
            n for n in args.count if n in SCHEME_CFG[scheme]["conf_dirs"]
        )
        for n in valid_counts:
            run_variant(scheme, n, seeds)

    print("\n" + "=" * 70)
    print("All done.  Run plot_as_variation.py to generate charts.")
    print("=" * 70)


if __name__ == "__main__":
    main()
