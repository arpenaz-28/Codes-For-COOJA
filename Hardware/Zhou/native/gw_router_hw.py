#!/usr/bin/env python3
"""
gw_router_hw.py — GW Router for Zhou scheme hardware simulation.

Runs on the laptop (same machine as gw_server_hw.py, different port).
Mirrors gw-node.c from Zhou-Scheme/.

Responsibilities:
  1. Receive GW_TOKEN from GW_Server → decrypt → store session keyed by DIDi_new
  2. Receive DATA from User → look up session by DIDi → decrypt sensor data → log

Token payload (81 B):
  DIDi_new(32) | GW_ID(1) | enc_tok(48)
  enc_tok = AES_enc(K_GW_RT, [user_id(1)|gw_id(1)|ts(1)|pad(13)|SK[0:16]|SK[16:32]])

DATA payload (48 B):
  DIDi(32) | AES_enc(SK[0:16], sensor(16))
"""
import os
import socket
import sys
import time
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_GW_RT,
    aes_ecb_dec,
    to_json_bytes, from_json_bytes,
    parse_env_file,
)


def _cfg_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "roles.env")


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    gw_bind      = cfg.get("GW_BIND",       "0.0.0.0")
    gw_rtr_port  = int(cfg.get("GW_ROUTER_PORT", "5683"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((gw_bind, gw_rtr_port))
    sock.settimeout(None)

    print(f"[GW-Router] Listening on {gw_bind}:{gw_rtr_port}")

    # Session table: DIDi_new (bytes) → { user_id, gw_id, SK, ts }
    sessions: Dict[bytes, Dict] = {}

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
        except Exception as exc:
            print(f"[GW-Router] recv error: {exc}")
            continue

        try:
            msg = from_json_bytes(raw)
        except Exception:
            continue

        mtype = msg.get("type", "")

        # =====================================================================
        # GW_TOKEN from GW_Server
        # payload = DIDi_new(32) | GW_ID(1) | enc_tok(48) = 81 B
        # =====================================================================
        if mtype == "GW_TOKEN":
            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) != 81:
                print(f"[GW-Router] GW_TOKEN wrong length {len(payload)} B (expected 81)")
                continue

            DIDi_new    = bytes(payload[0:32])
            gw_id_plain = payload[32]
            enc_tok     = bytes(payload[33:81])   # 48 B = 3 AES-ECB blocks

            # Decrypt token with K_GW_RT
            plain_tok = aes_ecb_dec(K_GW_RT, enc_tok)
            # Layout: [user_id(1)|gw_id(1)|ts(1)|pad(13)|SK[0:16]|SK[16:32]]
            user_id = plain_tok[0]
            gw_id   = plain_tok[1]
            ts      = plain_tok[2]
            SK      = bytes(plain_tok[16:48])   # 32-byte session key

            # Sanity check: GW_ID in plain header vs decrypted
            if gw_id != gw_id_plain:
                print(f"[GW-Router] Token rejected — GW_ID mismatch "
                      f"(header={gw_id_plain} decrypted={gw_id})")
                continue

            sessions[DIDi_new] = {
                "user_id": user_id,
                "gw_id":   gw_id,
                "SK":      SK,
                "ts":      ts,
            }
            print(f"[GW-Router] Token accepted  user={user_id}  DIDi={DIDi_new.hex()[:8]}...  "
                  f"SK={SK.hex()[:8]}...")

        # =====================================================================
        # DATA from User
        # payload = DIDi(32) | AES_enc(SK[0:16], sensor(16)) = 48 B
        # =====================================================================
        elif mtype == "DATA":
            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 48:
                print(f"[GW-Router] DATA too short: {len(payload)} B")
                continue

            recv_DIDi = bytes(payload[0:32])
            enc_data  = bytes(payload[32:48])

            sess: Optional[Dict] = sessions.get(recv_DIDi)
            if sess is None:
                print(f"[GW-Router] Rejected DATA — DIDi {recv_DIDi.hex()[:8]}... not found")
                continue

            # Decrypt using first 16 bytes of SK as AES-128 key
            from Crypto.Cipher import AES as _AES
            K_AES      = sess["SK"][:16]
            plain_data = _AES.new(K_AES, _AES.MODE_ECB).decrypt(enc_data)

            print(f"[GW-Router] DATA decrypted  user={sess['user_id']}  "
                  f"sensor_value={plain_data[0]}  DIDi={recv_DIDi.hex()[:8]}...")

        else:
            print(f"[GW-Router] Unknown message type '{mtype}' from {addr}")


if __name__ == "__main__":
    main()
