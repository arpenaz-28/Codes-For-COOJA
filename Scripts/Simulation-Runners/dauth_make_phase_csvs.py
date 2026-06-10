#!/usr/bin/env python3
"""
dauth_make_phase_csvs.py
==================================================================
Convert DAuth-Sweep seed_results.csv files into the per-device, seed-averaged
phase CSVs (enroll-results.csv / auth-results.csv / keyex-results.csv) that
plot_network_variation.py's load_raw_total() expects.

Columns produced: Device_ID, Energy_J, CPU_Time_s  (energy in Joules).

Scans:  Results/COOJA-Simulation/DAuth-Sweep/network-variation/N*/csv/seed_results.csv
Writes: <same dir>/{enroll,auth,keyex}-results.csv
"""

import csv, glob, os, statistics

REPO = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
ROOTS = [
    os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep", "network-variation"),
    os.path.join(REPO, "Results", "COOJA-Simulation", "DAuth-Sweep", "as-variation"),
]

PHASES = [
    ("enroll-results.csv", "Enroll_Energy_mJ", "Enroll_CPU_s"),
    ("auth-results.csv",   "Auth_Energy_mJ",   "Auth_CPU_s"),
    ("keyex-results.csv",  "Keyex_Energy_mJ",  "Keyex_CPU_s"),
]


def process(seed_csv):
    csv_dir = os.path.dirname(seed_csv)
    rows = list(csv.DictReader(open(seed_csv, encoding="utf-8")))
    if not rows:
        print(f"  empty: {seed_csv}")
        return
    for fname, e_col, c_col in PHASES:
        # per-device lists across seeds
        per_dev_e, per_dev_c = {}, {}
        for r in rows:
            dev = int(r["Device"])
            per_dev_e.setdefault(dev, []).append(float(r[e_col]))
            per_dev_c.setdefault(dev, []).append(float(r[c_col]))
        out = os.path.join(csv_dir, fname)
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Device_ID", "Energy_J", "CPU_Time_s"])
            for dev in sorted(per_dev_e):
                e_mJ = statistics.mean(per_dev_e[dev])
                c_s  = statistics.mean(per_dev_c[dev])
                w.writerow([dev, f"{e_mJ/1000.0:.8f}", f"{c_s:.6f}"])
    print(f"  wrote phase CSVs in {csv_dir}  ({len(rows)} seed-rows, "
          f"{len(set(int(r['Device']) for r in rows))} devices)")


def main():
    found = 0
    for root in ROOTS:
        for seed_csv in glob.glob(os.path.join(root, "N*", "csv", "seed_results.csv")):
            process(seed_csv)
            found += 1
    print(f"Done. Processed {found} seed_results.csv files.")


if __name__ == "__main__":
    main()
