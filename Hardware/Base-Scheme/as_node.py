#!/usr/bin/env python3
"""
Authentication Server — Base Scheme (LAAKA / das2026comsnets)
Runs on: RPi 1 (192.168.1.113)

Listens on:
  PORT_AS_ENROLL (5004)  ← Device: Enrollment
  PORT_AS_AUTH   (5005)  ← Device: Auth request [id_d(1)|masked_Y_dH(32)|ts_1(1)] = 34B

After auth, pushes 48-byte token to GW.
"""
import sys, os, threading, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (GW_IP, PORT_GW_TOKEN, PORT_AS_ENROLL, PORT_AS_AUTH,
                    NODE_AS, NODE_GW)

T_Acc    = bytearray([0xFF] * 32)
clients  = {}
clients_lock = threading.Lock()
session_ctr  = 0

def make_client():
    return {
        'enrolled': False,
        'y_d': 0, 'c_as_d': 0,
        'phi_d': 0, 'h_as_d': 0,
        'M_d': bytearray(32),
    }

# ── Enrollment ───────────────────────────────────────────────────────────────

def handle_enrollment(conn, addr):
    global T_Acc
    try:
        # REG0: AES(k_as_d, [id_d, 0×]) = 16B → reply AES(k_as_d, [c_d, m_d, 0×]) = 16B
        data = recv_msg(conn)
        if len(data) != 16:
            return
        plain = aes_dec_blocks(K_AS_D, data)
        id_d  = plain[0]

        c_d = 7    # fixed challenge (matches COOJA default)
        m_d = 5    # fixed initial M_d[0]
        rep0 = bytearray(16)
        rep0[0] = c_d
        rep0[1] = m_d
        send_msg(conn, aes_enc_blocks(K_AS_D, bytes(rep0)))

        # REG1: AES(k_as_d, [id_d, y_d, R_d, c_as_d, 0×]) = 16B → "Registered"
        data = recv_msg(conn)
        if len(data) != 16:
            return
        plain = aes_dec_blocks(K_AS_D, data)
        y_d    = plain[1]
        R_d    = plain[2]
        c_as_d = plain[3]

        R_as = puf_response(NODE_AS, c_as_d)
        phi  = R_d ^ R_as
        Y_dH = sha256(bytes([y_d]))

        M_d = bytearray(32)
        M_d[0] = m_d

        with clients_lock:
            T_test = bytearray(T_Acc)
            for i in range(32):
                T_test[i] &= Y_dH[i]
            T_Acc = T_test

            cl = make_client()
            cl['enrolled'] = True
            cl['y_d']      = y_d
            cl['c_as_d']   = c_as_d
            cl['phi_d']    = phi
            cl['M_d']      = M_d
            clients[id_d]  = cl

        send_msg(conn, b'Registered')
        print(f"[AS-BASE] Enrolled device {id_d}")
    except Exception as e:
        print(f"[AS-BASE] enrollment: {e}")
    finally:
        conn.close()

# ── Authentication ────────────────────────────────────────────────────────────

def handle_auth(conn, addr):
    global session_ctr
    try:
        # AUTH_REQ = [id_d(1) | masked_Y_dH(32) | ts_1(1)] = 34B
        data = recv_msg(conn)
        if len(data) != 34:
            print(f"[AS-BASE] Bad auth len={len(data)}")
            return

        id_d  = data[0]
        recv_masked = bytes(data[1:33])
        ts_1  = data[33]

        with clients_lock:
            cl = clients.get(id_d)
        if cl is None or not cl['enrolled']:
            print(f"[AS-BASE] Auth FAILED: dev {id_d} not found")
            send_msg(conn, bytes([0xFF]))
            return

        # Regenerate R_d
        R_as = puf_response(NODE_AS, cl['c_as_d'])
        R_d  = cl['phi_d'] ^ R_as

        # Recover Y_dH: mask = H(R_d || M_d(32) || id_d || ts_1)
        mask_in = bytes([R_d]) + bytes(cl['M_d']) + bytes([id_d, ts_1])
        mask    = sha256(mask_in)
        Y_dH    = xor32(recv_masked, mask)

        # Membership test
        with clients_lock:
            T_test = bytes(T_Acc[i] & Y_dH[i] for i in range(32))
        if T_test != bytes(T_Acc):
            print(f"[AS-BASE] Auth FAILED: membership for dev {id_d}")
            send_msg(conn, bytes([0xFF]))
            return

        print(f"[AS-BASE] Device {id_d} authenticated")

        # Generate new session material
        session_ctr = (session_ctr + 1) & 0xFF
        ts_2   = session_ctr
        M_new  = rand_bytes(32)

        # mask for key reply: H(Y_dH || M_d(32) || R_d || id_as || id_d || ts_2)
        kd_mask_in = Y_dH + bytes(cl['M_d']) + bytes([R_d, NODE_AS, id_d, ts_2])
        kd_mask    = sha256(kd_mask_in)
        M_new_masked = xor32(M_new, kd_mask)

        # k_gw_d = H(R_d || M_new)
        k_gw_d = sha256(bytes([R_d]) + M_new)

        with clients_lock:
            clients[id_d]['M_d'] = bytearray(M_new)

        # Reply: [AS_id(1) | masked_M_new(32) | ts_2(1)] = 34B
        reply = bytes([NODE_AS]) + M_new_masked + bytes([ts_2])
        send_msg(conn, reply)

        # Forward token to GW
        threading.Thread(target=_send_token,
                         args=(id_d, k_gw_d, ts_2), daemon=True).start()
    except Exception as e:
        print(f"[AS-BASE] auth: {e}")
    finally:
        conn.close()

def _send_token(id_d, k_gw_d, ts_auth):
    try:
        blk0 = bytearray(16)
        blk0[0] = id_d
        blk0[1] = NODE_AS
        blk0[2] = ts_auth
        token = (aes_enc_blocks(K_GW_AS, bytes(blk0)) +
                 aes_enc_blocks(K_GW_AS, k_gw_d[:16])  +
                 aes_enc_blocks(K_GW_AS, k_gw_d[16:32]))   # 48 bytes
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((GW_IP, PORT_GW_TOKEN))
            send_msg(s, token)
            recv_msg(s)
        print(f"[AS-BASE] Token sent to GW for dev {id_d}")
    except Exception as e:
        print(f"[AS-BASE] token delivery: {e}")

def listener(port, handler, name):
    srv = make_server(port)
    print(f"[AS-BASE] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    for port, fn, label in [
        (PORT_AS_ENROLL, handle_enrollment, "enroll"),
        (PORT_AS_AUTH,   handle_auth,       "auth"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()

    print(f"[AS-BASE] Base scheme AS (node {NODE_AS}) running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[AS-BASE] Stopping.")
