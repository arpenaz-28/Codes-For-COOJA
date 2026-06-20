#!/usr/bin/env python3
"""
Hardware measurement — LAAKA Scheme (Device role)
Runs on: Pi RPi (192.168.1.113)

Phases measured: Enrollment + NUM_ROUNDS × (Auth + Ack + Data)

LAAKA protocol (Das et al., COMSNETS 2026):
  Enrollment:  Device → RA  (32 B send, 80 B recv)
  Auth:        Device → Fog (81 B send, 82 B recv) — full key agreement
  Ack:         Device → Fog (40 B send, 2 B recv)  — mutual auth confirmation
  Data:        Device → Fog (36 B send, 1 B recv)  — encrypted sensor data

Metrics per phase:
  wall_ms   : wall-clock latency (includes network round-trip)
  cpu_ms    : CPU-only time (time.process_time)
  energy_mj : wall_s × RPi_power_mW  (1400 mW)

RPi 4B active power assumption: 3800 mW (single-core Python workload)
"""
import json, sys, os, time, socket, hashlib
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import GW_IP as RA_IP, AS_IP as FOG_IP, NODE_DEV

RPI_POWER_MW = 3800
NUM_ROUNDS   = 3
NUM_WARMUP   = 1    # warm-up rounds before measurement (discarded)

HASH_LEN = 20
RAND_LEN = 20

# ── LAAKA protocol constants ──────────────────────────────────────────────────
# Af and TIDf are NOT known a priori — the device learns them from the RA during
# its own registration (§4.2.2), after the fog has registered (§4.2.1).
K_RA_D = K_AS_D   # same byte values as K_AS_D in common.py

PORT_LAAKA_RA_REG   = 5006
PORT_LAAKA_FOG_AUTH = 5008
PORT_LAAKA_FOG_ACK  = 5009
PORT_LAAKA_FOG_DATA = 5010

IDd = NODE_DEV


