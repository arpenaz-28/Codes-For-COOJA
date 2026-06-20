#!/usr/bin/env python3
"""
Hardware measurement — Proposed Scheme (Device role)
Runs on: Pi (192.168.1.113)

Phases measured: Enrollment + 3 normal Auth rounds (Auth → KeyEx → Data)
Metrics per phase:
  - wall_ms  : wall-clock latency
  - cpu_ms   : CPU time (time.process_time)
  - energy_mj: estimated energy = wall_s × RPi_power_mW

RPi 4B active power assumption: 3800 mW (single-core Python workload)
"""
import json, sys, os, time, socket
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import (AS_IP, GW_IP, PORT_AS_ENROLL, PORT_AS_AUTH,
                    PORT_GW_KEYEX, PORT_GW_DATA, NODE_DEV, NODE_AS)

RPI_POWER_MW = 3800   # mW — RPi 4B typical single-core active
NUM_ROUNDS   = 3
NUM_WARMUP   = 1    # warm-up rounds before measurement (discarded)

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

    # ══ AUTH + KEY EXCHANGE — single outer timer (this is ONE protocol round) ══
    t_ak_wall = time.perf_counter();  t_ak_cpu = time.process_time()

    # ── Auth sub-phase ────────────────────────────────────────────────────────
    t0_wall = time.perf_counter();  t0_cpu = time.process_time()

    R_d      = h_d
    Y_dH     = sha256(bytes([y_d]))
    mask_in  = bytes([R_d]) + m_d + PID + bytes([ts_1])
    mask     = sha256(mask_in)
    y_asd    = xor32(Y_dH, mask)
    auth_PID = sha256(bytes([ID_D]) + m_d)
    payload  = auth_PID + y_asd + bytes([ts_1])
    rep      = tcp_send_recv(AS_IP, PORT_AS_AUTH, payload)

    auth_wall = time.perf_counter() - t0_wall
    auth_cpu  = time.process_time()  - t0_cpu

    if len(rep) != 34 or rep[0] != 0xAC:
        print(f"[DEV] R{round_num} auth NACK")
        return False

    # ── Key Exchange sub-phase ────────────────────────────────────────────────
    t1_wall = time.perf_counter();  t1_cpu = time.process_time()

    m_H  = bytes(rep[1:33])
    ts_2 = rep[33]
    diff = (ts_2 - last_ts2) % 256
    if diff == 0 or diff > 200:
        print(f"[DEV] R{round_num} stale ts_2={ts_2}")
        return False

    mh_in   = Y_dH + m_d + bytes([R_d, NODE_AS]) + auth_PID + bytes([ts_2])
    mh_mask = sha256(mh_in)
    m_new   = xor32(m_H, mh_mask)
    k_gw_d  = sha256(bytes([R_d]) + m_new)
    m_d     = m_new
    PID     = sha256(bytes([ID_D]) + m_new)   # PID rotation
    last_ts2 = ts_2
    ts_1    = (ts_1 + 1) & 0xFF
    ke_blk  = bytearray(16);  ke_blk[0] = ts_1
    ke_pay  = PID + aes_enc_blocks(k_gw_d[:16], bytes(ke_blk))
    tcp_send_recv(GW_IP, PORT_GW_KEYEX, ke_pay)

    ke_wall = time.perf_counter() - t1_wall
    ke_cpu  = time.process_time()  - t1_cpu

    # End outer Auth+KeyEx timer
    ak_wall = time.perf_counter() - t_ak_wall
    ak_cpu  = time.process_time()  - t_ak_cpu

    # ── Data phase (separate) ─────────────────────────────────────────────────
    t2_wall = time.perf_counter();  t2_cpu = time.process_time()

    sensor   = bytearray(16);  sensor[0] = 42
    data_pay = PID + aes_enc_blocks(k_gw_d[:16], bytes(sensor))
    tcp_send_recv(GW_IP, PORT_GW_DATA, data_pay)

    data_wall = time.perf_counter() - t2_wall
    data_cpu  = time.process_time()  - t2_cpu

    total_wall = ak_wall + data_wall
    total_cpu  = ak_cpu  + data_cpu

    print(f"[DEV] R{round_num} Auth+KeyEx  wall={ak_wall:.4f} s  cpu={ak_cpu:.4f} s  energy={energy(ak_wall):.6f} J")
    print(f"[DEV] R{round_num}   +- Auth    wall={auth_wall:.4f} s  cpu={auth_cpu:.4f} s  energy={energy(auth_wall):.6f} J")
    print(f"[DEV] R{round_num}   +- KeyEx   wall={ke_wall:.4f} s  cpu={ke_cpu:.4f} s  energy={energy(ke_wall):.6f} J")
    print(f"[DEV] R{round_num} Data        wall={data_wall:.4f} s  cpu={data_cpu:.4f} s  energy={energy(data_wall):.6f} J")
    print(f"[DEV] R{round_num} TOTAL       wall={total_wall:.4f} s  cpu={total_cpu:.4f} s  energy={energy(total_wall):.6f} J  PID={PID.hex()[:8]}")

    results.append({'phase': f'Round{round_num}',
                    'ak_s':    round(ak_wall,   4), 'ak_energy_j':   energy(ak_wall),
                    'auth_s':  round(auth_wall,  4), 'auth_energy_j': energy(auth_wall),
                    'ke_s':    round(ke_wall,    4), 'ke_energy_j':   energy(ke_wall),
                    'data_s':  round(data_wall,  4), 'data_energy_j': energy(data_wall),
                    'total_s': round(total_wall, 4), 'total_energy_j': energy(total_wall)})
    return True


