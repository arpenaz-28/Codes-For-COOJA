# DAuth (Das[1] Base Scheme) — COOJA Simulation Results

Source: `Manual-COOJA/DAuth-COOJA/` (gw-node, as-node, device-node)
Config: `Manual-COOJA/DAuth-COOJA/simulation.csc`
Topology: 100 motes — GW=1, AS=2-3 (active), Devices=81-100 (20 devices)
Seed: 123456 | UDGM, success ratio 1.0 | RPL Lite + CSMA/802.15.4

## Purpose

Re-measure the DAuth base scheme using the **identical delta-snapshot Energest
technique** as the Proposed scheme, so **enrollment energy is fairly comparable**.
The old Das[1] sim measured enrollment as a cumulative odometer from device boot
(included ~10-15 s of RPL startup → 1000-2500 mJ), which is not comparable to the
Proposed scheme's crypto-delta enrollment (~20-23 mJ).

## Key fix applied

Devices use staggered start `etimer_set(CLOCK_SECOND * (5 + node_id))` — identical
to the Proposed scheme. This waits out RPL convergence so each enrollment CoAP
round-trip is fast; the BEFORE/AFTER delta then captures crypto + a converged
round-trip, NOT the RPL boot wait.

Before fix (all devices fire at t=5 s, RPL not converged): enroll = 1400-3900 mJ.
After fix (staggered, RPL converged): enroll = 15.7-30.2 mJ. ✓

## Results (seed 123456, 20 devices, all completed)

| Metric            | DAuth (this run) | Proposed (ref, 10-seed mean) |
|-------------------|------------------|------------------------------|
| Enroll energy     | 23.64 mJ (mean)  | 23.15 mJ                     |
| Auth(+KeyEx) en.  | 12.27 mJ (mean)  | 29.04 mJ (auth+keyex)        |
| Enroll range      | 15.73 - 30.24 mJ | —                            |
| Auth range        | 3.87 - 20.08 mJ  | —                            |

Enrollment is now apples-to-apples comparable (≈23 mJ both schemes).

## NOTE on the auth structure (needs confirmation)

This DAuth build uses a **single combined auth+keyex CoAP round** (mirrors the
`Manual-COOJA/Proposed` code structure). The original Das[1] base scheme uses
**separate auth + DH key-exchange rounds** (see `Base-Scheme/Base-Scheme-Aligned`),
which is the structure the paper's 26.8%-overhead-reduction claim compares against.
The combined round here makes DAuth's auth cost lower than the true base scheme.
For the auth/keyex comparison in the paper, use the separate-round numbers from
`Base-Scheme-Aligned`; this folder's contribution is the fair **enrollment** number.

## Files

- `logs/testlog_seed123456.txt`  — raw COOJA testlog
- `seed_results.csv`             — per-device enroll/auth/total energy + CPU
