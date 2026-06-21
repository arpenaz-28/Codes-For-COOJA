# Proposed Scheme — Hardware Simulation Summary

## Overview

Hardware validation of the **Proposed Scheme (Revised Anonymity)** from the paper:
*"Lightweight, Anonymous, and Decoupled Distributed Authentication for Multihop IoT Networks"*

Three real devices are used to simulate the three protocol roles:

| Role | Device | IP | Username |
|------|--------|----|----------|
| Gateway (GW) | Laptop (Windows 11) | 192.168.1.203 | — |
| Authentication Server (AS) | Apex (RPi 3B+) | 192.168.1.132 | apex |
| IoT Device | Pi (RPi 3B+) | 192.168.1.113 | pi |

---

## Files Deployed

All files live in `Hardware/` (laptop) and `/home/<user>/ANUP_Hardware_Simulation/` (RPis).

| File | Runs on | Purpose |
|------|---------|---------|
| `Hardware/Proposed/gw.py` | Laptop | Gateway — listens on ports 5001 (token), 5002 (keyex), 5003 (data) |
| `Hardware/Proposed/hw_measure_as.py` | Apex | AS — listens on 5004 (enroll), 5005 (auth); logs per-request energy |
| `Hardware/Proposed/hw_measure_device.py` | Pi | Device — runs Enrollment + 3 Auth rounds; prints full results table |
| `Hardware/common.py` | Both RPis | Shared crypto: SHA-256, AES-128-ECB, TCP framing, software PUF |
| `Hardware/config.py` | Both RPis | IP/port constants (read from env vars GW_IP, AS_IP, DEV_IP) |

---

## Protocol Flow (4 Phases)

```
Device (Pi)                AS (Apex)               GW (Laptop)
    │                          │                        │
    │──── Phase 1: Enrollment ─────────────────────────│
    │  REG0: AES(K_AS_D, [id_d]) ──────────────▶       │
    │  ◀── AES(K_AS_D, [c_d | m_curr])                 │
    │  REG1: AES(K_AS_D, [id_d|Y_dH|R_d|c_as_d]) ───▶ │
    │  ◀── ACK  (AS stores PID=H(id_d||m_curr))        │
    │                          │                        │
    │──── Phase 2: Authentication ──────────────────────│
    │  [PID_curr | y_asd | ts_1] ──────────────▶       │
    │     AS verifies membership (T_acc & Y_dH)        │
    │     AS generates m_new, PID_new = H(id_d||m_new) │
    │     AS rotates: PID_old←PID_curr, PID_curr←PID_new
    │  ◀── [ACK | m_H | ts_2]                          │
    │     ──── TOKEN [PID_new | K_GW_D] ──────────────▶│
    │                          │                        │
    │  Device derives m_new, rotates PID ◄── HERE      │
    │                          │                        │
    │──── Phase 3: Key Exchange ────────────────────────│
    │  [PID_new | AES(K_GW_D, nonce)] ────────────────▶│
    │  ◀── AES(K_GW_D, nonce+1) ──────────────────────│
    │                          │                        │
    │──── Phase 4: Data Communication ──────────────────│
    │  [PID_new | AES(K_GW_D, sensor_val)] ───────────▶│
    │  ◀── ACK(0xAC) ──────────────────────────────────│
```

---

## Software PUF Implementation

**No external library (e.g. pypuf) is used.** The PUF is a deterministic multiplicative hash matching the C source in the COOJA simulation:

```python
def puf_response(node_id: int, challenge: int) -> int:
    s = (node_id * 2246822519) ^ (challenge * 2654435761)
    s &= 0xFFFFFFFF
    s = ((s >> 16) ^ s) * 0x45d9f3b & 0xFFFFFFFF
    s = ((s >> 16) ^ s) * 0x45d9f3b & 0xFFFFFFFF
    s ^= (s >> 16)
    return s & 0xFF
```

Same (node_id, challenge) always returns the same byte. AS and Device both compute the same R_d independently without storing it — matching the PUF property of no long-term key storage.

---

## Measurement Methodology

### Time
- `time.perf_counter()` — wall-clock time (includes network round-trip)
- `time.process_time()` — CPU-only time (computation excluding network wait)
- Each phase (Auth, KeyEx, Data) is timed independently with start/stop brackets

```
Device:   t0 = perf_counter()
          ── send message ──▶ AS/GW ── reply ──▶
          t1 = perf_counter()
          wall_ms = (t1 - t0) × 1000
```

### Energy
No external power meter — estimated from:

```
Energy (mJ) = Wall_time (s) × Power (mW)
```

**Power assumption: 1400 mW** — RPi 3B+ single-core Python workload (conservative estimate between idle ~1000 mW and peak ~2500 mW).

