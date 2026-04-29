#!/usr/bin/env python3
import json
import socket
import threading
import sys                     # <-- add this import
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

AS_IP = "192.168.1.113"
AS_PORT = 9000
GATEWAY_LISTEN_IP = "0.0.0.0"
GATEWAY_LISTEN_PORT = 9001
GATEWAY_SHARED_KEY = b"this_is_32_byte_key_for_gw_as_!!"

def aes_gcm_decrypt(key, encrypted_data):
    nonce = encrypted_data[:12]
    tag = encrypted_data[12:28]
    ciphertext = encrypted_data[28:]
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()

def handle_device(conn, addr, req):
    id_d = req.get('ID_D')
    if not id_d:
        conn.send(json.dumps({'status': 'error', 'msg': 'No ID'}).encode())
        conn.close()
        return
    # Ask AS for key material
    as_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    as_sock.connect((AS_IP, AS_PORT))
    as_sock.send(json.dumps({'type': 'key_req', 'ID_D': id_d, 'ID_AS': 'gateway'}).encode())
    resp = as_sock.recv(4096).decode()
    as_sock.close()
    if not resp:
        conn.send(json.dumps({'status': 'error', 'msg': 'No response from AS'}).encode())
        conn.close()
        return
    resp_data = json.loads(resp)
    if resp_data.get('status') != 'success':
        conn.send(json.dumps({'status': 'error', 'msg': resp_data.get('msg', 'AS error')}).encode())
        conn.close()
        return
    # Forward to device
    conn.send(json.dumps({
        'status': 'step1',
        'm_H': resp_data['m_H'],
        'ts2': resp_data['ts2'],
        'auth_token': resp_data['auth_token']
    }).encode())
    conn.close()
    # Confirm token with AS
    confirm = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    confirm.connect((AS_IP, AS_PORT))
    confirm.send(json.dumps({'type': 'token_confirm', 'auth_token': resp_data['auth_token'], 'ID_D': id_d}).encode())
    ack = json.loads(confirm.recv(4096).decode())
    confirm.close()
    if ack.get('status') == 'success':
        print(f"[Gateway] Session established with {id_d}")
    else:
        print(f"[Gateway] Token confirmation failed: {ack.get('msg')}")

def start():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((GATEWAY_LISTEN_IP, GATEWAY_LISTEN_PORT))
    server.listen(5)
    print(f"[Gateway] Listening on port {GATEWAY_LISTEN_PORT}")
    while True:
        conn, addr = server.accept()
        try:
            data = json.loads(conn.recv(4096).decode())
            # Check for shutdown command
            if data.get('type') == 'shutdown':
                print("[Gateway] Shutdown requested, exiting.")
                conn.send(json.dumps({'status': 'ok'}).encode())
                conn.close()
                sys.exit(0)      # now sys is defined
            if data.get('type') == 'device_key_req':
                handle_device(conn, addr, data)
            else:
                conn.send(json.dumps({'status': 'error', 'msg': 'Bad type'}).encode())
                conn.close()
        except Exception as e:
            print(f"Gateway error: {e}")
            conn.close()

if __name__ == '__main__':
    start()