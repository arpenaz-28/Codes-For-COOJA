#!/usr/bin/env python3
"""
run_local_sim.py — Local simulation of the LAAKA hardware protocol.

Runs all three roles on localhost, simulating the 2-RPi + laptop testbed.
Use this when real hardware is unavailable or to verify the protocol logic.

  Role mapping  (localhost):
    gw_hw.py   = Registration Authority (RA)  port 5683
    as_hw.py   = Fog Authentication Server    port 5684
    node_hw.py = Device Node (81)             port 5685

Output:
  results/ra.log         Registration Authority log
  results/fog.log        Fog Authentication Server log
  results/node.log       Device Node log  (contains HW_METRIC JSON line)
  results/hw_metrics.csv Parsed per-phase metrics
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
NATIVE_DIR  = SCRIPT_DIR / "native"
RESULTS_DIR = SCRIPT_DIR / "results"
PYTHON      = sys.executable

# Local config — all roles on 127.0.0.1, 1-second data interval for speed
LOCAL_CONFIG = """\
GW_HOST=127.0.0.1
AS_HOST=127.0.0.1
NODE_HOST=127.0.0.1
GW_USER=
AS_USER=
NODE_USER=
REMOTE_BASE_DIR=/tmp/mtp-hardware
PROJECT_DIR_NAME=LAAKA
GW_PORT=5683
AS_PORT=5684
NODE_PORT=5685
GW_BIND=0.0.0.0
AS_BIND=0.0.0.0
NODE_BIND=0.0.0.0
AS_NODE_ID=2
DEVICE_ID=81
NODE_SEND_COUNT=10
NODE_SEND_INTERVAL_S=1
CPU_POWER_W=2.5
NET_ENERGY_PER_BYTE_J=0.000002
"""


def _print_tail(path: Path, n: int = 40) -> None:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[-n:]:
        print(line)


def main() -> int:
    RESULTS_DIR.mkdir(exist_ok=True)

    # Write localhost config to a temp file
    cfg_fd, cfg_path = tempfile.mkstemp(suffix=".env", prefix="laaka_local_")
    with os.fdopen(cfg_fd, "w") as f:
        f.write(LOCAL_CONFIG)
    print(f"[sim] Local config written to {cfg_path}")

    env = dict(os.environ)
    env["LAAKA_ROLES_FILE"] = cfg_path
    env["PYTHONUNBUFFERED"] = "1"   # force line-flushed output even when piped

    procs: dict = {}
    log_fhs: dict = {}

    try:
        # ------------------------------------------------------------------ #
        # 1. Start Fog server — must be up before DEV_INFO arrives from RA   #
        # ------------------------------------------------------------------ #
        print("[sim] Starting Fog server (as_hw.py) ...")
        fog_log = open(RESULTS_DIR / "fog.log", "w", encoding="utf-8")
        procs["fog"] = subprocess.Popen(
            [PYTHON, "-u", str(NATIVE_DIR / "as_hw.py")],
            stdout=fog_log, stderr=subprocess.STDOUT, env=env,
        )
        log_fhs["fog"] = fog_log
        time.sleep(0.4)   # give it time to bind

        # ------------------------------------------------------------------ #
        # 2. Start Registration Authority (RA)                               #
        # ------------------------------------------------------------------ #
        print("[sim] Starting RA (gw_hw.py) ...")
        ra_log = open(RESULTS_DIR / "ra.log", "w", encoding="utf-8")
        procs["ra"] = subprocess.Popen(
            [PYTHON, "-u", str(NATIVE_DIR / "gw_hw.py")],
            stdout=ra_log, stderr=subprocess.STDOUT, env=env,
        )
        log_fhs["ra"] = ra_log
        time.sleep(0.4)

        # ------------------------------------------------------------------ #
        # 3. Start Device Node — drives the full protocol                    #
        # ------------------------------------------------------------------ #
        print("[sim] Starting Device Node (node_hw.py) ...")
        node_log = open(RESULTS_DIR / "node.log", "w", encoding="utf-8")
        procs["node"] = subprocess.Popen(
            [PYTHON, "-u", str(NATIVE_DIR / "node_hw.py")],
            stdout=node_log, stderr=subprocess.STDOUT, env=env,
        )
        log_fhs["node"] = node_log

        print("[sim] Protocol running - waiting for node to finish "
              "(10 packets x 1 s + overhead ~20 s) ...")

        try:
            rc = procs["node"].wait(timeout=60)
        except subprocess.TimeoutExpired:
            print("[sim] WARNING: Node timed out after 60 s — terminating")
            procs["node"].terminate()
            rc = -1

        if rc == 0:
            print("[sim] Node completed OK.")
        else:
            print(f"[sim] Node exited with code {rc}")

        time.sleep(0.5)   # let Fog flush its final DATA lines

    finally:
        for name in ("ra", "fog"):
            p = procs.get(name)
            if p and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
        for fh in log_fhs.values():
            fh.close()
        try:
            os.unlink(cfg_path)
        except OSError:
            pass

    # ---------------------------------------------------------------------- #
    # Parse HW_METRIC from all three logs; combine into hw_metrics.csv       #
    # ---------------------------------------------------------------------- #
    parse_script = SCRIPT_DIR / "scripts" / "06-parse-hw-metrics.py"
    role_logs    = [("ra", "ra.log"), ("fog", "fog.log"), ("node", "node.log")]
    per_role_csvs = []

    for role, log_name in role_logs:
        log_path  = RESULTS_DIR / log_name
        csv_out   = RESULTS_DIR / f"hw_metrics_{role}.csv"
        print(f"\n[sim] Parsing HW_METRIC from {log_name} ...")
        res = subprocess.run(
            [PYTHON, str(parse_script), str(log_path), str(csv_out)],
            capture_output=True, text=True,
        )
        if res.stdout.strip():
            print(res.stdout.strip())
        if res.returncode != 0:
            print(f"[sim] Parser warning for {log_name}:", res.stderr.strip())
        elif csv_out.exists():
            per_role_csvs.append(csv_out)

    # Combine per-role CSVs into one combined CSV
    combined_csv = RESULTS_DIR / "hw_metrics.csv"
    if per_role_csvs:
        header = per_role_csvs[0].read_text(encoding="utf-8").splitlines()[0]
        rows_combined = [header]
        for f in per_role_csvs:
            data_rows = f.read_text(encoding="utf-8").splitlines()[1:]
            rows_combined.extend(data_rows)
        combined_csv.write_text("\n".join(rows_combined) + "\n", encoding="utf-8")
        print(f"\n[sim] Combined CSV written: {combined_csv}")

    # ---------------------------------------------------------------------- #
    # Print log excerpts                                                      #
    # ---------------------------------------------------------------------- #
    print("\n" + "=" * 60)
    print("RA LOG (ra.log)")
    print("=" * 60)
    _print_tail(RESULTS_DIR / "ra.log", 30)

    print("\n" + "=" * 60)
    print("FOG LOG (fog.log)")
    print("=" * 60)
    _print_tail(RESULTS_DIR / "fog.log", 30)

    print("\n" + "=" * 60)
    print("NODE LOG (node.log)")
    print("=" * 60)
    _print_tail(RESULTS_DIR / "node.log", 50)

    if combined_csv.exists():
        print("\n" + "=" * 60)
        print("METRICS CSV (hw_metrics.csv) — all 3 roles")
        print("=" * 60)
        print(combined_csv.read_text(encoding="utf-8"))

    print(f"\n[sim] All logs saved to {RESULTS_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
