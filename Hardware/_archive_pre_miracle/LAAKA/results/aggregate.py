#!/usr/bin/env python3
"""
Aggregate LAAKA scheme hardware runs into summary CSVs and JSON.
Reads all run_NN.json files in this directory.

Outputs:
  laaka_hw_all_rounds.csv   — per-run, per-round raw data
  laaka_hw_summary.csv      — per-run aggregate (enrollment + avg auth+ack/round)
  laaka_hw_aggregate.csv    — cross-run mean ± 95% CI (use for paper)
  laaka_hw_aggregate.json   — same, machine-readable
"""
import json, csv, os, glob, statistics, math

HERE = os.path.dirname(os.path.abspath(__file__))

run_files = sorted(glob.glob(os.path.join(HERE, "run_*.json")))
if not run_files:
    raise SystemExit("No run_*.json files found")

print(f"Found {len(run_files)} runs: {[os.path.basename(f) for f in run_files]}")

runs = []
for path in run_files:
    with open(path) as f:
        runs.append(json.load(f))

# ── Per-run, per-round CSV ─────────────────────────────────────────────────────
all_rounds_path = os.path.join(HERE, "laaka_hw_all_rounds.csv")
with open(all_rounds_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Run", "Phase",
                "AA_Wall_s", "AA_Energy_J",
                "Auth_Wall_s", "Auth_Energy_J",
                "Ack_Wall_s", "Ack_Energy_J",
                "Data_Wall_s", "Data_Energy_J",
                "Total_Wall_s", "Total_Energy_J"])
    for ri, run in enumerate(runs, 1):
        enr = run["enrollment"]
        w.writerow([ri, "Enrollment",
                    "", "", "", "", "", "", "", "",
                    enr["wall_s"], enr["energy_j"]])
        for rnd in run["rounds"]:
            w.writerow([ri, rnd["phase"],
                        rnd["aa_s"],    rnd["aa_energy_j"],
                        rnd["auth_s"],  rnd["auth_energy_j"],
                        rnd["ack_s"],   rnd["ack_energy_j"],
                        rnd["data_s"],  rnd["data_energy_j"],
                        rnd["total_s"], rnd["total_energy_j"]])
print(f"Written: {all_rounds_path}")

# ── Per-run summary CSV ────────────────────────────────────────────────────────
summary_path = os.path.join(HERE, "laaka_hw_summary.csv")
with open(summary_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Run",
                "Enroll_Wall_s", "Enroll_Energy_J",
                "AA_Sum_J", "AA_Sum_s",
                "AA_Avg_J", "AA_Avg_s"])
    for ri, run in enumerate(runs, 1):
        s   = run["summary"]
        enr = run["enrollment"]
        w.writerow([ri,
                    round(enr["wall_s"],   4), round(enr["energy_j"], 6),
                    round(s["aa_energy_sum_j"], 6), round(s["aa_time_sum_s"], 6),
                    round(s["avg_aa_energy_j"], 6), round(s["avg_aa_time_s"], 6)])
print(f"Written: {summary_path}")

# ── Cross-run aggregate ────────────────────────────────────────────────────────
def ci95(vals):
    if len(vals) < 2: return 0.0
    return 1.96 * statistics.stdev(vals) / math.sqrt(len(vals))

enroll_energies = [r["enrollment"]["energy_j"] for r in runs]
enroll_times    = [r["enrollment"]["wall_s"]   for r in runs]
aa_avgs_j       = [r["summary"]["avg_aa_energy_j"] for r in runs]
aa_avgs_s       = [r["summary"]["avg_aa_time_s"]   for r in runs]
aa_sums_j       = [r["summary"]["aa_energy_sum_j"] for r in runs]
aa_sums_s       = [r["summary"]["aa_time_sum_s"]   for r in runs]

agg = {
    "num_runs":               len(runs),
    "enroll_energy_mean_j":   round(statistics.mean(enroll_energies), 6),
    "enroll_energy_ci_j":     round(ci95(enroll_energies), 6),
    "enroll_time_mean_s":     round(statistics.mean(enroll_times), 6),
    "enroll_time_ci_s":       round(ci95(enroll_times), 6),
    "aa_avg_energy_mean_j":   round(statistics.mean(aa_avgs_j), 6),
    "aa_avg_energy_ci_j":     round(ci95(aa_avgs_j), 6),
    "aa_avg_time_mean_s":     round(statistics.mean(aa_avgs_s), 6),
    "aa_avg_time_ci_s":       round(ci95(aa_avgs_s), 6),
    "aa_sum_energy_mean_j":   round(statistics.mean(aa_sums_j), 6),
    "aa_sum_time_mean_s":     round(statistics.mean(aa_sums_s), 6),
}

agg_json_path = os.path.join(HERE, "laaka_hw_aggregate.json")
with open(agg_json_path, "w") as f:
    json.dump(agg, f, indent=2)

agg_csv_path = os.path.join(HERE, "laaka_hw_aggregate.csv")
with open(agg_csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Metric", "Mean", "CI_95", "Unit"])
    w.writerow(["Enrollment_Energy",  agg["enroll_energy_mean_j"],  agg["enroll_energy_ci_j"],  "J"])
    w.writerow(["Enrollment_Time",    agg["enroll_time_mean_s"],    agg["enroll_time_ci_s"],    "s"])
    w.writerow(["AuthAck_Avg_Energy", agg["aa_avg_energy_mean_j"],  agg["aa_avg_energy_ci_j"],  "J/round"])
    w.writerow(["AuthAck_Avg_Time",   agg["aa_avg_time_mean_s"],    agg["aa_avg_time_ci_s"],    "s/round"])
print(f"Written: {agg_csv_path}")

print()
print("=" * 60)
print(f"AGGREGATE SUMMARY ({agg['num_runs']} runs, 1 warm-up discarded each)")
print("=" * 60)
print(f"  Enrollment energy : {agg['enroll_energy_mean_j']:.4f} J  (±{agg['enroll_energy_ci_j']:.4f})")
print(f"  Enrollment time   : {agg['enroll_time_mean_s']:.4f} s  (±{agg['enroll_time_ci_s']:.4f})")
print(f"  Auth+Ack /round   : {agg['aa_avg_energy_mean_j']:.4f} J  (±{agg['aa_avg_energy_ci_j']:.4f})")
print(f"  Auth+Ack /round   : {agg['aa_avg_time_mean_s']:.4f} s  (±{agg['aa_avg_time_ci_s']:.4f})")
print()
print("Use for plot_hw_comparison.py:")
print(f"  _ENERGY_SUM_J['LAAKA'] = {agg['aa_sum_energy_mean_j']:.4f}")
print(f"  _TIME_SUM_S['LAAKA']   = {agg['aa_sum_time_mean_s']:.4f}")
