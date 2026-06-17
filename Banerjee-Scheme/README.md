# Banerjee-Scheme — comparison baseline + closest prior art (PUF + anonymity, fuzzy-extractor)

## Citation (the one we use: the PUF / IEEE Access version)
Soumya Banerjee, Vanga Odelu, Ashok Kumar Das, Samiran Chattopadhyay,
Joel J. P. C. Rodrigues, Youngho Park, "Physically Secure Lightweight Anonymous User
Authentication Protocol for Internet of Things Using Physically Unclonable Functions,"
*IEEE Access*, vol. 7, pp. 85627-85644, 2019. DOI: 10.1109/ACCESS.2019.2926578.
BibTeX key: `banerjee2019access`.

> NOTE: the same group also has Banerjee et al., *IEEE IoT-J* 6(5), 2019 (hash+AES+FE,
> no PUF). We compare against the **IEEE Access (PUF) version** above, which is the
> closest scheme to ours.

## Why this scheme is used (IMPORTANT — closest prior art)
It is the **near-twin** of our scheme: PUF + anonymity + **pseudonym-based desync
recovery**, and **no ECC**. It overlaps three of our selling points, so we must both
(a) beat it on cost and (b) clearly differentiate our contribution #2 (desync recovery).

- Security class: PUF + anonymity + untraceability (three-factor user side)
- Crypto: hash + PUF + **fuzzy extractor** + XOR (no ECC)
- Desync recovery: **finite pseudo-identity pool** `{pid_0...pid_s}`; exhausts and needs
  TTP (GWN) **renewal** round.

## Differentiation vs Proposed (state explicitly in the paper)
| Axis | Banerjee-Access 2019 | Proposed |
|---|---|---|
| Recovery state | finite pseudonym pool (exhausts) | **bounded dual-state** `(PID_curr, PID_old)` |
| TTP needed for recovery | yes (pool renewal) | **no** |
| Fuzzy extractor | yes (2x, dominant cost) | **none** (PUF used directly) |
| Distribution | fixed GWN | decoupled, gateway-selected AS |

## Key data extracted (Authentication phase)
Operation counts:
- Total: `31T_hash + 2T_fe`  (User `17T_h+T_f`; GWN `8T_h`; Sensing device `6T_h+T_f`)
- **Two fuzzy extractors dominate (~89% of cost).**

Benchmark (their Table 2, ~2013-era): hash `T_h`=0.5 ms; fuzzy extractor `T_f`=63.075 ms.
- Reported total: **141.65 ms** (own slow bench)
- Re-priced on our hash basis (`T_fe`~4.45 ms est.): ~10 ms -> **Proposed ~15x lower (0.67 ms)**

Communication:
- 3 messages, **2048 bits** as reported (uses 160-bit SHA-1)
- Normalized to 256-bit hash: **~3200 bits** -> **Proposed ~2.3x lower (1376 b)**

## Files
- Place the paper PDF here (e.g. `Banerjee_etal_2019_IEEEAccess_PUF.pdf`).
- Optional: keep the IoT-J 2019 paper too if you cite it (`banerjee2019iotj`).
