#!/usr/bin/env python3
"""
sn_hw.py — Sensor Node (SNn) for Zhou scheme hardware simulation.

Runs on RPi #1.  Mirrors sn-node.c from Zhou-Scheme/:
  "Security-Enhanced Lightweight and Anonymity-Preserving User Authentication
   Scheme for IoT-Based Healthcare", Zhou et al., IEEE IoT Journal 2024

State machine:
  Phase 1 — Sensor Registration (2 rounds with GW_Server)
  Phase 2 — Auth loop: receive M2 from GW_Server, verify, reply M3

Registration exchange:
  Step 1: SN → GW: AES_enc(K_GW_SN, [SNn(1)|pad(15)])           = 16 B  SN_REG_REQ
  Step 2: GW → SN: AES_enc(K_GW_SN, [SIDn(32)|Cn(1)|pad(15)])  = 48 B  SN_REG_REP
  Step 3: SN → GW: AES_enc(K_GW_SN, [Rn(1)|sn_id(1)|pad(14)]) = 16 B  SN_REG1_REQ
  Step 4: GW → SN: empty ack                                             SN_REG1_REP

Authentication exchange (M2→M3):
  Recv M2: {SKn(64)|β(32)|Cn(1)} = 97 B
    1. Rn = PUF(Cn)                              [PUF call]
    2. mask64 = H2(Rn)                           [double-hash]
    3. SK'||SIDn_new' = SKn ⊕ mask64
    4. β' = H(SK'||Rn||SIDn||SIDn_new')          [hash]
    5. Verify β' == β
    6. γ = H(SIDn_new'||SK')                     [hash]
  Send M3: {γ(32)} = 32 B

Hash count: 3 per auth (matches paper Table VI)
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_GW_SN,
    aes_ecb_enc, aes_ecb_dec,
    sha256, H2, xor_bytes,
    simulate_puf_response,
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

    gw_srv_host = cfg.get("GW_HOST",       "127.0.0.1")
    gw_srv_port = int(cfg.get("GW_SERVER_PORT", "5684"))
    sn_port     = int(cfg.get("SN_PORT",    "5685"))
    sn_id       = int(cfg.get("SN_ID",      "4"))
    cpu_power   = float(cfg.get("CPU_POWER_W",          "2.5"))
    net_j       = float(cfg.get("NET_ENERGY_PER_BYTE_J", "0.000002"))

    gw_addr = (gw_srv_host, gw_srv_port)

    metrics = MetricsCollector(
        role="SN",
        cpu_power_w=cpu_power,
        net_energy_per_byte_j=net_j,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", sn_port))

    print(f"[SN {sn_id}] Listening on 0.0.0.0:{sn_port}")
    print(f"[SN {sn_id}] GW_Server at {gw_addr}")

    # =========================================================================
    # PHASE 1 — SENSOR REGISTRATION
    #
    # Step 1: Send SNn to GW (secure channel)
    #   Payload: AES_enc(K_GW_SN, [SNn(1) | pad(15)]) = 16 B
    # Step 2: Recv SIDn + Cn from GW
    #   Payload: AES_enc(K_GW_SN, [SIDn(32) | Cn(1) | pad(15)]) = 48 B
    # Step 3: Compute Rn = PUF(Cn), send back
    #   Payload: AES_enc(K_GW_SN, [Rn(1) | sn_id(1) | pad(14)]) = 16 B
    # Step 4: Recv ack
    # =========================================================================
    metrics.start("enroll")

    # --- Step 1 ---
    p0 = bytearray(16)
    p0[0] = sn_id
    enc_p0 = aes_ecb_enc(K_GW_SN, bytes(p0))
    _send(sock, {"type": "SN_REG_REQ", "enc": enc_p0.hex()}, gw_addr, metrics, "enroll")
    print(f"[SN {sn_id}] Sent SN_REG_REQ")

    # --- Step 2 ---
    rep0    = _recv(sock, "SN_REG_REP", timeout=30.0, metrics=metrics, phase="enroll")
    plain48 = aes_ecb_dec(K_GW_SN, bytes.fromhex(rep0["enc"]))
    SIDn    = bytes(plain48[0:32])
    Cn      = plain48[32]
    print(f"[SN {sn_id}] SN_REG_REP: SIDn={SIDn.hex()[:8]}...  Cn={Cn}")

    # --- Step 3 ---
    Rn = simulate_puf_response(sn_id, Cn)
    p1 = bytearray(16)
    p1[0] = Rn
    p1[1] = sn_id
    enc_p1 = aes_ecb_enc(K_GW_SN, bytes(p1))
    _send(sock, {"type": "SN_REG1_REQ", "enc": enc_p1.hex()}, gw_addr, metrics, "enroll")
    print(f"[SN {sn_id}] Sent PUF response Rn={Rn}")

    # --- Step 4 ---
    _recv(sock, "SN_REG1_REP", timeout=30.0, metrics=metrics, phase="enroll")
    metrics.stop("enroll")
    print(f"[SN {sn_id}] Registration complete!")

    # =========================================================================
    # PHASE 2 — AUTHENTICATION LOOP
    #
    # Receive M2: {SKn(64) | β(32) | Cn(1)} = 97 B
    # Process and reply M3: {γ(32)} = 32 B
    #
    # Steps (mirror sn-node.c res_auth_sn_handler):
    #   1. Rn = PUF(Cn)
    #   2. mask64 = H2(Rn)
    #   3. SK'     = SKn[0:32] ⊕ mask64[0:32]
    #   4. SIDn_new' = SKn[32:64] ⊕ mask64[32:64]
    #   5. β' = H(SK'||Rn||SIDn||SIDn_new')
    #   6. Verify β' == β
    #   7. γ = H(SIDn_new'||SK')
    #   Reply M3: γ
    # =========================================================================
    print(f"[SN {sn_id}] Waiting for M2 from GW_Server...")
    sock.settimeout(None)   # block indefinitely

    while True:
        raw, from_addr = sock.recvfrom(8192)
        try:
            msg = from_json_bytes(raw)
        except Exception:
            continue

        if msg.get("type") != "M2_REQ":
            continue

        metrics.start("auth")
        payload = bytes.fromhex(msg.get("payload", ""))
        if len(payload) < 97:
            print(f"[SN {sn_id}] M2 too short ({len(payload)} B) — ignored")
            metrics.stop("auth")
            continue

        metrics.add_rx("auth", len(raw))

        SKn      = bytes(payload[0:64])
        beta     = bytes(payload[64:96])
        Cn_auth  = payload[96]

        # Step 1: Rn = PUF(Cn)
        Rn_auth = simulate_puf_response(sn_id, Cn_auth)

        # Step 2: mask64 = H2(Rn)
        mask64 = H2(bytes([Rn_auth]))

        # Step 3+4: unmask SKn
        SK_prime      = xor_bytes(SKn[0:32],  mask64[0:32])
        SIDn_new_prime = xor_bytes(SKn[32:64], mask64[32:64])

        # Step 5: β' = H(SK'||Rn||SIDn||SIDn_new')   — 97 B
        beta_in = SK_prime + bytes([Rn_auth]) + SIDn + SIDn_new_prime
        assert len(beta_in) == 97
        beta_prime = sha256(beta_in)

        # Step 6: Verify
        if beta_prime != beta:
            print(f"[SN {sn_id}] M2 verification FAILED — β mismatch")
            metrics.stop("auth")
            continue

        # Accept new state
        SIDn = SIDn_new_prime
        print(f"[SN {sn_id}] M2 verified OK. New SIDn={SIDn.hex()[:8]}...")

        # Step 7: γ = H(SIDn_new'||SK')
        gamma_in = SIDn_new_prime + SK_prime  # 64 B
        gamma    = sha256(gamma_in)

        # Reply M3
        m3_msg = {"type": "M3_REP", "payload": gamma.hex()}
        raw_m3 = to_json_bytes(m3_msg)
        sock.sendto(raw_m3, from_addr)
        metrics.add_tx("auth", len(raw_m3))
        metrics.stop("auth")
        print(f"[SN {sn_id}] Sent M3 (γ)")

        # Print metrics after first auth cycle
        report = metrics.build_report(device_id=str(sn_id))
        print_metric_report(report)
        print(f"[SN {sn_id}] Auth cycle complete. Waiting for next M2...")


if __name__ == "__main__":
    main()
