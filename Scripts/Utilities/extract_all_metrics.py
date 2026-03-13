"""Extract enrollment, key-exchange, and authentication energy metrics from COOJA log.
Works for Base Scheme, LAAKA, and Extended Scheme.
Usage: python extract_all_metrics.py <logfile>
"""
import re, csv, sys, os

logfile = sys.argv[1] if len(sys.argv) > 1 else "COOJA-allmetrics-testlog.txt"

enroll = []
keyex  = []
auth   = []

with open(logfile, "r", errors="replace") as f:
    for line in f:
        # ENROLL_ENERGY|<id>|cpu_s=<v>|energy_j=<v>
        m = re.search(r"ENROLL_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)", line)
        if m:
            enroll.append({"Device_ID": int(m.group(1)), "CPU_Time_s": float(m.group(2)), "Energy_J": float(m.group(3))})
            continue

        # KEYEX_ENERGY|<id>|cpu_s=<v>|energy_j=<v>
        m = re.search(r"KEYEX_ENERGY\|(\d+)\|cpu_s=([\d.]+)\|energy_j=([\d.]+)", line)
        if m:
            keyex.append({"Device_ID": int(m.group(1)), "CPU_Time_s": float(m.group(2)), "Energy_J": float(m.group(3))})
            continue

        # AUTH_ENERGY|<id>|... format
        m = re.search(r"AUTH_ENERGY\|(\d+)\|.*cpu_s=([\d.]+)\|energy_j=([\d.]+)", line)
        if m:
            auth.append({"Device_ID": int(m.group(1)), "CPU_Time_s": float(m.group(2)), "Energy_J": float(m.group(3))})
            continue

        # Base scheme auth format: "authentication N for client ID are CPU and ENERGY"
        m = re.search(r"authentication \d+ for client (\d+) are ([\d.]+) and ([\d.]+)", line)
        if m:
            auth.append({"Device_ID": int(m.group(1)), "CPU_Time_s": float(m.group(2)), "Energy_J": float(m.group(3))})

outdir = os.path.dirname(os.path.abspath(logfile))

def write_csv(name, rows):
    path = os.path.join(outdir, name)
    if not rows:
        print(f"  {name}: 0 entries (skipped)")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Device_ID", "CPU_Time_s", "Energy_J"])
        w.writeheader()
        w.writerows(rows)
    avg_cpu = sum(r["CPU_Time_s"] for r in rows) / len(rows)
    avg_e   = sum(r["Energy_J"]   for r in rows) / len(rows)
    print(f"  {name}: {len(rows)} entries, Avg CPU={avg_cpu:.4f}s, Avg Energy={avg_e:.4f}J")

print(f"Parsed {logfile}:")
write_csv("enroll-results.csv", enroll)
write_csv("keyex-results.csv",  keyex)
write_csv("auth-results.csv",   auth)
