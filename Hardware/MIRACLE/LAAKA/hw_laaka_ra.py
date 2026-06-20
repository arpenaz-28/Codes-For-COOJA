#!/usr/bin/env python3
"""
Hardware measurement — LAAKA Scheme (RA / Registration Authority role)
Runs on: Laptop (192.168.1.201)

LAAKA Registration phase (§4.2), both sub-phases now performed live:

  §4.2.1 Fog registration  (port 5016):
    Fog -> RA : AES(K_RA_GW, [ID_f(1)|Af(20)|pad])  ; Af = h(ID_f||r1)
    RA  -> Fog: AES(K_RA_GW, [TIDf(20)|pad])        ; RA issues + stores TIDf, Af

  §4.2.2 Device registration  (port 5006):
    Dev -> RA : AES(K_RA_D, [IDd(1)|Ad(20)|pad])    ; Ad = h(IDd||r2)
    RA computes Bk = h(Ad||Af||K) using the REGISTERED fog's Af
    RA -> Dev : AES(K_RA_D, [TIDd(20)|TIDf(20)|Af(20)|Bk(20)])
    RA -> Fog : AES(K_RA_GW,[IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad])
"""
import sys, os, threading, time, socket, atexit, signal, hashlib
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import AS_IP as FOG_IP

HASH_LEN = 20
RAND_LEN = 20

K_MASTER = bytes([0xDE,0xAD,0xBE,0xEF,0xCA,0xFE,0xBA,0xBE,
                  0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF,
                  0xFE,0xDC,0xBA,0x98])

# K_RA_D and K_RA_GW share byte values with K_AS_D and K_GW_AS in common.py
K_RA_D  = K_AS_D
K_RA_GW = K_GW_AS

PORT_LAAKA_RA_FOGREG   = 5016
PORT_LAAKA_RA_REG      = 5006
PORT_LAAKA_FOG_DEVINFO = 5007


def h20(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()[:HASH_LEN]

# Secure databases populated at registration time (NOT hardcoded)
fogs    = {}   # ID_f -> {'Af':..., 'TIDf':...}
clients = {}   # id_d -> {TIDd, Ad, Bk}
db_lock = threading.Lock()

stats = {'fogreg_count': 0, 'fogreg_wall_s': 0.0,
         'devreg_count': 0, 'devreg_wall_s': 0.0}
stats_lock = threading.Lock()


def handle_fog_registration(conn, addr) -> None:
    """§4.2.1 — receive Af from fog, issue & store TIDf."""
    t_wall = time.perf_counter()
    try:
        data = recv_msg(conn)
        if len(data) != 32:
            print(f"[RA] Bad fog-reg length {len(data)}"); return
        plain = aes_dec_blocks(K_RA_GW, data)
        id_f = plain[0]
        Af   = bytes(plain[1:21])

        with db_lock:
            if id_f in fogs:
                TIDf = fogs[id_f]['TIDf']
                print(f"[RA] Re-registration for fog={id_f} — reusing TIDf")
            else:
                TIDf = h20(rand_bytes(HASH_LEN) + bytes([id_f]) + K_MASTER[:HASH_LEN])
                fogs[id_f] = {'Af': Af, 'TIDf': TIDf}

        rep = bytearray(32)
        rep[0:20] = TIDf
        send_msg(conn, aes_enc_blocks(K_RA_GW, bytes(rep)))

        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['fogreg_count'] += 1; stats['fogreg_wall_s'] += wall_s
        print(f"[RA] Registered fog={id_f}  wall={wall_s*1000:.2f} ms  "
              f"Af={Af.hex()[:8]}  TIDf={TIDf.hex()[:8]}")
    except Exception as e:
        print(f"[RA] fog-reg error: {e}")
    finally:
        conn.close()


def _forward_to_fog(id_d: int, TIDd: bytes, Ad: bytes, Bk: bytes) -> None:
    payload = bytearray(64)
    payload[0]     = id_d
    payload[1:21]  = TIDd
    payload[21:41] = Ad
    payload[41:61] = Bk
    enc = aes_enc_blocks(K_RA_GW, bytes(payload))
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((FOG_IP, PORT_LAAKA_FOG_DEVINFO))
            send_msg(s, enc)
            recv_msg(s)
        print(f"[RA] Forwarded dev={id_d} credentials to Fog")
    except Exception as e:
        print(f"[RA] Fog forwarding failed for dev={id_d}: {e}")


def handle_registration(conn, addr) -> None:
    """§4.2.2 — device registration, using the registered fog's Af/TIDf."""
    t_wall = time.perf_counter()
    try:
        data = recv_msg(conn)
        if len(data) != 32:
            print(f"[RA] Bad reg length {len(data)}"); return
        plain = aes_dec_blocks(K_RA_D, data)
        id_d    = plain[0]
        Ad_recv = bytes(plain[1:21])

        with db_lock:
            if not fogs:
                print("[RA] Device reg REJECTED: no fog registered yet")
                return
            fog = next(iter(fogs.values()))   # single fog in this testbed
            Af, TIDf = fog['Af'], fog['TIDf']
            if id_d in clients:
                TIDd = clients[id_d]['TIDd']; Bk = clients[id_d]['Bk']
                print(f"[RA] Re-registration for dev={id_d} — reusing credentials")
            else:
                TIDd = h20(rand_bytes(HASH_LEN) + bytes([id_d]) + K_MASTER[:HASH_LEN])
                Bk   = h20(Ad_recv + Af + K_MASTER[:HASH_LEN])    # Bk = h(Ad||Af||K)
                clients[id_d] = {'TIDd': TIDd, 'Ad': Ad_recv, 'Bk': Bk}

        rep = bytearray(80)
        rep[0:20]  = TIDd
        rep[20:40] = TIDf
        rep[40:60] = Af
        rep[60:80] = Bk
        send_msg(conn, aes_enc_blocks(K_RA_D, bytes(rep)))

        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['devreg_count'] += 1; stats['devreg_wall_s'] += wall_s
        print(f"[RA] Registered dev={id_d}  wall={wall_s*1000:.2f} ms  TIDd={TIDd.hex()[:8]}")

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
        fc, fw = stats['fogreg_count'], stats['fogreg_wall_s']
        dc, dw = stats['devreg_count'], stats['devreg_wall_s']
    print(f"  Fog registrations    : {fc}  ({fw*1000:.2f} ms total)")
    print(f"  Device registrations : {dc}  ({dw*1000:.2f} ms total)")
    print("=" * 70)


atexit.register(print_summary)


def listener(port, handler, name):
    srv = make_server(port)
    print(f"[RA] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    print("=" * 70)
    print("[RA] LAAKA Registration Authority")
    print(f"[RA] Fog={FOG_IP}  ports: {PORT_LAAKA_RA_FOGREG} (fog-reg), {PORT_LAAKA_RA_REG} (dev-reg)")
    print("=" * 70)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    for port, fn, label in [
        (PORT_LAAKA_RA_FOGREG, handle_fog_registration, "fog-reg"),
        (PORT_LAAKA_RA_REG,    handle_registration,     "dev-reg"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[RA] Stopping.")
