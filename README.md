# PUF-Based IoT Authentication - COOJA Simulations

Master's Thesis Project: formal verification and performance evaluation of lightweight PUF-based authentication schemes for constrained IoT motes.

## Overview

This repository contains implementation, simulation, and security analysis artifacts for multiple IoT authentication schemes in Contiki-NG/COOJA:

- Base Scheme (reference implementation)
- LAAKA
- Proposed Anonymity-Extended Base Scheme
- Desynchronization-resilience scenario for the proposed scheme

Core protocol features in the proposed scheme include:

- PUF-based device binding
- PID pseudonym rotation for anonymity
- dual-state recovery (current/old state) for desync tolerance
- lightweight AES-128 and SHA-256 usage in constrained nodes

## Repository Structure

| Path | Purpose |
|------|---------|
| `Anonymity-Extended-Base-Scheme/` | Proposed scheme source, simulation files, and scheme-specific README |
| `Base-Scheme/` | Base scheme source and related simulation assets |
| `Base-Scheme-Aligned/` | Aligned base variant used for fairer comparison experiments |
| `LAAKA/` | LAAKA scheme implementation and simulation setup |
| `Desync-Anonymity-Extended-Base-Scheme/` | Desynchronization experiment setup |
| `Results/CSV-Data/` | Final CSV outputs for per-scheme and cross-scheme comparison |
| `Results/Charts/` | Final chart outputs, including aligned and scalability analyses |
| `Results/Testlogs/` | COOJA logs organized by scheme and study type |
| `Scripts/Simulation-Runners/` | Automation scripts for running experiments and generating charts |
| `Scripts/Utilities/` | Parsing, extraction, and helper utilities |
| `ProVerif-Security-Analysis/` | Protocol models, outputs, and security chart snapshots |
| `proverif2.05/` | Local ProVerif distribution source and examples |

## Key Results Assets

Representative final charts are located in `Results/Charts/`:

- `Final-01-Energy-Comparison.png`
- `Final-02-CPU-Time-Comparison.png`
- `Final-03-Total-Protocol-Cost.png`
- `Final-04-Computation-Only-Energy.png`
- `Final-05-Comparison-Table.png`

Main comparison CSV is available at:

- `Results/CSV-Data/all-schemes-comparison.csv`

## Build and Run (Docker + COOJA)

Example using the proposed scheme folder on Windows PowerShell:

```powershell
docker run -d --name cooja-sim `
  -v "${PWD}\Anonymity-Extended-Base-Scheme:/opt/contiki-ng/examples/myproject" `
  contiker/contiki-ng tail -f /dev/null

docker exec cooja-sim bash -c "cd /opt/contiki-ng/examples/myproject && make TARGET=cooja"

docker exec cooja-sim bash -c "cd /opt/contiki-ng/tools/cooja && ./gradlew --no-watch-fs run --args='--no-gui --contiki=/opt/contiki-ng --autostart /opt/contiki-ng/examples/myproject/test-sim-100.csc'"
```

## ProVerif Analysis

Run protocol verification from `ProVerif-Security-Analysis/`:

```powershell
cd ProVerif-Security-Analysis
docker build -t proverif-tool .
docker run --rm -v "${PWD}:/work" proverif-tool /work/scheme.pv
```

Additional prepared models and outputs are available in the same folder, including `Anonymity_Extended_Scheme.pv` and related output files.

## Notes

- This repository includes source code, logs, CSVs, and generated plots used in thesis experiments.
- Some folders contain large collections of generated artifacts by design to preserve experiment reproducibility.

## License

Part of an academic master's thesis workflow. Reuse should follow your institutional and publication policies.
