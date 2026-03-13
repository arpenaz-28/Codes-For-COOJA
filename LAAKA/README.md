# LAAKA Scheme Implementation

Implementation of the **LAAKA** (Lightweight Anonymous Authentication and Key Agreement) scheme for Contiki-NG / COOJA simulation, based on:

> H. Ali, I. Ahmed, "LAAKA: Lightweight Anonymous Authentication and Key Agreement Scheme for Secure Fog-Driven IoT Systems," *Computers & Security*, vol. 140, 2024.

## Node Roles

| Node ID | LAAKA Role | Description |
|---------|------------|-------------|
| 1 | Gateway / Fog Server | RPL root, handles auth replies and data |
| 2–80 | Registration Authority (RA) | Registers devices, issues credentials |
| 81–100 | IoT Device (D_j) | Authenticates with fog server |

## Protocol Phases

1. **Registration (§4.2.2)** — Device computes `Ad = H(IDd || r2)` and sends to RA. RA replies with `(TIDd, TIDf, Af, Bk)`.
2. **Authentication (§4.3)** — Device sends `AuthReq = {TIDd, Td, Cd, Ed, Gd}` to GW. GW verifies and replies with `AuthRep`. Device sends `Ack = h(rf || Bk || SK)`.
3. **Data** — Device sends encrypted sensor data to GW.

## Project Structure

```
├── device-node.c           # IoT device D_j
├── as-node.c               # Registration Authority (RA)
├── gw-node.c               # Gateway / Fog Server
├── aes.c / aes.h           # AES-128-ECB encryption
├── sha256.c / sha256.h     # SHA-256 hashing
├── project-conf.h          # Network configuration
├── Makefile                # Contiki-NG build file
├── LAAKA_text.txt          # Extracted paper text for reference
├── test-sim-100.csc        # 100-node COOJA simulation config
└── test-sim-100-fixed.csc  # Fixed simulation config variant
```

## Build

```bash
make TARGET=cooja
```
