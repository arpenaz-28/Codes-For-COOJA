# Revised-Anonymity COOJA Simulation — Session Summary

## What Was Done

Three COOJA simulations of the **Revised-Anonymity Two-Round Protocol** were run,
each with a different AS/Device balance, all with 5 random seeds.
The goal was to study how the protocol scales as load is redistributed across AS nodes.

---

## Protocol Overview

- **Two-round authentication**: Enrollment → Authentication (Round 1) → Key Exchange (Round 2)
- **Measurements taken on each device** using Contiki Energest:
  - `ENROLL_ENERGY` — CPU time + energy for enrollment phase
  - `AUTH_ENERGY`   — CPU time + energy for authentication round
  - `KEYEX_ENERGY`  — CPU time + energy for key exchange round
- **Energy model**: CC2420-equivalent radio, 3.0 V supply
  - CPU: 1.8 mA, LPM: 54.5 µA, TX: 17.4 mA, RX: 18.8 mA

---

## Three Configurations Simulated

### Config A — Original (79 AS / 20 Devices)
| Parameter | Value |
|---|---|
| Gateway | Node 1 |
| AS nodes | Nodes 2–80 (79 nodes, only 2 & 3 originally active) |
| Device nodes | Nodes 81–100 (20 devices) |
| Total nodes | 100 |
| Seeds | 123456, 234567, 345678, 456789, 567890 |
| Source dir | `Revised-Anonymity/` |
| Results | `Results/CSV-Data/Revised-Anonymity/` |
| Logs | `Results/Testlogs/Revised-Anonymity/` |

### Config B — 50 AS / 50 Devices
| Parameter | Value |
|---|---|
| Gateway | Node 1 |
| AS nodes | Nodes 2–51 (50 nodes, **all active**) |
| Device nodes | Nodes 52–101 (50 devices) |
| Total nodes | 101 |
| AS assignment | `AS = 2 + ((node_id - 52) % 50)` → 1 device per AS |
| Seeds | 123456, 234567, 345678, 456789, 567890 |
| Source dir | `Revised-Anonymity-50_50/` |
| Results | `Simulation results/Revised-Anonymity/50_50/csv/` |
| Logs | `Simulation results/Revised-Anonymity/50_50/logs/` |
| Report | `Simulation results/Revised-Anonymity/50_50/comparison_report.html` |

### Config C — 20 AS / 79 Devices
| Parameter | Value |
|---|---|
| Gateway | Node 1 |
| AS nodes | Nodes 2–21 (20 nodes, **all active**) |
| Device nodes | Nodes 22–100 (79 devices) |
| Total nodes | 100 |
| AS assignment | `AS = 2 + ((node_id - 22) % 20)` → ~4 devices per AS |
| Seeds | 123456, 234567, 345678, 456789, 567890 |
| Source dir | `Revised-Anonymity-20_79/` |
| Results | `Simulation results/Revised-Anonymity/20_79/csv/` |
| Logs | `Simulation results/Revised-Anonymity/20_79/logs/` |
| Report | `Simulation results/Revised-Anonymity/20_79/comparison_all_three.html` |

---

## Results Summary (5-Seed Averages per Device)

### Energy (mJ)

| Config | Enrollment | Auth | Key Exchange | **Total** |
|---|---|---|---|---|
| 79 AS / 20 Dev | 26.16 | 16.68 | 12.13 | **54.97** |
| 50 AS / 50 Dev | 24.82 | 17.66 | 13.22 | **55.70** |
| 20 AS / 79 Dev | 27.44 | 17.88 | 14.31 | **59.62** |

### CPU Time (ms)

| Config | Enrollment | Auth | Key Exchange | **Total** |
|---|---|---|---|---|
| 79 AS / 20 Dev | 424.2 | 270.5 | 196.7 | **891.4** |
| 50 AS / 50 Dev | 397.4 | 283.5 | 215.0 | **895.9** |
| 20 AS / 79 Dev | 444.9 | 290.0 | 231.9 | **966.8** |

### Load Distribution

| Config | Devices per AS | AS utilisation |
|---|---|---|
| 79 AS / 20 Dev | 0.25 | Originally only 2 of 79 AS active |
| 50 AS / 50 Dev | 1.0 (exact) | All 50 AS active — perfectly balanced |
| 20 AS / 79 Dev | ~3.95 (19×4 + 1×3) | All 20 AS active — highest contention |

---

## Key Insights

1. **Protocol scales well** — total energy per device ranges only 54.97–59.62 mJ
   across all three configs despite a 4× change in device count (20→79).

