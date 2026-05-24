"""
run_small_network_variation.py
Run all 3 schemes × 3 small network sizes (N=10, 20, 30) for the small-network study.
N=20 logs are reused from the existing network-variation results if present.
N=10 and N=30 are always run fresh.

Topology (all sizes, 2 active AS, 10% newly joined devices):
  N=10  : 1 GW + 8 AS (2 active) + 1 device   (ID  10)
  N=20  : 1 GW + 17 AS (2 active) + 2 devices  (IDs 19–20)
  N=30  : 1 GW + 26 AS (2 active) + 3 devices  (IDs 28–30)

Zhou topology (1 GW + 2 GW-servers + N_SN SNs + N_users users):
  N=10  : 1 GW + 2 GW-srv + 6 SN + 1 user   (user ID 10)
  N=20  : 1 GW + 2 GW-srv + 15 SN + 2 users  (user IDs 19–20)
  N=30  : 1 GW + 2 GW-srv + 24 SN + 3 users  (user IDs 28–30)

All logs and CSVs are stored in:
  Results/Small-Network-Variation/Testlogs/{RA,LAAKA,Zhou}/N{10,20,30}/
  Results/Small-Network-Variation/CSV-Data/{RA,LAAKA,Zhou}/N{10,20,30}/

Usage:
  python3 run_small_network_variation.py                      # all schemes, all sizes
  python3 run_small_network_variation.py --scheme RA          # only Revised-Anonymity
  python3 run_small_network_variation.py --scheme LAAKA --size 10 30
  python3 run_small_network_variation.py --seeds 3            # use 3 seeds instead of 5
"""

import subprocess, os, re, csv, time, math, sys, shutil, argparse
import xml.etree.ElementTree as ET

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI   = "/home/apex/contiki-ng"
COOJA_DIR = os.path.join(CONTIKI, "tools", "cooja")
TESTLOG   = os.path.join(COOJA_DIR, "COOJA.testlog")

RESULTS_BASE = os.path.join(REPO, "Results", "Small-Network-Variation")

SEEDS = [123456, 234567, 345678, 456789, 567890,
         678901, 789012, 890123, 901234, 112345]

# ─────────────────────────────────────────────────────────────────────────────
# Topology catalogue
# ─────────────────────────────────────────────────────────────────────────────
# (n_as, n_devices, first_device_id)  — for RA and LAAKA
SIZES = {
    10: ( 8, 1, 10),
    20: (17, 2, 19),
    30: (26, 3, 28),
}

# Zhou topology: (n_sn, last_sn_id, n_users, first_user_id)
ZHOU_SIZES = {
    10: ( 6,  9, 1, 10),
    20: (15, 18, 2, 19),
    30: (24, 27, 3, 28),
}

SCHEME_CFG = {
    "RA": {
        "source_dir": os.path.join(REPO, "Revised-Anonymity", "Src-20AS-79Dev"),
        "conf_dirs": {
            10: os.path.join(REPO, "Revised-Anonymity", "NetVar-N10"),
            20: os.path.join(REPO, "Revised-Anonymity", "NetVar-N20"),
            30: os.path.join(REPO, "Revised-Anonymity", "NetVar-N30"),
        },
        # Existing N=20 logs from the original network-variation study
        "existing_log_dirs": {
            20: os.path.join(REPO, "Revised-Anonymity",
                             "Simulation results", "network-variation", "N20", "logs"),
        },
        "label": "RA",
    },
    "LAAKA": {
        "source_dir": os.path.join(REPO, "LAAKA"),
        "conf_dirs": {
            10: os.path.join(REPO, "LAAKA", "Network-Variation", "N10"),
            20: os.path.join(REPO, "LAAKA", "Network-Variation", "N20"),
            30: os.path.join(REPO, "LAAKA", "Network-Variation", "N30"),
        },
        "existing_log_dirs": {
            20: os.path.join(REPO, "LAAKA",
                             "Simulation results", "network-variation", "N20", "logs"),
        },
        "label": "LAAKA",
    },
    "Zhou": {
        "source_dir": os.path.join(REPO, "Zhou-Scheme"),
        "conf_dirs": {
            10: os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N10"),
            20: os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N20"),
            30: os.path.join(REPO, "Zhou-Scheme", "Network-Variation", "N30"),
        },
        "existing_log_dirs": {
            20: os.path.join(REPO, "Zhou-Scheme",
                             "Simulation results", "network-variation", "N20", "logs"),
        },
        "label": "Zhou",
    },
}

ZHOU_SOURCES = ["gw-node.c", "gw-server.c", "sn-node.c", "user-node.c",
                "aes.c", "aes.h", "sha256.c", "sha256.h", "project-conf.h"]
