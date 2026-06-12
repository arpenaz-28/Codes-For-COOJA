#!/usr/bin/env python3
"""
Hardware measurement — LAAKA Scheme (Fog Server role)
Runs on: Apex RPi (192.168.1.132)

Role: Fog Authentication Server — handles ALL post-registration protocol steps.

Ports:
  5007  RA → Fog: device credential push (AES 64 B)
  5008  Device → Fog: AuthReq (81 B) / AuthRep (82 B)
  5009  Device → Fog: Ack (40 B) — confirms mutual auth (LAAKA Step 9)
  5010  Device → Fog: encrypted sensor data (36 B)

LAAKA Auth Steps 2-5 (handled here):
  - Verify TIDd, extract rd*, verify Cd*, compute TIDd_new*, verify Gd*
  - Generate Tf, rf, Ts, compute SK = H20(rd||rf||Ts)
  - Reply with TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20) = 82 B

RPi 4B active power assumption: 3800 mW
"""
import sys, os, threading, time, socket, atexit, signal, hashlib
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *

RPI_POWER_MW = 3800

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

K_RA_GW = K_GW_AS   # same bytes as K_GW_AS in common.py

PORT_LAAKA_FOG_DEVINFO = 5007
PORT_LAAKA_FOG_AUTH    = 5008
PORT_LAAKA_FOG_ACK     = 5009
PORT_LAAKA_FOG_DATA    = 5010


