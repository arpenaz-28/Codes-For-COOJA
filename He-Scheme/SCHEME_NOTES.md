# He et al. 2023 — Lightweight Authentication and Key Exchange Protocol with Anonymity for IoT

**Full citation:**
D. He, Y. Cai, S. Zhu, Z. Zhao, S. Chan, and M. Guizani,
"A Lightweight Authentication and Key Exchange Protocol with Anonymity for IoT,"
*IEEE Trans. Wireless Communications*, vol. 22, no. 11, pp. 7862–7872, Nov. 2023.
DOI: 10.1109/TWC.2023.3257028

---

## 1. What Problem Does It Solve?

IoT devices at the network edge have two fundamental problems:
1. **Exposure** — all communications with the cloud server go over an open channel, visible to any attacker.
2. **Resource constraints** — IoT devices have limited battery, CPU, and memory, so heavy crypto (RSA, full ECC) is too expensive.

The paper designs an authentication + key exchange protocol that is:
- **Lightweight** — only hash functions, XOR, symmetric encryption, and *one* ECC operation per session
- **Anonymous** — the real device identity `Id_i` is **never sent on the open channel**
- **Mutually authenticating** — both the device and the cloud server verify each other

---

## 2. System Model

Three entities (Fig. 1):

| Entity | Role |
|---|---|
| `ED_i` | IoT device (i-th); resource-constrained; at the network edge |
| `CS` | Cloud Server; trusted; has private key `X_cs` and public key `P_cs` |
| Communication Module | Switch/router; just relays packets; **not** an authenticating entity |

**Adversary (Dolev-Yao model):**
- Can intercept, modify, replay, delete any message on the open channel
- Can steal the physical device and read everything stored on it
- Cannot compromise the CS itself
- Must obtain the key to decrypt any encrypted information

---

## 3. Notation (Table I)

| Symbol | Meaning |
|---|---|
| `ED_i` | i-th IoT device |
| `Id_i` | Real identity of `ED_i` (never sent openly) |
| `Pw_i` | Password of `ED_i` |
| `I_i` | Hashed credential: `h(Id_i ‖ Pw_i)` |
| `Pid_i` | Pseudonym (temporary ID) assigned by CS during registration |
| `CS` | Cloud Server |
| `ID_cs` | Identity of CS |
| `X_cs` | CS private key |
| `P_cs` | CS public key |
| `r_cs` | High-entropy random number chosen by CS during registration |
| `e_i` | Session random number chosen by device during authentication |
| `q_i` | Session random number chosen by CS during authentication |
| `C_k` | Symmetric key derived from server's secret + pseudonym |
| `A_i` | ECC-encrypted identity proof: `ENC_{X_cs}(Pid_i ‖ E_t)` |
| `R_i` | Auxiliary value: `r_cs ⊕ h(X_cs ‖ Pid_i)` |
| `sk` | Final session key |
| `E_t` | Device expiration time |
| `T1..T4` | Timestamps at each message step |
| `ΔT` | Maximum allowed transmission delay |
| `h(·)` | One-way collision-resistant hash function |
| `⊕` | Bitwise XOR |
| `‖` | Concatenation |
| `ENC_k / DEC_k` | Symmetric encryption/decryption with key k |
| `ECC_{P_cs}(·)` | ECC encryption with CS public key |
| `ECC_{X_cs}(·)` | ECC decryption with CS private key |

---

## 4. Protocol — Two Phases

### Phase 1: Registration Phase (offline, over secure channel)

This happens once, before any authentication. Device communicates with CS over a **secure (trusted) channel**.

