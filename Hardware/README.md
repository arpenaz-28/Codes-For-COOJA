# Hardware Deployment: Extended Scheme (Laptop GW + 2x RPi 3B+)

This folder contains a hardware deployment package for your extended scheme with this topology:

- Laptop: Gateway (GW)
- RPi 3B+ #1: Authentication Server (AS)
- RPi 3B+ #2: Device Node

## Folder Contents

- Extended-Scheme-Source/: Full copied source from Anonymity-Extended-Base-Scheme
- native/: Native Python runtime for GW/AS/Node
- scripts/: Setup, sync, build, and run helpers
- config/: IP and role mapping

## Native Runtime Included

Runnable role programs:

- native/gw_hw.py
- native/as_hw.py
- native/node_hw.py

Protocol flow preserved:

1. Enrollment (Node -> AS)
2. Authentication and PID rotation (Node <-> AS)
3. Session token forwarding (AS -> GW)
4. Encrypted data transmission (Node -> GW)

## PUF Engine (pypuf)

Native authentication uses pypuf challenge-response pairs:

1. Node enrolls a CRP set generated from local pypuf model.
2. AS stores enrolled CRPs per device.
3. AS sends one enrolled challenge during authentication.
4. Node evaluates pypuf response and returns proof.
5. AS verifies response, rotates PID, and forwards GW token.

## Quick Start

1. Edit config values in config/roles.env.
   - Minimum required: GW_HOST, AS_HOST, NODE_HOST.
   - If you only have IP addresses, that is enough.

2. Copy project to each RPi from laptop:
   - scripts/02-sync-project.sh

3. On each machine, install dependencies:
   - scripts/01-setup-rpi.sh
   - This installs pypuf and numpy from requirements.txt.

4. Build and run per role:
   - scripts/03-build-role.sh gw
   - scripts/03-build-role.sh as
   - scripts/03-build-role.sh node
   - scripts/04-run-role.sh gw|as|node

5. Orchestrate all three from your laptop:
   - scripts/05-orchestrate-from-laptop.ps1

## Suggested Role-IP Mapping

- GW (Laptop): 192.168.1.10
- AS (RPi-1): 192.168.1.20
- Node (RPi-2): 192.168.1.30

## Execution Order (Three Machines)

1. Laptop (GW):
   - ./scripts/03-build-role.sh gw
   - ./scripts/04-run-role.sh gw

2. RPi #1 (AS):
   - ./scripts/03-build-role.sh as
   - ./scripts/04-run-role.sh as

3. RPi #2 (Node):
   - ./scripts/03-build-role.sh node
   - ./scripts/04-run-role.sh node

Expected outcome: GW logs show token acceptance and decrypted DATA packets.

## Security Scope of Native Runtime

This runtime is for controlled LAN thesis experimentation. It mirrors protocol behavior but is not production-hardened.