RA_SOURCES   = ["gw-node.c", "as-node.c", "device-node.c",
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
    return [(x_off + (i % cols) * spacing,
             y_off + (i // cols) * spacing)
            for i in range(n)]


def generate_csc(scheme, n_total, seed):
    n_as, n_dev, first_dev = SIZES[n_total]

    gw_motes = _mote_entry(150.0, 150.0, 1)

    as_positions = grid_positions(n_as, cols=10, spacing=30.0, x_off=0.0, y_off=60.0)
    as_motes = "\n".join(_mote_entry(px, py, 2 + i)
                         for i, (px, py) in enumerate(as_positions))

    n_rows_as = math.ceil(n_as / 10)
    dev_y_off = 60.0 + n_rows_as * 30.0 + 30.0
    dev_positions = grid_positions(n_dev, cols=10, spacing=30.0,
                                   x_off=0.0, y_off=dev_y_off)
    dev_motes = "\n".join(_mote_entry(px, py, first_dev + i)
                          for i, (px, py) in enumerate(dev_positions))

    if scheme == "Zhou":
        n_sn, last_sn_id, n_users, first_user_id = ZHOU_SIZES[n_total]

        gw_srv_motes = "\n".join(_mote_entry(30.0 * (i + 1), 30.0, 2 + i) for i in range(2))
        gw_srv_block = _motetype_block("GW Server Node", "gw-server.c", "gw-server.cooja", gw_srv_motes)

        sn_positions = grid_positions(n_sn, cols=10, spacing=30.0, x_off=0.0, y_off=60.0)
        sn_motes = "\n".join(_mote_entry(px, py, 4 + i)
                             for i, (px, py) in enumerate(sn_positions))
        sn_block = _motetype_block("Sensor Node (SN)", "sn-node.c", "sn-node.cooja", sn_motes)

        n_rows_sn = math.ceil(n_sn / 10)
        user_y_off = 60.0 + n_rows_sn * 30.0 + 30.0
        user_positions = grid_positions(n_users, cols=10, spacing=30.0,
                                        x_off=0.0, y_off=user_y_off)
        user_motes = "\n".join(_mote_entry(px, py, first_user_id + i)
                               for i, (px, py) in enumerate(user_positions))
        dev_block = _motetype_block("User Node", "user-node.c", "user-node.cooja", user_motes)

        extra_blocks = f"{gw_srv_block}\n{sn_block}\n{dev_block}"
    else:
        if scheme == "RA":
            as_block  = _motetype_block("AS Node", "as-node.c", "as-node.cooja", as_motes)
            dev_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", dev_motes)
        else:  # LAAKA
            as_block  = _motetype_block("Fog AS Node", "as-node.c", "as-node.cooja", as_motes)
            dev_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", dev_motes)
        extra_blocks = f"{as_block}\n{dev_block}"

    gw_block = _motetype_block("GW Node", "gw-node.c", "gw-node.cooja", gw_motes)

    # Small networks finish much faster — 10 min is sufficient
    timeout_ms = 600000

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<simconf version="2022112801">
  <simulation>
    <title>{scheme} N={n_total} Small Network Variation</title>
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
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")


def prepare_build(scheme, n_total):
    cfg = SCHEME_CFG[scheme]
    src = cfg["source_dir"]
    conf_dir = cfg["conf_dirs"][n_total]

    os.makedirs(MYPROJECT, exist_ok=True)
    build_cooja = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build_cooja):
        shutil.rmtree(build_cooja)

    file_list = ZHOU_SOURCES if scheme == "Zhou" else RA_SOURCES
    for fname in file_list:
        src_path = os.path.join(src, fname)
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(MYPROJECT, fname))

    makefile_content = MAKEFILE_ZHOU if scheme == "Zhou" else MAKEFILE_RA
    with open(os.path.join(MYPROJECT, "Makefile"), "w") as f:
        f.write(makefile_content)

    variant_conf = os.path.join(conf_dir, "project-conf.h")
    if not os.path.exists(variant_conf):
        raise FileNotFoundError(f"Missing: {variant_conf}")
    shutil.copy2(variant_conf, os.path.join(MYPROJECT, "project-conf.h"))
    print(f"  Prepared source: {scheme} N={n_total}")


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
def run_simulation(scheme, n_total, seed):
    csc_content = generate_csc(scheme, n_total, seed)
    csc_path = os.path.join(MYPROJECT, f"smallnet_{scheme}_N{n_total}_s{seed}.csc")
    with open(csc_path, "w", encoding="utf-8") as f:
        f.write(csc_content)

    if os.path.isfile(TESTLOG):
        os.remove(TESTLOG)

    cmd = [
        "./gradlew", "--no-watch-fs", "run",
        f"--args=--no-gui --contiki={CONTIKI} --autostart {csc_path}"
    ]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=COOJA_DIR, capture_output=True, text=True, timeout=1200)
    elapsed = time.time() - t0
    output = r.stdout + r.stderr

    log_dest = None
    if os.path.isfile(TESTLOG):
        log_dest = f"/tmp/smallnet_testlog_{scheme}_N{n_total}_s{seed}.txt"
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


