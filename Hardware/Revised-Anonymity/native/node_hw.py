#!/usr/bin/env python3
"""
node_hw.py — IoT Device Node for Revised-Anonymity hardware simulation.

Runs on RPi #2 (device).  Mirrors the two-round protocol from
Revised-Anonymity/device-node.c:

  State machine:
    Phase 1  Enrollment   Reg-0 + Reg-1  →  AS
    Phase 2  Round 1 Auth /test/auth     →  AS  (sends 65 B, receives 2 B)
    Phase 3  Round 2 KeyEx /test/keyex   →  AS  (sends 33 B, receives 32 B)
    Phase 4  Data loop    /test/data     →  GW  (sends 48 B each)

Packet layout (bytes sent over UDP as hex-encoded JSON):
  REG0_REQ  payload = AES_enc(K_AS_D, id_d(1)|pad(15))           = 16 B
  REG0_REP  payload = AES_enc(K_AS_D, c_d(1)|m_d(32)|pad(15))    = 48 B
  REG1_REQ  payload = AES_enc(K_AS_D, id_d(1)|Y_dH(32)|R_d(1)|c_as_d(1)|pad(13)) = 48 B
  AUTH_REQ  payload = PID(32)|y_asd(32)|ts_1(1)                  = 65 B
  AUTH_REP  ack=0xAC, ts2=<int>
  KEYEX_REQ payload = PID(32)|ts_2(1)                            = 33 B
  KEYEX_REP m_H = <32 B hex>
  DATA      payload = PID(32)|AES_enc(K_GW_D[0:16], sensor(16)) = 48 B
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_AS_D,
    aes_ecb_enc, aes_ecb_dec,
    sha256, xor_bytes,
    simulate_puf_response, generate_helper, regenerate_response,
    seq_ts_fresh,
    to_json_bytes, from_json_bytes,
    parse_env_file,
    MetricsCollector, print_metric_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg_path() -> str:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = parse_env_file(_cfg_path())

    as_host  = cfg.get("AS_HOST",  "127.0.0.1")
    as_port  = int(cfg.get("AS_PORT",  "5684"))
    gw_host  = cfg.get("GW_HOST",  "127.0.0.1")
    gw_port  = int(cfg.get("GW_PORT",  "5683"))

    device_id       = int(cfg.get("DEVICE_ID",           "81"))
    as_node_id      = int(cfg.get("AS_NODE_ID",           "2"))
    send_count      = int(cfg.get("NODE_SEND_COUNT",      "10"))
    send_interval_s = float(cfg.get("NODE_SEND_INTERVAL_S", "3"))
    cpu_power_w     = float(cfg.get("CPU_POWER_W",        "2.5"))
    net_j           = float(cfg.get("NET_ENERGY_PER_BYTE_J", "0.000002"))

    # Constants from C source
    y_d    = 2   # device group secret (static uint8_t y_d = 2)
    c_as_d = 3   # challenge sent to AS during Reg-1 (static uint8_t c_as_d = 3)
    ts_1   = 1   # sequence counter (uint8, wraps at 256)

    metrics = MetricsCollector(
        role="NODE",
        cpu_power_w=cpu_power_w,
        net_energy_per_byte_j=net_j,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", int(cfg.get("NODE_PORT", "5685"))))

    as_addr = (as_host, as_port)
    gw_addr = (gw_host, gw_port)

    # =========================================================================
    # PHASE 1 — ENROLLMENT
    #
    # Reg-0:
    #   Send: AES_enc(K_AS_D, [id_d | pad(15)])        = 16 B
    #   Recv: AES_enc(K_AS_D, [c_d(1) | m_d(32) | pad(15)]) = 48 B
    #
    # Reg-1:
    #   Send: AES_enc(K_AS_D, [id_d(1)|Y_dH(32)|R_d(1)|c_as_d(1)|pad(13)]) = 48 B
    #   Recv: REG1_REP  (empty ack)
    # =========================================================================
    metrics.start("enroll")

    # --- Reg-0 ---
    p0 = bytearray(16)
    p0[0] = device_id
    enc_p0 = aes_ecb_enc(K_AS_D, bytes(p0))
    _send(sock, {"type": "REG0_REQ", "enc": enc_p0.hex()}, as_addr, metrics, "enroll")
    print(f"[NODE {device_id}] Sent Reg-0")

    rep0    = _recv(sock, "REG0_REP", timeout=10.0, metrics=metrics, phase="enroll")
    plain48 = aes_ecb_dec(K_AS_D, bytes.fromhex(rep0["enc"]))
    # Layout: c_d(1) | m_d(32) | pad(15)
    c_d = plain48[0]
    m_d = bytearray(plain48[1:33])
    print(f"[NODE {device_id}] Reg-0 OK: c_d={c_d}")

    # Compute PUF response and helper (mirrors Reg-1 block in C)
    R_d_enroll = simulate_puf_response(device_id, c_d)
    h_d, _     = generate_helper(R_d_enroll)

    # Y_dH = H(y_d as single byte)
    Y_dH_enroll = sha256(bytes([y_d]))

    # --- Reg-1 ---
    # Layout: id_d(1)|Y_dH(32)|R_d(1)|c_as_d(1)|pad(13) = 48 B
    p1 = bytearray(48)
    p1[0]     = device_id
    p1[1:33]  = Y_dH_enroll
    p1[33]    = R_d_enroll
    p1[34]    = c_as_d
    enc_p1    = aes_ecb_enc(K_AS_D, bytes(p1))
    _send(sock, {"type": "REG1_REQ", "enc": enc_p1.hex()}, as_addr, metrics, "enroll")
    print(f"[NODE {device_id}] Sent Reg-1")

    _recv(sock, "REG1_REP", timeout=10.0, metrics=metrics, phase="enroll")
    metrics.stop("enroll")
    print(f"[NODE {device_id}] Enrolled OK")

    # =========================================================================
    # PHASE 2 — ROUND 1: AUTHENTICATION  (/test/auth)
    #
    #   Send: PID(32) | y_asd(32) | ts_1(1)  = 65 B
    #   Recv: ACK(1)  | ts_2(1)              =  2 B  (NO key material yet)
    # =========================================================================
    metrics.start("auth")

    # Regenerate R_d from helper
    R_d = regenerate_response(c_d, h_d)

    # auth_PID = H(id_d || m_d)
    auth_PID  = sha256(bytes([device_id]) + bytes(m_d))

    # auth_Y_dH = H(y_d)
    auth_Y_dH = sha256(bytes([y_d]))

    # mask = H(R_d(1) | m_d(32) | auth_PID(32) | ts_1(1))  → 66 B input
    mask_in = bytes([R_d]) + bytes(m_d) + auth_PID + bytes([ts_1])
    assert len(mask_in) == 66
    mask  = sha256(mask_in)
    y_asd = xor_bytes(auth_Y_dH, mask)

    # auth payload: PID(32) | y_asd(32) | ts_1(1) = 65 B
    auth_payload = auth_PID + y_asd + bytes([ts_1])
    assert len(auth_payload) == 65
    _send(sock, {"type": "AUTH_REQ", "payload": auth_payload.hex()},
          as_addr, metrics, "auth")
    print(f"[NODE {device_id}] Round 1: Sent AUTH  PID={auth_PID.hex()[:12]}...  ts_1={ts_1}")

    auth_rep = _recv(sock, "AUTH_REP", timeout=10.0, metrics=metrics, phase="auth")
    ack  = int(auth_rep["ack"], 16)
    ts_2 = int(auth_rep["ts2"])
    if ack != 0xAC:
        print(f"[NODE {device_id}] Bad ACK byte: {ack:#04x} — aborting")
        return

    metrics.stop("auth")
    print(f"[NODE {device_id}] Round 1 Auth OK  ts_2={ts_2}")

    # =========================================================================
    # PHASE 3 — ROUND 2: KEY EXCHANGE  (/test/keyex)
    #
    #   Send: PID(32) | ts_2(1)  = 33 B
    #   Recv: m_H(32)            = 32 B
    #
    #   Device recovers m_new → K_GW_D → rotates PID.
    # =========================================================================
    metrics.start("keyex")

    # keyex payload: auth_PID(32) | ts_2(1) = 33 B
    keyex_payload = auth_PID + bytes([ts_2])
    assert len(keyex_payload) == 33
    _send(sock, {"type": "KEYEX_REQ", "payload": keyex_payload.hex()},
          as_addr, metrics, "keyex")
    print(f"[NODE {device_id}] Round 2: Sent KEYEX  ts_2={ts_2}")

    keyex_rep = _recv(sock, "KEYEX_REP", timeout=10.0, metrics=metrics, phase="keyex")
    m_H = bytes.fromhex(keyex_rep["m_H"])

    # Recover m_new:
    #   mh_mask = H(auth_Y_dH(32) | m_d(32) | R_d(1) | id_as(1) | auth_PID(32) | ts_2(1))
    #           = 99 B input
    mh_in = auth_Y_dH + bytes(m_d) + bytes([R_d, as_node_id]) + auth_PID + bytes([ts_2])
    assert len(mh_in) == 99
    mh_mask = sha256(mh_in)
    m_new   = xor_bytes(m_H, mh_mask)

    # K_GW_D = H(R_d(1) | m_new(32)) = 33 B input
    k_gw_d = sha256(bytes([R_d]) + m_new)

    # Rotate m_d and PID
    m_d = bytearray(m_new)
    PID = sha256(bytes([device_id]) + m_new)
    ts_1 = (ts_1 + 1) & 0xFF

    metrics.stop("keyex")
    print(f"[NODE {device_id}] Round 2 KeyEx OK  New PID={PID.hex()[:12]}...")

    # Allow GW time to receive the token from AS before data starts.
    time.sleep(1.5)

    # =========================================================================
    # PHASE 4 — DATA LOOP  (/test/data)
    #
    #   Send: PID(32) | AES_enc(K_GW_D[0:16], sensor(16)) = 48 B
    #   (Mirrors C: sensor[0] = 9, rest = 0x00)
    # =========================================================================
    metrics.start("data")
    K_AES = k_gw_d[:16]   # AES-128 key = first 16 bytes of K_GW_D

    for i in range(1, send_count + 1):
        sensor    = bytearray(16)
        sensor[0] = 9          # constant payload — same as C source
        enc_sensor = aes_ecb_enc(K_AES, bytes(sensor))

        data_payload = PID + enc_sensor   # 48 B
        assert len(data_payload) == 48
        _send(sock, {"type": "DATA", "payload": data_payload.hex()},
              gw_addr, metrics, "data")
        print(f"[NODE {device_id}] Sent DATA #{i}")
        time.sleep(send_interval_s)

    metrics.stop("data")
    print(f"[NODE {device_id}] Completed data loop.")

    report = metrics.build_report(device_id=str(device_id))
    print_metric_report(report)


if __name__ == "__main__":
    main()
