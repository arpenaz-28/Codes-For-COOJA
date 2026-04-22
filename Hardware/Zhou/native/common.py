#!/usr/bin/env python3
"""
common.py — Shared crypto helpers for Zhou scheme hardware simulation.

Mirrors the exact primitives from Zhou-Scheme/gw-server.c, sn-node.c, user-node.c:
  "Security-Enhanced Lightweight and Anonymity-Preserving User Authentication
   Scheme for IoT-Based Healthcare", Zhou et al., IEEE IoT Journal, Vol. 11, No. 6, 2024

Primitives:
  - AES-128-ECB  (pycryptodome)
  - SHA-256      (hashlib)
  - H2(x): H(x||0x00) || H(x||0x01)  → 64-byte mask   (sn-node.c: H2)
  - H3(x): H(x||0x00) || H(x||0x01) || H(x||0x02) → 96-byte mask (user-node.c: H3)
  - PUF: Rn = SHA256(node_id || challenge)[0]           (sn-node.c: simulate_puf_response)
  - XOR byte-arrays
  - MetricsCollector (wall time, CPU time, TX/RX bytes, estimated energy)
"""
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple

from Crypto.Cipher import AES as _AES

# =============================================================================
# Long-term symmetric keys  (MUST match C source exactly)
# =============================================================================

# K_GW_U — shared between GW and User:  "gwus myKuog Fu\x00"
K_GW_U: bytes = bytes([
    0x67, 0x77, 0x75, 0x73, 0x20, 0x6D, 0x79, 0x20,
    0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75, 0x00,
])

# K_GW_SN — shared between GW and Sensor: "sngw key_secure\x00"
K_GW_SN: bytes = bytes([
    0x73, 0x6E, 0x67, 0x77, 0x20, 0x6B, 0x65, 0x79,
    0x5F, 0x73, 0x65, 0x63, 0x75, 0x72, 0x65, 0x00,
])

# K_GW_RT — shared between GW Server and GW Router: "gbts myKuog Fu\x00"
K_GW_RT: bytes = bytes([
    0x67, 0x62, 0x74, 0x73, 0x20, 0x6D, 0x79, 0x20,
    0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75, 0x00,
])

# =============================================================================
# AES-128-ECB helpers
# =============================================================================

def aes_ecb_enc(key: bytes, data: bytes) -> bytes:
    assert len(data) % 16 == 0
    return _AES.new(key, _AES.MODE_ECB).encrypt(data)


def aes_ecb_dec(key: bytes, data: bytes) -> bytes:
    assert len(data) % 16 == 0
    return _AES.new(key, _AES.MODE_ECB).decrypt(data)


# =============================================================================
# SHA-256 and hash variants
# =============================================================================

def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def H2(data: bytes) -> bytes:
    """64-byte mask: H(data||0x00) || H(data||0x01). Mirrors sn-node.c: H2()"""
    return sha256(data + b'\x00') + sha256(data + b'\x01')


def H3(data: bytes) -> bytes:
    """96-byte mask: H(data||0x00) || H(data||0x01) || H(data||0x02). Mirrors user-node.c: H3()"""
    return sha256(data + b'\x00') + sha256(data + b'\x01') + sha256(data + b'\x02')


# =============================================================================
# XOR
# =============================================================================

def xor_bytes(a: bytes, b: bytes) -> bytes:
    assert len(a) == len(b), f"xor_bytes length mismatch: {len(a)} vs {len(b)}"
    return bytes(x ^ y for x, y in zip(a, b))


# =============================================================================
# PUF simulation
#
# Mirrors sn-node.c simulate_puf_response():
#   in[0] = (uint8_t)node_id;  in[1] = c;
#   SHA256(in, 2, out);  return out[0];
#
# Key difference from Revised-Anonymity: the full SHA256 is taken, then
# the first byte is returned as the 8-bit PUF response (not a 1-bit response).
# =============================================================================

