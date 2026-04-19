#!/usr/bin/env python3
"""
common.py — Shared cryptographic helpers for Revised-Anonymity hardware runtime.

Mirrors the exact crypto primitives from:
  Revised-Anonymity/as-node.c
  Revised-Anonymity/device-node.c
  Revised-Anonymity/gw-node.c

Primitives used:
  - AES-128-ECB  (pycryptodome)
  - SHA-256      (hashlib)
  - PUF simulation (deterministic seeded — mirrors C simulate_puf_response)
  - Helper / regenerate_response (mirrors C generate_helper / regenerate_response)
  - XOR byte-arrays
  - Metrics collector (wall time, CPU time, Tx/Rx bytes, estimated energy)
"""
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple

from Crypto.Cipher import AES as _AES

# =============================================================================
# Long-term keys  (MUST match the C source constants exactly)
# =============================================================================

#  K_AS_D  = "gats myKuog Fu\x00"  (16 bytes)
K_AS_D: bytes = bytes([
    0x67, 0x61, 0x74, 0x73, 0x20, 0x6D, 0x79, 0x20,
    0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75, 0x00,
])

#  K_GW_AS = "gbts myKuog Fu\x00"  (16 bytes)
K_GW_AS: bytes = bytes([
    0x67, 0x62, 0x74, 0x73, 0x20, 0x6D, 0x79, 0x20,
    0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75, 0x00,
])

# =============================================================================
# AES-128-ECB helpers
# =============================================================================

def aes_ecb_enc(key: bytes, data: bytes) -> bytes:
    """Encrypt data (must be multiple of 16 B) with AES-128-ECB."""
    assert len(data) % 16 == 0, f"aes_ecb_enc: data length {len(data)} not a multiple of 16"
    return _AES.new(key, _AES.MODE_ECB).encrypt(data)


def aes_ecb_dec(key: bytes, data: bytes) -> bytes:
    """Decrypt data (must be multiple of 16 B) with AES-128-ECB."""
    assert len(data) % 16 == 0, f"aes_ecb_dec: data length {len(data)} not a multiple of 16"
    return _AES.new(key, _AES.MODE_ECB).decrypt(data)


# =============================================================================
# SHA-256
# =============================================================================

def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


# =============================================================================
# XOR
# =============================================================================

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


# =============================================================================
# PUF simulation  (mirrors C simulate_puf_response / generate_helper /
#                  regenerate_response)
#
# C code:
#   simulate_puf_response(c):  p1 = rand^c; p2 = rand^c; return p1>p2 ? 1 : 0
#   generate_helper(r, h, s):  s=1; h = s & r          → h = r  (since s=1)
#   regenerate_response(c, h): h==0 ? h&c : h||c        → returns h always
#
# In hardware Python we make the PUF deterministic so it is reproducible
# across restarts.  We seed a SHA-256 of (node_id, challenge) to get two
# pseudo-random bytes and apply the same comparison as the C code.
# =============================================================================

def simulate_puf_response(node_id: int, challenge: int) -> int:
    """
    Deterministic 1-bit PUF response.
    Mirrors C: p1 = rand^c; p2 = rand^c; return p1 > p2 ? 1 : 0
    """
    seed = hashlib.sha256(
        node_id.to_bytes(2, "big") + challenge.to_bytes(2, "big")
    ).digest()
    p1 = (seed[0] ^ (challenge & 0xFF)) & 0xFF
    p2 = (seed[1] ^ (challenge & 0xFF)) & 0xFF
    return 1 if p1 > p2 else 0


def generate_helper(response: int) -> Tuple[int, int]:
    """
    Returns (helper, secret).
    Mirrors C: s = 1; h = s & r  →  helper = response, secret = 1
    """
    secret = 1
    helper = secret & response
    return helper, secret


def regenerate_response(challenge: int, helper: int) -> int:
    """
    Mirrors C: return (h == 0) ? (h & c) : (h || c)
    When h == 0: returns 0
    When h == 1: returns 1   (since 1 || anything == 1 in C boolean logic)
    Effectively returns helper regardless of challenge.
    """
    if helper == 0:
        return helper & challenge
    return 1  # h || c in C is any non-zero value → 1


# =============================================================================
# Freshness / sequence counter helpers
# =============================================================================

def seq_ts_fresh(new_ts: int, last_ts: int, window: int = 200) -> bool:
    """Sequence counter freshness: 0 < (new - last) mod 256 <= window."""
    diff = (new_ts - last_ts + 256) % 256
    return 0 < diff <= window


def clock_ts_fresh(recv_ts: int, window_s: int = 120) -> bool:
    """Clock-based uint8 freshness: low 8 bits of current time."""
    now  = int(time.time()) & 0xFF
    diff = (now - recv_ts + 256) % 256
    return diff < window_s


# =============================================================================
# JSON transport
# =============================================================================

def to_json_bytes(obj: Dict) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def from_json_bytes(raw: bytes) -> Dict:
    return json.loads(raw.decode("utf-8"))


# =============================================================================
# Config file parser  (same format as Extended-Scheme hardware)
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
# Identical structure to Extended-Scheme hardware for CSV compatibility.
# =============================================================================

@dataclass
class PhaseMetric:
    wall_s:  float = 0.0
    cpu_s:   float = 0.0
    tx_bytes: int  = 0
    rx_bytes: int  = 0
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
                "wall_s":    round(p.wall_s, 6),
                "cpu_s":     round(p.cpu_s,  6),
                "tx_bytes":  p.tx_bytes,
                "rx_bytes":  p.rx_bytes,
                "energy_j":  round(energy, 9),
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
