# Base Scheme — Reference Implementation

Reference implementation of the PUF-based IoT authentication scheme for Contiki-NG / COOJA simulation.

## Node Roles

| Node ID | Role |
|---------|------|
| 1 | Gateway (RPL root) |
| 2–80 | Authentication Servers (AS) |
| 81–100 | IoT Devices |

## Protocol Phases

1. **Enrollment** — Device registers with AS via `/test/reg` and `/test/reg1`.
2. **Authentication** — Device sends auth request to AS via `/test/auth`; session key derived.
3. **Key Exchange** — Device sends key-update to GW via `/test/keyupdate` and transmits data.

Each phase is measured in a separate timer tick and produces `ENROLL_ENERGY`, `AUTH_ENERGY`, and `KEYEX_ENERGY` output lines.

## Project Structure

```
├── device-node.c        # IoT device logic (nodes 81-100)
├── as-node.c            # Authentication server (nodes 2-80)
├── gw-node.c            # Gateway / RPL root (node 1)
├── aes.c / aes.h        # AES-128-ECB encryption
├── sha256.c / sha256.h  # SHA-256 hashing
├── project-conf.h       # Network and energest configuration
├── Makefile.unified     # Contiki-NG build file
├── Sim/                 # Server test logs and parsing script
├── Simulation/          # COOJA CSC configs, output logs, and analysis scripts
├── coap-client/ … coap-client8/  # CoAP client node variants
├── coap-gateway/        # Gateway CoAP implementation
└── coap-server/         # Server CoAP implementation
```

## Build

```bash
make -f Makefile.unified TARGET=cooja
```

## Simulation

Run headless with COOJA:

```bash
cd /opt/contiki-ng/tools/cooja && \
./gradlew run --args='--no-gui --autostart /path/to/test-sim-100.csc'
```
