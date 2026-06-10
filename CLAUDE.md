# Project Context: IoT Authentication Paper (IIT MTP)

## Paper identity

- **Title:** Lightweight, Anonymous, and Decoupled Distributed Authentication for Multihop IoT Networks
- **Author:** Anup Kulkarni, IIT (MTP thesis)
- **Main file:** `Paper/paper_revised_anonymity.tex`
- **Target venue:** IEEE conference (IEEEtran `conference` documentclass, two-column layout)
- **Base/predecessor scheme:** das2026comsnets (`\cite{das2026comsnets}`), labeled **DAuth** in code/charts (Das & Khatua, COMSNETS 2026) — the earlier paper is `Paper/2026Lightweight and Decoupled Distributed-COMSNETS.pdf`. **DAuth ≠ LAAKA** — LAAKA is a completely separate comparison scheme (see Workflow notes for the four-scheme disambiguation).

## Novel contributions of THIS paper (vs base scheme)

1. **Pseudonym rotation (anonymity):** Real device identity `ID_D` is never sent on the open channel. Instead, a rotating pseudonym `PID = H(ID_D || m_curr)` is used, refreshed after each successful key exchange (Phase 3). GW never learns `ID_D`.
2. **Dual-state desynchronization recovery:** Both AS and GW store `(m_curr, m_old, PID_curr, PID_old)`. If D misses a Phase 3 update packet, it still arrives with `PID_old`; AS recognizes it via the dual-state lookup and re-synchronizes — no re-enrollment needed.
3. **Performance claim:** 26.8% reduction in authentication-and-key-exchange byte overhead vs the base scheme (measured on Raspberry Pi 4B hardware; energy = wall_time × 3800 mW everywhere).

## What was NOT changed from the base scheme

- Four-phase protocol structure: Enrollment → Authentication → Key Exchange → Data Communication
- PUF-based secret derivation (no long-term key storage)
- Hash-based one-way accumulator for group-membership verification
- Gateway-selected (decoupled) authentication server — AS can be any capable node, not just the parent

## LaTeX conventions established in this project

- **Document class:** `\documentclass[conference]{IEEEtran}` — two-column
- **Single-column figure:** `\begin{figure}[!t]` + `\includegraphics[width=\columnwidth]{...}`
- **Two-column figure:** `\begin{figure*}[!t]` + `\includegraphics[width=\textwidth]{...}` — use only when a figure truly needs full page width
- **Float barrier:** `\usepackage{placeins}` is loaded; place `\FloatBarrier` before any `\section{}` heading to prevent figures from floating into the wrong section
- **ProVerif figure placement trick:** Define `\begin{figure}` AFTER the first `\subsubsection{}` heading inside Security Analysis so left-column text fills before the figure appears
- **Packages loaded:** `tikz`, `arrows.meta`, `booktabs`, `multirow`, `placeins`, `balance`, `url`, `array`, `tabularx`
- **TikZ desync figure:** A timeline diagram lives in `\subsubsection{Desynchronization Recovery}` using styles `sbox`, `obox`, `arr`, `lbl`

## Figure files (must be uploaded to Overleaf with these exact names)

| Overleaf filename | Local source file | Phase/purpose |
|---|---|---|
| `fig_enroll.jpg` | `Diagrams/diagrams/Enrollment_Phase_withSK _Anonymity.jpg.jpeg` | Phase 1 — Enrollment |
| `fig_auth.png` | `Diagrams/diagrams/Authentication phase+Datacomm - Anonymity.png` | Phase 2 — Authentication + Data Comm |
| `fig_keyex.jpg` | `Diagrams/diagrams/Key_Exchange_Anonymity.jpg.jpeg` | Phase 3 — Key Exchange |
| `fig_proverif.png` | `ProVerif-Security-Analysis/Revised_Anonymity_Proverif.png` | ProVerif terminal output |
| `fig_sim_total.png` | `Results/COOJA-Simulation/10-Seed-Comparison/Charts/cooja_02_perdev_energy_cpu.png` | COOJA sim — per-device mean total cost (energy+CPU dual panel, 10 seeds, 100-mote) |
| `fig_sim_as_energy.png` | `Results/COOJA-Simulation/Charts/Authenticator_variation/01_as_variation_total_energy.png` | Sim — total energy vs active AS count |
| `fig_sim_as_cpu.png` | `Results/COOJA-Simulation/Charts/Authenticator_variation/02_as_variation_total_time.png` | Sim — total CPU time vs active AS count |
| `fig_sim_net_energy.png` | `Results/COOJA-Simulation/Charts/Network_variation/12_total_energy_grouped_bar.png` | Sim — total energy vs network size (N=30,50,80,100,120; 20% newly-joined devices) |
| `fig_sim_net_cpu.png` | `Results/COOJA-Simulation/Charts/Network_variation/13_total_cpu_grouped_bar.png` | Sim — total CPU time vs network size (N=30,50,80,100,120; 20% newly-joined devices) |
| `fig_hw_comparison.png` | `Hardware/Charts/hw_total_comparison.png` | Hardware — per-round energy and CPU time on RPi 4B (Proposed vs LAAKA vs Zhou) |

All phase figures are referenced with `\includegraphics[width=\columnwidth]{fig_*}` (single column).
Simulation subfigure pairs use `\minipage[b]{0.48\columnwidth}` side-by-side layout.

## ProVerif analysis summary

