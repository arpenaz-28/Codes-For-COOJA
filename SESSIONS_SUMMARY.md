# Session History Summary
**Project:** Lightweight, Anonymous, and Decoupled Distributed Authentication for Multihop IoT Networks
**Author:** Anup Kulkarni — IIT Guwahati MTP Thesis
**Paper file:** `Paper/paper_revised_anonymity.tex`

---

## Session 1 — 7 Mar 2026: Project Initialisation
**What was done:**
- Created the repository and initial workspace structure.
- Established three scheme folders: `Revised-Anonymity/`, `LAAKA/` (base scheme), `Zhou-Scheme/`.
- Added first README documenting the simulation setup and performance charts.
- Initial COOJA simulation scripts added for Contiki-NG.

**Key output:** Project scaffold, first simulation results.

---

## Session 2 — 13 Mar 2026: Hardware PUF Implementation
**What was done:**
- Added native hardware PUF simulation (`Hardware/pypuf/`).
- Documented workspace structure and COOJA simulation paths.
- Synced Codes-For-COOJA workspace structure across machines.

**Key output:** `Hardware/` PUF native runtime.

---

## Session 3 — 26–28 Mar 2026: Zhou Scheme + Three-Scheme Comparison
**What was done:**
- Added Zhou scheme (Xin Zhou et al., IEEE IoT Journal 2024) COOJA simulation.
- Generated first three-scheme comparison charts: Proposed vs LAAKA vs Zhou.
- Added total-all-nodes cost chart (chart showing combined device energy).
- Restructured results folders; fixed Zhou CSV parsing.

**Key output:** First Proposed vs LAAKA vs Zhou energy/CPU comparison charts.

---

## Session 4 — 31 Mar 2026: Revised-Anonymity as Final Scheme
**What was done:**
- Established `Revised-Anonymity` as the final proposed scheme (replacing earlier `Extended` scheme).
- Ran COOJA simulations: 20-node network, 5 seeds, TelosB emulated platform.
- Added CPU time comparison charts alongside energy charts.
- Added combined chart (all schemes × all phases on one plot).

**Key numbers established:**
- Proposed: 52.21 mJ, 0.847 s — 42.8% lower energy than LAAKA, 34.6% lower than Zhou.

**Key output:** `Results/Charts/Revised-vs-LAAKA-vs-Zhou/` — 18 charts including `18_total_all_phases.png`.

---

## Session 5 — 7–8 May 2026: Network Variation Study + Paper Draft
**What was done:**
- Ran network variation study: 60 simulations across 3 schemes × 4 network sizes (N=20,40,60,100) × 5 seeds.
- Added charts 12 and 13: total energy and total CPU grouped bar charts vs network size.
- Added AS (Authenticator) pool variation study: 20 devices, AS count from 2 to 15.
- Wrote first paper draft (`Paper/paper_revised_anonymity.tex`) in IEEE two-column format.
- Added sections: Introduction, Literature Survey, Prerequisites, Base Scheme, Proposed Scheme, Security Analysis, Performance, Conclusion.
- Added `CLAUDE.md` with full project context, figure filenames, LaTeX conventions.
- Added protocol phase diagrams (Visio source files and exported images).
- Updated paper: inlined equations, unique secret for y_D, scheme scope limited to key exchange.
- Added Zhong et al. 2025 survey citation; removed 5 unused bibliography entries.
- Defined "Decoupled" term precisely: enrollment-authentication separation.

**Key output:** Full paper draft, `Results/Charts/Network_variation/`, `Results/Charts/Authenticator_variation/`.

---

## Session 6 — 9–10 May 2026: Chart Redesign + Paper Polish
**What was done:**
- Redesigned charts 12 & 13: muted palette, clean typography, value labels added.
- Removed TikZ desync figure from paper (replaced with prose).
- Clarified desync recovery description in paper: device must re-authenticate (not re-enrol) in proposed scheme.
- Restated AS pool variation study charts and SUMMARY docs.
- Removed `*.pdf` from `.gitignore`; committed all PDFs including base scheme paper.
- Restyles comparison charts: paper-matching hollow-hatch bar style, Liberation Sans font, bold labels.

