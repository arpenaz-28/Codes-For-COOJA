#!/usr/bin/env python3
"""
06-parse-hw-metrics.py — Parse HW_METRIC lines from role logs into a CSV.

Usage:
  python3 scripts/06-parse-hw-metrics.py <log.txt> <output.csv>

Handles all three LAAKA roles:
  NODE  — phases: register, auth, ack, data
  FOG   — phases: register, auth, ack, data
  RA    — phases: register

Missing phases default to 0.
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

            def ph(name, key, default=0):
                return phases.get(name, {}).get(key, default)

            row = {
                "Device_ID":           obj.get("device_id", ""),
                "Role":                obj.get("role", ""),
                # Registration
                "Register_Wall_s":     ph("register", "wall_s",   0.0),
                "Register_CPU_s":      ph("register", "cpu_s",    0.0),
                "Register_Tx_Bytes":   ph("register", "tx_bytes",   0),
                "Register_Rx_Bytes":   ph("register", "rx_bytes",   0),
                "Register_Energy_J":   ph("register", "energy_j", 0.0),
                # Authentication
                "Auth_Wall_s":         ph("auth",     "wall_s",   0.0),
                "Auth_CPU_s":          ph("auth",     "cpu_s",    0.0),
                "Auth_Tx_Bytes":       ph("auth",     "tx_bytes",   0),
                "Auth_Rx_Bytes":       ph("auth",     "rx_bytes",   0),
                "Auth_Energy_J":       ph("auth",     "energy_j", 0.0),
                # Acknowledgement
                "Ack_Wall_s":          ph("ack",      "wall_s",   0.0),
                "Ack_CPU_s":           ph("ack",      "cpu_s",    0.0),
                "Ack_Tx_Bytes":        ph("ack",      "tx_bytes",   0),
                "Ack_Rx_Bytes":        ph("ack",      "rx_bytes",   0),
                "Ack_Energy_J":        ph("ack",      "energy_j", 0.0),
                # Data loop
                "Data_Wall_s":         ph("data",     "wall_s",   0.0),
                "Data_CPU_s":          ph("data",     "cpu_s",    0.0),
                "Data_Tx_Bytes":       ph("data",     "tx_bytes",   0),
                "Data_Rx_Bytes":       ph("data",     "rx_bytes",   0),
                "Data_Energy_J":       ph("data",     "energy_j", 0.0),
                # Totals
                "Total_Wall_s":        totals.get("wall_s",   0.0),
                "Total_CPU_s":         totals.get("cpu_s",    0.0),
                "Total_Tx_Bytes":      totals.get("tx_bytes",   0),
                "Total_Rx_Bytes":      totals.get("rx_bytes",   0),
                "Total_Energy_J":      totals.get("energy_j", 0.0),
            }
            rows.append(row)
    return rows


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/06-parse-hw-metrics.py <log.txt> <output.csv>")
        return 1

    log_path = Path(sys.argv[1])
    out_csv  = Path(sys.argv[2])

    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        return 2

    rows = parse_metrics(log_path)
    if not rows:
        print(f"No HW_METRIC rows found in {log_path.name}")
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
