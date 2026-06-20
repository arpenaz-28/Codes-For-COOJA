"""Shared crypto primitives and TCP framing — same logic as the C source."""

import hashlib
import struct
import socket
import os

try:
    from Crypto.Cipher import AES
except ImportError:
    raise SystemExit("Install pycryptodome: pip3 install pycryptodome")

# ── Long-term keys (identical to the C constants) ──────────────────────────
K_AS_D  = bytes([0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
                 0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00])

K_GW_AS = bytes([0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
                 0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00])

# Zhou-scheme long-term keys
K_GW_U  = bytes([0x67,0x77,0x75,0x73,0x20,0x6D,0x79,0x20,
                 0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00])

K_GW_SN = bytes([0x73,0x6E,0x67,0x77,0x20,0x6B,0x65,0x79,
                 0x5F,0x73,0x65,0x63,0x75,0x72,0x65,0x00])

# ── Crypto helpers ──────────────────────────────────────────────────────────

def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def aes_enc_blocks(key: bytes, data: bytes) -> bytes:
    """AES-128-ECB encrypt, block by block (matches C aes_enc(key, buf, n))."""
    assert len(data) % 16 == 0, f"data length {len(data)} not multiple of 16"
    assert len(key) == 16
    result = bytearray()
    cipher = AES.new(key, AES.MODE_ECB)
    for i in range(0, len(data), 16):
        result += cipher.encrypt(data[i:i+16])
    return bytes(result)


def aes_dec_blocks(key: bytes, data: bytes) -> bytes:
    """AES-128-ECB decrypt, block by block."""
    assert len(data) % 16 == 0
    assert len(key) == 16
    result = bytearray()
    cipher = AES.new(key, AES.MODE_ECB)
    for i in range(0, len(data), 16):
        result += cipher.decrypt(data[i:i+16])
    return bytes(result)


def xor32(a: bytes, b: bytes) -> bytes:
    assert len(a) == 32 and len(b) == 32
    return bytes(x ^ y for x, y in zip(a, b))


def puf_response(node_id: int, challenge: int) -> int:
    """Deterministic software PUF — same multiplicative-hash as C puf_response()."""
    s = (node_id * 2246822519) ^ (challenge * 2654435761)
    s &= 0xFFFFFFFF
    s = ((s >> 16) ^ s) * 0x45d9f3b & 0xFFFFFFFF
    s = ((s >> 16) ^ s) * 0x45d9f3b & 0xFFFFFFFF
    s ^= (s >> 16)
    return s & 0xFF


def puf_response_zhou(node_id: int, challenge: int) -> int:
    """Zhou-scheme PUF: SHA256(node_id || challenge)[0]."""
    return sha256(bytes([node_id & 0xFF, challenge & 0xFF]))[0]


def rand_bytes(n: int) -> bytes:
    return os.urandom(n)


# Python-fallback fuzzy extractor stub (only Zhou uses a real FE; replaced by the
# MIRACL ECC FE below when USE_MIRACL=1). Kept so imports never break.
def fe_p256(data: bytes) -> bytes:
    return sha256(data)


# ── Optional MIRACL Core crypto backend ────────────────────────────────────
# When USE_MIRACL=1, route SHA-256 / AES-128-ECB / FE through libmiraclshim.so
# (ctypes). Outputs are byte-identical to the Python primitives above, so a
# MIRACL-backed device/AS interoperates with a Python-backed gateway.
if os.environ.get("USE_MIRACL") == "1":
    import sys as _sys
    try:
        from miracl_crypto import (sha256 as _m_sha256,
                                    aes_enc_blocks as _m_aes_enc,
                                    aes_dec_blocks as _m_aes_dec,
                                    fe_p256 as _m_fe)
        sha256          = _m_sha256
        aes_enc_blocks  = _m_aes_enc
        aes_dec_blocks  = _m_aes_dec
        fe_p256         = _m_fe
        print("[common] MIRACL Core crypto ENABLED", file=_sys.stderr)
    except Exception as _e:
        print(f"[common] MIRACL requested but unavailable ({_e}); "
              f"falling back to Python crypto", file=_sys.stderr)

# ── TCP framing (4-byte big-endian length prefix) ──────────────────────────

def send_msg(sock: socket.socket, data: bytes) -> None:
    sock.sendall(struct.pack('>I', len(data)) + data)


def recv_msg(sock: socket.socket) -> bytes:
    raw = _recv_exact(sock, 4)
    length = struct.unpack('>I', raw)[0]
    return _recv_exact(sock, length)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed unexpectedly")
        buf += chunk
    return buf


def make_server(port: int, backlog: int = 5) -> socket.socket:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', port))
    srv.listen(backlog)
    return srv