def h20(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()[:HASH_LEN]

def xor20(a: bytes, b: bytes) -> bytes:
    assert len(a) == HASH_LEN and len(b) == HASH_LEN
    return bytes(x ^ y for x, y in zip(a, b))


Af = h20(bytes([FOG_IDENTITY_ID]) + r1_fog)

# Device database: keyed by TIDd hex string
devices      = {}
devices_lock = threading.Lock()

stats = {
    'auth_count': 0, 'auth_wall_s': 0.0, 'auth_cpu_s': 0.0,
    'ack_count':  0, 'ack_wall_s':  0.0,
    'data_count': 0, 'data_wall_s': 0.0,
}
stats_lock = threading.Lock()


def make_device(id_d, TIDd, Ad, Bk):
    return {
        'IDd': id_d, 'TIDd': TIDd, 'Ad': Ad, 'Bk': Bk,
        'rf': b'\x00'*RAND_LEN, 'SK': b'\x00'*HASH_LEN,
        'TIDd_new': b'\x00'*HASH_LEN,
        'authenticated': False,
    }


def find_by_tid(tid: bytes):
    with devices_lock:
        return devices.get(tid.hex())

def find_by_tid_new(tid_new: bytes):
    with devices_lock:
        for dev in devices.values():
            if dev['TIDd_new'] == tid_new:
                return dev
    return None


# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_devinfo(conn, addr) -> None:
    """Receive device credentials forwarded by RA."""
    try:
        data = recv_msg(conn)
        if len(data) != 64:
            send_msg(conn, b'ERR')
            return
        plain  = aes_dec_blocks(K_RA_GW, data)
        id_d   = plain[0]
        TIDd   = bytes(plain[1:21])
        Ad     = bytes(plain[21:41])
        Bk     = bytes(plain[41:61])
        with devices_lock:
            devices[TIDd.hex()] = make_device(id_d, TIDd, Ad, Bk)
        send_msg(conn, b'OK')
        print(f"[FOG] Stored dev={id_d}  TIDd={TIDd.hex()[:8]}")
    except Exception as e:
        print(f"[FOG] devinfo error: {e}")
    finally:
        conn.close()


def handle_auth(conn, addr) -> None:
    """AuthReq → AuthRep  (LAAKA Steps 2–5)."""
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()
    try:
        data = recv_msg(conn)
        if len(data) != 81:
            print(f"[FOG] Bad auth len={len(data)}, expected 81")
            send_msg(conn, bytes([0xFF]))
            return

        # Parse: TIDd(20)+Td(1)+Cd(20)+Ed(20)+Gd(20)
        recv_TIDd = bytes(data[0:20])
        Td        = data[20]
        recv_Cd   = bytes(data[21:41])
        recv_Ed   = bytes(data[41:61])
        recv_Gd   = bytes(data[61:81])

        dev = find_by_tid(recv_TIDd)
        if dev is None:
            print(f"[FOG] Auth FAILED: TIDd={recv_TIDd.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        # Step 3: rd* = Ed XOR H20(Bk || Af)
        rd_star = xor20(recv_Ed, h20(dev['Bk'] + Af))

        # Verify Cd* = H20(Td || rd*)
        if h20(bytes([Td]) + rd_star) != recv_Cd:
            print(f"[FOG] Auth FAILED: Cd mismatch for dev={dev['IDd']}")
            send_msg(conn, bytes([0xFF]))
            return

        # TIDd_new* = TIDd XOR rd*
        TIDd_new_star = xor20(recv_TIDd, rd_star)

        # Verify Gd* = H20(Ad || TIDd_new* || Bk || rd*)
        if h20(dev['Ad'] + TIDd_new_star + dev['Bk'] + rd_star) != recv_Gd:
            print(f"[FOG] Auth FAILED: Gd mismatch for dev={dev['IDd']}")
            send_msg(conn, bytes([0xFF]))
            return

        # Step 4: Generate Tf, rf, Ts
        Tf = int(time.time()) & 0xFF
        rf = rand_bytes(RAND_LEN)
        Ts = (Tf + 1) & 0xFF

        Cf = h20(bytes([Tf]) + rf)
        SK = h20(rd_star + rf + bytes([Ts]))
        Ef = xor20(rf, h20(TIDd_new_star))
        TIDf_new = xor20(TIDf_const, rf)
        Gf = h20(TIDf_new + dev['Bk'] + rf + SK + bytes([Ts]))

        # Store session state
        with devices_lock:
            dev['rf']        = rf
            dev['SK']        = SK
            dev['TIDd_new']  = TIDd_new_star
            dev['authenticated'] = False

        # AuthRep: TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20) = 82 B
        rep = bytearray(82)
        rep[0:20]  = TIDf_const
        rep[20]    = Tf
        rep[21]    = Ts
        rep[22:42] = Cf
        rep[42:62] = Ef
        rep[62:82] = Gf
        send_msg(conn, bytes(rep))

        wall_s = time.perf_counter() - t_wall
        cpu_s  = time.process_time()  - t_cpu
        with stats_lock:
            stats['auth_count']  += 1
            stats['auth_wall_s'] += wall_s
            stats['auth_cpu_s']  += cpu_s
        print(f"[FOG] Auth OK dev={dev['IDd']}  wall={wall_s*1000:.2f} ms  "
              f"cpu={cpu_s*1000:.2f} ms  energy={wall_s*RPI_POWER_MW:.2f} mJ  "
              f"SK={SK.hex()[:8]}")
    except Exception as e:
        print(f"[FOG] auth error: {e}")
    finally:
        conn.close()


def handle_ack(conn, addr) -> None:
    """Ack from device — verifies mutual authentication (LAAKA Step 9)."""
    t_wall = time.perf_counter()
    try:
        data = recv_msg(conn)
        if len(data) != 40:
            print(f"[FOG] Bad ack len={len(data)}, expected 40")
            send_msg(conn, bytes([0xFF]))
            return

        recv_tid_new = bytes(data[0:20])
        recv_ack     = bytes(data[20:40])

        dev = find_by_tid_new(recv_tid_new)
        if dev is None:
            print(f"[FOG] Ack rejected: TIDd_new={recv_tid_new.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        # Expected Ack = H20(rf || Bk || SK)
        expected_ack = h20(dev['rf'] + dev['Bk'] + dev['SK'])
        if expected_ack != recv_ack:
            print(f"[FOG] Ack verification FAILED for dev={dev['IDd']}")
            send_msg(conn, bytes([0xFF]))
            return

        with devices_lock:
            dev['authenticated'] = True

        send_msg(conn, b'OK')
        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['ack_count']  += 1
            stats['ack_wall_s'] += wall_s
        print(f"[FOG] Ack OK dev={dev['IDd']}  wall={wall_s*1000:.2f} ms  Mutual auth complete")
    except Exception as e:
        print(f"[FOG] ack error: {e}")
    finally:
        conn.close()


def handle_data(conn, addr) -> None:
    """Encrypted sensor data from device."""
    t_wall = time.perf_counter()
    try:
        data = recv_msg(conn)
        if len(data) != 36:
            print(f"[FOG] Bad data len={len(data)}, expected 36")
            send_msg(conn, bytes([0xFF]))
            return

        recv_tid_new = bytes(data[0:20])
        enc_data     = bytes(data[20:36])

        dev = find_by_tid_new(recv_tid_new)
        if dev is None or not dev['authenticated']:
            print(f"[FOG] Data rejected: not authenticated (TIDd_new={recv_tid_new.hex()[:8]})")
            send_msg(conn, bytes([0xFF]))
            return

        plain = aes_dec_blocks(dev['SK'][:16], enc_data)
        send_msg(conn, bytes([0xAC]))
        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['data_count']  += 1
            stats['data_wall_s'] += wall_s
        print(f"[FOG] Data OK dev={dev['IDd']}  val={plain[0]}  wall={wall_s*1000:.2f} ms")
    except Exception as e:
        print(f"[FOG] data error: {e}")
    finally:
        conn.close()


def print_summary() -> None:
    print("\n" + "=" * 70)
    print("[FOG] ===== FOG SERVER ENERGY SUMMARY =====")
    with stats_lock:
        ac = stats['auth_count'];  aw = stats['auth_wall_s']
        ck = stats['ack_count'];   kw = stats['ack_wall_s']
        dc = stats['data_count'];  dw = stats['data_wall_s']
    print(f"{'Operation':<20} {'Count':>6} {'TotalWall(ms)':>14} {'TotalEnergy(mJ)':>16}")
    print("-" * 58)
    for lbl, cnt, wall in [('Auth', ac, aw), ('Ack', ck, kw), ('Data', dc, dw)]:
        print(f"{lbl:<20} {cnt:>6} {wall*1000:>14.2f} {wall*RPI_POWER_MW:>16.2f}")
    total_w = aw + kw + dw
    print("-" * 58)
    print(f"{'TOTAL':<20} {'':>6} {total_w*1000:>14.2f} {total_w*RPI_POWER_MW:>16.2f}")
    if ac > 0:
        print(f"\nAvg auth latency: {aw/ac*1000:.2f} ms  avg auth energy: {aw/ac*RPI_POWER_MW:.2f} mJ")
    print("=" * 70)


atexit.register(print_summary)


def listener(port: int, handler, name: str) -> None:
    srv = make_server(port)
    print(f"[FOG] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    for port, fn, label in [
        (PORT_LAAKA_FOG_DEVINFO, handle_devinfo, "devinfo"),
        (PORT_LAAKA_FOG_AUTH,    handle_auth,    "auth"),
        (PORT_LAAKA_FOG_ACK,     handle_ack,     "ack"),
        (PORT_LAAKA_FOG_DATA,    handle_data,    "data"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()

    print(f"[FOG] LAAKA Fog Server (node {FOG_IDENTITY_ID})  Af={Af.hex()[:8]}")
    print(f"[FOG] Power assumption: {RPI_POWER_MW} mW.  Ctrl+C to stop.")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[FOG] Stopping.")
