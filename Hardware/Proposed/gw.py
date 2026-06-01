#!/usr/bin/env python3
"""
Gateway — Proposed Scheme (Revised Anonymity)
Runs on: PC

Listens on three ports:
  PORT_GW_TOKEN  (5001)  ← AS: [PID_new(32)|id_as(1)|AES3(K_GW_AS, enc_tok)(48)] = 81 B
  PORT_GW_KEYEX  (5002)  ← Device: [PID(32)|AES1(K_GW_D[:16], nonce_blk)(16)] = 48 B
  PORT_GW_DATA   (5003)  ← Device: [PID(32)|AES1(K_GW_D[:16], sensor_blk)(16)] = 48 B
"""
import sys, os, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import PORT_GW_TOKEN, PORT_GW_KEYEX, PORT_GW_DATA, NODE_GW

sessions = {}          # pid_hex → {K_GW_D, ID_d, ID_as, ke_done}
sessions_lock = threading.Lock()

def handle_token(conn, addr):
    """Receive 81-byte auth token from AS, install session."""
    try:
        data = recv_msg(conn)
        if len(data) != 81:
            print(f"[GW] Bad token len={len(data)}")
            return
        pid_new  = data[0:32]
        id_as    = data[32]
        enc_tok  = data[33:81]              # 48 bytes, 3 AES blocks

        plain = aes_dec_blocks(K_GW_AS, enc_tok)
        id_d      = plain[0]
        id_as_chk = plain[1]
        K_GW_D    = plain[16:48]           # 32 bytes

        if id_as_chk != id_as:
            print(f"[GW] Token rejected: ID_AS mismatch ({id_as_chk} vs {id_as})")
            send_msg(conn, bytes([0xFF]))
            return

        pid_hex = pid_new.hex()
        with sessions_lock:
            sessions[pid_hex] = {
                'K_GW_D': K_GW_D, 'ID_d': id_d, 'ID_as': id_as, 'ke_done': False
            }
        print(f"[GW] Session stored: dev={id_d} as={id_as} PID={pid_hex[:6]}")
        send_msg(conn, b'OK')
    except Exception as e:
        print(f"[GW] token handler: {e}")
    finally:
        conn.close()

def handle_keyex(conn, addr):
    """Device key-exchange: decrypt nonce, reply nonce+1 encrypted."""
    try:
        data = recv_msg(conn)
        if len(data) != 48:
            print(f"[GW] Bad KeyEx len={len(data)}")
            return
        pid     = data[0:32]
        enc_blk = data[32:48]
        pid_hex = pid.hex()

        with sessions_lock:
            sess = sessions.get(pid_hex)
        if sess is None:
            print(f"[GW] KeyEx: unknown PID {pid_hex[:6]}")
            send_msg(conn, bytes([0xFF]))
            return

        K16   = sess['K_GW_D'][:16]
        plain = aes_dec_blocks(K16, enc_blk)
        nonce = plain[0]

        resp_blk = bytearray(16)
        resp_blk[0] = (nonce + 1) & 0xFF
        send_msg(conn, aes_enc_blocks(K16, bytes(resp_blk)))

        with sessions_lock:
            sessions[pid_hex]['ke_done'] = True
        print(f"[GW] KeyEx OK: dev={sess['ID_d']} PID={pid_hex[:6]} nonce={nonce}")
    except Exception as e:
        print(f"[GW] keyex handler: {e}")
    finally:
        conn.close()

def handle_data(conn, addr):
    """Receive AES-encrypted sensor data, verify session, ACK."""
    try:
        data = recv_msg(conn)
        if len(data) != 48:
            print(f"[GW] Bad data len={len(data)}")
            return
        pid     = data[0:32]
        enc_blk = data[32:48]
        pid_hex = pid.hex()

        with sessions_lock:
            sess = sessions.get(pid_hex)
        if sess is None:
            print(f"[GW] Data: unknown PID {pid_hex[:6]}")
            send_msg(conn, bytes([0xFF]))
            return

        K16   = sess['K_GW_D'][:16]
        plain = aes_dec_blocks(K16, enc_blk)
        print(f"[GW] Data OK: dev={sess['ID_d']} val={plain[0]} PID={pid_hex[:6]}")
        send_msg(conn, bytes([0xAC]))
    except Exception as e:
        print(f"[GW] data handler: {e}")
    finally:
        conn.close()

def listener(port, handler, name):
    srv = make_server(port)
    print(f"[GW] Listening on :{port} ({name})")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handler, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    for port, fn, label in [
        (PORT_GW_TOKEN, handle_token, "token"),
        (PORT_GW_KEYEX, handle_keyex, "keyex"),
        (PORT_GW_DATA,  handle_data,  "data"),
    ]:
        threading.Thread(target=listener, args=(port, fn, label), daemon=True).start()

    print(f"[GW] Proposed scheme gateway (node {NODE_GW}) running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[GW] Stopping.")
