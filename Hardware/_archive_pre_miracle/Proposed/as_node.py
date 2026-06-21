#!/usr/bin/env python3
"""
Authentication Server — Proposed Scheme (Revised Anonymity)
Runs on: RPi 1 (192.168.1.113)

Listens on:
  PORT_AS_ENROLL (5004)  ← Device: Enrollment (REG0 + REG1, two TCP exchanges)
  PORT_AS_AUTH   (5005)  ← Device: Auth+KeyEx request

After auth, pushes 81-byte token to GW on PORT_GW_TOKEN (5001).
"""
import sys, os, threading, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (GW_IP, PORT_GW_TOKEN, PORT_AS_ENROLL, PORT_AS_AUTH,
                    NODE_AS, NODE_GW)

T_acc   = bytearray([0xFF] * 32)       # AND-accumulator
clients = {}                           # id_d → client_state dict
clients_lock = threading.Lock()
session_ctr  = 0

def make_client():
    return {
        'enrolled': False,
        'c_d': 0, 'c_as_d': 0, 'phi_as_d': 0,
        'PID_curr': b'\x00'*32, 'PID_old': b'\x00'*32,
        'm_curr':   b'\x00'*32, 'm_old':   b'\x00'*32,
        'last_ts1': 0, 'pid_old_valid': False,
    }

# ── Enrollment ───────────────────────────────────────────────────────────────

def handle_enrollment(conn, addr):
    global T_acc
    try:
        # ── REG0 ──
        # Device → [AES1(K_AS_D, [id_d, 0×15])] = 16 bytes
        data = recv_msg(conn)
        if len(data) != 16:
            return
        plain = aes_dec_blocks(K_AS_D, data)
        id_d  = plain[0]

        c_d   = rand_bytes(1)[0]
        m_curr = rand_bytes(32)

        reply = bytearray(48)
        reply[0] = c_d
        reply[1:33] = m_curr
        send_msg(conn, aes_enc_blocks(K_AS_D, bytes(reply)))

        # ── REG1 ──
        # Device → [AES3(K_AS_D, [id_d, Y_dH(32), R_d, c_as_d, 0×...])] = 48 bytes
        data = recv_msg(conn)
        if len(data) != 48:
            return
        plain = aes_dec_blocks(K_AS_D, data)
        # plain[0]=id_d, plain[1:33]=Y_dH, plain[33]=R_d, plain[34]=c_as_d
        Y_dH   = bytes(plain[1:33])
        R_d    = plain[33]
        c_as_d = plain[34]

        R_as = puf_response(NODE_AS, c_as_d)
        phi  = R_as ^ R_d

        # T_acc &= H(y_d)  — accumulator update
        with clients_lock:
            for i in range(32):
                T_acc[i] &= Y_dH[i]

        pid_buf = bytes([id_d]) + m_curr
        PID_curr = sha256(pid_buf)

        with clients_lock:
            cl = make_client()
            cl['enrolled']      = True
            cl['c_d']           = c_d
            cl['c_as_d']        = c_as_d
            cl['phi_as_d']      = phi
            cl['PID_curr']      = PID_curr
            cl['PID_old']       = PID_curr      # initialise same
            cl['m_curr']        = bytes(m_curr)
            cl['m_old']         = bytes(m_curr)
            cl['last_ts1']      = 0
            cl['pid_old_valid'] = False
            clients[id_d]       = cl

        send_msg(conn, b'Registered')
        print(f"[AS] Enrolled device {id_d} PID={PID_curr.hex()[:6]}")
    except Exception as e:
        print(f"[AS] enrollment: {e}")
    finally:
        conn.close()

# ── Authentication + Key Exchange ────────────────────────────────────────────

