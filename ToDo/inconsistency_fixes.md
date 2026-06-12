# Inconsistency Fix Tasks
**Paper:** Lightweight, Anonymous, and Decoupled Distributed Authentication for Multihop IoT Networks  
**Date logged:** 2026-06-12

---

## CRITICAL — Fix before submission

### C1. Wrong reduction percentages vs Zhou
- **Where:** Paper abstract, results section (~line 938–941), conclusion
- **Problem:** Paper claims 34.6% energy / 35.3% CPU reduction over Zhou
- **Actual (from seed_results.csv):** 32.4% for both
- **Fix:** Change both values to **32.4%** everywhere they appear

### C2. Zhou Auth+KeyEx value wrong
- **Where:** Paper results paragraph (~line 943)
- **Problem:** "57.06 mJ for Zhou" — actual CSV mean is 53.94 mJ
- **Fix:** Change 57.06 → **53.94 mJ**

### C3. Zhou uses 10% newly-joined devices in Fig 7 — all cross-scheme comparisons invalid  
- **Where:** `Results/COOJA-Simulation/Charts/Network_variation/network_variation_summary.csv`
- **Problem:** Zhou N=100 uses 10 devices (nodes 91–100); all other schemes use 20 devices (nodes 81–100). Every Zhou bar in Fig 7 represents half as many devices — bars are not comparable.
- **Fix:** **Re-run Zhou network variation** with 20% newly-joined devices (N=30→6, N=50→10, N=80→16, N=100→20, N=120→24) and 10 seeds matching other schemes. Update summary CSV and regenerate charts.

### C4. Zhou has zero Key Exchange data in all COOJA experiments
- **Where:** `Zhou-Scheme/Simulation results/network-variation/N*/csv/keyex-results.csv` (empty); `Results/COOJA-Simulation/10-Seed-Comparison/Zhou/seed_results.csv` (Keyex_Energy_mJ = 0 for all rows)
- **Problem:** Zhou totals in Fig 5 and Fig 7 = Enroll + Auth only. Other schemes include all 3 phases. Paper/captions don't disclose this.
- **Fix:** Either (a) run the Zhou Key Exchange phase in COOJA simulation, or (b) add a disclosure note in the figure caption and paper text.

### C5. Fig 7 paragraph uses stale numbers (based on old 10-device Zhou)
- **Where:** Paper network-variation paragraph (~lines 988–992)
- **Problem:** "898 mJ for LAAKA, 1051 mJ for Zhou" were computed when LAAKA also used 10 devices. LAAKA was later corrected to 20 devices but Zhou was not — numbers are now mixed-basis.
- **Fix:** After C3 is resolved, recompute both totals and rewrite the paragraph with correct values and percentages.

---

## SIGNIFICANT — Fix for correctness

### S1. Paper says "N varied from 50 to 100" — chart covers 30 to 120
- **Where:** Paper ~line 978 (also flagged by guide)
- **Fix:** Change to **"varied from 30 to 120 nodes"**

### S2. Desync chart (Fig 8) wrong label and color for DAuth
- **Where:** `Scripts/Simulation-Runners/plot_desync_bar.py` lines 27–38
- **Problem:** DAuth bar is labeled `"Base"` and colored `#B85C2C` — which is LAAKA's color in every other figure
- **Fix:** Rename `"Base"` → `"DAuth"`, change color `#B85C2C` → `#7E5BA6`. Regenerate `fig_desync_bar.png` and upload to Overleaf.

### S3. DAuth seed 678901 device 97 outlier inflates CI
- **Where:** `Results/COOJA-Simulation/10-Seed-Comparison/DAuth/seed_results.csv` — one row with Enroll_Energy = 237.76 mJ (6–17× normal range of 14–43 mJ)
- **Problem:** Inflates DAuth CI from ~±0.6 mJ to ±2.24 mJ (4× larger than Proposed). Likely a COOJA simulator crash/retry artifact.
- **Fix:** Check the COOJA log for seed 678901. If it's a simulator artifact, exclude that row and recompute DAuth mean/CI for Fig 5.

### S4. Fig 5 vs Fig 7 per-device energy mismatch (4.1% for Proposed)
- **Where:** Cross-figure — Fig 5 Proposed = 52.19 mJ/device vs Fig 7 N=100 Proposed = 54.34 mJ/device
- **Problem:** Both claim N=100 + 20 newly-joined devices but values differ. Likely different active AS counts between experiments.
- **Fix:** Document the AS count used in each figure. If different, add a clarifying note in the paper.

### S5. Zhou AS variation value wrong
- **Where:** Paper ~line 968
- **Problem:** "Zhou's total cost remains flat at approximately 1503 mJ" — actual CSV value is 1544.94 mJ
- **Fix:** Change to **"~1545 mJ"**

### S6. DAuth missing at N=30 in Fig 7
- **Where:** Network variation summary CSV — DAuth has no entry for N=30
- **Problem:** DAuth bar absent at N=30 while all other schemes are present
- **Fix:** Either run DAuth at N=30 (small simulation), or add a caption note explaining data starts at N=50.

---

## MINOR

| ID | Where | Problem | Fix |
|----|-------|---------|-----|
| M1 | `CLAUDE.md` | States "26.8% reduction" — phrase no longer in paper | Remove or update |
| M2 | `Scripts/Simulation-Runners/plot_10seed_comparison.py` line 13 | Docstring lists only {Proposed, LAAKA, Zhou} — DAuth missing | Update docstring |
| M3 | Fig 7 N=100 | Proposed enrollment = DAuth enrollment (24.55 mJ exactly) — verify this is correct in source code | Check COOJA enrollment code for both schemes |

---

## Priority Order

| Priority | Task | Effort |
|----------|------|--------|
| 1 | C3 — Re-run Zhou network variation (20% devices, 10 seeds) | High (COOJA run) |
| 2 | C4 — Fill or disclose Zhou KeyEx=0 | Medium |
| 3 | S2 — Fix desync chart label + color | Low (2 lines + replot) |
| 4 | S3 — Investigate DAuth outlier | Low (check one log) |
| 5 | C1, C2, S1, S5 — Paper text number fixes | Low (text edits) |
| 6 | C5 — Rewrite Fig 7 paragraph after Zhou re-run | Low (after C3 done) |
| 7 | S6 — Run DAuth N=30 or add caption note | Low–Medium |

---

## Ordering Consistency Check

| Figure | Ranking (cheapest → costliest) | Status |
|--------|-------------------------------|--------|
| Fig 5 — 10-seed per-device | DAuth < Proposed < Zhou < LAAKA | OK |
| Fig 6 — AS variation | DAuth < Proposed < Zhou < LAAKA | OK |
| Fig 7 — Network variation N=100 | Mixed-basis — **invalid until C3 fixed** | BROKEN |
| Fig 9 — Hardware | DAuth < Proposed < Zhou < LAAKA | OK |
