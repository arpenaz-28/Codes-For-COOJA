# PUF-Based IoT Authentication - COOJA Simulations

Master's Thesis Project: formal verification and performance evaluation of lightweight PUF-based authentication schemes for constrained IoT motes.

## Overview


This repository contains implementation, simulation, and security analysis artifacts for multiple IoT authentication schemes in Contiki-NG/COOJA:

- Base Scheme (reference implementation)
- LAAKA
- Proposed Anonymity-Extended Base Scheme
- Desynchronization-resilience scenario for the proposed scheme
- **Zhou-Scheme** (Security-Enhanced Lightweight and Anonymity-Preserving User Authentication Scheme for IoT-Based Healthcare, IEEE IoT J 2024)

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
| `Zhou-Scheme/` | Zhou et al. 2024 scheme: source, 100-node simulation, and protocol README |
| `Hardware/` | Laptop + RPi deployment package with native GW/AS/Node runtime and pypuf-based authentication |
| `Results/CSV-Data/` | Final CSV outputs for per-scheme and cross-scheme comparison |
| `Results/Charts/` | Final chart outputs, including aligned and scalability analyses |
| `Results/Testlogs/` | COOJA logs organized by scheme and study type |
| `Scripts/Simulation-Runners/` | Automation scripts for running experiments and generating charts |
| `Scripts/Utilities/` | Parsing, extraction, and helper utilities |
| `ProVerif-Security-Analysis/` | Protocol models, outputs, and security chart snapshots |
| `proverif2.05/` | Local ProVerif distribution source and examples |
## Zhou-Scheme (2024)

**Zhou-Scheme** implements the protocol from:

> "Security-Enhanced Lightweight and Anonymity-Preserving User Authentication Scheme for IoT-Based Healthcare" (Zhou et al., IEEE IoT Journal, 2024)

Features:
- Three-entity protocol: User, Gateway, Sensor Node
- PUF-based device binding, fuzzy extractors, secret salt, and pseudonym rotation
- 100-node simulation scenario (`Zhou-Scheme/test-sim-100.csc`)
- Full source: `user-node.c`, `sn-node.c`, `gw-server.c`, `gw-node.c`
- See `Zhou-Scheme/README.md` for protocol details and build/run instructions

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

## Hardware Runtime (Laptop + 2x RPi)

Hardware deployment assets are in `Hardware/` and include:

- Native role runtimes: `Hardware/native/gw_hw.py`, `Hardware/native/as_hw.py`, `Hardware/native/node_hw.py`
- Setup and orchestration scripts in `Hardware/scripts/`
- IP-based role configuration in `Hardware/config/roles.env`

The native flow keeps the scheme sequence: Enrollment -> Authentication with pypuf CRP verification -> AS to GW token forwarding -> encrypted Node to GW data.

If only IP addresses are available, set `GW_HOST`, `AS_HOST`, and `NODE_HOST` in `Hardware/config/roles.env`; usernames default to `pi` in orchestration scripts when left blank.

## Notes

- This repository includes source code, logs, CSVs, and generated plots used in thesis experiments.
- Some folders contain large collections of generated artifacts by design to preserve experiment reproducibility.

## License

Part of an academic master's thesis workflow. Reuse should follow your institutional and publication policies.
