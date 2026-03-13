# Base Scheme — Aligned Measurement Variant

Modified version of the Base Scheme where Authentication, Key Exchange, and Data transmission all occur in **one timer tick**, matching the measurement methodology used by the Proposed and LAAKA schemes.

This variant exists solely for fair energy and CPU time comparisons across schemes.

## Differences from Base-Scheme

| Aspect | Base-Scheme | Base-Scheme-Aligned |
|--------|-------------|---------------------|
| Auth + KeyEx + Data | Separate timer ticks | Single timer tick |
| Energy labels | `AUTH_ENERGY`, `KEYEX_ENERGY` (separate) | `AUTH_ONLY_ENERGY`, `PROTOCOL_ENERGY`, `AUTH_TOTAL_ENERGY` |
| Purpose | Full protocol evaluation | Fair cross-scheme comparison |

## Project Structure

```
├── device-node.c        # Modified device: all phases in one tick
├── as-node.c            # Authentication server (same as Base-Scheme)
├── gw-node.c            # Gateway (same as Base-Scheme)
├── aes.c / aes.h        # AES-128-ECB encryption
├── sha256.c / sha256.h  # SHA-256 hashing
├── project-conf.h       # Network configuration
├── Makefile.unified     # Contiki-NG build file
└── test-sim-100.csc     # 100-node COOJA simulation config
```

## Build

```bash
make -f Makefile.unified TARGET=cooja
```