# ─────────────────────────────────────────────────────────────────────────────
# Main variant loop
# ─────────────────────────────────────────────────────────────────────────────
def run_variant(scheme, n_total, seeds, fresh=False):
    cfg    = SCHEME_CFG[scheme]
    label  = cfg["label"]
    log_dir = os.path.join(RESULTS_BASE, "Testlogs", label, f"N{n_total}")
    csv_dir = os.path.join(RESULTS_BASE, "CSV-Data",  label, f"N{n_total}")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(csv_dir, exist_ok=True)

    n_dev = SIZES[n_total][1]

    print(f"\n{'=' * 70}")
    print(f"  {scheme}  N={n_total}  ({n_dev} device(s), 2 active AS)"
          + ("  [FRESH]" if fresh else ""))
    print(f"{'=' * 70}")

    all_seeds = {}

    if not fresh:
        # ── Step 1: load logs already in the small-network results folder
        for seed in seeds:
            log_path = os.path.join(log_dir, f"testlog_seed{seed}.txt")
            if os.path.isfile(log_path):
                enroll, auth, keyex = extract_first(log_path)
                all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
                print(f"  Seed {seed}  [loaded from small-network logs]  "
                      f"E={len(enroll)} A={len(auth)} K={len(keyex)}")

        # ── Step 2: for N=20, copy from the existing network-variation study if available
        existing_src = cfg.get("existing_log_dirs", {}).get(n_total)
        if existing_src and os.path.isdir(existing_src):
            for seed in seeds:
                if seed in all_seeds:
                    continue
                src_log = os.path.join(existing_src, f"testlog_seed{seed}.txt")
                if os.path.isfile(src_log):
                    dst_log = os.path.join(log_dir, f"testlog_seed{seed}.txt")
                    shutil.copy2(src_log, dst_log)
                    enroll, auth, keyex = extract_first(dst_log)
                    all_seeds[seed] = {"enroll": enroll, "auth": auth, "keyex": keyex}
                    print(f"  Seed {seed}  [copied from existing network-variation study]  "
                          f"E={len(enroll)} A={len(auth)} K={len(keyex)}")

    # ── Step 3: run fresh simulations for remaining seeds
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
              os.path.join(csv_dir, "enroll-results.csv"))
    write_csv(avg_across_seeds(all_seeds, "auth"),
              os.path.join(csv_dir, "auth-results.csv"))
    write_csv(avg_across_seeds(all_seeds, "keyex"),
              os.path.join(csv_dir, "keyex-results.csv"))

    summary = write_summary(all_seeds, csv_dir, len(all_seeds))
    print(f"\n  Summary saved → {summary}")
    print(f"  Logs saved    → {log_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Small network variation simulations")
    parser.add_argument("--scheme", nargs="+", choices=["RA", "LAAKA", "Zhou"],
                        default=["RA", "LAAKA", "Zhou"])
    parser.add_argument("--size", nargs="+", type=int, choices=[10, 20, 30],
                        default=[10, 20, 30])
    parser.add_argument("--seeds", type=int, default=5,
                        help="Number of random seeds (1–10, default: 5)")
    parser.add_argument("--fresh", action="store_true",
                        help="Skip cached/copied logs and always run COOJA fresh")
    args = parser.parse_args()

    seeds = SEEDS[:args.seeds]

    print("Small Network Variation Simulation Runner")
    print(f"  Schemes : {args.scheme}")
    print(f"  Sizes   : {args.size}")
    print(f"  Seeds   : {seeds}")
    print(f"  Fresh   : {args.fresh}")
    print(f"  Results : {RESULTS_BASE}")
    print(f"  COOJA   : {COOJA_DIR}")

    for scheme in args.scheme:
        for n in sorted(args.size):
            run_variant(scheme, n, seeds, fresh=args.fresh)

    print("\n" + "=" * 70)
    print("All done.  Run plot_small_network_variation.py to generate charts.")
    print("=" * 70)


if __name__ == "__main__":
    main()
