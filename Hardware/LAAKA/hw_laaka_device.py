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

RPi 3B+ active power assumption: 1400 mW (single-core Python workload)
"""
import sys, os, time, socket, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import GW_IP as RA_IP, AS_IP as FOG_IP, NODE_DEV

RPI_POWER_MW = 1400
NUM_ROUNDS   = 3

HASH_LEN = 20
RAND_LEN = 20

# ── LAAKA protocol constants ──────────────────────────────────────────────────
r1_fog = bytes([0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,
                0x99,0xAA,0xBB,0xCC,0xDD,0xEE,0xFF,0x01,
                0x02,0x03,0x04,0x05])
TIDf_const = bytes([0xA1,0xB2,0xC3,0xD4,0xE5,0xF6,0x07,0x18,
                    0x29,0x3A,0x4B,0x5C,0x6D,0x7E,0x8F,0x90,
                    0x01,0x12,0x23,0x34])
FOG_IDENTITY_ID = 2

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
    return round(wall_s * RPI_POWER_MW, 3)

def tcp_send_recv(ip, port, payload: bytes) -> bytes:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        send_msg(s, payload)
        return recv_msg(s)


# ── Device state ──────────────────────────────────────────────────────────────
r2   = rand_bytes(RAND_LEN)
Ad   = h20(bytes([IDd]) + r2)
Af   = h20(bytes([FOG_IDENTITY_ID]) + r1_fog)  # pre-computed, matches Fog

TIDd = b'\x00' * HASH_LEN   # set during enrollment
TIDf = b'\x00' * HASH_LEN   # set during enrollment
Bk   = b'\x00' * HASH_LEN   # set during enrollment

results = []


def do_enrollment() -> None:
    global TIDd, TIDf, Bk
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()

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
    TIDf = bytes(plain[20:40])
    Af_ra = bytes(plain[40:60])   # should match our pre-computed Af
    Bk   = bytes(plain[60:80])

    if Af_ra != Af:
        print(f"[DEV] WARNING: RA's Af={Af_ra.hex()[:8]} differs from local Af={Af.hex()[:8]}")

    wall_s = time.perf_counter() - t_wall
    cpu_s  = time.process_time()  - t_cpu
    results.append({'phase': 'Enrollment',
                    'wall_ms': round(wall_s*1000, 2),
                    'cpu_ms':  round(cpu_s*1000, 2),
                    'energy_mj': energy(wall_s)})
    print(f"[DEV] Enrollment  wall={wall_s*1000:.2f} ms  cpu={cpu_s*1000:.2f} ms  "
          f"energy={energy(wall_s):.2f} mJ  TIDd={TIDd.hex()[:8]}")


def do_round(round_num: int) -> bool:
    """Run one full LAAKA authentication round: Auth → Ack → Data."""

    # ── Auth ─────────────────────────────────────────────────────────────────
    rd = rand_bytes(RAND_LEN)
    Td = int(time.time()) & 0xFF

    Cd = h20(bytes([Td]) + rd)
    Ed = xor20(rd, h20(Bk + Af))
    TIDd_new = xor20(TIDd, rd)
    Gd = h20(Ad + TIDd_new + Bk + rd)

    # AuthReq: TIDd(20)+Td(1)+Cd(20)+Ed(20)+Gd(20) = 81 B
    auth_req = TIDd + bytes([Td]) + Cd + Ed + Gd

    t0_wall = time.perf_counter();  t0_cpu = time.process_time()
    auth_rep = tcp_send_recv(FOG_IP, PORT_LAAKA_FOG_AUTH, auth_req)
    auth_wall = time.perf_counter() - t0_wall
    auth_cpu  = time.process_time()  - t0_cpu

    if len(auth_rep) != 82:
        print(f"[DEV] R{round_num} auth failed: bad reply len={len(auth_rep)}")
        return False

    # Parse AuthRep: TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20)
    recv_TIDf = bytes(auth_rep[0:20])
    Tf        = auth_rep[20]
    Ts        = auth_rep[21]
    recv_Cf   = bytes(auth_rep[22:42])
    recv_Ef   = bytes(auth_rep[42:62])
    recv_Gf   = bytes(auth_rep[62:82])

    # Step 6: Verify TIDf matches registration value
    if recv_TIDf != TIDf_const:
        print(f"[DEV] R{round_num} auth failed: TIDf mismatch")
        return False

    # Extract rf* = Ef XOR H20(TIDd_new)
    rf_star = xor20(recv_Ef, h20(TIDd_new))

    # Verify Cf* = H20(Tf || rf*)
    if h20(bytes([Tf]) + rf_star) != recv_Cf:
        print(f"[DEV] R{round_num} auth failed: Cf mismatch")
        return False

    # Compute SK* = H20(rd || rf* || Ts)
    SK = h20(rd + rf_star + bytes([Ts]))

    # Compute TIDf_new* = TIDf XOR rf*
    TIDf_new_star = xor20(TIDf_const, rf_star)

    # Verify Gf* = H20(TIDf_new* || Bk || rf* || SK || Ts)
    if h20(TIDf_new_star + Bk + rf_star + SK + bytes([Ts])) != recv_Gf:
        print(f"[DEV] R{round_num} auth failed: Gf mismatch")
        return False

    # ── Ack ──────────────────────────────────────────────────────────────────
    # Ack = H20(rf* || Bk || SK);  send TIDd_new(20) + Ack(20) = 40 B
    ack_val = h20(rf_star + Bk + SK)
    ack_msg = TIDd_new + ack_val

    t1_wall = time.perf_counter();  t1_cpu = time.process_time()
    tcp_send_recv(FOG_IP, PORT_LAAKA_FOG_ACK, ack_msg)
    ack_wall = time.perf_counter() - t1_wall
    ack_cpu  = time.process_time()  - t1_cpu

    # ── Data ─────────────────────────────────────────────────────────────────
    # TIDd_new(20) + AES(SK[0:16], sensor_data(16)) = 36 B
    sensor = bytearray(16);  sensor[0] = 42
    data_pkt = TIDd_new + aes_enc_blocks(SK[:16], bytes(sensor))

    t2_wall = time.perf_counter();  t2_cpu = time.process_time()
    tcp_send_recv(FOG_IP, PORT_LAAKA_FOG_DATA, data_pkt)
    data_wall = time.perf_counter() - t2_wall
    data_cpu  = time.process_time()  - t2_cpu

    total_wall = auth_wall + ack_wall + data_wall
    total_cpu  = auth_cpu  + ack_cpu  + data_cpu

    print(f"[DEV] R{round_num} Auth  wall={auth_wall*1000:.2f} ms  cpu={auth_cpu*1000:.2f} ms  "
          f"energy={energy(auth_wall):.2f} mJ")
    print(f"[DEV] R{round_num} Ack   wall={ack_wall*1000:.2f} ms  cpu={ack_cpu*1000:.2f} ms  "
          f"energy={energy(ack_wall):.2f} mJ")
    print(f"[DEV] R{round_num} Data  wall={data_wall*1000:.2f} ms  cpu={data_cpu*1000:.2f} ms  "
          f"energy={energy(data_wall):.2f} mJ")
    print(f"[DEV] R{round_num} TOTAL wall={total_wall*1000:.2f} ms  cpu={total_cpu*1000:.2f} ms  "
          f"energy={energy(total_wall):.2f} mJ  SK={SK.hex()[:8]}")

    results.append({
        'phase': f'Round{round_num}',
        'auth_ms':   round(auth_wall*1000, 2), 'auth_energy_mj':  energy(auth_wall),
        'ack_ms':    round(ack_wall*1000,  2), 'ack_energy_mj':   energy(ack_wall),
        'data_ms':   round(data_wall*1000, 2), 'data_energy_mj':  energy(data_wall),
        'total_ms':  round(total_wall*1000,2), 'total_energy_mj': energy(total_wall),
    })
    return True


if __name__ == '__main__':
    print("=" * 70)
    print("[DEV] LAAKA scheme — hardware energy + latency measurement")
    print(f"[DEV] RA={RA_IP}  FOG={FOG_IP}  IDd={IDd}")
    print(f"[DEV] Power assumption: {RPI_POWER_MW} mW  Rounds: {NUM_ROUNDS}")
    print("=" * 70)

    time.sleep(1.5)   # allow RA and Fog time to start

    do_enrollment()
    time.sleep(1.0)   # wait for RA→Fog forwarding to complete before first auth

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
    print(f"{'Phase':<22} {'Wall(ms)':>10} {'CPU(ms)':>10} {'Energy(mJ)':>12}")
    print("-" * 56)

    total_time_ms   = 0
    total_energy_mj = 0
    for r in results:
        if r['phase'] == 'Enrollment':
            print(f"{'Enrollment':<22} {r['wall_ms']:>10.2f} {r['cpu_ms']:>10.2f} {r['energy_mj']:>12.2f}")
            total_time_ms   += r['wall_ms']
            total_energy_mj += r['energy_mj']
        else:
            print(f"{r['phase']+' Auth':<22} {r['auth_ms']:>10.2f} {'':>10} {r['auth_energy_mj']:>12.2f}")
            print(f"{r['phase']+' Ack':<22} {r['ack_ms']:>10.2f} {'':>10} {r['ack_energy_mj']:>12.2f}")
            print(f"{r['phase']+' Data':<22} {r['data_ms']:>10.2f} {'':>10} {r['data_energy_mj']:>12.2f}")
            print(f"{r['phase']+' TOTAL':<22} {r['total_ms']:>10.2f} {'':>10} {r['total_energy_mj']:>12.2f}")
            total_time_ms   += r['total_ms']
            total_energy_mj += r['total_energy_mj']
        print()

    print("=" * 56)
    print(f"{'GRAND TOTAL':<22} {total_time_ms:>10.2f} {'':>10} {total_energy_mj:>12.2f}")
    if len(results) > 1:
        num_r = len(results) - 1
        print(f"\nAvg per round (auth+ack+data): "
              f"{(total_time_ms - results[0]['wall_ms']) / num_r:.2f} ms  "
              f"{(total_energy_mj - results[0]['energy_mj']) / num_r:.2f} mJ")
    print("=" * 70)
