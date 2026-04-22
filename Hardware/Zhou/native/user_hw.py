#!/usr/bin/env python3
"""
user_hw.py — User/Doctor Device for Zhou scheme hardware simulation.

Runs on RPi #2.  Mirrors user-node.c from Zhou-Scheme/:
  "Security-Enhanced Lightweight and Anonymity-Preserving User Authentication
   Scheme for IoT-Based Healthcare", Zhou et al., IEEE IoT Journal 2024

State machine:
  Phase 1 (enroll) — User Registration + SIDn binding
  Phase 2 (auth)   — Send M1, recv M1_ACK
  Phase 3 (keyex)  — Recv M4 (pushed by GW_Server), verify, derive SK
  Phase 4 (data)   — Send encrypted sensor data to GW_Router

User Registration (paper Section IV.A):
  Step 1: User → GW: AES_enc(K_GW_U, [IDi(1)|ki(32)|pad(15)]) = 48 B  USER_REG_REQ
  Step 2: GW → User: AES_enc(K_GW_U, [DIDi(32)|pad(16)])       = 48 B  USER_REG_REP
  Step 3: User → GW: AES_enc(K_GW_U, [sn_id(1)|pad(15)])       = 16 B  GET_SID_REQ
  Step 4: GW → User: AES_enc(K_GW_U, [SIDn(32)|pad(16)])       = 48 B  GET_SID_REP

Authentication M1 (paper Section IV.C):
  User → GW: {Ni(32)|α(32)|DIDi(32)|SIDn(32)} = 128 B  M1_REQ
  GW → User: ACK(1)                                      M1_ACK
  GW → User: {SKi(96)|λ(32)} = 128 B   (pushed async)   M4_PUSH

Data:
  User → GW_Router: {DIDi(32)|AES_enc(SK[0:16], sensor(16))} = 48 B  DATA

Hash count: 4 per auth (matches paper Table VI)
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_GW_U,
    aes_ecb_enc, aes_ecb_dec,
    sha256, H3, xor_bytes,
    to_json_bytes, from_json_bytes,
    parse_env_file,
    MetricsCollector, print_metric_report,
)


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


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    gw_srv_host  = cfg.get("GW_HOST",        "127.0.0.1")
    gw_srv_port  = int(cfg.get("GW_SERVER_PORT",  "5684"))
    gw_rtr_host  = cfg.get("GW_HOST",        "127.0.0.1")
    gw_rtr_port  = int(cfg.get("GW_ROUTER_PORT",  "5683"))
    user_port    = int(cfg.get("USER_PORT",   "5686"))
    user_id      = int(cfg.get("USER_ID",     "81"))
    sn_id        = int(cfg.get("SN_ID",       "4"))
    send_count   = int(cfg.get("USER_SEND_COUNT",    "10"))
    send_interval = float(cfg.get("USER_SEND_INTERVAL_S", "3"))
    cpu_power    = float(cfg.get("CPU_POWER_W",           "2.5"))
    net_j        = float(cfg.get("NET_ENERGY_PER_BYTE_J",  "0.000002"))

    gw_srv_addr = (gw_srv_host, gw_srv_port)
    gw_rtr_addr = (gw_rtr_host, gw_rtr_port)

    metrics = MetricsCollector(
        role="USER",
        cpu_power_w=cpu_power,
        net_energy_per_byte_j=net_j,
    )

    # Bind to USER_PORT so GW_Server can push M4 to this port
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", user_port))

    print(f"[User {user_id}] Listening on 0.0.0.0:{user_port}")
    print(f"[User {user_id}] GW_Server={gw_srv_addr}  GW_Router={gw_rtr_addr}")

    # Wait for SN to complete registration before starting.
    # USER_START_DELAY_S (default 30) gives time for SN to enroll.
    start_delay = float(cfg.get("USER_START_DELAY_S", "30"))
    print(f"[User {user_id}] Waiting {start_delay:.0f} s for SN to register first...")
    time.sleep(start_delay)

    # =========================================================================
    # PHASE 1 — ENROLLMENT (User Reg + SIDn binding)
    #
    # Mirrors user-node.c PROCESS_THREAD when reg == 0.
    #
    # 1. Generate ki(32) via fuzzy extractor simulation (os.urandom)
    # 2. Generate secret salt ri (8-bit)
    # 3. CPWi = H(ki||IDi||ri)
    # 4. Send {IDi, ki} to GW:  AES_enc(K_GW_U, [IDi(1)|ki(32)|pad(15)]) = 48 B
    # 5. Recv DIDi from GW:     AES_enc(K_GW_U, [DIDi(32)|pad(16)]) = 48 B
    # 6. Query SIDn for bound sensor: AES_enc(K_GW_U, [sn_id(1)|pad(15)]) = 16 B
    # 7. Recv SIDn: AES_enc(K_GW_U, [SIDn(32)|pad(16)]) = 48 B
    # =========================================================================
    metrics.start("enroll")

    # Simulate fuzzy extractor: ki = Gen(BIOi)
    ki   = os.urandom(32)
    ri   = os.urandom(1)[0]      # 8-bit secret salt

    # CPWi = H(ki || IDi || ri)
    CPWi = sha256(ki + bytes([user_id, ri]))

    # --- User Registration ---
    p0 = bytearray(48)
    p0[0] = user_id
    p0[1:33] = ki
    enc_p0 = aes_ecb_enc(K_GW_U, bytes(p0))
    _send(sock, {"type": "USER_REG_REQ", "enc": enc_p0.hex()}, gw_srv_addr, metrics, "enroll")
    print(f"[User {user_id}] Sent USER_REG_REQ")

    rep0    = _recv(sock, "USER_REG_REP", timeout=30.0, metrics=metrics, phase="enroll")
    plain48 = aes_ecb_dec(K_GW_U, bytes.fromhex(rep0["enc"]))
    DIDi    = bytes(plain48[0:32])
    print(f"[User {user_id}] Registered. DIDi={DIDi.hex()[:8]}...")

    # --- Bind sensor: query GW for SIDn ---
    # Retry until sensor is enrolled (GW returns err if not ready)
    SIDn: bytes = b''
    for attempt in range(10):
        gs = bytearray(16)
        gs[0] = sn_id
        enc_gs = aes_ecb_enc(K_GW_U, bytes(gs))
        _send(sock, {"type": "GET_SID_REQ", "enc": enc_gs.hex()}, gw_srv_addr, metrics, "enroll")

        sock.settimeout(5.0)
        try:
            while True:
                raw, _ = sock.recvfrom(8192)
                metrics.add_rx("enroll", len(raw))
                rsp = from_json_bytes(raw)
                if rsp.get("type") == "GET_SID_REP":
                    break
        except socket.timeout:
            print(f"[User {user_id}] get_sid timeout (attempt {attempt+1}), retrying...")
            time.sleep(3)
            continue

        if "err" in rsp:
            print(f"[User {user_id}] SN {sn_id} not enrolled yet, retrying in 3s...")
            time.sleep(3)
            continue

        plain_sid = aes_ecb_dec(K_GW_U, bytes.fromhex(rsp["enc"]))
        SIDn = bytes(plain_sid[0:32])
        print(f"[User {user_id}] Got SIDn={SIDn.hex()[:8]}... for SN {sn_id}")
        break

    if not SIDn:
        print(f"[User {user_id}] Could not get SIDn — SN may not be enrolled. Exiting.")
        sys.exit(1)

    metrics.stop("enroll")
    print(f"[User {user_id}] Enrollment complete.")

    # =========================================================================
    # PHASE 2 — AUTHENTICATION  (send M1, receive M1_ACK)
    #
    # Mirrors user-node.c PROCESS_THREAD when reg == 1.
    #
    # 1. Verify CPWi  (H(ki||IDi||ri) == CPWi)
    # 2. Generate bi_new(32)
    # 3. Ni = bi_new ⊕ H(ki)                       [hash 1]
    # 4. α = H(bi_new||ki||DIDi||SIDn)              [hash 2]
    # 5. Send M1: {Ni(32)|α(32)|DIDi(32)|SIDn(32)} = 128 B
    # 6. Recv M1_ACK: {ack=0xAC}
    # =========================================================================
    metrics.start("auth")

    # Step 1: Verify CPWi
    cpw_check = sha256(ki + bytes([user_id, ri]))
    assert cpw_check == CPWi, "CPWi mismatch — should not happen"

    # Step 2: Generate bi_new
    bi_new = os.urandom(32)

    # Step 3: Ni = bi_new ⊕ H(ki)
    h_ki = sha256(ki)            # hash 1
    Ni   = xor_bytes(bi_new, h_ki)

    # Step 4: α = H(bi_new||ki||DIDi||SIDn)
    alpha_in = bi_new + ki + DIDi + SIDn   # 128 B
    alpha    = sha256(alpha_in)             # hash 2

    # Step 5: Send M1
    m1 = Ni + alpha + DIDi + SIDn  # 128 B
    assert len(m1) == 128
    _send(sock, {"type": "M1_REQ", "payload": m1.hex()}, gw_srv_addr, metrics, "auth")
    print(f"[User {user_id}] Sent M1  DIDi={DIDi.hex()[:8]}...")

    # Step 6: Recv ACK
    ack_msg = _recv(sock, "M1_ACK", timeout=15.0, metrics=metrics, phase="auth")
    if ack_msg.get("ack") != "ac":
        print(f"[User {user_id}] Bad M1_ACK — aborting")
        sys.exit(1)
    metrics.stop("auth")
    print(f"[User {user_id}] M1_ACK received")

    # =========================================================================
    # PHASE 3 — KEY EXCHANGE  (receive M4 pushed by GW_Server, verify)
    #
    # Recv M4: {SKi(96)|λ(32)} = 128 B  (GW_Server pushes to USER_PORT)
    #
    # 8. (SIDn_new'||SK'||DIDi_new') = SKi ⊕ H3(ki)   [hash 3]
    # 9. λ' = H(SK'||DIDi||ki||DIDi_new'||SIDn_new')    [hash 4]
    # 10. Verify λ' == λ
    # 11. Accept SK', update DIDi and SIDn
    # =========================================================================
    metrics.start("keyex")
    print(f"[User {user_id}] Waiting for M4 from GW_Server...")

    m4_msg = _recv(sock, "M4_PUSH", timeout=60.0, metrics=metrics, phase="keyex")
    m4_payload = bytes.fromhex(m4_msg.get("payload", ""))
    if len(m4_payload) < 128:
        print(f"[User {user_id}] M4 too short ({len(m4_payload)} B) — aborting")
        sys.exit(1)

    SKi    = bytes(m4_payload[0:96])
    lam    = bytes(m4_payload[96:128])

    # Step 8: unmask SKi with H3(ki)
    mask96       = H3(ki)        # hash 3
    SIDn_new_p   = xor_bytes(SKi[0:32],  mask96[0:32])
    SK_prime     = xor_bytes(SKi[32:64], mask96[32:64])
    DIDi_new_p   = xor_bytes(SKi[64:96], mask96[64:96])

    # Step 9: λ' = H(SK'||DIDi||ki||DIDi_new'||SIDn_new')  — 160 B
    lambda_in = SK_prime + DIDi + ki + DIDi_new_p + SIDn_new_p
    assert len(lambda_in) == 160
    lam_prime = sha256(lambda_in)     # hash 4

    # Step 10: Verify
    if lam_prime != lam:
        print(f"[User {user_id}] M4 verification FAILED — λ mismatch")
        sys.exit(1)

    # Step 11: Accept
    SK   = SK_prime
    DIDi = DIDi_new_p
    SIDn = SIDn_new_p
    metrics.stop("keyex")
    print(f"[User {user_id}] M4 verified OK. "
          f"New DIDi={DIDi.hex()[:8]}...  SK={SK.hex()[:8]}...")

    # =========================================================================
    # PHASE 4 — DATA LOOP
    #
    # Send to GW_Router: {DIDi(32) | AES_enc(SK[0:16], sensor(16))} = 48 B
    # sensor[0] = 9 (constant, mirrors user-node.c)
    # =========================================================================
    metrics.start("data")
    K_AES = SK[:16]   # AES-128 key = first 16 bytes of SK

    for i in range(1, send_count + 1):
        sensor    = bytearray(16)
        sensor[0] = 9
        enc_sensor = aes_ecb_enc(K_AES, bytes(sensor))

        data_payload = DIDi + enc_sensor  # 48 B
        assert len(data_payload) == 48
        _send(sock, {"type": "DATA", "payload": data_payload.hex()},
              gw_rtr_addr, metrics, "data")
        print(f"[User {user_id}] Sent DATA #{i}")
        time.sleep(send_interval)

    metrics.stop("data")
    print(f"[User {user_id}] Data loop complete.")

    report = metrics.build_report(device_id=str(user_id))
    print_metric_report(report)


if __name__ == "__main__":
    main()
