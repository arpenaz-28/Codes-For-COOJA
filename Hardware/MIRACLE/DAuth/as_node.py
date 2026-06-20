#!/usr/bin/env python3
"""
Fair-DAuth — AS role  (Hardware/MIRACLE/DAuth)

Same transport/topology as the Proposed AS (binary framing, pushes the session
token to the GW during Auth). DAuth core differences vs Proposed:
  - device identified by a STATIC handle DH (no pseudonym rotation)
  - SINGLE state per device (no dual-state desync recovery)

Runs on: Apex (192.168.1.132)   [same placement as Proposed AS]
"""
import sys, os, threading, time, socket, atexit, signal
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _d)
from common import *
from config import (GW_IP, PORT_GW_TOKEN, PORT_AS_ENROLL, PORT_AS_AUTH,
                    NODE_AS, NODE_GW)

RPI_POWER_MW = 3800

T_acc        = bytearray([0xFF] * 32)
clients      = {}                  # DH(hex) -> client state (SINGLE state)
clients_lock = threading.Lock()
session_ctr  = 0

stats = {'enroll_count': 0, 'enroll_wall_s': 0.0, 'enroll_cpu_s': 0.0,
         'auth_count': 0, 'auth_wall_s': 0.0, 'auth_cpu_s': 0.0}
stats_lock = threading.Lock()


def make_client():
    return {'enrolled': False, 'id_d': 0, 'c_d': 0, 'c_as_d': 0, 'phi_as_d': 0,
            'DH': b'\x00'*32, 'm_curr': b'\x00'*32, 'last_ts1': 0}


def handle_enrollment(conn, addr):
    global T_acc
    t_wall = time.perf_counter(); t_cpu = time.process_time()
    try:
        data = recv_msg(conn)
        if len(data) != 16:
            return
        plain = aes_dec_blocks(K_AS_D, data)
        id_d  = plain[0]

        c_d    = rand_bytes(1)[0]
        m_curr = rand_bytes(32)
        reply  = bytearray(48)
        reply[0]    = c_d
        reply[1:33] = m_curr
        send_msg(conn, aes_enc_blocks(K_AS_D, bytes(reply)))

        data = recv_msg(conn)
        if len(data) != 48:
            return
        plain  = aes_dec_blocks(K_AS_D, data)
        Y_dH   = bytes(plain[1:33])
        R_d    = plain[33]
        c_as_d = plain[34]

        R_as = puf_response(NODE_AS, c_as_d)
        phi  = R_as ^ R_d

        with clients_lock:
            for i in range(32):
                T_acc[i] &= Y_dH[i]

        DH = sha256(bytes([id_d]) + m_curr)   # static handle

        with clients_lock:
            cl = make_client()
            cl.update(enrolled=True, id_d=id_d, c_d=c_d, c_as_d=c_as_d,
                      phi_as_d=phi, DH=DH, m_curr=bytes(m_curr), last_ts1=0)
            clients[DH.hex()] = cl

        send_msg(conn, b'Registered')

        wall_s = time.perf_counter() - t_wall; cpu_s = time.process_time() - t_cpu
        with stats_lock:
            stats['enroll_count'] += 1; stats['enroll_wall_s'] += wall_s; stats['enroll_cpu_s'] += cpu_s
        print(f"[AS] Enrolled dev={id_d}  wall={wall_s*1000:.2f}ms  DH={DH.hex()[:8]}")
    except Exception as e:
        print(f"[AS] enrollment: {e}")
    finally:
        conn.close()


