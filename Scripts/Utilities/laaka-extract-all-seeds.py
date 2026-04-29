"""Extract LAAKA AUTH_ENERGY results across all 5 seed logs.

Merges results: for each device takes the first successful AUTH_ENERGY
measurement found across seeds, giving a complete 20-device dataset.
Also prints per-seed success counts.
"""
import re
import csv
import os

LOG_DIR = r"c:\ANUP\MTP\Proposing\Codes For COOJA\Results\Testlogs\LAAKA"
OUT_CSV = r"c:\ANUP\MTP\Proposing\Codes For COOJA\Results\CSV-Data\LAAKA\auth-results-all-seeds.csv"

SEEDS = [123456, 234567, 345678, 456789, 567890]
DEV_START, DEV_END = 81, 100

auth_pattern = re.compile(
    r"AUTH_ENERGY\|(\d+)\|cpu_ticks=\d+\|energy_ticks=\d+\|cpu_s=([\d.]+)\|energy_j=([\d.]+)"
)

# per-seed results
seed_results = {}
for seed in SEEDS:
    log_path = os.path.join(LOG_DIR, f"testlog_seed{seed}.txt")
    found = {}
    with open(log_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = auth_pattern.search(line)
            if m:
                did = int(m.group(1))
                if DEV_START <= did <= DEV_END and did not in found:
                    found[did] = {
                        "Device_ID": did,
                        "Fog_ID": 2 if did < 91 else 3,
                        "CPU_Time_s": float(m.group(2)),
                        "Energy_J": float(m.group(3)),
                        "Seed": seed,
                    }
    seed_results[seed] = found

# Print per-seed summary
print(f"\n{'Seed':>10}  {'Successes':>10}  {'Missing Devices'}")
print("-" * 60)
all_devices = set(range(DEV_START, DEV_END + 1))
for seed in SEEDS:
    succeeded = set(seed_results[seed].keys())
    missing = sorted(all_devices - succeeded)
    print(f"{seed:>10}  {len(succeeded):>10}  {missing}")

# Build merged dataset: first success per device across seeds
merged = {}
for seed in SEEDS:
    for did, row in seed_results[seed].items():
        if did not in merged:
            merged[did] = row

covered = set(merged.keys())
missing_all = sorted(all_devices - covered)

print(f"\n{'='*60}")
print(f"Merged across {len(SEEDS)} seeds: {len(merged)}/20 devices covered")
if missing_all:
    print(f"Still missing: {missing_all}")
else:
    print("All 20 devices covered!")

# Print merged table
rows = sorted(merged.values(), key=lambda r: r["Device_ID"])
print(f"\n{'='*65}")
print(f"  LAAKA — Auth+KeyEx Energy (merged from best available seed)")
print(f"{'='*65}")
print(f"{'Device':>8}  {'Fog':>4}  {'CPU_Time(s)':>12}  {'Energy(J)':>12}  {'Seed':>10}")
print("-" * 65)
for r in rows:
    fog = "F2" if r["Device_ID"] < 91 else "F3"
    print(f"{r['Device_ID']:>8}  {fog:>4}  {r['CPU_Time_s']:>12.6f}  {r['Energy_J']:>12.6f}  {r['Seed']:>10}")

cpu_times = [r["CPU_Time_s"] for r in rows]
energies  = [r["Energy_J"]  for r in rows]
if rows:
    print("-" * 65)
    print(f"{'Min':>8}  {'':>4}  {min(cpu_times):>12.6f}  {min(energies):>12.6f}")
    print(f"{'Max':>8}  {'':>4}  {max(cpu_times):>12.6f}  {max(energies):>12.6f}")
    print(f"{'Avg':>8}  {'':>4}  {sum(cpu_times)/len(cpu_times):>12.6f}  {sum(energies)/len(energies):>12.6f}")
    print(f"{'='*65}")

# Write CSV
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Device_ID", "Fog_ID", "CPU_Time_s", "Energy_J", "Seed"])
    writer.writeheader()
    writer.writerows(rows)
print(f"\nSaved {len(rows)} rows to {OUT_CSV}")
