#!/usr/bin/env python3
"""
as_hw.py — Authentication Server for Revised-Anonymity hardware simulation.

Runs on RPi #1 (AS, node ID 2).  Mirrors the two-round protocol from
Revised-Anonymity/as-node.c:

  /test/reg     (REG0)   Enrollment round 0 — issue c_d + m_curr
  /test/reg1    (REG1)   Enrollment round 1 — receive Y_dH, R_d, c_as_d
  /test/auth    (AUTH)   Round 1: verify membership, store Phase-3 material, reply ACK+ts_2
  /test/keyex   (KEYEX)  Round 2: send m_H, rotate PID+m, forward GW token

GW token forwarded after KEYEX:
  new_PID(32) | ID_AS(1) | enc_tok(48)  =  81 B
  enc_tok = AES_enc(K_GW_AS, [ID_d|ID_AS|ts_auth|pad(13)] | K_GW_D[0:16] | K_GW_D[16:32])
"""
import os
import socket
import sys
import time
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_AS_D, K_GW_AS,
    aes_ecb_enc, aes_ecb_dec,
    sha256, xor_bytes,
    simulate_puf_response, generate_helper, regenerate_response,
    seq_ts_fresh, clock_ts_fresh,
    to_json_bytes, from_json_bytes,
    parse_env_file,
)