**Key output:** Polished chart set, PDF files committed, SUMMARY docs added.

---

## Session 7 — 15–17 May 2026: Merge Conflict Resolution + Folder Reorganisation
**What was done:**
- Resolved merge conflicts between local and remote: kept simulation-based paper with polished abstract.
- Reorganised folder structure: scheme-specific source under `Revised-Anonymity/Src/`, `Base-Scheme/Src/`, `Zhou-Scheme/Src/`.
- Added Zhou scheme source data CSVs and reference PDF.
- Fixed chart 10 (integer x-axis ticks), fixed Zhou CSV parsing edge case.
- Updated paper for chart-text consistency.

**Key output:** Clean folder structure, resolved conflicts.

---

## Session 8 — 22 May 2026: Paper Prose + Chart Text Fixes
**What was done:**
- Converted inline arrow-notation state updates (e.g. `m_curr ← m_new`) to prose descriptions throughout paper.
- Fixed discrepancies between chart values and in-text numbers.
- Updated "Proposed" label in all charts (was "Revised-Anonymity").
- Increased font sizes and moved legend positions in charts.
- Copied final chart PNGs into `Paper/` folder with Overleaf-ready filenames (`fig_sim_total.png`, `fig_sim_net_energy.png`, etc.).

**Key output:** Paper and charts in sync; Paper figures committed.

---

## Session 9 — 24 May 2026: Small Network Variation + Desync Recovery Charts (Analytic)
**What was done:**

### Small network variation (N=10, 20, 30):
- Ran `run_small_network_variation.py`: COOJA simulations for 3 schemes × 3 network sizes × 5 seeds.
- Results stored in `Results/Small-Network-Variation/CSV-Data/{RA,LAAKA,Zhou}/N{10,20,30}/summary.csv`.
- Generated 12 charts: per-phase line charts + grouped bar totals + combined phase overlay.

### Desync recovery comparison (analytic estimate):
- Created `Results/Desync-Recovery-Analysis/` with two 4-bar before/after charts.
- These used existing `comparison_summary.csv` values (analytic arithmetic, no new simulation).
- Before loss = Enrollment + Auth+KeyEx; After loss = Proposed: Auth+KeyEx only / Base: Enrollment + Auth+KeyEx.
- Fixed logical error: "After loss" for Proposed is NOT free — it costs Auth+KeyEx (28.87 mJ).
- Applied full paper chart style: hollow-hatch bars, Liberation Sans, bold labels, error bars.
- Legend moved to upper left so all bars are visible.

**Key output:**
- `Results/Small-Network-Variation/Charts/` — 12 charts.
- `Results/Desync-Recovery-Analysis/01_energy_before_after.png`, `02_cpu_before_after.png`.

---

## Session 10 — 25 May 2026: Actual COOJA Desync Demo Simulations
**What was done:**

### Infrastructure:
- Added `Revised-Anonymity/Src-DesyncDemo/device-node.c`: ENERGEST energy/CPU logging added for 5 rounds (ENROLL, ROUND1–ROUND4). Logs `DESYNC_*_ENERGY|node|cpu_s=X|energy_j=X` lines.
- Created `Base-Scheme/Src-DesyncDemo/`: full 4-round desync demo for base scheme. Round 3 = auth fails → forced re-enrolment → retry auth. Fixed build error: `COAP_BLOCKING_REQUEST` inlined directly in `PROCESS_THREAD` (cannot be called from a regular function).
- Created `Scripts/Simulation-Runners/run_desync_demo.py`: COOJA runner for both schemes. Generates CSC, runs headless, parses logs, writes CSV. Fixed TESTLOG path (`COOJA.testlog` in COOJA working dir, not `TEST_OK.log`).
- Created `Scripts/Simulation-Runners/plot_desync_demo_results.py`: 6-chart generator from simulation CSVs.
- Created `Scripts/Simulation-Runners/plot_desync_sim_before_after.py`: clean 4-bar before/after chart in paper style, using actual simulation data.

