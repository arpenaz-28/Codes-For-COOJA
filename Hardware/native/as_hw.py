#!/usr/bin/env python3
import os
import random
import secrets
import socket
from typing import Dict, Tuple

from common import now_ts, parse_env_file, sha256_hex, to_json_bytes, from_json_bytes, xor_hex


def role_paths() -> Tuple[str, str]:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = os.path.join(base, "config", "roles.env")
    return base, cfg


def main() -> None:
    _, cfg_path = role_paths()
    cfg = parse_env_file(cfg_path)

    as_host = cfg.get("AS_BIND", "0.0.0.0")
    as_port = int(cfg.get("AS_PORT", "5684"))
    gw_host = cfg.get("GW_HOST", "127.0.0.1")
    gw_port = int(cfg.get("GW_PORT", "5683"))
    freshness_window = int(cfg.get("FRESHNESS_WINDOW_S", "120"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((as_host, as_port))

    print(f"[AS] Listening on {as_host}:{as_port}")

    # Per-device state.
    state: Dict[str, Dict[str, str]] = {}

    while True:
        raw, addr = sock.recvfrom(8192)
        msg = from_json_bytes(raw)
        mtype = msg.get("type", "")

        if mtype == "ENROLL_REQ":
            device_id = str(msg.get("device_id", ""))
            y_hash = msg.get("y_hash", "")
            crps = msg.get("crps", [])
            if not device_id or not y_hash or not isinstance(crps, list) or not crps:
                continue

            crp_map: Dict[str, Dict[str, int | str | bool]] = {}
            for item in crps:
                cid = str(item.get("cid", ""))
                challenge = item.get("challenge", "")
                response = int(item.get("response", 0))
                if not cid or not challenge or response not in (-1, 1):
                    continue
                crp_map[cid] = {
                    "challenge": challenge,
                    "response": response,
                    "used": False,
                }
            if not crp_map:
                continue

            m_curr = secrets.token_hex(16)
            pid_curr = sha256_hex(f"{device_id}|{m_curr}")

            state[device_id] = {
                "y_hash": y_hash,
                "m_curr": m_curr,
                "m_old": m_curr,
                "pid_curr": pid_curr,
                "pid_old": pid_curr,
                "crps": crp_map,
            }

            reply = {
                "type": "ENROLL_OK",
                "device_id": device_id,
                "pid": pid_curr,
                "ts": now_ts(),
            }
            sock.sendto(to_json_bytes(reply), addr)
            print(f"[AS] Enrollment ok for device {device_id}")

        elif mtype == "AUTH_REQ":
            device_id = str(msg.get("device_id", ""))
            pid = msg.get("pid", "")
            ts = int(msg.get("ts", 0))

            d = state.get(device_id)
            if d is None:
                continue

            if abs(now_ts() - ts) > freshness_window:
                fail = {"type": "AUTH_FAIL", "reason": "stale_ts"}
                sock.sendto(to_json_bytes(fail), addr)
                continue

            pid_ok = pid in (d["pid_curr"], d["pid_old"])
            if not pid_ok:
                fail = {"type": "AUTH_FAIL", "reason": "pid"}
                sock.sendto(to_json_bytes(fail), addr)
                continue

            crp_pool = [cid for cid, v in d["crps"].items() if not v["used"]]
            if not crp_pool:
                fail = {"type": "AUTH_FAIL", "reason": "crp_exhausted"}
                sock.sendto(to_json_bytes(fail), addr)
                continue

            cid = random.choice(crp_pool)
            ch = d["crps"][cid]["challenge"]
            ch_msg = {
                "type": "AUTH_CHALLENGE",
                "device_id": device_id,
                "pid": pid,
                "cid": cid,
                "challenge": ch,
                "ts": now_ts(),
            }
            sock.sendto(to_json_bytes(ch_msg), addr)

        elif mtype == "AUTH_PROOF":
            device_id = str(msg.get("device_id", ""))
            pid = msg.get("pid", "")
            cid = str(msg.get("cid", ""))
            response = int(msg.get("response", 0))
            ts = int(msg.get("ts", 0))

            d = state.get(device_id)
            if d is None:
                continue
            if abs(now_ts() - ts) > freshness_window:
                fail = {"type": "AUTH_FAIL", "reason": "stale_ts"}
                sock.sendto(to_json_bytes(fail), addr)
                continue
            if pid not in (d["pid_curr"], d["pid_old"]):
                fail = {"type": "AUTH_FAIL", "reason": "pid"}
                sock.sendto(to_json_bytes(fail), addr)
                continue

            crp = d["crps"].get(cid)
            if crp is None or crp["used"]:
                fail = {"type": "AUTH_FAIL", "reason": "cid"}
                sock.sendto(to_json_bytes(fail), addr)
                continue
            if response != int(crp["response"]):
                fail = {"type": "AUTH_FAIL", "reason": "puf_response"}
                sock.sendto(to_json_bytes(fail), addr)
                continue

            crp["used"] = True

            m_new = secrets.token_hex(16)
            pid_new = sha256_hex(f"{device_id}|{m_new}")
            mask_key = sha256_hex(f"{d['y_hash']}|mask")
            m_masked = xor_hex(m_new, mask_key[:32])
            session_key = sha256_hex(f"{d['y_hash']}|{response}|{m_new}")

            d["m_old"] = d["m_curr"]
            d["pid_old"] = d["pid_curr"]
            d["m_curr"] = m_new
            d["pid_curr"] = pid_new

            auth_ok = {
                "type": "AUTH_OK",
                "device_id": device_id,
                "pid_new": pid_new,
                "m_masked": m_masked,
                "ts": now_ts(),
            }
            sock.sendto(to_json_bytes(auth_ok), addr)

            gw_ts = now_ts()
            token = sha256_hex(f"{session_key}|gw-token|{gw_ts}")
            gw_msg = {
                "type": "GW_TOKEN",
                "device_id": device_id,
                "pid": pid_new,
                "session_key": session_key,
                "token": token,
                "ts": gw_ts,
            }
            sock.sendto(to_json_bytes(gw_msg), (gw_host, gw_port))
            print(f"[AS] Auth ok for device {device_id}; token forwarded to GW")

        else:
            # Ignore unknown message types.
            pass


if __name__ == "__main__":
    main()
