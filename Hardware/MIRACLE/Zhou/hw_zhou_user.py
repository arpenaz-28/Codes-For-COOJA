#!/usr/bin/env python3
"""
Hardware measurement — Zhou Scheme (User role)
Runs on: Apex (192.168.1.132)   [measurement target]

In Zhou's scheme the "User" is a healthcare device (doctor/patient).

Phases measured: Registration + NUM_ROUNDS × (Auth + Data)

  Registration (one-time):
    Step 1 — send [ID_I|ki] to GW, receive DIDi
    Step 2 — query GW for SIDn of target sensor node
    (Both steps within a single timer — they are setup-time operations)

  Auth per round (= full M1→M4 exchange):
    Build M1 = [Ni(32)|α(32)|DIDi(32)|SIDn(32)] = 128 B
    Send M1 to GW; GW internally does M2/M3 with SN
    Receive M4 = [SKi(96)|λ(32)] = 128 B, verify λ, extract SK/DIDi_new/SIDn_new
    This is the Auth+KeyEx equivalent — one round-trip from User's perspective.

  Data per round (separate timer):
    Send DIDi_new + AES(SK[:16], sensor[16]) = 48 B to GW, receive ACK

Metrics per phase:
  wall_s  : wall-clock latency (crypto + full TCP round-trip)
  cpu_s   : CPU-only time (time.process_time)
  energy_j: wall_s × 1.4 W  (1400 mW RPi 3B+ single-core active)

RPi 4B active power assumption: 3800 mW
"""
import json, sys, os, time, socket
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import (GW_IP, PORT_ZHOU_USER_REG, PORT_ZHOU_AUTH,
                    PORT_ZHOU_DATA, NODE_DEV, NODE_SN)

RPI_POWER_MW = 3800
NUM_ROUNDS   = 3
NUM_WARMUP   = 1    # warm-up rounds before measurement (discarded)

# User state
ID_I    = NODE_DEV
BIO_INPUT = bytes([ID_I]) + b'biometric-key'         # biometric sample (FE input)
ki      = b'\x00' * 32                                # derived via fuzzy extractor (FE)
DIDi    = b'\x00' * 32
SIDn    = b'\x00' * 32
SK      = b'\x00' * 32
results = []


def h3(x: bytes) -> bytes:
    return sha256(x + b'\x00') + sha256(x + b'\x01') + sha256(x + b'\x02')

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

def tcp_send_recv(ip, port, payload: bytes) -> bytes:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        send_msg(s, payload)
        return recv_msg(s)

def energy(wall_s: float) -> float:
    return round(wall_s * (RPI_POWER_MW / 1000), 6)   # W × s = J


# ── Registration ──────────────────────────────────────────────────────────────

def do_registration() -> None:
    global DIDi, SIDn, ki
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()

    # FE #1: fuzzy extractor generates biometric key ki (ECC P-256 scalar mult)
    ki = fe_p256(BIO_INPUT)

    # Step 1: send [ID_I(1)|ki(32)|0×15] = 48 B encrypted, receive DIDi
    p0 = bytearray(48)
    p0[0]    = ID_I
    p0[1:33] = ki
    rep  = tcp_send_recv(GW_IP, PORT_ZHOU_USER_REG, aes_enc_blocks(K_GW_U, bytes(p0)))
    DIDi = bytes(aes_dec_blocks(K_GW_U, rep)[0:32])

    # Step 2: query GW for current SIDn of target sensor node
    q = bytearray(16)
    q[0] = 0xFF     # query flag
    q[1] = NODE_SN
    rep2 = tcp_send_recv(GW_IP, PORT_ZHOU_USER_REG, aes_enc_blocks(K_GW_U, bytes(q)))
    SIDn = bytes(aes_dec_blocks(K_GW_U, rep2)[0:32])

    wall_s = time.perf_counter() - t_wall
    cpu_s  = time.process_time()  - t_cpu
    results.append({'phase':    'Registration',
                    'wall_s':   round(wall_s, 4),
                    'cpu_s':    round(cpu_s,  4),
                    'energy_j': energy(wall_s)})
    print(f"[USR-ZHOU] Registration  wall={wall_s:.4f} s  cpu={cpu_s:.4f} s  "
          f"energy={energy(wall_s):.6f} J  DIDi={DIDi.hex()[:8]}  SIDn={SIDn.hex()[:8]}")


