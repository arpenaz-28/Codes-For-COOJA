"""
Cryptographic Operation Benchmark — RPi 4B
===========================================
Measures average execution time (ms) over N iterations for all common
cryptographic operations used in IoT authentication papers.

Operations measured:
  T_hash   : SHA-256 one-way hash
  T_hmac   : HMAC-SHA-256 (keyed hash)
  T_aes    : AES-128 symmetric encryption / decryption
  T_rand   : Secure random number generation
  T_puf    : Software arbiter-PUF (HMAC-SHA256 with device seed)
  T_fe_gen : Fuzzy extractor Gen  (BCH secure sketch + SHA-256 extractor)
  T_fe_rep : Fuzzy extractor Rep  (BCH decode + SHA-256 extractor)
  T_kdf    : HKDF-SHA-256 key derivation
  T_xor    : Byte-wise XOR (16 bytes) — expected negligible
  T_concat : Byte concatenation     — expected negligible

Run on target device:
    python3 benchmark_rpi.py

Requirements (install once):
    pip3 install pycryptodome bchlib
"""

import hashlib
import hmac as _hmac
import os
import time
import statistics
import platform
import sys

# ── optional dependency flags ────────────────────────────────────────────────
try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("[WARN] pycryptodome not found — AES benchmark skipped.")
    print("       pip3 install pycryptodome\n")

try:
    import bchlib
    HAS_BCH = True
except ImportError:
    HAS_BCH = False
    print("[WARN] bchlib not found — fuzzy extractor will use hash-only fallback.")
    print("       pip3 install bchlib\n")

# ── configuration ─────────────────────────────────────────────────────────────

N_WARMUP  = 100    # iterations discarded before measurement
N_MEASURE = 1000   # measured iterations

# Fixed payloads — representative of 128-bit auth tokens
DATA_16 = os.urandom(16)
DATA_32 = os.urandom(32)
AES_KEY = os.urandom(16)
HMAC_KEY = os.urandom(32)

# PUF: device-unique seed from RPi serial in /proc/cpuinfo
def _rpi_serial() -> bytes:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("Serial"):
                    return bytes.fromhex(line.split(":")[1].strip().zfill(16))
    except Exception:
        pass
    return b"\xde\xad\xbe\xef\xca\xfe\xba\xbe\x01\x23\x45\x67\x89\xab\xcd\xef"

PUF_SEED      = _rpi_serial()
PUF_CHALLENGE = os.urandom(16)

# BCH fuzzy extractor parameters
# BCH_POLY and BCH_BITS must match when creating bchlib.BCH()
BCH_POLY = 8219
BCH_BITS = 4          # corrects up to 4 bit-flips in biometric
BIO_LEN  = 16         # biometric template length in bytes

# Fixed biometric template (simulates fingerprint template)
BIOMETRIC = os.urandom(BIO_LEN)

# ── timing helper ─────────────────────────────────────────────────────────────

def measure(func) -> tuple:
    """Return (mean_ms, stdev_ms, min_ms, max_ms) over N_MEASURE iterations."""
    for _ in range(N_WARMUP):
        func()
    samples = []
    for _ in range(N_MEASURE):
        t0 = time.perf_counter_ns()
        func()
        t1 = time.perf_counter_ns()
        samples.append((t1 - t0) / 1_000_000)   # ns → ms
    return (
        statistics.mean(samples),
        statistics.stdev(samples),
        min(samples),
        max(samples),
    )

def report(symbol: str, name: str, result: tuple):
    mean, std, lo, hi = result
    print(f"  {symbol:<14s}  {name:<40s}  "
          f"mean={mean:.4f} ms   std={std:.4f}   "
          f"[{lo:.4f}, {hi:.4f}]")

# ── benchmark functions ───────────────────────────────────────────────────────

# --- Hash ---
def b_hash():
    hashlib.sha256(DATA_32).digest()

def b_hash3():
    hashlib.sha3_256(DATA_32).digest()

# --- Keyed hash / HMAC ---
def b_hmac():
    _hmac.new(HMAC_KEY, DATA_32, hashlib.sha256).digest()

# --- Random generation ---
def b_rand():
    os.urandom(16)

# --- PUF (software arbiter PUF via HMAC-SHA256 with device seed) ---
def b_puf():
    _hmac.new(PUF_SEED, PUF_CHALLENGE, hashlib.sha256).digest()

# --- AES-128 ECB (single 16-byte block) ---
if HAS_CRYPTO:
    def b_aes_enc():
        AES.new(AES_KEY, AES.MODE_ECB).encrypt(DATA_16)

    _ct = AES.new(AES_KEY, AES.MODE_ECB).encrypt(DATA_16)
    def b_aes_dec():
        AES.new(AES_KEY, AES.MODE_ECB).decrypt(_ct)

# --- HKDF (key derivation) ---
def b_kdf():
    # HKDF-SHA256: extract then expand
    prk = _hmac.new(b"salt_16byteslong", DATA_32, hashlib.sha256).digest()
    _hmac.new(prk, b"info" + b"\x01", hashlib.sha256).digest()

# --- XOR (negligible — for completeness) ---
def b_xor():
    bytes(a ^ b for a, b in zip(DATA_16, DATA_32[:16]))

# --- Concatenation (negligible) ---
def b_concat():
    DATA_16 + DATA_32

