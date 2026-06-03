"""
parse_results.py
Parse the 100-node base scheme COOJA log and save per-device energy/CPU to CSV.

Log source: Simulation/100(Single Auth +data)1.txt
Measurement: "authentication 1" delta (after-registration minus before-registration snapshot)
             → covers combined auth + key-exchange phase of the base scheme.
             Units: CPU time in seconds, energy in Joules (converted to mJ here).

Output: results/base_scheme_100node.csv
"""

import re, csv, os

LOG_PATH = os.path.join(os.path.dirname(__file__),
                        "Simulation", "100(Single Auth +data)1.txt")
OUT_DIR  = os.path.join(os.path.dirname(__file__), "results")
OUT_CSV  = os.path.join(OUT_DIR, "base_scheme_100node.csv")

# Pattern for auth measurement lines
PAT_AUTH = re.compile(
    r"ID:(\d+)\s+The CPU time and energy at the end of authentication \d+ "
    r"for client (\d+) are ([\d.]+) and ([\d.]+)"
)

os.makedirs(OUT_DIR, exist_ok=True)

records = []
with open(LOG_PATH) as f:
    for line in f:
        m = PAT_AUTH.search(line)
        if m:
            node_id    = int(m.group(2))
            cpu_s      = float(m.group(3))   # seconds
            energy_j   = float(m.group(4))   # Joules
            energy_mj  = energy_j * 1000.0   # millijoules
            records.append((node_id, cpu_s, energy_j, energy_mj))

records.sort(key=lambda r: r[0])

with open(OUT_CSV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Device", "Auth_CPU_s", "Auth_Energy_J", "Auth_Energy_mJ",
                "Phase_Covered", "Num_Seeds"])
    for node_id, cpu_s, energy_j, energy_mj in records:
        w.writerow([node_id,
                    f"{cpu_s:.6f}",
                    f"{energy_j:.6f}",
                    f"{energy_mj:.4f}",
                    "Auth+KeyEx",
                    1])

print(f"Saved {len(records)} device records to {OUT_CSV}\n")
print(f"{'Device':>8}  {'CPU (s)':>10}  {'Energy (mJ)':>13}")
print("-" * 38)
for node_id, cpu_s, energy_j, energy_mj in records:
    print(f"{node_id:>8}  {cpu_s:>10.6f}  {energy_mj:>13.4f}")

import statistics
cpus    = [r[1] for r in records]
energies = [r[3] for r in records]
print("-" * 38)
print(f"{'Mean':>8}  {statistics.mean(cpus):>10.6f}  {statistics.mean(energies):>13.4f}")
print(f"{'Std':>8}  {statistics.stdev(cpus):>10.6f}  {statistics.stdev(energies):>13.4f}")
print(f"{'Min':>8}  {min(cpus):>10.6f}  {min(energies):>13.4f}")
print(f"{'Max':>8}  {max(cpus):>10.6f}  {max(energies):>13.4f}")
