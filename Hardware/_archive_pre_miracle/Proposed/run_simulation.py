#!/usr/bin/env python3
"""
Orchestration script — Proposed Scheme hardware simulation.
Starts GW (local), AS (Apex), Device (Pi) in order and streams output.

Usage:
  python run_simulation.py [run_number]
  Results saved to: Hardware/Proposed/results/run_<N>.json
"""
import json, subprocess, threading, time, sys, os
import paramiko

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

GW_SCRIPT  = os.path.join(os.path.dirname(__file__), "gw.py")
APEX_IP    = "192.168.1.132"
PI_IP      = "192.168.1.113"
PASSWORD   = "raspberrypi"
REMOTE_DIR = "ANUP_Hardware_Simulation"
# USE_MIRACL=1 (default) routes device/AS crypto through libmiraclshim.so; set 0 for Python baseline.
USE_MIRACL = os.environ.get("USE_MIRACL", "1")
_mir = (f" USE_MIRACL={USE_MIRACL} MIRACL_SO=$HOME/{REMOTE_DIR}/libmiraclshim.so"
        if USE_MIRACL == "1" else "")
ENV        = "export GW_IP=192.168.1.201 AS_IP=192.168.1.132 DEV_IP=192.168.1.113" + _mir


def stream(tag, channel):
    for line in channel:
        print(f"{tag} {line}", end="", flush=True)


def scp_file(local_path, ip, user, remote_dir, filename=None):
    fname = filename or os.path.basename(local_path)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    client.exec_command(f"mkdir -p ~/{remote_dir}")
    time.sleep(0.3)
    sftp = client.open_sftp()
    sftp.put(local_path, f"/home/{user}/{remote_dir}/{fname}")
    sftp.close()
    client.close()
    print(f"[SCP] {fname} -> {user}@{ip}:~/{remote_dir}/")


def ssh_run_background(ip, user, cmd, tag):
    # Kill any stale instance on a separate connection first
    killer = paramiko.SSHClient()
    killer.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    killer.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, ko, _ = killer.exec_command("pkill -f hw_measure_as.py; sleep 0.3")
    ko.read()   # wait for pkill to finish
    killer.close()
    time.sleep(0.5)
    # Start the AS on a fresh connection
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, stdout, stderr = client.exec_command(
        f"cd ~/{REMOTE_DIR} && {ENV} && {cmd}", get_pty=False)
    threading.Thread(target=stream, args=(tag, stdout), daemon=True).start()
    threading.Thread(target=stream, args=(tag, stderr), daemon=True).start()
    return client


def ssh_run_foreground(ip, user, cmd, tag):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && {ENV} && {cmd}", get_pty=False)
    for line in stdout:
        print(f"{tag} {line}", end="", flush=True)
    for line in stderr:
        print(f"{tag}[ERR] {line}", end="", flush=True)
    rc = stdout.channel.recv_exit_status()
    client.close()
    return rc


if __name__ == "__main__":
    run_num  = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out_json = os.path.join(RESULTS_DIR, f"run_{run_num:02d}.json")

    print("=" * 70)
    print(f"Proposed Scheme Hardware Simulation — orchestrated run #{run_num}")
    print(f"  GW     : Laptop   (local)")
    print(f"  AS     : Apex     ({APEX_IP})")
    print(f"  Device : Pi       ({PI_IP})")
    print(f"  Output : {out_json}")
    print("=" * 70)

    here = os.path.dirname(os.path.abspath(__file__))

    # ── Step 0: Copy updated scripts to remotes ───────────────────────────
    print("\n[ORCH] Copying scripts to Apex (AS) ...")
    scp_file(os.path.join(here, "hw_measure_as.py"),       APEX_IP, "apex", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "common.py"),        APEX_IP, "apex", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "config.py"),        APEX_IP, "apex", REMOTE_DIR)

    print("\n[ORCH] Copying scripts to Pi (Device) ...")
    scp_file(os.path.join(here, "hw_measure_device.py"),   PI_IP, "pi", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "common.py"),        PI_IP, "pi", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "config.py"),        PI_IP, "pi", REMOTE_DIR)

    # ── MIRACL crypto backend (device + AS only; GW stays Python) ─────────
    if USE_MIRACL == "1":
        print("\n[ORCH] Deploying MIRACL backend to AS + Device ...")
        for ip, user in [(APEX_IP, "apex"), (PI_IP, "pi")]:
            scp_file(os.path.join(here, "..", "MIRACLE", "miracl_crypto.py"),   ip, user, REMOTE_DIR)
            scp_file(os.path.join(here, "..", "MIRACLE", "libmiraclshim.so"),   ip, user, REMOTE_DIR)

    # ── Step 1: Start GW on Laptop ────────────────────────────────────────
    print("\n[ORCH] Starting GW on Laptop...")
    gw_env = os.environ.copy()
    gw_env["GW_IP"]  = "192.168.1.201"
    gw_env["AS_IP"]  = "192.168.1.132"
    gw_env["DEV_IP"] = "192.168.1.113"
    gw_proc = subprocess.Popen(
        [sys.executable, GW_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=gw_env
    )
    threading.Thread(target=stream, args=("[GW]  ", gw_proc.stdout), daemon=True).start()
    time.sleep(1.5)

    # ── Step 2: Start AS on Apex ──────────────────────────────────────────
    print("\n[ORCH] Starting AS on Apex...")
    as_client = ssh_run_background(APEX_IP, "apex", "python3 hw_measure_as.py", "[AS]  ")
    time.sleep(2.0)

    # ── Step 3: Run Device on Pi (wait for completion) ────────────────────
    print("\n[ORCH] Running Device on Pi...")
    rc = ssh_run_foreground(PI_IP, "pi", "python3 hw_measure_device.py", "[DEV] ")

    print(f"\n[ORCH] Device finished (exit={rc}). Waiting for AS summary...")
    time.sleep(2)

    # ── Collect results JSON from Pi ──────────────────────────────────────
    print("[ORCH] Collecting results from Pi ...")
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(PI_IP, username="pi", password=PASSWORD, timeout=10)
        sftp = c.open_sftp()
        sftp.get(f"/home/pi/{REMOTE_DIR}/proposed_hw_run.json", out_json)
        sftp.close()
        c.close()
        with open(out_json) as f:
            data = json.load(f)
        s = data.get('summary', {})
        print(f"[ORCH] Saved : {out_json}")
        print(f"[ORCH] Avg Auth+KeyEx : {s.get('avg_ak_energy_j', 0):.6f} J  {s.get('avg_ak_time_s', 0):.4f} s")
    except Exception as e:
        print(f"[ORCH] WARNING: Could not collect results JSON: {e}")

    # ── Teardown ──────────────────────────────────────────────────────────
    print("[ORCH] Stopping AS...")
    as_client.exec_command("pkill -f hw_measure_as.py")
    as_client.close()
    time.sleep(0.5)
    print("[ORCH] Stopping GW...")
    gw_proc.terminate()
    gw_proc.wait()
    print("[ORCH] Done.")
