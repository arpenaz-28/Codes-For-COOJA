#!/usr/bin/env python3
"""
run_dauth_sweep.py
==================================================================
Run the DAuth / Das[1] BASE scheme (Src-DAuth, two-round, fair delta
Energest) across the same three studies as the Proposed scheme so DAuth
can be added as a 4th series to the paper figures:

  --study 10seed : N=100, NUM_AS=2, 10 seeds  → fig_sim_total
  --study as     : N=100, NUM_AS in {2,5,10}  → fig_sim_as_*
  --study net    : N in {30,50,80,100}, NUM_AS=2 → fig_sim_net_*
  --study all    : everything

DAuth emits ENROLL_ENERGY / AUTH_ENERGY / KEYEX_ENERGY per device, exactly
like the reference Proposed (Src-20AS-79Dev), so the existing summary.csv /
seed_results.csv formats apply unchanged.

Outputs:
  10seed → Results/COOJA-Simulation/10-Seed-Comparison/DAuth/
             {logs/, seed_results.csv, summary.csv}
  as     → Results/COOJA-Simulation/DAuth-Sweep/as-variation/N{numas}/csv/summary.csv
  net    → Results/COOJA-Simulation/DAuth-Sweep/network-variation/N{n}/csv/summary.csv
"""

import argparse, csv, math, os, re, shutil, statistics, subprocess, time

REPO      = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
CONTIKI   = "/home/apex/contiki-ng"
COOJA_DIR = os.path.join(CONTIKI, "tools", "cooja")
TESTLOG   = os.path.join(COOJA_DIR, "COOJA.testlog")
SRC_DAUTH = os.path.join(REPO, "Revised-Anonymity", "Src-DAuth")
MYPROJECT = os.path.join(CONTIKI, "examples", "myproject")

OUT_10SEED = os.path.join(REPO, "Results", "COOJA-Simulation", "10-Seed-Comparison", "DAuth")
OUT_SWEEP  = os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep")

SEEDS = [123456, 234567, 345678, 456789, 567890,
         678901, 789012, 890123, 901234, 112345]

# Network-variation topology: N_total -> (n_as, n_dev, first_dev)
# Matches the existing Proposed/LAAKA/Zhou bar-chart topology exactly
# (N=30 uses 3 devices, ids 28-30, so the comparison is apples-to-apples).
SIZES = {
    30:  (26,  3, 28),
    50:  (39, 10, 41),
    80:  (63, 16, 65),
    100: (79, 20, 81),
    120: (95, 24, 97),   # 24 newly-joined devices (20% of 120), 95 AS, 1 GW
}

SOURCES = ["gw-node.c", "as-node.c", "device-node.c",
           "aes.c", "aes.h", "sha256.c", "sha256.h"]

MAKEFILE = f"""CONTIKI_PROJECT = device-node as-node gw-node
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


def project_conf(num_as, first_dev):
    return f"""#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define NUM_AS           {num_as}
#define FIRST_DEVICE_ID  {first_dev}
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
#endif
"""


# ── CSC generation ────────────────────────────────────────────────────────────
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
      <commands>$(MAKE) -j$(CPUS) {fw_name} TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/{fw_name}</firmware>
{MOTE_IFACES}
{motes_xml}
    </motetype>"""


