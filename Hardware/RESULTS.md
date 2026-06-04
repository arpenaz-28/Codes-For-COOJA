# Hardware Measurement Results
## Proposed Scheme vs LAAKA vs Zhou — Raspberry Pi 4B

**Date:** 2026-06-04
**Device under test:** Raspberry Pi 4B (Pi: 192.168.1.113, Apex: 192.168.1.132)
**Power assumption:** 3800 mW (RPi 4B single-core active)
**Energy formula:** E (J) = wall\_time (s) × 3.8 W
**Rounds measured:** 3 per scheme

---

## Setup

| Role | Device | IP |
|---|---|---|
| GW / RA | Laptop (Windows 11) | 192.168.1.201 |
| AS / Fog / SN | RPi 4B (Pi or Apex) | 192.168.1.113 / .132 |
| Device / User | RPi 4B (Pi or Apex) | 192.168.1.113 / .132 |

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
| Enrollment | 0.2286 | 0.0024 | 0.868680 |
| Round 1 Auth+KeyEx | 0.0602 | 0.0009 | 0.228760 |
| &nbsp;&nbsp;+- Auth | 0.0501 | 0.0004 | 0.190380 |
| &nbsp;&nbsp;+- KeyEx | 0.0101 | 0.0006 | 0.038380 |
| Round 1 Data | 0.0101 | 0.0004 | 0.038380 |
| **Round 1 TOTAL** | **0.0703** | **0.0013** | **0.267140** |
| Round 2 Auth+KeyEx | 0.1007 | 0.0006 | 0.382660 |
| &nbsp;&nbsp;+- Auth | 0.0895 | 0.0003 | 0.340100 |
| &nbsp;&nbsp;+- KeyEx | 0.0111 | 0.0003 | 0.042180 |
| Round 2 Data | 0.0083 | 0.0003 | 0.031540 |
| **Round 2 TOTAL** | **0.1090** | **0.0009** | **0.414200** |
| Round 3 Auth+KeyEx | 0.0649 | 0.0006 | 0.246620 |
| &nbsp;&nbsp;+- Auth | 0.0551 | 0.0003 | 0.209380 |
| &nbsp;&nbsp;+- KeyEx | 0.0097 | 0.0004 | 0.036860 |
| Round 3 Data | 0.0083 | 0.0002 | 0.031540 |
| **Round 3 TOTAL** | **0.0732** | **0.0008** | **0.278160** |
| **GRAND TOTAL** | **0.4811** | — | **1.828180** |

### Averages

| Metric | Value |
|---|---|
| Avg Auth+KeyEx per round | 0.0753 s / 0.286140 J |
| Avg Data per round | 0.0089 s / 0.033820 J |
| Avg total per round | 0.0842 s / 0.319960 J |

---

## LAAKA Scheme Results

### Phase definitions
- **Enrollment:** Single registration exchange with RA/Laptop
- **Auth+Ack:** Single outer timer covering AuthReq/AuthRep (to Fog/Apex) + Ack (to Fog/Apex) — this is one complete protocol round
- **Data:** AES-encrypted sensor data to Fog

### Raw results

| Phase | Wall (s) | CPU (s) | Energy (J) |
|---|---|---|---|
| Enrollment | 0.0147 | 0.0022 | 0.055860 |
| Round 1 Auth+Ack | 0.0955 | 0.0007 | 0.362900 |
| &nbsp;&nbsp;+- Auth | 0.0527 | 0.0004 | 0.200260 |
| &nbsp;&nbsp;+- Ack | 0.0427 | 0.0003 | 0.162260 |
| Round 1 Data | 0.0470 | 0.0004 | 0.178600 |
| **Round 1 TOTAL** | **0.1424** | **0.0011** | **0.541120** |
| Round 2 Auth+Ack | 0.0875 | 0.0008 | 0.332500 |
| &nbsp;&nbsp;+- Auth | 0.0469 | 0.0005 | 0.178220 |
| &nbsp;&nbsp;+- Ack | 0.0406 | 0.0003 | 0.154280 |
| Round 2 Data | 0.0434 | 0.0004 | 0.164920 |
| **Round 2 TOTAL** | **0.1310** | **0.0011** | **0.497800** |
| Round 3 Auth+Ack | 0.1156 | 0.0005 | 0.439280 |
| &nbsp;&nbsp;+- Auth | 0.0484 | 0.0003 | 0.183920 |
| &nbsp;&nbsp;+- Ack | 0.0672 | 0.0002 | 0.255360 |
| Round 3 Data | 0.0865 | 0.0004 | 0.328700 |
| **Round 3 TOTAL** | **0.2021** | **0.0009** | **0.767980** |
| **GRAND TOTAL** | **0.4902** | — | **1.862760** |

### Averages

| Metric | Value |
|---|---|
| Avg Auth+Ack per round | 0.0995 s / 0.378100 J |
| Avg Data per round | 0.0590 s / 0.224200 J |
| Avg total per round | 0.1585 s / 0.602300 J |

---

## Zhou Scheme Results

**Date:** 2026-06-04
**Raw output:** `Hardware/Zhou/zhou_output.txt`

