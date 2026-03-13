"""
Scalability study: run simulations with 1, 5, 20 device nodes for all 3 schemes.
Generates CSC files dynamically, runs simulations, extracts metrics,
and produces comparison charts with theoretical analysis.
"""
import subprocess, os, re, csv, sys, time, statistics

BASE = r"c:\ANUP\MTP\Proposing\Codes For COOJA"
CONTAINER = "cooja-sim"
PROJECT_DIR = "/opt/contiki-ng/examples/myproject"
COOJA_DIR = "/opt/contiki-ng/tools/cooja"
SEEDS = [123456, 234567, 345678]
NODE_COUNTS = [1, 5, 20]

SCHEMES = {
    "Base-Scheme": {
        "path": os.path.join(BASE, "Base-Scheme"),
        "makefile_src": "Makefile.unified",
        "sources": ["aes.c", "aes.h", "sha256.c", "sha256.h",
                     "as-node.c", "device-node.c", "gw-node.c",
                     "project-conf.h"],
    },
    "LAAKA": {
        "path": os.path.join(BASE, "LAAKA"),
        "makefile_src": "Makefile",
        "sources": ["aes.c", "aes.h", "sha256.c", "sha256.h",
                     "as-node.c", "device-node.c", "gw-node.c",
                     "project-conf.h"],
    },
    "Proposed-Scheme": {
        "path": os.path.join(BASE, "Anonymity-Extended-Base-Scheme"),
        "makefile_src": "Makefile",
        "sources": ["aes.c", "aes.h", "sha256.c", "sha256.h",
                     "as-node.c", "device-node.c", "gw-node.c",
                     "project-conf.h"],
    },
}

MOTE_INTERFACES = """      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
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


def generate_csc(num_devices, seed, timeout_ms=None):
    """Generate a CSC file with 1 GW + 1 AS + num_devices Device nodes."""
    if timeout_ms is None:
        timeout_ms = {1: 600000, 5: 900000, 20: 1800000}.get(num_devices, 1800000)

    total = 2 + num_devices  # GW(1) + AS(2) + devices(3..N+2)

    # Grid layout
    motes_gw = '      <mote>\n        <interface_config>\n          org.contikios.cooja.interfaces.Position\n          <pos x="0" y="0" />\n        </interface_config>\n        <interface_config>\n          org.contikios.cooja.contikimote.interfaces.ContikiMoteID\n          <id>1</id>\n        </interface_config>\n      </mote>'

    motes_as = '      <mote>\n        <interface_config>\n          org.contikios.cooja.interfaces.Position\n          <pos x="30" y="0" />\n        </interface_config>\n        <interface_config>\n          org.contikios.cooja.contikimote.interfaces.ContikiMoteID\n          <id>2</id>\n        </interface_config>\n      </mote>'

    device_motes = []
    for i in range(num_devices):
        dev_id = 3 + i
        x = (i % 10) * 30
        y = 30 + (i // 10) * 30
        mote = f"""      <mote>
        <interface_config>
          org.contikios.cooja.interfaces.Position
          <pos x="{x}" y="{y}" />
        </interface_config>
        <interface_config>
          org.contikios.cooja.contikimote.interfaces.ContikiMoteID
          <id>{dev_id}</id>
        </interface_config>
      </mote>"""
        device_motes.append(mote)

    csc = f"""<?xml version="1.0" encoding="UTF-8"?>
<simconf version="2022112801">
  <simulation>
    <title>Scalability {num_devices}dev (1GW+1AS+{num_devices}Dev)</title>
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
    </events>    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>GW Node</description>
      <source>[CONTIKI_DIR]/examples/myproject/gw-node.c</source>
      <commands>$(MAKE) TARGET=cooja clean
$(MAKE) -j$(CPUS) gw-node.cooja TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/gw-node.cooja</firmware>
{MOTE_INTERFACES}{motes_gw}    </motetype>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>AS Node</description>
      <source>[CONTIKI_DIR]/examples/myproject/as-node.c</source>
      <commands>$(MAKE) TARGET=cooja clean
$(MAKE) -j$(CPUS) as-node.cooja TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/as-node.cooja</firmware>
{MOTE_INTERFACES}{motes_as}    </motetype>
    <motetype>
      org.contikios.cooja.contikimote.ContikiMoteType
      <description>Device Node</description>
      <source>[CONTIKI_DIR]/examples/myproject/device-node.c</source>
      <commands>$(MAKE) TARGET=cooja clean
