#!/usr/bin/env python3
"""
node_hw.py — IoT Device Node for LAAKA hardware simulation.

Runs on RPi #2 (device).  Mirrors the protocol from LAAKA/device-node.c:

  Phase 1  Registration    REG_REQ → RA (Laptop/GW)
                           REG_REP ← RA
  Phase 2  Authentication  AUTH_REQ → Fog (RPi #1)
                           AUTH_REP ← Fog
  Phase 3  Acknowledgement ACK → Fog
  Phase 4  Data loop       DATA → Fog  (10 packets)

Packet layouts:
  REG_REQ   payload = AES_enc(K_RA_D, IDd(1)|Ad(20)|pad(11))       = 32 B
  REG_REP   payload = AES_enc(K_RA_D, TIDd(20)|TIDf(20)|Af(20)|Bk(20)) = 80 B
  AUTH_REQ  payload = TIDd(20)|Td(1)|Cd(20)|Ed(20)|Gd(20)          = 81 B
  AUTH_REP  payload = TIDf(20)|Tf(1)|Ts(1)|Cf(20)|Ef(20)|Gf(20)    = 82 B
  ACK       payload = TIDd_new(20)|Ack_val(20)                      = 40 B
  DATA      payload = TIDd_new(20)|AES_enc(SK[0:16],sensor(16))     = 36 B
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_RA_D,
    TIDF_CONST,
    aes_ecb_enc, aes_ecb_dec,
    sha256_20, xor_bytes,
    to_json_bytes, from_json_bytes,
    parse_env_file,
    MetricsCollector, print_metric_report,
)


def _cfg_path() -> str:
    override = os.environ.get("LAAKA_ROLES_FILE")
    if override:
        return override
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "roles.env")


def _send(sock: socket.socket, msg: dict, addr: tuple,
          metrics: MetricsCollector, phase: str) -> None:
    raw = to_json_bytes(msg)
    sock.sendto(raw, addr)
    metrics.add_tx(phase, len(raw))


def _recv(sock: socket.socket, expected_type: str, timeout: float,
          metrics: MetricsCollector, phase: str) -> dict:
    sock.settimeout(timeout)
    while True:
        raw, _ = sock.recvfrom(8192)
        metrics.add_rx(phase, len(raw))
        msg = from_json_bytes(raw)
        if msg.get("type") == expected_type:
            return msg


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    gw_host         = cfg.get("GW_HOST",              "127.0.0.1")
    gw_port         = int(cfg.get("GW_PORT",           "5683"))
    fog_host        = cfg.get("AS_HOST",               "127.0.0.1")
    fog_port        = int(cfg.get("AS_PORT",            "5684"))
    device_id       = int(cfg.get("DEVICE_ID",         "81"))
    send_count      = int(cfg.get("NODE_SEND_COUNT",   "10"))
    send_interval_s = float(cfg.get("NODE_SEND_INTERVAL_S", "3"))
    cpu_power_w     = float(cfg.get("CPU_POWER_W",     "2.5"))
    net_j           = float(cfg.get("NET_ENERGY_PER_BYTE_J", "0.000002"))

    metrics = MetricsCollector(
        role="NODE",
        cpu_power_w=cpu_power_w,
        net_energy_per_byte_j=net_j,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", int(cfg.get("NODE_PORT", "5685"))))

    ra_addr  = (gw_host,  gw_port)
    fog_addr = (fog_host, fog_port)

    # =========================================================================
    # PHASE 1 — REGISTRATION
    #
    #   REG_REQ: AES_enc(K_RA_D, IDd(1)|Ad(20)|pad(11)) = 32 B  → RA
    #   REG_REP: AES_enc(K_RA_D, TIDd(20)|TIDf(20)|Af(20)|Bk(20)) = 80 B ← RA
    # =========================================================================
    metrics.start("register")

    r2 = os.urandom(20)
    Ad = sha256_20(bytes([device_id]) + r2)

    # REG_REQ: IDd(1) | Ad(20) | pad(11) = 32 B
    req_plain = bytearray(32)
    req_plain[0]    = device_id
    req_plain[1:21] = Ad
    enc_req = aes_ecb_enc(K_RA_D, bytes(req_plain))
    _send(sock, {"type": "REG_REQ", "enc": enc_req.hex()}, ra_addr, metrics, "register")
    print(f"[NODE {device_id}] Sent REG_REQ  Ad={Ad.hex()[:12]}...")

    rep_msg   = _recv(sock, "REG_REP", timeout=10.0, metrics=metrics, phase="register")
    rep_plain = aes_ecb_dec(K_RA_D, bytes.fromhex(rep_msg["enc"]))
    # Layout: TIDd(20)|TIDf(20)|Af(20)|Bk(20) = 80 B
    TIDd = bytes(rep_plain[0:20])
    TIDf = bytes(rep_plain[20:40])
    Af   = bytes(rep_plain[40:60])
    Bk   = bytes(rep_plain[60:80])

    metrics.stop("register")
    print(f"[NODE {device_id}] Registered OK  TIDd={TIDd.hex()[:12]}...")

    # =========================================================================
    # PHASE 2 — AUTHENTICATION
    #
    #   AUTH_REQ: TIDd(20)|Td(1)|Cd(20)|Ed(20)|Gd(20) = 81 B → Fog
    #   AUTH_REP: TIDf(20)|Tf(1)|Ts(1)|Cf(20)|Ef(20)|Gf(20) = 82 B ← Fog
    # =========================================================================
    metrics.start("auth")

    rd      = os.urandom(20)
    Td      = int(time.time()) & 0xFF
    TIDd_new = xor_bytes(TIDd, rd)

    Cd = sha256_20(bytes([Td]) + rd)
    Ed = xor_bytes(rd, sha256_20(Bk + Af))
    Gd = sha256_20(Ad + TIDd_new + Bk + rd)

    # AUTH_REQ: TIDd(20)|Td(1)|Cd(20)|Ed(20)|Gd(20) = 81 B
    auth_payload = TIDd + bytes([Td]) + Cd + Ed + Gd
    assert len(auth_payload) == 81
    _send(sock, {"type": "AUTH_REQ", "payload": auth_payload.hex()},
          fog_addr, metrics, "auth")
    print(f"[NODE {device_id}] Sent AUTH_REQ  Td={Td}")

    auth_rep_msg = _recv(sock, "AUTH_REP", timeout=10.0, metrics=metrics, phase="auth")
    rep_payload  = bytes.fromhex(auth_rep_msg["payload"])
    if len(rep_payload) < 82:
        print(f"[NODE {device_id}] AUTH_REP too short: {len(rep_payload)} B — aborting")
        return

    # Parse AUTH_REP: TIDf(20)|Tf(1)|Ts(1)|Cf(20)|Ef(20)|Gf(20)
    recv_TIDf = bytes(rep_payload[0:20])
    Tf        = rep_payload[20]
    Ts        = rep_payload[21]
    Cf        = bytes(rep_payload[22:42])
    Ef        = bytes(rep_payload[42:62])
    Gf        = bytes(rep_payload[62:82])

    # Verify TIDf matches what RA provided
    if recv_TIDf != TIDf:
        print(f"[NODE {device_id}] TIDf mismatch — aborting")
        return

    # Recover rf = Ef XOR H(TIDd_new)
    rf = xor_bytes(Ef, sha256_20(TIDd_new))

    # Verify Cf = H(Tf || rf)
    if sha256_20(bytes([Tf]) + rf) != Cf:
        print(f"[NODE {device_id}] Cf verification failed — aborting")
        return

    # Derive SK = H(rd || rf || Ts)
    SK = sha256_20(rd + rf + bytes([Ts]))

    # Verify Gf = H(TIDf_new || Bk || rf || SK || Ts)
    TIDf_new = xor_bytes(TIDf, rf)
    if sha256_20(TIDf_new + Bk + rf + SK + bytes([Ts])) != Gf:
        print(f"[NODE {device_id}] Gf verification failed — aborting")
        return

    metrics.stop("auth")
    print(f"[NODE {device_id}] Auth OK  SK={SK.hex()[:12]}...  Ts={Ts}")

    # =========================================================================
    # PHASE 3 — ACKNOWLEDGEMENT
    #
    #   ACK: TIDd_new(20)|Ack_val(20) = 40 B → Fog
    # =========================================================================
    metrics.start("ack")

    Ack_val = sha256_20(rf + Bk + SK)
    ack_payload = TIDd_new + Ack_val
    assert len(ack_payload) == 40
    _send(sock, {"type": "ACK", "payload": ack_payload.hex()},
          fog_addr, metrics, "ack")

    metrics.stop("ack")
    print(f"[NODE {device_id}] Sent ACK")

    # Allow Fog time to process ACK before data starts
    time.sleep(0.5)

    # =========================================================================
    # PHASE 4 — DATA LOOP
    #
    #   DATA: TIDd_new(20)|AES_enc(SK[0:16], sensor(16)) = 36 B → Fog
    #   Sensor layout: [IDd(1)|timestamp(1)|zeros(14)]  (mirrors C source)
    # =========================================================================
    metrics.start("data")
    K_AES = SK[:16]

    for i in range(1, send_count + 1):
        sensor    = bytearray(16)
        sensor[0] = device_id
        sensor[1] = int(time.time()) & 0xFF
        enc_sensor = aes_ecb_enc(K_AES, bytes(sensor))

        data_payload = TIDd_new + enc_sensor   # 36 B
        assert len(data_payload) == 36
        _send(sock, {"type": "DATA", "payload": data_payload.hex()},
              fog_addr, metrics, "data")
        print(f"[NODE {device_id}] Sent DATA #{i}")
        time.sleep(send_interval_s)

    metrics.stop("data")
    print(f"[NODE {device_id}] Completed data loop.")

    report = metrics.build_report(device_id=str(device_id))
    print_metric_report(report)


if __name__ == "__main__":
    main()
