#!/usr/bin/env python3
"""
gw_hw.py — Registration Authority (RA) for LAAKA hardware simulation.

Runs on the laptop (GW/RA, node ID 1).  Mirrors gw-node.c (LAAKA):

  REG_REQ from device  (32 B, AES-encrypted with K_RA_D):
    AES_enc(K_RA_D, IDd(1)|Ad(20)|pad(11))
    → decrypt, generate TIDd + Bk, reply REG_REP, forward DEV_INFO to Fog

  REG_REP to device  (80 B, AES-encrypted with K_RA_D):
    AES_enc(K_RA_D, TIDd(20)|TIDf_const(20)|Af(20)|Bk(20))

  DEV_INFO to Fog  (64 B, AES-encrypted with K_RA_GW):
    AES_enc(K_RA_GW, IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3))

Emits HW_METRIC JSON after processing each successful REG_REQ
(and on SIGTERM/SIGINT so the orchestrator can safely kill it).
"""
import os
import signal
import socket
import sys
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    K_RA_D, K_RA_GW, K_MASTER,
    R1_FOG, TIDF_CONST, FOG_IDENTITY_ID,
    aes_ecb_enc, aes_ecb_dec,
    sha256_20,
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


def main() -> None:
    cfg = parse_env_file(_cfg_path())

    gw_bind     = cfg.get("GW_BIND",               "0.0.0.0")
    gw_port     = int(cfg.get("GW_PORT",            "5683"))
    fog_host    = cfg.get("AS_HOST",                "127.0.0.1")
    fog_port    = int(cfg.get("AS_PORT",            "5684"))
    cpu_power_w = float(cfg.get("CPU_POWER_W",      "2.5"))
    net_j       = float(cfg.get("NET_ENERGY_PER_BYTE_J", "0.000002"))

    metrics = MetricsCollector(
        role="RA",
        cpu_power_w=cpu_power_w,
        net_energy_per_byte_j=net_j,
    )

    # Emit metrics and exit cleanly on SIGTERM or SIGINT
    def _shutdown(sig, frame):
        print("[RA] Received signal — emitting metrics and exiting")
        report = metrics.build_report(device_id="1")
        print_metric_report(report)
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((gw_bind, gw_port))
    sock.settimeout(None)

    # Precompute Af = H(FOG_IDENTITY_ID || r1_fog)  (mirrors GW init in C)
    Af = sha256_20(bytes([FOG_IDENTITY_ID]) + R1_FOG)

    fog_addr = (fog_host, fog_port)
    print(f"[RA] Listening on {gw_bind}:{gw_port}"
          f"  Fog={fog_addr}"
          f"  Af={Af.hex()[:12]}...", flush=True)

    # Registered clients table: device_id → dict
    clients: Dict[int, Dict] = {}

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
        except Exception as exc:
            print(f"[RA] recv error: {exc}", flush=True)
            continue

        try:
            msg = from_json_bytes(raw)
        except Exception:
            continue

        mtype = msg.get("type", "")

        # =====================================================================
        # REG_REQ from device
        #   Recv: AES_enc(K_RA_D, IDd(1)|Ad(20)|pad(11)) = 32 B
        #   Send to device: AES_enc(K_RA_D, TIDd(20)|TIDf(20)|Af(20)|Bk(20)) = 80 B
        #   Send to Fog:    AES_enc(K_RA_GW, IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3)) = 64 B
        # =====================================================================
        if mtype == "REG_REQ":
            metrics.start("register")
            metrics.add_rx("register", len(raw))

            enc_in = bytes.fromhex(msg.get("enc", ""))
            if len(enc_in) != 32:
                print(f"[RA] REG_REQ wrong length {len(enc_in)} B (expected 32)", flush=True)
                metrics.stop("register")
                continue

            plain = aes_ecb_dec(K_RA_D, enc_in)
            id_d  = plain[0]
            Ad    = bytes(plain[1:21])

            if id_d == 0:
                metrics.stop("register")
                continue

            # TIDd = H(random_seed(20) || IDd(1) || K_MASTER(20))
            random_seed = os.urandom(20)
            TIDd = sha256_20(random_seed + bytes([id_d]) + K_MASTER)

            # Bk = H(Ad || Af || K_MASTER)
            Bk = sha256_20(Ad + Af + K_MASTER)

            clients[id_d] = {"id_d": id_d, "TIDd": TIDd, "Ad": Ad, "Bk": Bk}

            # REG_REP: TIDd(20)|TIDf_const(20)|Af(20)|Bk(20) = 80 B
            rep_plain = TIDd + TIDF_CONST + Af + Bk
            assert len(rep_plain) == 80
            enc_rep   = aes_ecb_enc(K_RA_D, rep_plain)
            rep_raw   = to_json_bytes({"type": "REG_REP", "enc": enc_rep.hex()})
            sock.sendto(rep_raw, addr)
            metrics.add_tx("register", len(rep_raw))
            print(f"[RA] REG_REP sent to device {id_d}  TIDd={TIDd.hex()[:12]}...",
                  flush=True)

            # DEV_INFO: IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3) = 64 B
            dev_info_plain = bytearray(64)
            dev_info_plain[0]     = id_d
            dev_info_plain[1:21]  = TIDd
            dev_info_plain[21:41] = Ad
            dev_info_plain[41:61] = Bk
            enc_info    = aes_ecb_enc(K_RA_GW, bytes(dev_info_plain))
            info_raw    = to_json_bytes({"type": "DEV_INFO", "enc": enc_info.hex()})
            sock.sendto(info_raw, fog_addr)
            metrics.add_tx("register", len(info_raw))

            metrics.stop("register")
            print(f"[RA] DEV_INFO forwarded for device {id_d} to Fog {fog_addr}",
                  flush=True)

            # RA's job is done after registration — emit metrics immediately
            report = metrics.build_report(device_id=str(id_d))
            print_metric_report(report)
            sys.stdout.flush()

        else:
            print(f"[RA] Unknown message type '{mtype}' from {addr}", flush=True)


if __name__ == "__main__":
    main()
