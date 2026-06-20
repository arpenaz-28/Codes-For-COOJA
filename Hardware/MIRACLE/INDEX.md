# Hardware/MIRACLE — index

MIRACL Core (NIST P-256) hardware work for all four schemes. **Exploratory /
archival — not in the paper.** All crypto on the measured RPi 4B nodes is routed
through `libmiraclshim.so`; the laptop-side node (GW/RA) stays Python and
interoperates because MIRACL SHA-256/AES are byte-identical.

## Shared backend
- `miracl_shim.c` → `libmiraclshim.so` — C shim over MIRACL Core (sha256, aes-128
  ecb enc/dec, ECC P-256 fuzzy extractor). Statically links `core.a`; aarch64.
- `miracl_crypto.py` — ctypes wrapper. Enabled per process by `USE_MIRACL=1`.

## (A) Compute-only benchmark (pure computation, no network)
- `scheme_compute_bench.c`, `run_*.csv`, `plot_compute_miracl.py`,
  `compute_miracl_aggregate.json`, `hw_compute_miracl.png` — see `README.md`.
- Result: Zhou ~45× heavier (ECC FE); the other three sub-0.1 mJ of computation.

## (B) Full end-to-end sims (real TCP + real computation), per scheme
Each folder is self-contained (role scripts + common/config + MIRACL backend +
orchestrator + results). Run `python run_simulation.py <n>` inside it.

| Folder | Scheme | Measured node | Notes |
|---|---|---|---|
| `Proposed/` | Proposed (this paper) | Device=Pi | push-based KeyEx |
| `LAAKA/`    | LAAKA (2024)         | Device=Pi | Auth+Ack+Data to Fog |
| `Zhou/`     | Zhou (2024)          | User=Apex | **real ECC fuzzy extractor** |
| `DAuth/`    | **Fair-DAuth**       | Device=Pi | DAuth core on Proposed's transport |

- Cross-scheme comparison + MIRACL-vs-Python: `batch_e2e.py`, `aggregate_e2e.py`,
  `e2e/`, `e2e_aggregate.json`, `hw_e2e_miracl_vs_python.png` — see `E2E_README.md`.
- DAuth fairness study (push vs pull): `DAuth/compare_fair.py`,
  `DAuth/compare_fair_result.json` — see `DAuth/README.md`.

## Headline findings
1. **End-to-end is network-bound:** MIRACL vs Python differs by < 1 std for every
   scheme; even Zhou's real ECC FE (~1.1 ms) is invisible against ~28 ms of RTT.
2. **Scheme ordering is set by round-trips, not crypto.** The original
   "DAuth > Proposed" was a JSON + pull-KeyEx artifact; with transport equalized
   (`DAuth/`), Fair-DAuth is marginally *lighter* than Proposed — matching the
   computational-cost table (DAuth 0.114 ms < Proposed 0.150 ms).