def handle_auth(conn, addr):
    global session_ctr
    t_wall = time.perf_counter(); t_cpu = time.process_time()
    try:
        data = recv_msg(conn)
        if len(data) != 65:
            print(f"[AS] Bad auth len={len(data)}"); return

        recv_DH = bytes(data[0:32])
        y_asd   = bytes(data[32:64])
        ts_1    = data[64]

        with clients_lock:                       # SINGLE-state lookup (no PID_old)
            cl = clients.get(recv_DH.hex())
        if cl is None or not cl['enrolled']:
            print(f"[AS] Auth FAILED: DH {recv_DH.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF])); return

        m_active = cl['m_curr']
        diff = (ts_1 - cl['last_ts1']) % 256
        if diff == 0 or diff > 200:
            send_msg(conn, bytes([0xFF])); return

        R_as = puf_response(NODE_AS, cl['c_as_d'])
        R_d  = cl['phi_as_d'] ^ R_as
        mask = sha256(bytes([R_d]) + m_active + recv_DH + bytes([ts_1]))
        Y_dH = xor32(y_asd, mask)

        with clients_lock:
            T_test = bytes(T_acc[i] & Y_dH[i] for i in range(32))
        if T_test != bytes(T_acc):
            print(f"[AS] Auth FAILED: membership check")
            send_msg(conn, bytes([0xFF])); return

        session_ctr = (session_ctr + 1) & 0xFF
        ts_2  = session_ctr
        m_new = sha256(rand_bytes(32))

        mh_mask = sha256(Y_dH + m_active + bytes([R_d, NODE_AS]) + recv_DH + bytes([ts_2]))
        m_H     = xor32(m_new, mh_mask)
        K_GW_D  = sha256(bytes([R_d]) + m_new)

        with clients_lock:                       # update key-freshness state only; DH fixed
            cl['m_curr']   = m_new
            cl['last_ts1'] = ts_1

        send_msg(conn, bytes([0xAC]) + m_H + bytes([ts_2]))

        # PUSH the session token to the GW (keyed by the static handle DH)
        threading.Thread(target=_send_token_to_gw,
                         args=(recv_DH, cl['id_d'], K_GW_D, ts_2), daemon=True).start()

        wall_s = time.perf_counter() - t_wall; cpu_s = time.process_time() - t_cpu
        with stats_lock:
            stats['auth_count'] += 1; stats['auth_wall_s'] += wall_s; stats['auth_cpu_s'] += cpu_s
        print(f"[AS] Auth OK dev={cl['id_d']}  wall={wall_s*1000:.2f}ms  DH={recv_DH.hex()[:8]}")
    except Exception as e:
        print(f"[AS] auth: {e}")
    finally:
        conn.close()


def _send_token_to_gw(DH, id_d, K_GW_D, ts_auth):
    try:
        enc_tok = bytearray(48)
        enc_tok[0]     = id_d
        enc_tok[1]     = NODE_AS
        enc_tok[2]     = ts_auth
        enc_tok[16:32] = K_GW_D[:16]
        enc_tok[32:48] = K_GW_D[16:32]
        token = DH + bytes([NODE_AS]) + aes_enc_blocks(K_GW_AS, bytes(enc_tok))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((GW_IP, PORT_GW_TOKEN))
            send_msg(s, token)
            recv_msg(s)
    except Exception as e:
        print(f"[AS] token delivery failed: {e}")


def print_summary():
    print("\n" + "=" * 70)
    print("[AS] ===== AS ENERGY SUMMARY (fair-DAuth) =====")
    with stats_lock:
        ec, ew = stats['enroll_count'], stats['enroll_wall_s']
        ac, aw = stats['auth_count'],   stats['auth_wall_s']
    print(f"Enrollment x{ec}: {ew*1000:.2f} ms   Auth x{ac}: {aw*1000:.2f} ms")
    if ac > 0:
        print(f"Avg auth latency: {aw/ac*1000:.2f} ms  energy: {aw/ac*RPI_POWER_MW:.2f} mJ")
    print("=" * 70)


atexit.register(print_summary)


def listener(port, handler, name):
    srv = make_server(port)
    print(f"[AS] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    for port, fn, label in [(PORT_AS_ENROLL, handle_enrollment, "enroll"),
                            (PORT_AS_AUTH,   handle_auth,       "auth")]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()
    print(f"[AS] Fair-DAuth AS (node {NODE_AS})  GW={GW_IP}")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[AS] Stopping.")
