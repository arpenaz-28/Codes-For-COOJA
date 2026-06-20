# Total end-to-end scheme cost (per respective paper)

*Hardware testbed: RPi 4B · MIRACL Core (NIST P-256) · CPU governor pinned to
performance during measurement · energy = wall_time × 3.8 W · median of 7 runs.*

Phases included per scheme (Data phase excluded everywhere; for Proposed/Fair-DAuth
the session key is established within Authentication via the AS→GW push, so there is
no separate D↔GW key-exchange phase counted):

- **Proposed / Fair-DAuth** : Device Enrollment + Authentication
- **LAAKA** : IoT-device Registration + Fog-server Registration + Mutual Authentication & Key Exchange (Auth + Ack)
- **Zhou** : User Registration + Sensor-Node Registration + Authentication & Key Exchange (M1→M4)

## Total cost

| Scheme | Phases included | Total Energy (J) | Total Time (s) |
|---|---|---|---|
| **Proposed** | Device Enrollment + Authentication | **0.2697** | **0.0710** |
| **Fair-DAuth** | Device Enrollment + Authentication | **0.2943** | **0.0774** |
| **LAAKA** | IoT-dev Reg + Fog Reg + Mutual Auth & Key Exch (Auth+Ack) | **0.2092** | **0.0550** |
| **Zhou** | User Reg + SN Reg + Auth & Key Exch (M1→M4) | **0.2980** | **0.0784** |

## Per-phase breakdown (median, Energy J / Time s)

| Scheme | Reg / Enroll #1 | Reg #2 | Auth | Key-Exch part |
|---|---|---|---|---|
| **Proposed** | enroll 0.207 / 0.054 | — | 0.062 / 0.016 | (in Auth) |
| **Fair-DAuth** | enroll 0.237 / 0.062 | — | 0.061 / 0.016 | (in Auth) |
| **LAAKA** | dev-reg 0.061 / 0.016 | fog-reg 0.050 / 0.013 | 0.062 / 0.016 | ack 0.034 / 0.009 |
| **Zhou** | user-reg 0.097 / 0.025 | sn-reg 0.084 / 0.022 | 0.107 / 0.028 | (in M1→M4) |

## Notes

- Proposed/Fair-DAuth: session key established within Authentication (AS→GW push);
  no separate D↔GW key-exchange phase and no Data phase counted.
- LAAKA "mutual authentication & key exchange" = Auth + Ack; both registration
  legs (device + fog) are performed live and measured.
- Zhou "authentication & key exchange" = single M1→M4 round, which internally
  includes the GW↔SN round-trip (M2/M3) and **both** ECC fuzzy-extractor ops
  (FE #1 in User Reg, FE #2 in Auth). Both SN and User registrations are measured.
- Totals are computed as per-run total → median (robust to enrollment cold-start
  spikes); per-phase column shows each phase's own median, so components do not
  sum exactly to the total.
- All values reproducible via `build_total.py`; raw aggregate in
  `table_total_miracl.json`.

Reading: the four schemes fall in a tight 0.21–0.30 J band. Proposed (0.270) and
Fair-DAuth (0.294) carry a heavier device enrollment (2 round-trips to the
RPi-hosted AS) but a light single authentication; LAAKA (0.209) is lowest
(160-bit ops, laptop-hosted RA); Zhou (0.298) is highest among the
registration-inclusive set, driven by its two ECC fuzzy extractors plus the
nested GW↔SN hop in M1→M4. These end-to-end numbers are network-round-trip
dominated — the MIRACL crypto itself is sub-millisecond.