def _cfg_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "roles.env")


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    as_bind  = cfg.get("AS_BIND", "0.0.0.0")
    as_port  = int(cfg.get("AS_PORT", "5684"))
    gw_host  = cfg.get("GW_HOST", "127.0.0.1")
    gw_port  = int(cfg.get("GW_PORT", "5683"))
    as_id    = int(cfg.get("AS_NODE_ID", "2"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((as_bind, as_port))
    sock.settimeout(None)   # blocking recv

    print(f"[AS {as_id}] Listening on {as_bind}:{as_port}")

    # Membership AND accumulator — init to 0xFF...FF (mirrors memset T_acc,0xFF)
    T_acc = bytearray(b'\xff' * 32)

    # ts_2 session counter (uint8)
    session_ctr: int = 0

    # Per-client enrolled state  { device_id (int) → dict }
    clients: Dict[int, Dict] = {}

    # Pending key-exchange table  { device_id (int) → dict }
    pending: Dict[int, Dict] = {}

    gw_addr = (gw_host, gw_port)

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
        except Exception as exc:
            print(f"[AS {as_id}] recv error: {exc}")
            continue

        try:
            msg = from_json_bytes(raw)
        except Exception:
            continue

        mtype = msg.get("type", "")

        # =====================================================================
        # REG0 — Enrollment Round 0
        #   Recv: AES_enc(K_AS_D, id_d(1)|pad(15))               = 16 B
        #   Send: AES_enc(K_AS_D, c_d(1)|m_curr(32)|pad(15))     = 48 B
        # =====================================================================
        if mtype == "REG0_REQ":
            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 16:
                continue
            plain = aes_ecb_dec(K_AS_D, enc_in)
            id_d  = plain[0]
            if id_d == 0:
                continue

            c_d    = int.from_bytes(os.urandom(1), "big")
            m_curr = os.urandom(32)

            clients[id_d] = {
                "id_d":          id_d,
                "c_d":           c_d,
                "m_curr":        bytearray(m_curr),
                "m_old":         bytearray(m_curr),
                "PID_curr":      None,          # bytes(32), set in REG1
                "PID_old":       bytes(32),
                "pid_old_valid": False,
                "last_ts1":      0,
                "enrolled":      False,
                # AS-side PUF state (filled in REG1)
                "c_as_d":        0,
                "h_as_d":        0,             # = R_as  (helper = response)
                "phi_as_d":      0,             # = R_as XOR R_d
            }
            pending.pop(id_d, None)

            # Reply: c_d(1) | m_curr(32) | pad(15) = 48 B
            rep = bytearray(48)
            rep[0]    = c_d
            rep[1:33] = m_curr
            enc_rep   = aes_ecb_enc(K_AS_D, bytes(rep))
            sock.sendto(to_json_bytes({"type": "REG0_REP", "enc": enc_rep.hex()}), addr)
            print(f"[AS {as_id}] Reg-0 for device {id_d}  (c_d={c_d})")

        # =====================================================================
        # REG1 — Enrollment Round 1
        #   Recv: AES_enc(K_AS_D, id_d(1)|Y_dH(32)|R_d(1)|c_as_d(1)|pad(13)) = 48 B
        #   Send: REG1_REP  (empty ack)
        # =====================================================================
        elif mtype == "REG1_REQ":
            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 48:
                continue
            plain  = aes_ecb_dec(K_AS_D, enc_in)
            id_d   = plain[0]
            if id_d not in clients:
                continue

            # Parse layout: id_d(1)|Y_dH(32)|R_d(1)|c_as_d(1)|pad(13)
            Y_dH   = bytes(plain[1:33])
            R_d    = plain[33]
            c_as_d = plain[34]

            cl = clients[id_d]
            cl["c_as_d"] = c_as_d

            # Update group membership accumulator: T_acc &= Y_dH
            for i in range(32):
                T_acc[i] &= Y_dH[i]

            # AS-side PUF response and helper
            R_as = simulate_puf_response(as_id, c_as_d)
            h_as_d, _ = generate_helper(R_as)
            cl["h_as_d"]   = h_as_d           # = R_as
            cl["phi_as_d"] = R_as ^ R_d        # stored for auth recovery

            # Compute initial PID = H(id_d || m_curr)
            cl["PID_curr"] = sha256(bytes([id_d]) + bytes(cl["m_curr"]))
            cl["PID_old"]  = bytes(32)
            cl["pid_old_valid"] = False
            cl["enrolled"] = True

            sock.sendto(to_json_bytes({"type": "REG1_REP"}), addr)
            print(f"[AS {as_id}] Reg-1 complete for device {id_d}")

        # =====================================================================
        # AUTH — Round 1: Authentication
        #   Recv: PID(32)|y_asd(32)|ts_1(1) = 65 B
        #   Send: ACK(1)|ts_2(1)            =  2 B  (no key material yet)
        #
        #   Computes all Phase-3 material (m_new, m_H, K_GW_D, enc_token)
        #   and stores in pending[device_id].  PID + m rotation deferred to KEYEX.
        # =====================================================================
        elif mtype == "AUTH_REQ":
            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 65:
                print(f"[AS {as_id}] AUTH_REQ too short: {len(payload)} B")
                continue
            recv_PID = bytes(payload[0:32])
            y_asd    = bytes(payload[32:64])
            ts_1     = payload[64]

            # Find client by PID (current or old for desync recovery)
            found:   Optional[int] = None
            use_old: bool          = False
            for did, cl in clients.items():
                if not cl["enrolled"]:
                    continue
                if cl["PID_curr"] == recv_PID:
                    found = did; use_old = False; break
                if cl["pid_old_valid"] and cl["PID_old"] == recv_PID:
                    found = did; use_old = True;  break

            if found is None:
                print(f"[AS {as_id}] AUTH failed — PID not found")
                continue

            if use_old:
                print(f"[AS {as_id}] Desync recovery for device {found} (matched PID_old)")

            cl       = clients[found]
            m_active = bytes(cl["m_old"] if use_old else cl["m_curr"])

            # Freshness check on ts_1
            if use_old:
                diff = (ts_1 - cl["last_ts1"] + 256) % 256
                if diff > 200:
                    print(f"[AS {as_id}] Bad ts_1 (desync) for device {found}")
                    continue
            else:
                if not seq_ts_fresh(ts_1, cl["last_ts1"]):
                    print(f"[AS {as_id}] Stale ts_1 for device {found}")
                    continue

            # Reconstruct R_d from stored phi_as_d and AS-side PUF helper
            R_as = regenerate_response(cl["c_as_d"], cl["h_as_d"])  # = h_as_d = R_as
            R_d  = cl["phi_as_d"] ^ R_as

            # Unmask Y_dH from y_asd
            # mask = H(R_d(1) | m_active(32) | recv_PID(32) | ts_1(1)) = 66 B
            mask_in = bytes([R_d]) + m_active + recv_PID + bytes([ts_1])
            assert len(mask_in) == 66
            mask = sha256(mask_in)
            Y_dH = xor_bytes(y_asd, mask)

            # Membership test: T_acc & Y_dH == T_acc
            T_new = bytes(T_acc[i] & Y_dH[i] for i in range(32))
            if T_new != bytes(T_acc):
                print(f"[AS {as_id}] Membership test failed for device {found}")
                continue

            cl["last_ts1"] = ts_1
            print(f"[AS {as_id}] Device {found} authenticated (Round 1)")

            # ------------------------------------------------------------------
            # Compute all Phase-3 material — stored in pending, NOT sent yet
            # ------------------------------------------------------------------

            # m_new = H(nonce)
            n1    = os.urandom(32)
            m_new = sha256(n1)

            # ts_2 = sequential counter (uint8)
            session_ctr = (session_ctr + 1) & 0xFF
            ts_2 = session_ctr

            # mh_mask = H(Y_dH(32)|m_active(32)|R_d(1)|id_as(1)|recv_PID(32)|ts_2(1)) = 99 B
            mh_in = Y_dH + m_active + bytes([R_d, as_id]) + recv_PID + bytes([ts_2])
            assert len(mh_in) == 99
            mh_mask = sha256(mh_in)
            m_H     = xor_bytes(m_new, mh_mask)

            # K_GW_D = H(R_d(1) | m_new(32)) = 33 B
            K_GW_D = sha256(bytes([R_d]) + m_new)

            # new_PID = H(id_d(1) | m_new(32))
            new_PID = sha256(bytes([found]) + m_new)

            # enc_token: 3 AES-ECB blocks with K_GW_AS
            # Block 0 (bytes  0-15): ID_d(1) | ID_AS(1) | ts_auth(1) | pad(13)
            # Block 1 (bytes 16-31): K_GW_D[0:16]
            # Block 2 (bytes 32-47): K_GW_D[16:32]
            ts_auth = int(time.time()) & 0xFF
            enc_tok_plain = bytearray(48)
            enc_tok_plain[0]     = found    # ID_d
            enc_tok_plain[1]     = as_id    # ID_AS
            enc_tok_plain[2]     = ts_auth
            enc_tok_plain[16:32] = K_GW_D[0:16]
            enc_tok_plain[32:48] = K_GW_D[16:32]
            enc_tok = aes_ecb_enc(K_GW_AS, bytes(enc_tok_plain))

            # Store in pending (includes m_new — the critical fix from C source)
            pending[found] = {
                "valid":    True,
                "device_id": found,
                "ts_2":     ts_2,
                "auth_PID": recv_PID,
                "m_new":    m_new,         # FIX: stored so KEYEX can rotate m_curr
                "m_H":      m_H,
                "new_PID":  new_PID,
                "enc_tok":  enc_tok,
            }

            # Reply: ACK(1) | ts_2(1)  — key material withheld until KEYEX
            reply = {"type": "AUTH_REP", "ack": "ac", "ts2": ts_2}
            sock.sendto(to_json_bytes(reply), addr)
            print(f"[AS {as_id}] Round 1 reply to device {found}  ts_2={ts_2}  pending keyex")

        # =====================================================================
        # KEYEX — Round 2: Key Exchange
        #   Recv: PID(32) | ts_2(1)  = 33 B
        #   Send: m_H(32)            = 32 B
        #
        #   Also: rotate PID + m_curr, forward enc_token to GW.
        # =====================================================================
        elif mtype == "KEYEX_REQ":
            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 33:
                print(f"[AS {as_id}] KEYEX_REQ too short: {len(payload)} B")
                continue
            recv_PID = bytes(payload[0:32])
            recv_ts2 = payload[32]

            # Find pending entry by matching auth_PID and ts_2
            found: Optional[int] = None
            for did, pe in pending.items():
                if pe.get("valid") and pe["auth_PID"] == recv_PID and pe["ts_2"] == recv_ts2:
                    found = did
                    break

            if found is None:
                print(f"[AS {as_id}] KEYEX failed — no pending entry for given PID/ts_2")
                continue

            pe = pending[found]
            cl = clients[found]

            # Reply: m_H(32)
            sock.sendto(to_json_bytes({"type": "KEYEX_REP", "m_H": pe["m_H"].hex()}), addr)
            print(f"[AS {as_id}] Round 2 reply to device {found}  Forwarding GW token")

            # PID rotation (deferred from auth handler)
            cl["PID_old"]       = cl["PID_curr"]
            cl["PID_curr"]      = pe["new_PID"]
            cl["pid_old_valid"] = True

            # m rotation (FIX: was missing in earlier scheme)
            cl["m_old"]  = bytearray(cl["m_curr"])
            cl["m_curr"] = bytearray(pe["m_new"])

            # Forward GW token: new_PID(32) | ID_AS(1) | enc_tok(48) = 81 B
            gw_pkt = pe["new_PID"] + bytes([as_id]) + pe["enc_tok"]
            assert len(gw_pkt) == 81
            sock.sendto(to_json_bytes({"type": "GW_TOKEN", "payload": gw_pkt.hex()}), gw_addr)
            print(f"[AS {as_id}] GW token forwarded for device {found}")

            # Clear pending slot
            pe["valid"] = False

        # else: ignore unknown message types


if __name__ == "__main__":
    main()
