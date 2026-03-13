# Desynchronization Recovery — Anonymity-Extended Scheme

Demonstrates the **dual-state desynchronization recovery** mechanism of the Anonymity-Extended Base Scheme.

## How It Works

The AS maintains both current and old copies of the device PID and session seed (`PID_curr` / `PID_old`, `m_curr` / `m_old`). If a reply is lost and the device falls out of sync, the AS can still match the device using its old state and re-synchronize.

### Simulation Rounds

| Round | Behaviour |
|-------|-----------|
| 1 | Normal authentication — both sides in sync |
| 2 | Auth sent, AS processes and rotates state, but device **drops** the reply → AS is ahead, device is stuck on old state (**desync**) |
| 3 | Device retries with old PID/mask → AS matches `PID_old` → recovery succeeds → both sides re-synced |
| 4 | Normal authentication with new synced state — confirms recovery worked |

## Project Structure

```
├── device-node.c        # Desync demonstration device node
├── as-node.c            # AS with dual-state storage
├── gw-node.c            # Gateway / RPL root
├── aes.c / aes.h        # AES-128-ECB encryption
├── sha256.c / sha256.h  # SHA-256 hashing
├── project-conf.h       # Network configuration
├── Makefile             # Contiki-NG build file
└── desync-sim.csc       # COOJA simulation config for desync demo
```

## Build

```bash
make TARGET=cooja
```
