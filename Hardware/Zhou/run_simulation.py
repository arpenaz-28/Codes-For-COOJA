#!/usr/bin/env python3
"""
Orchestration script — Zhou Scheme hardware simulation.
Starts GW (local), SN (Pi), User (Apex) in order and streams all output.

Role mapping (Zhou scheme reverses RPi roles vs Proposed/LAAKA):
  GW   → Laptop (local subprocess)     hw_zhou_gw.py
  SN   → Pi     (192.168.1.113, pi)    hw_zhou_sn.py
  User → Apex   (192.168.1.132, apex)  hw_zhou_user.py  ← measurement target
"""
import subprocess, threading, time, sys, os
import paramiko

GW_SCRIPT  = os.path.join(os.path.dirname(__file__), "hw_zhou_gw.py")
APEX_IP    = "192.168.1.132"    # User (measurement target)
PI_IP      = "192.168.1.113"    # SN
PASSWORD   = "raspberrypi"
REMOTE_DIR = "ANUP_Hardware_Simulation"
# GW_IP = laptop, AS_IP = SN (Pi), DEV_IP = User (Apex)
ENV        = "export GW_IP=192.168.1.201 AS_IP=192.168.1.113 DEV_IP=192.168.1.132"


def stream(tag, channel):
    for line in channel:
        print(f"{tag} {line}", end="", flush=True)


def ssh_run_background(ip, user, script_name, tag, kill_pattern=None):
    """SSH to host, optionally kill an old instance, start script, stream output."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    if kill_pattern:
        client.exec_command(f"pkill -f {kill_pattern}; sleep 0.5")
        time.sleep(0.8)
    _, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && {ENV} && python3 {script_name}", get_pty=False)
    threading.Thread(target=stream, args=(tag, stdout), daemon=True).start()
    threading.Thread(target=stream, args=(tag, stderr), daemon=True).start()
    return client


def ssh_run_foreground(ip, user, script_name, tag):
    """SSH to host, run script, wait for it to finish, return exit code."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && {ENV} && python3 {script_name}", get_pty=False)
    for line in stdout:
        print(f"{tag} {line}", end="", flush=True)
    for line in stderr:
        print(f"{tag}[ERR] {line}", end="", flush=True)
    rc = stdout.channel.recv_exit_status()
    client.close()
    return rc


if __name__ == "__main__":
    print("=" * 70)
    print("Zhou Scheme Hardware Simulation — orchestrated run")
    print("=" * 70)

    # ── Step 1: Start GW on Laptop ────────────────────────────────────────
    print("\n[ORCH] Starting GW on Laptop (local)...")
    gw_env = os.environ.copy()
    gw_env["GW_IP"]  = "192.168.1.201"
    gw_env["AS_IP"]  = "192.168.1.113"   # SN = Pi
    gw_env["DEV_IP"] = "192.168.1.132"   # User = Apex
    gw_proc = subprocess.Popen(
        [sys.executable, GW_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=gw_env
    )
    threading.Thread(target=stream, args=("[GW]  ", gw_proc.stdout), daemon=True).start()
    time.sleep(1.5)   # wait for all 4 GW listeners to bind

    # ── Step 2: Start SN on Pi (background) ──────────────────────────────
    print("\n[ORCH] Starting SN on Pi...")
    sn_client = ssh_run_background(PI_IP, "pi", "hw_zhou_sn.py",
                                   "[SN]  ", kill_pattern="hw_zhou_sn.py")
    time.sleep(2.5)   # allow SN to register with GW and open M2 listener

    # ── Step 3: Run User on Apex (foreground — measurement target) ────────
    print("\n[ORCH] Running User on Apex (measurement target)...")
    rc = ssh_run_foreground(APEX_IP, "apex", "hw_zhou_user.py", "[USR] ")

    print(f"\n[ORCH] User script finished (exit={rc}). Waiting 2 s for server summaries...")
    time.sleep(2)

    # ── Teardown ──────────────────────────────────────────────────────────
    print("\n[ORCH] Stopping SN on Pi...")
    sn_client.exec_command("pkill -f hw_zhou_sn.py")
    sn_client.close()
    time.sleep(0.5)

    print("[ORCH] Stopping GW...")
    gw_proc.terminate()
    gw_proc.wait()

    print("\n[ORCH] Zhou hardware simulation complete.")