Wall time is used (not CPU time) because the RPi draws power during network wait too — consistent with COOJA's Energest philosophy which tracks energy across all node states (CPU, LPM, TX, RX).

---

## Experimental Results

### Device-side (Pi at 192.168.1.113)

| Phase | Wall (ms) | CPU (ms) | Energy (mJ) |
|-------|-----------|----------|-------------|
| Enrollment | 139.27 | 2.79 | 194.97 |
| Round 1 — Auth | 50.29 | 0.24 | 70.40 |
| Round 1 — KeyEx | 11.11 | 0.18 | 15.56 |
| Round 1 — Data | 9.04 | 0.13 | 12.66 |
| **Round 1 — Total** | **70.44** | **0.55** | **98.62** |
| Round 2 — Auth | 55.18 | 0.19 | 77.26 |
| Round 2 — KeyEx | 10.68 | 0.16 | 14.95 |
| Round 2 — Data | 9.67 | 0.13 | 13.53 |
| **Round 2 — Total** | **75.52** | **0.49** | **105.73** |
| Round 3 — Auth | 43.40 | 0.20 | 60.77 |
| Round 3 — KeyEx | 10.38 | 0.17 | 14.53 |
| Round 3 — Data | 10.95 | 0.13 | 15.33 |
| **Round 3 — Total** | **64.73** | **0.50** | **90.62** |
| **Grand Total** | **349.96** | — | **489.95** |

**Average per auth round (Auth + KeyEx + Data): 70.23 ms / 98.33 mJ**

### PID Rotation Trace (confirms anonymity mechanism working)

```
Enrollment  →  PID = e86cb657...   (initial pseudonym)
Round 1     →  PID = bf504972...   (rotated after auth reply)
Round 2     →  PID = f5795f76...   (rotated after auth reply)
Round 3     →  PID = 685ffa20...   (rotated after auth reply)
```

Real identity `ID_D` is never transmitted. GW only ever sees PID values.

---

## PID Rotation — When Exactly

PID rotates **immediately after the AS auth reply is received**, before KeyEx and Data:

```
Auth REQ sent with PID_curr
        ↓
AS reply received [ACK | m_H | ts_2]
        ↓
Device derives m_new = m_H XOR mh_mask
Device computes PID_new = H(ID_D || m_new)   ◄── ROTATION POINT
        ↓
KeyEx sent with PID_new
Data  sent with PID_new
        ↓
Next round Auth sent with PID_new (now current)
```

**In this simulation:** 1 Auth + 1 KeyEx + 1 Data per round (tight loop for measurement).
**In real deployment:** 1 Auth + 1 KeyEx + many Data packets per session, re-auth on session expiry.

---

## How to Re-run

### Prerequisites
- Both RPis: Python 3.11+, pycryptodome (`pip3 install pycryptodome`)
- Files already in `/home/pi/ANUP_Hardware_Simulation/` and `/home/apex/ANUP_Hardware_Simulation/`
- Windows Firewall rule open for TCP 5001-5003 inbound (rule name: `HW_SIM_GW_5001_5003`)

### Step 1 — Terminal 1: GW on Laptop
```
cd "c:\ANUP\MTP\Proposing\Codes For COOJA\Hardware\Proposed"
python gw.py
```

### Step 2 — Terminal 2: AS on Apex
```
ssh apex@192.168.1.132          # password: raspberrypi
cd ANUP_Hardware_Simulation
pkill -f hw_measure_as.py       # kill any leftover instance
export GW_IP=192.168.1.203
export AS_IP=192.168.1.132
export DEV_IP=192.168.1.113
python3 hw_measure_as.py
```

### Step 3 — Terminal 3: Device on Pi
```
ssh pi@192.168.1.113            # password: raspberrypi
cd ANUP_Hardware_Simulation
export GW_IP=192.168.1.203
export AS_IP=192.168.1.132
export DEV_IP=192.168.1.113
python3 hw_measure_device.py
```

Wait for Terminal 3 to finish, then press `Ctrl+C` in Terminal 2 to get AS-side summary.

### Order: GW first → AS second → Device last (device script waits 1.5 s automatically)

---

## Key Observations

1. **Auth dominates latency** (~50–55 ms of ~70 ms per round) — network round-trip to AS on a different device is the bottleneck, not computation (CPU time is only ~0.2 ms).
2. **KeyEx + Data are fast** (~10 ms each) — GW is on same LAN, low round-trip.
3. **CPU time << Wall time** — confirms the RPi is mostly waiting for network, not computing. Protocol is lightweight as claimed.
4. **PID rotation verified** — pseudonym changes every round, GW never sees the same PID twice after re-auth, real `ID_D` never on wire.
5. **Desync recovery** is implemented in `hw_measure_as.py` — dual-state `(PID_curr, PID_old)` lookup. Can be tested using the original `device.py` (4-round desync demo).
