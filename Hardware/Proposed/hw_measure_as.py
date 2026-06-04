#!/usr/bin/env python3
"""
Hardware measurement — Proposed Scheme (AS role)
Runs on: Apex (192.168.1.132)

Same logic as as_node.py but with per-request CPU time + energy logging.
Prints a summary on exit (Ctrl+C or SIGTERM).
"""
import sys, os, threading, time, socket, atexit, signal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (GW_IP, PORT_GW_TOKEN, PORT_AS_ENROLL, PORT_AS_AUTH,
                    NODE_AS, NODE_GW)

RPI_POWER_MW = 3800   # mW — RPi 4B typical single-core active

T_acc        = bytearray([0xFF] * 32)
clients      = {}
clients_lock = threading.Lock()
session_ctr  = 0

# Measurement accumulators
stats = {
    'enroll_count': 0,
    'enroll_wall_s': 0.0,
    'enroll_cpu_s':  0.0,
    'auth_count': 0,
    'auth_wall_s': 0.0,
    'auth_cpu_s':  0.0,
}
stats_lock = threading.Lock()


def make_client():
    return {
        'enrolled': False,
        'c_d': 0, 'c_as_d': 0, 'phi_as_d': 0,
        'PID_curr': b'\x00'*32, 'PID_old': b'\x00'*32,
        'm_curr':   b'\x00'*32, 'm_old':   b'\x00'*32,
        'last_ts1': 0, 'pid_old_valid': False,
    }


def handle_enrollment(conn, addr):
    global T_acc
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()
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

        pid_buf  = bytes([id_d]) + m_curr
        PID_curr = sha256(pid_buf)

        with clients_lock:
            cl = make_client()
            cl['enrolled']      = True
            cl['c_d']           = c_d
            cl['c_as_d']        = c_as_d
            cl['phi_as_d']      = phi
            cl['PID_curr']      = PID_curr
            cl['PID_old']       = PID_curr
            cl['m_curr']        = bytes(m_curr)
            cl['m_old']         = bytes(m_curr)
            cl['last_ts1']      = 0
            cl['pid_old_valid'] = False
            clients[id_d]       = cl

        send_msg(conn, b'Registered')

        wall_s = time.perf_counter() - t_wall
        cpu_s  = time.process_time()  - t_cpu
        with stats_lock:
            stats['enroll_count']  += 1
            stats['enroll_wall_s'] += wall_s
            stats['enroll_cpu_s']  += cpu_s
        print(f"[AS] Enrolled dev={id_d}  wall={wall_s*1000:.2f}ms  cpu={cpu_s*1000:.2f}ms  "
              f"energy={wall_s*RPI_POWER_MW:.2f}mJ  PID={PID_curr.hex()[:8]}")
    except Exception as e:
        print(f"[AS] enrollment: {e}")
    finally:
        conn.close()


