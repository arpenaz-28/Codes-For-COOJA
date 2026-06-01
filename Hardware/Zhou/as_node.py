#!/usr/bin/env python3
"""
Sensor Node (SN) — Zhou et al. scheme
Runs on: RPi 1 (192.168.1.113)

In Zhou's scheme this role is the Sensor/Fog node, NOT an Auth Server.

Listens on:
  PORT_ZHOU_SN_REG (5012) → registration two-step (initiated by this script, connects to GW)
  PORT_ZHOU_M2     (5014) ← GW: M2 = [SKn(64)|β(32)|Cn(1)] = 97 bytes, replies M3 = [γ(32)]
"""
import sys, os, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (GW_IP, PORT_ZHOU_SN_REG, PORT_ZHOU_M2, NODE_SN)

# ── Sensor state ──────────────────────────────────────────────────────────────
SN_ID    = NODE_SN
SIDn     = b'\x00' * 32
Cn       = 0
Rn_state = 0
registered = False
results    = []

def h2(x: bytes) -> bytes:
    return sha256(x + b'\x00') + sha256(x + b'\x01')

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

# ── Sensor Registration (SN connects to GW) ───────────────────────────────────

def do_registration():
    global SIDn, Cn, Rn_state, registered

    t0 = time.perf_counter()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((GW_IP, PORT_ZHOU_SN_REG))

        # Step 1: AES1(K_GW_SN, [SNn, 0×15]) = 16B
        p0 = bytearray(16)
        p0[0] = SN_ID
        send_msg(s, aes_enc_blocks(K_GW_SN, bytes(p0)))

        # Receive: AES3(K_GW_SN, [SIDn(32), Cn(1), 0×]) = 48B
        rep = recv_msg(s)
        plain = aes_dec_blocks(K_GW_SN, rep)
        SIDn = bytes(plain[0:32])
        Cn   = plain[32]

        # Step 3: compute Rn via PUF, send AES1(K_GW_SN, [Rn, sn_id, 0×]) = 16B
        Rn_state = puf_response_zhou(SN_ID, Cn)
        p1 = bytearray(16)
        p1[0] = Rn_state
        p1[1] = SN_ID
        send_msg(s, aes_enc_blocks(K_GW_SN, bytes(p1)))

        ack = recv_msg(s)

    registered = True
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"[SN-ZHOU] Registration done in {elapsed:.1f} ms | SIDn={SIDn.hex()[:6]} Cn={Cn} Rn={Rn_state}")
    results.append({'phase': 'SN-Enroll', 'time_ms': round(elapsed, 2)})

# ── M2 handler (listens for GW, replies M3) ───────────────────────────────────

def handle_m2(conn, addr):
    global SIDn

    try:
        t0 = time.perf_counter()

        # M2: [SKn(64)|β(32)|Cn(1)] = 97 bytes
        data = recv_msg(conn)
        if len(data) != 97:
            print(f"[SN-ZHOU] M2 bad len {len(data)}")
            return

        SKn  = bytes(data[0:64])
        beta = bytes(data[64:96])
        Cn_m = data[96]

        # Rn = PUF(Cn)
        Rn = puf_response_zhou(SN_ID, Cn_m)

        # (SK' || SIDn_new') = SKn XOR H2(Rn)
        mask64   = h2(bytes([Rn]))
        decoded  = xor_bytes(SKn, mask64)
        SK_prime    = decoded[0:32]
        SIDn_new_p  = decoded[32:64]

        # β' = H(SK' || Rn || SIDn_active || SIDn_new')
        beta_in = SK_prime + bytes([Rn]) + SIDn + SIDn_new_p
        beta_p  = sha256(beta_in)

        if beta_p != beta:
            print(f"[SN-ZHOU] M2 FAIL: β mismatch")
            send_msg(conn, bytes([0xFF]))
            return

        # γ = H(SIDn_new' || SK')
        gamma = sha256(SIDn_new_p + SK_prime)
        send_msg(conn, gamma)

        # Update SIDn
        SIDn = SIDn_new_p

        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[SN-ZHOU] M3 sent in {elapsed:.1f} ms | SIDn_new={SIDn.hex()[:6]}")
        results.append({'phase': 'M2-M3', 'time_ms': round(elapsed, 2)})
    except Exception as e:
        print(f"[SN-ZHOU] M2 handler: {e}")
    finally:
        conn.close()

def listen_m2():
    srv = make_server(PORT_ZHOU_M2)
    print(f"[SN-ZHOU] Listening for M2 on :{PORT_ZHOU_M2}")
    while True:
        conn, addr = srv.accept()
        handle_m2(conn, addr)   # sequential — one auth at a time

if __name__ == '__main__':
    print("=" * 60)
    print("[SN-ZHOU] Zhou scheme Sensor Node")
    print("=" * 60)

    import threading
    time.sleep(1)
    do_registration()
    threading.Thread(target=listen_m2, daemon=True).start()

    print("[SN-ZHOU] Ready for M2 messages. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SN-ZHOU] Results:", results)