### Simulation results (5 seeds × 3 devices = 15 data points per scheme per round):

| Round | Proposed | Base |
|---|---|---|
| ENROLL | 786.81 mJ | 774.27 mJ |
| ROUND1 (Normal auth) | 14.51 mJ | 24.92 mJ |
| ROUND2 (Packet drop) | 10.71 mJ | 6.80 mJ |
| **ROUND3 (Recovery)** | **14.34 mJ** | **30.42 mJ** |
| ROUND4 (Post-recovery) | 14.35 mJ | — (timeout) |

### Key finding:
**Proposed recovery (ROUND3) = 14.34 mJ ≈ Normal auth (ROUND1) = 14.51 mJ** — dual-state lookup is completely transparent from device energy perspective. The extra `memcmp(PID_old)` lookup happens on the AS, not the device.

**Base recovery (ROUND3) = 30.42 mJ = 2.12× more than Proposed** — due to 5 CoAP round-trips (failed auth + 2 re-enrol steps + retry auth + data) vs 2 for Proposed. Dominated by extra radio TX/RX time, not computation.

### What ENERGEST measures:
- CPU active time × 1.8 mA × 3.0 V
- LPM time × 0.0545 mA × 3.0 V
- Radio TX time × 17.4 mA × 3.0 V
- Radio RX/listen time × 18.8 mA × 3.0 V
- SHA256, AES, XOR all run on CPU — fully included in energy measurement.

### Charts produced (paper style, hollow-hatch bars):
- `Results/Desync-Demo/Charts/sim_01_energy_before_after.png` — **the key paper chart**
- `Results/Desync-Demo/Charts/sim_02_cpu_before_after.png`
- `Results/Desync-Demo/Charts/01_energy_per_round.png` through `06_recovery_overhead_cpu.png`

**Key output:** Real COOJA desync simulation with deliberate packet drop. Before loss = ROUND1 (normal auth). After loss = ROUND3 (recovery session). Paper-ready charts at `Results/Desync-Demo/Charts/`.

---

## Current Paper Status

| Section | Status |
|---|---|
| I — Introduction | Complete |
| II — Literature Survey | Complete |
| III — Prerequisites | Complete |
| IV — Base Scheme | Complete |
| V — Proposed Scheme | Complete (desync recovery subsection verified by simulation) |
| VI — Security Analysis | Complete (ProVerif 19/19 queries satisfied) |
| VII — Performance Analysis | Complete (simulation + HW + desync demo) |
| VIII — Conclusion | Complete |

## Key File Locations

| Purpose | Path |
|---|---|
| Paper | `Paper/paper_revised_anonymity.tex` |
| Main comparison charts | `Results/Charts/Revised-vs-LAAKA-vs-Zhou/` |
| Network variation charts | `Results/Charts/Network_variation/` |
| AS variation charts | `Results/Charts/Authenticator_variation/` |
| Small network (N=10/20/30) | `Results/Small-Network-Variation/Charts/` |
| Desync demo charts (paper-ready) | `Results/Desync-Demo/Charts/sim_01_energy_before_after.png` |
| Desync demo raw logs | `Results/Desync-Demo/{Proposed,Base}/logs/` |
| Simulation runner scripts | `Scripts/Simulation-Runners/` |
| ProVerif analysis | `ProVerif-Security-Analysis/` |
| Source code (proposed) | `Revised-Anonymity/Src/` |
| Source code (base scheme) | `Base-Scheme/Src/` |
| Source code (Zhou scheme) | `Zhou-Scheme/Src/` |