# ── Authentication + Data round ───────────────────────────────────────────────

def do_round(round_num: int) -> bool:
    global DIDi, SIDn, SK, ki

    # ══ AUTH — outer timer covers full M1→M4 round-trip ═════════════════════
    t_auth_wall = time.perf_counter();  t_auth_cpu = time.process_time()

    # FE #2: user re-generates biometric key ki each session (ECC P-256 scalar mult)
    ki = fe_p256(BIO_INPUT)

    # Build M1
    bi_new = rand_bytes(32)
    Ni     = xor_bytes(bi_new, sha256(ki))
    alpha  = sha256(bi_new + ki + DIDi + SIDn)
    m1     = Ni + alpha + DIDi + SIDn   # 128 B

    try:
        m4 = tcp_send_recv(GW_IP, PORT_ZHOU_AUTH, m1)
    except Exception as e:
        print(f"[USR-ZHOU] R{round_num} M1 send failed: {e}")
        return False

    if len(m4) != 128 or m4[0] == 0xFF:
        print(f"[USR-ZHOU] R{round_num} Auth FAILED  len={len(m4)}  first={m4[0]:02x}")
        return False

    # Decode M4: (SIDn_new || SK' || DIDi_new) = SKi XOR H3(ki)
    SKi     = bytes(m4[0:96])
    lam     = bytes(m4[96:128])
    decoded  = xor_bytes(SKi, h3(ki))
    SIDn_new = decoded[0:32]
    SK_new   = decoded[32:64]
    DIDi_new = decoded[64:96]

    # Verify λ = H(SK' || DIDi_old || ki || DIDi_new || SIDn_new)
    lam_p = sha256(SK_new + DIDi + ki + DIDi_new + SIDn_new)
    if lam_p != lam:
        print(f"[USR-ZHOU] R{round_num} λ mismatch — Auth FAILED")
        return False

    # Commit new state
    DIDi_old = DIDi   # keep for potential debug logging
    DIDi = DIDi_new
    SK   = SK_new
    SIDn = SIDn_new

    auth_wall = time.perf_counter() - t_auth_wall
    auth_cpu  = time.process_time()  - t_auth_cpu

    # ══ DATA phase — separate timer ══════════════════════════════════════════
    t_data_wall = time.perf_counter();  t_data_cpu = time.process_time()

    sensor   = bytearray(16);  sensor[0] = 42
    data_pkt = DIDi + aes_enc_blocks(SK[:16], bytes(sensor))   # 32 + 16 = 48 B
    tcp_send_recv(GW_IP, PORT_ZHOU_DATA, data_pkt)

    data_wall = time.perf_counter() - t_data_wall
    data_cpu  = time.process_time()  - t_data_cpu

    total_wall = auth_wall + data_wall
    total_cpu  = auth_cpu  + data_cpu

    print(f"[USR-ZHOU] R{round_num} Auth        wall={auth_wall:.4f} s  "
          f"cpu={auth_cpu:.4f} s  energy={energy(auth_wall):.6f} J  SK={SK.hex()[:8]}")
    print(f"[USR-ZHOU] R{round_num} Data        wall={data_wall:.4f} s  "
          f"cpu={data_cpu:.4f} s  energy={energy(data_wall):.6f} J")
    print(f"[USR-ZHOU] R{round_num} TOTAL       wall={total_wall:.4f} s  "
          f"cpu={total_cpu:.4f} s  energy={energy(total_wall):.6f} J  DIDi={DIDi.hex()[:8]}")

    results.append({'phase':         f'Round{round_num}',
                    'auth_s':         round(auth_wall,  4),
                    'auth_energy_j':  energy(auth_wall),
                    'data_s':         round(data_wall,  4),
                    'data_energy_j':  energy(data_wall),
                    'total_s':        round(total_wall, 4),
                    'total_energy_j': energy(total_wall)})
    return True


