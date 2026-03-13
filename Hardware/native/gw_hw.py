#!/usr/bin/env python3
import os
import socket
from typing import Dict, Tuple

from common import from_json_bytes, now_ts, parse_env_file, decrypt_text, sha256_hex


def role_paths() -> Tuple[str, str]:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = os.path.join(base, "config", "roles.env")
    return base, cfg


def main() -> None:
    _, cfg_path = role_paths()
    cfg = parse_env_file(cfg_path)

    gw_host = cfg.get("GW_BIND", "0.0.0.0")
    gw_port = int(cfg.get("GW_PORT", "5683"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((gw_host, gw_port))

    print(f"[GW] Listening on {gw_host}:{gw_port}")

    sessions: Dict[str, Dict[str, str]] = {}

    while True:
        raw, addr = sock.recvfrom(8192)
        msg = from_json_bytes(raw)
        mtype = msg.get("type", "")

        if mtype == "GW_TOKEN":
            device_id = str(msg.get("device_id", ""))
            pid = msg.get("pid", "")
            sk = msg.get("session_key", "")
            token = msg.get("token", "")
            ts = int(msg.get("ts", 0))

            if abs(now_ts() - ts) > 120:
                print("[GW] Rejected token: stale ts")
                continue

            expected = sha256_hex(f"{sk}|gw-token|{ts}")
            if token != expected:
                print("[GW] Rejected token: invalid")
                continue

            sessions[device_id] = {"pid": pid, "session_key": sk}
            print(f"[GW] Session updated for device {device_id}")

        elif mtype == "DATA":
            device_id = str(msg.get("device_id", ""))
            pid = msg.get("pid", "")
            nonce = msg.get("nonce", "")
            cipher = msg.get("cipher", "")
            counter = int(msg.get("counter", 0))
            mac = msg.get("mac", "")

            sess = sessions.get(device_id)
            if sess is None:
                print(f"[GW] No session for device {device_id}; data dropped")
                continue
            if pid != sess["pid"]:
                print(f"[GW] PID mismatch for device {device_id}; data dropped")
                continue

            expected_mac = sha256_hex(f"{sess['session_key']}|{cipher}|{counter}")
            if mac != expected_mac:
                print(f"[GW] MAC failed for device {device_id}; data dropped")
                continue

            plain = decrypt_text(cipher, sess["session_key"], nonce)
            print(f"[GW] DATA from device {device_id}: {plain}")

        else:
            print(f"[GW] Unknown message type from {addr}: {mtype}")


if __name__ == "__main__":
    main()