# --- Fuzzy Extractor (BCH secure sketch + SHA-256 strong extractor) ---
#
# Construction (Dodis et al., Eurocrypt 2004):
#   Gen(w):
#     1. Encode w with BCH → ecc_bits
#     2. Compute helper P = ecc_bits   (public — reveals no info about w)
#     3. Key R = SHA-256(w || P)
#     Returns (R, P)
#
#   Rep(w', P):
#     1. BCH-decode w' using P → w_corrected  (corrects up to BCH_BITS errors)
#     2. Recompute R = SHA-256(w_corrected || P)
#     Returns R  (identical to Gen output if dist(w,w') ≤ BCH_BITS)

if HAS_BCH:
    _bch = bchlib.BCH(BCH_POLY, BCH_BITS)
    _bio_bytes = bytearray(BIOMETRIC)
    _ecc_ref   = bytearray(_bch.encode(_bio_bytes))

    def b_fe_gen():
        bio = bytearray(os.urandom(BIO_LEN))   # fresh biometric each time
        ecc = bytearray(_bch.encode(bio))
        _ = hashlib.sha256(bytes(bio) + bytes(ecc)).digest()

    def b_fe_rep():
        # Simulate noisy reading: flip 2 bits (within BCH_BITS tolerance)
        noisy = bytearray(_bio_bytes)
        noisy[0] ^= 0x03
        data_with_ecc = bytearray(noisy) + bytearray(_ecc_ref)
        _bch.decode(data_with_ecc[:BIO_LEN], data_with_ecc[BIO_LEN:])
        _ = hashlib.sha256(bytes(data_with_ecc[:BIO_LEN]) + bytes(_ecc_ref)).digest()

else:
    # Hash-only fallback (no error correction — measures lower-bound cost)
    def b_fe_gen():
        bio = os.urandom(BIO_LEN)
        helper = hashlib.sha256(bio).digest()
        _ = hashlib.sha256(bio + helper).digest()

    def b_fe_rep():
        bio = os.urandom(BIO_LEN)
        helper = hashlib.sha256(bio).digest()
        _ = hashlib.sha256(bio + helper).digest()

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("  Cryptographic Operation Benchmark — RPi 4B")
    print("=" * 80)
    print(f"  Platform   : {platform.machine()} / {platform.system()} {platform.release()}")
    print(f"  Python     : {sys.version.split()[0]}")
    print(f"  Iterations : {N_WARMUP} warm-up  +  {N_MEASURE} measured")
    print(f"  PUF seed   : RPi hardware serial ({PUF_SEED.hex()})")
    print(f"  BCH library: {'bchlib (proper FE)' if HAS_BCH else 'fallback hash-only FE'}")
    print()

    print("── Hash operations ──────────────────────────────────────────────────────────")
    report("T_hash",       "SHA-256 (32-byte input)",          measure(b_hash))
    report("T_hash3",      "SHA-3-256 (32-byte input)",        measure(b_hash3))
    report("T_hmac",       "HMAC-SHA-256 (keyed hash)",        measure(b_hmac))
    print()

    print("── Random / PUF ─────────────────────────────────────────────────────────────")
    report("T_rand",       "os.urandom(16)",                   measure(b_rand))
    report("T_puf",        "Soft. PUF — HMAC(device_seed, C)", measure(b_puf))
    print()

    print("── Fuzzy Extractor  (Dodis et al. BCH+SHA256 construction) ──────────────────")
    report("T_fe_gen",     "FE Gen  — BCH encode + SHA-256",   measure(b_fe_gen))
    report("T_fe_rep",     "FE Rep  — BCH decode + SHA-256",   measure(b_fe_rep))
    print()

    if HAS_CRYPTO:
        print("── Symmetric cipher (AES-128 ECB, 16-byte block) ────────────────────────────")
        report("T_aes_enc",    "AES-128 encrypt",               measure(b_aes_enc))
        report("T_aes_dec",    "AES-128 decrypt",               measure(b_aes_dec))
        print()

    print("── Key derivation ───────────────────────────────────────────────────────────")
    report("T_kdf",        "HKDF-SHA-256",                     measure(b_kdf))
    print()

    print("── Negligible operations (expected < 0.001 ms) ──────────────────────────────")
    report("T_xor",        "XOR 16 bytes",                     measure(b_xor))
    report("T_concat",     "Byte concat (16+32)",              measure(b_concat))
    print()

    # ── summary table ─────────────────────────────────────────────────────────
    print("=" * 80)
    print("  SUMMARY — values for paper Table (mean over 1000 iterations, RPi 4B)")
    print("=" * 80)
    rows = [
        ("T_hash",    "SHA-256",          b_hash),
        ("T_hmac",    "HMAC-SHA-256",     b_hmac),
        ("T_rand",    "os.urandom(16)",   b_rand),
        ("T_puf",     "Software PUF",     b_puf),
        ("T_fe_gen",  "FE Gen",           b_fe_gen),
        ("T_fe_rep",  "FE Rep",           b_fe_rep),
        ("T_kdf",     "HKDF",             b_kdf),
    ]
    if HAS_CRYPTO:
        rows.insert(2, ("T_aes",  "AES-128 enc",  b_aes_enc))

    print(f"  {'Symbol':<12}  {'Operation':<20}  {'Mean (ms)':>10}  {'Std (ms)':>10}")
    print(f"  {'-'*12}  {'-'*20}  {'-'*10}  {'-'*10}")
    for sym, name, func in rows:
        m, s, _, _ = measure(func)
        print(f"  {sym:<12}  {name:<20}  {m:>10.4f}  {s:>10.4f}")
    print()

if __name__ == "__main__":
    main()
