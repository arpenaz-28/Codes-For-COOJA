#!/usr/bin/env python3
"""
Orchestrator — DAuth hardware simulation (Hardware/MIRACLE/DAuth).
Self-contained: deploys all files from THIS folder, runs GW locally, AS on Apex,
Device on Pi (same role placement as the Proposed scheme), collects results.

Usage:  python run_simulation.py [run_number]   ->  results/run_<N>.json
Env:    USE_MIRACL=1 (default) routes device/AS crypto through libmiraclshim.so.
"""
import json, subprocess, threading, time, sys, os
import paramiko

HERE        = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

GW_SCRIPT  = os.path.join(HERE, "gw.py")
APEX_IP    = "192.168.1.132"     # AS
PI_IP      = "192.168.1.113"     # Device (measurement target)
PASSWORD   = "raspberrypi"
REMOTE_DIR = "DAuthFair_HW"
USE_MIRACL = os.environ.get("USE_MIRACL", "1")
_mir = (f" USE_MIRACL={USE_MIRACL} MIRACL_SO=$HOME/{REMOTE_DIR}/libmiraclshim.so"
        if USE_MIRACL == "1" else "")
ENV        = "export GW_IP=192.168.1.201 AS_IP=192.168.1.132 DEV_IP=192.168.1.113" + _mir


def stream(tag, channel):
    for line in channel:
        print(f"{tag} {line}", end="", flush=True)


def scp_file(local_path, ip, user, remote_dir, filename=None):
    fname = filename or os.path.basename(local_path)
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username=user, password=PASSWORD, timeout=10)
    c.exec_command(f"mkdir -p ~/{remote_dir}"); time.sleep(0.3)
    sftp = c.open_sftp(); sftp.put(local_path, f"/home/{user}/{remote_dir}/{fname}")
    sftp.close(); c.close()
    print(f"[SCP] {fname} -> {user}@{ip}:~/{remote_dir}/")


def ssh_run_background(ip, user, cmd, tag, kill_pattern):
    k = paramiko.SSHClient(); k.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    k.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, ko, _ = k.exec_command(f"pkill -f {kill_pattern}; sleep 0.3"); ko.read(); k.close()
    time.sleep(0.5)
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, so, se = c.exec_command(f"cd ~/{REMOTE_DIR} && {ENV} && {cmd}", get_pty=False)
    threading.Thread(target=stream, args=(tag, so), daemon=True).start()
    threading.Thread(target=stream, args=(tag, se), daemon=True).start()
    return c


def ssh_run_foreground(ip, user, cmd, tag):
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username=user, password=PASSWORD, timeout=10)
    _, so, se = c.exec_command(f"cd {REMOTE_DIR} && {ENV} && {cmd}", get_pty=False)
    for line in so: print(f"{tag} {line}", end="", flush=True)
    for line in se: print(f"{tag}[ERR] {line}", end="", flush=True)
    rc = so.channel.recv_exit_status(); c.close(); return rc


if __name__ == "__main__":
    run_num  = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out_json = os.path.join(RESULTS_DIR, f"run_{run_num:02d}.json")
    print("=" * 70)
    print(f"DAuth Hardware Simulation — run #{run_num}  (MIRACL={USE_MIRACL})")
    print(f"  GW: Laptop   AS: Apex({APEX_IP})   Device: Pi({PI_IP})")
    print("=" * 70)

    shared = ["common.py", "config.py"]
    mir    = ["miracl_crypto.py", "libmiraclshim.so"] if USE_MIRACL == "1" else []

    print("\n[ORCH] Copying to Apex (AS) ...")
    for f in ["as_node.py"] + shared + mir:
        scp_file(os.path.join(HERE, f), APEX_IP, "apex", REMOTE_DIR)
    print("\n[ORCH] Copying to Pi (Device) ...")
    for f in ["device.py"] + shared + mir:
        scp_file(os.path.join(HERE, f), PI_IP, "pi", REMOTE_DIR)

    print("\n[ORCH] Starting GW on Laptop ...")
    gw_env = os.environ.copy()
    gw_env.update(GW_IP="192.168.1.201", AS_IP="192.168.1.132", DEV_IP="192.168.1.113")
    gw_env.pop("USE_MIRACL", None)   # GW stays Python
    gw_proc = subprocess.Popen([sys.executable, GW_SCRIPT], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1, env=gw_env)
    threading.Thread(target=stream, args=("[GW]  ", gw_proc.stdout), daemon=True).start()
    time.sleep(1.5)

    print("\n[ORCH] Starting AS on Apex ...")
    as_client = ssh_run_background(APEX_IP, "apex", "python3 as_node.py", "[AS]  ",
                                   kill_pattern="as_node.py")
    time.sleep(2.0)

    print("\n[ORCH] Running Device on Pi ...")
    rc = ssh_run_foreground(PI_IP, "pi", "python3 device.py", "[DEV] ")
    print(f"\n[ORCH] Device finished (exit={rc}).")
    time.sleep(2)

    print("[ORCH] Collecting results from Pi ...")
    try:
        c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(PI_IP, username="pi", password=PASSWORD, timeout=10)
        sftp = c.open_sftp()
        sftp.get(f"/home/pi/{REMOTE_DIR}/dauthfair_hw_run.json", out_json)
        sftp.close(); c.close()
        s = json.load(open(out_json)).get("summary", {})
        print(f"[ORCH] Saved: {out_json}")
        print(f"[ORCH] Avg Auth+KeyEx : {s.get('avg_ak_energy_j',0):.6f} J  {s.get('avg_ak_time_s',0):.4f} s")
    except Exception as e:
        print(f"[ORCH] WARNING: could not collect results: {e}")

    print("[ORCH] Stopping AS ...")
    as_client.exec_command("pkill -f as_node.py"); as_client.close(); time.sleep(0.5)
    print("[ORCH] Stopping GW ..."); gw_proc.terminate(); gw_proc.wait()
    print("[ORCH] Done.")
