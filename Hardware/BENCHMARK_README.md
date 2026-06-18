# Hardware Benchmark: Cryptographic Operation Timing on RPi 4B

## Overview

This directory contains two benchmark implementations for measuring the execution
time of cryptographic operations on a Raspberry Pi 4B — the same platform used
for the hardware evaluation in this paper. The benchmarks replicate the methodology
of Kim et al. (Electronics 2025, 14, 1953, Section 8.1, Table 3), which used the
MIRACL cryptographic library to derive operation costs.

These measured values replace the earlier Windows/Pycrypto benchmark values that
were used in the computational cost comparison tables (Tables for Enrolment and
Auth & Key Exchange phases), giving first-party, platform-native numbers that
directly match the hardware evaluation setup.

---

## Why These Benchmarks

The paper's computational cost comparison (Section: Computational Cost) counts
cryptographic operations per phase for each scheme (Proposed, DAuth, LAAKA, Zhou)
and multiplies by unit costs. Having unit costs measured on the same RPi 4B used
for the hardware experiments makes the comparison self-consistent and independently
verifiable by reviewers.

**Reference methodology:** Kim et al. (Electronics 2025) measured the following
operations on a Raspberry Pi 4B (ARM Cortex-A72 @ 1.5 GHz, Ubuntu 20.04 LTS 64-bit)
using the MIRACL library:

| Symbol | Operation                        | GWN (ms) | RPi 4B (ms) |
|--------|----------------------------------|----------|-------------|
| T_M    | ECC point multiplication         | 0.411    | 2.353       |
| T_H    | SHA-256 one-way hash             | 0.001    | 0.009       |
| T_Kh   | HMAC-SHA-256 (keyed hash)        | 0.001    | 0.009       |
| T_S    | AES-128 symmetric enc/dec        | 0.001    | 0.004       |
| T_A    | RSA-2048 asymmetric enc/dec      | 0.373    | 4.764       |
| T_F    | Fuzzy extractor Gen              | 0.411    | 2.353       |
| T_P    | Physical unclonable function     | 0.0007   | 0.0063      |

Key observations from Kim et al.'s values that informed the implementation:
- **T_F = T_M**: The fuzzy extractor is ECC-based (Dodis et al., Eurocrypt 2004
  construction). `Gen(biometric)` hashes the biometric to a scalar then performs
  one ECC point multiplication — identical cost to T_M.
- **T_P < T_H**: The PUF is NOT a full hash. It is a software XOR-Arbiter PUF
  simulation: challenge bits are XOR'd against a device-unique delay table derived
  from the RPi hardware serial (`/proc/cpuinfo`). This takes ~128 XOR operations,
  far cheaper than SHA-256.
- **T_Kh ≈ T_H**: Keyed hash (HMAC) is two SHA-256 calls on short inputs,
  giving approximately the same cost as a single hash.

---

## Files

### `benchmark_rpi.py` — Python benchmark (quick start)

Measures all operations using standard Python libraries:

| Library       | Used for                        |
|---------------|---------------------------------|
| `hashlib`     | T_hash (SHA-256), T_hash3 (SHA-3) |
| `hmac`        | T_hmac (HMAC-SHA-256)           |
| `pycryptodome`| T_aes (AES-128)                 |
| `os.urandom`  | T_rand                          |
| `hmac` + serial | T_puf (HMAC with device seed) |
| `bchlib` + hash | T_fe_gen / T_fe_rep (BCH+SHA-256 FE) |
| `hmac` (HKDF) | T_kdf                           |

**Install dependencies:**
```bash
pip3 install pycryptodome bchlib
```

**Run:**
```bash
python3 benchmark_rpi.py
```

Reports: mean, stdev, min, max over 1000 iterations (100 warm-up discarded).

---

### `miracl_benchmark/` — C + MIRACL Core benchmark (exact replication)

Replicates Kim et al.'s exact methodology using the MIRACL cryptographic library.

#### Files

| File                    | Purpose                                        |
|-------------------------|------------------------------------------------|
| `setup_miracl_rpi.sh`   | Clones and builds MIRACL Core from GitHub      |
| `benchmark_miracl.c`    | C benchmark using MIRACL Core API              |
| `Makefile`              | Builds benchmark_miracl against MIRACL Core    |

#### Setup and run (on RPi 4B)

```bash
cd miracl_benchmark/
chmod +x setup_miracl_rpi.sh
./setup_miracl_rpi.sh        # clones github.com/miracl/MIRACL, builds core.a
make                          # compiles benchmark_miracl.c
./benchmark_miracl            # runs benchmark, prints table + Kim et al. comparison
```

`setup_miracl_rpi.sh` automates:
1. `sudo apt-get install git gcc python3 libssl-dev`
2. `git clone https://github.com/miracl/core.git`
3. `python3 config.py` (selects 64-bit word size + NIST P-256 curve)
4. `make` → produces `core.a`
5. Copies headers + library to `./miracl_core/`

#### MIRACL Core API used

| Operation       | MIRACL Core function                            |
|-----------------|-------------------------------------------------|
| SHA-256         | `HASH256_init`, `HASH256_process`, `HASH256_hash` |
| HMAC-SHA-256    | RFC 2104 manual construction over `HASH256_*`   |
| AES-128 ECB     | `AES_init(&a, ECB, 16, key, NULL)`, `AES_encrypt` |
| ECC P-256 mult  | `ECP_NIST256_generator`, `ECP_NIST256_mul`      |
| Fuzzy extractor | SHA-256 → scalar, then `ECP_NIST256_mul` (= T_M)|
| XOR-Arbiter PUF | 128-stage bitwise XOR against device delay table |
| RSA-2048        | OpenSSL `RSA_public_encrypt` (MIRACL FF module optional) |

---

## How to Cite Your Own Measurements

Once you run the benchmark on RPi 4B, replace the existing footnote in the paper:

**Before (Windows/Pycrypto):**
> Benchmark (avg. 100 iterations): T_rand=0.0018 ms, T_puf=0.0522 ms,
> T_hash=0.0353 ms, T_aes=0.0867 ms.

**After (RPi 4B / MIRACL):**
> Benchmark (avg. 1000 iterations on RPi 4B, ARM Cortex-A72 @ 1.5 GHz,
> Ubuntu 20.04 LTS 64-bit, MIRACL Core library): T_hash=X ms, T_puf=X ms,
> T_aes=X ms, T_rand=X ms. Methodology follows Kim et al. \cite{kim2025puf}.

---

## Hardware Setup for Benchmark

| Device  | Role      | IP Address      | Credentials      |
|---------|-----------|-----------------|------------------|
| RPi 4B  | Device    | 192.168.1.132   | Apex / raspberrypi |
| RPi 4B  | AS        | 192.168.1.113   | Pi / raspberrypi  |
| Laptop  | GW / Host | 172.16.117.188  | apex             |

Transfer files to RPi:
```bash
scp -r Hardware/miracl_benchmark/ Apex@192.168.1.132:~/
scp Hardware/benchmark_rpi.py     Apex@192.168.1.132:~/
```

Or pull from the RPi side:
```bash
# Run on RPi:
scp -r apex@172.16.117.188:/home/apex/contiki-ng/examples/Codes-For-COOJA/Hardware/miracl_benchmark/ ~/
```

---

## Reference

Kim, C.; Son, S.; Park, Y. A Privacy-Preserving Authentication Scheme Using PUF
and Biometrics for IoT-Enabled Smart Cities. *Electronics* **2025**, *14*, 1953.
https://doi.org/10.3390/electronics14101953

MIRACL Cryptographic SDK. Available: https://github.com/miracl/MIRACL