```
ED_i                                          CS
------                                        ------
Compute I_i = h(Id_i ‖ Pw_i)      ──(I_i)──>    [secure channel]
                                               Select random r_cs
                                               Pid_i = h(I_i ‖ ID_cs) ⊕ ID_cs      ...(2)
                                               C_k   = h(X_cs ‖ Pid_i ‖ E_t ‖ r_cs) ⊕ ID_cs ...(3)
                                               C'_k  = C_k ⊕ I_i                   ...(4)
                                               A_i   = ENC_{X_cs}(Pid_i ‖ E_t)     ...(5)
                                               A'_i  = A_i ⊕ I_i                   ...(6)
                                               R_i   = r_cs ⊕ h(X_cs ‖ Pid_i)      ...(7)
                                               R'_i  = R_i ⊕ I_i                   ...(8)
                                               Store {R_i, E_t, Pid_i} in DB (secure)
Store {I_i, Pid_i, C'_k, A'_i, R'_i}  <──(Pid_i, A'_i, R'_i, C'_k)── [secure channel]
```

**What is sent over secure channel:**
- Device → CS: only `I_i = h(Id_i ‖ Pw_i)` — NOT the raw `Id_i` or `Pw_i`
- CS → Device: `{Pid_i, A'_i, R'_i, C'_k}` — all XOR-masked with `I_i`

**Key insight — why XOR masking?**
The CS sends `C'_k = C_k ⊕ I_i` (not raw `C_k`). If the secure channel has an insider attacker who can read `I_i`, they still cannot recover `C_k` without also knowing `I_i`. The real values `C_k, A_i, R_i` are never stored in plain form on the device.

---

### Phase 2: Authentication Phase (over open channel)

This runs every time the device wants to access CS. Four steps.

```
ED_i                                          CS
------                                        ------

[STEP 1 — Device prepares login]

User inputs Id'_i, Pw'_i
I*_i = h(Id'_i ‖ Pw'_i)                     (9)
Verify I*_i == stored I_i  (reject if not)
Recover: C_k  = C'_k ⊕ I_i                  (10)
         A_i  = A'_i ⊕ I_i                  (11)
         R_i  = R'_i ⊕ I_i                  (12)
Choose random e_i, get timestamp T1
N_i = ECC_{P_cs}(Pid_i ‖ R_i)               (13)  [ECC-encrypted with CS public key]
E_i = ENC_{C_k}(e_i, T1, A_i)               (14)  [symmetric encrypted]

        ──── {N_i, T1, E_i} ────────────────> [open channel]

[STEP 2 — CS authenticates device, sends reply]

                                               Check: T2 - T1 < ΔT (freshness)
                                               Decrypt: (Pid_i, R_i) = ECC_{X_cs}(N_i)
                                               Lookup Pid_i in database
                                               Check expiry E_t is valid
                                               Recover: r_cs = R_i ⊕ h(X_cs ‖ Pid_i)  (15)
                                               Recompute: C_k = h(X_cs ‖ Pid_i ‖ E_t ‖ r_cs) ⊕ ID_cs (16)
                                               Decrypt: (e*_i, T*1, A*_i) = DEC_{C_k}(E_i)
                                               Decrypt: (Pid*_i, E*_t)   = DEC_{X_cs}(A*_i)
                                               Verify: Pid*_i == Pid_i  AND  E*_t == E_t
                                               Verify: T*1 == T1
                                               Choose random q_i
                                               Q_i = h(A_i ‖ C_k)                     (17)
                                               s_i = q_i ⊕ C_k                        (18)
                                               w_i = h(Pid_i ‖ e*_i)                  (19)
                                               T_i = ENC_{A*_i}(s_i, w_i, T2)         (20)

        <──── {T_i, T2} ─────────────────────  [open channel]

[STEP 3 — Device authenticates CS, computes session key]

Check: T3 - T2 < ΔT (freshness)
Decrypt: (s_i, w_i, T'2) = DEC_{A_i}(T_i)
Compute: w'_i = h(Pid_i ‖ e_i)              (21)
Verify: w'_i == w_i  (proves CS is genuine)
Verify: T'2 == T2
q'_i  = s_i ⊕ C_k                           (22)
Q_i   = h(A_i ‖ C_k)                        (23)
sk    = h(e_i ‖ C_k ‖ Q_i ‖ R_i ‖ s_i)    (24)  [SESSION KEY on device side]
MN_i  = h(sk ‖ q_i ‖ s_i ‖ Q_i)            (25)

        ──── {MN_i, T3} ─────────────────────> [open channel]

[STEP 4 — CS confirms session key]

                                               Check: T4 - T3 < ΔT
                                               sk_CS = h(e*_i ‖ C_k ‖ Q_i ‖ R_i ‖ s_i) (26)
                                               MN'_i = h(sk ‖ q_i ‖ s_i ‖ Q_i)          (27)
                                               Verify: MN_i == MN'_i
                                               ✓ AUTHENTICATION COMPLETE — use sk
```

