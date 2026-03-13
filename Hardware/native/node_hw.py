#!/usr/bin/env python3
import os
import secrets
import socket
import time
from typing import Dict, Tuple

from common import (
    from_json_bytes,
    make_puf,
    now_ts,
    puf_response_bit,
    parse_env_file,
    random_challenge_hex,
    sha256_hex,
    to_json_bytes,
    xor_hex,
    encrypt_text,
)


def role_paths() -> Tuple[str, str]:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = os.path.join(base, "config", "roles.env")
    return base, cfg


def recv_until(sock: socket.socket, expected: str, timeout: float = 5.0) -> Dict:
    sock.settimeout(timeout)
    while True:
        raw, _ = sock.recvfrom(8192)
        msg = from_json_bytes(raw)
        if msg.get("type") == expected:
            return msg


def main() -> None:
    _, cfg_path = role_paths()
    cfg = parse_env_file(cfg_path)

    as_host = cfg.get("AS_HOST", "127.0.0.1")
    as_port = int(cfg.get("AS_PORT", "5684"))
    gw_host = cfg.get("GW_HOST", "127.0.0.1")
    gw_port = int(cfg.get("GW_PORT", "5683"))

    device_id = cfg.get("DEVICE_ID", "81")
    device_secret = cfg.get("DEVICE_SECRET", "device-secret-81")
    puf_seed = cfg.get("PUF_SEED", f"puf-seed-{device_id}")
    puf_bits = int(cfg.get("PUF_CHALLENGE_BITS", "64"))
    enroll_crp_count = int(cfg.get("PUF_ENROLL_CRP_COUNT", "64"))
    send_count = int(cfg.get("NODE_SEND_COUNT", "10"))
    send_interval_s = float(cfg.get("NODE_SEND_INTERVAL_S", "3"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((cfg.get("NODE_BIND", "0.0.0.0"), int(cfg.get("NODE_PORT", "5685"))))

    puf = make_puf(puf_seed, puf_bits)
    y_hash = sha256_hex(device_secret)
    crps = []
    for i in range(enroll_crp_count):
        ch = random_challenge_hex(puf_bits)
        resp = puf_response_bit(puf, ch, puf_bits)
        crps.append({"cid": str(i), "challenge": ch, "response": resp})

    enroll = {
        "type": "ENROLL_REQ",
        "device_id": device_id,
        "y_hash": y_hash,
        "crps": crps,
        "ts": now_ts(),
    }
    sock.sendto(to_json_bytes(enroll), (as_host, as_port))
    enroll_ok = recv_until(sock, "ENROLL_OK", timeout=8.0)
    pid = enroll_ok["pid"]
    print(f"[NODE] Enrolled. pid={pid[:12]}...")

    auth = {
        "type": "AUTH_REQ",
        "device_id": device_id,
        "pid": pid,
        "ts": now_ts(),
    }
    sock.sendto(to_json_bytes(auth), (as_host, as_port))

    ch_msg = recv_until(sock, "AUTH_CHALLENGE", timeout=8.0)
    cid = str(ch_msg["cid"])
    challenge = ch_msg["challenge"]
    response = puf_response_bit(puf, challenge, puf_bits)

    proof = {
        "type": "AUTH_PROOF",
        "device_id": device_id,
        "pid": pid,
        "cid": cid,
        "response": response,
        "ts": now_ts(),
    }
    sock.sendto(to_json_bytes(proof), (as_host, as_port))

    auth_ok = recv_until(sock, "AUTH_OK", timeout=8.0)

    pid = auth_ok["pid_new"]
    m_masked = auth_ok["m_masked"]
    mask_key = sha256_hex(f"{y_hash}|mask")
    m_new = xor_hex(m_masked, mask_key[:32])
    session_key = sha256_hex(f"{y_hash}|{response}|{m_new}")
    print(f"[NODE] Authenticated. new pid={pid[:12]}...")

    # Small delay lets GW receive token from AS before data starts.
    time.sleep(1.0)

    for i in range(1, send_count + 1):
        payload = f"sensor_temp=26.{i:02d};sensor_hum=58.{i:02d};ts={now_ts()}"
        nonce = secrets.token_hex(8)
        cipher = encrypt_text(payload, session_key, nonce)
        mac = sha256_hex(f"{session_key}|{cipher}|{i}")

        pkt = {
            "type": "DATA",
            "device_id": device_id,
            "pid": pid,
            "counter": i,
            "nonce": nonce,
            "cipher": cipher,
            "mac": mac,
        }
        sock.sendto(to_json_bytes(pkt), (gw_host, gw_port))
        print(f"[NODE] Sent DATA #{i}")
        time.sleep(send_interval_s)

    print("[NODE] Completed data send loop.")


if __name__ == "__main__":
    main()