- **File:** `ProVerif-Security-Analysis/Revised_Anonymity_Scheme.pv`
- **Tool:** ProVerif 2.x under Dolev–Yao adversary model
- **Result:** All **19 queries satisfied** (`true`)
- **Query breakdown:**
  - Q1–Q2: Enrollment correspondence (injective + non-injective)
  - Q3–Q6: Two-round authentication correspondence (both rounds, both directions)
  - Q7: Cross-round binding (GW links auth round 1 to key exchange)
  - Q8–Q9: Token delivery and data communication correspondence
  - Q10–Q12: Session key (`SK`) secrecy — three views (D, AS, GW)
  - Q13: `m_new` forward secrecy (new nonce not derivable from old state)
  - Q14: `R_D` (PUF response) secrecy
  - Q15: `ID_D` anonymity (real identity not derivable)
  - Q16: `ts_2` (timestamp) secrecy
  - Q17–Q19: Weak secrecy (offline dictionary/guessing resistance)
- **Verification output image:** `ProVerif-Security-Analysis/Revised_Anonymity_Proverif.png`
- **Partial log:** `ProVerif-Security-Analysis/Revised_Anonymity_output.txt` (Docker crashed mid-run; covers Q1–Q4)

## Key notation used in the paper

| Symbol | Meaning |
|---|---|
| `ID_D` | Real device identity (never sent on open channel in this scheme) |
| `PID = H(ID_D \|\| m_curr)` | Current session pseudonym |
| `PID_curr`, `PID_old` | Dual-state pseudonym pair stored at AS and GW |
| `m_curr`, `m_old` | Dual-state nonce pair stored at AS and GW |
| `SK` | Session key established in Phase 3 |
| `R_D` | PUF response (device secret, never stored) |
| `ts_2` | Timestamp from Phase 2 |
| AS | Authentication Server (gateway-selected, any capable node) |
| GW | Gateway |
| D | Device (IoT node) |

## Workflow notes

- The paper is compiled on **Overleaf**. Figures are not in the git repo — upload them manually using the filenames in the table above.
- When editing the `.tex` file, always check that float barriers are in place before any `\section{}` that follows a figure-heavy section.
- The `\balance` package is loaded to equalize the two columns on the last page; call `\balance` just before `\section{Conclusion}` if needed.
- Performance evaluation: COOJA simulation (100-mote networks, RPL Lite routing, CSMA/802.15.4). All evaluation charts are COOJA-based.
- **Four distinct schemes — do NOT conflate them (esp. DAuth vs LAAKA):**
  - **Proposed** — this paper (Anup's MTP).
  - **DAuth** — the base/predecessor scheme = das2026comsnets (Das & Khatua, COMSNETS 2026). Used for the 26.8% byte-overhead claim and the desync-recovery comparison; code in `Manual-COOJA/DAuth-COOJA/`, `Hardware/DAuth/`, `Hardware/Base-Scheme/`.
  - **LAAKA** — a **completely separate** scheme: Hala Ali & Irfan Ahmed, "LAAKA: Lightweight Anonymous Authentication and Key Agreement Scheme for Secure Fog-Driven IoT Systems," Computers & Security 140 (2024) 103770 (Elsevier, VCU). **This is NOT das2026comsnets.** Code in `LAAKA/` (as-node.c, device-node.c, gw-node.c) and `Hardware/LAAKA/`; paper PDF at `LAAKA/LAAKA.pdf`.
  - **Zhou** — see next bullet.
- **Main COOJA evaluation charts now plot FOUR schemes — Proposed, DAuth, LAAKA, Zhou.** DAuth was added as a 4th series (purple `#7E5BA6`, dot hatch `...`) to `fig_sim_total`, `fig_sim_as_energy/cpu`, and `fig_sim_net_energy/cpu`; the desync chart relabels its "Base" bar to "DAuth". DAuth COOJA data comes from `Revised-Anonymity/Src-DAuth/` (3-phase, PID-stripped, fair delta enrollment) via `Scripts/Simulation-Runners/run_dauth_sweep.py`, with results under `Results/COOJA-Simulation/DAuth-Sweep/` (as-/network-variation) and `Results/COOJA-Simulation/10-Seed-Comparison/DAuth/` (total). Result: DAuth sits just below Proposed everywhere (Proposed pays ~8% for PID anonymity), both far below LAAKA/Zhou; enrollment is now fairly comparable (DAuth ~24.6 vs Proposed ~23.2 mJ).
- The **hardware** evaluation chart (`fig_hw_comparison.png`) now plots **Proposed, DAuth, LAAKA, Zhou** — DAuth added (purple `#7E5BA6`, dot hatch `...`). DAuth hardware data: **3 RPi 4B runs** (Apex=device, Pi=AS, Laptop=GW), 1 warm-up round discarded per run; results in `Hardware/DAuth/results/`. Auth+KeyEx per round: **0.152 J ± 0.010 J**, **0.040 s ± 0.003 s**. Enrollment: 0.255 J / 0.067 s. Order: DAuth (0.152 J) < Proposed (0.286 J) < Zhou (0.333 J) < LAAKA (0.602 J). Charts have per-bar value labels.
- **Zhou scheme implemented:** Xin Zhou et al., "Security-Enhanced Lightweight and Anonymity-Preserving User Authentication Scheme for IoT-Based Healthcare," IEEE IoT Journal, Vol. 11, No. 6, 2024. Source code in `Zhou-Scheme/`. **Distinct from** `zhou2021iot` (I. Zhou et al., IEEE Access 2021, IoT survey paper — used only in the Introduction as a general IoT reference).
