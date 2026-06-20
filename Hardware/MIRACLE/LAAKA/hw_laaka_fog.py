#!/usr/bin/env python3
"""
Hardware measurement — LAAKA Scheme (Fog Server role)
Runs on: Apex RPi (192.168.1.132)

Role: Fog Authentication Server.

LAAKA Registration of fog server (§4.2.1) — NOW PERFORMED LIVE (was hardcoded):
  At startup the fog picks ID_f and a secret random r1, computes Af = h(ID_f||r1),
  securely sends Af to the RA, and receives a temporary identifier TIDf which it
  stores. This one-time setup is measured and saved to fogreg_hw_run.json.
    Fog -> RA : AES(K_RA_GW, [ID_f(1)|Af(20)|pad]) = 32 B
    RA -> Fog : AES(K_RA_GW, [TIDf(20)|pad])       = 32 B

Post-registration ports:
  5007  RA  -> Fog: device credential push (AES 64 B)
  5008  Dev -> Fog: AuthReq (81 B) / AuthRep (82 B)
  5009  Dev -> Fog: Ack (40 B)
  5010  Dev -> Fog: encrypted sensor data (36 B)

RPi 4B active power assumption: 3800 mW
"""
import sys, os, json, threading, time, socket, atexit, signal, hashlib
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import GW_IP as RA_IP   # RA runs on the laptop (GW host)

RPI_POWER_MW = 3800
HASH_LEN = 20
RAND_LEN = 20

FOG_IDENTITY_ID = 2
K_RA_GW = K_GW_AS   # secure RA<->Fog channel key (models the "secure channel")

PORT_LAAKA_RA_FOGREG   = 5016   # Fog -> RA: fog registration (§4.2.1)
PORT_LAAKA_FOG_DEVINFO = 5007
PORT_LAAKA_FOG_AUTH    = 5008
PORT_LAAKA_FOG_ACK     = 5009
PORT_LAAKA_FOG_DATA    = 5010

# Fog credentials — established by live registration with RA (NOT hardcoded)
r1   = b'\x00' * RAND_LEN
Af   = b'\x00' * HASH_LEN
TIDf = b'\x00' * HASH_LEN


