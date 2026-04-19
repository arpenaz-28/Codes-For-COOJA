# Hardware Deployment: Revised-Anonymity Scheme (Laptop GW + 2× RPi)

This folder contains the native Python hardware runtime for the **Revised-Anonymity Two-Round** scheme.

## Topology

| Role | Machine | Node ID | Default IP |
|------|---------|---------|------------|
| Gateway (GW) | Laptop | 1 | 192.168.1.10 |
| Auth Server (AS) | RPi #1 | 2 | 192.168.1.20 |
| Device Node | RPi #2 | 81 | 192.168.1.30 |

## Two-Round Protocol

```
Device (RPi #2)           AS (RPi #1)              GW (Laptop)
      |                       |                         |
      |-- REG0_REQ (16 B) --->|                         |
      |<-- REG0_REP (48 B) ---|                         |
      |-- REG1_REQ (48 B) --->|                         |
      |<-- REG1_REP ----------|                         |
      |                       |                         |
      |-- AUTH_REQ (65 B) --->| (Round 1: Auth only)    |
      |<-- AUTH_REP (2 B) ----|   ACK + ts_2            |
      |                       |                         |
      |-- KEYEX_REQ (33 B) -->| (Round 2: Key Exch.)    |
      |<-- KEYEX_REP (32 B) --|   m_H                   |
      |                       |--- GW_TOKEN (81 B) ---->|
      |                       |                         |
      |---------- DATA (48 B) ------------------------->|
```

### Packet sizes (match C source exactly)

| Message | Direction | Bytes |
|---------|-----------|-------|
| REG0_REQ | Node → AS | 16 B |
| REG0_REP | AS → Node | 48 B |
| REG1_REQ | Node → AS | 48 B |
| AUTH_REQ | Node → AS | 65 B |
| AUTH_REP | AS → Node | 2 B |
| KEYEX_REQ | Node → AS | 33 B |
| KEYEX_REP | AS → Node | 32 B |
| GW_TOKEN | AS → GW | 81 B |
| DATA | Node → GW | 48 B |

## Files

```
Revised-Anonymity/
├── README.md
├── requirements.txt          # pycryptodome only
├── config/
│   └── roles.env             # IPs, ports, node IDs — EDIT THIS
├── native/
│   ├── common.py             # Crypto + metrics helpers
│   ├── node_hw.py            # Device node  (RPi #2)
│   ├── as_hw.py              # Auth server  (RPi #1)
│   └── gw_hw.py              # Gateway      (Laptop)
└── scripts/
    ├── 01-setup-rpi.sh       # Install dependencies on each machine
    ├── 02-sync-project.sh    # rsync project to both RPis from laptop
    ├── 03-build-role.sh      # No-op (Python, no build needed)
    ├── 04-run-role.sh        # Start role: gw | as | node
    ├── 05-orchestrate-from-laptop.ps1  # Start AS+Node via SSH, prompt for GW
    └── 06-parse-hw-metrics.py          # Parse HW_METRIC log → CSV
```

## Quick Start

### 1. Edit IPs in config/roles.env

```
GW_HOST=<laptop IP>
AS_HOST=<RPi-1 IP>
NODE_HOST=<RPi-2 IP>
```

### 2. Copy project to both RPis (from laptop)

```bash
bash scripts/02-sync-project.sh
```

### 3. Install dependencies on each machine

On each RPi (and optionally on the laptop):
```bash
bash scripts/01-setup-rpi.sh
```

### 4. Start roles in order

**Terminal 1 — Laptop (GW):**
```bash
bash scripts/04-run-role.sh gw
```

**Terminal 2 — RPi #1 (AS):**
```bash
bash scripts/04-run-role.sh as
```

**Terminal 3 — RPi #2 (Device):**
```bash
bash scripts/04-run-role.sh node
```

Or start AS + Node remotely from one PowerShell window:
```powershell
.\scripts\05-orchestrate-from-laptop.ps1
```
Then start `./scripts/04-run-role.sh gw` locally.

### 5. Collect and parse metrics

On RPi #2 (Node), tee the output:
```bash
bash scripts/04-run-role.sh node | tee node-hw.log
```

Then parse:
```bash
python3 scripts/06-parse-hw-metrics.py node-hw.log metrics-hw.csv
```

## Cryptographic Fidelity

The Python runtime mirrors the C source exactly:

| C primitive | Python equivalent |
|-------------|-------------------|
| AES_ECB_encrypt/decrypt | `pycryptodome` AES-ECB |
| SHA256 | `hashlib.sha256` |
| `simulate_puf_response(c)` | deterministic seeded hash → same comparison |
| `generate_helper(r)` → `h = r` | `generate_helper()` in `common.py` |
| `regenerate_response(c,h)` → `h` | `regenerate_response()` in `common.py` |
| `T_acc &= Y_dH` membership | byte-wise AND accumulator |
| `phi_as_d = R_as XOR R_d` | integer XOR |

All packet byte layouts (sizes and field offsets) match the C `#define` constants in `as-node.c`.

## Energy Estimation Model

Same model as the Extended-Scheme hardware runtime:

```
energy_j = cpu_s × CPU_POWER_W + (tx_bytes + rx_bytes) × NET_ENERGY_PER_BYTE_J
```

Defaults: `CPU_POWER_W=2.5`, `NET_ENERGY_PER_BYTE_J=0.000002`
Configure in `config/roles.env`.
