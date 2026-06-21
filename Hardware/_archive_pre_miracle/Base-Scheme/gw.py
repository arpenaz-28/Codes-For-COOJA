#!/usr/bin/env python3
"""
Gateway — Base Scheme (LAAKA / das2026comsnets)
Runs on: PC

Listens on:
  PORT_GW_TOKEN  (5001)  ← AS: [AES(k_gw_as, [id_d,id_as,ts,0×])(16) |
                                 AES(k_gw_as, K_GW_D[0:16])(16) |
                                 AES(k_gw_as, K_GW_D[16:32])(16)] = 48 B
  PORT_GW_KEYEX  (5002)  ← Device: [id_d(1) | AES(K_GW_D[:16], [alpha,0×])(16)] = 17 B
  PORT_GW_DATA   (5003)  ← Device: [id_d(1) | AES(K_GW_D[:16], sensor)(16)]  = 17 B
"""
import sys, os, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import *
from config import PORT_GW_TOKEN, PORT_GW_KEYEX, PORT_GW_DATA, NODE_GW, DH_G, DH_P, DH_B

sessions = {}          # id_d → {k_gw_d}
sessions_lock = threading.Lock()

def handle_token(conn, addr):
    """Receive 48-byte auth token from AS."""
    try:
        data = recv_msg(conn)
        if len(data) != 48:
            print(f"[GW-BASE] Bad token len={len(data)}")
            return
        block0 = aes_dec_blocks(K_GW_AS, data[0:16])
        key1   = aes_dec_blocks(K_GW_AS, data[16:32])
        key2   = aes_dec_blocks(K_GW_AS, data[32:48])

        id_d   = block0[0]
        id_as  = block0[1]
        k_gw_d = key1 + key2

        with sessions_lock:
            sessions[id_d] = {'k_gw_d': k_gw_d}

        print(f"[GW-BASE] Token stored: dev={id_d} as={id_as}")
        send_msg(conn, b'Received')
    except Exception as e:
        print(f"[GW-BASE] token: {e}")
    finally:
        conn.close()

def handle_keyex(conn, addr):
    """DH key exchange: receive alpha from device, reply with beta."""
    try:
        data = recv_msg(conn)
        if len(data) != 17:
            print(f"[GW-BASE] Bad KeyEx len={len(data)}")
            return
        id_d    = data[0]
        enc_blk = data[1:17]

        with sessions_lock:
            sess = sessions.get(id_d)
        if sess is None:
            print(f"[GW-BASE] KeyEx: unknown dev {id_d}")
            send_msg(conn, bytes([0xFF]))
            return

        K16   = sess['k_gw_d'][:16]
        plain = aes_dec_blocks(K16, enc_blk)
        alpha = plain[0]

        # Update session key: k_gw_d[0] = (alpha XOR b) % p
        new_k = bytearray(sess['k_gw_d'])
        new_k[0] = (alpha ^ DH_B) % DH_P
        for i in range(1, 32):
            new_k[i] = 0

        # Reply: beta = (g XOR b) % p, encrypted
        beta = (DH_G ^ DH_B) % DH_P
        resp_blk = bytearray(16)
        resp_blk[0] = beta
        send_msg(conn, aes_enc_blocks(K16, bytes(resp_blk)))

        with sessions_lock:
            sessions[id_d]['k_gw_d'] = bytes(new_k)
        print(f"[GW-BASE] KeyEx OK: dev={id_d} alpha={alpha} beta={beta}")
    except Exception as e:
        print(f"[GW-BASE] keyex: {e}")
    finally:
        conn.close()

def handle_data(conn, addr):
    """Receive encrypted sensor data."""
    try:
        data = recv_msg(conn)
        if len(data) != 17:
            print(f"[GW-BASE] Bad data len={len(data)}")
            return
        id_d    = data[0]
        enc_blk = data[1:17]

        with sessions_lock:
            sess = sessions.get(id_d)
        if sess is None:
            print(f"[GW-BASE] Data: unknown dev {id_d}")
            send_msg(conn, bytes([0xFF]))
            return

        K16   = sess['k_gw_d'][:16]
        plain = aes_dec_blocks(K16, enc_blk)
        print(f"[GW-BASE] Data OK: dev={id_d} val={plain[0]}")
        send_msg(conn, bytes([0xAC]))
    except Exception as e:
        print(f"[GW-BASE] data: {e}")
    finally:
        conn.close()

def listener(port, handler, name):
    srv = make_server(port)
    print(f"[GW-BASE] Listening on :{port} ({name})")
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

    print(f"[GW-BASE] Base scheme gateway (node {NODE_GW}) running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[GW-BASE] Stopping.")