def handle_auth(conn, addr):
    global session_ctr
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()
    try:
        data = recv_msg(conn)
        if len(data) != 65:
            print(f"[AS] Bad auth len={len(data)}")
            return

        recv_PID = bytes(data[0:32])
        y_asd    = bytes(data[32:64])
        ts_1     = data[64]

        with clients_lock:
            found   = None
            use_old = False
            for id_d, cl in clients.items():
                if not cl['enrolled']:
                    continue
                if cl['PID_curr'] == recv_PID:
                    found, use_old = cl, False;  break
                if cl['pid_old_valid'] and cl['PID_old'] == recv_PID:
                    found, use_old = cl, True;   break

        if found is None:
            print(f"[AS] Auth FAILED: PID {recv_PID.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        cl       = found
        m_active = cl['m_old'] if use_old else cl['m_curr']

        diff = (ts_1 - cl['last_ts1']) % 256
        if diff == 0 or diff > 200:
            send_msg(conn, bytes([0xFF]))
            return

        R_as = puf_response(NODE_AS, cl['c_as_d'])
        R_d  = cl['phi_as_d'] ^ R_as
        mask_in = bytes([R_d]) + m_active + recv_PID + bytes([ts_1])
        mask    = sha256(mask_in)
        Y_dH    = xor32(y_asd, mask)

        with clients_lock:
            T_test = bytes(T_acc[i] & Y_dH[i] for i in range(32))
        if T_test != bytes(T_acc):
            print(f"[AS] Auth FAILED: membership check")
            send_msg(conn, bytes([0xFF]))
            return

        session_ctr = (session_ctr + 1) & 0xFF
        ts_2  = session_ctr
        n1    = rand_bytes(32)
        m_new = sha256(n1)

        mh_in   = Y_dH + m_active + bytes([R_d, NODE_AS]) + recv_PID + bytes([ts_2])
        mh_mask = sha256(mh_in)
        m_H     = xor32(m_new, mh_mask)

        kd_in  = bytes([R_d]) + m_new
        K_GW_D = sha256(kd_in)

        new_pid_in = bytes([id_d]) + m_new
        PID_new    = sha256(new_pid_in)

        with clients_lock:
            cl['PID_old']       = cl['PID_curr']
            cl['m_old']         = cl['m_curr']
            cl['pid_old_valid'] = True
            cl['PID_curr']      = PID_new
            cl['m_curr']        = m_new
            cl['last_ts1']      = ts_1

        reply = bytes([0xAC]) + m_H + bytes([ts_2])
        send_msg(conn, reply)

        threading.Thread(target=_send_token_to_gw,
                         args=(PID_new, id_d, K_GW_D, ts_2), daemon=True).start()

        wall_s = time.perf_counter() - t_wall
        cpu_s  = time.process_time()  - t_cpu
        with stats_lock:
            stats['auth_count']  += 1
            stats['auth_wall_s'] += wall_s
            stats['auth_cpu_s']  += cpu_s
        print(f"[AS] Auth OK dev={id_d}  wall={wall_s*1000:.2f}ms  cpu={cpu_s*1000:.2f}ms  "
              f"energy={wall_s*RPI_POWER_MW:.2f}mJ  PID_new={PID_new.hex()[:8]}")
    except Exception as e:
        print(f"[AS] auth: {e}")
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
        token = PID_new + bytes([NODE_AS]) + aes_enc_blocks(K_GW_AS, bytes(enc_tok))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((GW_IP, PORT_GW_TOKEN))
            send_msg(s, token)
            recv_msg(s)
    except Exception as e:
        print(f"[AS] token delivery failed: {e}")


def print_summary():
    print("\n" + "=" * 70)
    print("[AS] ===== AS ENERGY SUMMARY =====")
    with stats_lock:
        ec = stats['enroll_count']
        ew = stats['enroll_wall_s']
        ac = stats['auth_count']
        aw = stats['auth_wall_s']
    print(f"{'Operation':<20} {'Count':>6} {'TotalWall(ms)':>14} {'TotalEnergy(mJ)':>16}")
    print("-" * 58)
    print(f"{'Enrollment':<20} {ec:>6} {ew*1000:>14.2f} {ew*RPI_POWER_MW:>16.2f}")
    print(f"{'Auth+KeyEx':<20} {ac:>6} {aw*1000:>14.2f} {aw*RPI_POWER_MW:>16.2f}")
    total_w = ew + aw
    print("-" * 58)
    print(f"{'TOTAL':<20} {ec+ac:>6} {total_w*1000:>14.2f} {total_w*RPI_POWER_MW:>16.2f}")
    if ac > 0:
        print(f"\nAvg auth latency: {aw/ac*1000:.2f} ms  avg auth energy: {aw/ac*RPI_POWER_MW:.2f} mJ")
    print("=" * 70)


atexit.register(print_summary)


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

    print(f"[AS] Proposed hw-measure AS (node {NODE_AS})  GW={GW_IP}")
    print(f"[AS] Power assumption: {RPI_POWER_MW} mW.  Ctrl+C to stop and print summary.")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[AS] Stopping.")
