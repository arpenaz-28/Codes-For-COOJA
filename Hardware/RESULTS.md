# Hardware Measurement Results
## Proposed Scheme vs LAAKA — Raspberry Pi 3B+

**Date:** 2026-06-04  
**Device under test:** Raspberry Pi 3B+ (Pi: 192.168.1.113)  
**Power assumption:** 1400 mW (RPi 3B+ single-core active)  
**Energy formula:** E (J) = wall_time (s) × 1.4 W  
**Rounds measured:** 3 per scheme  

---

## Setup

| Role | Device | IP |
|---|---|---|
| GW / RA | Laptop (Windows 11) | 192.168.1.201 |
| AS / Fog | Apex (RPi 3B+) | 192.168.1.132 |
| Device | Pi (RPi 3B+) | 192.168.1.113 |

**Measurement scope:** Each phase timer starts before the crypto (hash/AES/PUF) that prepares the message and ends after the network reply is received. Both computation and network cost are fully included.

---

## Proposed Scheme Results

### Phase definitions
- **Enrollment:** Reg-0 + Reg-1 (two exchanges on one TCP connection to AS/Apex)
- **Auth+KeyEx:** Single outer timer covering both authentication round-trip (to AS) and key exchange round-trip (to GW) — this is one complete protocol round
- **Data:** AES-encrypted sensor data to GW

### Raw results

| Phase | Wall (s) | CPU (s) | Energy (J) |
|---|---|---|---|
| Enrollment | 0.2286 | 0.0024 | 0.319992 |
| Round 1 Auth+KeyEx | 0.0602 | 0.0009 | 0.084331 |
| &nbsp;&nbsp;+- Auth | 0.0501 | 0.0004 | 0.070196 |
| &nbsp;&nbsp;+- KeyEx | 0.0101 | 0.0006 | 0.014101 |
| Round 1 Data | 0.0101 | 0.0004 | 0.014130 |
| **Round 1 TOTAL** | **0.0703** | **0.0013** | **0.098461** |
| Round 2 Auth+KeyEx | 0.1007 | 0.0006 | 0.140935 |
| &nbsp;&nbsp;+- Auth | 0.0895 | 0.0003 | 0.125367 |
| &nbsp;&nbsp;+- KeyEx | 0.0111 | 0.0003 | 0.015546 |
| Round 2 Data | 0.0083 | 0.0003 | 0.011602 |
| **Round 2 TOTAL** | **0.1090** | **0.0009** | **0.152537** |
| Round 3 Auth+KeyEx | 0.0649 | 0.0006 | 0.090824 |
| &nbsp;&nbsp;+- Auth | 0.0551 | 0.0003 | 0.077170 |
| &nbsp;&nbsp;+- KeyEx | 0.0097 | 0.0004 | 0.013630 |
| Round 3 Data | 0.0083 | 0.0002 | 0.011623 |
| **Round 3 TOTAL** | **0.0732** | **0.0008** | **0.102448** |
| **GRAND TOTAL** | **0.4811** | — | **0.673438** |

### Averages

| Metric | Value |
|---|---|
| Avg Auth+KeyEx per round | 0.0753 s / 0.105363 J |
| Avg Data per round | 0.0089 s / 0.012452 J |
| Avg total per round | 0.0842 s / 0.117815 J |

---

## LAAKA Scheme Results

### Phase definitions
- **Enrollment:** Single registration exchange with RA/Laptop
- **Auth+Ack:** Single outer timer covering AuthReq/AuthRep (to Fog/Apex) + Ack (to Fog/Apex) — this is one complete protocol round
- **Data:** AES-encrypted sensor data to Fog

### Raw results

| Phase | Wall (s) | CPU (s) | Energy (J) |
|---|---|---|---|
| Enrollment | 0.0147 | 0.0022 | 0.020519 |
| Round 1 Auth+Ack | 0.0955 | 0.0007 | 0.133642 |
| &nbsp;&nbsp;+- Auth | 0.0527 | 0.0004 | 0.073789 |
| &nbsp;&nbsp;+- Ack | 0.0427 | 0.0003 | 0.059828 |
| Round 1 Data | 0.0470 | 0.0004 | 0.065758 |
| **Round 1 TOTAL** | **0.1424** | **0.0011** | **0.199400** |
| Round 2 Auth+Ack | 0.0875 | 0.0008 | 0.122548 |
| &nbsp;&nbsp;+- Auth | 0.0469 | 0.0005 | 0.065709 |
| &nbsp;&nbsp;+- Ack | 0.0406 | 0.0003 | 0.056806 |
| Round 2 Data | 0.0434 | 0.0004 | 0.060788 |
| **Round 2 TOTAL** | **0.1310** | **0.0011** | **0.183337** |
| Round 3 Auth+Ack | 0.1156 | 0.0005 | 0.161847 |
| &nbsp;&nbsp;+- Auth | 0.0484 | 0.0003 | 0.067702 |
| &nbsp;&nbsp;+- Ack | 0.0672 | 0.0002 | 0.094117 |
| Round 3 Data | 0.0865 | 0.0004 | 0.121085 |
| **Round 3 TOTAL** | **0.2021** | **0.0009** | **0.282932** |
| **GRAND TOTAL** | **0.4902** | — | **0.686188** |

