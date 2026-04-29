#!/usr/bin/env python3
"""
Device D using Arbitrary PUF (no SEL, no recovery). Measures wall time (ns), CPU time, energy.
"""

import json, os, hashlib, hmac, secrets, time, socket

AS_IP = "192.168.1.113"
AS_PORT = 9000
GATEWAY_IP = "192.168.1.130"     # replace with your laptop's IP
GATEWAY_PORT = 9001
STORAGE_FILE = "device_storage.json"
ESTIMATED_POWER_W = 5.0

APUF_MASTER_D = b"dev_apuf_master_32b_long_!!!"

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
        if isinstance(v, bytes):
            copy[k] = v.hex()
        else:
            copy[k] = v
    with open(STORAGE_FILE, 'w') as f:
        json.dump(copy, f, indent=2)

class Measure:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        self.wall_start = time.perf_counter_ns()
        self.cpu_start = time.process_time()
        return self
    def __exit__(self, *args):
        wall_ns = time.perf_counter_ns() - self.wall_start
        cpu_s = time.process_time() - self.cpu_start
        energy = cpu_s * ESTIMATED_POWER_W
        print(f"\n=== {self.name} ===")
        print(f"Wall time: {wall_ns / 1e6:.3f} ms  ({wall_ns} ns)")
        print(f"CPU time: {cpu_s:.6f} s")
        print(f"Energy: {energy:.6f} J\n")

def enroll():
    device_id = f"device_{int(time.time()*1000)}"
    print(f"Device ID: {device_id}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((AS_IP, AS_PORT))
    sock.send(json.dumps({'type': 'enroll', 'ID_D': device_id}).encode())
    resp = json.loads(sock.recv(4096).decode())
    if resp.get('status') != 'enroll_step1':
        print("Enroll failed:", resp)
        sock.close()
        return False
    c_D = bytes.fromhex(resp['c_D'])
    m_D = bytes.fromhex(resp['m_D'])
    y_D = secrets.token_bytes(32)
    c_AS_D = secrets.token_bytes(8)
    R_D = APUF_D(c_D)
    storage = {'y_D': y_D, 'c_D': c_D, 'm_D': m_D, 'c_AS_D': c_AS_D, 'ID_D': device_id}
    save_storage(storage)
    sock.send(json.dumps({
        'type': 'enroll_finish',
        'y_D': y_D.hex(),
        'R_D': R_D.hex(),
        'c_AS_D': c_AS_D.hex()
    }).encode())
    final = json.loads(sock.recv(4096).decode())
    sock.close()
    if final.get('status') == 'success':
        print("Enrollment success")
        return True
    else:
        print("Enrollment final error:", final)
        return False

def authenticate():
    storage = load_storage()
    if not storage:
        print("No storage")
        return False
    id_d = storage['ID_D']
    y_D = storage['y_D']
    c_D = storage['c_D']
    m_D = storage['m_D']
    R_D = APUF_D(c_D)
    t_S1 = time.time()
    Y_D_H = H(y_D)
    Y_AS_D_H = xor_bytes(Y_D_H, H(R_D, m_D, id_d, str(t_S1).encode()))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((AS_IP, AS_PORT))
    sock.send(json.dumps({'type': 'auth', 'ID_D': id_d, 'Y_AS_D_H': Y_AS_D_H.hex(), 't_S1': t_S1}).encode())
    resp = json.loads(sock.recv(4096).decode())
    sock.close()
    if resp.get('status') == 'success':
        print("Authentication OK")
        return True
    else:
        print("Auth failed:", resp)
        return False

def key_exchange():
    storage = load_storage()
    if not storage:
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((GATEWAY_IP, GATEWAY_PORT))
    sock.send(json.dumps({'type': 'device_key_req', 'ID_D': storage['ID_D']}).encode())
    resp = json.loads(sock.recv(4096).decode())
    sock.close()
    if resp.get('status') != 'step1':
        print("Key exchange step1 failed:", resp)
        return False
    m_H = bytes.fromhex(resp['m_H'])
    ts2 = resp['ts2']
    y_D = storage['y_D']
    m_D = storage['m_D']
    c_D = storage['c_D']
    R_D = APUF_D(c_D)
    ID_AS = "auth_server"
    id_d = storage['ID_D']
    to_hash = H(y_D) + m_D + R_D + ID_AS.encode() + id_d.encode() + str(ts2).encode()
    m_new = xor_bytes(m_H, H(to_hash))
    storage['m_D'] = m_new
    K_GW_D = H(R_D, m_new)
    storage['K_GW_D'] = K_GW_D.hex()
    save_storage(storage)
    print(f"Session key: {K_GW_D.hex()}")
    print("Key exchange completed")
    return True

def shutdown_servers():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((GATEWAY_IP, GATEWAY_PORT))
        s.send(json.dumps({'type': 'shutdown'}).encode())
        s.close()
    except: pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((AS_IP, AS_PORT))
        s.send(json.dumps({'type': 'shutdown'}).encode())
        s.close()
    except: pass

def main():
    print("\n=== Starting automated device sequence (no recovery, single attempt) ===")
    with Measure("Enrollment"):
        if not enroll():
            return
    time.sleep(0.2)
    with Measure("Authentication"):
        if not authenticate():
            return
    time.sleep(0.2)
    with Measure("Key Exchange"):
        if not key_exchange():
            return
    print("All phases completed.")
    shutdown_servers()

if __name__ == '__main__':
    main()
