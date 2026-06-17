"""
run_network_variation.py
Run all 3 schemes × 4 network sizes for the network-scalability study.
Uses the local COOJA installation (no Docker required).

Topology (all sizes, 20% devices, 2 active AS/GW-servers):
  N=30  : 1 GW + 23 AS (2 active) +  6 devices  (IDs 25–30)
  N=50  : 1 GW + 39 AS (2 active) + 10 devices  (IDs 41–50)
  N=80  : 1 GW + 63 AS (2 active) + 16 devices  (IDs 65–80)
  N=100 : 1 GW + 79 AS (2 active) + 20 devices  (IDs 81–100)

Zhou additionally has paired SN nodes (1 SN per user/device).

Simulations terminate early once all devices log their final-phase
energy marker (KEYEX_ENERGY for RA/LAAKA, AUTH_ENERGY for Zhou).
A per-size safety timeout is used if early exit never triggers.

Usage:
  python3 run_network_variation.py                      # all schemes, all sizes
  python3 run_network_variation.py --scheme RA          # only Revised-Anonymity
  python3 run_network_variation.py --scheme LAAKA --size 30 50
  python3 run_network_variation.py --seeds 5            # use 5 seeds instead of 10
"""

import subprocess, os, re, csv, time, math, sys, shutil, argparse
import xml.etree.ElementTree as ET

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
REPO        = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI     = "/home/apex/contiki-ng"
COOJA_DIR   = os.path.join(CONTIKI, "tools", "cooja")
BUILD_DIR   = "/tmp/cooja-netvar-build"   # scratch build area
TESTLOG     = os.path.join(COOJA_DIR, "COOJA.testlog")

SEEDS = [123456, 234567, 345678, 456789, 567890,
         678901, 789012, 890123, 901234, 112345]

# ─────────────────────────────────────────────────────────────────────────────
# Variant catalogue
# ─────────────────────────────────────────────────────────────────────────────
# Each entry: (n_as, n_devices, first_device_id)  — for RA and LAAKA
SIZES = {
    30:  (23,  6, 25),
    50:  (39, 10, 41),
    80:  (63, 16, 65),
    100: (79, 20, 81),
    120: (95, 24, 97),   # 24 newly-joined devices (20% of 120), 95 AS, 1 GW
}

# Zhou topology: 1 GW + 2 GW-servers + N_SN sensor nodes + N_users user nodes
# Each entry: (n_sn, last_sn_id, n_users, first_user_id)
ZHOU_SIZES = {
    30:  (21, 24,  6, 25),
    50:  (37, 40, 10, 41),
    80:  (61, 64, 16, 65),
    100: (77, 80, 20, 81),
    120: (93, 96, 24, 97),   # 24 users (20%), 93 SN (ids 4-96), users 97-120
}

SCHEME_CFG = {
    "RA": {
        "source_dir":  os.path.join(REPO, "Revised-Anonymity", "Src-20AS-79Dev"),
        "conf_dirs": {
            30:  os.path.join(REPO, "Revised-Anonymity", "NetVar-N30"),
            50:  os.path.join(REPO, "Revised-Anonymity", "NetVar-N50"),
            80:  os.path.join(REPO, "Revised-Anonymity", "NetVar-N80"),
            100: os.path.join(REPO, "Revised-Anonymity", "NetVar-N100"),
            120: os.path.join(REPO, "Revised-Anonymity", "NetVar-N120"),
        },
        "results_base": os.path.join(REPO, "Revised-Anonymity", "Simulation results", "network-variation"),
        "node_files":   ["gw-node.c", "as-node.c", "device-node.c"],
        "device_pattern_prefix": "",   # uses ENROLL/AUTH/KEYEX_ENERGY
    },
    "LAAKA": {
        "source_dir":  os.path.join(REPO, "LAAKA"),
        "conf_dirs": {
            30:  os.path.join(REPO, "LAAKA", "Network-Variation", "N30"),
            50:  os.path.join(REPO, "LAAKA", "Network-Variation", "N50"),
            80:  os.path.join(REPO, "LAAKA", "Network-Variation", "N80"),
            100: os.path.join(REPO, "LAAKA", "Network-Variation", "N100"),
            120: os.path.join(REPO, "LAAKA", "Network-Variation", "N120"),
        },
        "results_base": os.path.join(REPO, "LAAKA", "Simulation results", "network-variation"),
        "node_files":   ["gw-node.c", "as-node.c", "device-node.c"],
        "device_pattern_prefix": "",
    },
    "Zhou": {
        "source_dir":  os.path.join(REPO, "Zhou-Scheme"),
        "conf_dirs": {
            30:  os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N30"),
            50:  os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N50"),
            80:  os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N80"),
            100: os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N100"),
            120: os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N120"),
        },
        "results_base": os.path.join(REPO, "Zhou-Scheme", "Simulation results", "network-variation"),
        "node_files":   ["gw-node.c", "gw-server.c", "sn-node.c", "user-node.c"],
        "device_pattern_prefix": "",
    },
    "Li": {
        "source_dir":  os.path.join(REPO, "Li-Scheme"),
        "conf_dirs": {
            30:  os.path.join(REPO, "Li-Scheme"),
            50:  os.path.join(REPO, "Li-Scheme"),
            80:  os.path.join(REPO, "Li-Scheme"),
            100: os.path.join(REPO, "Li-Scheme"),
            120: os.path.join(REPO, "Li-Scheme"),
        },
        "results_base": os.path.join(REPO, "Li-Scheme", "Simulation results", "network-variation"),
        "node_files":   ["gw-node.c", "as-node.c", "device-node.c"],
        "device_pattern_prefix": "",
    },
}

