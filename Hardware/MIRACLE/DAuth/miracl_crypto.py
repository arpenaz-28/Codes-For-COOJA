"""
miracl_crypto.py — ctypes wrapper over libmiraclshim.so (MIRACL Core, NIST P-256).

Drop-in crypto primitives for the end-to-end hardware sims, byte-compatible with
the Python (hashlib/pycryptodome) implementations in Hardware/common.py so that a
MIRACL-backed device/AS interoperates with a Python-backed gateway.

Locate the .so via env MIRACL_SO, else ./libmiraclshim.so next to this file.
"""
import os
import ctypes

_SO = os.environ.get("MIRACL_SO") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "libmiraclshim.so")
_lib = ctypes.CDLL(_SO)

_lib.m_sha256.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]
_lib.m_aes128_ecb_enc.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]
_lib.m_aes128_ecb_dec.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]
_lib.m_fe_p256.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]


def sha256(data: bytes) -> bytes:
    out = ctypes.create_string_buffer(32)
    _lib.m_sha256(bytes(data), len(data), out)
    return out.raw[:32]


def aes_enc_blocks(key: bytes, data: bytes) -> bytes:
    assert len(key) == 16 and len(data) % 16 == 0
    n = len(data) // 16
    out = ctypes.create_string_buffer(len(data))
    _lib.m_aes128_ecb_enc(bytes(key), bytes(data), n, out)
    return out.raw[:len(data)]


def aes_dec_blocks(key: bytes, data: bytes) -> bytes:
    assert len(key) == 16 and len(data) % 16 == 0
    n = len(data) // 16
    out = ctypes.create_string_buffer(len(data))
    _lib.m_aes128_ecb_dec(bytes(key), bytes(data), n, out)
    return out.raw[:len(data)]


def fe_p256(data: bytes) -> bytes:
    """ECC P-256 fuzzy extractor (one scalar mult); deterministic 32-byte output."""
    out = ctypes.create_string_buffer(32)
    _lib.m_fe_p256(bytes(data), len(data), out)
    return out.raw[:32]
