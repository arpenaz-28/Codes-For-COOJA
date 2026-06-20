# Full end-to-end hardware simulation with MIRACL Core (all 4 schemes)

Real network (TCP over LAN) **+** real cryptographic computation, with all crypto
on the measured RPi nodes routed through **MIRACL Core (NIST P-256)** via
`libmiraclshim.so`. Zhou additionally runs its **real ECC fuzzy extractor** (2
scalar multiplications), which the previous Python end-to-end sim did not.

## Architecture

- **Crypto backend:** `miracl_shim.c` -> `libmiraclshim.so` (statically links
  `core.a`; depends only on libc, so the same `.so` runs on both RPi 4B nodes).
  `miracl_crypto.py` is the ctypes wrapper. Enabled by `USE_MIRACL=1`.
- **Interop:** MIRACL SHA-256 / AES-128-ECB are byte-identical to
  hashlib / pycryptodome (verified), so MIRACL-backed device/AS interoperate
  with the **Python** gateway/RA running on the laptop (which is not measured).
- **Integration points:**
  - `Hardware/common.py` — `USE_MIRACL` branch (Proposed, LAAKA, Zhou)
  - `Hardware/DAuth/device.py` — `USE_MIRACL` branch (SHA-256 + HMAC over MIRACL)
  - `Hardware/Zhou/hw_zhou_user.py` — 2 `fe_p256()` ECC fuzzy-extractor calls
  - Each scheme's `run_*.py` orchestrator deploys the backend + sets the env.

## How to reproduce

```bash
cd Hardware/MIRACLE
python batch_e2e.py 5      # 5 runs x 4 schemes x 2 modes (MIRACL + Python), 1 session
python aggregate_e2e.py    # -> e2e_aggregate.json + charts
```
Per-run JSON is harvested to `e2e/<scheme>/<mode>/run_NN.json`.

## Result (5 runs each, same session; per-round Auth(+KeyEx/Ack); energy = wall x 3.8 W)

| Scheme   | MIRACL (J) | Python (J) | Δ      | MIRACL (s) | Python (s) |
|----------|-----------:|-----------:|:------:|-----------:|-----------:|
| Proposed | 0.1108     | 0.1119     | -1.0%  | 0.0292     | 0.0295     |
| DAuth    | 0.1555     | 0.1644     | -5.4%  | 0.0409     | 0.0433     |
| LAAKA    | 0.0967     | 0.0992     | -2.6%  | 0.0255     | 0.0261     |
| Zhou     | 0.1118     | 0.1074     | +4.1%  | 0.0294     | 0.0283     |

**Every MIRACL-vs-Python difference is within one standard deviation**
(run-to-run spread ~0.005–0.013 J, i.e. ~5–11%). The crypto library is
statistically irrelevant at the end-to-end level: the cost is **network-bound**.
Even Zhou's real ECC fuzzy extractor (~1.1 ms compute/round) is invisible against
~28 ms of network round-trip — note Zhou MIRACL is even slightly *higher* than
Python, the opposite of a compute saving, because the ECC FE was added.

Scheme ordering is set by **round-trip count**, not crypto: Proposed/LAAKA lowest,
DAuth highest (its KeyEx proxies device->GW->AS, an extra server hop).

## Files

| File | What |
|---|---|
| `miracl_shim.c`, `libmiraclshim.so` | MIRACL crypto backend (C + built aarch64 .so) |
| `miracl_crypto.py` | ctypes wrapper (sha256/aes/fe) |
| `batch_e2e.py` | runs all schemes x both modes, harvests JSON |
| `aggregate_e2e.py` | aggregates + plots |
| `e2e/` | raw per-run JSON |
| `e2e_aggregate.json` | aggregated means/std |
| `hw_e2e_miracl_vs_python.png` | grouped-bar comparison (energy + time) |
| `hw_e2e_miracl.png` | MIRACL-only, paper-style dual panel |

## Status / paper

Exploratory + archival, **not yet in the paper**. The end-to-end numbers are
network-dominated, so switching the crypto library to MIRACL does not change the
paper's conclusions; it adds methodological uniformity and Zhou-ECC fidelity. The
decision on whether to swap the paper's `fig_hw_comparison` for the MIRACL
end-to-end chart is pending review of these results.
