#!/usr/bin/env python3
"""
06-parse-hw-metrics.py — Extract HW_METRIC rows from log files and write CSV.

Usage:
  python3 scripts/06-parse-hw-metrics.py <log-file> <output.csv>

Example:
  python3 scripts/06-parse-hw-metrics.py results/user.log results/hw_metrics_user.csv
  python3 scripts/06-parse-hw-metrics.py results/sn.log   results/hw_metrics_sn.csv
"""
import csv
import json
import sys
from pathlib import Path


def parse_metrics(log_path: Path):
    rows = []
    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("HW_METRIC|"):
                continue
            payload = line.split("|", 1)[1]
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue

            phases = obj.get("phases", {})
            totals = obj.get("totals", {})
            row = {
                "Device_ID":      obj.get("device_id", ""),
                "Role":           obj.get("role", ""),
                # Enrollment
                "Enroll_Wall_s":  phases.get("enroll", {}).get("wall_s",   0.0),
                "Enroll_CPU_s":   phases.get("enroll", {}).get("cpu_s",    0.0),
                "Enroll_Tx_B":    phases.get("enroll", {}).get("tx_bytes", 0),
                "Enroll_Rx_B":    phases.get("enroll", {}).get("rx_bytes", 0),
                "Enroll_Energy_J":phases.get("enroll", {}).get("energy_j", 0.0),
                # Auth (M1 send + M1_ACK recv for User; M2 recv + M3 reply for SN)
                "Auth_Wall_s":    phases.get("auth", {}).get("wall_s",   0.0),
                "Auth_CPU_s":     phases.get("auth", {}).get("cpu_s",    0.0),
                "Auth_Tx_B":      phases.get("auth", {}).get("tx_bytes", 0),
                "Auth_Rx_B":      phases.get("auth", {}).get("rx_bytes", 0),
                "Auth_Energy_J":  phases.get("auth", {}).get("energy_j", 0.0),
                # Key Exchange (M4 recv + verify for User; 0 for SN)
                "KeyEx_Wall_s":   phases.get("keyex", {}).get("wall_s",   0.0),
                "KeyEx_CPU_s":    phases.get("keyex", {}).get("cpu_s",    0.0),
                "KeyEx_Tx_B":     phases.get("keyex", {}).get("tx_bytes", 0),
                "KeyEx_Rx_B":     phases.get("keyex", {}).get("rx_bytes", 0),
                "KeyEx_Energy_J": phases.get("keyex", {}).get("energy_j", 0.0),
                # Data (User only)
                "Data_Wall_s":    phases.get("data", {}).get("wall_s",   0.0),
                "Data_CPU_s":     phases.get("data", {}).get("cpu_s",    0.0),
                "Data_Tx_B":      phases.get("data", {}).get("tx_bytes", 0),
                "Data_Rx_B":      phases.get("data", {}).get("rx_bytes", 0),
                "Data_Energy_J":  phases.get("data", {}).get("energy_j", 0.0),
                # Totals
                "Total_Wall_s":   totals.get("wall_s",   0.0),
                "Total_CPU_s":    totals.get("cpu_s",    0.0),
                "Total_Tx_B":     totals.get("tx_bytes", 0),
                "Total_Rx_B":     totals.get("rx_bytes", 0),
                "Total_Energy_J": totals.get("energy_j", 0.0),
            }
            rows.append(row)
    return rows


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 06-parse-hw-metrics.py <log-file> <output.csv>")
        return 1

    log_path = Path(sys.argv[1])
    out_csv  = Path(sys.argv[2])

    rows = parse_metrics(log_path)
    if not rows:
        print(f"No HW_METRIC rows found in {log_path}")
        return 2

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} row(s) to {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