def handle_auth(conn, addr):
    global session_ctr
    try:
        # AUTH_REQ = [PID(32) | y_asd(32) | ts_1(1)] = 65 bytes
        data = recv_msg(conn)
        if len(data) != 65:
            print(f"[AS] Bad auth len={len(data)}")
            return

        recv_PID = bytes(data[0:32])
        y_asd    = bytes(data[32:64])
        ts_1     = data[64]

        # ── PID lookup: curr first, then old ──
        with clients_lock:
            found   = None
            use_old = False
            for id_d, cl in clients.items():
                if not cl['enrolled']:
                    continue
                if cl['PID_curr'] == recv_PID:
                    found, use_old = cl, False
                    break
                if cl['pid_old_valid'] and cl['PID_old'] == recv_PID:
                    found, use_old = cl, True
                    break

        if found is None:
            print(f"[AS] Auth FAILED: PID {recv_PID.hex()[:6]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        cl       = found
        m_active = cl['m_old'] if use_old else cl['m_curr']
        log_path = "DESYNC-RECOVERY" if use_old else "NORMAL"

        # ── Freshness ──
        diff = (ts_1 - cl['last_ts1']) % 256
        if diff == 0 or diff > 200:
            print(f"[AS] Auth FAILED: stale ts_1 for dev {id_d}")
            send_msg(conn, bytes([0xFF]))
            return

        # ── Recover R_d ──
        R_as = puf_response(NODE_AS, cl['c_as_d'])
        R_d  = cl['phi_as_d'] ^ R_as

        # ── Recover Y_dH ──
        mask_in = bytes([R_d]) + m_active + recv_PID + bytes([ts_1])  # 66 bytes
        mask    = sha256(mask_in)
        Y_dH    = xor32(y_asd, mask)

        # ── Membership test: T_acc & Y_dH == T_acc ──
        with clients_lock:
            T_test = bytes(T_acc[i] & Y_dH[i] for i in range(32))
        if T_test != bytes(T_acc):
            print(f"[AS] Auth FAILED: membership check for dev {id_d}")
            send_msg(conn, bytes([0xFF]))
            return

        print(f"[AS] Device authenticated ({log_path}) | use_old={use_old}")

        # ── Key Exchange ──
        session_ctr = (session_ctr + 1) & 0xFF
        ts_2  = session_ctr
        n1    = rand_bytes(32)
        m_new = sha256(n1)

        # mh_mask = H(Y_dH || m_active || R_d || id_as || recv_PID || ts_2)  [99 bytes]
        mh_in = Y_dH + m_active + bytes([R_d, NODE_AS]) + recv_PID + bytes([ts_2])
        mh_mask = sha256(mh_in)
        m_H = xor32(m_new, mh_mask)

        kd_in  = bytes([R_d]) + m_new
        K_GW_D = sha256(kd_in)

        # ── Pseudonym rotation ──
        new_pid_in = bytes([id_d]) + m_new
        PID_new    = sha256(new_pid_in)

        with clients_lock:
            cl['PID_old']       = cl['PID_curr']
            cl['m_old']         = cl['m_curr']
            cl['pid_old_valid'] = True
            cl['PID_curr']      = PID_new
            cl['m_curr']        = m_new
            cl['last_ts1']      = ts_1

        print(f"[AS] Rotated state for dev {id_d} | PID_new={PID_new.hex()[:6]}")

        # ── Reply to device: [ACK(1) | m_H(32) | ts_2(1)] = 34 bytes ──
        reply = bytes([0xAC]) + m_H + bytes([ts_2])
        send_msg(conn, reply)

        # ── Forward token to GW (async) ──
        threading.Thread(target=_send_token_to_gw,
                         args=(PID_new, id_d, K_GW_D, ts_2), daemon=True).start()

    except Exception as e:
        print(f"[AS] auth handler: {e}")
    finally:
        conn.close()

def _send_token_to_gw(PID_new, id_d, K_GW_D, ts_auth):
    try:
        enc_tok = bytearray(48)
        enc_tok[0]     = id_d
        enc_tok[1]     = NODE_AS
        enc_tok[2]     = ts_auth
        enc_tok[16:32] = K_GW_D[:16]
        enc_tok[32:48] = K_GW_D[16:32]
        enc_tok_bytes  = aes_enc_blocks(K_GW_AS, bytes(enc_tok))

        token = PID_new + bytes([NODE_AS]) + enc_tok_bytes   # 81 bytes
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((GW_IP, PORT_GW_TOKEN))
            send_msg(s, token)
            ack = recv_msg(s)
        print(f"[AS] Token delivered to GW, ack={ack}")
    except Exception as e:
        print(f"[AS] token delivery failed: {e}")

# ── Listeners ────────────────────────────────────────────────────────────────

def listener(port, handler, name):
    srv = make_server(port)
    print(f"[AS] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    for port, fn, label in [
        (PORT_AS_ENROLL, handle_enrollment, "enroll"),
        (PORT_AS_AUTH,   handle_auth,       "auth"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()

    print(f"[AS] Proposed scheme AS (node {NODE_AS}) running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[AS] Stopping.")
