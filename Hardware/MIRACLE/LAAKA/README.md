# LAAKA — full end-to-end hardware sim (MIRACL Core)

Self-contained copy of the LAAKA scheme (Ali & Ahmed, Computers & Security 2024)
end-to-end hardware simulation, crypto on the measured RPi nodes via MIRACL Core.

## Roles
| Role | Host | Script |
|---|---|---|
| Registration Authority (RA) | Laptop (Python) | `hw_laaka_ra.py` |
| Fog | Apex 192.168.1.132 (MIRACL) | `hw_laaka_fog.py` |
| Device | Pi 192.168.1.113 (MIRACL, measured) | `hw_laaka_device.py` |

Per round: Auth + Ack (key establishment) + Data, all device→Fog.

## Registration phase (now follows the scheme strictly — §4.2)

Both LAAKA registration sub-phases are performed **live and measured**, instead of
hard-coding the fog's credentials:

- **§4.2.1 Fog registration** (one-time, at fog startup, measured): the fog picks
  `ID_f` and a secret random `r1`, computes `Af = h(ID_f‖r1)`, sends `Af` to the RA
  over a secure channel (`AES(K_RA_GW,…)`, port 5016), and receives + stores the
  RA-issued `TIDf`. Cost is saved to `fogreg_hw_run.json` and reported separately
  (e.g. ~0.044 J / ~12 ms wall on RPi 4B).
- **§4.2.2 Device registration**: the RA computes `Bk = h(Ad‖Af‖K)` from the
  **registered** fog's `Af` and sends `(TIDd, TIDf, Af, Bk)` to the device — which
  now learns `Af`/`TIDf` from the RA (it never knows `r1`).

This is a one-time setup cost (amortised over all sessions); it does **not** affect
the per-round Auth/Ack/Data numbers. The other schemes' analogous infra
provisioning (e.g. AS↔GW keys) remains pre-shared, as before.

## Run
```bash
cd Hardware/MIRACLE/LAAKA
python run_simulation.py 1        # -> results/run_01.json
# USE_MIRACL=0 python run_simulation.py 1   # Python-crypto baseline
```

## Files
`hw_laaka_device.py`, `hw_laaka_fog.py`, `hw_laaka_ra.py`, `common.py`,
`config.py`, `miracl_crypto.py`, `libmiraclshim.so`, `run_simulation.py`, `results/`.

Archive/exploratory — see `../E2E_README.md` for the cross-scheme comparison.
