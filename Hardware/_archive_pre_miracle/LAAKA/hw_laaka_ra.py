#!/usr/bin/env python3
"""
Hardware measurement — LAAKA Scheme (RA / Registration Authority role)
Runs on: Laptop (192.168.1.203)

Role: Registration Authority (RA)
  Listens on PORT_LAAKA_RA_REG (5006) for device registrations.
  Replies with (TIDd, TIDf, Af, Bk) and forwards credentials to Fog.

LAAKA Registration (§4.2.2):
  Recv:  AES(K_RA_D, [IDd(1)|Ad(20)|pad(11)])          = 32 B
  Reply: AES(K_RA_D, [TIDd(20)|TIDf(20)|Af(20)|Bk(20)]) = 80 B
  Fwd→Fog: AES(K_RA_GW,[IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3)]) = 64 B
"""
import sys, os, threading, time, socket, atexit, signal, hashlib
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import AS_IP as FOG_IP

HASH_LEN = 20
RAND_LEN = 20

# ── LAAKA protocol constants (identical to C source in LAAKA/gw-node.c) ──────
r1_fog = bytes([0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,
                0x99,0xAA,0xBB,0xCC,0xDD,0xEE,0xFF,0x01,
                0x02,0x03,0x04,0x05])
TIDf_const = bytes([0xA1,0xB2,0xC3,0xD4,0xE5,0xF6,0x07,0x18,
                    0x29,0x3A,0x4B,0x5C,0x6D,0x7E,0x8F,0x90,
                    0x01,0x12,0x23,0x34])
K_MASTER = bytes([0xDE,0xAD,0xBE,0xEF,0xCA,0xFE,0xBA,0xBE,
                  0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF,
                  0xFE,0xDC,0xBA,0x98])
FOG_IDENTITY_ID = 2

# K_RA_D and K_RA_GW share byte values with K_AS_D and K_GW_AS in common.py
K_RA_D  = K_AS_D
K_RA_GW = K_GW_AS

PORT_LAAKA_RA_REG      = 5006
PORT_LAAKA_FOG_DEVINFO = 5007


def h20(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()[:HASH_LEN]


# Pre-compute Af = H20(FOG_IDENTITY_ID || r1_fog)
Af = h20(bytes([FOG_IDENTITY_ID]) + r1_fog)

clients      = {}   # id_d -> {TIDd, Ad, Bk}
clients_lock = threading.Lock()

stats = {'reg_count': 0, 'reg_wall_s': 0.0}
stats_lock = threading.Lock()


def _forward_to_fog(id_d: int, TIDd: bytes, Ad: bytes, Bk: bytes) -> None:
    """RA → Fog: AES(K_RA_GW, [IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3)]) = 64 B."""
    payload = bytearray(64)
    payload[0]    = id_d
    payload[1:21] = TIDd
    payload[21:41] = Ad
    payload[41:61] = Bk
    enc = aes_enc_blocks(K_RA_GW, bytes(payload))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((FOG_IP, PORT_LAAKA_FOG_DEVINFO))
            send_msg(s, enc)
            recv_msg(s)
        print(f"[RA] Forwarded dev={id_d} credentials to Fog ({FOG_IP}:{PORT_LAAKA_FOG_DEVINFO})")
    except Exception as e:
        print(f"[RA] Fog forwarding failed for dev={id_d}: {e}")


def handle_registration(conn, addr) -> None:
    t_wall = time.perf_counter()
    try:
        data = recv_msg(conn)
        if len(data) != 32:
            print(f"[RA] Bad reg length {len(data)}, expected 32")
            return

        plain = aes_dec_blocks(K_RA_D, data)
        id_d   = plain[0]
        Ad_recv = bytes(plain[1:21])

        with clients_lock:
            if id_d in clients:
                # Idempotent: reuse stored credentials
                TIDd = clients[id_d]['TIDd']
                Bk   = clients[id_d]['Bk']
                print(f"[RA] Re-registration for dev={id_d} — reusing credentials")
            else:
                seed = rand_bytes(HASH_LEN) + bytes([id_d]) + K_MASTER[:HASH_LEN]
                TIDd = h20(seed)
                Bk   = h20(Ad_recv + Af + K_MASTER[:HASH_LEN])
                clients[id_d] = {'TIDd': TIDd, 'Ad': Ad_recv, 'Bk': Bk}

        # Reply: AES(K_RA_D, [TIDd(20)|TIDf(20)|Af(20)|Bk(20)]) = 80 B (5 blocks)
        rep = bytearray(80)
        rep[0:20]  = TIDd
        rep[20:40] = TIDf_const
        rep[40:60] = Af
        rep[60:80] = Bk
        send_msg(conn, aes_enc_blocks(K_RA_D, bytes(rep)))

        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['reg_count']  += 1
            stats['reg_wall_s'] += wall_s
        print(f"[RA] Registered dev={id_d}  wall={wall_s*1000:.2f} ms  TIDd={TIDd.hex()[:8]}")

        # Forward credentials to Fog asynchronously (after reply to device)
        threading.Thread(target=_forward_to_fog,
                         args=(id_d, TIDd, Ad_recv, Bk), daemon=True).start()
    except Exception as e:
        print(f"[RA] reg handler error: {e}")
    finally:
        conn.close()


def print_summary() -> None:
    print("\n" + "=" * 70)
    print("[RA] ===== RA SUMMARY =====")
    with stats_lock:
        rc = stats['reg_count']
        rw = stats['reg_wall_s']
    print(f"  Registrations served : {rc}")
    print(f"  Total wall time      : {rw*1000:.2f} ms")
    if rc > 0:
        print(f"  Avg per registration : {rw/rc*1000:.2f} ms")
    print("=" * 70)


atexit.register(print_summary)


if __name__ == '__main__':
    print("=" * 70)
    print("[RA] LAAKA Registration Authority")
    print(f"[RA] Fog={FOG_IP}:{PORT_LAAKA_FOG_DEVINFO}   Af={Af.hex()[:8]}")
    print(f"[RA] Listening on :{PORT_LAAKA_RA_REG} (device registration)")
    print(f"[RA] Ctrl+C to stop and print summary.")
    print("=" * 70)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    srv = make_server(PORT_LAAKA_RA_REG)
    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_registration,
                             args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("[RA] Stopping.")
