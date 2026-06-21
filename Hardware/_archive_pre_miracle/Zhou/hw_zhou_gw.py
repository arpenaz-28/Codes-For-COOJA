#!/usr/bin/env python3
"""
Hardware measurement — Zhou Scheme (GW / Medical Gateway role)
Runs on: Laptop (local process)

Ports served:
  5011 ← User: registration; also SIDn query (flag byte 0xFF)
  5012 ← SN:   two-step PUF registration
  5013 ← User: M1 — GW verifies M1, does M2/M3 with SN, replies M4
  5014 → SN:   M2 delivery (GW connects as client, SN replies M3)
  5015 ← User: encrypted sensor data (DIDi_new + AES(SK, data)) → ACK

RPi 4B active power assumption: 3800 mW (same across all three scheme GW roles).
"""
import sys, os, threading, time, socket, atexit, signal
_d = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_d, '..')); sys.path.insert(0, _d)
from common import *
from config import (AS_IP as SN_IP, PORT_ZHOU_USER_REG, PORT_ZHOU_SN_REG,
                    PORT_ZHOU_AUTH, PORT_ZHOU_M2, PORT_ZHOU_DATA, NODE_GW)

RPI_POWER_MW = 3800

users        = {}   # id_i → {ki, bi, DIDi_curr, DIDi_old, IDi_padded, SK, ...}
sensors      = {}   # sn_id → {Cn, Rn, bn, SIDn_curr, SIDn_old, SNn_padded, ...}
users_lock   = threading.Lock()
sensors_lock = threading.Lock()

stats = {
    'reg_u_count': 0,  'reg_u_wall_s': 0.0,
    'reg_sn_count': 0, 'reg_sn_wall_s': 0.0,
    'auth_count': 0,   'auth_wall_s': 0.0, 'auth_cpu_s': 0.0,
    'data_count': 0,   'data_wall_s': 0.0,
}
stats_lock = threading.Lock()


def h2(x: bytes) -> bytes:
    return sha256(x + b'\x00') + sha256(x + b'\x01')

def h3(x: bytes) -> bytes:
    return sha256(x + b'\x00') + sha256(x + b'\x01') + sha256(x + b'\x02')

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


# ── User Registration ─────────────────────────────────────────────────────────

def handle_user_reg(conn, addr):
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()
    try:
        data = recv_msg(conn)

        # SIDn query: 16 bytes starting with 0xFF flag
        if len(data) == 16:
            plain = aes_dec_blocks(K_GW_U, data)
            if plain[0] == 0xFF:
                sn_id = plain[1]
                with sensors_lock:
                    sn = sensors.get(sn_id)
                if sn and sn.get('enrolled'):
                    rep = bytearray(48)
                    rep[0:32] = sn['SIDn_curr']
                    send_msg(conn, aes_enc_blocks(K_GW_U, bytes(rep)))
                else:
                    send_msg(conn, bytes([0xFE]))
                return

        if len(data) != 48:
            print(f"[GW-ZHOU] user_reg: bad len {len(data)}, expected 48")
            return

        plain = aes_dec_blocks(K_GW_U, data)
        id_i  = plain[0]
        ki    = bytes(plain[1:33])

        id_padded = bytes([id_i]) + b'\x00' * 31
        bi        = rand_bytes(32)
        DIDi      = xor_bytes(bi, id_padded)

        with users_lock:
            users[id_i] = {
                'ki': ki, 'bi': bi,
                'DIDi_curr': DIDi, 'DIDi_old': DIDi,
                'IDi_padded': id_padded,
                'did_old_valid': False, 'enrolled': True,
                'SK': b'\x00' * 32,
            }

        reply = bytearray(48)
        reply[0:32] = DIDi
        send_msg(conn, aes_enc_blocks(K_GW_U, bytes(reply)))

        wall_s = time.perf_counter() - t_wall
        cpu_s  = time.process_time()  - t_cpu
        with stats_lock:
            stats['reg_u_count']  += 1
            stats['reg_u_wall_s'] += wall_s
        print(f"[GW-ZHOU] User {id_i} registered  wall={wall_s*1000:.2f} ms  DIDi={DIDi.hex()[:8]}")
    except Exception as e:
        print(f"[GW-ZHOU] user_reg error: {e}")
    finally:
        conn.close()


# ── Sensor Node Registration ──────────────────────────────────────────────────

