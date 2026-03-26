# Zhou et al. — Security-Enhanced Lightweight Authentication Scheme

COOJA/Contiki-NG simulation of:

> **"Security-Enhanced Lightweight and Anonymity-Preserving User Authentication Scheme for IoT-Based Healthcare"**
> Xin Zhou, Shengbao Wang, Kang Wen, Bin Hu, Xiao Tan, Qi Xie
> IEEE Internet of Things Journal, Vol. 11, No. 6, March 2024

## Protocol Overview

Three-entity IoT-based healthcare authentication protocol using hash functions, XOR, PUFs, fuzzy extractors, and secret salts.

| Entity | Description | Node IDs | Firmware |
|--------|-------------|----------|----------|
| RPL Root | Network gateway, data relay | 1 | `gw-node.c` |
| Medical Gateway | Registration, auth orchestration | 2–3 (active) | `gw-server.c` |
| Sensor Node (SNn) | PUF-equipped IoMT device | 4–23 | `sn-node.c` |
| User (Doctor) | Smart device with biometrics | 81–100 | `user-node.c` |

### Protocol Phases

1. **User Registration** — User sends `{IDi, ki}` to GW; GW generates pseudonym `DIDi`
2. **Sensor Node Registration** — Sensor sends `SNn`; GW issues challenge `Cn`; Sensor responds with PUF `Rn`
3. **Authentication & Key Exchange** — 4-message round:
   - **M1 (U→GW):** `{Ni, α, DIDi, SIDn}` — 128 bytes
   - **M2 (GW→SN):** `{SKn, β, Cn}` — 97 bytes
   - **M3 (SN→GW):** `{γ}` — 32 bytes
   - **M4 (GW→U):** `{SKi, λ}` — 128 bytes

### Hash Operations (per auth, matches paper Table VI)

| Entity | Hash Count |
|--------|-----------|
| User | 4H |
| Gateway | 7H |
| Sensor | 3H |
| **Total** | **14H** |

## Project Structure

| File | Description |
|------|-------------|
| `user-node.c` | User device: fuzzy extractor, secret salt, M1/M4 handling |
| `gw-server.c` | Medical Gateway: user/sensor reg, async M2→M3→M4 pipeline |
| `sn-node.c` | Sensor node: PUF, M2 verification, M3 generation |
| `gw-node.c` | RPL root: token + data reception |
| `aes.c/h` | AES-128-ECB |
| `sha256.c/h` | SHA-256 |
| `project-conf.h` | Node IDs, Energest, CoAP/RPL config |
| `Makefile` | Contiki-NG build (4 targets) |
| `test-sim-100.csc` | 100-node COOJA simulation |

## Build and Run (Docker)

```powershell
# Reload PATH if needed
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")

# Create container
docker run -d --name zhou-sim `
  -v "c:\ANUP\MTP\Proposing\Codes For COOJA\Zhou-Scheme:/opt/contiki-ng/examples/myproject" `
  contiker/contiki-ng tail -f /dev/null

# Build firmware
docker exec zhou-sim bash -c "cd /opt/contiki-ng/examples/myproject && make TARGET=cooja"

# Verify build (4 firmware files)
docker exec zhou-sim bash -c "ls -la /opt/contiki-ng/examples/myproject/build/cooja/*.cooja"

# Run headless simulation
docker exec zhou-sim bash -c "cd /opt/contiki-ng/tools/cooja && ./gradlew --no-watch-fs run --args='--no-gui --contiki=/opt/contiki-ng --autostart /opt/contiki-ng/examples/myproject/test-sim-100.csc'" 2>&1 | Select-Object -Last 200
```

## Security Properties

- ✓ Resistant to offline password guessing (biometrics + secret salt)
- ✓ Resistant to session key compromise (PUF + fuzzy extractor)
- ✓ Anonymity and untraceability (pseudonym rotation)
- ✓ Resistant to cloning/physical attacks (PUF)
- ✓ Resistant to impersonation attacks
- ✗ Forward security (no DH key exchange, by design)

## Energy Output

Simulation outputs `AUTH_ENERGY`, `ENROLL_ENERGY`, `KEYEX_ENERGY`, and `AUTH_ENERGY_SN` lines for performance comparison.
