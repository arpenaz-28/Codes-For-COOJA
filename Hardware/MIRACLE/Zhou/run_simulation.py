#!/usr/bin/env python3
"""
Orchestration script — Zhou Scheme hardware simulation.
Starts GW (local), SN (Pi), User (Apex) in order and streams all output.

Role mapping (Zhou scheme reverses RPi roles vs Proposed/LAAKA):
  GW   → Laptop (local subprocess)     hw_zhou_gw.py
  SN   → Pi     (192.168.1.113, pi)    hw_zhou_sn.py
  User → Apex   (192.168.1.132, apex)  hw_zhou_user.py  ← measurement target

Usage:
  python run_simulation.py [run_number]
  Results saved to: Hardware/Zhou/results/run_<N>.json
"""
import json, subprocess, threading, time, sys, os
import paramiko

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

GW_SCRIPT  = os.path.join(os.path.dirname(__file__), "hw_zhou_gw.py")
APEX_IP    = "192.168.1.132"    # User (measurement target)
PI_IP      = "192.168.1.113"    # SN
PASSWORD   = "raspberrypi"
REMOTE_DIR = "ANUP_Hardware_Simulation"
# USE_MIRACL=1 (default) routes User/SN crypto through libmiraclshim.so; set 0 for Python baseline.
USE_MIRACL = os.environ.get("USE_MIRACL", "1")
_mir = (f" USE_MIRACL={USE_MIRACL} MIRACL_SO=$HOME/{REMOTE_DIR}/libmiraclshim.so"
        if USE_MIRACL == "1" else "")
ENV        = "export GW_IP=192.168.1.201 AS_IP=192.168.1.113 DEV_IP=192.168.1.132" + _mir


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


def ssh_run_background(ip, user, script_name, tag, kill_pattern=None):
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
        f"cd ~/{REMOTE_DIR} && {ENV} && python3 {script_name}", get_pty=False)
    threading.Thread(target=stream, args=(tag, stdout), daemon=True).start()
    threading.Thread(target=stream, args=(tag, stderr), daemon=True).start()
    return client


def ssh_run_foreground(ip, user, script_name, tag):
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
    run_num  = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out_json = os.path.join(RESULTS_DIR, f"run_{run_num:02d}.json")

    print("=" * 70)
    print(f"Zhou Scheme Hardware Simulation — orchestrated run #{run_num}")
    print(f"  GW     : Laptop   (local)")
    print(f"  SN     : Pi       ({PI_IP})")
    print(f"  User   : Apex     ({APEX_IP})  ← measurement target")
    print(f"  Output : {out_json}")
    print("=" * 70)

    here = os.path.dirname(os.path.abspath(__file__))

    # ── Step 0: Copy updated scripts to remotes ───────────────────────────
    print("\n[ORCH] Copying scripts to Pi (SN) ...")
    scp_file(os.path.join(here, "hw_zhou_sn.py"),          PI_IP, "pi", REMOTE_DIR)
    scp_file(os.path.join(here, "common.py"),        PI_IP, "pi", REMOTE_DIR)
    scp_file(os.path.join(here, "config.py"),        PI_IP, "pi", REMOTE_DIR)

    print("\n[ORCH] Copying scripts to Apex (User / measurement target) ...")
    scp_file(os.path.join(here, "hw_zhou_user.py"),        APEX_IP, "apex", REMOTE_DIR)
    scp_file(os.path.join(here, "common.py"),        APEX_IP, "apex", REMOTE_DIR)
    scp_file(os.path.join(here, "config.py"),        APEX_IP, "apex", REMOTE_DIR)

    # ── MIRACL crypto backend (User + SN only; GW stays Python) ───────────
    if USE_MIRACL == "1":
        print("\n[ORCH] Deploying MIRACL backend to User + SN ...")
        for ip, user in [(APEX_IP, "apex"), (PI_IP, "pi")]:
            scp_file(os.path.join(here, "miracl_crypto.py"),   ip, user, REMOTE_DIR)
            scp_file(os.path.join(here, "libmiraclshim.so"),   ip, user, REMOTE_DIR)

    # ── Step 1: Start GW on Laptop ────────────────────────────────────────
    print("\n[ORCH] Starting GW on Laptop (local)...")
    gw_env = os.environ.copy(); gw_env.pop("USE_MIRACL", None)
    gw_env["GW_IP"]  = "192.168.1.201"
    gw_env["AS_IP"]  = "192.168.1.113"
    gw_env["DEV_IP"] = "192.168.1.132"
    gw_proc = subprocess.Popen(
        [sys.executable, GW_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=gw_env
    )
    threading.Thread(target=stream, args=("[GW]  ", gw_proc.stdout), daemon=True).start()
    time.sleep(1.5)

    # ── Step 2: Start SN on Pi ────────────────────────────────────────────
    print("\n[ORCH] Starting SN on Pi...")
    sn_client = ssh_run_background(PI_IP, "pi", "hw_zhou_sn.py",
                                   "[SN]  ", kill_pattern="hw_zhou_sn.py")
    time.sleep(2.5)

    # ── Step 3: Run User on Apex (foreground — measurement target) ────────
    print("\n[ORCH] Running User on Apex (measurement target)...")
    rc = ssh_run_foreground(APEX_IP, "apex", "hw_zhou_user.py", "[USR] ")

    print(f"\n[ORCH] User script finished (exit={rc}). Waiting 2 s for server summaries...")
    time.sleep(2)

    # ── Collect results JSON from Apex ────────────────────────────────────
    print("[ORCH] Collecting results from Apex ...")
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(APEX_IP, username="apex", password=PASSWORD, timeout=10)
        sftp = c.open_sftp()
        sftp.get(f"/home/apex/{REMOTE_DIR}/zhou_hw_run.json", out_json)
        sftp.close()
        c.close()
        with open(out_json) as f:
            data = json.load(f)
        s = data.get('summary', {})
        print(f"[ORCH] Saved : {out_json}")
        print(f"[ORCH] Avg Auth(M1-M4) : {s.get('avg_auth_energy_j', 0):.6f} J  {s.get('avg_auth_time_s', 0):.4f} s")
    except Exception as e:
        print(f"[ORCH] WARNING: Could not collect results JSON: {e}")

    # ── Collect SN-registration one-time setup cost from SN (Pi) ──────────────
    try:
        sn_json = os.path.join(RESULTS_DIR, f"snreg_{run_num:02d}.json")
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(PI_IP, username="pi", password=PASSWORD, timeout=10)
        sftp = c.open_sftp()
        sftp.get(f"/home/pi/{REMOTE_DIR}/snreg_hw_run.json", sn_json)
        sftp.close(); c.close()
        sr = json.load(open(sn_json))
        print(f"[ORCH] SN registration (one-time): "
              f"{sr['energy_j']:.6f} J  {sr['wall_s']:.4f} s  (cpu {sr['cpu_s']:.4f} s)")
    except Exception as e:
        print(f"[ORCH] WARNING: Could not collect SN-reg JSON: {e}")

    # ── Teardown ──────────────────────────────────────────────────────────
    print("\n[ORCH] Stopping SN on Pi...")
    sn_client.exec_command("pkill -f hw_zhou_sn.py")
    sn_client.close()
    time.sleep(0.5)
    print("[ORCH] Stopping GW...")
    gw_proc.terminate()
    gw_proc.wait()
    print("\n[ORCH] Zhou hardware simulation complete.")
