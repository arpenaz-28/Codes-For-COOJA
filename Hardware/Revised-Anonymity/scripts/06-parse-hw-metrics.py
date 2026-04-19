#!/usr/bin/env python3
"""
06-parse-hw-metrics.py — Parse HW_METRIC lines from node log into a CSV.

Usage:
  python3 scripts/06-parse-hw-metrics.py <node-log.txt> <output.csv>

Phases captured: enroll, auth, keyex, data  (mirrors Revised-Anonymity C phases)
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
                "Device_ID":        obj.get("device_id", ""),
                "Role":             obj.get("role", ""),
                # Enrollment
                "Enroll_Wall_s":    ph("enroll", "wall_s",   0.0),
                "Enroll_CPU_s":     ph("enroll", "cpu_s",    0.0),
                "Enroll_Tx_Bytes":  ph("enroll", "tx_bytes",   0),
                "Enroll_Rx_Bytes":  ph("enroll", "rx_bytes",   0),
                "Enroll_Energy_J":  ph("enroll", "energy_j", 0.0),
                # Round 1 — Auth
                "Auth_Wall_s":      ph("auth",   "wall_s",   0.0),
                "Auth_CPU_s":       ph("auth",   "cpu_s",    0.0),
                "Auth_Tx_Bytes":    ph("auth",   "tx_bytes",   0),
                "Auth_Rx_Bytes":    ph("auth",   "rx_bytes",   0),
                "Auth_Energy_J":    ph("auth",   "energy_j", 0.0),
                # Round 2 — Key Exchange
                "KeyEx_Wall_s":     ph("keyex",  "wall_s",   0.0),
                "KeyEx_CPU_s":      ph("keyex",  "cpu_s",    0.0),
                "KeyEx_Tx_Bytes":   ph("keyex",  "tx_bytes",   0),
                "KeyEx_Rx_Bytes":   ph("keyex",  "rx_bytes",   0),
                "KeyEx_Energy_J":   ph("keyex",  "energy_j", 0.0),
                # Data loop
                "Data_Wall_s":      ph("data",   "wall_s",   0.0),
                "Data_CPU_s":       ph("data",   "cpu_s",    0.0),
                "Data_Tx_Bytes":    ph("data",   "tx_bytes",   0),
                "Data_Rx_Bytes":    ph("data",   "rx_bytes",   0),
                "Data_Energy_J":    ph("data",   "energy_j", 0.0),
                # Totals
                "Total_Wall_s":     totals.get("wall_s",   0.0),
                "Total_CPU_s":      totals.get("cpu_s",    0.0),
                "Total_Tx_Bytes":   totals.get("tx_bytes",   0),
                "Total_Rx_Bytes":   totals.get("rx_bytes",   0),
                "Total_Energy_J":   totals.get("energy_j", 0.0),
            }
            rows.append(row)
    return rows


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/06-parse-hw-metrics.py <node-log.txt> <output.csv>")
        return 1

    log_path = Path(sys.argv[1])
    out_csv  = Path(sys.argv[2])

    rows = parse_metrics(log_path)
    if not rows:
        print("No HW_METRIC rows found in log.")
        return 2

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
