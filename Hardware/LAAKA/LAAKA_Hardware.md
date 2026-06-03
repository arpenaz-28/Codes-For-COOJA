# LAAKA Scheme — Hardware Simulation Summary

## Overview

Hardware validation of the **LAAKA Scheme** (base/predecessor scheme), implemented for direct comparison with the Proposed Scheme hardware results.

Reference: *"Lightweight and Decoupled Distributed Authentication..."* (das2026comsnets)

Three real devices simulate three protocol roles:

| Role | Device | IP | Username |
|------|--------|----|----------|
| Registration Authority (RA) | Laptop (Windows 11) | 192.168.1.203 | — |
| Fog Authentication Server | Apex (RPi 3B+) | 192.168.1.132 | apex |
| IoT Device | Pi (RPi 3B+) | 192.168.1.113 | pi |

> **Mapping difference from Proposed scheme:**
> In LAAKA the RA and Fog are architecturally separate. The Laptop acts as RA (registration only) and forwards credentials to the Fog. The Fog (Apex) handles ALL authentication, ack, and data. In the Proposed scheme, the Laptop (GW) handled keyex+data directly.

---

## Files

| File | Runs on | Purpose |
|------|---------|---------|
| `Hardware/LAAKA/hw_laaka_ra.py` | Laptop | RA — listens on port 5006 (reg), forwards to Fog on port 5007 |
| `Hardware/LAAKA/hw_laaka_fog.py` | Apex | Fog Server — ports 5007 (devinfo), 5008 (auth), 5009 (ack), 5010 (data) |
| `Hardware/LAAKA/hw_laaka_device.py` | Pi | Device — enrollment + 3 auth rounds; prints results table |
| `Hardware/common.py` | Both RPis | Shared crypto: SHA-256, AES-128-ECB, TCP framing |
| `Hardware/config.py` | Both RPis | IP/port constants (read from env vars GW_IP, AS_IP) |

---

## Protocol Flow

```
Device (Pi)               RA/Laptop               Fog/Apex
    │                         │                        │
    │──── Phase 1: Registration ───────────────────────│
    │  AES(K_RA_D,[IDd|Ad|pad])=32B ────────────────▶  │
    │                         │  AES(K_RA_GW,[IDd|TIDd │
    │                         │  |Ad|Bk|pad])=64B ────▶│
    │  ◀── AES(K_RA_D,[TIDd|TIDf|Af|Bk])=80B          │
    │                         │                        │
    │──── Phase 2: Authentication (Steps 1-5) ──────────
    │  AuthReq=TIDd(20)+Td(1)+Cd(20)+Ed(20)+Gd(20)=81B│
    │  ──────────────────────────────────────────────▶  │
    │                         │  Fog verifies Cd, Gd   │
    │                         │  generates SK=H(rd||rf||Ts)
    │  ◀── AuthRep=TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20)=82B
    │  Device verifies TIDf, Cf, Gf; derives SK        │
    │                         │                        │
    │──── Phase 3: Ack (Step 9, mutual auth confirm) ───
    │  TIDd_new(20)+Ack=H(rf||Bk||SK)(20)=40B ───────▶│
    │  ◀── OK                                           │
    │                         │                        │
    │──── Phase 4: Data Communication ──────────────────
    │  TIDd_new(20)+AES(SK[0:16],data)(16)=36B ───────▶│
    │  ◀── ACK(0xAC)                                    │
```

### Key sizes
All hash values are **20 bytes** (SHA-256 truncated to 160 bits), matching the COOJA C source (`HASH_LEN = 20`).

---

## Pre-configured Constants (from C source LAAKA/gw-node.c)

```python
r1_fog     = bytes([0x11,0x22,...,0x05])           # 20 B fog identity seed
TIDf_const = bytes([0xA1,0xB2,...,0x34])           # 20 B pre-shared fog TID
K_MASTER   = bytes([0xDE,0xAD,0xBE,0xEF,...,0x98]) # 20 B master key
FOG_IDENTITY_ID = 2
Af = H20(FOG_IDENTITY_ID || r1_fog)                # fog identity hash
Bk = H20(Ad || Af || K_MASTER)                     # per-device binding key
```

---

## Port Assignments (no conflict with Proposed scheme ports 5001-5005)

| Port | Direction | Purpose |
|------|-----------|---------|
| 5006 | Device → RA | Registration request/reply |
| 5007 | RA → Fog | Device credential forwarding |
| 5008 | Device → Fog | AuthReq / AuthRep |
| 5009 | Device → Fog | Ack (mutual auth confirmation) |
| 5010 | Device → Fog | Encrypted data |

---

## Measurement Methodology

Same approach as Proposed scheme hardware:

- **Time:** `time.perf_counter()` (wall) and `time.process_time()` (CPU-only)
- **Energy:** `wall_s × 1400 mW` — RPi 3B+ single-core active load
- **Phases timed independently:** Enrollment / Auth / Ack / Data

```
Device:  t0 = perf_counter()
         ── send request ──▶ RA/Fog ── reply ──▶
         t1 = perf_counter()
         wall_ms = (t1 - t0) × 1000
```

The RA→Fog credential forwarding is **asynchronous** (device reply is sent first). Device waits **1.0 s** after enrollment before attempting authentication — sufficient for LAN forwarding to complete.

---

## How to Run

### Prerequisites
- Firewall: TCP ports 5006-5010 inbound open on Laptop (add rules if not already open)
- RPis: `pycryptodome` installed (`pip3 install pycryptodome`)
- Files deployed to `/home/pi/ANUP_Hardware_Simulation/` and `/home/apex/ANUP_Hardware_Simulation/`

### Step 1 — Laptop: start RA
```
cd "c:\ANUP\MTP\Proposing\Codes For COOJA\Hardware\LAAKA"
python hw_laaka_ra.py
```

### Step 2 — Apex: start Fog Server
```
ssh apex@192.168.1.132          # password: raspberrypi
cd ANUP_Hardware_Simulation
pkill -f hw_laaka_fog.py
export GW_IP=192.168.1.203
export AS_IP=192.168.1.132
export DEV_IP=192.168.1.113
python3 hw_laaka_fog.py
```

### Step 3 — Pi: run Device (starts automatically after 1.5 s)
```
ssh pi@192.168.1.113            # password: raspberrypi
cd ANUP_Hardware_Simulation
export GW_IP=192.168.1.203
export AS_IP=192.168.1.132
export DEV_IP=192.168.1.113
python3 hw_laaka_device.py
```

Wait for Pi terminal to print the full results table, then `Ctrl+C` on Apex for Fog summary.

**Start order: RA first → Fog second → Device last**

---

## Comparison with Proposed Scheme

| Metric | LAAKA | Proposed |
|--------|-------|----------|
| Auth message to server (B) | **81** (AuthReq) | 65 (auth payload) |
| Server reply (B) | **82** (AuthRep w/ key material) | 2 (ACK+ts_2 only) |
| Key confirmation msg (B) | 40 (Ack) | 33 (keyex req) |
| Key confirmation reply (B) | 2 (OK) | 32 (m_H) |
| Data message (B) | 36 | 48 |
| Server-side role split | RA+Fog separate | AS does enroll+auth; GW does keyex+data |
| Pseudonym rotation | None (TIDd fixed across rounds) | Yes (PID rotates every round) |

The Proposed scheme's smaller auth reply (2 B vs 82 B) is the primary reason for lower
per-round energy despite the extra pseudonym rotation hash operations.