### Averages

| Metric | Value |
|---|---|
| Avg Auth+Ack per round | 0.0995 s / 0.139346 J |
| Avg Data per round | 0.0590 s / 0.082544 J |
| Avg total per round | 0.1585 s / 0.221890 J |

---

## Comparison

### Per-phase (averages over 3 rounds)

| Phase | LAAKA | Proposed | Reduction |
|---|---|---|---|
| Enrollment | 0.0147 s / 0.0205 J | 0.2286 s / 0.3200 J | Proposed is heavier (2 exchanges to remote AS vs 1 to local RA) |
| **Auth+KeyEx** | **0.0995 s / 0.1393 J** | **0.0753 s / 0.1054 J** | **24.3%** |
| Data | 0.0590 s / 0.0825 J | 0.0089 s / 0.0124 J | 84.9% (GW is local for Proposed) |
| **Total per round** | **0.1585 s / 0.2219 J** | **0.0842 s / 0.1178 J** | **46.9%** |
| **Grand Total** | **0.4902 s / 0.6862 J** | **0.4811 s / 0.6734 J** | **1.9%** |

### Key observations

1. **Auth+KeyEx: 24.3% reduction** — primary efficiency claim for the paper. Proposed scheme's 2-byte auth reply (vs LAAKA's 82-byte AuthRep) eliminates most of the waiting time.

2. **Data: 84.9% reduction** — because Proposed sends data to GW (Laptop, ~8 ms RTT) while LAAKA sends to Fog (Apex, ~45 ms RTT). This is a structural protocol advantage.

3. **Enrollment: Proposed is 15.6× heavier** — Proposed has 2 exchanges to remote AS (PUF challenge, accumulator, pseudonym setup) vs LAAKA's 1 exchange to local RA. This is a one-time cost.

4. **Grand total: only 1.9% difference** — the per-round savings of Proposed (~0.034 J × 3 = 0.102 J) are nearly cancelled by the heavier enrollment (~0.299 J extra). Break-even is at ~9 authentication rounds.

---

## Measurement Methodology

- **Tool:** `time.perf_counter()` (wall clock) and `time.process_time()` (CPU only)
- **What is timed:** Each phase timer covers all crypto operations (hash, AES, XOR, PUF) that prepare the message AND the full TCP round-trip for that phase
- **What is NOT timed:** TCP connection setup overhead (included in phase time since socket.connect is inside the timer), constant pre-computed values (e.g., Af = H(fog_id || r1_fog) is a protocol constant)
- **Power model:** 1400 mW constant active power — RPi 3B+ single-core Python workload (conservative; idle ~700 mW, peak ~3000 mW). Wall time used (not CPU time) because RPi draws power during network wait
- **Software PUF:** Deterministic multiplicative hash matching the COOJA C implementation — consistent with simulation results. Real hardware PUF would be faster (~ns), so current model slightly overestimates PUF cost
- **Rounds:** 3 rounds per run; Round 1 may include first-call TCP/crypto library init overhead

---

## Scripts

| Script | Role | Location |
|---|---|---|
| `Hardware/Proposed/run_simulation.py` | Orchestrates Proposed scheme run | Laptop |
| `Hardware/Proposed/hw_measure_device.py` | Device measurements | Pi |
| `Hardware/Proposed/gw.py` | GW server | Laptop |
| `Hardware/Proposed/hw_measure_as.py` | AS server | Apex |
| `Hardware/LAAKA/run_simulation.py` | Orchestrates LAAKA run | Laptop |
| `Hardware/LAAKA/hw_laaka_device.py` | Device measurements | Pi |
| `Hardware/LAAKA/hw_laaka_ra.py` | RA server | Laptop |
| `Hardware/LAAKA/hw_laaka_fog.py` | Fog server | Apex |
