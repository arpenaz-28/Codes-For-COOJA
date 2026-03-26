#!/usr/bin/env python3
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict

import numpy as np
from pypuf.simulation import ArbiterPUF


def now_ts() -> int:
    return int(time.time())


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def xor_hex(a_hex: str, b_hex: str) -> str:
    a = bytes.fromhex(a_hex)
    b = bytes.fromhex(b_hex)
    out = bytes(x ^ y for x, y in zip(a, b))
    return out.hex()


def keystream(key_hex: str, nonce: str, nbytes: int) -> bytes:
    key = bytes.fromhex(key_hex)
    out = b""
    counter = 0
    while len(out) < nbytes:
        block = hashlib.sha256(key + nonce.encode("utf-8") + str(counter).encode("utf-8")).digest()
        out += block
        counter += 1
    return out[:nbytes]


def encrypt_text(plaintext: str, key_hex: str, nonce: str) -> str:
    data = plaintext.encode("utf-8")
    ks = keystream(key_hex, nonce, len(data))
    cipher = bytes(a ^ b for a, b in zip(data, ks))
    return cipher.hex()


def decrypt_text(cipher_hex: str, key_hex: str, nonce: str) -> str:
    data = bytes.fromhex(cipher_hex)
    ks = keystream(key_hex, nonce, len(data))
    plain = bytes(a ^ b for a, b in zip(data, ks))
    return plain.decode("utf-8", errors="replace")


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


def to_json_bytes(obj: Dict) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def from_json_bytes(raw: bytes) -> Dict:
    return json.loads(raw.decode("utf-8"))


def seed_to_int(seed_text: str) -> int:
    return int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)


def make_puf(device_seed: str, n_bits: int) -> ArbiterPUF:
    return ArbiterPUF(n=n_bits, k=1, seed=seed_to_int(device_seed))


def challenge_from_hex(ch_hex: str, n_bits: int) -> np.ndarray:
    bits = []
    for c in ch_hex.lower():
        v = int(c, 16)
        bits.extend([(v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1])
    bits = bits[:n_bits]
    return np.array([1 if b == 1 else -1 for b in bits], dtype=np.int8)


def random_challenge_hex(n_bits: int) -> str:
    n_hex = (n_bits + 3) // 4
    return os.urandom(n_hex).hex()


def puf_response_bit(puf: ArbiterPUF, challenge_hex: str, n_bits: int) -> int:
    ch = challenge_from_hex(challenge_hex, n_bits)
    resp = puf.eval(ch.reshape(1, -1))[0]
    return 1 if float(resp) >= 0 else -1


@dataclass
class PhaseMetric:
    wall_s: float = 0.0
    cpu_s: float = 0.0
    tx_bytes: int = 0
    rx_bytes: int = 0
    _wall_start: float = 0.0
    _cpu_start: float = 0.0
    _active: bool = False


@dataclass
class MetricsCollector:
    role: str
    cpu_power_w: float
    net_energy_per_byte_j: float
    phases: Dict[str, PhaseMetric] = field(default_factory=dict)

    def _get(self, name: str) -> PhaseMetric:
        if name not in self.phases:
            self.phases[name] = PhaseMetric()
        return self.phases[name]

    def start(self, name: str) -> None:
        p = self._get(name)
        p._wall_start = time.perf_counter()
        p._cpu_start = time.process_time()
        p._active = True

    def stop(self, name: str) -> None:
        p = self._get(name)
        if not p._active:
            return
        p.wall_s += max(0.0, time.perf_counter() - p._wall_start)
        p.cpu_s += max(0.0, time.process_time() - p._cpu_start)
        p._active = False

    def add_tx(self, name: str, nbytes: int) -> None:
        self._get(name).tx_bytes += int(nbytes)

    def add_rx(self, name: str, nbytes: int) -> None:
        self._get(name).rx_bytes += int(nbytes)

    def phase_energy_j(self, name: str) -> float:
        p = self._get(name)
        return p.cpu_s * self.cpu_power_w + (p.tx_bytes + p.rx_bytes) * self.net_energy_per_byte_j

    def build_report(self, device_id: str) -> Dict:
        totals = {"wall_s": 0.0, "cpu_s": 0.0, "tx_bytes": 0, "rx_bytes": 0, "energy_j": 0.0}
        phase_report: Dict[str, Dict] = {}
        for name, p in self.phases.items():
            energy = self.phase_energy_j(name)
            phase_report[name] = {
                "wall_s": round(p.wall_s, 6),
                "cpu_s": round(p.cpu_s, 6),
                "tx_bytes": p.tx_bytes,
                "rx_bytes": p.rx_bytes,
                "energy_j": round(energy, 9),
            }
            totals["wall_s"] += p.wall_s
            totals["cpu_s"] += p.cpu_s
            totals["tx_bytes"] += p.tx_bytes
            totals["rx_bytes"] += p.rx_bytes
            totals["energy_j"] += energy

        return {
            "kind": "HW_METRIC",
            "role": self.role,
            "device_id": str(device_id),
            "phases": phase_report,
            "totals": {
                "wall_s": round(totals["wall_s"], 6),
                "cpu_s": round(totals["cpu_s"], 6),
                "tx_bytes": int(totals["tx_bytes"]),
                "rx_bytes": int(totals["rx_bytes"]),
                "energy_j": round(totals["energy_j"], 9),
            },
            "model": {
                "cpu_power_w": self.cpu_power_w,
                "net_energy_per_byte_j": self.net_energy_per_byte_j,
            },
            "ts": now_ts(),
        }


def print_metric_report(report: Dict) -> None:
    print("HW_METRIC|" + json.dumps(report, separators=(",", ":"), sort_keys=True))
