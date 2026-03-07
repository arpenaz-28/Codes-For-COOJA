# ProVerif Security Analysis — Anonymity-Extended-Base-Scheme

Formal security analysis of the PUF-based IoT authentication protocol with dual-state storage, using the **ProVerif** automated cryptographic protocol verifier.

## Verification Results (All 10/10 PASS)

| # | Query | Property | Result |
|---|-------|----------|--------|
| Q1 | `not attacker(sQ_sesskey)` | **Session Key Secrecy** — K_GW_D cannot be learned | **TRUE** |
| Q2 | `not attacker(sQ_mnew)` | **Session Seed Secrecy** — rotated m_new is secret | **TRUE** |
| Q3 | `not attacker(sQ_Rd)` | **PUF Response Secrecy** — R_d cannot be extracted | **TRUE** |
| Q4 | `not attacker(sQ_devid)` | **Device Anonymity** — real identity unlinkable from PID | **TRUE** |
| Q5a | `not attacker(K_AD)` | **Pre-shared Key (Device↔AS) Secrecy** | **TRUE** |
| Q5b | `not attacker(K_GA)` | **Pre-shared Key (AS↔GW) Secrecy** | **TRUE** |
| Q6 | `AS_Authenticates ⟹ DeviceStarts` | **Device Authentication** — AS only authenticates if device initiated | **TRUE** |
| Q7 | `DeviceDataAccepted ⟹ AS_Replies` | **Implicit AS Authentication** — device confirms data only if AS genuinely replied (key confirmation via GW) | **TRUE** |
| Q8 | `GW_DataAccepted ⟹ AS_TokenSent` | **End-to-End Auth** — GW accepts data only if AS forwarded token | **TRUE** |
| Q9 | `inj-event(AS_Authenticates) ⟹ inj-event(DeviceStarts)` | **Replay Resistance (Injective Agreement)** — each AS auth maps to exactly one device initiation | **TRUE** |

## What Each Query Proves

### Secrecy Properties (Q1–Q5)
- **Q1–Q2**: Even with full network control, the attacker cannot derive the session key or new session seed. This is because recovering m_new requires knowledge of R_d (PUF response), Y_dH (membership value), and the current session seed m_d — all of which are private.
- **Q3**: PUF responses are physically bound to hardware and cannot be cloned or computed by the attacker.
- **Q4**: Pseudonyms (PIDs) are unlinkable to real device identities because PID = H(id_d ∥ m_d) and m_d rotates each session.
- **Q5**: Pre-shared symmetric keys remain confidential throughout the protocol execution.

### Authentication Properties (Q6–Q9)
- **Q6**: The AS only authenticates a device if that device genuinely initiated the authentication (the attacker cannot forge a valid auth request without knowing the PUF response and membership value).
- **Q7**: Implicit AS authentication via key confirmation — if the device successfully sends encrypted data to the GW and gets it accepted, the AS must have genuinely replied (because only the real AS can compute the correct seed mask for m_new delivery).
- **Q8**: The GW only accepts device data if the AS previously forwarded a valid encrypted session token (attacker cannot forge tokens without K_GW_AS).
- **Q9**: Injective agreement ensures each authentication at the AS corresponds to exactly one unique device initiation — proving replay attacks are impossible.

## Threat Model

The analysis uses the **Dolev-Yao** attacker model:
- Full control over public network (intercept, modify, replay, inject messages)
- **Cannot**: clone PUF hardware, access secure enrollment channel, extract device secrets from tamper-resistant memory

## Security Properties Verified

| OWASP/IoT Security Concern | ProVerif Query | Status |
|----------------------------|---------------|--------|
| Broken Authentication | Q6, Q9 | Mitigated |
| Credential Stuffing/Replay | Q9 (injective) | Mitigated |
| Session Hijacking | Q1 (key secrecy) | Mitigated |
| Identity Linkability | Q4 (anonymity) | Mitigated |
| Man-in-the-Middle | Q6, Q7 (mutual auth) | Mitigated |
| Token Forgery | Q5b, Q8 | Mitigated |
| PUF Cloning | Q3 | Mitigated |
| Desynchronization | Dual-state in model | Handled |

## Files

| File | Description |
|------|-------------|
| `scheme.pv` | ProVerif model of the complete protocol |
| `proverif-full-output.txt` | Complete ProVerif verification output |
| `Dockerfile` | Docker image for running ProVerif |

## How to Run

```bash
# Build ProVerif Docker image (one-time)
cd "ProVerif-Security-Analysis"
docker build -t proverif-tool .

# Run verification
docker run --rm -v "${PWD}:/work" proverif-tool /work/scheme.pv
```
