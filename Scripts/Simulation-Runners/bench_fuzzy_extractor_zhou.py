"""
bench_fe_zhou.py -- Direct measurement of Zhou et al.'s BIOMETRIC fuzzy
extractor (Gen / Rep), on the SAME platform/methodology as every other
primitive in the paper: avg. 100 iterations, Windows, pycryptodome (+ bchlib
for the error-correcting-code step).

Zhou's protocol:
    registration:   (k_i, hid_i) = Gen(BIO_i)
    authentication: k_i          = Rep(hid_i, BIO_i)

Construction = standard code-offset fuzzy extractor with a CONCATENATED code
(realistic for noisy biometrics with a high intra-template error rate):
    inner  = repetition code (R-bit majority vote)  -> beats down the raw
             biometric error rate
    outer  = BCH code over the inner-decoded symbols -> corrects residuals
    extractor = SHA-256 over the recovered secret    -> uniform key k_i

We report Gen, Rep, and one full FE invocation (Gen+Rep).
"""

import os, time, statistics, numpy as np
import bchlib
from Crypto.Hash import SHA256

ITERS    = 100
REP      = 7            # inner repetition factor (majority vote)
ERR_RATE = 0.15         # ~15% intra-biometric bit error rate
BCH_M    = 9            # outer BCH over GF(2^9): codeword n = 511 bits
BCH_T    = 22           # outer correction capacity

bch = bchlib.BCH(BCH_T, m=BCH_M)
OUTER_DATA_B = bch.n // 8 - bch.ecc_bytes          # secret bytes (outer message)
OUTER_LEN_B  = OUTER_DATA_B + bch.ecc_bytes        # outer codeword bytes
OUTER_LEN    = OUTER_LEN_B * 8                      # outer codeword bits
BIO_BITS     = OUTER_LEN * REP                      # biometric template length

def _bits(b: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(b, dtype=np.uint8))

def _bytes(bits: np.ndarray) -> bytes:
    return np.packbits(bits).tobytes()

def gen(bio_bits: np.ndarray):
    d   = os.urandom(OUTER_DATA_B)                  # random secret
    ecc = bytes(bch.encode(d))
    outer_cw = _bits(d + ecc)                       # OUTER_LEN bits
    inner_cw = np.repeat(outer_cw, REP)             # BIO_BITS bits
    s = np.bitwise_xor(bio_bits, inner_cw)          # helper data
    R = SHA256.new(d).digest()
    return R, s

def rep(bio_noisy: np.ndarray, s: np.ndarray):
    ec = np.bitwise_xor(bio_noisy, s)               # inner codeword + errors
    # inner decode: majority vote over each block of REP bits
    votes = ec.reshape(-1, REP).sum(axis=1)
    outer_est = (votes > (REP // 2)).astype(np.uint8)   # OUTER_LEN bits
    cw = _bytes(outer_est)
    data = bytearray(cw[:OUTER_DATA_B])
    ecc  = bytearray(cw[OUTER_DATA_B:])
    bch.decode(data, ecc)                           # outer decode + correct
    bch.correct(data, ecc)
    R = SHA256.new(bytes(data)).digest()
    return R

def time_loop(fn, iters):
    ts = []
    for _ in range(iters):
        t0 = time.perf_counter(); fn(); ts.append((time.perf_counter()-t0)*1000.0)
    return statistics.mean(ts), statistics.stdev(ts)

def main():
    n_err = int(ERR_RATE * BIO_BITS)
    print(f"Zhou biometric FE: template={BIO_BITS} bits, secret={OUTER_DATA_B*8} bits, "
          f"rep={REP}, outer BCH(m={BCH_M},t={BCH_T}), err={ERR_RATE} (~{n_err} flips), "
          f"iters={ITERS}\n")

    bio = _bits(os.urandom(BIO_BITS // 8))
    R0, s0 = gen(bio)
    noisy = bio.copy()
    flip = np.random.choice(BIO_BITS, n_err, replace=False)
    noisy[flip] ^= 1
    print(f"Rep recovers key correctly: {rep(noisy, s0) == R0}")

    g_mean, g_sd = time_loop(lambda: gen(bio), ITERS)
    r_mean, r_sd = time_loop(lambda: rep(noisy, s0), ITERS)
    print(f"\nT_fe (Gen)      = {g_mean:.4f} ms  (sd {g_sd:.4f})")
    print(f"T_fe (Rep)      = {r_mean:.4f} ms  (sd {r_sd:.4f})")
    print(f"T_fe (Gen+Rep)  = {g_mean + r_mean:.4f} ms")
    print(f"\nReference (same platform): T_hash=0.0353  T_aes=0.0867  "
          f"T_puf=0.0522  T_rand=0.0018 ms")

if __name__ == "__main__":
    main()
