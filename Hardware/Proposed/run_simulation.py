#!/usr/bin/env python3
"""
Orchestration script — Proposed Scheme hardware simulation.
Starts GW (local), AS (Apex), Device (Pi) in order and streams output.
"""
import subprocess, threading, time, sys, os
import paramiko

GW_SCRIPT  = os.path.join(os.path.dirname(__file__), "gw.py")
APEX_IP    = "192.168.1.132"
PI_IP      = "192.168.1.113"
PASSWORD   = "raspberrypi"
REMOTE_DIR = "ANUP_Hardware_Simulation"
ENV        = "export GW_IP=192.168.1.201 AS_IP=192.168.1.132 DEV_IP=192.168.1.113"


def stream(tag, channel):
    for line in channel:
        print(f"{tag} {line}", end="", flush=True)


def ssh_run_background(ip, user, cmd, tag):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    client.exec_command("pkill -f hw_measure_as.py; sleep 0.5")
    time.sleep(0.8)
    _, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && {ENV} && {cmd}", get_pty=False)
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
    print("=" * 70)
    print("Proposed Scheme Hardware Simulation — orchestrated run")
    print("=" * 70)

    # Step 1: Start GW on Laptop
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

    # Step 2: Start AS on Apex
    print("\n[ORCH] Starting AS on Apex...")
    as_client = ssh_run_background(APEX_IP, "apex", "python3 hw_measure_as.py", "[AS]  ")
    time.sleep(2.0)

    # Step 3: Run Device on Pi (wait for completion)
    print("\n[ORCH] Running Device on Pi...")
    rc = ssh_run_foreground(PI_IP, "pi", "python3 hw_measure_device.py", "[DEV] ")

    print(f"\n[ORCH] Device finished (exit={rc}). Waiting for AS summary...")
    time.sleep(2)

    # Teardown
    print("[ORCH] Stopping AS...")
    as_client.exec_command("pkill -f hw_measure_as.py")
    as_client.close()
    time.sleep(0.5)
    print("[ORCH] Stopping GW...")
    gw_proc.terminate()
    gw_proc.wait()
    print("[ORCH] Done.")
