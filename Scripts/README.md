# Scripts

Automation and analysis scripts for running COOJA experiments and processing results.

## Simulation-Runners

Scripts that orchestrate Docker-based COOJA simulations and generate charts.

| Script | Purpose |
|--------|---------|
| `run_multi_seed.py` | Run all three schemes with multiple random seeds (5 seeds) |
| `run_extended_only.py` | Re-run the Proposed Scheme after PUF model updates |
| `run_scalability.py` | Scalability study across 1, 5, and 20 device nodes |
| `generate_charts.py` | Generate comprehensive comparison charts |
| `generate_final_charts.py` | Publication-quality charts with multi-seed error bars |
| `generate_scalability_charts.py` | Scalability visualization with theoretical analysis |
| `compare_all_schemes.py` | Cross-scheme comparison CSV and bar charts |

## Utilities

Data extraction, parsing, and helper scripts.

| Script | Purpose |
|--------|---------|
| `base-gen_csc.py` | Generate 100-node COOJA CSC config for Base Scheme |
| `laaka-gen_csc.py` | Generate 100-node COOJA CSC config for LAAKA |
| `extract_all_metrics.py` | Extract Enroll/Auth/KeyEx metrics from any scheme log |
| `extract_desync.py` | Parse desync round data from test logs |
| `extract_laaka.py` | Extract text from LAAKA paper PDF |
| `laaka-extract_results.py` | Extract AUTH_ENERGY from LAAKA logs |
| `aligned_comparison.py` | Fair comparison analysis (total cost and protocol-only) |
| `plot_desync.py` | Desync visualization (timeline, energy, comparison) |
| `base-plot_comparison.py` | Per-device CPU/energy charts for Base Scheme |
| `proposed-plot_comparison.py` | LAAKA vs Proposed scheme comparison charts |
| `proposed-extract_pdf.py` | Extract text from Proposed Scheme paper PDF |
| `proposed-extract_all_metrics.py` | Metric extraction with full statistics |
| `proposed-generate_paper.py` | Auto-generate academic paper as Word document |
| `check_enroll.py` | Verify enrollment success across schemes |