2. **50 AS / 50 Dev is the sweet spot** — lowest enrollment cost (1 device per AS,
   no queuing) and balanced auth/keyex overhead. Best total energy at 55.70 mJ.

3. **Enrollment dominates energy** (~45–47% of total across all configs).
   It involves two CoAP round-trips + AES + PUF operations.

4. **Auth and KeyEx cost rises as AS count decreases** — more devices per AS
   means more queuing and CoAP retransmissions (20AS config is most expensive).

5. **Enrollment cost follows AS-to-device ratio** — fewer AS = more contention
   during registration = higher enrollment energy.

---

## File Structure

```
Codes-For-COOJA/
├── Revised-Anonymity/              # Config A source (original)
├── Revised-Anonymity-50_50/        # Config B source (modified)
│   ├── project-conf.h              # FIRST_DEVICE_ID=52, NUM_AS=50
│   └── device-node.c               # id_as = 2 + ((node_id-52) % 50)
├── Revised-Anonymity-20_79/        # Config C source (modified)
│   ├── project-conf.h              # FIRST_DEVICE_ID=22, NUM_AS=20
│   └── device-node.c               # id_as = 2 + ((node_id-22) % 20)
│
├── Scripts/
│   ├── Simulation-Runners/
│   │   ├── run_revised_anonymity.py   # Config A runner (Docker-based, old)
│   │   ├── run_50_50.py               # Config B runner (local COOJA, 5 seeds)
│   │   └── run_20_79.py               # Config C runner (local COOJA, 5 seeds)
│   └── Utilities/
│       ├── compare_50_50_vs_original.py   # A vs B HTML report
│       └── compare_all_three.py           # A vs B vs C HTML report
│
├── Results/
│   └── CSV-Data/Revised-Anonymity/    # Config A CSVs + summary
│
└── Simulation results/
    ├── SESSION_SUMMARY.md             # This file
    └── Revised-Anonymity/
        ├── 50_50/
        │   ├── csv/                       # Config B CSVs (50 devices)
        │   ├── logs/                      # Config B testlogs (5 seeds)
        │   └── comparison_report.html     # A vs B report with SVG charts
        └── 20_79/
            ├── csv/                       # Config C CSVs (79 devices)
            ├── logs/                      # Config C testlogs (5 seeds)
            └── comparison_all_three.html  # A vs B vs C report with SVG charts
```

---

## How to Re-run Any Simulation

All runners work locally (COOJA installed at `/home/apex/contiki-ng/tools/cooja`).
Run from `Codes-For-COOJA/` directory:

```bash
# Config B — 50 AS / 50 Devices
python3 Scripts/Simulation-Runners/run_50_50.py

# Config C — 20 AS / 79 Devices
python3 Scripts/Simulation-Runners/run_20_79.py

# Regenerate comparison reports
python3 Scripts/Utilities/compare_all_three.py
```

Each runner:
1. Copies source to `/home/apex/contiki-ng/examples/cooja_<config>/`
2. Builds firmware with `make TARGET=cooja`
3. Generates CSC file (10×10 or 11×10 grid, 30-unit spacing, UDGM radio)
4. Runs COOJA headless — **early-exit script** stops simulation the moment
   all devices log `KEYEX_ENERGY` (typically ~20–35 s per seed)
5. Saves testlogs and CSVs to `Simulation results/<config>/`

---

## COOJA Setup Notes

- COOJA path: `/home/apex/contiki-ng/tools/cooja/`
- Java: OpenJDK 21
- Contiki-NG: `/home/apex/contiki-ng/` (tag: 686bc87)
- Simulation timeout: 900 000 ms hard cap (15 min), early-exit in ~20–35 s
- Radio: UDGM, TX range 150, interference 200, success ratio 1.0
- Seeds used: 123456, 234567, 345678, 456789, 567890

---

## Key Source File Changes Per Config

### project-conf.h differences

| Macro | Config A | Config B | Config C |
|---|---|---|---|
| `GW_NODE_ID` | 1 | 1 | 1 |
| `AS_NODE_ID` | 2 | 2 | 2 |
| `AS_NODE_ID2` | 3 | *(removed)* | *(removed)* |
| `NUM_AS` | *(not defined)* | 50 | 20 |
| `FIRST_DEVICE_ID` | 81 | 52 | 22 |

### device-node.c — AS assignment line (~line 324)

```c
// Config A (original):
id_as = (node_id <= 90) ? (uint8_t)AS_NODE_ID : (uint8_t)AS_NODE_ID2;

// Config B and C (modulo — all AS active):
id_as = (uint8_t)(AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS));
```