# Zhou uses "user" nodes; RA & LAAKA use "device" nodes
ZHOU_SOURCES = ["gw-node.c", "gw-server.c", "sn-node.c", "user-node.c",
                "aes.c", "aes.h", "sha256.c", "sha256.h", "project-conf.h"]
RA_SOURCES   = ["gw-node.c", "as-node.c", "device-node.c",
                "aes.c", "aes.h", "sha256.c", "sha256.h", "project-conf.h"]
# Li adds real ECC (micro-ecc) + the ecc-util wrapper to the RA file set.
LI_SOURCES   = ["gw-node.c", "as-node.c", "device-node.c",
                "ecc-util.h", "uECC.c", "uECC.h", "types.h",
                "aes.c", "aes.h", "sha256.c", "sha256.h", "project-conf.h"]

# Makefile templates with absolute CONTIKI path (relative paths break inside myproject)
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

MAKEFILE_ZHOU = f"""CONTIKI_PROJECT = user-node gw-server sn-node gw-node
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

MAKEFILE_LI = f"""CONTIKI_PROJECT = device-node as-node gw-node
all: $(CONTIKI_PROJECT)

CONTIKI = {CONTIKI}
PROJECT_SOURCEFILES += aes.c sha256.c uECC.c
MODULES += os/net/app-layer/coap

CFLAGS += -DuECC_SUPPORTS_secp256r1=1
CFLAGS += -DuECC_SUPPORT_COMPRESSED_POINT=0
CFLAGS += -DuECC_OPTIMIZATION_LEVEL=2
CFLAGS += -Wno-error=unused-function
CFLAGS += -Wno-error=unused-variable
CFLAGS += -Wno-error=unused-result
CFLAGS += -Wno-error=unused-but-set-variable

