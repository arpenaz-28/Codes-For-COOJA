# Compute-only MIRACL hardware benchmark (RPi 4B) — ARCHIVE, NOT IN PAPER

> **Status:** exploratory / archival. This work is **deliberately kept out of the
> paper.** It is preserved here (logs, source, results, chart, aggregated values)
> as a self-contained record of the MIRACL-based compute re-measurement.

Companion analysis to the **network-bound** end-to-end hardware chart
(`Hardware/Charts/hw_total_comparison.png`). This isolates **pure cryptographic
computation** measured live on an RPi 4B via **MIRACL Core (NIST P-256)** — each
scheme's actual operation sequence is executed (no TCP), so Zhou's ECC fuzzy
extractor is faithfully exercised.

## Files in this folder

| File | What |
|---|---|
| `scheme_compute_bench.c` | C benchmark (MIRACL Core API) — runs each scheme's op-sequence |
| `run_01.csv` … `run_03.csv` | raw per-run output (`scheme,phase,mean_ms,sd_ms,iters`) |
| `plot_compute_miracl.py` | self-contained aggregator + plotter (reads/writes this dir) |
| `compute_miracl_aggregate.json` | aggregated values (mean of 3 runs) |
| `hw_compute_miracl.png` | dual-panel chart (compute energy + compute time) |
| `build_run.log` | build + run console log from the RPi |

## How it was produced

- Built against the existing MIRACL Core `core.a` on `apex@192.168.1.132`
  (`~/miracl_bench/work/`), `gcc -O2`, NIST P-256, RPi 4B @ 1.8 GHz, governor
  `ondemand`.
  ```bash
  scp scheme_compute_bench.c apex@192.168.1.132:~/miracl_bench/work/
  ssh apex@192.168.1.132 'cd ~/miracl_bench/work && \
      gcc -O2 scheme_compute_bench.c miracl_core/core.a -lm -o scheme_compute_bench && \
      ./scheme_compute_bench'
  ```
- Per phase: 200 warm-up + 2000 measured iterations, `CLOCK_MONOTONIC`.
- 3 runs captured: `run_01.csv`, `run_02.csv`, `run_03.csv`.
- Op-counts identical to the paper's `tab:comp_total` /
  `Scripts/Simulation-Runners/plot_comparison_kim_rpi.py`.
- Energy = compute_time x 3.8 W (same 3800 mW power model as end-to-end chart).
- Regenerate chart + JSON locally: `python plot_compute_miracl.py`.

## Results (per-round / Auth phase, mean of 3 runs)

| Scheme   | Compute time (ms) | Compute energy (mJ) |
|----------|-------------------|---------------------|
| DAuth    | 0.0201            | 0.0764              |
| LAAKA    | 0.0239            | 0.0908              |
| Proposed | 0.0246            | 0.0936              |
| Zhou     | 1.1171            | 4.2450              |

**Zhou is ~45x the heaviest non-ECC scheme** — its two ECC fuzzy-extractor
operations dominate. Proposed/DAuth/LAAKA are all sub-0.1 mJ of computation.

## Why it is not in the paper (number-consistency note)

The paper's `tab:comp_total` uses Kim et al.'s **reference** RPi 4B unit costs
(1.5 GHz, T_fe = 2.353 ms) → Proposed 0.150 ms, Zhou 4.872 ms. This benchmark
used **our own RPi 4B at 1.8 GHz**, giving faster absolute times
(T_fe = T_M ≈ 1.10 ms) → Proposed 0.0246 ms, Zhou 1.117 ms. The two agree in
**structure and ranking** (Zhou FE-dominated; the other three ~50x lighter) and
differ in absolute scale only because of clock speed / build flags. To avoid
presenting two conflicting absolute-number sets for "RPi 4B," this measured set
is archived here rather than added to the paper.
