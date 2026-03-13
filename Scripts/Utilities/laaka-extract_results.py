"""Parse LAAKA COOJA simulation log and extract AUTH_ENERGY results for
device nodes 81-100 to CSV, with tabular summary for comparison."""
import re
import csv

LOG_FILE = r"c:\ANUP\MTP\Proposing\Codes For COOJA\LAAKA\COOJA-100node-testlog.txt"
CSV_FILE = r"c:\ANUP\MTP\Proposing\Codes For COOJA\LAAKA\simulation-results.csv"

# Device range
DEV_START = 81
DEV_END = 100

pattern = re.compile(
    r"AUTH_ENERGY\|(\d+)\|cpu_ticks=(\d+)\|energy_ticks=(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)"
)

# Collect FIRST measurement per device (initial auth+ack+data cycle)
first_seen = {}
with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        m = pattern.search(line)
        if m:
            dev_id = int(m.group(1))
            if DEV_START <= dev_id <= DEV_END and dev_id not in first_seen:
                first_seen[dev_id] = {
                    "Device_ID": dev_id,
                    "CPU_Ticks": int(m.group(2)),
                    "Energy_Ticks": int(m.group(3)),
                    "CPU_Time_s": float(m.group(4)),
                    "Energy_J": float(m.group(5)),
                }

rows = sorted(first_seen.values(), key=lambda r: r["Device_ID"])

# Write CSV
with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Device_ID", "CPU_Ticks", "Energy_Ticks", "CPU_Time_s", "Energy_J"])
    writer.writeheader()
    writer.writerows(rows)

# Print tabular summary
print(f"\n{'='*65}")
print(f"  LAAKA Scheme — Auth+Data Energy Results (Nodes {DEV_START}-{DEV_END})")
print(f"  Topology: 1 GW + 79 Fog AS + 20 Devices")
print(f"  Devices 81-90 -> Fog 2,  Devices 91-100 -> Fog 3")
print(f"{'='*65}")
print(f"{'Device':>8}  {'Fog':>4}  {'CPU_Time(s)':>12}  {'Energy(J)':>12}")
print(f"{'-'*8}  {'-'*4}  {'-'*12}  {'-'*12}")
for r in rows:
    fog = "F2" if r["Device_ID"] < 91 else "F3"
    print(f"{r['Device_ID']:>8}  {fog:>4}  {r['CPU_Time_s']:>12.6f}  {r['Energy_J']:>12.6f}")

if rows:
    energies = [r["Energy_J"] for r in rows]
    cpu_times = [r["CPU_Time_s"] for r in rows]
    print(f"{'-'*8}  {'-'*4}  {'-'*12}  {'-'*12}")
    print(f"{'Min':>8}  {'':>4}  {min(cpu_times):>12.6f}  {min(energies):>12.6f}")
    print(f"{'Max':>8}  {'':>4}  {max(cpu_times):>12.6f}  {max(energies):>12.6f}")
    print(f"{'Avg':>8}  {'':>4}  {sum(cpu_times)/len(cpu_times):>12.6f}  {sum(energies)/len(energies):>12.6f}")
    print(f"{'='*65}")
    print(f"\nExtracted {len(rows)} device results to {CSV_FILE}")
