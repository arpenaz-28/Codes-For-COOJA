#!/usr/bin/env python3
"""
Medical Gateway — Zhou et al. scheme (IEEE IoT Journal 2024)
Runs on: PC

Handles:
  PORT_ZHOU_USER_REG (5011)  ← User:  registration
  PORT_ZHOU_SN_REG   (5012)  ← SN:    registration (two-step on same conn)
  PORT_ZHOU_AUTH     (5013)  ← User:  M1 — GW does M2/M3 with SN, replies M4

Outbound:
  PORT_ZHOU_M2 (5014)  → SN: M2 (GW acts as client here, SN replies M3)
"""
import sys, os, threading, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (AS_IP, PORT_ZHOU_USER_REG, PORT_ZHOU_SN_REG,
                    PORT_ZHOU_AUTH, PORT_ZHOU_M2, NODE_GW)

users   = {}   # id_i → {ki, bi, DIDi_curr, DIDi_old, IDi_padded, ...}
sensors = {}   # sn_id → {Cn, Rn, bn, SIDn_curr, SIDn_old, SNn_padded, ...}
users_lock   = threading.Lock()
sensors_lock = threading.Lock()

def h2(x: bytes) -> bytes:
    """64-byte double-hash: H(x||0x00) || H(x||0x01)"""
    return sha256(x + b'\x00') + sha256(x + b'\x01')

def h3(x: bytes) -> bytes:
    """96-byte triple-hash"""
    return sha256(x + b'\x00') + sha256(x + b'\x01') + sha256(x + b'\x02')

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

# ── User Registration ─────────────────────────────────────────────────────────

def handle_user_reg(conn, addr):
    try:
        data = recv_msg(conn)
        # SIDn query: 16 bytes with plain[0]==0xFF
        if len(data) == 16:
            plain = aes_dec_blocks(K_GW_U, data)
            if plain[0] == 0xFF:
                sn_id = plain[1]
                with sensors_lock:
                    sn = sensors.get(sn_id)
                if sn and sn['enrolled']:
                    rep = bytearray(48)
                    rep[0:32] = sn['SIDn_curr']
                    send_msg(conn, aes_enc_blocks(K_GW_U, bytes(rep)))
                else:
                    send_msg(conn, bytes([0xFE]))
                return
        if len(data) != 48:
            return
        plain = aes_dec_blocks(K_GW_U, data)
        id_i = plain[0]
        ki   = bytes(plain[1:33])

        id_padded = bytes([id_i]) + b'\x00' * 31
        bi        = rand_bytes(32)
        DIDi      = xor_bytes(bi, id_padded)

        with users_lock:
            users[id_i] = {
                'ki': ki, 'bi': bi, 'DIDi_curr': DIDi, 'DIDi_old': DIDi,
                'IDi_padded': id_padded, 'did_old_valid': False, 'enrolled': True
            }

        reply = bytearray(48)
        reply[0:32] = DIDi
        send_msg(conn, aes_enc_blocks(K_GW_U, bytes(reply)))
        print(f"[GW-ZHOU] User {id_i} registered | DIDi={DIDi.hex()[:6]}")
    except Exception as e:
        print(f"[GW-ZHOU] user_reg: {e}")
    finally:
        conn.close()

# ── Sensor Registration (two messages on same TCP conn) ──────────────────────

def handle_sn_reg(conn, addr):
    try:
        # Step 1: SN → GW: AES1(K_GW_SN, [SNn, 0×15]) = 16B
        data = recv_msg(conn)
        if len(data) != 16:
            return
        plain = aes_dec_blocks(K_GW_SN, data)
        sn_id = plain[0]

        sn_padded = bytes([sn_id]) + b'\x00' * 31
        bn        = rand_bytes(32)
        SIDn      = xor_bytes(bn, sn_padded)
        Cn        = rand_bytes(1)[0]

        # Reply: AES3(K_GW_SN, [SIDn(32), Cn(1), 0×15]) = 48B
        rep1 = bytearray(48)
        rep1[0:32] = SIDn
        rep1[32]   = Cn
        send_msg(conn, aes_enc_blocks(K_GW_SN, bytes(rep1)))

        # Step 2: SN → GW: AES1(K_GW_SN, [Rn(1), sn_id(1), 0×14]) = 16B
        data = recv_msg(conn)
        if len(data) != 16:
            return
        plain = aes_dec_blocks(K_GW_SN, data)
        Rn     = plain[0]
        sn_chk = plain[1]

        with sensors_lock:
            sensors[sn_id] = {
                'Cn': Cn, 'Rn': Rn, 'bn': bn, 'SIDn_curr': SIDn,
                'SIDn_old': SIDn, 'SNn_padded': sn_padded,
                'sid_old_valid': False, 'enrolled': True, 'SNn': sn_id
            }

        send_msg(conn, b'OK')
        print(f"[GW-ZHOU] Sensor {sn_id} registered | SIDn={SIDn.hex()[:6]} Cn={Cn} Rn={Rn}")
    except Exception as e:
        print(f"[GW-ZHOU] sn_reg: {e}")
    finally:
        conn.close()

# ── Authentication: receive M1, do M2/M3, send M4 ────────────────────────────