if __name__ == '__main__':
    print("=" * 70)
    print("[USR-ZHOU] Zhou scheme — hardware energy + latency measurement")
    print(f"[USR-ZHOU] GW={GW_IP}  ID_I={ID_I}")
    print(f"[USR-ZHOU] Power assumption: {RPI_POWER_MW} mW  Rounds: {NUM_ROUNDS}  Warmup: {NUM_WARMUP}")
    print("=" * 70)

    time.sleep(2.0)   # allow GW + SN to start and SN to register

    do_registration()
    time.sleep(0.5)

    enroll_rec = results[0]   # save before warm-up pollutes list

    print(f"\n[USR-ZHOU] === Warm-up ({NUM_WARMUP} round, discarded) ===")
    for _ in range(NUM_WARMUP):
        ok = do_round(0)
        if not ok:
            raise SystemExit("Warm-up failed — aborting")
        time.sleep(0.3)

    results.clear()
    results.append(enroll_rec)   # restore registration record

    for r in range(1, NUM_ROUNDS + 1):
        print(f"\n[USR-ZHOU] === Round {r} ===")
        ok = do_round(r)
        if not ok:
            print(f"[USR-ZHOU] Round {r} FAILED — aborting")
            break
        time.sleep(0.3)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[USR-ZHOU] ===== RESULTS SUMMARY =====")
    print(f"{'Phase':<24} {'Wall(s)':>10} {'CPU(s)':>10} {'Energy(J)':>12}")
    print("-" * 58)

    total_time_s   = 0.0
    total_energy_j = 0.0
    for r in results:
        if r['phase'] == 'Registration':
            print(f"{'Registration':<24} {r['wall_s']:>10.4f} {r['cpu_s']:>10.4f} {r['energy_j']:>12.6f}")
            total_time_s   += r['wall_s']
            total_energy_j += r['energy_j']
        else:
            print(f"{r['phase']+' Auth':<24} {r['auth_s']:>10.4f} {'':>10} {r['auth_energy_j']:>12.6f}")
            print(f"{r['phase']+' Data':<24} {r['data_s']:>10.4f} {'':>10} {r['data_energy_j']:>12.6f}")
            print(f"{r['phase']+' TOTAL':<24} {r['total_s']:>10.4f} {'':>10} {r['total_energy_j']:>12.6f}")
            total_time_s   += r['total_s']
            total_energy_j += r['total_energy_j']
        print()

    print("=" * 58)
    print(f"{'GRAND TOTAL':<24} {total_time_s:>10.4f} {'':>10} {total_energy_j:>12.6f}")
    num_r = len(results) - 1
    if num_r > 0:
        avg_auth  = sum(r['auth_s']        for r in results if r['phase'] != 'Registration') / num_r
        avg_authe = sum(r['auth_energy_j'] for r in results if r['phase'] != 'Registration') / num_r
        avg_data  = sum(r['data_s']        for r in results if r['phase'] != 'Registration') / num_r
        avg_datae = sum(r['data_energy_j'] for r in results if r['phase'] != 'Registration') / num_r
        avg_tot   = (total_time_s   - results[0]['wall_s'])   / num_r
        avg_tote  = (total_energy_j - results[0]['energy_j']) / num_r
        print(f"\nAvg Auth(M1->M4) per round : {avg_auth:.4f} s  {avg_authe:.6f} J")
        print(f"Avg Data        per round : {avg_data:.4f} s  {avg_datae:.6f} J")
        print(f"Avg total       per round : {avg_tot:.4f} s  {avg_tote:.6f} J")
    print("=" * 70)

    # ── Save results to JSON for collection by orchestrator ───────────────
    if num_r > 0:
        out = {
            'enrollment': results[0],
            'rounds':     [r for r in results if r['phase'] != 'Registration'],
            'summary': {
                'auth_energy_sum_j':  round(sum(r['auth_energy_j'] for r in results if r['phase'] != 'Registration'), 6),
                'auth_time_sum_s':    round(sum(r['auth_s']         for r in results if r['phase'] != 'Registration'), 6),
                'total_energy_sum_j': round(sum(r['total_energy_j'] for r in results if r['phase'] != 'Registration'), 6),
                'total_time_sum_s':   round(sum(r['total_s']        for r in results if r['phase'] != 'Registration'), 6),
                'avg_auth_energy_j':  round(avg_authe, 6),
                'avg_auth_time_s':    round(avg_auth,  6),
            }
        }
        with open('zhou_hw_run.json', 'w') as f:
            json.dump(out, f, indent=2)
        print("[USR-ZHOU] Results saved to zhou_hw_run.json")