---

## 5. Session Key

```
sk = h(e_i ‖ C_k ‖ Q_i ‖ R_i ‖ s_i)
```

Where:
- `e_i` — device's fresh random (this session only)
- `q_i` — server's fresh random (this session only), inside `s_i = q_i ⊕ C_k`
- `C_k` — derived from server's private key + pseudonym (never on the open channel)
- `Q_i = h(A_i ‖ C_k)` — binding hash
- `R_i` — derived from `r_cs ⊕ h(X_cs ‖ Pid_i)`

Both fresh randoms `e_i` and `q_i` are used, so each session produces a completely independent key.

---

## 6. Anonymity Mechanism

The real identity `Id_i` is **never sent on the open channel**. Here is how it is hidden:

1. **Registration:** Device sends only `I_i = h(Id_i ‖ Pw_i)` — a one-way hash. CS never learns `Id_i` directly.
2. **Authentication:** The pseudonym `Pid_i` is sent encrypted inside `N_i = ECC_{P_cs}(Pid_i ‖ R_i)`. Only CS (with private key `X_cs`) can decrypt it.
3. **Pseudonym computation:** `Pid_i = h(I_i ‖ ID_cs) ⊕ ID_cs` — derived by CS from the hashed credential. `I_i` itself is the hash of real identity + password, so `Id_i` is never known to CS.

---

## 7. Security Properties (Table II)

| Security Feature | Proposed |
|---|---|
| Perfect forward secrecy | ✓ |
| Device anonymity | ✓ |
| Mutual authentication | ✓ |
| Replay attack resistance | ✓ |
| Device impersonation attack resistance | ✓ |
| Server impersonation attack resistance | ✓ |
| Stolen device attack resistance | ✓ |
| DoS attack resistance | ✓ |
| Known key secrecy | ✓ |
| Formal security analysis | ✓ |
| Session key security | ✓ |

**All 11 properties satisfied.** Competing protocols [3][22][23][24][25] each miss at least one (most commonly device anonymity or mutual authentication).

### Why key attacks fail:

**Replay attack:** Every message has a timestamp T_i. Both the device and CS check `T_{i+1} - T_i < ΔT`. Old captured packets are rejected due to stale timestamps.

**Device impersonation:** An attacker cannot compute the correct `N_i = ECC_{P_cs}(Pid_i ‖ R_i)` or `E_i = ENC_{C_k}(e_i, T1, A_i)` without knowing `C_k` and `A_i`, which require `I_i` (password hash). Without the correct values, CS's decryption produces a wrong `Pid_i` that fails the database lookup.

**Server impersonation:** CS proves its identity in Step 2 by sending `w_i = h(Pid_i ‖ e_i)` inside `T_i`. Only a genuine CS that correctly decrypted `e_i` from `E_i` can compute the correct `w_i`. The device verifies `w'_i = w_i` in Step 3.

**Stolen device attack:** CS does **not** store the password `Pw_i` or the session key `sk`. The session key depends on fresh randoms `e_i`, `q_i` generated only during authentication. So even if the device is physically stolen, the attacker cannot reconstruct any past `sk`.

**Perfect forward secrecy:** Even if the long-term password `Pw_i` or the server's long-term key `X_cs` is later compromised, past session keys cannot be recomputed because `e_i` and `q_i` are ephemeral (discarded after each session).

