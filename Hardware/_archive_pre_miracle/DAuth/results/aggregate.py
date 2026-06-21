#!/usr/bin/env python3
"""
Aggregate DAuth hardware simulation runs into summary CSV.
Reads all run_NN.json files in this directory.
Outputs:
  dauth_hw_all_rounds.csv   — per-run, per-round raw data
  dauth_hw_summary.csv      — per-run aggregate (enrollment + avg auth/round)
  dauth_hw_aggregate.csv    — cross-run mean ± std for paper
"""

import json, csv, os, glob, statistics, math

HERE = os.path.dirname(os.path.abspath(__file__))

run_files = sorted(glob.glob(os.path.join(HERE, "run_*.json")))
if not run_files:
    raise SystemExit("No run_*.json files found")

print(f"Found {len(run_files)} runs: {[os.path.basename(f) for f in run_files]}")

# ── Load all runs ──────────────────────────────────────────────────────────────
runs = []
for path in run_files:
    with open(path) as f:
        runs.append(json.load(f))

# ── Write per-run, per-round CSV ───────────────────────────────────────────────
all_rounds_path = os.path.join(HERE, "dauth_hw_all_rounds.csv")
with open(all_rounds_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Run", "Phase",
                "Wall_s", "CPU_s",
                "AK_Wall_s", "AK_Energy_J",
                "Auth_Wall_s", "Auth_Energy_J",
                "KeyEx_Wall_s", "KeyEx_Energy_J",
                "Data_Wall_s", "Data_Energy_J",
                "Total_Wall_s", "Total_Energy_J"])
    for ri, run in enumerate(runs, 1):
        enr = run["enrollment"]
        w.writerow([ri, "Enrollment",
                    enr["wall_s"], enr["cpu_s"],
                    "", "", "", "", "", "", "", "",
                    enr["wall_s"], enr["energy_j"]])
        for rnd in run["rounds"]:
            w.writerow([ri, rnd["phase"],
                        rnd["ak_s"], "",
                        rnd["ak_s"],    rnd["ak_energy_j"],
                        rnd["auth_s"],  rnd["auth_energy_j"],
                        rnd["ke_s"],    rnd["ke_energy_j"],
                        rnd["data_s"],  rnd["data_energy_j"],
                        rnd["total_s"], rnd["total_energy_j"]])

print(f"Written: {all_rounds_path}")

# ── Per-run summary ────────────────────────────────────────────────────────────
summary_path = os.path.join(HERE, "dauth_hw_summary.csv")
with open(summary_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Run",
                "Enroll_Wall_s", "Enroll_Energy_J",
                "AK_Sum_J", "AK_Sum_s",
                "AK_Avg_J", "AK_Avg_s",
                "Total_Avg_J", "Total_Avg_s"])
    for ri, run in enumerate(runs, 1):
        s = run["summary"]
        enr = run["enrollment"]
        w.writerow([ri,
                    round(enr["wall_s"],   4), round(enr["energy_j"], 6),
                    round(s["ak_energy_sum_j"], 6), round(s["ak_time_sum_s"], 6),
                    round(s["avg_ak_energy_j"], 6), round(s["avg_ak_time_s"], 6),
                    round(s["total_energy_sum_j"] / len(run["rounds"]), 6),
                    round(s["total_time_sum_s"]   / len(run["rounds"]), 6)])

print(f"Written: {summary_path}")

# ── Cross-run aggregate ────────────────────────────────────────────────────────
enroll_energies = [r["enrollment"]["energy_j"] for r in runs]
enroll_times    = [r["enrollment"]["wall_s"]   for r in runs]
ak_avgs_j       = [r["summary"]["avg_ak_energy_j"] for r in runs]
ak_avgs_s       = [r["summary"]["avg_ak_time_s"]   for r in runs]
ak_sums_j       = [r["summary"]["ak_energy_sum_j"] for r in runs]
ak_sums_s       = [r["summary"]["ak_time_sum_s"]   for r in runs]
tot_avgs_j      = [r["summary"]["total_energy_sum_j"] / len(r["rounds"]) for r in runs]
tot_avgs_s      = [r["summary"]["total_time_sum_s"]   / len(r["rounds"]) for r in runs]

