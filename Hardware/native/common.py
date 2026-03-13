#!/usr/bin/env python3
import hashlib
import json
import os
import time
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