**DoS attack:** Timestamps mean any malformed or delayed packet is dropped immediately before any heavy computation is done.

---

## 8. Formal Verification

**Tool:** AVISPA (HLPSL language) — same tool widely used in authentication protocol analysis.

**Backends run:**
- OFMC (On-the-Fly Model Checker): **SAFE**
- CL_AtSe (Constraint-Logic-based Attack Searcher): **SAFE**

**Security goals verified:**
1. Secrecy of `sec1` (session key material on device side)
2. Secrecy of `sec2` (session key material on server side)
3. Authentication goal: `alice_bob_r1` (device → server authentication)
4. Authentication goal: `bob_alice_r2` (server → device authentication)

**ROR (Real-Or-Random) model proof:**
Formally proves that the session key `sk` is semantically secure (indistinguishable from a random string):
```
Adv_P^{ake} ≤ q_h² / |Hash| + 2·q_send / |D|
```
where `q_h` = number of hash oracle queries, `q_send` = number of Send queries, `|Hash|` = hash range size, `|D|` = password dictionary size. When these are large, the advantage is negligible → protocol is secure.

---

## 9. Performance

**Hardware for timing:** RK3568 development board, 2GB RAM, KaihongOS 1.2.2.010
- `T_h` = 0.092 ms (one hash)
- `T_en` = 1.202 ms (one symmetric enc/dec)
- `T_p` = 0.5046 ms (one ECC scalar multiplication)

**Computation cost (Table III):**

| Entity | Operations | Time |
|---|---|---|
| Device | 5T_h + 1T_en + 1T_d + 1T_p | ~2.61 ms |
| Server | 6T_h + 1T_en + 2T_d + 1T_p | ~3.33 ms |
| **Total** | **11T_h + 2T_en + 3T_d + 2T_p** | **5.939 ms** |

**Comparison:** Other protocols cost 9.15–18.48 ms. This protocol is **the fastest**.

**Communication cost (Table IV):**

| Message | Contents | Bits |
|---|---|---|
| Device → CS | `{N_i, T1, E_i}` | 480 bits |
| CS → Device | `{T_i, T2}` | 160 bits |
| Device → CS | `{MN_i, T3}` | 192 bits |

- Bit sizes: hash=160b, random=32b, timestamp=32b, symmetric enc=128b, ECC point=320b
- **Total: 662 bits** (competing protocols: 1760–4416 bits each)

---

## 10. Comparison With Our Proposed Scheme (das2026comsnets / Revised Anonymity)

| Aspect | He et al. 2023 | Our Proposed Scheme |
|---|---|---|
| System entities | Device + Cloud Server (2 entities) | Device + GW + AS (3 entities, multihop) |
| Anonymity | Pseudonym `Pid_i = h(I_i ‖ ID_cs) ⊕ ID_cs` (static per registration) | Rotating pseudonym `PID = H(ID_D ‖ m_curr)`, refreshed after each key exchange |
| Desync recovery | Not addressed | Dual-state `(m_curr, m_old)` recovery |
| Topology | Device–Server direct (edge) | Multihop IoT network, GW-selected AS |
| PUF | No | Yes (PUF-based secret derivation) |
| Authentication selection | Centralized (fixed CS) | Decoupled (GW selects any capable node as AS) |
| Formal verification | AVISPA (4 goals) | ProVerif (19 queries) |
| Key primitives | Hash + XOR + 1 ECC + symmetric enc | Hash + XOR + one-way accumulator |

He et al. is a simpler two-party scheme for edge IoT. Our scheme adds a three-party multihop architecture with rotating anonymity and desynchronization recovery — which He et al. do not address.

---

## 11. Files in This Folder

| File | Description |
|---|---|
| `A_Lightweight_Authentication_and_Key_Exchange_Protocol_With_Anonymity_for_IoT.pdf` | Original paper |
| `SCHEME_NOTES.md` | This explanation document |
