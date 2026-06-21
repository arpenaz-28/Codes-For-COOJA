#!/usr/bin/env python3
"""
IoT Device — Proposed Scheme (Revised Anonymity)
Runs on: RPi 2 (192.168.1.132)

Runs 4 auth rounds demonstrating desync recovery:
  Round 1: Normal auth  → success
  Round 2: Auth OK on AS side but device drops reply → DESYNC
  Round 3: Retry with old PID → AS uses PID_old → RECOVERY
  Round 4: Normal auth post-recovery → confirms sync
"""
import sys, os, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (AS_IP, GW_IP, PORT_AS_ENROLL, PORT_AS_AUTH,
                    PORT_GW_KEYEX, PORT_GW_DATA, NODE_DEV, NODE_AS, NODE_GW)

# ── Device state ─────────────────────────────────────────────────────────────
ID_D    = NODE_DEV
y_d     = 2
c_as_d  = 3
c_d     = 0
h_d     = 0
m_d     = b'\x00' * 32
PID     = b'\x00' * 32
k_gw_d  = b'\x00' * 32
ts_1    = 1
last_ts2 = 0
results = []

def tcp_send_recv(ip, port, payload):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        send_msg(s, payload)
        return recv_msg(s)

# ── Enrollment ───────────────────────────────────────────────────────────────

def do_enrollment():
    global c_d, h_d, m_d, PID

    t0 = time.perf_counter()

    # REG0: send AES(K_AS_D, [id_d, 0×15]) = 16 bytes
    p0 = bytearray(16)
    p0[0] = ID_D
    reg0_req = aes_enc_blocks(K_AS_D, bytes(p0))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((AS_IP, PORT_AS_ENROLL))
        send_msg(s, reg0_req)

        # REG0 reply: AES(K_AS_D, [c_d, m_curr(32), 0×15]) = 48 bytes
        rep0 = recv_msg(s)
        plain0 = aes_dec_blocks(K_AS_D, rep0)
        c_d = plain0[0]
        m_d = bytes(plain0[1:33])

        # REG1: AES(K_AS_D, [id_d, Y_dH(32), R_d, c_as_d, 0×...]) = 48 bytes
        R_d   = puf_response(ID_D, c_d)
        h_d   = R_d
        Y_dH  = sha256(bytes([y_d]))

        p1 = bytearray(48)
        p1[0]    = ID_D
        p1[1:33] = Y_dH
        p1[33]   = R_d
        p1[34]   = c_as_d
        send_msg(s, aes_enc_blocks(K_AS_D, bytes(p1)))

        ack = recv_msg(s)

    # Compute initial PID = H(id_d || m_curr)
    PID = sha256(bytes([ID_D]) + m_d)

    elapsed = time.perf_counter() - t0
    print(f"[DEV] Enrollment done in {elapsed*1000:.1f} ms | PID={PID.hex()[:6]}")
    results.append({'phase': 'Enroll', 'time_ms': round(elapsed*1000, 2)})

# ── Auth + Key Exchange (one round) ─────────────────────────────────────────

