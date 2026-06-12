#!/usr/bin/env python3
"""
Orchestration script — LAAKA Scheme hardware simulation.
Starts RA (local), Fog (Apex), Device (Pi) in order and streams output.

Usage:
  python run_simulation.py [run_number]
  Results saved to: Hardware/LAAKA/results/run_<N>.json
"""
import json, subprocess, threading, time, sys, os
import paramiko

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

RA_SCRIPT  = os.path.join(os.path.dirname(__file__), "hw_laaka_ra.py")
APEX_IP    = "192.168.1.132"
PI_IP      = "192.168.1.113"
PASSWORD   = "raspberrypi"
REMOTE_DIR = "ANUP_Hardware_Simulation"
ENV        = "export GW_IP=192.168.1.201 AS_IP=192.168.1.132 DEV_IP=192.168.1.113"


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


def ssh_run_background(ip, user, cmd, tag, kill_pattern=None):
    if kill_pattern:
        killer = paramiko.SSHClient()
        killer.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        killer.connect(ip, username=user, password=PASSWORD, timeout=10)
        _, ko, _ = killer.exec_command(f"pkill -f {kill_pattern}; sleep 0.3")
        ko.read()
        killer.close()
        time.sleep(0.5)
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
    print(f"LAAKA Scheme Hardware Simulation — orchestrated run #{run_num}")
    print(f"  RA     : Laptop   (local)")
    print(f"  Fog    : Apex     ({APEX_IP})")
    print(f"  Device : Pi       ({PI_IP})")
    print(f"  Output : {out_json}")
    print("=" * 70)

    here = os.path.dirname(os.path.abspath(__file__))

    # ── Step 0: Copy updated scripts to remotes ───────────────────────────
    print("\n[ORCH] Copying scripts to Apex (Fog) ...")
    scp_file(os.path.join(here, "hw_laaka_fog.py"),        APEX_IP, "apex", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "common.py"),        APEX_IP, "apex", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "config.py"),        APEX_IP, "apex", REMOTE_DIR)

    print("\n[ORCH] Copying scripts to Pi (Device) ...")
    scp_file(os.path.join(here, "hw_laaka_device.py"),     PI_IP, "pi", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "common.py"),        PI_IP, "pi", REMOTE_DIR)
    scp_file(os.path.join(here, "..", "config.py"),        PI_IP, "pi", REMOTE_DIR)

    # ── Step 1: Start RA on Laptop ────────────────────────────────────────
    print("\n[ORCH] Starting RA on Laptop...")
    ra_env = os.environ.copy()
    ra_env["GW_IP"]  = "192.168.1.201"
    ra_env["AS_IP"]  = "192.168.1.132"
    ra_env["DEV_IP"] = "192.168.1.113"
    ra_proc = subprocess.Popen(
        [sys.executable, RA_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=ra_env
    )
    threading.Thread(target=stream, args=("[RA]   ", ra_proc.stdout), daemon=True).start()
    time.sleep(1.5)

    # ── Step 2: Start Fog on Apex ─────────────────────────────────────────
    print("\n[ORCH] Starting Fog on Apex...")
    fog_client = ssh_run_background(APEX_IP, "apex",
                                    "python3 hw_laaka_fog.py", "[FOG] ",
                                    kill_pattern="hw_laaka_fog.py")
    time.sleep(2.0)

    # ── Step 3: Run Device on Pi (wait for completion) ────────────────────
    print("\n[ORCH] Running Device on Pi...")
    rc = ssh_run_foreground(PI_IP, "pi", "python3 hw_laaka_device.py", "[DEV] ")

    print(f"\n[ORCH] Device finished (exit={rc}). Waiting for Fog summary...")
    time.sleep(2)

    # ── Collect results JSON from Pi ──────────────────────────────────────
    print("[ORCH] Collecting results from Pi ...")
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(PI_IP, username="pi", password=PASSWORD, timeout=10)
        sftp = c.open_sftp()
        sftp.get(f"/home/pi/{REMOTE_DIR}/laaka_hw_run.json", out_json)
        sftp.close()
        c.close()
        with open(out_json) as f:
            data = json.load(f)
        s = data.get('summary', {})
        print(f"[ORCH] Saved : {out_json}")
        print(f"[ORCH] Avg Auth+Ack : {s.get('avg_aa_energy_j', 0):.6f} J  {s.get('avg_aa_time_s', 0):.4f} s")
    except Exception as e:
        print(f"[ORCH] WARNING: Could not collect results JSON: {e}")

    # ── Teardown ──────────────────────────────────────────────────────────
    print("\n[ORCH] Stopping Fog...")
    fog_client.exec_command("pkill -f hw_laaka_fog.py")
    fog_client.close()
    time.sleep(0.5)
    print("[ORCH] Stopping RA...")
    ra_proc.terminate()
    ra_proc.wait()
    print("[ORCH] Done.")
