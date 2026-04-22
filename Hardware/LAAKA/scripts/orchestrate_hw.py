#!/usr/bin/env python3
"""
orchestrate_hw.py — Full automated LAAKA hardware simulation runner.

Runs entirely from the laptop.  Uses paramiko for SSH + SFTP so no
SSH keys or sshpass are required — plain password auth works.

Topology
  Laptop          = Registration Authority (RA)   port 5683   gw_hw.py
  RPi #1 (Fog)    = Fog Auth Server               port 5684   as_hw.py
  RPi #2 (Node)   = IoT Device                    port 5685   node_hw.py

What this script does
  1. Install paramiko locally if missing
  2. SSH into both RPis (password from roles.env)
  3. Upload native/ + config/ + requirements.txt via SFTP
  4. pip3 install pycryptodome on each RPi
  5. Start Fog on RPi #1 (SSH channel, stdout -> fog.log)
  6. Start RA on this laptop (subprocess, stdout -> ra.log)
  7. Start Node on RPi #2 (SSH channel, stdout -> node.log)
  8. Wait for Node to finish (natural exit after data loop)
  9. Wait 3 s, then stop Fog + RA
 10. Parse HW_METRIC lines from all 3 logs -> hw_metrics.csv
 11. Print full log + metrics summary

Usage
  cd "c:\\ANUP\\MTP\\Proposing\\Codes For COOJA\\Hardware\\LAAKA"
  python scripts/orchestrate_hw.py
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE         = Path(__file__).resolve().parent.parent   # …/LAAKA/
NATIVE_DIR   = HERE / "native"
CONFIG_DIR   = HERE / "config"
RESULTS_DIR  = HERE / "results"
PARSE_SCRIPT = HERE / "scripts" / "06-parse-hw-metrics.py"

RESULTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Install paramiko if needed
# ---------------------------------------------------------------------------
try:
    import paramiko
except ImportError:
    print("[setup] paramiko not found — installing ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "--quiet"])
    import paramiko  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
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
    """Create remote directory tree (like mkdir -p)."""
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
    """Recursively upload local_dir to remote_dir via SFTP."""
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
                   log_path: Path,
                   prefix: str) -> None:
    """Read SSH channel stdout and write to log file + console."""
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
                fh.write(text + "\n")
                fh.flush()
                print(f"[{prefix}] {text}", flush=True)
        # flush remainder
        if buf:
            text = buf.decode("utf-8", errors="replace")
            fh.write(text + "\n")
            fh.flush()
            print(f"[{prefix}] {text}", flush=True)


def print_section(title: str) -> None:
    print("")
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    cfg_path = CONFIG_DIR / "roles.env"
    if not cfg_path.exists():
        print(f"[ERROR] roles.env not found: {cfg_path}")
        return 1

    cfg = parse_env_file(str(cfg_path))

    as_user   = cfg.get("AS_USER")   or "pi"
    as_host   = cfg.get("AS_HOST",   "192.168.1.132")
    as_pass   = cfg.get("AS_PASS",   "raspberrypi")

    node_user = cfg.get("NODE_USER") or "pi"
    node_host = cfg.get("NODE_HOST", "192.168.1.113")
    node_pass = cfg.get("NODE_PASS", "raspberrypi")

    gw_host   = cfg.get("GW_HOST",   "192.168.1.202")
    gw_port   = int(cfg.get("GW_PORT",  "5683"))

    send_count    = int(cfg.get("NODE_SEND_COUNT", "10"))
    send_interval = float(cfg.get("NODE_SEND_INTERVAL_S", "3"))

    remote_fog  = f"/home/{as_user}/mtp-hardware/LAAKA"
    remote_node = f"/home/{node_user}/mtp-hardware/LAAKA"

    print_section("LAAKA Hardware Simulation")
    print(f"  RA   (this laptop) : {gw_host}:{gw_port}")
    print(f"  Fog  (RPi #1)      : {as_user}@{as_host}")
    print(f"  Node (RPi #2)      : {node_user}@{node_host}")
    print(f"  Data packets       : {send_count} x {send_interval}s")
    print(f"  Results dir        : {RESULTS_DIR}")

    # ------------------------------------------------------------------
    # 1. Connect
    # ------------------------------------------------------------------
    print_section("1/7  Connecting to RPis")
    print(f"[ssh] Connecting to Fog  {as_user}@{as_host} ...")
    fog_ssh = ssh_connect(as_host, as_user, as_pass)
    print(f"[ssh] Connected to Fog.")

    print(f"[ssh] Connecting to Node {node_user}@{node_host} ...")
    node_ssh = ssh_connect(node_host, node_user, node_pass)
    print(f"[ssh] Connected to Node.")

    # ------------------------------------------------------------------
    # 2. Deploy project files via SFTP
    # ------------------------------------------------------------------
    print_section("2/7  Deploying project files")

    for ssh_c, remote_base, label in [
        (fog_ssh,  remote_fog,  f"{as_user}@{as_host}"),
        (node_ssh, remote_node, f"{node_user}@{node_host}"),
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
        print(f"       done.")

    # ------------------------------------------------------------------
    # 3. Install pycryptodome
    # ------------------------------------------------------------------
    print_section("3/7  Installing pycryptodome on RPis")

    for ssh_c, label in [(fog_ssh, "Fog"), (node_ssh, "Node")]:
        print(f"[pip] {label} ...")
        # --break-system-packages is required on Raspberry Pi OS (Bookworm / PEP 668)
        _, out, _ = ssh_c.exec_command(
            "pip3 install pycryptodome --quiet --break-system-packages 2>&1 | tail -2"
            " || pip3 install pycryptodome --quiet 2>&1 | tail -2")
        result = out.read().decode("utf-8", errors="replace").strip()
        if result:
            print(f"      {result}")

    # ------------------------------------------------------------------
    # 4. Start Fog on RPi #1
    # ------------------------------------------------------------------
    print_section("4/7  Starting Fog server on RPi #1")

    fog_tr  = fog_ssh.get_transport()
    fog_ch  = fog_tr.open_session()
    fog_ch.set_combine_stderr(True)
    fog_ch.exec_command(f"cd {remote_fog} && python3 -u native/as_hw.py")

    fog_log    = RESULTS_DIR / "fog.log"
    fog_thread = threading.Thread(
        target=stream_channel,
        args=(fog_ch, fog_log, "FOG"),
        daemon=True,
    )
    fog_thread.start()
    time.sleep(3)   # give Fog socket time to bind
    print(f"[fog] Running — log: {fog_log}")

    # ------------------------------------------------------------------
    # 5. Start RA on this laptop
    # ------------------------------------------------------------------
    print_section("5/7  Starting RA on laptop")

    ra_log    = RESULTS_DIR / "ra.log"
    ra_log_fh = open(ra_log, "w", encoding="utf-8")
    env_ra    = dict(os.environ)
    env_ra["PYTHONUNBUFFERED"] = "1"
    env_ra["LAAKA_ROLES_FILE"] = str(cfg_path)

    ra_proc = subprocess.Popen(
        [sys.executable, "-u", str(NATIVE_DIR / "gw_hw.py")],
        stdout=ra_log_fh,
        stderr=subprocess.STDOUT,
        env=env_ra,
    )
    time.sleep(2)   # give RA socket time to bind
    print(f"[ra] Running (PID {ra_proc.pid}) — log: {ra_log}")

    # Mirror RA log to console in a background thread
    def _tail_ra():
        ra_log_read = open(ra_log, "r", encoding="utf-8", errors="replace")
        while ra_proc.poll() is None or True:
            line = ra_log_read.readline()
            if line:
                print(f"[RA ] {line.rstrip()}", flush=True)
            else:
                time.sleep(0.1)
                if ra_proc.poll() is not None:
                    break

    threading.Thread(target=_tail_ra, daemon=True).start()

    # ------------------------------------------------------------------
    # 6. Start Device Node on RPi #2
    # ------------------------------------------------------------------
    print_section("6/7  Starting Device Node on RPi #2")

    node_tr = node_ssh.get_transport()
    node_ch = node_tr.open_session()
    node_ch.set_combine_stderr(True)
    node_ch.exec_command(f"cd {remote_node} && python3 -u native/node_hw.py")

    node_log    = RESULTS_DIR / "node.log"
    node_thread = threading.Thread(
        target=stream_channel,
        args=(node_ch, node_log, "NODE"),
        daemon=True,
    )
    node_thread.start()

    # Wait for Node to complete
    timeout_s = int(send_count * send_interval + 90)
    print(f"[node] Running — waiting up to {timeout_s}s "
          f"({send_count} packets x {send_interval}s + 90s slack) ...")
    deadline = time.monotonic() + timeout_s
    while not node_ch.closed and time.monotonic() < deadline:
        time.sleep(1)

    node_thread.join(timeout=10)

    exit_code = node_ch.recv_exit_status()
    if exit_code == 0:
        print("\n[node] Completed successfully (exit 0).", flush=True)
    else:
        print(f"\n[node] Exited with code {exit_code}", flush=True)

    # ------------------------------------------------------------------
    # 7. Shutdown Fog + RA
    # ------------------------------------------------------------------
    print_section("7/7  Stopping Fog + RA")

    print("[cleanup] Waiting 3 s for Fog to flush final DATA lines ...")
    time.sleep(3)

    fog_ch.close()
    fog_thread.join(timeout=5)
    ra_proc.terminate()
    ra_log_fh.flush()
    ra_log_fh.close()
    fog_ssh.close()
    node_ssh.close()
    print("[cleanup] Done.")

    # ------------------------------------------------------------------
    # Parse metrics from all 3 logs
    # ------------------------------------------------------------------
    print_section("Parsing Metrics")

    per_role_csvs = []
    for role, log_name in [("ra", "ra.log"), ("fog", "fog.log"),
                            ("node", "node.log")]:
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
            print(f"  {role.upper()}: log not found ({lf.name})")

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

    for role_label, log_name in [("RA", "ra.log"),
                                  ("FOG", "fog.log"),
                                  ("NODE", "node.log")]:
        lf = RESULTS_DIR / log_name
        if not lf.exists():
            continue
        lines = lf.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"\n--- {role_label} LOG (last 25 lines) ---")
        for line in lines[-25:]:
            tag = "  >>  " if "HW_METRIC|" in line else "      "
            print(tag + line)

    if combined.exists():
        print("\n--- hw_metrics.csv (all 3 roles) ---")
        print(combined.read_text(encoding="utf-8"))

    print(f"\nAll logs saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