if __name__ == '__main__':
    print("=" * 70)
    print("[DEV] Proposed scheme — hardware energy + latency measurement")
    print(f"[DEV] AS={AS_IP}  GW={GW_IP}")
    print(f"[DEV] Power assumption: {RPI_POWER_MW} mW  Rounds: {NUM_ROUNDS}  Warmup: {NUM_WARMUP}")
    print("=" * 70)
    time.sleep(1.5)   # allow GW + AS time to start

    do_enrollment()
    time.sleep(0.3)

    enroll_rec = results[0]   # save before warm-up pollutes list

    print(f"\n[DEV] === Warm-up ({NUM_WARMUP} round, discarded) ===")
    for _ in range(NUM_WARMUP):
        ok = do_auth(0)
        if not ok:
            raise SystemExit("Warm-up failed — aborting")
        time.sleep(0.3)

    results.clear()
    results.append(enroll_rec)   # restore enrollment

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
            print(f"{'Enrollment':<24} {r['wall_s']:>10.4f} {r['cpu_s']:>10.4f} {r['energy_j']:>12.6f}")
            total_time_s   += r['wall_s']
            total_energy_j += r['energy_j']
        else:
            print(f"{r['phase']+' Auth+KeyEx':<24} {r['ak_s']:>10.4f} {'':>10} {r['ak_energy_j']:>12.6f}")
            print(f"{'  +- Auth':<24} {r['auth_s']:>10.4f} {'':>10} {r['auth_energy_j']:>12.6f}")
            print(f"{'  +- KeyEx':<24} {r['ke_s']:>10.4f} {'':>10} {r['ke_energy_j']:>12.6f}")
            print(f"{r['phase']+' Data':<24} {r['data_s']:>10.4f} {'':>10} {r['data_energy_j']:>12.6f}")
            print(f"{r['phase']+' TOTAL':<24} {r['total_s']:>10.4f} {'':>10} {r['total_energy_j']:>12.6f}")
            total_time_s   += r['total_s']
            total_energy_j += r['total_energy_j']
        print()

    print("=" * 58)
    print(f"{'GRAND TOTAL':<24} {total_time_s:>10.4f} {'':>10} {total_energy_j:>12.6f}")
    num_r = len(results) - 1
    if num_r > 0:
        avg_ak  = sum(r['ak_s']        for r in results if r['phase'] != 'Enrollment') / num_r
        avg_ake = sum(r['ak_energy_j'] for r in results if r['phase'] != 'Enrollment') / num_r
        avg_tot = (total_time_s - results[0]['wall_s']) / num_r
        avg_tote= (total_energy_j - results[0]['energy_j']) / num_r
        print(f"\nAvg Auth+KeyEx per round : {avg_ak:.4f} s  {avg_ake:.6f} J")
        print(f"Avg total    per round   : {avg_tot:.4f} s  {avg_tote:.6f} J")
    print("=" * 70)

    # ── Save results to JSON for collection by orchestrator ───────────────
    if num_r > 0:
        out = {
            'enrollment': results[0],
            'rounds':     [r for r in results if r['phase'] != 'Enrollment'],
            'summary': {
                'ak_energy_sum_j':    round(sum(r['ak_energy_j']   for r in results if r['phase'] != 'Enrollment'), 6),
                'ak_time_sum_s':      round(sum(r['ak_s']           for r in results if r['phase'] != 'Enrollment'), 6),
                'total_energy_sum_j': round(sum(r['total_energy_j'] for r in results if r['phase'] != 'Enrollment'), 6),
                'total_time_sum_s':   round(sum(r['total_s']        for r in results if r['phase'] != 'Enrollment'), 6),
                'avg_ak_energy_j':    round(avg_ake, 6),
                'avg_ak_time_s':      round(avg_ak,  6),
            }
        }
        with open('proposed_hw_run.json', 'w') as f:
            json.dump(out, f, indent=2)
        print("[DEV] Results saved to proposed_hw_run.json")
