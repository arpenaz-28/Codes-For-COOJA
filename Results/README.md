# Results

Experimental results from COOJA simulations of all authentication schemes.

## Directory Layout

```
Results/
├── CSV-Data/        # Extracted performance metrics in CSV format
├── Charts/          # Generated comparison and analysis charts
│   ├── Aligned-Comparison/   # Fair cross-scheme comparison charts
│   └── Scalability/          # Scalability study charts
└── Testlogs/        # Raw COOJA simulation output logs
    ├── Base-Scheme/
    ├── LAAKA/
    ├── Proposed-Scheme/
    └── Scalability/
```

## CSV Data

Per-scheme metrics are split by protocol phase:

| File Pattern | Contents |
|-------------|----------|
| `<Scheme>-enroll-results.csv` | Enrollment energy and CPU time per device |
| `<Scheme>-auth-results.csv` | Authentication energy and CPU time per device |
| `<Scheme>-keyex-results.csv` | Key exchange energy and CPU time per device |
| `<Scheme>-simulation-results.csv` | Combined simulation results |
| `all-schemes-comparison.csv` | Cross-scheme comparison summary |
| `scalability-results.csv` | Scalability study (1, 5, 20 devices) |
| `multi-seed-summary.csv` | Multi-seed experiment averages |

## Key Charts

Final comparison charts used in the thesis:

| Chart | Description |
|-------|-------------|
| `Final-01-Energy-Comparison.png` | Total energy per scheme |
| `Final-02-CPU-Time-Comparison.png` | CPU time per scheme |
| `Final-03-Total-Protocol-Cost.png` | Combined protocol cost |
| `Final-04-Computation-Only-Energy.png` | Computation-only energy |
| `Final-05-Comparison-Table.png` | Summary comparison table |
