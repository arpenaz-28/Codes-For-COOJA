# Proposed — full end-to-end hardware sim (MIRACL Core)

Self-contained copy of the Proposed scheme's end-to-end hardware simulation with
all crypto on the measured RPi nodes routed through MIRACL Core (NIST P-256).

## Roles
| Role | Host | Script |
|---|---|---|
| Gateway (GW) | Laptop (Python) | `gw.py` |
| Auth Server (AS) | Apex 192.168.1.132 (MIRACL) | `hw_measure_as.py` |
| Device | Pi 192.168.1.113 (MIRACL, measured) | `hw_measure_device.py` |

Key delivery is **push** (AS pushes the session token to GW during Auth), so Key
Exchange is a single device→GW round-trip.

## Run
```bash
cd Hardware/MIRACLE/Proposed
python run_simulation.py 1        # -> results/run_01.json
# USE_MIRACL=0 python run_simulation.py 1   # Python-crypto baseline
```

## Files
`hw_measure_device.py`, `hw_measure_as.py`, `gw.py`, `common.py`, `config.py`,
`miracl_crypto.py`, `libmiraclshim.so`, `run_simulation.py`, `results/`.

Archive/exploratory — see `../E2E_README.md` for the cross-scheme comparison.
