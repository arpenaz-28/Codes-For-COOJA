# Project Context: IoT Authentication Paper (IIT MTP)

## Paper identity

- **Title:** Lightweight, Anonymous, and Decoupled Distributed Authentication for Multihop IoT Networks
- **Author:** Anup Kulkarni, IIT (MTP thesis)
- **Main file:** `Paper/paper_revised_anonymity.tex`
- **Target venue:** IEEE conference (IEEEtran `conference` documentclass, two-column layout)
- **Base/predecessor scheme:** das2026comsnets (`\cite{das2026comsnets}`) — the earlier paper is `Paper/2026Lightweight and Decoupled Distributed-COMSNETS.pdf`

## Novel contributions of THIS paper (vs base scheme)

1. **Pseudonym rotation (anonymity):** Real device identity `ID_D` is never sent on the open channel. Instead, a rotating pseudonym `PID = H(ID_D || m_curr)` is used, refreshed after each successful key exchange (Phase 3). GW never learns `ID_D`.
2. **Dual-state desynchronization recovery:** Both AS and GW store `(m_curr, m_old, PID_curr, PID_old)`. If D misses a Phase 3 update packet, it still arrives with `PID_old`; AS recognizes it via the dual-state lookup and re-synchronizes — no re-enrollment needed.
3. **Performance claim:** 26.8% reduction in authentication-and-key-exchange byte overhead vs the base scheme (measured on Raspberry Pi 3B+ hardware).

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

All phase figures are referenced with `\includegraphics[width=\columnwidth]{fig_*}` (single column).

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
- Performance evaluation hardware: Raspberry Pi 3B+ (three nodes acting as D, AS, GW).
- The comparison schemes in evaluation charts are: **Proposed** (this paper), **Base** (das2026comsnets), **Zhou** (zhou2021iot).
