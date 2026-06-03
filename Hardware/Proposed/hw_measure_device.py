#!/usr/bin/env python3
"""
Hardware measurement — Proposed Scheme (Device role)
Runs on: Pi (192.168.1.113)

Phases measured: Enrollment + 3 normal Auth rounds (Auth → KeyEx → Data)
Metrics per phase:
  - wall_ms  : wall-clock latency
  - cpu_ms   : CPU time (time.process_time)
  - energy_mj: estimated energy = wall_s × RPi_power_mW

RPi 3B+ active power assumption: 1400 mW (single-core Python workload)
"""
import sys, os, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (AS_IP, GW_IP, PORT_AS_ENROLL, PORT_AS_AUTH,
                    PORT_GW_KEYEX, PORT_GW_DATA, NODE_DEV, NODE_AS)

RPI_POWER_MW = 1400   # mW — RPi 3B+ typical single-core active
NUM_ROUNDS   = 3

# Device state
ID_D     = NODE_DEV
y_d      = 2
c_as_d   = 3
c_d      = 0
h_d      = 0
m_d      = b'\x00' * 32
PID      = b'\x00' * 32
k_gw_d   = b'\x00' * 32
ts_1     = 1
last_ts2 = 0
results  = []


def tcp_send_recv(ip, port, payload):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        send_msg(s, payload)
        return recv_msg(s)


def energy(wall_s):
    return round(wall_s * (RPI_POWER_MW / 1000), 6)   # Watts × seconds = Joules


def do_enrollment():
    global c_d, h_d, m_d, PID
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()

    p0 = bytearray(16)
    p0[0] = ID_D
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((AS_IP, PORT_AS_ENROLL))
        send_msg(s, aes_enc_blocks(K_AS_D, bytes(p0)))
        rep0   = recv_msg(s)
        plain0 = aes_dec_blocks(K_AS_D, rep0)
        c_d    = plain0[0]
        m_d    = bytes(plain0[1:33])

        R_d  = puf_response(ID_D, c_d)
        h_d  = R_d
        Y_dH = sha256(bytes([y_d]))
        p1 = bytearray(48)
        p1[0]    = ID_D
        p1[1:33] = Y_dH
        p1[33]   = R_d
        p1[34]   = c_as_d
        send_msg(s, aes_enc_blocks(K_AS_D, bytes(p1)))
        recv_msg(s)

    PID = sha256(bytes([ID_D]) + m_d)

    wall_s = time.perf_counter() - t_wall
    cpu_s  = time.process_time()  - t_cpu
    results.append({'phase': 'Enrollment',
                    'wall_s': round(wall_s, 4),
                    'cpu_s':  round(cpu_s,  4),
                    'energy_j': energy(wall_s)})
    print(f"[DEV] Enrollment  wall={wall_s:.4f} s  cpu={cpu_s:.4f} s  "
          f"energy={energy(wall_s):.6f} J  PID={PID.hex()[:8]}")


