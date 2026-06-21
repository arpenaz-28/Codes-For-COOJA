#!/usr/bin/env python3
"""
Orchestration script — DAuth Scheme hardware simulation.
Topology (mirrors Proposed with roles swapped):
  GW     : Laptop   (192.168.1.201)  — runs locally
  AS     : Pi       (192.168.1.113)  — as_server.py
  Device : Apex     (192.168.1.132)  — device.py

Usage:
  python run_dauth_simulation.py [run_number]
  Results saved to: Hardware/DAuth/results/run_<N>.json
"""
import subprocess, threading, time, sys, os, json
import paramiko

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

GW_SCRIPT  = os.path.join(os.path.dirname(__file__), "gateway.py")
PI_IP      = "192.168.1.113"
APEX_IP    = "192.168.1.132"
PASSWORD   = "raspberrypi"
REMOTE_DIR = "DAuth_HW"
# USE_MIRACL=1 (default) routes the measured device's crypto through libmiraclshim.so.
USE_MIRACL = os.environ.get("USE_MIRACL", "1")
MIRACLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MIRACLE")


def stream(tag, channel):
    for line in channel:
        print(f"{tag} {line}", end="", flush=True)


def ssh_run_background(ip, user, cmd, tag):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    client.exec_command("pkill -f as_server.py 2>/dev/null; sleep 0.5")
    time.sleep(0.8)
    _, stdout, stderr = client.exec_command(
        f"cd ~/{REMOTE_DIR} && {cmd}", get_pty=False)
    threading.Thread(target=stream, args=(tag, stdout), daemon=True).start()
    threading.Thread(target=stream, args=(tag, stderr), daemon=True).start()
    return client


def ssh_run_foreground(ip, user, cmd, tag):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, stdout, stderr = client.exec_command(
        f"cd ~/{REMOTE_DIR} && {cmd}", get_pty=False)
    for line in stdout:
        print(f"{tag} {line}", end="", flush=True)
    for line in stderr:
        print(f"{tag}[ERR] {line}", end="", flush=True)
    rc = stdout.channel.recv_exit_status()
    client.close()
    return rc


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


if __name__ == "__main__":
    run_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out_json = os.path.join(RESULTS_DIR, f"run_{run_num:02d}.json")

    print("=" * 70)
    print(f"DAuth Scheme Hardware Simulation — orchestrated run #{run_num}")
    print(f"  GW     : Laptop   (local)")
    print(f"  AS     : Pi       ({PI_IP})")
    print(f"  Device : Apex     ({APEX_IP})")
    print(f"  Output : {out_json}")
    print("=" * 70)

    here = os.path.dirname(os.path.abspath(__file__))

    # ── Step 0: Copy files to remotes ────────────────────────────────────────
    print("\n[ORCH] Copying files to Pi (AS) ...")
    scp_file(os.path.join(here, "as_server.py"),   PI_IP,   "pi",   REMOTE_DIR)
    scp_file(os.path.join(here, "crypto_utils.py"),PI_IP,   "pi",   REMOTE_DIR)

    print("\n[ORCH] Copying files to Apex (Device) ...")
    scp_file(os.path.join(here, "device.py"),      APEX_IP, "apex", REMOTE_DIR)
    scp_file(os.path.join(here, "crypto_utils.py"),APEX_IP, "apex", REMOTE_DIR)
    if USE_MIRACL == "1":
        print("\n[ORCH] Deploying MIRACL backend to Device (Apex) ...")
        scp_file(os.path.join(MIRACLE_DIR, "miracl_crypto.py"), APEX_IP, "apex", REMOTE_DIR)
        scp_file(os.path.join(MIRACLE_DIR, "libmiraclshim.so"), APEX_IP, "apex", REMOTE_DIR)

    # ── Step 1: Start GW locally ─────────────────────────────────────────────
    print("\n[ORCH] Starting GW on Laptop ...")
    gw_proc = subprocess.Popen(
        [sys.executable, GW_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    threading.Thread(target=stream, args=("[GW]  ", gw_proc.stdout), daemon=True).start()
    time.sleep(1.5)

    # ── Step 2: Start AS on Pi ────────────────────────────────────────────────
    print("\n[ORCH] Starting AS on Pi ...")
    as_client = ssh_run_background(PI_IP, "pi", "python3 as_server.py", "[AS]  ")
    time.sleep(2.0)

    # ── Step 3: Run Device on Apex (wait for completion) ─────────────────────
    print("\n[ORCH] Running Device on Apex ...")
    dev_cmd = "python3 device.py"
    if USE_MIRACL == "1":
        dev_cmd = f"USE_MIRACL=1 MIRACL_SO=$HOME/{REMOTE_DIR}/libmiraclshim.so " + dev_cmd
    rc = ssh_run_foreground(APEX_IP, "apex", dev_cmd, "[DEV] ")

    print(f"\n[ORCH] Device finished (exit={rc}). Waiting for AS to flush ...")
    time.sleep(2)

    # ── Collect results JSON from Apex ────────────────────────────────────────
    print("[ORCH] Collecting results from Apex ...")
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(APEX_IP, username="apex", password=PASSWORD, timeout=10)
        sftp = c.open_sftp()
        sftp.get(f"/home/apex/{REMOTE_DIR}/dauth_hw_run.json", out_json)
        sftp.close()
        c.close()
        with open(out_json) as f:
            data = json.load(f)
        s = data.get('summary', {})
        print(f"[ORCH] Saved: {out_json}")
        print(f"[ORCH] Avg Auth+KeyEx : {s.get('avg_ak_energy_j', 0):.6f} J  {s.get('avg_ak_time_s', 0):.4f} s")
    except Exception as e:
        print(f"[ORCH] WARNING: Could not collect results JSON: {e}")

    # ── Teardown ──────────────────────────────────────────────────────────────
    print("[ORCH] Stopping AS ...")
    as_client.exec_command("pkill -f as_server.py")
    as_client.close()
    time.sleep(0.5)
    print("[ORCH] Stopping GW ...")
    gw_proc.terminate()
    gw_proc.wait()
    print("[ORCH] Done.")
