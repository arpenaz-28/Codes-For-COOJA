# Hardware/MIRACLE — MIRACL Core hardware study (all four schemes)

This folder holds the **MIRACL Core (NIST P-256)** hardware work for all four
authentication schemes — **Proposed, DAuth, LAAKA, Zhou** — run on real Raspberry
Pi 4B nodes. It is **exploratory / archival and is NOT part of the paper**; the
paper's existing charts and tables are untouched.

All cryptography on the **measured RPi nodes** is routed through
`libmiraclshim.so` (a thin C shim over MIRACL Core, called from Python via
ctypes). The laptop-side node (GW/RA) stays on Python and still interoperates,
because MIRACL SHA-256 / AES-128-ECB are **byte-identical** to hashlib /
pycryptodome (verified on both Pis).

> Testbed: Device/Pi `192.168.1.113`, AS/Apex `192.168.1.132`, GW/RA = laptop
> `192.168.1.201`. Energy model: `wall_time × 3.8 W` (3800 mW), as in the existing
> hardware charts. Per-process backend toggle: `USE_MIRACL=1`.

## Shared MIRACL backend
| File | Purpose |
|---|---|
| `miracl_shim.c` | C shim over MIRACL Core: SHA-256, AES-128-ECB enc/dec, ECC P-256 fuzzy extractor |
| `libmiraclshim.so` | built shim (aarch64; statically links `core.a`; libc-only deps) |
| `miracl_crypto.py` | ctypes wrapper exposing `sha256 / aes_enc_blocks / aes_dec_blocks / fe_p256` |

## (A) Compute-only benchmark — pure computation, no network
Runs each scheme's exact operation sequence through MIRACL on the Pi and times it.
- Files: `scheme_compute_bench.c`, `run_01..03.csv`, `plot_compute_miracl.py`,
  `compute_miracl_aggregate.json`, `hw_compute_miracl.png`, `build_run.log`.
- Details: **[COMPUTE_BENCHMARK.md](COMPUTE_BENCHMARK.md)**.
- Result: Zhou ≈ 45× heavier (ECC fuzzy extractor); the other three are sub-0.1 mJ
  of computation per round.

## (B) Full end-to-end sims — real TCP + real computation, per scheme
Each subfolder is **self-contained** (role scripts + `common.py`/`config.py` +
MIRACL backend + orchestrator + `results/`). Run from inside it:
```bash
cd Hardware/MIRACLE/<scheme>
python run_simulation.py 1            # MIRACL end-to-end -> results/run_01.json
USE_MIRACL=0 python run_simulation.py 1   # Python-crypto baseline
```

| Folder | Scheme | Measured node | Notes |
|---|---|---|---|
| [`Proposed/`](Proposed/README.md) | Proposed (this paper) | Device = Pi | push-based KeyEx |
| [`LAAKA/`](LAAKA/README.md) | LAAKA (2024) | Device = Pi | **live Fog↔RA registration** (§4.2.1), measured |
| [`Zhou/`](Zhou/README.md) | Zhou (2024) | User = Apex | **real ECC fuzzy extractor** (2 FE ops) |
| [`DAuth/`](DAuth/README.md) | **Fair-DAuth** | Device = Pi | DAuth core on Proposed's transport (push, binary) |

- Cross-scheme + MIRACL-vs-Python: `batch_e2e.py`, `aggregate_e2e.py`, `e2e/`,
  `e2e_aggregate.json`, `hw_e2e_miracl_vs_python.png`, `hw_e2e_miracl.png` —
  details in **[E2E_README.md](E2E_README.md)**.
- DAuth fairness study (push vs pull): `DAuth/compare_fair.py` — see `DAuth/README.md`.

## Headline findings
1. **End-to-end is network-bound.** MIRACL vs Python differs by < 1 std for every
   scheme; even Zhou's real ECC fuzzy extractor (~1.1 ms) is invisible against
   ~28 ms of TCP round-trip. Scheme ordering is set by **round-trip count**, not crypto.
2. **The original "DAuth > Proposed" was an implementation artifact** (JSON + a
   pull-based Key Exchange = one extra round-trip). With transport equalized
   (`DAuth/`), Fair-DAuth is marginally *lighter* than Proposed — matching the
   computational-cost table (DAuth 0.114 ms < Proposed 0.150 ms).
3. **LAAKA Fog↔RA registration** is now performed live and measured as a one-time
   setup cost (~0.044 J / ~12 ms on RPi 4B), instead of using hard-coded fog
   credentials — kept separate from the per-round comparison.

## Reproducibility note
Orchestrators use paramiko over SSH with the testbed's default RPi password; IPs
and credentials match the lab setup above. Adjust the constants at the top of each
`run_simulation.py` for a different testbed.
