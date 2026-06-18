"""
bench_fe.py  --  Direct measurement of fuzzy-extractor cost (T_fe) on the SAME
platform/methodology used for T_hash, T_aes, T_puf in the paper:
    avg. of 100 iterations, Windows, pycryptodome (+ bchlib for the ECC step).

Fuzzy extractor = code-offset construction (the standard PUF FE):
  Gen(w):  k_seed <- random message ;  c = k_seed || BCH.encode(k_seed) ;
           helper s = w XOR c ;  key R = SHA256(k_seed)            -> (R, s)
  Rep(w',s): c' = w' XOR s ;  (data,ecc)=split(c') ;
             BCH.decode+correct -> k_seed ;  R = SHA256(k_seed)    -> R

Banerjee et al.'s "2 T_fe" = two FE invocations; we report a single FE = the
Rep (reproduction) path, which dominates runtime (encode is cheap, decode does
syndrome + Berlekamp-Massey + Chien search).
"""

import os, time, statistics, random
import bchlib
from Crypto.Hash import SHA256

ITERS   = 100          # match paper methodology (avg 100 iterations)
BCH_M   = 9            # GF(2^9) -> codeword n = 511 bits
BCH_T   = 40           # correct up to 40 bit errors
N_ERR   = 30           # injected intra-PUF errors (< t, so Rep succeeds)

bch = bchlib.BCH(BCH_T, m=BCH_M)
DATA_BYTES = bch.n // 8 - bch.ecc_bytes   # secret/message size (18 B)
ECC_BYTES  = bch.ecc_bytes                # parity size        (45 B)
RESP_BYTES = DATA_BYTES + ECC_BYTES       # full PUF response  (63 B = 504 b)

def gen(w: bytes):
    k_seed = os.urandom(DATA_BYTES)
    ecc    = bytes(bch.encode(k_seed))
    c      = k_seed + ecc                                  # full codeword
    s      = bytes(a ^ b for a, b in zip(w, c))            # helper data
    R      = SHA256.new(k_seed).digest()                   # extracted key
    return R, s

def rep(w_noisy: bytes, s: bytes):
    c_prime = bytes(a ^ b for a, b in zip(w_noisy, s))     # codeword + errors
    data    = bytearray(c_prime[:DATA_BYTES])
    ecc     = bytearray(c_prime[DATA_BYTES:])
    bch.decode(data, ecc)
    bch.correct(data, ecc)
    R = SHA256.new(bytes(data)).digest()
    return R

def time_loop(fn, iters):
    ts = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000.0)     # ms
    return statistics.mean(ts), statistics.stdev(ts)

def main():
    print(f"FE: code-offset, resp={RESP_BYTES*8} bits, secret={DATA_BYTES*8} bits, "
          f"BCH(m={BCH_M}, t={BCH_T}), {N_ERR} injected errors, iters={ITERS}\n")

    w = os.urandom(RESP_BYTES)
    R0, s0 = gen(w)
    wn = bytearray(w)
    for p in random.sample(range(RESP_BYTES * 8), N_ERR):
        wn[p // 8] ^= 1 << (p % 8)
    w_noisy = bytes(wn)

    print(f"Rep recovers key correctly: {rep(w_noisy, s0) == R0}")

    g_mean, g_sd = time_loop(lambda: gen(w), ITERS)
    r_mean, r_sd = time_loop(lambda: rep(w_noisy, s0), ITERS)

    print(f"\nT_fe (Gen)      = {g_mean:.4f} ms  (sd {g_sd:.4f})")
    print(f"T_fe (Rep)      = {r_mean:.4f} ms  (sd {r_sd:.4f})")
    print(f"T_fe (Gen+Rep)  = {g_mean + r_mean:.4f} ms")
    print(f"\n--> Single FE invocation (Rep = dominant cost): {r_mean:.4f} ms")
    # for reference, the other paper primitives:
    print("\nReference (paper): T_hash=0.0353  T_aes=0.0867  T_puf=0.0522  T_rand=0.0018 ms")

if __name__ == "__main__":
    main()
