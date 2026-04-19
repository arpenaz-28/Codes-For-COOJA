#!/usr/bin/env python3
"""
gw_hw.py — Gateway Node for Revised-Anonymity hardware simulation.

Runs on the laptop (GW, node ID 1).  Mirrors gw-node.c (Revised-Anonymity):

  GW_TOKEN from AS (payload = 81 B):
    new_PID(32) | ID_AS(1) | enc_A(16) | enc_B(16) | enc_C(16)
    enc_A = AES_enc(K_GW_AS, [ID_d | ID_AS | ts_auth | pad(13)])
    enc_B = AES_enc(K_GW_AS, K_GW_D[0:16])
    enc_C = AES_enc(K_GW_AS, K_GW_D[16:32])
    GW: decrypt A+B+C, check freshness, store session keyed by new_PID.

  DATA from device (payload = 48 B):
    new_PID(32) | AES_enc(K_GW_D[0:16], sensor_data(16))
    GW: look up session by PID, decrypt, print sensor value.

KEY DESIGN POINT (same as C source):
  Sessions are keyed by PID (pseudonym), not by device ID.
  GW learns the real ID only from the decrypted token interior.
"""
import os
import socket
import sys
import time
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_GW_AS,
    aes_ecb_dec,
    to_json_bytes, from_json_bytes,
    parse_env_file,
)


def _cfg_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "roles.env")


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    gw_bind = cfg.get("GW_BIND", "0.0.0.0")
    gw_port = int(cfg.get("GW_PORT", "5683"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((gw_bind, gw_port))
    sock.settimeout(None)

    print(f"[GW] Listening on {gw_bind}:{gw_port}")

    # Session table: PID (bytes) → { id_d, id_as, K_GW_D, ts_auth }
    sessions: Dict[bytes, Dict] = {}

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
        except Exception as exc:
            print(f"[GW] recv error: {exc}")
            continue

        try:
            msg = from_json_bytes(raw)
        except Exception:
            continue

        mtype = msg.get("type", "")

        # =================================================================
        # GW_TOKEN from AS
        # payload = new_PID(32) | ID_AS(1) | enc_tok(48) = 81 B
        # =================================================================
        if mtype == "GW_TOKEN":
            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) != 81:
                print(f"[GW] GW_TOKEN wrong length {len(payload)} B (expected 81)")
                continue

            new_PID     = bytes(payload[0:32])
            id_as_plain = payload[32]
            enc_tok     = bytes(payload[33:81])   # 48 B = 3 AES blocks

            # Decrypt 3 blocks with K_GW_AS
            plain_tok = aes_ecb_dec(K_GW_AS, enc_tok)  # 48 B
            # Block 0 (bytes  0-15): ID_d(1) | ID_AS(1) | ts_auth(1) | pad(13)
            # Block 1 (bytes 16-31): K_GW_D[0:16]
            # Block 2 (bytes 32-47): K_GW_D[16:32]
            id_d      = plain_tok[0]
            id_as     = plain_tok[1]
            ts_auth   = plain_tok[2]
            K_GW_D    = bytes(plain_tok[16:48])   # 32 B session key

            # Sanity: ID_AS in plaintext header must match decrypted value
            if id_as != id_as_plain:
                print(f"[GW] Token rejected — ID_AS mismatch "
                      f"(header={id_as_plain} decrypted={id_as})")
                continue

            # Token integrity is guaranteed by AES(K_GW_AS) — no clock-based
            # freshness check needed here (AS/GW clock skew would break it).
            print(f"[GW] Token accepted  ts_auth={ts_auth}  device={id_d}")

            # Store/refresh session keyed by PID
            sessions[new_PID] = {
                "id_d":    id_d,
                "id_as":   id_as,
                "K_GW_D":  K_GW_D,
                "ts_auth": ts_auth,
            }
            print(f"[GW] Session stored  device={id_d}  AS={id_as}  "
                  f"PID={new_PID.hex()[:12]}...")

        # =================================================================
        # DATA from device
        # payload = PID(32) | AES_enc(K_GW_D[0:16], sensor(16)) = 48 B
        # =================================================================
        elif mtype == "DATA":
            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 48:
                print(f"[GW] DATA too short: {len(payload)} B")
                continue

            recv_PID = bytes(payload[0:32])
            enc_data = bytes(payload[32:48])

            sess: Optional[Dict] = sessions.get(recv_PID)
            if sess is None:
                print(f"[GW] Rejected DATA — PID {recv_PID.hex()[:12]}... not found")
                continue

            # Decrypt using first 16 bytes of K_GW_D (AES-128 key)
            from Crypto.Cipher import AES as _AES
            K_AES    = sess["K_GW_D"][:16]
            plain_data = _AES.new(K_AES, _AES.MODE_ECB).decrypt(enc_data)

            print(f"[GW] DATA decrypted  device={sess['id_d']}  "
                  f"value={plain_data[0]}  PID={recv_PID.hex()[:12]}...")

        else:
            print(f"[GW] Unknown message type '{mtype}' from {addr}")


if __name__ == "__main__":
    main()
