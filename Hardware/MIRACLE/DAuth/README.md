# Fair-DAuth — DAuth on the Proposed scheme's transport (end-to-end, MIRACL)

> **Purpose.** The original DAuth end-to-end sim looked *slower* than Proposed
> (0.155 J vs 0.111 J per round). That gap was an **implementation artifact**,
> not DAuth's protocol: DAuth used JSON framing and a **pull-based** Key Exchange
> (device→GW→AS→GW→device, an extra server round-trip), whereas Proposed uses
> compact binary framing and **push-based** key delivery (the AS pushes the
> session token to the GW during Auth, so KeyEx is a single device→GW hop).
>
> This folder re-hosts **DAuth's core logic** on the **Proposed scheme's
> transport and topology** so the two are compared on equal footing.

## What was matched to Proposed (everything except DAuth's core)

- binary length-prefixed TCP framing (no JSON)
- **push-based** AS→GW token delivery → single-round-trip KeyEx
- identical per-phase timing brackets, 3.8 W energy model
- MIRACL Core crypto on the measured nodes (`USE_MIRACL=1`)
- same role placement: Device = Pi (.113), AS = Apex (.132), GW = laptop

## What stayed DAuth (its core novelty/logic — the only differences from Proposed)

- device identified by a **static handle** `DH = H(ID_D ‖ m0)` fixed at
  enrollment — **no pseudonym rotation**
- AS/GW keep **single state** — **no dual-state desync recovery**
- key freshness still via the per-round nonce update `m_new`

(Pseudonym rotation + dual-state desync are exactly the *Proposed* scheme's
contributions, so they are correctly absent here.)

## Files

| File | Role |
|---|---|
| `device.py` | Device (Pi) — measured node |
| `as_node.py` | AS (Apex) — pushes token to GW |
| `gw.py` | Gateway (laptop, Python) — reused from Proposed, handle-keyed |
| `common.py`, `config.py` | shared crypto + network config (MIRACL flag) |
| `miracl_crypto.py`, `libmiraclshim.so` | MIRACL backend |
| `run_simulation.py` | orchestrator (self-contained) |
| `compare_fair.py` | runs Proposed vs Fair-DAuth interleaved, same session |
| `results/`, `compare_fair_result.json` | raw + aggregated output |

## Reproduce

```bash
cd Hardware/MIRACLE/DAuth
python run_simulation.py 1     # one fair-DAuth run
python compare_fair.py 6       # Proposed vs Fair-DAuth, 6 runs, same session
```

## Result (6 runs each, interleaved, same session, MIRACL)

| Scheme     | AK energy (J) | AK time (s) | auth (ms) | KeyEx (ms) |
|------------|--------------:|------------:|----------:|-----------:|
| Proposed   | 0.1165        | 0.0307      | 16.8      | 13.9       |
| Fair-DAuth | 0.1057        | 0.0278      | 15.9      | **11.9**   |

**KeyEx dropped from ~24 ms (old pull-based DAuth) to ~12 ms**, matching
Proposed. With transport equalized, Fair-DAuth is now **marginally lighter than
Proposed** (≈9% lower energy) — consistent with its lighter computation (no
pseudonym-rotation hashing, no dual-state), i.e. exactly what the paper's
computational-cost table shows (DAuth 0.114 ms < Proposed 0.150 ms).

**Takeaway:** the earlier "DAuth > Proposed" end-to-end was purely the JSON +
pull-KeyEx implementation, not the protocol. On equal footing, Proposed pays a
small, expected premium over DAuth for the anonymity (pseudonym rotation) and
dual-state desync-recovery features that DAuth lacks.

Archive / exploratory — not in the paper.
