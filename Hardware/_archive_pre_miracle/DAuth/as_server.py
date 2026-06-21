#!/usr/bin/env python3
"""
Authentication Server using Arbitrary PUF (no SEL, no recovery attempts).
"""

import json, os, hashlib, hmac, secrets, time, socket, threading
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

AS_IP = "0.0.0.0"
AS_PORT = 9000
GATEWAY_SHARED_KEY = b"this_is_32_byte_key_for_gw_as_!!"
STORAGE_FILE = "as_storage.json"

APUF_MASTER_AS = b"as_apuf_master_32b_long_!!!"

def APUF_AS(challenge: bytes) -> bytes:
    if len(challenge) != 8:
        raise ValueError("Challenge must be 64 bits (8 bytes)")
    h = hmac.new(APUF_MASTER_AS, challenge, hashlib.sha256).digest()
    return h[:8]

def H(*args):
    h = hashlib.sha256()
    for a in args:
        if isinstance(a, str):
            a = a.encode()
        h.update(a)
    return h.digest()

def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))

def aes_gcm_encrypt(key, plaintext):
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return ciphertext, nonce, encryptor.tag

def load_storage():
    if not os.path.exists(STORAGE_FILE):
        return {}
    with open(STORAGE_FILE, 'r') as f:
        data = json.load(f)
    for dev, rec in data.items():
        for k, v in rec.items():
            if k in ['c_D', 'm_D', 'c_AS_D', 'phi_AS_D', 'T_Acc']:
                rec[k] = bytes.fromhex(v)
    return data

def save_storage(data):
    copy = {}
    for dev, rec in data.items():
        copy[dev] = {}
        for k, v in rec.items():
            if isinstance(v, bytes):
                copy[dev][k] = v.hex()
            else:
                copy[dev][k] = v
    with open(STORAGE_FILE, 'w') as f:
        json.dump(copy, f, indent=2)

def handle_enrollment(conn, addr, req):
    id_d = req['ID_D']
    storage = load_storage()
    if id_d in storage:
        conn.send(json.dumps({'status': 'error', 'msg': 'ID exists'}).encode())
        return
    c_D = secrets.token_bytes(8)
    m_D = secrets.token_bytes(32)
    conn.send(json.dumps({'status': 'enroll_step1',
                          'c_D': c_D.hex(),
                          'm_D': m_D.hex()}).encode())

    resp = json.loads(conn.recv(4096).decode())
    if resp.get('type') != 'enroll_finish':
        conn.send(json.dumps({'status': 'error', 'msg': 'Protocol mismatch'}).encode())
        return

    y_D = bytes.fromhex(resp['y_D'])
    R_D = bytes.fromhex(resp['R_D'])
    c_AS_D = bytes.fromhex(resp['c_AS_D'])
    if len(c_AS_D) != 8:
        conn.send(json.dumps({'status': 'error', 'msg': 'c_AS_D must be 64-bit'}).encode())
        return

    Y_D_H = H(y_D)
    T_Acc = Y_D_H
    R_AS_D = APUF_AS(c_AS_D)
    phi_AS_D = xor_bytes(R_AS_D, R_D)

    storage[id_d] = {
        'T_Acc': T_Acc,
        'phi_AS_D': phi_AS_D,
        'c_AS_D': c_AS_D,
        'm_D': m_D,
        'c_D': c_D
    }
    save_storage(storage)
    conn.send(json.dumps({'status': 'success'}).encode())
    print(f"[AS] Device {id_d} enrolled.")

def handle_authentication(conn, addr, req):
    id_d = req['ID_D']
    Y_AS_D_H = bytes.fromhex(req['Y_AS_D_H'])
    t_S1 = req['t_S1']
    storage = load_storage()
    if id_d not in storage:
        conn.send(json.dumps({'status': 'error', 'msg': 'Unknown device'}).encode())
        return
    rec = storage[id_d]
    if abs(time.time() - t_S1) > 60:
        conn.send(json.dumps({'status': 'error', 'msg': 'Timestamp expired'}).encode())
        return

    m_D = rec['m_D']
    c_AS_D = rec['c_AS_D']
    phi_AS_D = rec['phi_AS_D']
    stored_T_Acc = rec['T_Acc']

    R_AS_D = APUF_AS(c_AS_D)
    R_D_prime = xor_bytes(phi_AS_D, R_AS_D)
    Y_D_H_prime = xor_bytes(Y_AS_D_H, H(R_D_prime, m_D, id_d, str(t_S1).encode()))
    T_Acc_new = bytes(a & b for a, b in zip(stored_T_Acc, Y_D_H_prime))

    if T_Acc_new == stored_T_Acc:
        conn.send(json.dumps({'status': 'success'}).encode())
        print(f"[AS] Device {id_d} authenticated.")
    else:
        conn.send(json.dumps({'status': 'error', 'msg': 'Authentication failed'}).encode())
        print(f"[AS] Device {id_d} authentication FAILED.")

def handle_gateway_key_request(conn, addr, req):
    id_d = req['ID_D']
    storage = load_storage()
    if id_d not in storage:
        conn.send(json.dumps({'status': 'error', 'msg': 'Unknown device'}).encode())
        return
    rec = storage[id_d]
    R_AS_D = APUF_AS(rec['c_AS_D'])
    R_D_prime = xor_bytes(rec['phi_AS_D'], R_AS_D)
    Y_D_H = rec['T_Acc']

    n1 = secrets.token_bytes(32)
    ts2 = time.time()
    m_new = H(n1)
    to_hash = Y_D_H + rec['m_D'] + R_D_prime + req['ID_AS'].encode() + id_d.encode() + str(ts2).encode()
    m_H = xor_bytes(m_new, H(to_hash))
    ts_auth = time.time()
    K_GW_D = H(R_D_prime, m_new)

    plain = id_d.encode() + req['ID_AS'].encode() + K_GW_D + str(ts_auth).encode()
    ciphertext, nonce, tag = aes_gcm_encrypt(GATEWAY_SHARED_KEY, plain)
    auth_token = nonce + tag + ciphertext

    rec['m_D'] = m_new
    save_storage(storage)

    conn.send(json.dumps({
        'status': 'success',
        'm_H': m_H.hex(),
        'ts2': ts2,
        'auth_token': auth_token.hex()
    }).encode())
    print(f"[AS] Key material sent for {id_d}.")

def handle_token_confirm(conn, addr, req):
    conn.send(json.dumps({'status': 'success'}).encode())

def handle_shutdown(conn, addr, req):
    print("[AS] Shutdown requested, exiting.")
    conn.send(json.dumps({'status': 'ok'}).encode())
    os._exit(0)

def handle_client(conn, addr):
    try:
        data = json.loads(conn.recv(4096).decode())
        t = data.get('type')
        if t == 'enroll':
            handle_enrollment(conn, addr, data)
        elif t == 'auth':
            handle_authentication(conn, addr, data)
        elif t == 'key_req':
            handle_gateway_key_request(conn, addr, data)
        elif t == 'token_confirm':
            handle_token_confirm(conn, addr, data)
        elif t == 'shutdown':
            handle_shutdown(conn, addr, data)
        else:
            conn.send(json.dumps({'status': 'error', 'msg': 'Unknown type'}).encode())
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((AS_IP, AS_PORT))
    server.listen(5)
    print(f"[AS] Listening on {AS_IP}:{AS_PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == '__main__':
    main()