def handle_sn_reg(conn, addr):
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()
    try:
        # Step 1: SN → GW: AES1(K_GW_SN, [SN_ID, 0×]) = 16 B
        data = recv_msg(conn)
        if len(data) != 16:
            return
        plain = aes_dec_blocks(K_GW_SN, data)
        sn_id = plain[0]

        sn_padded = bytes([sn_id]) + b'\x00' * 31
        bn        = rand_bytes(32)
        SIDn      = xor_bytes(bn, sn_padded)
        Cn        = rand_bytes(1)[0]

        # Reply: AES3(K_GW_SN, [SIDn(32)|Cn(1)|0×]) = 48 B
        rep1 = bytearray(48)
        rep1[0:32] = SIDn
        rep1[32]   = Cn
        send_msg(conn, aes_enc_blocks(K_GW_SN, bytes(rep1)))

        # Step 2: SN → GW: AES1(K_GW_SN, [Rn(1)|SN_ID(1)|0×]) = 16 B
        data2 = recv_msg(conn)
        if len(data2) != 16:
            return
        plain2 = aes_dec_blocks(K_GW_SN, data2)
        Rn     = plain2[0]

        with sensors_lock:
            sensors[sn_id] = {
                'Cn': Cn, 'Rn': Rn, 'bn': bn,
                'SIDn_curr': SIDn, 'SIDn_old': SIDn,
                'SNn_padded': sn_padded,
                'sid_old_valid': False, 'enrolled': True, 'SNn': sn_id,
            }

        send_msg(conn, b'OK')
        wall_s = time.perf_counter() - t_wall
        cpu_s  = time.process_time()  - t_cpu
        with stats_lock:
            stats['reg_sn_count']  += 1
            stats['reg_sn_wall_s'] += wall_s
        print(f"[GW-ZHOU] Sensor {sn_id} registered  wall={wall_s*1000:.2f} ms  "
              f"SIDn={SIDn.hex()[:8]}  Cn={Cn}  Rn={Rn}")
    except Exception as e:
        print(f"[GW-ZHOU] sn_reg error: {e}")
    finally:
        conn.close()


# ── Authentication: M1 → (M2/M3 with SN) → M4 ───────────────────────────────

