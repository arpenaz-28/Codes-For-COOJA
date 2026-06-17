# Li-Scheme — comparison baseline (PUF + strong anonymity, ECC-based)

## Citation
Sensen Li, Yicai Huang, Bin Yu, "A practical and flexible PUF-based end-to-end
anonymous authentication protocol for IoT," *Computer Networks* 247 (2024) 110426.
DOI: 10.1016/j.comnet.2024.110426. BibTeX key: `li2024puf`.

## Why this scheme is used
Closest **modern** scheme to ours in security class: **PUF + strong anonymity for IoT**,
and it is benchmarked on the **same Raspberry Pi 4B** hardware we use. It relies on
ECC (certificateless), so it lets us show our computation advantage honestly against a
peer that provides comparable security guarantees.

- Security class: PUF + **strong** anonymity (server/verifier cannot recover real ID)
- Crypto: PUF + fuzzy extractor + ECC (no bilinear pairing)
- System model: end-to-end device <-> service node (no TTP during auth)
- Desync handling: TTP-assisted via revoked-parameter list (re-provision at management server)

## Key data extracted (Authentication & Key Exchange phase)
Operation counts:
- Total: `2T_puf + 2T_fe + 7T_hash + 4T_ea + 12T_em`
  (Initiator `T_puf+T_fe+3T_hash+T_ea+6T_em`; Verifier `T_puf+T_fe+4T_hash+3T_ea+6T_em`; Server 0)
- **12 ECC point multiplications** dominate the cost.

Benchmark (their Table III, RPi 4B, C++/MIRACL):
- ECC point mult `T_em` = 2.352 ms; ECC point add `T_ea` = 0.012 ms;
  hash = 0.003 ms; sym enc/dec = 0.009 ms; bilinear pairing = 24.436 ms (unused).

Costs:
- Computation ~28.7 ms (re-priced on common RPi 4B basis) -> **Proposed is ~97.7% lower (0.67 ms)**
- Communication: 3 rounds, **2336 bits** (ECC point = 512 b) -> **Proposed ~41% lower (1376 b)**

## Files
- Place the paper PDF here (e.g. `Li_Huang_Yu_2024_ComputerNetworks.pdf`).
