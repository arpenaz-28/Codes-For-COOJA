#!/usr/bin/env python3
"""
User/Device — Zhou et al. scheme
Runs on: RPi 2 (192.168.1.132)

In Zhou's scheme this is the "User" (doctor/patient device) role.

Steps:
  1. User Registration: send (IDi, ki) to GW, receive DIDi
  2. Fetch SIDn from GW (needed to build M1)
  3. Authentication: send M1 = [Ni|α|DIDi|SIDn], receive M4 = [SKi|λ]
"""
import sys, os, time, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import (GW_IP, PORT_ZHOU_USER_REG, PORT_ZHOU_AUTH, NODE_DEV, NODE_SN)

# ── User state ────────────────────────────────────────────────────────────────
ID_I   = NODE_DEV
ki     = sha256(bytes([ID_I]) + b'biometric-key')   # deterministic test key
DIDi   = b'\x00' * 32
SIDn   = b'\x00' * 32
bi_curr = b'\x00' * 32
SK     = b'\x00' * 32
results = []

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

def h3(x: bytes) -> bytes:
    return sha256(x + b'\x00') + sha256(x + b'\x01') + sha256(x + b'\x02')

def tcp_send_recv(ip, port, payload):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        send_msg(s, payload)
        return recv_msg(s)

# ── User Registration ─────────────────────────────────────────────────────────

def do_registration():
    global DIDi

    t0 = time.perf_counter()

    p0 = bytearray(48)
    p0[0]    = ID_I
    p0[1:33] = ki
    rep = tcp_send_recv(GW_IP, PORT_ZHOU_USER_REG,
                        aes_enc_blocks(K_GW_U, bytes(p0)))

    plain = aes_dec_blocks(K_GW_U, rep)
    DIDi  = bytes(plain[0:32])

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"[USR-ZHOU] Registration done in {elapsed:.1f} ms | DIDi={DIDi.hex()[:6]}")
    results.append({'phase': 'User-Enroll', 'time_ms': round(elapsed, 2)})

# ── Fetch SIDn from GW ────────────────────────────────────────────────────────
# GW serves current SIDn for a given sensor node ID.
# We re-use PORT_ZHOU_USER_REG with a special query message.
# (Alternatively hard-code a separate port — kept simple here by
#  asking GW during auth setup via a 1-byte "get_sid" prefix msg.)
#
# For simplicity in hardware demo: GW's handle_user_reg already stores SIDn;
# device.py fetches SIDn by sending a single AES-encrypted [0xFF, sn_id] query.

def fetch_sidn():
    global SIDn

    # Special query: AES1(K_GW_U, [0xFF, sn_id, 0×]) = 16B
    # GW replies with AES3(K_GW_U, [SIDn(32), 0×]) = 48B
    # We reuse the get_sid handler on PORT_ZHOU_USER_REG via a flag byte.
    q = bytearray(16)
    q[0] = 0xFF        # query flag
    q[1] = NODE_SN     # which sensor

    # Open a fresh connection for the query
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((GW_IP, PORT_ZHOU_USER_REG))
        send_msg(s, aes_enc_blocks(K_GW_U, bytes(q)))
        rep = recv_msg(s)

    if len(rep) == 48:
        plain = aes_dec_blocks(K_GW_U, rep)
        SIDn  = bytes(plain[0:32])
        print(f"[USR-ZHOU] Got SIDn={SIDn.hex()[:6]}")
    else:
        print(f"[USR-ZHOU] fetch_sidn: unexpected reply len {len(rep)}")

# ── Authentication ────────────────────────────────────────────────────────────

def do_auth(round_num=1):
    global DIDi, SK, bi_curr

    t0 = time.perf_counter()

    # Generate fresh bi_new
    bi_new = rand_bytes(32)
    bi_curr = bi_new

    # Ni = bi_new XOR H(ki)
    h_ki = sha256(ki)
    Ni   = xor_bytes(bi_new, h_ki)

    # α = H(bi_new || ki || DIDi || SIDn)
    alpha_in = bi_new + ki + DIDi + SIDn
    alpha    = sha256(alpha_in)

    # M1: [Ni(32)|α(32)|DIDi(32)|SIDn(32)] = 128 bytes
    m1 = Ni + alpha + DIDi + SIDn

    t_send = time.perf_counter()
    try:
        m4 = tcp_send_recv(GW_IP, PORT_ZHOU_AUTH, m1)
    except Exception as e:
        print(f"[USR-ZHOU] Round {round_num}: M1 send failed: {e}")
        return False
    elapsed_rtt = time.perf_counter() - t_send

    if len(m4) != 128 or m4[0] == 0xFF:
        print(f"[USR-ZHOU] Round {round_num}: Auth FAILED (M4 len={len(m4)})")
        return False

    SKi = bytes(m4[0:96])
    lam = bytes(m4[96:128])

    # Decode SKi: (SIDn_new || SK' || DIDi_new) = SKi XOR H3(ki)
    mask96   = h3(ki)
    decoded  = xor_bytes(SKi, mask96)
    SIDn_new = decoded[0:32]
    SK_new   = decoded[32:64]
    DIDi_new = decoded[64:96]

    # Verify λ = H(SK' || DIDi || ki || DIDi_new || SIDn_new)
    lam_in = SK_new + DIDi + ki + DIDi_new + SIDn_new
    lam_p  = sha256(lam_in)
    if lam_p != lam:
        print(f"[USR-ZHOU] Round {round_num}: λ mismatch — Auth FAILED")
        return False

    # Commit new state
    global SIDn
    DIDi = DIDi_new
    SK   = SK_new
    SIDn = SIDn_new

    total_ms = (time.perf_counter() - t0) * 1000
    print(f"[USR-ZHOU] Round {round_num}: Auth OK | rtt={elapsed_rtt*1000:.1f} ms | total={total_ms:.1f} ms")
    results.append({
        'phase': f'Auth-R{round_num}',
        'rtt_ms':   round(elapsed_rtt*1000, 2),
        'total_ms': round(total_ms, 2),
    })
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("[USR-ZHOU] Zhou scheme hardware test")
    print("=" * 60)

    time.sleep(1)
    do_registration()
    time.sleep(0.5)

    fetch_sidn()
    time.sleep(0.5)

    print("\n[USR-ZHOU] === Auth Round 1 ===")
    do_auth(1)
    time.sleep(0.5)

    print("\n[USR-ZHOU] === Auth Round 2 ===")
    do_auth(2)

    print("\nResults:")
    for r in results:
        print(" ", r)
