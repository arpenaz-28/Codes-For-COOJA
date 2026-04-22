#!/usr/bin/env python3
"""
as_hw.py — Fog Authentication Server for LAAKA hardware simulation.

Runs on RPi #1 (Fog, node ID 2).  Mirrors as-node.c (LAAKA):

  DEV_INFO from RA  (64 B, AES-encrypted with K_RA_GW):
    AES_enc(K_RA_GW, IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3))
    → store device credentials

  AUTH_REQ from device  (81 B, unencrypted):
    TIDd(20)|Td(1)|Cd(20)|Ed(20)|Gd(20)
    → recover rd, verify Cd + Gd, generate rf + SK, reply AUTH_REP

  ACK from device  (40 B, unencrypted):
    TIDd_new(20)|Ack_val(20)
    → verify H(rf||Bk||SK), mark device as authenticated

  DATA from device  (36 B):
    TIDd_new(20)|AES_enc(SK[0:16],sensor(16))
    → decrypt and log sensor data

Emits HW_METRIC JSON after processing send_count DATA packets
(and also on SIGTERM/SIGINT so the orchestrator can safely kill it).
"""
import os
import signal
import socket
import sys
import time
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_RA_GW,
    R1_FOG, TIDF_CONST, FOG_IDENTITY_ID,
    aes_ecb_enc, aes_ecb_dec,
    sha256_20, xor_bytes,
    to_json_bytes, from_json_bytes,
    parse_env_file,
    MetricsCollector, print_metric_report,
)

from Crypto.Cipher import AES as _AES