def handle_auth(conn, addr):
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()
    try:
        # M1: [Ni(32)|α(32)|DIDi(32)|SIDn(32)] = 128 B
        data = recv_msg(conn)
        if len(data) != 128:
            print(f"[GW-ZHOU] M1 bad len {len(data)}, expected 128")
            send_msg(conn, bytes([0xFF]))
            return

        Ni        = bytes(data[0:32])
        alpha     = bytes(data[32:64])
        recv_DIDi = bytes(data[64:96])
        recv_SIDn = bytes(data[96:128])

        # Find user by DIDi (current or old for desync recovery)
        with users_lock:
            u = next((v for v in users.values()
                      if v['DIDi_curr'] == recv_DIDi
                      or (v['did_old_valid'] and v['DIDi_old'] == recv_DIDi)), None)
        if u is None:
            print(f"[GW-ZHOU] M1 FAIL: DIDi {recv_DIDi.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        # Recover bi_new and verify α
        bi_new  = xor_bytes(Ni, sha256(u['ki']))
        alpha_p = sha256(bi_new + u['ki'] + recv_DIDi + recv_SIDn)
        if alpha_p != alpha:
            print(f"[GW-ZHOU] M1 FAIL: α mismatch for user {u['IDi_padded'][0]}")
            send_msg(conn, bytes([0xFF]))
            return

        # Find sensor by SIDn (current or old)
        with sensors_lock:
            s = next((v for v in sensors.values()
                      if v['SIDn_curr'] == recv_SIDn
                      or (v['sid_old_valid'] and v['SIDn_old'] == recv_SIDn)), None)
        if s is None:
            print(f"[GW-ZHOU] M1 FAIL: SIDn {recv_SIDn.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        # Generate new session state
        bn_new   = rand_bytes(32)
        SK       = rand_bytes(32)
        SIDn_new = xor_bytes(s['SNn_padded'], bn_new)

        # SKn = (SK || SIDn_new) XOR H2(Rn) — 64 B
        SKn = xor_bytes(SK + SIDn_new, h2(bytes([s['Rn']])))

        # β = H(SK || Rn || SIDn_active || SIDn_new)
        SIDn_active = (s['SIDn_old'] if (s['sid_old_valid'] and s['SIDn_old'] == recv_SIDn)
                       else s['SIDn_curr'])
        beta = sha256(SK + bytes([s['Rn']]) + SIDn_active + SIDn_new)

        # M2 → SN: [SKn(64)|β(32)|Cn(1)] = 97 B
        m2_payload = SKn + beta + bytes([s['Cn']])
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ss:
                ss.connect((SN_IP, PORT_ZHOU_M2))
                send_msg(ss, m2_payload)
                m3 = recv_msg(ss)
        except Exception as e:
            print(f"[GW-ZHOU] M2 → SN failed: {e}")
            send_msg(conn, bytes([0xFF]))
            return

        if len(m3) != 32:
            print(f"[GW-ZHOU] M3 bad len {len(m3)}, expected 32")
            send_msg(conn, bytes([0xFF]))
            return

        # Verify γ = H(SIDn_new || SK)
        if sha256(SIDn_new + SK) != bytes(m3):
            print(f"[GW-ZHOU] M3 FAIL: γ mismatch")
            send_msg(conn, bytes([0xFF]))
            return

        # Build M4: SKi(96) || λ(32) = 128 B
        DIDi_new = xor_bytes(u['IDi_padded'], bi_new)
        SKi      = xor_bytes(SIDn_new + SK + DIDi_new, h3(u['ki']))
        lam      = sha256(SK + recv_DIDi + u['ki'] + DIDi_new + SIDn_new)
        send_msg(conn, SKi + lam)

        # Rotate user and sensor pseudonyms
        id_i  = u['IDi_padded'][0]
        sn_id = s['SNn']
        with users_lock:
            users[id_i]['DIDi_old']      = users[id_i]['DIDi_curr']
            users[id_i]['DIDi_curr']     = DIDi_new
            users[id_i]['bi']            = bi_new
            users[id_i]['did_old_valid'] = True
            users[id_i]['SK']            = SK
        with sensors_lock:
            sensors[sn_id]['SIDn_old']      = sensors[sn_id]['SIDn_curr']
            sensors[sn_id]['SIDn_curr']     = SIDn_new
            sensors[sn_id]['bn']            = bn_new
            sensors[sn_id]['sid_old_valid'] = True

        wall_s = time.perf_counter() - t_wall
        cpu_s  = time.process_time()  - t_cpu
        with stats_lock:
            stats['auth_count']  += 1
            stats['auth_wall_s'] += wall_s
            stats['auth_cpu_s']  += cpu_s
        print(f"[GW-ZHOU] Auth OK user={id_i}  wall={wall_s*1000:.2f} ms  "
              f"cpu={cpu_s*1000:.2f} ms  energy={wall_s*RPI_POWER_MW:.2f} mJ  SK={SK.hex()[:8]}")
    except Exception as e:
        print(f"[GW-ZHOU] auth error: {e}")
    finally:
        conn.close()


# ── Encrypted data (post-auth) ────────────────────────────────────────────────

def handle_data(conn, addr):
    t_wall = time.perf_counter()
    try:
        # DIDi_new(32) + AES(SK[:16], sensor[16]) = 48 B
        data = recv_msg(conn)
        if len(data) != 48:
            print(f"[GW-ZHOU] Data: bad len {len(data)}, expected 48")
            send_msg(conn, bytes([0xFF]))
            return

        recv_DIDi = bytes(data[0:32])
        enc_data  = bytes(data[32:48])

        with users_lock:
            u = next((v for v in users.values()
                      if v['DIDi_curr'] == recv_DIDi
                      or (v['did_old_valid'] and v['DIDi_old'] == recv_DIDi)), None)
        if u is None:
            print(f"[GW-ZHOU] Data: DIDi {recv_DIDi.hex()[:8]} not found")
            send_msg(conn, bytes([0xFF]))
            return

        plain = aes_dec_blocks(u['SK'][:16], enc_data)
        send_msg(conn, bytes([0xAC]))

        wall_s = time.perf_counter() - t_wall
        with stats_lock:
            stats['data_count']  += 1
            stats['data_wall_s'] += wall_s
        print(f"[GW-ZHOU] Data OK user={u['IDi_padded'][0]}  "
              f"val={plain[0]}  wall={wall_s*1000:.2f} ms")
    except Exception as e:
        print(f"[GW-ZHOU] data error: {e}")
    finally:
        conn.close()


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "=" * 70)
    print("[GW-ZHOU] ===== GW ENERGY SUMMARY =====")
    with stats_lock:
        ru = stats['reg_u_count'];   ruw = stats['reg_u_wall_s']
        rs = stats['reg_sn_count'];  rsw = stats['reg_sn_wall_s']
        ac = stats['auth_count'];    aw  = stats['auth_wall_s']
        dc = stats['data_count'];    dw  = stats['data_wall_s']
    print(f"{'Operation':<22} {'Count':>6} {'TotalWall(ms)':>14} {'TotalEnergy(mJ)':>16}")
    print("-" * 60)
    for lbl, cnt, wall in [('UserReg',    ru, ruw),
                            ('SNReg',      rs, rsw),
                            ('Auth(M1→M4)', ac, aw),
                            ('Data',        dc, dw)]:
        print(f"{lbl:<22} {cnt:>6} {wall*1000:>14.2f} {wall*RPI_POWER_MW:>16.2f}")
    total_w = ruw + rsw + aw + dw
    print("-" * 60)
    print(f"{'TOTAL':<22} {'':>6} {total_w*1000:>14.2f} {total_w*RPI_POWER_MW:>16.2f}")
    if ac > 0:
        print(f"\nAvg auth(M1->M4) latency : {aw/ac*1000:.2f} ms  "
              f"avg energy : {aw/ac*RPI_POWER_MW:.2f} mJ")
    print("=" * 70)


atexit.register(print_summary)


def listener(port, handler, name):
    srv = make_server(port)
    print(f"[GW-ZHOU] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    for port, fn, label in [
        (PORT_ZHOU_USER_REG, handle_user_reg, "user-reg"),
        (PORT_ZHOU_SN_REG,   handle_sn_reg,   "sn-reg"),
        (PORT_ZHOU_AUTH,     handle_auth,      "auth"),
        (PORT_ZHOU_DATA,     handle_data,      "data"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()

    print(f"[GW-ZHOU] Zhou scheme gateway (node {NODE_GW})  SN_IP={SN_IP}  Power={RPI_POWER_MW} mW")
    print(f"[GW-ZHOU] Ctrl+C to stop and print summary.")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[GW-ZHOU] Stopping.")
