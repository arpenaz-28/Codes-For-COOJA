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
3. **Performance claim (current paper):** COOJA per-device total energy (10-seed, N=100, 2 AS) — Proposed 52.19 mJ, DAuth 48.08 mJ, **LAAKA 57.68 mJ** (corrected; was 91.29 due to double-counting bug), Zhou 77.25 mJ. Ordering: DAuth < Proposed < LAAKA < Zhou on both COOJA and hardware. Proposed reduces energy **9.5% vs LAAKA and 32.4% vs Zhou**; DAuth (non-anonymous baseline) is 7.9% cheaper than Proposed — this is the anonymity overhead. Hardware (auth+keyex phase, MIRACL Core): Proposed 0.0617 J, DAuth 0.0611 J, LAAKA 0.0959 J, Zhou 0.1074 J; proposed is 36% below LAAKA and 43% below Zhou. No ordering reversal between platforms. Hardware energy = wall_time × 3800 mW everywhere.

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
| `fig_hw_comparison.png` | `Hardware/MIRACLE/Authentication&KeyExchange_HW.png` | Hardware — auth+keyex phase energy and CPU time on RPi 4B, MIRACL Core (Proposed/DAuth/LAAKA/Zhou); title-free, (a)/(b) only |

All phase figures are referenced with `\includegraphics[width=\columnwidth]{fig_*}` (single column).
Simulation subfigure pairs use `\minipage[b]{0.48\columnwidth}` side-by-side layout.

## ProVerif analysis summary

- **File:** `ProVerif-Security-Analysis/Revised_Anonymity_Scheme.pv`
- **Tool:** ProVerif 2.x under Dolev–Yao adversary model
- **Result:** All **10 queries satisfied** (`true`). The committed `.pv`, the paper prose ("Ten queries… all satisfied"), and the figure `Paper/fig_proverif.png` (final, supplied 2026-06-20) all agree on these 10.
- **Query breakdown (matches committed `.pv` + figure):**
  - Q1–Q5: Correspondence — inj DeviceEnrolled, inj DeviceAuthenticated, inj AuthenticationServerEnds, inj AuthenticationEndsFull (binds auth↔keyex via R_D, m_D), non-inj DeviceKeyExDone
  - Q6–Q7: Session key (`K_GW-D`) secrecy — two views (Device, GW)
  - Q8: `m_new` forward secrecy
  - Q9: `ID_D` anonymity (real identity not derivable)
  - Q10: Weak secrecy of `K_GW-D` (offline guessing resistance)
- **Verification output image (final):** `Paper/fig_proverif.png` — shows all 10 as `is true`.
- NOTE: an earlier draft / CLAUDE.md claimed "19 queries" and a partial crash log — that is superseded; the live model and figure have 10.

## Key notation used in the paper

| Symbol | Meaning |
|---|---|
| `ID_D` | Real device identity (never sent on open channel in this scheme) |
| `PID = H(ID_D \|\| m_curr)` | Current session pseudonym |
| `PID_curr`, `PID_old` | Dual-state pseudonym pair stored at AS (GW stores only the current PID) |
| `m_curr`, `m_old` | Dual-state nonce pair stored at AS (GW stores only the current PID) |
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
- The **hardware** evaluation chart (`fig_hw_comparison.png`) plots **Proposed, DAuth, LAAKA, Zhou**. **Authoritative source = `Hardware/MIRACLE/` only** (runs 2026-06-20, RPi 4B, MIRACL Core NIST P-256, governor pinned, energy = wall × 3.8 W, median of 7 runs, warm-up discarded). Generated by `Hardware/MIRACLE/plot_auth_keyex.py` (writes to both MIRACLE and `Paper/fig_hw_comparison.png`). Auth+KeyEx per round: **Proposed 0.0617 J / 0.0162 s ≈ DAuth 0.0611 J / 0.0161 s < LAAKA 0.0959 J / 0.0253 s < Zhou 0.1074 J / 0.0282 s**. Paper claims (correct vs this data): Proposed≈DAuth (<1%), both beat LAAKA ~36% and Zhou ~43%. **All other `Hardware/` contents moved to `Hardware/_archive_pre_miracle/` (stale/inconsistent — do not cite).** Note ordering vs COOJA is reversed for LAAKA/Zhou (COOJA: LAAKA>Zhou; HW: Zhou>LAAKA).
- **Zhou scheme implemented:** Xin Zhou et al., "Security-Enhanced Lightweight and Anonymity-Preserving User Authentication Scheme for IoT-Based Healthcare," IEEE IoT Journal, Vol. 11, No. 6, 2024. Source code in `Zhou-Scheme/`. **Distinct from** `zhou2021iot` (I. Zhou et al., IEEE Access 2021, IoT survey paper — used only in the Introduction as a general IoT reference).
