# Zhou — full end-to-end hardware sim (MIRACL Core, real ECC fuzzy extractor)

Self-contained copy of the Zhou et al. scheme (IEEE IoT Journal 2024) end-to-end
hardware simulation. Crypto on the measured RPi nodes via MIRACL Core, and the
**biometric fuzzy extractor runs as a real ECC P-256 scalar multiplication**
(2 FE ops: one at registration, one re-generated each auth round) — the previous
Python sim did not perform ECC at all.

## Roles
| Role | Host | Script |
|---|---|---|
| Gateway (GW) | Laptop (Python) | `hw_zhou_gw.py` |
| Sensor Node (SN) | Pi 192.168.1.113 (MIRACL) | `hw_zhou_sn.py` |
| User | Apex 192.168.1.132 (MIRACL, measured) | `hw_zhou_user.py` |

Per round: Auth M1→M4 (User↔GW, with internal GW↔SN M2/M3) + Data.

## Run
```bash
# Output contains arrows; force UTF-8 on Windows consoles:
cd Hardware/MIRACLE/Zhou
PYTHONUTF8=1 python run_simulation.py 1     # -> results/run_01.json
# USE_MIRACL=0 PYTHONUTF8=1 python run_simulation.py 1   # Python baseline (no real ECC)
```

## Files
`hw_zhou_user.py`, `hw_zhou_sn.py`, `hw_zhou_gw.py`, `common.py`, `config.py`,
`miracl_crypto.py`, `libmiraclshim.so`, `run_simulation.py`, `results/`.

Note: the ECC FE makes Zhou's per-round CPU ~2 ms (vs ~0.6 ms for the others),
but end-to-end this is still dwarfed by ~28 ms of network round-trip.

Archive/exploratory — see `../E2E_README.md` for the cross-scheme comparison.
