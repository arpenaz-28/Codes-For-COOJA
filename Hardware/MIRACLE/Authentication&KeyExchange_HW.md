# Authentication & Key-Exchange phase cost (hardware)

*RPi 4B · MIRACL Core (NIST P-256) · CPU governor pinned · energy = wall × 3.8 W ·
median of 7 runs · per-round (warm-up discarded) · Data phase excluded.*

| Scheme | Phase | Energy (J) | Time (s) |
|---|---|---|---|
| **Proposed** | Authentication (D↔AS) | **0.0617** | **0.0162** |
| **DAuth** | Authentication (D↔AS) | **0.0611** | **0.0161** |
| **LAAKA** | Mutual Auth & Key Exch (AuthReq + AuthRep + Ack) | **0.0959** | **0.0253** |
| **Zhou** | Auth & Key Exch (M1→M4) | **0.1074** | **0.0282** |

## Notes
- **Proposed ≈ DAuth** (~0.062 J): a single D↔AS round-trip; the session key
  is derived from the AS reply and the AS→GW token push runs server-side, off the
  device's critical path.
- **LAAKA** (0.096 J): mutual auth = two device→Fog round-trips (AuthReq/AuthRep + Ack).
- **Zhou** (0.107 J): single M1→M4 round carrying the nested GW↔SN round-trip
  (M2/M3) plus the ECC fuzzy extractor (FE #2) on the user side.
- Network-round-trip dominated; the MIRACL crypto itself is sub-millisecond.

Chart: `Authentication&KeyExchange_HW.png` · reproduce with `plot_auth_keyex.py`.