def handle_auth(conn, addr):
    try:
        t_start = time.perf_counter()

        # M1: [Ni(32)|α(32)|DIDi(32)|SIDn(32)] = 128 bytes
        data = recv_msg(conn)
        if len(data) != 128:
            print(f"[GW-ZHOU] M1 bad len {len(data)}")
            return
        Ni        = bytes(data[0:32])
        alpha     = bytes(data[32:64])
        recv_DIDi = bytes(data[64:96])
        recv_SIDn = bytes(data[96:128])

        # ── Find user by DIDi ──
        with users_lock:
            u = next((v for v in users.values()
                      if v['DIDi_curr'] == recv_DIDi
                      or (v['did_old_valid'] and v['DIDi_old'] == recv_DIDi)), None)
        if u is None:
            print(f"[GW-ZHOU] M1 FAIL: DIDi {recv_DIDi.hex()[:6]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        # Step 2: bi_new' = Ni XOR H(ki)
        h_ki      = sha256(u['ki'])
        bi_new    = xor_bytes(Ni, h_ki)

        # Step 3: α' = H(bi_new || ki || DIDi || SIDn)
        alpha_in  = bi_new + u['ki'] + recv_DIDi + recv_SIDn
        alpha_p   = sha256(alpha_in)

        if alpha_p != alpha:
            print(f"[GW-ZHOU] M1 FAIL: α mismatch")
            send_msg(conn, bytes([0xFF]))
            return

        print(f"[GW-ZHOU] M1 verified for user {u['IDi_padded'][0]}")

        # ── Find sensor by SIDn ──
        with sensors_lock:
            s = next((v for v in sensors.values()
                      if v['SIDn_curr'] == recv_SIDn
                      or (v['sid_old_valid'] and v['SIDn_old'] == recv_SIDn)), None)
        if s is None:
            print(f"[GW-ZHOU] M1 FAIL: SIDn {recv_SIDn.hex()[:6]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        # Step 6: generate bn_new, SK
        bn_new = rand_bytes(32)
        SK     = rand_bytes(32)

        # Step 7: SIDn_new = SNn_padded XOR bn_new
        SIDn_new = xor_bytes(s['SNn_padded'], bn_new)

        # Step 8: SKn = (SK||SIDn_new) XOR H2(Rn) — 64 bytes
        mask64 = h2(bytes([s['Rn']]))
        SKn    = xor_bytes(SK + SIDn_new, mask64)

        # Step 9: β = H(SK || Rn || SIDn_active || SIDn_new)
        SIDn_active = s['SIDn_old'] if (s['sid_old_valid'] and s['SIDn_old'] == recv_SIDn) else s['SIDn_curr']
        beta_in = SK + bytes([s['Rn']]) + SIDn_active + SIDn_new
        beta    = sha256(beta_in)

        # ── M2 → SN (connect as client) ──
        m2_payload = SKn + beta + bytes([s['Cn']])   # 97 bytes
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_sock:
                s_sock.connect((AS_IP, PORT_ZHOU_M2))
                send_msg(s_sock, m2_payload)
                m3 = recv_msg(s_sock)
        except Exception as e:
            print(f"[GW-ZHOU] M2 send failed: {e}")
            send_msg(conn, bytes([0xFF]))
            return

        if len(m3) != 32:
            print(f"[GW-ZHOU] M3 bad len {len(m3)}")
            send_msg(conn, bytes([0xFF]))
            return

        gamma = bytes(m3)

        # Step 12: γ' = H(SIDn_new || SK)
        gamma_p = sha256(SIDn_new + SK)
        if gamma_p != gamma:
            print(f"[GW-ZHOU] M3 FAIL: γ mismatch")
            send_msg(conn, bytes([0xFF]))
            return

        print(f"[GW-ZHOU] M3 verified (SN authenticated)")

        # Step 14: DIDi_new = IDi_padded XOR bi_new
        DIDi_new = xor_bytes(u['IDi_padded'], bi_new)

        # Step 15: SKi = (SIDn_new || SK || DIDi_new) XOR H3(ki) — 96 bytes
        mask96 = h3(u['ki'])
        SKi    = xor_bytes(SIDn_new + SK + DIDi_new, mask96)

        # Step 16: λ = H(SK || DIDi || ki || DIDi_new || SIDn_new)
        lam_in = SK + recv_DIDi + u['ki'] + DIDi_new + SIDn_new
        lam    = sha256(lam_in)

        # ── M4 → User ──
        m4_payload = SKi + lam   # 128 bytes
        send_msg(conn, m4_payload)

        # ── Rotate pseudonyms ──
        id_i = u['IDi_padded'][0]
        with users_lock:
            users[id_i]['DIDi_old']       = users[id_i]['DIDi_curr']
            users[id_i]['DIDi_curr']      = DIDi_new
            users[id_i]['bi']             = bi_new
            users[id_i]['did_old_valid']  = True

        sn_id = s['SNn']
        with sensors_lock:
            sensors[sn_id]['SIDn_old']       = sensors[sn_id]['SIDn_curr']
            sensors[sn_id]['SIDn_curr']      = SIDn_new
            sensors[sn_id]['bn']             = bn_new
            sensors[sn_id]['sid_old_valid']  = True

        elapsed = (time.perf_counter() - t_start) * 1000
        print(f"[GW-ZHOU] M4 sent | Auth complete in {elapsed:.1f} ms")

    except Exception as e:
        print(f"[GW-ZHOU] auth: {e}")
    finally:
        conn.close()

# ── Listeners ─────────────────────────────────────────────────────────────────

def listener(port, handler, name):
    srv = make_server(port)
    print(f"[GW-ZHOU] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    for port, fn, label in [
        (PORT_ZHOU_USER_REG, handle_user_reg, "user-reg"),
        (PORT_ZHOU_SN_REG,   handle_sn_reg,   "sn-reg"),
        (PORT_ZHOU_AUTH,     handle_auth,      "auth"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()

    print(f"[GW-ZHOU] Zhou scheme gateway (node {NODE_GW}) running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[GW-ZHOU] Stopping.")