def h20(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()[:HASH_LEN]

def xor20(a: bytes, b: bytes) -> bytes:
    assert len(a) == HASH_LEN and len(b) == HASH_LEN
    return bytes(x ^ y for x, y in zip(a, b))

def energy(wall_s: float) -> float:
    return round(wall_s * (RPI_POWER_MW / 1000), 6)


def register_with_ra() -> None:
    """LAAKA §4.2.1 — fog registers with RA; measured one-time setup cost."""
    global r1, Af, TIDf
    t_wall = time.perf_counter(); t_cpu = time.process_time()

    r1 = rand_bytes(RAND_LEN)
    Af = h20(bytes([FOG_IDENTITY_ID]) + r1)        # Af = h(ID_f || r1)

    req = bytearray(32)
    req[0]    = FOG_IDENTITY_ID
    req[1:21] = Af
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((RA_IP, PORT_LAAKA_RA_FOGREG))
        send_msg(s, aes_enc_blocks(K_RA_GW, bytes(req)))
        rep = recv_msg(s)
    plain = aes_dec_blocks(K_RA_GW, rep)
    TIDf = bytes(plain[0:20])                        # RA issues TIDf

    wall_s = time.perf_counter() - t_wall
    cpu_s  = time.process_time()  - t_cpu
    rec = {'phase': 'FogRegistration',
           'wall_s': round(wall_s, 4), 'cpu_s': round(cpu_s, 4),
           'energy_j': energy(wall_s)}
    try:
        with open(os.path.join(_d, 'fogreg_hw_run.json'), 'w') as f:
            json.dump(rec, f, indent=2)
    except Exception:
        pass
    print(f"[FOG] Registered with RA  wall={wall_s:.4f} s  cpu={cpu_s:.4f} s  "
          f"energy={energy(wall_s):.6f} J  Af={Af.hex()[:8]}  TIDf={TIDf.hex()[:8]}")


# Device database: keyed by TIDd hex string
devices      = {}
devices_lock = threading.Lock()

stats = {'auth_count': 0, 'auth_wall_s': 0.0, 'auth_cpu_s': 0.0,
         'ack_count': 0, 'ack_wall_s': 0.0,
         'data_count': 0, 'data_wall_s': 0.0}
stats_lock = threading.Lock()


def make_device(id_d, TIDd, Ad, Bk):
    return {'IDd': id_d, 'TIDd': TIDd, 'Ad': Ad, 'Bk': Bk,
            'rf': b'\x00'*RAND_LEN, 'SK': b'\x00'*HASH_LEN,
            'TIDd_new': b'\x00'*HASH_LEN, 'authenticated': False}


def find_by_tid(tid: bytes):
    with devices_lock:
        return devices.get(tid.hex())

def find_by_tid_new(tid_new: bytes):
    with devices_lock:
        for dev in devices.values():
            if dev['TIDd_new'] == tid_new:
                return dev
    return None


def handle_devinfo(conn, addr) -> None:
    try:
        data = recv_msg(conn)
        if len(data) != 64:
            send_msg(conn, b'ERR'); return
        plain = aes_dec_blocks(K_RA_GW, data)
        id_d  = plain[0]
        TIDd  = bytes(plain[1:21]); Ad = bytes(plain[21:41]); Bk = bytes(plain[41:61])
        with devices_lock:
            devices[TIDd.hex()] = make_device(id_d, TIDd, Ad, Bk)
        send_msg(conn, b'OK')
        print(f"[FOG] Stored dev={id_d}  TIDd={TIDd.hex()[:8]}")
    except Exception as e:
        print(f"[FOG] devinfo error: {e}")
    finally:
        conn.close()


def handle_auth(conn, addr) -> None:
    t_wall = time.perf_counter(); t_cpu = time.process_time()
    try:
        data = recv_msg(conn)
        if len(data) != 81:
            print(f"[FOG] Bad auth len={len(data)}"); send_msg(conn, bytes([0xFF])); return

        recv_TIDd = bytes(data[0:20]); Td = data[20]
        recv_Cd = bytes(data[21:41]); recv_Ed = bytes(data[41:61]); recv_Gd = bytes(data[61:81])

        dev = find_by_tid(recv_TIDd)
        if dev is None:
            print(f"[FOG] Auth FAILED: TIDd={recv_TIDd.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF])); return

        rd_star = xor20(recv_Ed, h20(dev['Bk'] + Af))
        if h20(bytes([Td]) + rd_star) != recv_Cd:
            print(f"[FOG] Auth FAILED: Cd mismatch"); send_msg(conn, bytes([0xFF])); return
        TIDd_new_star = xor20(recv_TIDd, rd_star)
        if h20(dev['Ad'] + TIDd_new_star + dev['Bk'] + rd_star) != recv_Gd:
            print(f"[FOG] Auth FAILED: Gd mismatch"); send_msg(conn, bytes([0xFF])); return

        Tf = int(time.time()) & 0xFF
        rf = rand_bytes(RAND_LEN)
        Ts = (Tf + 1) & 0xFF
        Cf = h20(bytes([Tf]) + rf)
        SK = h20(rd_star + rf + bytes([Ts]))
        Ef = xor20(rf, h20(TIDd_new_star))
        TIDf_new = xor20(TIDf, rf)                       # uses registered TIDf
        Gf = h20(TIDf_new + dev['Bk'] + rf + SK + bytes([Ts]))

        with devices_lock:
            dev['rf'] = rf; dev['SK'] = SK; dev['TIDd_new'] = TIDd_new_star
            dev['authenticated'] = False

        rep = bytearray(82)
        rep[0:20] = TIDf                                 # uses registered TIDf
        rep[20] = Tf; rep[21] = Ts
        rep[22:42] = Cf; rep[42:62] = Ef; rep[62:82] = Gf
        send_msg(conn, bytes(rep))

        wall_s = time.perf_counter() - t_wall; cpu_s = time.process_time() - t_cpu
        with stats_lock:
            stats['auth_count'] += 1; stats['auth_wall_s'] += wall_s; stats['auth_cpu_s'] += cpu_s
        print(f"[FOG] Auth OK dev={dev['IDd']}  wall={wall_s*1000:.2f} ms  SK={SK.hex()[:8]}")
    except Exception as e:
        print(f"[FOG] auth error: {e}")
    finally:
        conn.close()


def handle_ack(conn, addr) -> None:
    t_wall = time.perf_counter()
    try:
        data = recv_msg(conn)
        if len(data) != 40:
            send_msg(conn, bytes([0xFF])); return
        recv_tid_new = bytes(data[0:20]); recv_ack = bytes(data[20:40])
        dev = find_by_tid_new(recv_tid_new)
        if dev is None:
            send_msg(conn, bytes([0xFF])); return
        if h20(dev['rf'] + dev['Bk'] + dev['SK']) != recv_ack:
            print(f"[FOG] Ack verification FAILED"); send_msg(conn, bytes([0xFF])); return
        with devices_lock:
            dev['authenticated'] = True
        send_msg(conn, b'OK')
        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['ack_count'] += 1; stats['ack_wall_s'] += wall_s
        print(f"[FOG] Ack OK dev={dev['IDd']}  Mutual auth complete")
    except Exception as e:
        print(f"[FOG] ack error: {e}")
    finally:
        conn.close()


def handle_data(conn, addr) -> None:
    t_wall = time.perf_counter()
    try:
        data = recv_msg(conn)
        if len(data) != 36:
            send_msg(conn, bytes([0xFF])); return
        recv_tid_new = bytes(data[0:20]); enc_data = bytes(data[20:36])
        dev = find_by_tid_new(recv_tid_new)
        if dev is None or not dev['authenticated']:
            send_msg(conn, bytes([0xFF])); return
        plain = aes_dec_blocks(dev['SK'][:16], enc_data)
        send_msg(conn, bytes([0xAC]))
        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['data_count'] += 1; stats['data_wall_s'] += wall_s
        print(f"[FOG] Data OK dev={dev['IDd']}  val={plain[0]}")
    except Exception as e:
        print(f"[FOG] data error: {e}")
    finally:
        conn.close()


def print_summary() -> None:
    print("\n" + "=" * 70)
    print("[FOG] ===== FOG SERVER ENERGY SUMMARY =====")
    with stats_lock:
        ac, aw = stats['auth_count'], stats['auth_wall_s']
        ck, kw = stats['ack_count'],  stats['ack_wall_s']
        dc, dw = stats['data_count'], stats['data_wall_s']
    for lbl, cnt, wall in [('Auth', ac, aw), ('Ack', ck, kw), ('Data', dc, dw)]:
        print(f"{lbl:<10} x{cnt}: {wall*1000:.2f} ms")
    print("=" * 70)


atexit.register(print_summary)


def listener(port: int, handler, name: str) -> None:
    srv = make_server(port)
    print(f"[FOG] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    print(f"[FOG] LAAKA Fog Server (node {FOG_IDENTITY_ID})  RA={RA_IP}")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # §4.2.1 — register with RA FIRST (one-time, measured), then serve
    register_with_ra()

    for port, fn, label in [
        (PORT_LAAKA_FOG_DEVINFO, handle_devinfo, "devinfo"),
        (PORT_LAAKA_FOG_AUTH,    handle_auth,    "auth"),
        (PORT_LAAKA_FOG_ACK,     handle_ack,     "ack"),
        (PORT_LAAKA_FOG_DATA,    handle_data,    "data"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()
    print(f"[FOG] Power assumption: {RPI_POWER_MW} mW.  Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[FOG] Stopping.")
