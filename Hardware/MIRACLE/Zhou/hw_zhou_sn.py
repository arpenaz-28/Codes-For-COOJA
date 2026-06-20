#!/usr/bin/env python3
"""
Hardware measurement — Zhou Scheme (Sensor Node / SN role)
Runs on: Pi (192.168.1.113)

In Zhou's scheme this is the "Sensor Node" — the healthcare sensor device.

Steps:
  1. SN Registration with GW on startup (2-step PUF exchange)
  2. Serve M2 requests from GW: compute Rn via PUF, verify β, reply M3 = γ

Metrics:
  wall_s  : wall-clock latency per M2→M3 exchange
  cpu_s   : CPU-only time (time.process_time)
  energy_j: wall_s × RPi_power_W

RPi 4B active power assumption: 3800 mW
"""
import sys, os, threading, time, socket, atexit, signal
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import (GW_IP, PORT_ZHOU_SN_REG, PORT_ZHOU_M2, NODE_SN)

RPI_POWER_MW = 3800

# SN state — mutable dict so threads can update SIDn without global reassignment
sn_state      = {'SIDn': b'\x00' * 32, 'Cn': 0, 'Rn': 0}
sn_state_lock = threading.Lock()

stats = {
    'reg_wall_s': 0.0, 'reg_cpu_s': 0.0,
    'm2_count': 0, 'm2_wall_s': 0.0, 'm2_cpu_s': 0.0,
}
stats_lock = threading.Lock()


def h2(x: bytes) -> bytes:
    return sha256(x + b'\x00') + sha256(x + b'\x01')

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

def energy(wall_s: float) -> float:
    return round(wall_s * (RPI_POWER_MW / 1000), 6)


# ── SN Registration ───────────────────────────────────────────────────────────

def do_registration() -> None:
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((GW_IP, PORT_ZHOU_SN_REG))

        # Step 1: AES1(K_GW_SN, [SN_ID, 0×15]) = 16 B → GW
        p0 = bytearray(16)
        p0[0] = NODE_SN
        send_msg(s, aes_enc_blocks(K_GW_SN, bytes(p0)))

        # Receive: AES3(K_GW_SN, [SIDn(32)|Cn(1)|0×]) = 48 B
        rep   = recv_msg(s)
        plain = aes_dec_blocks(K_GW_SN, rep)
        SIDn_new = bytes(plain[0:32])
        Cn_new   = plain[32]

        # Step 3: PUF(SN_ID, Cn), send AES1(K_GW_SN, [Rn(1)|SN_ID(1)|0×]) = 16 B
        Rn_new = puf_response_zhou(NODE_SN, Cn_new)
        p1 = bytearray(16)
        p1[0] = Rn_new
        p1[1] = NODE_SN
        send_msg(s, aes_enc_blocks(K_GW_SN, bytes(p1)))
        recv_msg(s)   # "OK"

    with sn_state_lock:
        sn_state['SIDn'] = SIDn_new
        sn_state['Cn']   = Cn_new
        sn_state['Rn']   = Rn_new

    wall_s = time.perf_counter() - t_wall
    cpu_s  = time.process_time()  - t_cpu
    with stats_lock:
        stats['reg_wall_s'] = wall_s
        stats['reg_cpu_s']  = cpu_s
    print(f"[SN-ZHOU] Registration  wall={wall_s:.4f} s  cpu={cpu_s:.4f} s  "
          f"energy={energy(wall_s):.6f} J  SIDn={SIDn_new.hex()[:8]}  Cn={Cn_new}  Rn={Rn_new}")


# ── M2 → M3 handler ──────────────────────────────────────────────────────────

def handle_m2(conn, addr) -> None:
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()
    try:
        # M2: [SKn(64)|β(32)|Cn(1)] = 97 B
        data = recv_msg(conn)
        if len(data) != 97:
            print(f"[SN-ZHOU] M2 bad len {len(data)}, expected 97")
            send_msg(conn, bytes([0xFF]))
            return

        SKn  = bytes(data[0:64])
        beta = bytes(data[64:96])
        Cn_m = data[96]

        # PUF response for the challenge sent in M2
        Rn = puf_response_zhou(NODE_SN, Cn_m)

        # Recover (SK' || SIDn_new') = SKn XOR H2(Rn)
        decoded    = xor_bytes(SKn, h2(bytes([Rn])))
        SK_prime   = decoded[0:32]
        SIDn_new_p = decoded[32:64]

        # Verify β = H(SK' || Rn || SIDn_active || SIDn_new')
        with sn_state_lock:
            cur_sidn = sn_state['SIDn']
        beta_p = sha256(SK_prime + bytes([Rn]) + cur_sidn + SIDn_new_p)
        if beta_p != beta:
            print(f"[SN-ZHOU] M2 FAIL: β mismatch")
            send_msg(conn, bytes([0xFF]))
            return

        # M3: γ = H(SIDn_new' || SK')
        gamma = sha256(SIDn_new_p + SK_prime)
        send_msg(conn, gamma)

        # Rotate SIDn
        with sn_state_lock:
            sn_state['SIDn'] = SIDn_new_p

        wall_s = time.perf_counter() - t_wall
        cpu_s  = time.process_time()  - t_cpu
        with stats_lock:
            stats['m2_count']  += 1
            stats['m2_wall_s'] += wall_s
            stats['m2_cpu_s']  += cpu_s
        print(f"[SN-ZHOU] M3 sent  wall={wall_s:.4f} s  cpu={cpu_s:.4f} s  "
              f"energy={energy(wall_s):.6f} J  SIDn_new={SIDn_new_p.hex()[:8]}")
    except Exception as e:
        print(f"[SN-ZHOU] M2 handler: {e}")
    finally:
        conn.close()


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary() -> None:
    print("\n" + "=" * 70)
    print("[SN-ZHOU] ===== SN ENERGY SUMMARY =====")
    with stats_lock:
        rw = stats['reg_wall_s'];  rc = stats['reg_cpu_s']
        mc = stats['m2_count'];    mw = stats['m2_wall_s']
    print(f"{'Phase':<22} {'Wall(s)':>10} {'CPU(s)':>10} {'Energy(J)':>12}")
    print("-" * 56)
    print(f"{'Registration':<22} {rw:>10.4f} {rc:>10.4f} {energy(rw):>12.6f}")
    print(f"{'M2→M3 total':<22} {mw:>10.4f} {'':>10} {energy(mw):>12.6f}")
    if mc > 0:
        print(f"{'M2→M3 avg ('+str(mc)+')':<22} {mw/mc:>10.4f} {'':>10} {energy(mw/mc):>12.6f}")
    print("=" * 70)


atexit.register(print_summary)


if __name__ == '__main__':
    print("=" * 70)
    print("[SN-ZHOU] Zhou scheme Sensor Node — hardware measurement")
    print(f"[SN-ZHOU] GW={GW_IP}  SN_ID={NODE_SN}  Power={RPI_POWER_MW} mW")
    print(f"[SN-ZHOU] Registering with GW, then listening for M2 on :{PORT_ZHOU_M2}")
    print("=" * 70)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    time.sleep(1.0)   # allow GW to start listening before SN connects
    do_registration()

    srv = make_server(PORT_ZHOU_M2)
    print(f"[SN-ZHOU] Ready. Ctrl+C to stop and print summary.")
    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_m2, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("[SN-ZHOU] Stopping.")
