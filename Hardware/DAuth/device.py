#!/usr/bin/env python3
"""
DAuth Device — measurement-aligned with Proposed scheme.
Phases: Enrollment + 3× (Auth + KeyEx + Data)
Energy: wall_s × 3.8 W  (RPi 4B single-core active, matches Proposed)
Core protocol logic unchanged.
"""

import json, os, hashlib, hmac, secrets, time, socket

AS_IP        = "192.168.1.113"
AS_PORT      = 9000
GATEWAY_IP   = "192.168.1.201"   # Laptop — matches Proposed GW_IP
GATEWAY_PORT = 9001
STORAGE_FILE = "device_storage.json"

RPI_POWER_MW = 3800   # mW — RPi 4B typical single-core active
NUM_ROUNDS   = 3

APUF_MASTER_D = b"dev_apuf_master_32b_long_!!!"

# ── Core protocol primitives (unchanged) ─────────────────────────────────────

def APUF_D(challenge: bytes) -> bytes:
    if len(challenge) != 8:
        raise ValueError("Challenge must be 64 bits (8 bytes)")
    return hmac.new(APUF_MASTER_D, challenge, hashlib.sha256).digest()[:8]

def H(*args):
    h = hashlib.sha256()
    for a in args:
        if isinstance(a, str):
            a = a.encode()
        h.update(a)
    return h.digest()

def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))

def load_storage():
    if not os.path.exists(STORAGE_FILE):
        return {}
    with open(STORAGE_FILE, 'r') as f:
        data = json.load(f)
    for k in ['y_D', 'c_D', 'm_D', 'c_AS_D']:
        if k in data and isinstance(data[k], str):
            data[k] = bytes.fromhex(data[k])
    return data

def save_storage(data):
    copy = {}
    for k, v in data.items():
        copy[k] = v.hex() if isinstance(v, bytes) else v
    with open(STORAGE_FILE, 'w') as f:
        json.dump(copy, f, indent=2)

# ── Measurement helper ────────────────────────────────────────────────────────

def energy(wall_s):
    return round(wall_s * (RPI_POWER_MW / 1000), 6)   # Watts × seconds = Joules

results = []

# ── Enrollment ────────────────────────────────────────────────────────────────