### Phase definitions
- **Registration:** User reg (send [IDi|ki] → receive DIDi) + SIDn fetch — one-time setup (2 exchanges to GW)
- **Auth (M1→M4):** User builds M1, sends to GW; GW does M2/M3 with SN internally, replies M4; User verifies, extracts SK — single round-trip from User perspective
- **Data:** AES-encrypted sensor data sent to GW using session key SK

### Raw results

| Phase | Wall (s) | CPU (s) | Energy (J) |
|---|---|---|---|
| Registration | 0.1235 | 0.0849 | 0.469300 |
| Round 1 Auth | 0.0827 | 0.0143 | 0.314260 |
| Round 1 Data | 0.0247 | 0.0120 | 0.093860 |
| **Round 1 TOTAL** | **0.1075** | **0.0264** | **0.408500** |
| Round 2 Auth | 0.0383 | 0.0094 | 0.145540 |
| Round 2 Data | 0.0238 | 0.0100 | 0.090440 |
| **Round 2 TOTAL** | **0.0620** | **0.0194** | **0.235600** |
| Round 3 Auth | 0.0635 | 0.0209 | 0.241300 |
| Round 3 Data | 0.0303 | 0.0178 | 0.115140 |
| **Round 3 TOTAL** | **0.0937** | **0.0387** | **0.356060** |
| **GRAND TOTAL** | **0.3867** | — | **1.469460** |

### Averages

| Metric | Value |
|---|---|
| Avg Auth (M1->M4) per round | 0.0615 s / 0.233700 J |
| Avg Data per round | 0.0263 s / 0.099940 J |
| Avg total per round | 0.0877 s / 0.333260 J |

---

## Three-Way Comparison (Proposed vs LAAKA vs Zhou)

### Setup

| Role | Device | IP | Note |
|---|---|---|---|
| GW / RA | Laptop | 192.168.1.201 | All three schemes |
| AS / Fog / SN | RPi 4B | 192.168.1.113 / .132 | Server role |
| Device / User | RPi 4B | 192.168.1.113 / .132 | **Measurement target** |

> Note: Proposed and LAAKA measure on Pi (192.168.1.113); Zhou measures on Apex (192.168.1.132).

### Per-phase averages over 3 rounds

| Phase | Proposed | LAAKA | Zhou |
|---|---|---|---|
| Registration / Enrollment | 0.2286 s / 0.8687 J | 0.0147 s / 0.0559 J | 0.1235 s / 0.4693 J |
| **Auth + Key Establish** | **0.0753 s / 0.2861 J** | **0.0995 s / 0.3781 J** | **0.0615 s / 0.2337 J** |
| Data | 0.0089 s / 0.0338 J | 0.0590 s / 0.2242 J | 0.0263 s / 0.0999 J |
| **Total per round** | **0.0842 s / 0.3200 J** | **0.1585 s / 0.6023 J** | **0.0877 s / 0.3333 J** |
| **Grand Total** | **0.4811 s / 1.8282 J** | **0.4902 s / 1.8628 J** | **0.3867 s / 1.4695 J** |

### Key observations

1. **Auth+Key: Proposed beats LAAKA by 24.3%** — Proposed's compact auth reply eliminates most waiting time vs LAAKA's 82-byte AuthRep + Ack.

2. **Auth+Key: Zhou fastest (0.0615 s / 0.2337 J)** — Zhou's M1→M4 is one User round-trip; however Zhou is costlier in COOJA (larger 128B messages over 802.15.4).

3. **Data: Proposed 84.9% cheaper than LAAKA** — Proposed sends data to local GW (~8 ms RTT) vs LAAKA to remote Fog (~45 ms RTT).

4. **Total per round: Proposed beats LAAKA by 46.9%**, nearly ties Zhou (Proposed 0.0842 s vs Zhou 0.0877 s).

5. **Grand Total: Zhou cheapest overall** due to lighter registration. Proposed and LAAKA are within 1.9% of each other.

6. **Enrollment: Proposed heaviest (0.2286 s)** — one-time cost for PUF + accumulator + pseudonym setup at remote AS.

---

## Measurement Methodology

- **Tool:** `time.perf_counter()` (wall clock) and `time.process_time()` (CPU only)
- **What is timed:** Each phase timer covers all crypto operations (hash, AES, XOR, PUF) that prepare the message AND the full TCP round-trip for that phase
- **Power model:** 3800 mW constant active power — RPi 4B single-core Python workload (idle ~3000 mW, single-core active ~3800 mW, full load ~7500 mW). Wall time used (not CPU time) because RPi draws power during network wait
- **Software PUF:** Deterministic multiplicative hash matching the COOJA C implementation. Real PUF would be faster, so current model slightly overestimates PUF cost
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
| `Hardware/Zhou/run_simulation.py` | Orchestrates Zhou run | Laptop |
| `Hardware/Zhou/hw_zhou_user.py` | User measurements | Apex |
| `Hardware/Zhou/hw_zhou_gw.py` | GW server | Laptop |
| `Hardware/Zhou/hw_zhou_sn.py` | SN server | Pi |