def grid_positions(n, cols=10, spacing=30.0, x_off=0.0, y_off=0.0):
    return [(x_off + (i % cols) * spacing, y_off + (i // cols) * spacing)
            for i in range(n)]


def generate_csc(title, seed, n_as, n_dev, first_dev, timeout_ms):
    gw_motes = _mote_entry(150.0, 150.0, 1)
    as_positions = grid_positions(n_as, cols=10, spacing=30.0, x_off=0.0, y_off=60.0)
    as_motes = "\n".join(_mote_entry(px, py, 2 + i)
                         for i, (px, py) in enumerate(as_positions))
    n_rows_as = math.ceil(n_as / 10)
    dev_y_off = 60.0 + n_rows_as * 30.0 + 30.0
    dev_positions = grid_positions(n_dev, cols=10, spacing=30.0, x_off=0.0, y_off=dev_y_off)
    dev_motes = "\n".join(_mote_entry(px, py, first_dev + i)
                          for i, (px, py) in enumerate(dev_positions))

    gw_block  = _motetype_block("GW Node", "gw-node.c", "gw-node.cooja", gw_motes)
    as_block  = _motetype_block("AS Node", "as-node.c", "as-node.cooja", as_motes)
    dev_block = _motetype_block("Device Node", "device-node.c", "device-node.cooja", dev_motes)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<simconf version="2022112801">
  <simulation>
    <title>{title}</title>
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
var completed = {{}};
var nExpected = {n_dev};
var firstId   = {first_dev};
TIMEOUT({timeout_ms}, log.testOK());
while(true) {{
  log.log(time + " " + id + " " + msg + "\\n");
  if (msg.indexOf("KEYEX_ENERGY") !== -1) {{
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


# ── Build ───────────────────────────────────────────────────────────────────
def prepare_build(num_as, first_dev):
    os.makedirs(MYPROJECT, exist_ok=True)
    build_cooja = os.path.join(MYPROJECT, "build", "cooja")
    if os.path.isdir(build_cooja):
        shutil.rmtree(build_cooja)
    for fname in SOURCES:
        shutil.copy2(os.path.join(SRC_DAUTH, fname), os.path.join(MYPROJECT, fname))
    with open(os.path.join(MYPROJECT, "Makefile"), "w") as f:
        f.write(MAKEFILE)
    with open(os.path.join(MYPROJECT, "project-conf.h"), "w") as f:
        f.write(project_conf(num_as, first_dev))


def build_firmware():
    r = subprocess.run(["make", f"CONTIKI={CONTIKI}", "TARGET=cooja",
                        f"-j{os.cpu_count() or 4}"],
                       cwd=MYPROJECT, capture_output=True, text=True, timeout=360)
    if r.returncode != 0:
        print(f"  BUILD FAILED:\n{(r.stdout + r.stderr)[-1500:]}")
        return False
    fw = [f for f in os.listdir(os.path.join(MYPROJECT, "build", "cooja"))
          if f.endswith(".cooja")]
    return len(fw) >= 3


def run_one(title, seed, n_as, n_dev, first_dev, timeout_ms, log_dest):
    if os.path.isfile(log_dest):
        print(f"    [cached] {os.path.basename(log_dest)}")
        return log_dest
    csc = generate_csc(title, seed, n_as, n_dev, first_dev, timeout_ms)
    csc_path = os.path.join(MYPROJECT, f"_dauth_s{seed}.csc")
    with open(csc_path, "w", encoding="utf-8") as f:
        f.write(csc)
    if os.path.isfile(TESTLOG):
        os.remove(TESTLOG)
    t0 = time.time()
    r = subprocess.run(
        ["./gradlew", "--no-watch-fs", "run",
         f"--args=--no-gui --contiki={CONTIKI} --autostart {csc_path}"],
        cwd=COOJA_DIR, capture_output=True, text=True, timeout=2400)
    elapsed = time.time() - t0
    try:
        os.remove(csc_path)
    except OSError:
        pass
    if os.path.isfile(TESTLOG):
        os.makedirs(os.path.dirname(log_dest), exist_ok=True)
        shutil.copy2(TESTLOG, log_dest)
        print(f"    seed {seed}: OK ({elapsed:.0f}s)")
        return log_dest
    fail = log_dest.replace(".txt", "_FAIL.txt")
    os.makedirs(os.path.dirname(fail), exist_ok=True)
    with open(fail, "w") as f:
        f.write((r.stdout + r.stderr)[-60000:])
    print(f"    seed {seed}: FAILED ({elapsed:.0f}s)")
    return None


# ── Parsing ──────────────────────────────────────────────────────────────────
_PAT_ENROLL = re.compile(r'ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')
_PAT_AUTH   = re.compile(r'(?<![A-Z_])AUTH_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')
_PAT_KEYEX  = re.compile(r'KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')


def parse_log(path, device_ids):
    text = open(path, encoding="utf-8", errors="replace").read()
    enroll, auth, keyex = {}, {}, {}
    for m in _PAT_ENROLL.finditer(text):
        nid = int(m.group(1))
        if nid in device_ids: enroll[nid] = (float(m.group(2)), float(m.group(3)))
    for m in _PAT_AUTH.finditer(text):
        nid = int(m.group(1))
        if nid in device_ids: auth[nid] = (float(m.group(2)), float(m.group(3)))
    for m in _PAT_KEYEX.finditer(text):
        nid = int(m.group(1))
        if nid in device_ids: keyex[nid] = (float(m.group(2)), float(m.group(3)))
    return enroll, auth, keyex


def _ci95(xs):
    n = len(xs)
    return 1.96 * statistics.stdev(xs) / math.sqrt(n) if n > 1 else 0.0


def write_summary(per_seed, out_dir, n_seeds):
    """per_seed: seed -> {'enroll':{id:(cpu,e)}, 'auth':..., 'keyex':...}"""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "summary.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Phase", "Seeds", "n_devices",
                    "Avg_CPU_s", "Std_CPU_s", "CI95_CPU_s",
                    "Avg_Energy_mJ", "Std_Energy_mJ", "CI95_Energy_mJ"])
        for key, name in [("enroll", "Enrollment"), ("auth", "Authentication"),
                          ("keyex", "Key Exchange")]:
            ps_cpu, ps_e, ns = [], [], []
            for sd, data in per_seed.items():
                rows = data[key]
                if not rows: continue
                ps_cpu.append(statistics.mean(v[0] for v in rows.values()))
                ps_e.append(statistics.mean(v[1] for v in rows.values()))
                ns.append(len(rows))
            if not ps_cpu: continue
            w.writerow([name, n_seeds, int(round(statistics.mean(ns))),
                        f"{statistics.mean(ps_cpu):.6f}",
                        f"{(statistics.stdev(ps_cpu) if len(ps_cpu)>1 else 0):.6f}",
                        f"{_ci95(ps_cpu):.6f}",
                        f"{statistics.mean(ps_e)*1000:.4f}",
                        f"{(statistics.stdev(ps_e)*1000 if len(ps_e)>1 else 0):.4f}",
                        f"{_ci95(ps_e)*1000:.4f}"])
    return path


def write_seed_results(per_seed, out_dir, device_ids):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "seed_results.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Seed", "Device",
                    "Enroll_Energy_mJ", "Enroll_CPU_s",
                    "Auth_Energy_mJ", "Auth_CPU_s",
                    "Keyex_Energy_mJ", "Keyex_CPU_s",
                    "Total_Energy_mJ", "Total_CPU_s"])
        for sd in sorted(per_seed):
            d = per_seed[sd]
            for dev in sorted(set(d["enroll"]) | set(d["auth"]) | set(d["keyex"])):
                ec, ee = d["enroll"].get(dev, (0, 0))
                ac, ae = d["auth"].get(dev, (0, 0))
                kc, ke = d["keyex"].get(dev, (0, 0))
                w.writerow([sd, dev,
                            f"{ee*1000:.4f}", f"{ec:.6f}",
                            f"{ae*1000:.4f}", f"{ac:.6f}",
                            f"{ke*1000:.4f}", f"{kc:.6f}",
                            f"{(ee+ae+ke)*1000:.4f}", f"{ec+ac+kc:.6f}"])
    return path


# ── Study runners ─────────────────────────────────────────────────────────────
def run_config(label, num_as, n_as, n_dev, first_dev, seeds, log_dir, timeout_ms):
    """Build once for (num_as, first_dev) then run all seeds. Returns per_seed dict."""
    print(f"\n=== {label}  (NUM_AS={num_as}, AS_nodes={n_as}, devices={n_dev}@{first_dev}) ===")
    prepare_build(num_as, first_dev)
    if not build_firmware():
        print("  build failed — skipping")
        return {}
    device_ids = set(range(first_dev, first_dev + n_dev))
    per_seed = {}
    for sd in seeds:
        log_dest = os.path.join(log_dir, f"testlog_s{sd}.txt")
        lp = run_one(f"DAuth {label}", sd, n_as, n_dev, first_dev, timeout_ms, log_dest)
        if not lp: continue
        en, au, kx = parse_log(lp, device_ids)
        per_seed[sd] = {"enroll": en, "auth": au, "keyex": kx}
        print(f"      parsed enroll={len(en)} auth={len(au)} keyex={len(kx)} / {n_dev}")
    return per_seed


def study_10seed(seeds):
    log_dir = os.path.join(OUT_10SEED, "logs")
    per_seed = run_config("10seed N=100", 2, 79, 20, 81, seeds, log_dir, 1500000)
    if not per_seed: return
    write_seed_results(per_seed, OUT_10SEED, set(range(81, 101)))
    write_summary(per_seed, OUT_10SEED, len(per_seed))
    allE = [v[1]*1000 for d in per_seed.values() for v in {**d["enroll"]}.values()]
    print(f"  10seed enroll mean = {statistics.mean(allE):.2f} mJ over {len(per_seed)} seeds")
    print(f"  → {OUT_10SEED}")


def study_as(seeds):
    for num_as in [2, 5, 10]:
        log_dir = os.path.join(OUT_SWEEP, "as-variation", f"N{num_as}", "logs")
        per_seed = run_config(f"as-var NUM_AS={num_as}", num_as, 79, 20, 81,
                              seeds, log_dir, 1500000)
        if not per_seed: continue
        csv_dir = os.path.join(OUT_SWEEP, "as-variation", f"N{num_as}", "csv")
        write_summary(per_seed, csv_dir, len(per_seed))
        write_seed_results(per_seed, csv_dir, set(range(81, 101)))
        print(f"  → {csv_dir}/summary.csv")


def study_net(seeds):
    timeouts = {30: 600000, 50: 900000, 80: 1200000, 100: 1500000, 120: 1800000}
    for n_total in [30, 50, 80, 100, 120]:
        n_as, n_dev, first_dev = SIZES[n_total]
        log_dir = os.path.join(OUT_SWEEP, "network-variation", f"N{n_total}", "logs")
        per_seed = run_config(f"net-var N={n_total}", 2, n_as, n_dev, first_dev,
                              seeds, log_dir, timeouts[n_total])
        if not per_seed: continue
        csv_dir = os.path.join(OUT_SWEEP, "network-variation", f"N{n_total}", "csv")
        write_summary(per_seed, csv_dir, len(per_seed))
        write_seed_results(per_seed, csv_dir, set(range(first_dev, first_dev + n_dev)))
        print(f"  → {csv_dir}/summary.csv")


def main():
    ap = argparse.ArgumentParser(description="DAuth base-scheme sweep")
    ap.add_argument("--study", nargs="+", default=["all"],
                    choices=["10seed", "as", "net", "all"])
    ap.add_argument("--seeds", type=int, default=10, help="number of seeds (max 10)")
    args = ap.parse_args()
    seeds = SEEDS[:args.seeds]
    studies = ["10seed", "as", "net"] if "all" in args.study else args.study
    print(f"DAuth sweep — studies={studies}  seeds={seeds}")
    if "10seed" in studies: study_10seed(seeds)
    if "as"     in studies: study_as(seeds[:5] if args.seeds >= 5 else seeds)
    if "net"    in studies: study_net(seeds)
    print("\nDAuth sweep done.")


if __name__ == "__main__":
    main()