def do_enrollment():
    t_wall = time.perf_counter()
    t_cpu  = time.process_time()

    device_id = f"device_{int(time.time()*1000)}"
    print(f"[DEV] Device ID: {device_id}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((AS_IP, AS_PORT))
    sock.send(json.dumps({'type': 'enroll', 'ID_D': device_id}).encode())
    resp = json.loads(sock.recv(4096).decode())
    if resp.get('status') != 'enroll_step1':
        print("[DEV] Enroll step1 failed:", resp)
        sock.close()
        return False

    c_D    = bytes.fromhex(resp['c_D'])
    m_D    = bytes.fromhex(resp['m_D'])
    y_D    = secrets.token_bytes(32)
    c_AS_D = secrets.token_bytes(8)
    R_D    = APUF_D(c_D)

    storage = {'y_D': y_D, 'c_D': c_D, 'm_D': m_D, 'c_AS_D': c_AS_D, 'ID_D': device_id}
    save_storage(storage)

    sock.send(json.dumps({
        'type':   'enroll_finish',
        'y_D':    y_D.hex(),
        'R_D':    R_D.hex(),
        'c_AS_D': c_AS_D.hex()
    }).encode())
    final = json.loads(sock.recv(4096).decode())
    sock.close()

    wall_s = time.perf_counter() - t_wall
    cpu_s  = time.process_time()  - t_cpu

    if final.get('status') != 'success':
        print("[DEV] Enrollment failed:", final)
        return False

    results.append({'phase':    'Enrollment',
                    'wall_s':   round(wall_s, 4),
                    'cpu_s':    round(cpu_s,  4),
                    'energy_j': energy(wall_s)})
    print(f"[DEV] Enrollment  wall={wall_s:.4f} s  cpu={cpu_s:.4f} s  "
          f"energy={energy(wall_s):.6f} J")
    return True

# ── Auth + KeyEx + Data (one round) ──────────────────────────────────────────

def do_round(round_num):
    storage = load_storage()
    if not storage:
        print(f"[DEV] R{round_num}: no storage found")
        return False

    id_d = storage['ID_D']
    y_D  = storage['y_D']
    c_D  = storage['c_D']
    m_D  = storage['m_D']
    R_D  = APUF_D(c_D)

    # ══ AUTH + KEY EXCHANGE — outer timer ════════════════════════════════════
    t_ak_wall = time.perf_counter();  t_ak_cpu = time.process_time()

    # ── Auth sub-phase ────────────────────────────────────────────────────────
    t0_wall = time.perf_counter();  t0_cpu = time.process_time()

    t_S1     = time.time()
    Y_D_H    = H(y_D)
    Y_AS_D_H = xor_bytes(Y_D_H, H(R_D, m_D, id_d, str(t_S1).encode()))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((AS_IP, AS_PORT))
    sock.send(json.dumps({'type': 'auth', 'ID_D': id_d,
                          'Y_AS_D_H': Y_AS_D_H.hex(), 't_S1': t_S1}).encode())
    auth_resp = json.loads(sock.recv(4096).decode())
    sock.close()

    auth_wall = time.perf_counter() - t0_wall
    auth_cpu  = time.process_time()  - t0_cpu

    if auth_resp.get('status') != 'success':
        print(f"[DEV] R{round_num} auth NACK")
        return False

    # ── Key Exchange sub-phase ────────────────────────────────────────────────
    t1_wall = time.perf_counter();  t1_cpu = time.process_time()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((GATEWAY_IP, GATEWAY_PORT))
    sock.send(json.dumps({'type': 'device_key_req', 'ID_D': id_d}).encode())
    ke_resp = json.loads(sock.recv(4096).decode())
    sock.close()

    if ke_resp.get('status') != 'step1':
        print(f"[DEV] R{round_num} KeyEx step1 failed:", ke_resp)
        return False

    m_H     = bytes.fromhex(ke_resp['m_H'])
    ts2     = ke_resp['ts2']
    ID_AS   = "auth_server"
    to_hash = H(y_D) + m_D + R_D + ID_AS.encode() + id_d.encode() + str(ts2).encode()
    m_new   = xor_bytes(m_H, H(to_hash))
    K_GW_D  = H(R_D, m_new)

    storage['m_D']    = m_new
    storage['K_GW_D'] = K_GW_D.hex()
    save_storage(storage)

    ke_wall = time.perf_counter() - t1_wall
    ke_cpu  = time.process_time()  - t1_cpu

    # End outer Auth+KeyEx timer
    ak_wall = time.perf_counter() - t_ak_wall
    ak_cpu  = time.process_time()  - t_ak_cpu

    # ── Data Communication phase ──────────────────────────────────────────────
    t2_wall = time.perf_counter();  t2_cpu = time.process_time()

    sensor     = b'\x2a' * 16                  # simulated sensor value
    key_stream = H(K_GW_D + b'data')[:16]      # hash-based keystream (no AES in DAuth)
    enc_data   = xor_bytes(key_stream, sensor)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((GATEWAY_IP, GATEWAY_PORT))
    sock.send(json.dumps({'type': 'data_comm', 'ID_D': id_d,
                          'data': enc_data.hex()}).encode())
    json.loads(sock.recv(4096).decode())
    sock.close()

    data_wall = time.perf_counter() - t2_wall
    data_cpu  = time.process_time()  - t2_cpu

    total_wall = ak_wall + data_wall
    total_cpu  = ak_cpu  + data_cpu

    print(f"[DEV] R{round_num} Auth+KeyEx  wall={ak_wall:.4f} s  cpu={ak_cpu:.4f} s  energy={energy(ak_wall):.6f} J")
    print(f"[DEV] R{round_num}   +- Auth    wall={auth_wall:.4f} s  cpu={auth_cpu:.4f} s  energy={energy(auth_wall):.6f} J")
    print(f"[DEV] R{round_num}   +- KeyEx   wall={ke_wall:.4f} s  cpu={ke_cpu:.4f} s  energy={energy(ke_wall):.6f} J")
    print(f"[DEV] R{round_num} Data        wall={data_wall:.4f} s  cpu={data_cpu:.4f} s  energy={energy(data_wall):.6f} J")
    print(f"[DEV] R{round_num} TOTAL       wall={total_wall:.4f} s  cpu={total_cpu:.4f} s  energy={energy(total_wall):.6f} J")

    results.append({
        'phase':         f'Round{round_num}',
        'ak_s':          round(ak_wall,   4), 'ak_energy_j':   energy(ak_wall),
        'auth_s':        round(auth_wall,  4), 'auth_energy_j': energy(auth_wall),
        'ke_s':          round(ke_wall,    4), 'ke_energy_j':   energy(ke_wall),
        'data_s':        round(data_wall,  4), 'data_energy_j': energy(data_wall),
        'total_s':       round(total_wall, 4), 'total_energy_j': energy(total_wall),
    })
    return True

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 70)
    print("[DEV] DAuth scheme — hardware energy + latency measurement")
    print(f"[DEV] AS={AS_IP}  GW={GATEWAY_IP}")
    print(f"[DEV] Power assumption: {RPI_POWER_MW} mW  Rounds: {NUM_ROUNDS}")
    print("=" * 70)
    time.sleep(1.5)   # allow GW + AS time to start

    if not do_enrollment():
        raise SystemExit("Enrollment failed — aborting")
    time.sleep(0.3)

    for r in range(1, NUM_ROUNDS + 1):
        print(f"\n[DEV] === Round {r} ===")
        ok = do_round(r)
        if not ok:
            print(f"[DEV] Round {r} FAILED — aborting")
            break
        time.sleep(0.3)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[DEV] ===== RESULTS SUMMARY =====")
    print(f"{'Phase':<24} {'Wall(s)':>10} {'CPU(s)':>10} {'Energy(J)':>12}")
    print("-" * 58)

    total_time_s   = 0.0
    total_energy_j = 0.0
    for r in results:
        if r['phase'] == 'Enrollment':
            print(f"{'Enrollment':<24} {r['wall_s']:>10.4f} {r['cpu_s']:>10.4f} {r['energy_j']:>12.6f}")
            total_time_s   += r['wall_s']
            total_energy_j += r['energy_j']
        else:
            print(f"{r['phase']+' Auth+KeyEx':<24} {r['ak_s']:>10.4f} {'':>10} {r['ak_energy_j']:>12.6f}")
            print(f"{'  +- Auth':<24} {r['auth_s']:>10.4f} {'':>10} {r['auth_energy_j']:>12.6f}")
            print(f"{'  +- KeyEx':<24} {r['ke_s']:>10.4f} {'':>10} {r['ke_energy_j']:>12.6f}")
            print(f"{r['phase']+' Data':<24} {r['data_s']:>10.4f} {'':>10} {r['data_energy_j']:>12.6f}")
            print(f"{r['phase']+' TOTAL':<24} {r['total_s']:>10.4f} {'':>10} {r['total_energy_j']:>12.6f}")
            total_time_s   += r['total_s']
            total_energy_j += r['total_energy_j']
        print()

    num_r = len(results) - 1
    print("=" * 58)
    print(f"{'GRAND TOTAL':<24} {total_time_s:>10.4f} {'':>10} {total_energy_j:>12.6f}")
    if num_r > 0:
        avg_ak   = sum(r['ak_s']        for r in results if r['phase'] != 'Enrollment') / num_r
        avg_ake  = sum(r['ak_energy_j'] for r in results if r['phase'] != 'Enrollment') / num_r
        avg_tot  = (total_time_s   - results[0]['wall_s']) / num_r
        avg_tote = (total_energy_j - results[0]['energy_j']) / num_r
        print(f"\nAvg Auth+KeyEx per round : {avg_ak:.4f} s  {avg_ake:.6f} J")
        print(f"Avg total    per round   : {avg_tot:.4f} s  {avg_tote:.6f} J")
    print("=" * 70)