def _cfg_path() -> str:
    override = os.environ.get("LAAKA_ROLES_FILE")
    if override:
        return override
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "roles.env")


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    as_bind     = cfg.get("AS_BIND",               "0.0.0.0")
    as_port     = int(cfg.get("AS_PORT",            "5684"))
    fog_id      = int(cfg.get("AS_NODE_ID",         "2"))
    send_count  = int(cfg.get("NODE_SEND_COUNT",    "10"))
    cpu_power_w = float(cfg.get("CPU_POWER_W",      "2.5"))
    net_j       = float(cfg.get("NET_ENERGY_PER_BYTE_J", "0.000002"))

    metrics = MetricsCollector(
        role="FOG",
        cpu_power_w=cpu_power_w,
        net_energy_per_byte_j=net_j,
    )

    # Emit metrics and exit cleanly on SIGTERM or SIGINT (Ctrl-C)
    def _shutdown(sig, frame):
        print(f"[FOG {fog_id}] Received signal {sig} — emitting metrics and exiting")
        report = metrics.build_report(device_id=str(fog_id))
        print_metric_report(report)
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((as_bind, as_port))
    sock.settimeout(None)

    # Precompute Af = H(FOG_IDENTITY_ID || r1_fog)  (mirrors fog init in C)
    Af = sha256_20(bytes([FOG_IDENTITY_ID]) + R1_FOG)
    print(f"[FOG {fog_id}] Listening on {as_bind}:{as_port}  Af={Af.hex()[:12]}...",
          flush=True)

    # Per-device credentials  { device_id (int) → dict }
    devices: Dict[int, Dict] = {}

    # Active sessions keyed by TIDd_new  { bytes → dict }
    sessions: Dict[bytes, Dict] = {}

    data_count: int = 0       # total DATA packets processed (single-device test)
    _metrics_emitted = False  # only emit once via the count path

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
        except Exception as exc:
            print(f"[FOG {fog_id}] recv error: {exc}", flush=True)
            continue

        try:
            msg = from_json_bytes(raw)
        except Exception:
            continue

        mtype = msg.get("type", "")

        # =====================================================================
        # DEV_INFO from RA
        #   Recv: AES_enc(K_RA_GW, IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3)) = 64 B
        # =====================================================================
        if mtype == "DEV_INFO":
            metrics.start("register")
            metrics.add_rx("register", len(raw))

            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 64:
                print(f"[FOG {fog_id}] DEV_INFO wrong length {len(enc_in)} B (expected 64)",
                      flush=True)
                metrics.stop("register")
                continue

            plain = aes_ecb_dec(K_RA_GW, enc_in)
            id_d  = plain[0]
            TIDd  = bytes(plain[1:21])
            Ad    = bytes(plain[21:41])
            Bk    = bytes(plain[41:61])

            if id_d == 0:
                metrics.stop("register")
                continue

            devices[id_d] = {
                "id_d":          id_d,
                "TIDd":          TIDd,
                "Ad":            Ad,
                "Bk":            Bk,
                "authenticated": False,
            }
            metrics.stop("register")
            print(f"[FOG {fog_id}] Stored credentials for device {id_d}"
                  f"  TIDd={TIDd.hex()[:12]}...", flush=True)

        # =====================================================================
        # AUTH_REQ from device
        #   Recv: TIDd(20)|Td(1)|Cd(20)|Ed(20)|Gd(20) = 81 B
        #   Send: TIDf(20)|Tf(1)|Ts(1)|Cf(20)|Ef(20)|Gf(20) = 82 B
        # =====================================================================
        elif mtype == "AUTH_REQ":
            metrics.start("auth")
            metrics.add_rx("auth", len(raw))

            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 81:
                print(f"[FOG {fog_id}] AUTH_REQ too short: {len(payload)} B", flush=True)
                metrics.stop("auth")
                continue

            recv_TIDd = bytes(payload[0:20])
            Td        = payload[20]
            Cd        = bytes(payload[21:41])
            Ed        = bytes(payload[41:61])
            Gd        = bytes(payload[61:81])

            found: Optional[int] = None
            for did, dev in devices.items():
                if dev["TIDd"] == recv_TIDd:
                    found = did
                    break

            if found is None:
                print(f"[FOG {fog_id}] AUTH_REQ — device not found by TIDd", flush=True)
                metrics.stop("auth")
                continue

            dev = devices[found]
            Bk  = dev["Bk"]
            Ad  = dev["Ad"]

            now  = int(time.time()) & 0xFF
            diff = (now - Td + 256) % 256
            if diff > 120:
                print(f"[FOG {fog_id}] Stale Td={Td} from device {found}", flush=True)
                metrics.stop("auth")
                continue

            # Recover rd = Ed XOR H(Bk || Af)
            rd_star  = xor_bytes(Ed, sha256_20(Bk + Af))
            TIDd_new = xor_bytes(recv_TIDd, rd_star)

            # Verify Cd = H(Td || rd)
            if sha256_20(bytes([Td]) + rd_star) != Cd:
                print(f"[FOG {fog_id}] Cd verification FAILED for device {found}", flush=True)
                metrics.stop("auth")
                continue

            # Verify Gd = H(Ad || TIDd_new || Bk || rd)
            if sha256_20(Ad + TIDd_new + Bk + rd_star) != Gd:
                print(f"[FOG {fog_id}] Gd verification FAILED for device {found}", flush=True)
                metrics.stop("auth")
                continue

            print(f"[FOG {fog_id}] Device {found} auth passed — generating session key",
                  flush=True)

            rf = os.urandom(20)
            Tf = int(time.time()) & 0xFF
            Ts = (Tf + 1) & 0xFF

            SK       = sha256_20(rd_star + rf + bytes([Ts]))
            TIDf_new = xor_bytes(TIDF_CONST, rf)
            Cf       = sha256_20(bytes([Tf]) + rf)
            Ef       = xor_bytes(rf, sha256_20(TIDd_new))
            Gf       = sha256_20(TIDf_new + Bk + rf + SK + bytes([Ts]))

            sessions[TIDd_new] = {
                "id_d": found,
                "rf":   rf,
                "SK":   SK,
                "Bk":   Bk,
            }

            rep_payload = TIDF_CONST + bytes([Tf, Ts]) + Cf + Ef + Gf
            assert len(rep_payload) == 82
            reply_raw = to_json_bytes({"type": "AUTH_REP",
                                       "payload": rep_payload.hex()})
            sock.sendto(reply_raw, addr)
            metrics.add_tx("auth", len(reply_raw))
            metrics.stop("auth")
            print(f"[FOG {fog_id}] Sent AUTH_REP to device {found}"
                  f"  SK={SK.hex()[:12]}...", flush=True)

        # =====================================================================
        # ACK from device
        #   Recv: TIDd_new(20)|Ack_val(20) = 40 B
        # =====================================================================
        elif mtype == "ACK":
            metrics.start("ack")
            metrics.add_rx("ack", len(raw))

            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 40:
                print(f"[FOG {fog_id}] ACK too short: {len(payload)} B", flush=True)
                metrics.stop("ack")
                continue

            recv_TIDd_new = bytes(payload[0:20])
            recv_ack_val  = bytes(payload[20:40])

            sess: Optional[Dict] = sessions.get(recv_TIDd_new)
            if sess is None:
                print(f"[FOG {fog_id}] ACK — session not found for TIDd_new", flush=True)
                metrics.stop("ack")
                continue

            expected_ack = sha256_20(sess["rf"] + sess["Bk"] + sess["SK"])
            if recv_ack_val != expected_ack:
                print(f"[FOG {fog_id}] ACK verification FAILED for device {sess['id_d']}",
                      flush=True)
                metrics.stop("ack")
                continue

            dev_id = sess["id_d"]
            if dev_id in devices:
                devices[dev_id]["authenticated"] = True
            metrics.stop("ack")
            print(f"[FOG {fog_id}] Device {dev_id} ACK verified — session ACTIVE", flush=True)

        # =====================================================================
        # DATA from device
        #   Recv: TIDd_new(20)|AES_enc(SK[0:16],sensor(16)) = 36 B
        # =====================================================================
        elif mtype == "DATA":
            if data_count == 0:
                metrics.start("data")
            metrics.add_rx("data", len(raw))

            payload = bytes.fromhex(msg.get("payload", ""))
            if len(payload) < 36:
                print(f"[FOG {fog_id}] DATA too short: {len(payload)} B", flush=True)
                continue

            recv_TIDd_new = bytes(payload[0:20])
            enc_data      = bytes(payload[20:36])

            sess = sessions.get(recv_TIDd_new)
            if sess is None:
                print(f"[FOG {fog_id}] DATA — session not found", flush=True)
                continue

            dev_id = sess["id_d"]
            if not devices.get(dev_id, {}).get("authenticated", False):
                print(f"[FOG {fog_id}] DATA from unauthenticated device {dev_id} — dropped",
                      flush=True)
                continue

            K_AES      = sess["SK"][:16]
            plain_data = _AES.new(K_AES, _AES.MODE_ECB).decrypt(enc_data)

            data_count += 1
            print(f"[FOG {fog_id}] DATA #{data_count}/{send_count}"
                  f"  device={dev_id}"
                  f"  id_field={plain_data[0]}"
                  f"  ts_field={plain_data[1]}"
                  f"  TIDd_new={recv_TIDd_new.hex()[:12]}...", flush=True)

            # After receiving all expected packets emit the metric report
            if data_count >= send_count and not _metrics_emitted:
                metrics.stop("data")
                _metrics_emitted = True
                report = metrics.build_report(device_id=str(fog_id))
                print_metric_report(report)
                sys.stdout.flush()

        else:
            print(f"[FOG {fog_id}] Unknown message type '{mtype}' from {addr}", flush=True)


if __name__ == "__main__":
    main()
