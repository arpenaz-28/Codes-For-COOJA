#!/usr/bin/env python3
"""
IoT Device — Base Scheme (LAAKA / das2026comsnets)
Runs on: RPi 2 (192.168.1.132)

Single-round: Enroll → Auth → KeyEx (DH) → Data
"""
import sys, os, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (AS_IP, GW_IP, PORT_AS_ENROLL, PORT_AS_AUTH,
                    PORT_GW_KEYEX, PORT_GW_DATA,
                    NODE_DEV, NODE_AS, DH_G, DH_P, DH_A)

ID_D   = NODE_DEV
y_d    = 2
c_as_d = 3
c_d    = 0
h_d    = 0
M_d    = bytearray(32)
k_gw_d = bytearray(32)
K_GW_D = bytearray(16)
results = []

def tcp_send_recv(ip, port, payload):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        send_msg(s, payload)
        return recv_msg(s)

# ── Enrollment ───────────────────────────────────────────────────────────────

def do_enrollment():
    global c_d, h_d, M_d

    t0 = time.perf_counter()

    p0 = bytearray(16)
    p0[0] = ID_D

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((AS_IP, PORT_AS_ENROLL))
        send_msg(s, aes_enc_blocks(K_AS_D, bytes(p0)))

        rep0  = recv_msg(s)
        plain = aes_dec_blocks(K_AS_D, rep0)
        c_d   = plain[0]
        m_d0  = plain[1]

        M_d      = bytearray(32)
        M_d[0]   = m_d0

        # PUF response
        R_d = puf_response(ID_D, c_d)
        h_d = R_d

        # REG1
        p1 = bytearray(16)
        p1[0] = ID_D
        p1[1] = y_d
        p1[2] = R_d
        p1[3] = c_as_d
        send_msg(s, aes_enc_blocks(K_AS_D, bytes(p1)))
        ack = recv_msg(s)

    elapsed = time.perf_counter() - t0
    print(f"[DEV-BASE] Enrollment done in {elapsed*1000:.1f} ms")
    results.append({'phase': 'Enroll', 'time_ms': round(elapsed*1000, 2)})

# ── Authentication ────────────────────────────────────────────────────────────

def do_auth_and_keyex():
    global M_d, k_gw_d, K_GW_D

    t0 = time.perf_counter()

    R_d  = puf_response(ID_D, c_d)
    Y_dH = sha256(bytes([y_d]))

    # mask = H(R_d || M_d(32) || id_d || ts_1)
    mask_in = bytes([R_d]) + bytes(M_d) + bytes([ID_D, 0])
    mask    = sha256(mask_in)
    masked_Y = xor32(Y_dH, mask)

    auth_req = bytes([ID_D]) + masked_Y + bytes([0])   # ts_1=0

    t_auth = time.perf_counter()
    rep = tcp_send_recv(AS_IP, PORT_AS_AUTH, auth_req)
    elapsed_auth = time.perf_counter() - t_auth

    if len(rep) != 34 or rep[0] == 0xFF:
        print("[DEV-BASE] Auth FAILED")
        return False

    # rep = [AS_id(1) | masked_M_new(32) | ts_2(1)]
    ts_2         = rep[33]
    masked_M_new = bytes(rep[1:33])

    # Unmask M_new
    kd_mask_in = Y_dH + bytes(M_d) + bytes([R_d, NODE_AS, ID_D, ts_2])
    kd_mask    = sha256(kd_mask_in)
    M_new      = xor32(masked_M_new, kd_mask)

    # k_gw_d = H(R_d || M_new)
    k_gw_d = sha256(bytes([R_d]) + M_new)
    M_d    = bytearray(M_new)
    K_GW_D = bytearray(k_gw_d[:16])

    print(f"[DEV-BASE] Auth OK in {elapsed_auth*1000:.1f} ms")

    # ── Key Exchange (DH) ─────────────────────────────────────────────────────
    alpha    = (DH_G ** DH_A) % DH_P
    ke_blk   = bytearray(16)
    ke_blk[0] = alpha
    ke_payload = bytes([ID_D]) + aes_enc_blocks(bytes(K_GW_D), bytes(ke_blk))

    t_ke = time.perf_counter()
    ke_rep = tcp_send_recv(GW_IP, PORT_GW_KEYEX, ke_payload)
    elapsed_ke = time.perf_counter() - t_ke

    if len(ke_rep) == 16:
        plain_ke = aes_dec_blocks(bytes(K_GW_D), ke_rep)
        beta     = plain_ke[0]
        k_gw_d_new      = bytearray(32)
        k_gw_d_new[0]   = (beta ^ DH_A) % DH_P
        k_gw_d = bytes(k_gw_d_new)
        K_GW_D = bytearray(k_gw_d[:16])
        print(f"[DEV-BASE] KeyEx OK in {elapsed_ke*1000:.1f} ms | k_gw_d[0]={k_gw_d[0]}")

    # ── Data ──────────────────────────────────────────────────────────────────
    sensor_blk    = bytearray(16)
    sensor_blk[0] = 9
    data_payload  = bytes([ID_D]) + aes_enc_blocks(bytes(K_GW_D), bytes(sensor_blk))

    t_data = time.perf_counter()
    data_rep = tcp_send_recv(GW_IP, PORT_GW_DATA, data_payload)
    elapsed_data = time.perf_counter() - t_data

    total_ms = (time.perf_counter() - t0) * 1000
    print(f"[DEV-BASE] Data ACK | total={total_ms:.1f} ms")
    results.append({
        'phase': 'Auth+KE',
        'auth_ms':  round(elapsed_auth*1000, 2),
        'ke_ms':    round(elapsed_ke*1000, 2),
        'data_ms':  round(elapsed_data*1000, 2),
        'total_ms': round(total_ms, 2),
    })
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("[DEV-BASE] Base scheme hardware test")
    print("=" * 60)

    time.sleep(1)
    do_enrollment()
    time.sleep(0.5)
    do_auth_and_keyex()

    print("\nResults:")
    for r in results:
        print(" ", r)
