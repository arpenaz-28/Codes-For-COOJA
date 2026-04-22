#!/usr/bin/env python3
"""
common.py — Shared cryptographic helpers for LAAKA hardware runtime.

Mirrors the exact crypto primitives from:
  LAAKA/as-node.c
  LAAKA/device-node.c
  LAAKA/gw-node.c

Primitives used:
  - AES-128-ECB  (pycryptodome)
  - SHA-256 truncated to 20 bytes  (HASH_LEN = 20)
  - XOR byte-arrays
  - Metrics collector (wall time, CPU time, Tx/Rx bytes, estimated energy)
"""
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict

from Crypto.Cipher import AES as _AES

# =============================================================================
# LAAKA Protocol Constants  (MUST match the C source constants exactly)
# =============================================================================

HASH_LEN: int = 20   # SHA-256 output truncated to first 20 bytes
RAND_LEN: int = 20   # All random values: 20 bytes

#  K_RA_D  = "gats myKuog Fu\x00"  (16 bytes)
K_RA_D: bytes = bytes([
    0x67, 0x61, 0x74, 0x73, 0x20, 0x6D, 0x79, 0x20,
    0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75, 0x00,
])

#  K_RA_GW = "gbts myKuog Fu\x00"  (16 bytes)
K_RA_GW: bytes = bytes([
    0x67, 0x62, 0x74, 0x73, 0x20, 0x6D, 0x79, 0x20,
    0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75, 0x00,
])

# K_MASTER (20 bytes)
K_MASTER: bytes = bytes([
    0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE, 0xBA, 0xBE,
    0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF,
    0xFE, 0xDC, 0xBA, 0x98,
])

# r1_fog — Fog server identity random (20 bytes)
R1_FOG: bytes = bytes([
    0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88,
    0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x01,
    0x02, 0x03, 0x04, 0x05,
])

# TIDf_const — Fixed Fog Terminal ID (20 bytes)
TIDF_CONST: bytes = bytes([
    0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6, 0x07, 0x18,
    0x29, 0x3A, 0x4B, 0x5C, 0x6D, 0x7E, 0x8F, 0x90,
    0x01, 0x12, 0x23, 0x34,
])

# FOG_IDENTITY_ID from project-conf.h
FOG_IDENTITY_ID: int = 1

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
# SHA-256 truncated to HASH_LEN (20 bytes)
# Mirrors C: sha256_truncate() → first HASH_LEN bytes of digest
# =============================================================================

def sha256_20(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()[:HASH_LEN]


# =============================================================================
# XOR
# =============================================================================

def xor_bytes(a: bytes, b: bytes) -> bytes:
    assert len(a) == len(b), f"xor_bytes: length mismatch {len(a)} vs {len(b)}"
    return bytes(x ^ y for x, y in zip(a, b))


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
# Identical structure to Revised-Anonymity hardware for CSV compatibility.
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
