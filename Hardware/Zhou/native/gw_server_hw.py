#!/usr/bin/env python3
"""
gw_server_hw.py — GW Server (Registration Authority) for Zhou scheme hardware simulation.

Runs on the laptop.  Mirrors gw-server.c from Zhou-Scheme/:
  "Security-Enhanced Lightweight and Anonymity-Preserving User Authentication
   Scheme for IoT-Based Healthcare", Zhou et al., IEEE IoT Journal 2024

Handles:
  Phase 1 — Sensor Node Registration  (POST /test/sn_reg, /test/sn_reg1)
  Phase 2 — User Registration         (POST /test/user_reg, /test/get_sid)
  Phase 3 — Authentication pipeline   (POST /test/auth):
      M1 (User→GW_Server) → ACK → M2 (GW_Server→SN) → M3 (SN→GW_Server)
      → M4 (GW_Server→User) + token (GW_Server→GW_Router)

Protocol message types (JSON over UDP):
  SN_REG_REQ  / SN_REG_REP    — Sensor step 1 registration
  SN_REG1_REQ / SN_REG1_REP   — Sensor step 2 registration (PUF response)
  USER_REG_REQ / USER_REG_REP — User registration
  GET_SID_REQ / GET_SID_REP   — User queries sensor pseudonym
  M1_REQ / M1_ACK             — Authentication message 1 (User→GW_Server)
  M2_REQ / M3_REP             — M2 to sensor, M3 from sensor
  M4_PUSH                     — GW_Server → User (key material)
  GW_TOKEN                    — forwarded to GW_Router
"""
import os
import socket
import sys
import time
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_GW_U, K_GW_SN, K_GW_RT,
    aes_ecb_enc, aes_ecb_dec,
    sha256, H2, H3, xor_bytes,
    simulate_puf_response,
    to_json_bytes, from_json_bytes,
    parse_env_file,
)

GW_ID = 1   # GW Server node ID in Zhou paper


