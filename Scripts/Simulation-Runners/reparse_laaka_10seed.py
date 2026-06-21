#!/usr/bin/env python3
"""
reparse_laaka_10seed.py
=======================
Re-parse existing LAAKA 10-seed log files with the corrected formula:

  total = enroll + AUTH    (KEYEX excluded — it is a sub-window of AUTH)

Overwrites:
  Results/COOJA-Simulation/10-Seed-Comparison/LAAKA/seed_results.csv
  Results/COOJA-Simulation/10-Seed-Comparison/LAAKA/summary.csv

No COOJA re-run needed: AUTH_ENERGY in the existing logs already captures
the full per-round cost (auth-req + ack + data).
"""
import csv, math, os, re, statistics

REPO     = "/home/apex/contiki-ng/examples/Codes-For-COOJA"
LOG_DIR  = os.path.join(REPO, "Results", "COOJA-Simulation",
                        "10-Seed-Comparison", "LAAKA", "logs")
OUT_DIR  = os.path.join(REPO, "Results", "COOJA-Simulation",
                        "10-Seed-Comparison", "LAAKA")
DEVICE_IDS = list(range(81, 101))

SEEDS = [123456, 234567, 345678, 456789, 567890,
         678901, 789012, 890123, 901234, 112345]

_PAT_ENROLL = re.compile(
    r'ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')
_PAT_AUTH = re.compile(
    r'AUTH_ENERGY\|(\d+)\|(?:cpu_ticks=[\d.eE+\-]+\|energy_ticks=[\d.eE+\-]+\|)?'
    r'cpu_s=([\d.eE+\-]+)\|energy_j=([\d.eE+\-]+)')


def parse_log(path):
    text   = open(path).read()
    enroll = {}
    auth_list = {}
    for m in _PAT_ENROLL.finditer(text):
        nid = int(m.group(1))
        if nid in DEVICE_IDS:
            enroll[nid] = (float(m.group(2)), float(m.group(3)))
    for m in _PAT_AUTH.finditer(text):
        nid = int(m.group(1))
        if nid in DEVICE_IDS:
            auth_list.setdefault(nid, []).append(
                (float(m.group(2)), float(m.group(3))))

    result = {}
    for nid in DEVICE_IDS:
        if nid not in enroll and nid not in auth_list:
            continue
        e_cpu, e_ej = enroll.get(nid, (0.0, 0.0))
        if auth_list.get(nid):
            rounds = auth_list[nid]
            a_cpu = statistics.mean(r[0] for r in rounds)
            a_ej  = statistics.mean(r[1] for r in rounds)
        else:
            a_cpu, a_ej = 0.0, 0.0
        result[nid] = {"enroll": (e_cpu, e_ej), "auth": (a_cpu, a_ej)}
    return result


def ci95(vals):
    n = len(vals)
    if n < 2:
        return 0.0
    return 1.96 * statistics.stdev(vals) / math.sqrt(n)


def main():
    all_records = {}
    for seed in SEEDS:
        log = os.path.join(LOG_DIR, f"testlog_seed{seed}.txt")
        if not os.path.exists(log):
            print(f"  MISSING: {log}")
            continue
        rec = parse_log(log)
        all_records[seed] = rec
        devs = sorted(rec)
        totals = [(rec[d]["enroll"][1] + rec[d]["auth"][1]) * 1000 for d in devs]
        print(f"  seed {seed}: {len(devs)} devices, mean total = {statistics.mean(totals):.2f} mJ")

    # Write seed_results.csv
    seed_csv = os.path.join(OUT_DIR, "seed_results.csv")
    with open(seed_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Seed", "Device",
                    "Enroll_Energy_mJ", "Enroll_CPU_s",
                    "Auth_Energy_mJ",   "Auth_CPU_s",
                    "Keyex_Energy_mJ",  "Keyex_CPU_s",
                    "Total_Energy_mJ",  "Total_CPU_s"])
        for seed in sorted(all_records):
            rec = all_records[seed]
            for dev in sorted(rec):
                en_cpu, en_ej = rec[dev]["enroll"]
                au_cpu, au_ej = rec[dev]["auth"]
                tot_ej  = (en_ej + au_ej) * 1000
                tot_cpu = en_cpu + au_cpu
                w.writerow([seed, dev,
                             f"{en_ej*1000:.4f}", f"{en_cpu:.6f}",
                             f"{au_ej*1000:.4f}", f"{au_cpu:.6f}",
                             "0.0000",            "0.000000",
                             f"{tot_ej:.4f}",     f"{tot_cpu:.6f}"])
    print(f"\n  seed_results.csv → {seed_csv}")

    # Write summary.csv
    dev_means = {}
    dev_cpu   = {}
    for seed, rec in all_records.items():
        for dev in sorted(rec):
            en_cpu, en_ej = rec[dev]["enroll"]
            au_cpu, au_ej = rec[dev]["auth"]
            tot_ej  = (en_ej + au_ej) * 1000
            tot_cpu = en_cpu + au_cpu
            dev_means.setdefault(dev, []).append(tot_ej)
            dev_cpu.setdefault(dev, []).append(tot_cpu)

    summary_csv = os.path.join(OUT_DIR, "summary.csv")
    with open(summary_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Device", "Mean_Total_Energy_mJ", "CI_Energy_mJ",
                    "Mean_Total_CPU_s", "CI_CPU_s", "Num_Seeds"])
        for dev in sorted(dev_means):
            evals = dev_means[dev]
            cvals = dev_cpu[dev]
            n = len(evals)
            e_mean = statistics.mean(evals)
            c_mean = statistics.mean(cvals)
            e_ci = ci95(evals)
            c_ci = ci95(cvals)
            w.writerow([dev, f"{e_mean:.4f}", f"{e_ci:.4f}",
                        f"{c_mean:.6f}", f"{c_ci:.6f}", n])
    print(f"  summary.csv      → {summary_csv}")

    # Overall mean
    all_e = [v for vals in dev_means.values() for v in vals]
    all_c = [v for vals in dev_cpu.values() for v in vals]
    print(f"\n  CORRECTED LAAKA — Device-level mean total energy : {statistics.mean(all_e):.2f} mJ")
    print(f"  CORRECTED LAAKA — Device-level mean CPU time     : {statistics.mean(all_c):.4f} s")
    print(f"  (Previously reported with double-counting: ~91.29 mJ)")


if __name__ == "__main__":
    main()
