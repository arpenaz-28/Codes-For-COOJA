#!/usr/bin/env python3
"""
orchestrate_hw.py — Full automated Zhou scheme hardware simulation runner.

Topology
  Laptop          = GW Server (port 5684) + GW Router (port 5683)
  RPi #1 (SN)     = Sensor Node  (apex@192.168.1.132  port 5685)
  RPi #2 (User)   = User Device  (pi@192.168.1.113    port 5686)

What this script does
  1.  Install paramiko locally if missing
  2.  SSH into both RPis (password from roles.env)
  3.  Upload native/ + config/ + requirements.txt via SFTP
  4.  pip3 install pycryptodome on each RPi
  5.  Start GW_Server on this laptop     (subprocess → gw_server.log)
  6.  Start GW_Router on this laptop     (subprocess → gw_router.log)
  7.  Start Sensor Node on RPi #1        (SSH channel → sn.log)
  8.  Start User Device on RPi #2        (SSH channel → user.log)
       [User has a USER_START_DELAY_S=30 built-in wait for SN to register]
  9.  Wait for User to complete
 10.  Wait 3 s, then stop GW processes
 11.  Parse HW_METRIC lines from all logs → hw_metrics.csv
 12.  Print full summary

Usage
  cd "c:\\ANUP\\MTP\\Proposing\\Codes For COOJA\\Hardware\\Zhou"
  python scripts/orchestrate_hw.py
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

# Force UTF-8 console output on Windows so Greek/special chars don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE         = Path(__file__).resolve().parent.parent   # …/Zhou/
NATIVE_DIR   = HERE / "native"
CONFIG_DIR   = HERE / "config"
RESULTS_DIR  = HERE / "results"
PARSE_SCRIPT = HERE / "scripts" / "06-parse-hw-metrics.py"

RESULTS_DIR.mkdir(exist_ok=True)

try:
    import paramiko
except ImportError:
    print("[setup] paramiko not found — installing ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "--quiet"])
    import paramiko  # type: ignore


# ---------------------------------------------------------------------------
# Helpers (same as LAAKA orchestrator)
# ---------------------------------------------------------------------------

def parse_env_file(path: str) -> dict:
    cfg: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def ssh_connect(host: str, username: str, password: str) -> "paramiko.SSHClient":
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password,
                   timeout=30, banner_timeout=30, auth_timeout=30)
    return client


def sftp_mkdir_p(sftp: "paramiko.SFTPClient", remote_path: str) -> None:
    parts = [p for p in remote_path.split("/") if p]
    cur = ""
    for part in parts:
        cur = cur + "/" + part
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def sftp_upload_dir(sftp: "paramiko.SFTPClient",
                    local_dir: Path, remote_dir: str) -> None:
    sftp_mkdir_p(sftp, remote_dir)
    for item in sorted(local_dir.iterdir()):
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        remote_item = remote_dir + "/" + item.name
        if item.is_dir():
            sftp_upload_dir(sftp, item, remote_item)
        else:
            sftp.put(str(item), remote_item)


def stream_channel(channel: "paramiko.Channel",
                   log_path: Path, prefix: str) -> None:
    with open(log_path, "w", encoding="utf-8", errors="replace") as fh:
        buf = b""
        while True:
            try:
                chunk = channel.recv(4096)
            except Exception:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace")
                fh.write(text + "\n"); fh.flush()
                try:
                    print(f"[{prefix}] {text}", flush=True)
                except Exception:
                    pass
        if buf:
            text = buf.decode("utf-8", errors="replace")
            fh.write(text + "\n"); fh.flush()
            try:
                print(f"[{prefix}] {text}", flush=True)
            except Exception:
                pass


def tail_proc_log(proc: subprocess.Popen, log_path: Path, prefix: str) -> None:
    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        while True:
            line = fh.readline()
            if line:
                print(f"[{prefix}] {line.rstrip()}", flush=True)
            else:
                time.sleep(0.1)
                if proc.poll() is not None:
                    break


def print_section(title: str) -> None:
    print(""); print("=" * 65); print(f"  {title}"); print("=" * 65)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    cfg_path = CONFIG_DIR / "roles.env"
    cfg = parse_env_file(str(cfg_path))

    sn_user   = cfg.get("SN_USER")   or "pi"
    sn_host   = cfg.get("SN_HOST",   "192.168.1.132")
    sn_pass   = cfg.get("SN_PASS",   "raspberrypi")

    user_user = cfg.get("USER_USER") or "pi"
    user_host = cfg.get("USER_HOST", "192.168.1.113")
    user_pass = cfg.get("USER_PASS", "raspberrypi")

    gw_host      = cfg.get("GW_HOST", "192.168.1.202")
    gw_srv_port  = int(cfg.get("GW_SERVER_PORT",  "5684"))
    gw_rtr_port  = int(cfg.get("GW_ROUTER_PORT",  "5683"))

    send_count    = int(cfg.get("USER_SEND_COUNT",    "10"))
    send_interval = float(cfg.get("USER_SEND_INTERVAL_S", "3"))
    start_delay   = float(cfg.get("USER_START_DELAY_S",   "30"))

    remote_sn   = f"/home/{sn_user}/mtp-hardware/Zhou"
    remote_user = f"/home/{user_user}/mtp-hardware/Zhou"

    print_section("Zhou Scheme Hardware Simulation")
    print(f"  GW Server+Router (laptop) : {gw_host}  ports {gw_rtr_port}/{gw_srv_port}")
    print(f"  Sensor Node (RPi #1)      : {sn_user}@{sn_host}")
    print(f"  User Device (RPi #2)      : {user_user}@{user_host}")
    print(f"  User start delay          : {start_delay:.0f}s  (SN registers first)")
    print(f"  Data packets              : {send_count} x {send_interval}s")
    print(f"  Results dir               : {RESULTS_DIR}")

    # ------------------------------------------------------------------
    # 1. Connect
    # ------------------------------------------------------------------
    print_section("1/7  Connecting to RPis")
    print(f"[ssh] Connecting to SN   {sn_user}@{sn_host} ...")
    sn_ssh = ssh_connect(sn_host, sn_user, sn_pass)
    print(f"[ssh] Connected to SN.")
    print(f"[ssh] Connecting to User {user_user}@{user_host} ...")
    user_ssh = ssh_connect(user_host, user_user, user_pass)
    print(f"[ssh] Connected to User.")

    # ------------------------------------------------------------------
    # 2. Deploy
    # ------------------------------------------------------------------
    print_section("2/7  Deploying project files")
    for ssh_c, remote_base, label in [
        (sn_ssh,   remote_sn,   f"{sn_user}@{sn_host}"),
        (user_ssh, remote_user, f"{user_user}@{user_host}"),
    ]:
        print(f"[sftp] Uploading to {label}:{remote_base} ...")
        sftp = ssh_c.open_sftp()
        sftp_upload_dir(sftp, NATIVE_DIR, remote_base + "/native")
        sftp_upload_dir(sftp, CONFIG_DIR, remote_base + "/config")
        req_txt = HERE / "requirements.txt"
        if req_txt.exists():
            sftp_mkdir_p(sftp, remote_base)
            sftp.put(str(req_txt), remote_base + "/requirements.txt")
        sftp.close()
        print("       done.")

    # ------------------------------------------------------------------
    # 3. Install pycryptodome
    # ------------------------------------------------------------------
    print_section("3/7  Installing pycryptodome on RPis")
    for ssh_c, label in [(sn_ssh, "SN"), (user_ssh, "User")]:
        print(f"[pip] {label} ...")
        _, out, _ = ssh_c.exec_command(
            "pip3 install pycryptodome --quiet --break-system-packages 2>&1 | tail -2"
            " || pip3 install pycryptodome --quiet 2>&1 | tail -2")
        result = out.read().decode("utf-8", errors="replace").strip()
        if result:
            print(f"      {result}")

    # ------------------------------------------------------------------
    # 4. Start GW_Server on laptop
    # ------------------------------------------------------------------
    print_section("4/7  Starting GW_Server + GW_Router on laptop")

    env_gw = dict(os.environ)
    env_gw["PYTHONUNBUFFERED"] = "1"

    gw_srv_log    = RESULTS_DIR / "gw_server.log"
    gw_srv_log_fh = open(gw_srv_log, "w", encoding="utf-8")
    gw_srv_proc   = subprocess.Popen(
        [sys.executable, "-u", str(NATIVE_DIR / "gw_server_hw.py")],
        stdout=gw_srv_log_fh, stderr=subprocess.STDOUT, env=env_gw,
    )
    threading.Thread(target=tail_proc_log,
                     args=(gw_srv_proc, gw_srv_log, "GW-SRV"), daemon=True).start()

    gw_rtr_log    = RESULTS_DIR / "gw_router.log"
    gw_rtr_log_fh = open(gw_rtr_log, "w", encoding="utf-8")
    gw_rtr_proc   = subprocess.Popen(
        [sys.executable, "-u", str(NATIVE_DIR / "gw_router_hw.py")],
        stdout=gw_rtr_log_fh, stderr=subprocess.STDOUT, env=env_gw,
    )
    threading.Thread(target=tail_proc_log,
                     args=(gw_rtr_proc, gw_rtr_log, "GW-RTR"), daemon=True).start()

    time.sleep(2)
    print(f"[gw-srv] PID {gw_srv_proc.pid} — log: {gw_srv_log}")
    print(f"[gw-rtr] PID {gw_rtr_proc.pid} — log: {gw_rtr_log}")

    # ------------------------------------------------------------------
    # 5. Start Sensor Node on RPi #1
    # ------------------------------------------------------------------
    print_section("5/7  Starting Sensor Node on RPi #1")

    sn_tr  = sn_ssh.get_transport()
    sn_ch  = sn_tr.open_session()
    sn_ch.set_combine_stderr(True)
    sn_ch.exec_command(f"cd {remote_sn} && python3 -u native/sn_hw.py")

    sn_log    = RESULTS_DIR / "sn.log"
    sn_thread = threading.Thread(
        target=stream_channel, args=(sn_ch, sn_log, "SN"), daemon=True)
    sn_thread.start()
    time.sleep(2)
    print(f"[sn] Running — log: {sn_log}")

    # ------------------------------------------------------------------
    # 6. Start User Device on RPi #2
    # ------------------------------------------------------------------
    print_section("6/7  Starting User Device on RPi #2")

    user_tr = user_ssh.get_transport()
    user_ch = user_tr.open_session()
    user_ch.set_combine_stderr(True)
    user_ch.exec_command(f"cd {remote_user} && python3 -u native/user_hw.py")

    user_log    = RESULTS_DIR / "user.log"
    user_thread = threading.Thread(
        target=stream_channel, args=(user_ch, user_log, "USER"), daemon=True)
    user_thread.start()

    # Wait for User to complete
    timeout_s = int(start_delay + 60 + send_count * send_interval + 60)
    print(f"[user] Running — user waits {start_delay:.0f}s for SN then does protocol")
    print(f"       Total timeout: {timeout_s}s")
    deadline = time.monotonic() + timeout_s
    while not user_ch.closed and time.monotonic() < deadline:
        time.sleep(1)
    user_thread.join(timeout=10)

    exit_code = user_ch.recv_exit_status()
    if exit_code == 0:
        print("\n[user] Completed successfully (exit 0).", flush=True)
    else:
        print(f"\n[user] Exited with code {exit_code}", flush=True)

    # ------------------------------------------------------------------
    # 7. Shutdown
    # ------------------------------------------------------------------
    print_section("7/7  Stopping all processes")
    print("[cleanup] Waiting 3 s for GW_Router to flush DATA lines ...")
    time.sleep(3)

    sn_ch.close(); sn_thread.join(timeout=5)
    for proc, fh in [(gw_srv_proc, gw_srv_log_fh),
                     (gw_rtr_proc, gw_rtr_log_fh)]:
        proc.terminate()
        fh.flush(); fh.close()
    sn_ssh.close(); user_ssh.close()
    print("[cleanup] Done.")

    # ------------------------------------------------------------------
    # Parse metrics from all 4 logs
    # ------------------------------------------------------------------
    print_section("Parsing Metrics")

    per_role_csvs = []
    for role, log_name in [("gw_server", "gw_server.log"),
                            ("gw_router", "gw_router.log"),
                            ("sn",        "sn.log"),
                            ("user",      "user.log")]:
        lf  = RESULTS_DIR / log_name
        csv = RESULTS_DIR / f"hw_metrics_{role}.csv"
        if lf.exists():
            res = subprocess.run(
                [sys.executable, str(PARSE_SCRIPT), str(lf), str(csv)],
                capture_output=True, text=True,
            )
            msg = (res.stdout + res.stderr).strip()
            print(f"  {role.upper()}: {msg}")
            if csv.exists():
                per_role_csvs.append(csv)
        else:
            print(f"  {role.upper()}: log not found")

    combined = RESULTS_DIR / "hw_metrics.csv"
    if per_role_csvs:
        header = per_role_csvs[0].read_text(encoding="utf-8").splitlines()[0]
        rows   = [header]
        for f in per_role_csvs:
            rows.extend(f.read_text(encoding="utf-8").splitlines()[1:])
        combined.write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(f"\n  Combined CSV: {combined}")

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------
    print_section("RESULTS")

    for label, log_name in [("GW_SERVER", "gw_server.log"),
                             ("SN",       "sn.log"),
                             ("USER",     "user.log")]:
        lf = RESULTS_DIR / log_name
        if not lf.exists():
            continue
        lines = lf.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"\n--- {label} LOG (last 20 lines) ---")
        for line in lines[-20:]:
            tag = "  >>  " if "HW_METRIC|" in line else "      "
            try:
                print(tag + line)
            except UnicodeEncodeError:
                print(tag + line.encode("ascii", errors="replace").decode("ascii"))

    if combined.exists():
        print("\n--- hw_metrics.csv ---")
        print(combined.read_text(encoding="utf-8"))

    print(f"\nAll logs saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