def _cfg_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "roles.env")


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    gw_bind      = cfg.get("GW_BIND",       "0.0.0.0")
    gw_srv_port  = int(cfg.get("GW_SERVER_PORT", "5684"))
    gw_rtr_host  = cfg.get("GW_HOST",       "127.0.0.1")
    gw_rtr_port  = int(cfg.get("GW_ROUTER_PORT", "5683"))
    sn_host      = cfg.get("SN_HOST",        "127.0.0.1")
    sn_port      = int(cfg.get("SN_PORT",    "5685"))
    user_port    = int(cfg.get("USER_PORT",  "5686"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((gw_bind, gw_srv_port))
    sock.settimeout(None)   # blocking recv

    gw_rtr_addr = (gw_rtr_host, gw_rtr_port)
    sn_addr     = (sn_host, sn_port)

    print(f"[GW-Server] Listening on {gw_bind}:{gw_srv_port}")
    print(f"[GW-Server] Will forward tokens to GW-Router {gw_rtr_addr}")

    # Per-sensor state keyed by sn_id (int)
    sensors: Dict[int, Dict] = {}
    # Per-user state keyed by user_id (int)
    users: Dict[int, Dict] = {}

    def send(msg: dict, addr: tuple) -> None:
        sock.sendto(to_json_bytes(msg), addr)

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
        except Exception as exc:
            print(f"[GW-Server] recv error: {exc}")
            continue

        try:
            msg = from_json_bytes(raw)
        except Exception:
            continue

        mtype = msg.get("type", "")

        # =====================================================================
        # SENSOR REGISTRATION — Step 1  (sn-node.c → /test/sn_reg)
        #
        # Recv: AES_enc(K_GW_SN, [SNn(1) | pad(15)]) = 16 B
        # Send: AES_enc(K_GW_SN, [SIDn(32) | Cn(1) | pad(15)]) = 48 B
        #
        # GW generates random bn(32), SIDn = bn ⊕ SNn_padded(32), random Cn(1)
        # =====================================================================
        if mtype == "SN_REG_REQ":
            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 16:
                continue
            plain = aes_ecb_dec(K_GW_SN, enc_in)
            sn_id = plain[0]
            if sn_id == 0:
                continue

            bn   = os.urandom(32)
            SIDn = xor_bytes(bn, bytes([sn_id]) + bytes(31))  # SNn_padded: [sn_id, 0,...,0]
            Cn   = os.urandom(1)[0]

            sensors[sn_id] = {
                "sn_id":         sn_id,
                "SNn_padded":    bytes([sn_id]) + bytes(31),
                "bn":            bn,
                "SIDn_curr":     SIDn,
                "SIDn_old":      bytes(32),
                "sid_old_valid": False,
                "Cn":            Cn,
                "Rn":            None,
                "enrolled":      False,
                "reg_step":      1,
            }

            rep = bytearray(48)
            rep[0:32] = SIDn
            rep[32]   = Cn
            enc_rep = aes_ecb_enc(K_GW_SN, bytes(rep))
            send({"type": "SN_REG_REP", "enc": enc_rep.hex()}, addr)
            print(f"[GW-Server] SN {sn_id}: reg step 1  SIDn={SIDn.hex()[:8]}...  Cn={Cn}")

        # =====================================================================
        # SENSOR REGISTRATION — Step 2  (sn-node.c → /test/sn_reg1)
        #
        # Recv: AES_enc(K_GW_SN, [Rn(1) | sn_id(1) | pad(14)]) = 16 B
        # Send: SN_REG1_REP  (empty ack)
        # =====================================================================
        elif mtype == "SN_REG1_REQ":
            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 16:
                continue
            plain = aes_ecb_dec(K_GW_SN, enc_in)
            Rn    = plain[0]
            sn_id = plain[1]
            if sn_id not in sensors or sensors[sn_id]["reg_step"] != 1:
                continue

            sensors[sn_id]["Rn"]       = Rn
            sensors[sn_id]["enrolled"] = True
            send({"type": "SN_REG1_REP"}, addr)
            print(f"[GW-Server] SN {sn_id}: registration complete  Cn={sensors[sn_id]['Cn']}  Rn={Rn}")

        # =====================================================================
        # USER REGISTRATION  (user-node.c → /test/user_reg)
        #
        # Recv: AES_enc(K_GW_U, [IDi(1) | ki(32) | pad(15)]) = 48 B
        # Send: AES_enc(K_GW_U, [DIDi(32) | pad(16)]) = 48 B
        #
        # GW generates random bi(32), DIDi = bi ⊕ IDi_padded
        # =====================================================================
        elif mtype == "USER_REG_REQ":
            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 48:
                continue
            plain = aes_ecb_dec(K_GW_U, enc_in)
            id_i  = plain[0]
            ki    = bytes(plain[1:33])
            if id_i == 0:
                continue

            IDi_padded = bytes([id_i]) + bytes(31)
            bi         = os.urandom(32)
            DIDi       = xor_bytes(bi, IDi_padded)

            users[id_i] = {
                "id_i":          id_i,
                "IDi_padded":    IDi_padded,
                "ki":            ki,
                "bi":            bi,
                "DIDi_curr":     DIDi,
                "DIDi_old":      bytes(32),
                "did_old_valid": False,
                "enrolled":      True,
            }

            rep = bytearray(48)
            rep[0:32] = DIDi
            enc_rep   = aes_ecb_enc(K_GW_U, bytes(rep))
            send({"type": "USER_REG_REP", "enc": enc_rep.hex()}, addr)
            print(f"[GW-Server] User {id_i}: registered  DIDi={DIDi.hex()[:8]}...")

        # =====================================================================
        # GET SENSOR SIDn  (user-node.c → /test/get_sid)
        #
        # Recv: AES_enc(K_GW_U, [sn_id(1) | pad(15)]) = 16 B
        # Send: AES_enc(K_GW_U, [SIDn(32) | pad(16)]) = 48 B
        # =====================================================================
        elif mtype == "GET_SID_REQ":
            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 16:
                continue
            plain = aes_ecb_dec(K_GW_U, enc_in)
            sn_id = plain[0]

            if sn_id not in sensors or not sensors[sn_id]["enrolled"]:
                send({"type": "GET_SID_REP", "err": "not_enrolled"}, addr)
                print(f"[GW-Server] get_sid: SN {sn_id} not enrolled yet")
                continue

            SIDn_cur = sensors[sn_id]["SIDn_curr"]
            rep = bytearray(48)
            rep[0:32] = SIDn_cur
            enc_rep   = aes_ecb_enc(K_GW_U, bytes(rep))
            send({"type": "GET_SID_REP", "enc": enc_rep.hex()}, addr)
            print(f"[GW-Server] get_sid: returned SIDn for SN {sn_id}")

        # =====================================================================
        # AUTHENTICATION M1  (user-node.c → /test/auth)
        #
        # Recv M1: {Ni(32) | α(32) | DIDi(32) | SIDn(32)} = 128 B
        #
        # Steps (mirrors gw-server.c res_auth_handler):
        #   1. Find user by DIDi
        #   2. bi_new' = Ni ⊕ H(ki)                   [hash 1]
        #   3. α' = H(bi_new'||ki||DIDi||SIDn)          [hash 2]
        #   4. Verify α' == α
        #   5. Find sensor by SIDn
        #   6. Generate bn_new(32), SK(32)
        #   7. SIDn_new = SNn_padded ⊕ bn_new
        #   8. SKn = (SK||SIDn_new) ⊕ H2(Rn)            [hash 3]
        #   9. β = H(SK||Rn||SIDn||SIDn_new)             [hash 4]
        #  10. ACK user (interim)
        #  11. Send M2 to SN, wait M3
        #  12. γ' = H(SIDn_new||SK)                      [hash 5]
        #  13. Verify γ' == γ
        #  14. DIDi_new = IDi_padded ⊕ bi_new'
        #  15. SKi = (SIDn_new||SK||DIDi_new) ⊕ H3(ki)   [hash 6/7]
        #  16. λ = H(SK||DIDi||ki||DIDi_new||SIDn_new)   [hash 7]
        #  17. Send M4 to user
        #  18. Forward token to GW_Router
        #  19. Rotate pseudonyms
        # =====================================================================
        elif mtype == "M1_REQ":
            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 128:
                print(f"[GW-Server] M1 too short: {len(payload)} B")
                continue

            Ni        = bytes(payload[0:32])
            alpha     = bytes(payload[32:64])
            recv_DIDi = bytes(payload[64:96])
            recv_SIDn = bytes(payload[96:128])

            # Step 1: Find user by DIDi
            uidx: Optional[int] = None
            use_old_u = False
            for uid, u in users.items():
                if not u["enrolled"]:
                    continue
                if u["DIDi_curr"] == recv_DIDi:
                    uidx = uid; use_old_u = False; break
                if u["did_old_valid"] and u["DIDi_old"] == recv_DIDi:
                    uidx = uid; use_old_u = True; break

            if uidx is None:
                print("[GW-Server] M1 rejected — DIDi not found")
                continue

            u  = users[uidx]
            ki = u["ki"]

            # Step 2: bi_new' = Ni ⊕ H(ki)
            h_ki     = sha256(ki)               # hash 1
            bi_new   = xor_bytes(Ni, h_ki)

            # Step 3: α' = H(bi_new'||ki||DIDi||SIDn)
            alpha_in = bi_new + ki + recv_DIDi + recv_SIDn   # 128 B
            alpha_p  = sha256(alpha_in)         # hash 2

            # Step 4: Verify
            if alpha_p != alpha:
                print(f"[GW-Server] M1 auth failed — α mismatch for user {uidx}")
                continue
            print(f"[GW-Server] User {uidx} M1 verified")

            # Step 5: Find sensor by SIDn
            sidx: Optional[int] = None
            use_old_s = False
            for sn_id, s in sensors.items():
                if not s["enrolled"]:
                    continue
                if s["SIDn_curr"] == recv_SIDn:
                    sidx = sn_id; use_old_s = False; break
                if s["sid_old_valid"] and s["SIDn_old"] == recv_SIDn:
                    sidx = sn_id; use_old_s = True; break

            if sidx is None:
                print("[GW-Server] M1 rejected — SIDn not found")
                continue

            s = sensors[sidx]

            # Step 6: Generate bn_new(32), SK(32)
            bn_new = os.urandom(32)
            SK     = os.urandom(32)

            # Step 7: SIDn_new = SNn_padded ⊕ bn_new
            SIDn_new = xor_bytes(s["SNn_padded"], bn_new)

            # Step 8: SKn = (SK||SIDn_new) ⊕ H2(Rn)  [64 B]
            mask64 = H2(bytes([s["Rn"]]))       # hash 3 (double-hash on 1-byte Rn)
            SKn    = xor_bytes(SK + SIDn_new, mask64)
            assert len(SKn) == 64

            # Step 9: β = H(SK||Rn||SIDn||SIDn_new)  — 97 B input
            SIDn_active = s["SIDn_old"] if use_old_s else s["SIDn_curr"]
            beta_in = SK + bytes([s["Rn"]]) + SIDn_active + SIDn_new  # 32+1+32+32 = 97 B
            beta    = sha256(beta_in)            # hash 4

            # Step 10: ACK the user (addr from incoming M1)
            user_addr: Tuple[str, int] = addr
            send({"type": "M1_ACK", "ack": "ac"}, user_addr)
            print(f"[GW-Server] M1 ACK sent to user {uidx}")

            # Step 11: Send M2 to SN  {SKn(64)|β(32)|Cn(1)} = 97 B
            m2_payload = SKn + beta + bytes([s["Cn"]])
            assert len(m2_payload) == 97
            send({"type": "M2_REQ", "payload": m2_payload.hex()}, sn_addr)
            print(f"[GW-Server] M2 sent to SN {sidx}")

            # Wait for M3 from SN (γ = 32 B)
            sock.settimeout(30.0)
            gamma: Optional[bytes] = None
            try:
                while True:
                    raw2, addr2 = sock.recvfrom(8192)
                    try:
                        msg2 = from_json_bytes(raw2)
                    except Exception:
                        continue
                    if msg2.get("type") == "M3_REP":
                        pl = bytes.fromhex(msg2.get("payload", ""))
                        if len(pl) >= 32:
                            gamma = bytes(pl[0:32])
                        break
                    # Other messages while waiting for M3 — re-queue would be ideal;
                    # for single-session simulation, just log and skip.
                    print(f"[GW-Server] (ignored {msg2.get('type')} while waiting M3)")
            except socket.timeout:
                print("[GW-Server] Timeout waiting for M3 — aborting auth")
                sock.settimeout(None)
                continue
            sock.settimeout(None)

            if gamma is None:
                print("[GW-Server] M3 payload invalid — aborting")
                continue
            print(f"[GW-Server] M3 received from SN {sidx}")

            # Step 12: γ' = H(SIDn_new||SK)
            gamma_in = SIDn_new + SK  # 64 B
            gamma_p  = sha256(gamma_in)  # hash 5

            # Step 13: Verify γ' == γ
            if gamma_p != gamma:
                print(f"[GW-Server] Auth failed — γ mismatch from SN {sidx}")
                continue
            print(f"[GW-Server] M3 verified from SN {sidx}")

            # Step 14: DIDi_new = IDi_padded ⊕ bi_new'
            DIDi_new = xor_bytes(u["IDi_padded"], bi_new)

            # Step 15: SKi = (SIDn_new||SK||DIDi_new) ⊕ H3(ki)  [96 B]
            mask96  = H3(ki)           # hash 6 (triple-hash on ki, 3 calls in C)
            ski_plain = SIDn_new + SK + DIDi_new  # 96 B
            SKi       = xor_bytes(ski_plain, mask96)
            assert len(SKi) == 96

            # Step 16: λ = H(SK||DIDi||ki||DIDi_new||SIDn_new)  — 160 B input
            lambda_in = SK + recv_DIDi + ki + DIDi_new + SIDn_new  # 32+32+32+32+32 = 160 B
            lam       = sha256(lambda_in)   # hash 7

            # Step 17: Send M4 to user  {SKi(96)|λ(32)} = 128 B
            m4_payload = SKi + lam
            assert len(m4_payload) == 128
            send({"type": "M4_PUSH", "payload": m4_payload.hex()}, user_addr)
            print(f"[GW-Server] M4 sent to user {uidx}")

            # Step 18: Forward token to GW_Router
            # Token: DIDi_new(32) | GW_ID(1) | enc_tok(48) = 81 B
            ts_auth = int(time.time()) & 0xFF
            enc_tok_plain = bytearray(48)
            enc_tok_plain[0]     = uidx           # ID_user
            enc_tok_plain[1]     = GW_ID
            enc_tok_plain[2]     = ts_auth
            enc_tok_plain[16:32] = SK[0:16]
            enc_tok_plain[32:48] = SK[16:32]
            enc_tok = aes_ecb_enc(K_GW_RT, bytes(enc_tok_plain))
            token_pkt = DIDi_new + bytes([GW_ID]) + enc_tok  # 81 B
            assert len(token_pkt) == 81
            send({"type": "GW_TOKEN", "payload": token_pkt.hex()}, gw_rtr_addr)
            print(f"[GW-Server] Token forwarded to GW_Router for user {uidx}")

            # Step 19: Rotate pseudonyms
            s["SIDn_old"]       = s["SIDn_curr"]
            s["SIDn_curr"]      = SIDn_new
            s["sid_old_valid"]  = True
            u["DIDi_old"]       = u["DIDi_curr"]
            u["DIDi_curr"]      = DIDi_new
            u["did_old_valid"]  = True
            print(f"[GW-Server] Pseudonyms rotated for user {uidx} / SN {sidx}")

        # else: ignore unknown types


if __name__ == "__main__":
    main()