def ci95(vals):
    if len(vals) < 2: return 0.0
    return 1.96 * statistics.stdev(vals) / math.sqrt(len(vals))

agg = {
    "num_runs":           len(runs),
    "enroll_energy_mean_j": round(statistics.mean(enroll_energies), 6),
    "enroll_energy_ci_j":   round(ci95(enroll_energies), 6),
    "enroll_time_mean_s":   round(statistics.mean(enroll_times), 6),
    "enroll_time_ci_s":     round(ci95(enroll_times), 6),
    "ak_avg_energy_mean_j": round(statistics.mean(ak_avgs_j), 6),
    "ak_avg_energy_ci_j":   round(ci95(ak_avgs_j), 6),
    "ak_avg_time_mean_s":   round(statistics.mean(ak_avgs_s), 6),
    "ak_avg_time_ci_s":     round(ci95(ak_avgs_s), 6),
    "ak_sum_energy_mean_j": round(statistics.mean(ak_sums_j), 6),
    "ak_sum_time_mean_s":   round(statistics.mean(ak_sums_s), 6),
    "total_avg_energy_mean_j": round(statistics.mean(tot_avgs_j), 6),
    "total_avg_time_mean_s":   round(statistics.mean(tot_avgs_s), 6),
}

agg_path = os.path.join(HERE, "dauth_hw_aggregate.json")
with open(agg_path, "w") as f:
    json.dump(agg, f, indent=2)

agg_csv_path = os.path.join(HERE, "dauth_hw_aggregate.csv")
with open(agg_csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Metric", "Mean", "CI_95", "Unit"])
    w.writerow(["Enrollment_Energy",   agg["enroll_energy_mean_j"], agg["enroll_energy_ci_j"], "J"])
    w.writerow(["Enrollment_Time",     agg["enroll_time_mean_s"],   agg["enroll_time_ci_s"],   "s"])
    w.writerow(["AuthKeyEx_Avg_Energy",agg["ak_avg_energy_mean_j"], agg["ak_avg_energy_ci_j"], "J/round"])
    w.writerow(["AuthKeyEx_Avg_Time",  agg["ak_avg_time_mean_s"],   agg["ak_avg_time_ci_s"],   "s/round"])
    w.writerow(["Total_Avg_Energy",    agg["total_avg_energy_mean_j"], "", "J/round"])
    w.writerow(["Total_Avg_Time",      agg["total_avg_time_mean_s"],   "", "s/round"])

print(f"Written: {agg_csv_path}")
print()
print("=" * 60)
print("AGGREGATE SUMMARY (3 runs, 1 warm-up round discarded each)")
print("=" * 60)
print(f"  Enrollment energy : {agg['enroll_energy_mean_j']:.4f} J  (±{agg['enroll_energy_ci_j']:.4f})")
print(f"  Enrollment time   : {agg['enroll_time_mean_s']:.4f} s  (±{agg['enroll_time_ci_s']:.4f})")
print(f"  Auth+KeyEx /round : {agg['ak_avg_energy_mean_j']:.4f} J  (±{agg['ak_avg_energy_ci_j']:.4f})")
print(f"  Auth+KeyEx /round : {agg['ak_avg_time_mean_s']:.4f} s  (±{agg['ak_avg_time_ci_s']:.4f})")
print(f"  Total /round      : {agg['total_avg_energy_mean_j']:.4f} J")
print(f"  Total /round      : {agg['total_avg_time_mean_s']:.4f} s")
print()
print("Use for plot_hw_comparison.py:")
print(f"  _ENERGY_SUM_J['DAuth'] = {agg['ak_sum_energy_mean_j']:.4f}")
print(f"  _TIME_SUM_S['DAuth']   = {agg['ak_sum_time_mean_s']:.4f}")
print()
print("Use for plot_hw_with_enrollment.py:")
print(f"  ENROLL_ENERGY_J['DAuth'] = {agg['enroll_energy_mean_j']:.4f}")
print(f"  ENROLL_TIME_S['DAuth']   = {agg['enroll_time_mean_s']:.4f}")
print(f"  AUTH_ENERGY_J['DAuth']   = {agg['ak_avg_energy_mean_j']:.4f}")
print(f"  AUTH_TIME_S['DAuth']     = {agg['ak_avg_time_mean_s']:.4f}")