def do_auth(round_num):
    global m_d, PID, k_gw_d, ts_1, last_ts2

    # ── Auth phase: timer covers pre-auth crypto + network round-trip ─────────
    t0_wall = time.perf_counter();  t0_cpu = time.process_time()

    R_d      = h_d
    Y_dH     = sha256(bytes([y_d]))                          # SHA256(y_d)
    mask_in  = bytes([R_d]) + m_d + PID + bytes([ts_1])
    mask     = sha256(mask_in)                               # SHA256(R_d||m_d||PID||ts_1)
    y_asd    = xor32(Y_dH, mask)
    auth_PID = sha256(bytes([ID_D]) + m_d)                  # SHA256(ID_D||m_d)
    payload  = auth_PID + y_asd + bytes([ts_1])

    rep = tcp_send_recv(AS_IP, PORT_AS_AUTH, payload)

    auth_wall = time.perf_counter() - t0_wall
    auth_cpu  = time.process_time()  - t0_cpu

    if len(rep) != 34 or rep[0] != 0xAC:
        print(f"[DEV] R{round_num} auth NACK")
        return False

    # ── Key Exchange: timer covers m_new derivation + PID rotation + network ──
    t1_wall = time.perf_counter();  t1_cpu = time.process_time()

    m_H  = bytes(rep[1:33])
    ts_2 = rep[33]
    diff = (ts_2 - last_ts2) % 256
    if diff == 0 or diff > 200:
        print(f"[DEV] R{round_num} stale ts_2={ts_2}")
        return False

    mh_in   = Y_dH + m_d + bytes([R_d, NODE_AS]) + auth_PID + bytes([ts_2])
    mh_mask = sha256(mh_in)                                  # SHA256(Y_dH||m_d||R_d||ID_AS||PID||ts_2)
    m_new   = xor32(m_H, mh_mask)
    k_gw_d  = sha256(bytes([R_d]) + m_new)                  # SHA256(R_d||m_new)
    m_d     = m_new
    PID     = sha256(bytes([ID_D]) + m_new)                 # SHA256(ID_D||m_new) — PID rotation
    last_ts2 = ts_2
    ts_1    = (ts_1 + 1) & 0xFF
    ke_blk  = bytearray(16);  ke_blk[0] = ts_1
    ke_pay  = PID + aes_enc_blocks(k_gw_d[:16], bytes(ke_blk))  # AES encrypt

    tcp_send_recv(GW_IP, PORT_GW_KEYEX, ke_pay)

    ke_wall = time.perf_counter() - t1_wall
    ke_cpu  = time.process_time()  - t1_cpu

    # ── Data phase: timer covers AES encrypt + network ────────────────────────
    t2_wall = time.perf_counter();  t2_cpu = time.process_time()

    sensor   = bytearray(16);  sensor[0] = 42
    data_pay = PID + aes_enc_blocks(k_gw_d[:16], bytes(sensor))  # AES encrypt
    tcp_send_recv(GW_IP, PORT_GW_DATA, data_pay)

    data_wall = time.perf_counter() - t2_wall
    data_cpu  = time.process_time()  - t2_cpu

    total_wall = auth_wall + ke_wall + data_wall
    total_cpu  = auth_cpu  + ke_cpu  + data_cpu

    print(f"[DEV] R{round_num} Auth  wall={auth_wall:.4f} s  cpu={auth_cpu:.4f} s  energy={energy(auth_wall):.6f} J")
    print(f"[DEV] R{round_num} KeyEx wall={ke_wall:.4f} s  cpu={ke_cpu:.4f} s  energy={energy(ke_wall):.6f} J")
    print(f"[DEV] R{round_num} Data  wall={data_wall:.4f} s  cpu={data_cpu:.4f} s  energy={energy(data_wall):.6f} J")
    print(f"[DEV] R{round_num} TOTAL wall={total_wall:.4f} s  cpu={total_cpu:.4f} s  energy={energy(total_wall):.6f} J  PID={PID.hex()[:8]}")

    results.append({'phase': f'Round{round_num}',
                    'auth_s':  round(auth_wall,  4), 'auth_energy_j':  energy(auth_wall),
                    'ke_s':    round(ke_wall,    4), 'ke_energy_j':    energy(ke_wall),
                    'data_s':  round(data_wall,  4), 'data_energy_j':  energy(data_wall),
                    'total_s': round(total_wall, 4), 'total_energy_j': energy(total_wall)})
    return True


if __name__ == '__main__':
    print("=" * 70)
    print("[DEV] Proposed scheme — hardware energy + latency measurement")
    print(f"[DEV] AS={AS_IP}  GW={GW_IP}")
    print(f"[DEV] Power assumption: {RPI_POWER_MW} mW  Rounds: {NUM_ROUNDS}")
    print("=" * 70)
    time.sleep(1.5)   # allow GW + AS time to start

    do_enrollment()
    time.sleep(0.3)

    for r in range(1, NUM_ROUNDS + 1):
        print(f"\n[DEV] === Round {r} ===")
        ok = do_auth(r)
        if not ok:
            print(f"[DEV] Round {r} FAILED — aborting")
            break
        time.sleep(0.3)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[DEV] ===== RESULTS SUMMARY =====")
    print(f"{'Phase':<20} {'Wall(s)':>10} {'CPU(s)':>10} {'Energy(J)':>12}")
    print("-" * 54)

    total_time_s   = 0.0
    total_energy_j = 0.0
    for r in results:
        if r['phase'] == 'Enrollment':
            print(f"{'Enrollment':<20} {r['wall_s']:>10.4f} {r['cpu_s']:>10.4f} {r['energy_j']:>12.6f}")
            total_time_s   += r['wall_s']
            total_energy_j += r['energy_j']
        else:
            print(f"{r['phase']+' Auth':<20} {r['auth_s']:>10.4f} {'':>10} {r['auth_energy_j']:>12.6f}")
            print(f"{r['phase']+' KeyEx':<20} {r['ke_s']:>10.4f} {'':>10} {r['ke_energy_j']:>12.6f}")
            print(f"{r['phase']+' Data':<20} {r['data_s']:>10.4f} {'':>10} {r['data_energy_j']:>12.6f}")
            print(f"{r['phase']+' TOTAL':<20} {r['total_s']:>10.4f} {'':>10} {r['total_energy_j']:>12.6f}")
            total_time_s   += r['total_s']
            total_energy_j += r['total_energy_j']
        print()

    print("=" * 54)
    print(f"{'GRAND TOTAL':<20} {total_time_s:>10.4f} {'':>10} {total_energy_j:>12.6f}")
    print(f"\nAvg per round (auth+ke+data): "
          f"{(total_time_s - results[0]['wall_s']) / NUM_ROUNDS:.4f} s  "
          f"{(total_energy_j - results[0]['energy_j']) / NUM_ROUNDS:.6f} J")
    print("=" * 70)
