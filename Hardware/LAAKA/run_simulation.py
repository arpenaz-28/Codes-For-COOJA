#!/usr/bin/env python3
"""
Orchestration script — starts RA (local), Fog (Apex), Device (Pi) in order
and streams all output to the console.
"""
import subprocess, threading, time, sys, os
import paramiko

RA_SCRIPT  = os.path.join(os.path.dirname(__file__), "hw_laaka_ra.py")
APEX_IP    = "192.168.1.132"
PI_IP      = "192.168.1.113"
PASSWORD   = "raspberrypi"
REMOTE_DIR = "ANUP_Hardware_Simulation"
ENV        = "export GW_IP=192.168.1.201 AS_IP=192.168.1.132 DEV_IP=192.168.1.113"

ra_proc = None


def stream(tag, channel):
    for line in channel:
        print(f"{tag} {line}", end="", flush=True)


def ssh_run_background(ip, cmd, tag):
    """Start a command on remote host, stream output in a background thread."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username="apex" if ip == APEX_IP else "pi",
                   password=PASSWORD, timeout=10)
    stdin, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && {ENV} && {cmd}", get_pty=False)
    t1 = threading.Thread(target=stream, args=(tag, stdout), daemon=True)
    t2 = threading.Thread(target=stream, args=(tag, stderr), daemon=True)
    t1.start(); t2.start()
    return client, stdout, t1, t2


def ssh_run_foreground(ip, user, cmd, tag):
    """Run command on remote host and wait for it to finish, return output."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=PASSWORD, timeout=10)
    stdin, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && {ENV} && {cmd}", get_pty=False)
    lines = []
    for line in stdout:
        print(f"{tag} {line}", end="", flush=True)
        lines.append(line)
    for line in stderr:
        print(f"{tag}[ERR] {line}", end="", flush=True)
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    return exit_code, lines


if __name__ == "__main__":
    print("=" * 70)
    print("LAAKA Hardware Simulation — orchestrated run")
    print("=" * 70)

    # ── Step 1: Start RA locally ──────────────────────────────────────────
    print("\n[ORCH] Starting RA on Laptop...")
    ra_env = os.environ.copy()
    ra_env["GW_IP"]  = "192.168.1.201"
    ra_env["AS_IP"]  = "192.168.1.132"   # Fog = Apex
    ra_env["DEV_IP"] = "192.168.1.113"
    ra_proc = subprocess.Popen(
        [sys.executable, RA_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=ra_env
    )
    def stream_ra():
        for line in ra_proc.stdout:
            print(f"[RA]   {line}", end="", flush=True)
    threading.Thread(target=stream_ra, daemon=True).start()
    time.sleep(1.5)   # wait for RA socket to bind

    # ── Step 2: Kill any old Fog, start fresh ─────────────────────────────
    print("\n[ORCH] Starting Fog on Apex...")
    fog_client = paramiko.SSHClient()
    fog_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    fog_client.connect(APEX_IP, username="apex", password=PASSWORD, timeout=10)
    fog_client.exec_command("pkill -f hw_laaka_fog.py; sleep 0.5")
    time.sleep(0.8)

    _, fog_stdout, _, _ = ssh_run_background(
        APEX_IP,
        "python3 hw_laaka_fog.py",
        "[FOG] "
    )
    time.sleep(2.0)   # wait for all 4 Fog listeners to bind

    # ── Step 3: Run Device on Pi (foreground — wait for completion) ───────
    print("\n[ORCH] Running Device on Pi...")
    rc, _ = ssh_run_foreground(PI_IP, "pi",
                               "python3 hw_laaka_device.py", "[DEV] ")

    print(f"\n[ORCH] Device script finished (exit={rc})")
    print("[ORCH] Waiting 2 s for final Fog output...")
    time.sleep(2)

    # ── Teardown ──────────────────────────────────────────────────────────
    print("\n[ORCH] Stopping Fog...")
    fog_client.exec_command("pkill -f hw_laaka_fog.py")
    fog_client.close()
    time.sleep(0.5)

    print("[ORCH] Stopping RA...")
    ra_proc.terminate()
    ra_proc.wait()

    print("\n[ORCH] Simulation complete.")