def simulate_puf_response(node_id: int, challenge: int) -> int:
    """Returns 8-bit PUF response: SHA256(node_id_byte || challenge_byte)[0]"""
    return sha256(bytes([node_id & 0xFF, challenge & 0xFF]))[0]


# =============================================================================
# JSON transport
# =============================================================================

def to_json_bytes(obj: Dict) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def from_json_bytes(raw: bytes) -> Dict:
    return json.loads(raw.decode("utf-8"))


# =============================================================================
# Config file parser
# =============================================================================

def parse_env_file(path: str) -> Dict[str, str]:
    cfg: Dict[str, str] = {}
    if not os.path.exists(path):
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


# =============================================================================
# Metrics collector
# =============================================================================

@dataclass
class PhaseMetric:
    wall_s:    float = 0.0
    cpu_s:     float = 0.0
    tx_bytes:  int   = 0
    rx_bytes:  int   = 0
    _wall_start: float = 0.0
    _cpu_start:  float = 0.0
    _active:     bool  = False


@dataclass
class MetricsCollector:
    role:                  str
    cpu_power_w:           float
    net_energy_per_byte_j: float
    phases: Dict[str, PhaseMetric] = field(default_factory=dict)

    def _get(self, name: str) -> PhaseMetric:
        if name not in self.phases:
            self.phases[name] = PhaseMetric()
        return self.phases[name]

    def start(self, name: str) -> None:
        p = self._get(name)
        p._wall_start = time.perf_counter()
        p._cpu_start  = time.process_time()
        p._active     = True

    def stop(self, name: str) -> None:
        p = self._get(name)
        if not p._active:
            return
        p.wall_s += max(0.0, time.perf_counter() - p._wall_start)
        p.cpu_s  += max(0.0, time.process_time() - p._cpu_start)
        p._active = False

    def add_tx(self, name: str, nbytes: int) -> None:
        self._get(name).tx_bytes += int(nbytes)

    def add_rx(self, name: str, nbytes: int) -> None:
        self._get(name).rx_bytes += int(nbytes)

    def phase_energy_j(self, name: str) -> float:
        p = self._get(name)
        return (p.cpu_s * self.cpu_power_w +
                (p.tx_bytes + p.rx_bytes) * self.net_energy_per_byte_j)

    def build_report(self, device_id: str) -> Dict:
        totals = {"wall_s": 0.0, "cpu_s": 0.0,
                  "tx_bytes": 0, "rx_bytes": 0, "energy_j": 0.0}
        phase_report: Dict[str, Dict] = {}
        for name, p in self.phases.items():
            energy = self.phase_energy_j(name)
            phase_report[name] = {
                "wall_s":   round(p.wall_s, 6),
                "cpu_s":    round(p.cpu_s,  6),
                "tx_bytes": p.tx_bytes,
                "rx_bytes": p.rx_bytes,
                "energy_j": round(energy, 9),
            }
            totals["wall_s"]   += p.wall_s
            totals["cpu_s"]    += p.cpu_s
            totals["tx_bytes"] += p.tx_bytes
            totals["rx_bytes"] += p.rx_bytes
            totals["energy_j"] += energy
        return {
            "kind":      "HW_METRIC",
            "role":      self.role,
            "device_id": str(device_id),
            "phases":    phase_report,
            "totals": {
                "wall_s":   round(totals["wall_s"],   6),
                "cpu_s":    round(totals["cpu_s"],    6),
                "tx_bytes": int(totals["tx_bytes"]),
                "rx_bytes": int(totals["rx_bytes"]),
                "energy_j": round(totals["energy_j"], 9),
            },
            "model": {
                "cpu_power_w":           self.cpu_power_w,
                "net_energy_per_byte_j": self.net_energy_per_byte_j,
            },
            "ts": int(time.time()),
        }


def print_metric_report(report: Dict) -> None:
    print("HW_METRIC|" + json.dumps(report, separators=(",", ":"), sort_keys=True))