$(MAKE) -j$(CPUS) device-node.cooja TARGET=cooja</commands>
      <firmware>[CONTIKI_DIR]/examples/myproject/build/cooja/device-node.cooja</firmware>
{MOTE_INTERFACES}{"".join(device_motes)}    </motetype>
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
</simconf>"""
    return csc


def docker_exec(cmd, timeout=900):
    full = f'docker exec {CONTAINER} bash -c "{cmd}"'
    r = subprocess.run(full, capture_output=True, text=True, shell=True, timeout=timeout)
    return r.stdout + r.stderr, r.returncode


def docker_cp(src, dst):
    cmd = f'docker cp "{src}" {CONTAINER}:{dst}'
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
    return r.returncode == 0


def clean_project():
    docker_exec(f"cd {PROJECT_DIR} && rm -f *.c *.h Makefile *.csc && rm -rf build")


def deploy_scheme(scheme_name, scheme_info):
    print(f"  Deploying {scheme_name}...")
    clean_project()
    path = scheme_info["path"]
    for src in scheme_info["sources"]:
        src_path = os.path.join(path, src)
        if not os.path.exists(src_path):
            print(f"    WARNING: {src} not found at {src_path}")
            continue
        if not docker_cp(src_path, f"{PROJECT_DIR}/{src}"):
            print(f"    FAILED to copy {src}")
            return False
    makefile_src = os.path.join(path, scheme_info["makefile_src"])
    if not docker_cp(makefile_src, f"{PROJECT_DIR}/Makefile"):
        print(f"    FAILED to copy Makefile")
        return False
    print(f"  Building {scheme_name}...")
    out, rc = docker_exec(f"cd {PROJECT_DIR} && rm -rf build && make TARGET=cooja", timeout=120)
    if rc != 0:
        print(f"  BUILD FAILED:\n{out[-500:]}")
        return False
    out2, _ = docker_exec(f"ls {PROJECT_DIR}/build/cooja/*.cooja")
    cooja_files = [l.strip() for l in out2.strip().split('\n') if l.strip().endswith('.cooja')]
    print(f"  Built {len(cooja_files)} firmware files")
    return len(cooja_files) >= 3


def run_simulation(csc_container_path, sim_timeout=900):
    cmd = (f"cd {COOJA_DIR} && ./gradlew --no-watch-fs run "
           f"--args='--no-gui --contiki=/opt/contiki-ng "
           f"--autostart {csc_container_path}'")
    t0 = time.time()
    out, rc = docker_exec(cmd, timeout=sim_timeout)
    elapsed = time.time() - t0
    success = "TEST OK" in out
    if not success:
        lines = out.strip().split('\n')
        print(f"    SIM FAILED (rc={rc}, {elapsed:.0f}s):")
        for l in lines[-5:]:
            print(f"      {l}")
    return success, elapsed


def save_testlog(dest_path):
    out, rc = docker_exec(f"cat {COOJA_DIR}/COOJA.testlog")
    if rc == 0 and out.strip():
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(out)
        return True
    return False


def extract_metrics(logfile):
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


def compute_stats(values):
    """Return mean, stddev for a list of values."""
    if not values:
        return 0, 0
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0
    return mean, sd


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    results_dir = os.path.join(BASE, "Results", "CSV-Data")
    logs_dir = os.path.join(BASE, "Results", "Testlogs", "Scalability")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    # results[scheme][num_devices] = {phase: [list of per-device values across seeds]}
    all_results = {}

    for scheme_name, scheme_info in SCHEMES.items():
        print(f"\n{'='*60}")
        print(f"SCHEME: {scheme_name}")
        print(f"{'='*60}")

        all_results[scheme_name] = {}

        # Deploy and build once per scheme
        if not deploy_scheme(scheme_name, scheme_info):
            print(f"SKIPPING {scheme_name} — build failed")
            continue

        for num_dev in NODE_COUNTS:
            print(f"\n  --- {num_dev} device(s) ---")
            all_results[scheme_name][num_dev] = {
                "enroll_cpu": [], "enroll_energy": [],
                "auth_cpu": [], "auth_energy": [],
                "keyex_cpu": [], "keyex_energy": [],
            }

            for seed in SEEDS:
                print(f"    Seed {seed}:")

                # Generate CSC
                csc_content = generate_csc(num_dev, seed)
                tmp_csc = os.path.join(scheme_info["path"], f"_tmp_scale_{num_dev}_{seed}.csc")
                with open(tmp_csc, "w") as f:
                    f.write(csc_content)

                # Copy to container
                ok = docker_cp(tmp_csc, f"{PROJECT_DIR}/test-sim.csc")
                os.remove(tmp_csc)
                if not ok:
                    print(f"      Failed to copy CSC")
                    continue

                # Simulation timeout: smaller networks finish faster
                sim_timeout = {1: 600, 5: 600, 20: 900}.get(num_dev, 900)

                # Run
                success, elapsed = run_simulation(f"{PROJECT_DIR}/test-sim.csc", sim_timeout)
                print(f"      {'OK' if success else 'FAILED'} in {elapsed:.0f}s")

                if not success:
                    continue

                # Save testlog
                log_subdir = os.path.join(logs_dir, scheme_name)
                os.makedirs(log_subdir, exist_ok=True)
                log_path = os.path.join(log_subdir, f"scalability_{num_dev}dev_seed{seed}.txt")
                if not save_testlog(log_path):
                    print(f"      Failed to save testlog")
                    continue

                # Extract metrics
                enroll, auth, keyex = extract_metrics(log_path)
                print(f"      Extracted: E={len(enroll)} A={len(auth)} K={len(keyex)}")

                # Collect per-device values
                for d in enroll:
                    all_results[scheme_name][num_dev]["enroll_cpu"].append(d["cpu"])
                    all_results[scheme_name][num_dev]["enroll_energy"].append(d["energy"])
                for d in auth:
                    all_results[scheme_name][num_dev]["auth_cpu"].append(d["cpu"])
                    all_results[scheme_name][num_dev]["auth_energy"].append(d["energy"])
                for d in keyex:
                    all_results[scheme_name][num_dev]["keyex_cpu"].append(d["cpu"])
                    all_results[scheme_name][num_dev]["keyex_energy"].append(d["energy"])

    # ==========================================================================
    # WRITE SCALABILITY CSV
    # ==========================================================================
    scale_csv = os.path.join(results_dir, "scalability-results.csv")
    with open(scale_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scheme", "Num_Devices", "Phase",
                     "Num_Samples", "Avg_CPU_s", "StdDev_CPU_s",
                     "Avg_Energy_J", "StdDev_Energy_J",
                     "Avg_CPU_Only_Energy_J"])

        for scheme_name in SCHEMES:
            if scheme_name not in all_results:
                continue
            for num_dev in NODE_COUNTS:
                if num_dev not in all_results[scheme_name]:
                    continue
                r = all_results[scheme_name][num_dev]
                for phase_key, phase_label in [("enroll", "Enrollment"),
                                                ("auth", "Authentication"),
                                                ("keyex", "Key Exchange")]:
                    cpu_vals = r[f"{phase_key}_cpu"]
                    en_vals = r[f"{phase_key}_energy"]
                    n = len(cpu_vals)
                    if n == 0:
                        continue
                    avg_cpu, sd_cpu = compute_stats(cpu_vals)
                    avg_en, sd_en = compute_stats(en_vals)
                    cpu_energy = avg_cpu * 0.0054
                    w.writerow([scheme_name, num_dev, phase_label,
                               n, f"{avg_cpu:.6f}", f"{sd_cpu:.6f}",
                               f"{avg_en:.6f}", f"{sd_en:.6f}",
                               f"{cpu_energy:.8f}"])

    print(f"\nScalability CSV: {scale_csv}")

    # ==========================================================================
    # PRINT SUMMARY
    # ==========================================================================
    print(f"\n{'='*80}")
    print("SCALABILITY SUMMARY")
    print(f"{'='*80}")
    for scheme_name in SCHEMES:
        if scheme_name not in all_results:
            continue
        print(f"\n{scheme_name}:")
        for num_dev in NODE_COUNTS:
            if num_dev not in all_results[scheme_name]:
                continue
            r = all_results[scheme_name][num_dev]
            e_n = len(r["enroll_cpu"])
            a_n = len(r["auth_cpu"])
            k_n = len(r["keyex_cpu"])
            e_avg = statistics.mean(r["enroll_energy"]) if e_n else 0
            a_avg = statistics.mean(r["auth_energy"]) if a_n else 0
            k_avg = statistics.mean(r["keyex_energy"]) if k_n else 0
            total = e_avg + a_avg + k_avg
            print(f"  {num_dev:2d} devices: E={e_n:3d}  A={a_n:3d}  K={k_n:3d}  "
                  f"Enroll={e_avg:.4f}J  Auth={a_avg:.4f}J  KeyEx={k_avg:.4f}J  "
                  f"Total={total:.4f}J")

    print("\nDone!")