include $(CONTIKI)/Makefile.include
"""

# ─────────────────────────────────────────────────────────────────────────────
# CSC generator
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
    """Return list of (x, y) positions in a left-to-right grid."""
    return [(x_off + (i % cols) * spacing,
             y_off + (i // cols) * spacing)
            for i in range(n)]


def generate_csc(scheme, n_total, seed, project_dir):
    """
    Generate a COOJA .csc XML string for the given scheme and network size.
    project_dir is the path COOJA sees as [CONTIKI_DIR]/examples/myproject.
    """
    n_as, n_dev, first_dev = SIZES[n_total]

    # Early-exit defaults (RA / LAAKA): all devices have logged KEYEX_ENERGY
    _done_marker = "KEYEX_ENERGY"
    _n_expected  = n_dev
    _first_id    = first_dev

    # GW — always node 1, centre
    gw_motes = _mote_entry(150.0, 150.0, 1)

    # AS / Fog / GW-server nodes: IDs 2 … n_as+1, grid starting at (0,60)
    as_positions = grid_positions(n_as, cols=10, spacing=30.0, x_off=0.0, y_off=60.0)
    as_motes = "\n".join(_mote_entry(px, py, 2 + i)
                         for i, (px, py) in enumerate(as_positions))

    # Device / User nodes: IDs first_dev … n_total, row below AS
    n_rows_as = math.ceil(n_as / 10)
    dev_y_off = 60.0 + n_rows_as * 30.0 + 30.0
    dev_positions = grid_positions(n_dev, cols=10, spacing=30.0,
                                   x_off=0.0, y_off=dev_y_off)
    dev_motes = "\n".join(_mote_entry(px, py, first_dev + i)
                          for i, (px, py) in enumerate(dev_positions))

    if scheme == "Zhou":
        # Zhou topology: 1 GW + 2 GW-servers (nodes 2-3) + N_SN sn-nodes + N_users user-nodes
        n_sn, last_sn_id, n_users, first_user_id = ZHOU_SIZES[n_total]
        # Override early-exit: all users have logged AUTH_ENERGY (no KeyEx phase)
        _done_marker = "AUTH_ENERGY"
        _n_expected  = n_users
        _first_id    = first_user_id

        # One CONTINUOUS uniform grid for all Zhou nodes, in node-ID order, with
        # the SAME firmware split as the clean 10-seed run: ONLY the n_users
        # user-bound SNs run the active sn-node.c; the remaining SN slots are
        # IDLE FILLER running gw-server.c (which does nothing for node_id !=
        # GW_SERVER_ID/ID2). Previously all n_sn SNs ran sn-node.c, so 77 active
        # sensors flooded the medium and inflated Zhou's relayed-auth energy
        # (only Zhou is relay-based, so only Zhou suffered). Clean run = 20
        # active SN + 57 idle filler; we now reproduce that exactly.
        all_pos = grid_positions(n_total, cols=10, spacing=30.0, x_off=0.0, y_off=0.0)
        n_active_sn = n_users            # user-bound SNs (ids 4 .. 3+n_users)
        n_filler    = n_sn - n_users     # idle filler SN slots → gw-server.c

        # GW (node 1) takes the first grid cell (override the centre default)
        gw_motes = _mote_entry(all_pos[0][0], all_pos[0][1], 1)

        # GW-server firmware: the 2 active servers (nodes 2,3) + all idle fillers
        srv_entries = [_mote_entry(all_pos[1][0], all_pos[1][1], 2),
                       _mote_entry(all_pos[2][0], all_pos[2][1], 3)]
        for i in range(n_filler):
            cell = 3 + n_active_sn + i
            fid  = 4 + n_active_sn + i
            srv_entries.append(_mote_entry(all_pos[cell][0], all_pos[cell][1], fid))
        gw_srv_block = _motetype_block("GW Server Node", "gw-server.c", "gw-server.cooja",
                                       "\n".join(srv_entries))

        # Active (user-bound) sensor nodes: ids 4 .. 3+n_active_sn (cells 3 ..)
        sn_motes = "\n".join(_mote_entry(all_pos[3 + i][0], all_pos[3 + i][1], 4 + i)
                             for i in range(n_active_sn))
        sn_block = _motetype_block("Sensor Node (SN)", "sn-node.c", "sn-node.cooja", sn_motes)

        # User motes: nodes first_user_id .. n_total (grid cells 3+n_sn ..)
        user_motes = "\n".join(_mote_entry(all_pos[3 + n_sn + i][0], all_pos[3 + n_sn + i][1],
                                           first_user_id + i)
                               for i in range(n_users))
        dev_block = _motetype_block("User Node", "user-node.c", "user-node.cooja", user_motes)

        extra_blocks = f"{gw_srv_block}\n{sn_block}\n{dev_block}"
    else:
        if scheme in ("RA", "Li"):
            as_block  = _motetype_block("AS/SN Node", "as-node.c", "as-node.cooja", as_motes)
            dev_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", dev_motes)
        else:  # LAAKA
            as_block  = _motetype_block("Fog AS Node", "as-node.c", "as-node.cooja", as_motes)
            dev_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", dev_motes)
        extra_blocks = f"{as_block}\n{dev_block}"

    gw_block = _motetype_block("GW Node", "gw-node.c", "gw-node.cooja", gw_motes)

    # Per-size safety timeout (early exit fires before this in normal runs)
    _timeouts_ms = {30: 600000, 50: 900000, 80: 1200000, 100: 1500000}
    timeout_ms = _timeouts_ms.get(n_total, 1800000)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<simconf version="2022112801">
  <simulation>
    <title>{scheme} N={n_total} Network Variation</title>
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
{extra_blocks}
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
var nExpected = {_n_expected};
var firstId   = {_first_id};
TIMEOUT({timeout_ms}, log.testOK());
while(true) {{
  log.log(time + " " + id + " " + msg + "\\n");
  if (msg.indexOf("{_done_marker}") !== -1) {{
    if (id >= firstId) {{
      completed[id] = 1;
      var count = 0;
      for (var k in completed) {{ count++; }}
      if (count >= nExpected) {{
        log.log("EARLY EXIT: all " + nExpected + " nodes done\\n");
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
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")


def prepare_build(scheme, n_total):
    """Copy source files + variant project-conf.h into MYPROJECT."""
    cfg = SCHEME_CFG[scheme]
    src = cfg["source_dir"]
    conf_dir = cfg["conf_dirs"][n_total]

    os.makedirs(MYPROJECT, exist_ok=True)
    # wipe old build artefacts to force recompile with new conf
    build_cooja = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build_cooja):
        shutil.rmtree(build_cooja)

    file_list = (LI_SOURCES if scheme == "Li"
                 else ZHOU_SOURCES if scheme == "Zhou" else RA_SOURCES)
    for fname in file_list:
        src_path = os.path.join(src, fname)
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(MYPROJECT, fname))

    # Write Makefile with absolute CONTIKI path (relative paths break in myproject)
    makefile_content = (MAKEFILE_LI if scheme == "Li"
                        else MAKEFILE_ZHOU if scheme == "Zhou" else MAKEFILE_RA)
    with open(os.path.join(MYPROJECT, "Makefile"), "w") as f:
        f.write(makefile_content)

    # override project-conf.h with variant version
    variant_conf = os.path.join(conf_dir, "project-conf.h")
    if not os.path.exists(variant_conf):
        raise FileNotFoundError(f"Missing: {variant_conf}")
    shutil.copy2(variant_conf, os.path.join(MYPROJECT, "project-conf.h"))
    print(f"  Prepared source: {scheme} N={n_total}")


def build_firmware():
    """Build all firmware in MYPROJECT. Returns True on success."""
    print("  Building firmware (TARGET=cooja)...")
    r = subprocess.run(
        ["make", f"CONTIKI={CONTIKI}", "TARGET=cooja"],
        cwd=MYPROJECT, capture_output=True, text=True, timeout=300
    )
    if r.returncode != 0:
        print(f"  BUILD FAILED:\n{(r.stdout+r.stderr)[-1500:]}")
        return False
    fw = [f for f in os.listdir(os.path.join(MYPROJECT, "build", "cooja"))
          if f.endswith(".cooja")]
    print(f"  Firmware built: {fw}")
    return len(fw) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# Simulation runner
# ─────────────────────────────────────────────────────────────────────────────
def run_simulation(scheme, n_total, seed):
    """Write CSC, run COOJA headless, return (ok, elapsed, testlog_path)."""
    csc_content = generate_csc(scheme, n_total, seed, MYPROJECT)
    csc_path = os.path.join(MYPROJECT, f"netvar_{scheme}_N{n_total}_s{seed}.csc")
    with open(csc_path, "w", encoding="utf-8") as f:
        f.write(csc_content)

    # Remove stale testlog so we never read a result from a previous run
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

    # TEST OK written to COOJA.testlog by the JavaScript script runner
    log_dest = None
    if os.path.isfile(TESTLOG):
        log_dest = f"/tmp/netvar_testlog_{scheme}_N{n_total}_s{seed}.txt"
        shutil.copy2(TESTLOG, log_dest)

    ok = "TEST OK" in output or (log_dest and "TEST OK" in open(log_dest, errors="replace").read())

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
# Zhou uses AUTH_ENERGY but no KEYEX_ENERGY (key exchange is part of auth phase)


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


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Device_ID", "CPU_Time_s", "Energy_J"])
        for r in sorted(rows, key=lambda x: x["id"]):
            w.writerow([r["id"], f"{r['cpu']:.6f}", f"{r['energy']:.6f}"])


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
                if not rows: continue
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
                        f"{ae*1000:.4f}", f"{se*1000:.4f}", f"{ce*1000:.4f}"])
    return summary_path


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
    return [{"id": did, "cpu": v["cpu"]/v["n"], "energy": v["energy"]/v["n"]}
            for did, v in acc.items()]

# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
def run_variant(scheme, n_total, seeds):
    cfg = SCHEME_CFG[scheme]
    label = f"N{n_total:03d}"
    out_dir = os.path.join(cfg["results_base"], f"N{n_total}", "csv")
    log_dir = os.path.join(cfg["results_base"], f"N{n_total}", "logs")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  {scheme}  N={n_total}  ({SIZES[n_total][1]} devices, 2 active AS)")
    print(f"{'='*70}")

    # Load any existing logs first (skip re-running them)
    all_seeds = {}
    for seed in seeds:
        log_dest = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        if os.path.isfile(log_dest):
            enroll, auth, keyex = extract_first(log_dest)
            all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
            print(f"\n  --- Seed {seed}  [loaded from existing log]")
            print(f"  Devices parsed: E={len(enroll)}  A={len(auth)}  K={len(keyex)}")

    # Run only seeds that don't have a log yet
    new_seeds = [s for s in seeds if s not in all_seeds]
    if new_seeds:
        prepare_build(scheme, n_total)
        if not build_firmware():
            print("  Skipping new seeds — build failed.")
            new_seeds = []

    for seed in new_seeds:
        print(f"\n  --- Seed {seed}")
        ok, elapsed, log_tmp = run_simulation(scheme, n_total, seed)
        status = "TEST OK" if ok else "TIMEOUT/FAILED"
        print(f"  Result : {status}  ({elapsed:.0f}s)")

        if not log_tmp or not os.path.isfile(log_tmp):
            print("  No testlog — skipping seed.")
            continue

        # Save log to results folder
        log_dest = os.path.join(log_dir, f"testlog_seed{seed}.txt")
        shutil.copy2(log_tmp, log_dest)
        os.remove(log_tmp)

        enroll, auth, keyex = extract_first(log_dest)
        all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
        print(f"  Devices parsed: E={len(enroll)}  A={len(auth)}  K={len(keyex)}")

    if not all_seeds:
        print("  No results collected.")
        return

    write_csv(avg_across_seeds(all_seeds, "enroll"),
              os.path.join(out_dir, "enroll-results.csv"))
    write_csv(avg_across_seeds(all_seeds, "auth"),
              os.path.join(out_dir, "auth-results.csv"))
    write_csv(avg_across_seeds(all_seeds, "keyex"),
              os.path.join(out_dir, "keyex-results.csv"))

    summary = write_summary(all_seeds, out_dir, len(all_seeds))
    print(f"\n  Summary saved → {summary}")
    print(f"  Logs saved    → {log_dir}")


def main():
    parser = argparse.ArgumentParser(description="Network variation simulations")
    parser.add_argument("--scheme", nargs="+", choices=["RA", "LAAKA", "Zhou", "Li"],
                        default=["RA", "LAAKA", "Zhou"],
                        help="Which schemes to run (default: all three; add 'Li' explicitly)")
    parser.add_argument("--size", nargs="+", type=int, choices=[30, 50, 80, 100, 120],
                        default=[30, 50, 80, 100],
                        help="Network sizes to simulate (default: all four)")
    parser.add_argument("--seeds", type=int, default=10,
                        help="Number of random seeds to use (1–10, default: 10)")
    args = parser.parse_args()

    seeds = SEEDS[:args.seeds]

    print("Network Variation Simulation Runner")
    print(f"  Schemes : {args.scheme}")
    print(f"  Sizes   : {args.size}")
    print(f"  Seeds   : {seeds}")
    print(f"  COOJA   : {COOJA_DIR}")
    print(f"  Build   : {MYPROJECT}")

    for scheme in args.scheme:
        for n in sorted(args.size):
            run_variant(scheme, n, seeds)

    print("\n" + "="*70)
    print("All done.  Run plot_network_variation.py to generate charts.")
    print("="*70)


if __name__ == "__main__":
    main()