def h20(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()[:HASH_LEN]

def xor20(a: bytes, b: bytes) -> bytes:
    assert len(a) == HASH_LEN and len(b) == HASH_LEN
    return bytes(x ^ y for x, y in zip(a, b))

def energy(wall_s: float) -> float:
    return round(wall_s * (RPI_POWER_MW / 1000), 6)   # Watts × seconds = Joules

def tcp_send_recv(ip, port, payload: bytes) -> bytes:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        send_msg(s, payload)
        return recv_msg(s)


# ── Device state ──────────────────────────────────────────────────────────────
Af   = b'\x00' * HASH_LEN   # received from RA during enrollment (fog's Af)

# r2 and Ad are generated inside do_enrollment() so they are fully timed
r2   = b'\x00' * RAND_LEN
Ad   = b'\x00' * HASH_LEN

TIDd = b'\x00' * HASH_LEN   # set during enrollment
TIDf = b'\x00' * HASH_LEN   # set during enrollment
Bk   = b'\x00' * HASH_LEN   # set during enrollment

results = []


def do_enrollment() -> None:
    global r2, Ad, TIDd, TIDf, Bk, Af
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()

    # r2 and Ad computed inside timer — enrollment cost includes key derivation
    r2 = rand_bytes(RAND_LEN)
    Ad = h20(bytes([IDd]) + r2)   # H20(IDd || r2)

    # Build: AES(K_RA_D, [IDd(1)|Ad(20)|pad(11)]) = 32 B
    req = bytearray(32)
    req[0]    = IDd
    req[1:21] = Ad
    rep = tcp_send_recv(RA_IP, PORT_LAAKA_RA_REG, aes_enc_blocks(K_RA_D, bytes(req)))

    if len(rep) != 80:
        raise RuntimeError(f"Enrollment reply wrong length {len(rep)}, expected 80")

    # Decrypt: AES(K_RA_D, [TIDd(20)|TIDf(20)|Af_ra(20)|Bk(20)]) = 80 B
    plain = aes_dec_blocks(K_RA_D, rep)
    TIDd = bytes(plain[0:20])
    TIDf = bytes(plain[20:40])   # fog's temporary identifier, issued by RA
    Af   = bytes(plain[40:60])   # fog's Af, conveyed by RA (device never knows r1)
    Bk   = bytes(plain[60:80])

    wall_s = time.perf_counter() - t_wall
    cpu_s  = time.process_time()  - t_cpu
    results.append({'phase': 'Enrollment',
                    'wall_s': round(wall_s, 4),
                    'cpu_s':  round(cpu_s, 4),
                    'energy_j': energy(wall_s)})
    print(f"[DEV] Enrollment  wall={wall_s:.4f} s  cpu={cpu_s:.4f} s  "
          f"energy={energy(wall_s):.6f} J  TIDd={TIDd.hex()[:8]}")


def do_round(round_num: int) -> bool:
    """Run one full LAAKA round: (Auth + Ack) + Data.

    Auth+Ack is ONE protocol round (key establishment). Data is separate.
    Outer timer wraps Auth+Ack; sub-timers give breakdown.
    """

    # ══ AUTH + ACK — single outer timer (one complete key establishment round) ══
    t_aa_wall = time.perf_counter();  t_aa_cpu = time.process_time()

    # ── Auth sub-phase ────────────────────────────────────────────────────────
    t0_wall = time.perf_counter();  t0_cpu = time.process_time()

    rd = rand_bytes(RAND_LEN)
    Td = int(time.time()) & 0xFF
    Cd       = h20(bytes([Td]) + rd)
    Ed       = xor20(rd, h20(Bk + Af))
    TIDd_new = xor20(TIDd, rd)
    Gd       = h20(Ad + TIDd_new + Bk + rd)
    auth_req = TIDd + bytes([Td]) + Cd + Ed + Gd
    auth_rep = tcp_send_recv(FOG_IP, PORT_LAAKA_FOG_AUTH, auth_req)

    auth_wall = time.perf_counter() - t0_wall
    auth_cpu  = time.process_time()  - t0_cpu

    if len(auth_rep) != 82:
        print(f"[DEV] R{round_num} auth failed: bad reply len={len(auth_rep)}")
        return False

    # ── Ack sub-phase ─────────────────────────────────────────────────────────
    t1_wall = time.perf_counter();  t1_cpu = time.process_time()

    recv_TIDf = bytes(auth_rep[0:20])
    Tf        = auth_rep[20];  Ts = auth_rep[21]
    recv_Cf   = bytes(auth_rep[22:42])
    recv_Ef   = bytes(auth_rep[42:62])
    recv_Gf   = bytes(auth_rep[62:82])

    if recv_TIDf != TIDf:
        print(f"[DEV] R{round_num} auth failed: TIDf mismatch");  return False

    rf_star = xor20(recv_Ef, h20(TIDd_new))
    if h20(bytes([Tf]) + rf_star) != recv_Cf:
        print(f"[DEV] R{round_num} auth failed: Cf mismatch");  return False
    SK = h20(rd + rf_star + bytes([Ts]))
    TIDf_new_star = xor20(TIDf, rf_star)
    if h20(TIDf_new_star + Bk + rf_star + SK + bytes([Ts])) != recv_Gf:
        print(f"[DEV] R{round_num} auth failed: Gf mismatch");  return False

    ack_val = h20(rf_star + Bk + SK)
    tcp_send_recv(FOG_IP, PORT_LAAKA_FOG_ACK, TIDd_new + ack_val)

    ack_wall = time.perf_counter() - t1_wall
    ack_cpu  = time.process_time()  - t1_cpu

    # End outer Auth+Ack timer
    aa_wall = time.perf_counter() - t_aa_wall
    aa_cpu  = time.process_time()  - t_aa_cpu

    # ── Data phase (separate) ─────────────────────────────────────────────────
    t2_wall = time.perf_counter();  t2_cpu = time.process_time()

    sensor   = bytearray(16);  sensor[0] = 42
    data_pkt = TIDd_new + aes_enc_blocks(SK[:16], bytes(sensor))
    tcp_send_recv(FOG_IP, PORT_LAAKA_FOG_DATA, data_pkt)

    data_wall = time.perf_counter() - t2_wall
    data_cpu  = time.process_time()  - t2_cpu

    total_wall = aa_wall + data_wall
    total_cpu  = aa_cpu  + data_cpu

    print(f"[DEV] R{round_num} Auth+Ack    wall={aa_wall:.4f} s  cpu={aa_cpu:.4f} s  energy={energy(aa_wall):.6f} J  SK={SK.hex()[:8]}")
    print(f"[DEV] R{round_num}   +- Auth    wall={auth_wall:.4f} s  cpu={auth_cpu:.4f} s  energy={energy(auth_wall):.6f} J")
    print(f"[DEV] R{round_num}   +- Ack     wall={ack_wall:.4f} s  cpu={ack_cpu:.4f} s  energy={energy(ack_wall):.6f} J")
    print(f"[DEV] R{round_num} Data        wall={data_wall:.4f} s  cpu={data_cpu:.4f} s  energy={energy(data_wall):.6f} J")
    print(f"[DEV] R{round_num} TOTAL       wall={total_wall:.4f} s  cpu={total_cpu:.4f} s  energy={energy(total_wall):.6f} J")

    results.append({
        'phase': f'Round{round_num}',
        'aa_s':    round(aa_wall,   4), 'aa_energy_j':   energy(aa_wall),
        'auth_s':  round(auth_wall,  4), 'auth_energy_j': energy(auth_wall),
        'ack_s':   round(ack_wall,   4), 'ack_energy_j':  energy(ack_wall),
        'data_s':  round(data_wall,  4), 'data_energy_j': energy(data_wall),
        'total_s': round(total_wall, 4), 'total_energy_j': energy(total_wall),
    })
    return True


if __name__ == '__main__':
    print("=" * 70)
    print("[DEV] LAAKA scheme — hardware energy + latency measurement")
    print(f"[DEV] RA={RA_IP}  FOG={FOG_IP}  IDd={IDd}")
    print(f"[DEV] Power assumption: {RPI_POWER_MW} mW  Rounds: {NUM_ROUNDS}  Warmup: {NUM_WARMUP}")
    print("=" * 70)

    time.sleep(1.5)   # allow RA and Fog time to start

    do_enrollment()
    time.sleep(1.0)   # wait for RA→Fog forwarding to complete before first auth

    enroll_rec = results[0]   # save before warm-up pollutes list

    print(f"\n[DEV] === Warm-up ({NUM_WARMUP} round, discarded) ===")
    for _ in range(NUM_WARMUP):
        ok = do_round(0)
        if not ok:
            raise SystemExit("Warm-up failed — aborting")
        time.sleep(0.3)

    results.clear()
    results.append(enroll_rec)   # restore enrollment

    for r in range(1, NUM_ROUNDS + 1):
        print(f"\n[DEV] === Round {r} ===")
        ok = do_round(r)
        if not ok:
            print(f"[DEV] Round {r} FAILED — aborting")
            break
        time.sleep(0.3)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[DEV] ===== RESULTS SUMMARY =====")
    print(f"{'Phase':<22} {'Wall(s)':>10} {'CPU(s)':>10} {'Energy(J)':>12}")
    print("-" * 56)

    total_time_s   = 0.0
    total_energy_j = 0.0
    for r in results:
        if r['phase'] == 'Enrollment':
            print(f"{'Enrollment':<24} {r['wall_s']:>10.4f} {r['cpu_s']:>10.4f} {r['energy_j']:>12.6f}")
            total_time_s   += r['wall_s']
            total_energy_j += r['energy_j']
        else:
            print(f"{r['phase']+' Auth+Ack':<24} {r['aa_s']:>10.4f} {'':>10} {r['aa_energy_j']:>12.6f}")
            print(f"{'  +- Auth':<24} {r['auth_s']:>10.4f} {'':>10} {r['auth_energy_j']:>12.6f}")
            print(f"{'  +- Ack':<24} {r['ack_s']:>10.4f} {'':>10} {r['ack_energy_j']:>12.6f}")
            print(f"{r['phase']+' Data':<24} {r['data_s']:>10.4f} {'':>10} {r['data_energy_j']:>12.6f}")
            print(f"{r['phase']+' TOTAL':<24} {r['total_s']:>10.4f} {'':>10} {r['total_energy_j']:>12.6f}")
            total_time_s   += r['total_s']
            total_energy_j += r['total_energy_j']
        print()

    print("=" * 58)
    print(f"{'GRAND TOTAL':<24} {total_time_s:>10.4f} {'':>10} {total_energy_j:>12.6f}")
    num_r = len(results) - 1
    if num_r > 0:
        avg_aa  = sum(r['aa_s']        for r in results if r['phase'] != 'Enrollment') / num_r
        avg_aae = sum(r['aa_energy_j'] for r in results if r['phase'] != 'Enrollment') / num_r
        avg_tot = (total_time_s - results[0]['wall_s']) / num_r
        avg_tote= (total_energy_j - results[0]['energy_j']) / num_r
        print(f"\nAvg Auth+Ack  per round : {avg_aa:.4f} s  {avg_aae:.6f} J")
        print(f"Avg total     per round : {avg_tot:.4f} s  {avg_tote:.6f} J")
    print("=" * 70)

    # ── Save results to JSON for collection by orchestrator ───────────────
    if num_r > 0:
        out = {
            'enrollment': results[0],
            'rounds':     [r for r in results if r['phase'] != 'Enrollment'],
            'summary': {
                'aa_energy_sum_j':    round(sum(r['aa_energy_j']   for r in results if r['phase'] != 'Enrollment'), 6),
                'aa_time_sum_s':      round(sum(r['aa_s']           for r in results if r['phase'] != 'Enrollment'), 6),
                'total_energy_sum_j': round(sum(r['total_energy_j'] for r in results if r['phase'] != 'Enrollment'), 6),
                'total_time_sum_s':   round(sum(r['total_s']        for r in results if r['phase'] != 'Enrollment'), 6),
                'avg_aa_energy_j':    round(avg_aae, 6),
                'avg_aa_time_s':      round(avg_aa,  6),
            }
        }
        with open('laaka_hw_run.json', 'w') as f:
            json.dump(out, f, indent=2)
        print("[DEV] Results saved to laaka_hw_run.json")
