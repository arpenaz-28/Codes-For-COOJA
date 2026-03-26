# Proposed-Scheme-Two-Round

## Purpose

This is a structural variant of the **Anonymity-Extended-Base-Scheme** where
Authentication (Phase 2) and Key Exchange (Phase 3) are split into **two
separate CoAP rounds**, mirroring the Base Scheme (Ding et al.) structure.

This enables **fair, per-phase comparison** of Auth and KeyEx independently,
with independent Energest measurements for each.

---

## Protocol Flow

```
ENROLLMENT  (same as original)
  Device → AS : /test/reg   AES_enc(K_AS_D, [ID_d|pad]) = 16 B
  AS     → Dev: AES_enc(K_AS_D, [c_d|m_d(32)|pad])      = 48 B
  Device → AS : /test/reg1  AES_enc(K_AS_D, [...])       = 48 B
  Logged as: ENROLL_ENERGY|<id>|cpu_s=...|energy_j=...

ROUND 1 — AUTHENTICATION  (/test/auth)
  Device → AS : PID(32) | Y_asd(32) | ts_1(1)            = 65 B
  AS verifies membership, computes m_H/K_GW_D/token,
  stores in pending table — does NOT reply with m_H yet.
  AS → Device : ACK(1) | ts_2(1)                         =  2 B
  Logged as: AUTH_ENERGY|<id>|cpu_s=...|energy_j=...

ROUND 2 — KEY EXCHANGE  (/test/keyex)   ← NEW separate round
  Device → AS : PID(32) | ts_2(1)                        = 33 B
  AS looks up pending entry, replies with m_H,
  performs PID rotation, forwards token to GW.
  AS → Device : m_H(32)                                  = 32 B
  AS → GW     : new_PID(32)|ID_AS(1)|enc_token(48)       = 81 B
  Logged as: KEYEX_ENERGY|<id>|cpu_s=...|energy_j=...

DATA LOOP  (same as original)
  Device → GW : PID(32) | AES_enc(K_GW_D, data)         = 48 B
```

---

## Key Differences from `Anonymity-Extended-Base-Scheme`

| | Original (One-Round) | This (Two-Round) |
|---|---|---|
| `/test/auth` reply | ACK + m_H + ts_2 = 34 B | ACK + ts_2 only = **2 B** |
| m_H delivery | In auth reply | In new `/test/keyex` reply |
| PID rotation | After auth handler | After keyex handler |
| `AUTH_ENERGY` | Auth CoAP + data CoAP | Auth CoAP only |
| `KEYEX_ENERGY` | Auth CoAP only | KeyEx CoAP only |
| AS pending table | Not needed | Added (`pending_t[MAX_CLIENTS]`) |

---

## Files Changed

- **`device-node.c`** — New three-state machine: Enroll → Auth → KeyEx → Data
- **`as-node.c`** — Split auth handler + new `/test/keyex` resource + pending table
- All others (`gw-node.c`, `aes.*`, `sha256.*`, `project-conf.h`, `Makefile`) are unchanged copies

---

## Log Extraction

Use the same extraction script:
```bash
python Scripts/Utilities/proposed-extract_all_metrics.py <logfile>
```
Outputs three CSVs: `enroll-results.csv`, `auth-results.csv`, `keyex-results.csv`

---

## Security Properties Preserved

All original security properties are maintained:
- PUF-based binding
- Rotating pseudonyms (PID rotation, just deferred one step)
- Desynchronisation recovery (dual-state PID_curr/PID_old)
- Membership test (AND accumulator)
- Replay protection (ts_1 freshness, ts_2 echo)
- Token freshness on GW side (ts_auth)