def do_auth(round_num, simulate_drop=False):
    global m_d, PID, k_gw_d, ts_1, last_ts2

    R_d  = h_d
    Y_dH = sha256(bytes([y_d]))

    # mask = H(R_d || m_d || PID || ts_1)  [66 bytes]
    mask_in = bytes([R_d]) + m_d + PID + bytes([ts_1])
    mask    = sha256(mask_in)
    y_asd   = xor32(Y_dH, mask)

    auth_PID = sha256(bytes([ID_D]) + m_d)

    payload = auth_PID + y_asd + bytes([ts_1])   # 65 bytes

    print(f"[DEV] Round {round_num}: sending auth | PID={auth_PID.hex()[:6]} ts_1={ts_1}")
    t0 = time.perf_counter()

    try:
        rep = tcp_send_recv(AS_IP, PORT_AS_AUTH, payload)
    except Exception as e:
        print(f"[DEV] Round {round_num}: auth send failed: {e}")
        return False

    elapsed_auth = time.perf_counter() - t0

    if rep[0] == 0xFF:
        print(f"[DEV] Round {round_num}: auth NACK from AS")
        return False

    if simulate_drop:
        print(f"[DEV] Round {round_num}: SIMULATED DROP — ignoring valid AS reply")
        print(f"[DEV] Round {round_num}: Device DESYNCHRONIZED (keeps old PID/m)")
        results.append({'phase': f'Auth-R{round_num}(drop)', 'time_ms': round(elapsed_auth*1000,2)})
        return False

    if len(rep) != 34 or rep[0] != 0xAC:
        print(f"[DEV] Round {round_num}: bad auth reply")
        return False

    m_H  = bytes(rep[1:33])
    ts_2 = rep[33]

    # Freshness check on ts_2
    diff = (ts_2 - last_ts2) % 256
    if diff == 0 or diff > 200:
        print(f"[DEV] Round {round_num}: stale ts_2={ts_2}")
        return False

    # Derive m_new: m_H = m_new XOR mh_mask
    mh_in   = Y_dH + m_d + bytes([R_d, NODE_AS]) + auth_PID + bytes([ts_2])
    mh_mask = sha256(mh_in)
    m_new   = xor32(m_H, mh_mask)

    # Derive K_GW_D = H(R_d || m_new)
    k_gw_d = sha256(bytes([R_d]) + m_new)

    # Commit new state
    m_d      = m_new
    PID      = sha256(bytes([ID_D]) + m_new)
    last_ts2 = ts_2
    ts_1     = (ts_1 + 1) & 0xFF

    print(f"[DEV] Round {round_num}: auth OK | New PID={PID.hex()[:6]}")

    # ── Key Exchange ──────────────────────────────────────────────────────────
    ke_blk = bytearray(16)
    ke_blk[0] = ts_1
    ke_payload = PID + aes_enc_blocks(k_gw_d[:16], bytes(ke_blk))

    t1 = time.perf_counter()
    try:
        ke_rep = tcp_send_recv(GW_IP, PORT_GW_KEYEX, ke_payload)
    except Exception as e:
        print(f"[DEV] Round {round_num}: KeyEx failed: {e}")
        return False
    elapsed_ke = time.perf_counter() - t1

    if len(ke_rep) == 16:
        plain_ke = aes_dec_blocks(k_gw_d[:16], ke_rep)
        print(f"[DEV] Round {round_num}: KeyEx OK | nonce_resp={plain_ke[0]}")
    else:
        print(f"[DEV] Round {round_num}: bad KeyEx reply")

    # ── Data ──────────────────────────────────────────────────────────────────
    sensor_blk = bytearray(16)
    sensor_blk[0] = 9          # simulated sensor value
    data_payload = PID + aes_enc_blocks(k_gw_d[:16], bytes(sensor_blk))

    t2 = time.perf_counter()
    try:
        data_rep = tcp_send_recv(GW_IP, PORT_GW_DATA, data_payload)
    except Exception as e:
        print(f"[DEV] Round {round_num}: Data send failed: {e}")
        return False
    elapsed_data = time.perf_counter() - t2

    total_ms = (time.perf_counter() - t0) * 1000
    print(f"[DEV] Round {round_num}: Data ACK | total={total_ms:.1f} ms")
    results.append({
        'phase': f'Auth+KE-R{round_num}',
        'auth_ms': round(elapsed_auth*1000, 2),
        'ke_ms':   round(elapsed_ke*1000, 2),
        'data_ms': round(elapsed_data*1000, 2),
        'total_ms': round(total_ms, 2),
    })
    return True

# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("[DEV] Proposed scheme — 4-round desync demo")
    print("=" * 60)

    time.sleep(1)  # give servers time to start

    do_enrollment()
    time.sleep(0.5)

    print("\n[DEV] === Round 1: Normal auth ===")
    do_auth(1)
    time.sleep(0.5)

    print("\n[DEV] === Round 2: Desync trigger (drop reply) ===")
    do_auth(2, simulate_drop=True)
    time.sleep(0.5)

    print("\n[DEV] === Round 3: Desync recovery (retry with old PID) ===")
    ok = do_auth(3)
    if ok:
        print("[DEV] Round 3: RECOVERY SUCCESSFUL")
    else:
        print("[DEV] Round 3: Recovery FAILED")
    time.sleep(0.5)

    print("\n[DEV] === Round 4: Post-recovery normal auth ===")
    do_auth(4)

    print("\n" + "=" * 60)
    print("[DEV] Results summary:")
    for r in results:
        print(" ", r)
    print("=" * 60)
