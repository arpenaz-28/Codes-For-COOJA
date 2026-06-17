# Running the Li-Scheme COOJA simulation (100-node, 20% newly-joined)

This mirrors the existing network-variation study: **N=100, 1 GW + 79 AS/SN +
20 devices (IDs 81-100, 20%)**, ContikiMote (native), UDGM, 10 seeds.
COOJA runs on the **apex host** (`/home/apex/contiki-ng`), not on Windows.

## One-time setup (on apex)
```sh
# 1) sync this repo to apex (git pull on apex, or your usual sync)
cd /home/apex/contiki-ng/examples/Codes-For-COOJA/Li-Scheme

# 2) vendor real ECC (micro-ecc, secp256r1) + copy shared sha256/aes
./setup.sh
#    -> creates uECC.c, uECC.h, types.h, sha256.*, aes.*
```

## Run (registered in the shared runner as scheme "Li")
```sh
cd /home/apex/contiki-ng/examples/Codes-For-COOJA
python3 Scripts/Simulation-Runners/run_network_variation.py --scheme Li --size 100 --seeds 10
```
Results are written under:
```
Li-Scheme/Simulation results/network-variation/N100/
  csv/enroll-results.csv
  csv/auth-results.csv
  csv/keyex-results.csv      <- per-device mean (auth+key-exchange) energy/CPU
  csv/summary.csv
  logs/
```
The runner builds firmware (`TARGET=cooja`), generates the `.csc`, runs COOJA
headless via `./gradlew run --no-gui`, early-exits when all 20 devices have
logged `KEYEX_ENERGY`, and parses the markers.

> NOTE on CONTIKI path: the runner's `MAKEFILE_LI` template sets
> `CONTIKI=/home/apex/contiki-ng`. The standalone `Makefile` here uses
> `/opt/contiki-ng` — edit it only if you build manually with `make TARGET=cooja`.

## What runs on each node
| Node | Role | Per-session crypto (matches Li Table 6) |
|---|---|---|
| device-node.c | Terminal Device (initiator) | PUF + FE + 3 hashes + **6 ECC scalar mults** |
| as-node.c | Service Node (verifier) | PUF + FE + 4 hashes + **6 ECC scalar mults** |
| gw-node.c | Management Server | registration only (issues Xj, Ppub) |

## Modeling notes (read before citing the numbers)
- **ECC scalar multiplications are REAL** (micro-ecc secp256r1). Each side
  performs the same *count* as Li et al. (6), so the measured COOJA CPU/energy
  reflects Li's true dominant cost.
- micro-ecc's public API gives `k*G` (`uECC_compute_public_key`) and `k*P`
  (`uECC_shared_secret`). **Point additions** in Li's verification equation
  (`T_ea` ≈ 0.012 ms, ~200× cheaper than a mult) are folded into hash binding —
  negligible for energy, noted for honesty.
- **PUF** = per-node keyed-AES map; **fuzzy extractor** = hash secure sketch
  (Gen/Rep). Both cheap, matching Li's accounting where ECC dominates.
- **SN session state** is a single slot bridging M1→M3. Device starts are
  staggered (`5+node_id` s) and requests are CoAP-blocking, so a device's
  M1 and M3 are back-to-back — safe for the cost measurement.
- Mote type is `ContikiMoteType` (native x86), so ECC fits and runs fast;
  Energest still tracks the CPU time spent in the real ECC code.

## Expected outcome
Per-device auth+key-exchange energy/CPU should land **far above** Proposed/
DAuth/LAAKA/Zhou (the 6 ECC mults dominate), consistent with the theoretical
~28-30 ms vs Proposed's ~0.67 ms. If a build error mentions `uECC`, re-run
`./setup.sh`; if it mentions a missing `sha256.h`/`aes.h`, the copy step failed
(check `../LAAKA`).
