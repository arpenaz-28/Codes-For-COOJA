"""
Extract and summarize desync demonstration results from COOJA log.
Parses DESYNC_LOG lines to show the 4-round sequence per device.
"""
import re
import csv
from collections import defaultdict

LOG_FILE = "COOJA-desync-testlog.txt"
CSV_FILE = "desync-results.csv"

# Parse all DESYNC_LOG lines
events = []
with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if "DESYNC_LOG" not in line:
            continue
        # Extract timestamp from start (e.g. "25066880 3 DESYNC_LOG|...")
        m = re.match(r"(\d+)\s+(\d+)\s+(DESYNC_LOG\|.+)", line)
        if m:
            ts_us = int(m.group(1))
            node = int(m.group(2))
            msg = m.group(3)
            events.append((ts_us, node, msg))

# Group by device node (3, 4, 5)
device_events = defaultdict(list)
for ts, node, msg in events:
    if "Node " in msg:
        # Extract device ID from msg
        dm = re.search(r"Node (\d+)", msg)
        if dm:
            did = int(dm.group(1))
            device_events[did].append((ts, msg))

# Track round results per device
results = []
for did in sorted(device_events.keys()):
    dev_data = {"Device": did}
    for ts, msg in device_events[did]:
        # Round results
        if "Round 1|RESULT:" in msg:
            dev_data["Round1"] = "SUCCESS" if "SUCCESS" in msg else "FAILED"
            dev_data["Round1_ts"] = ts / 1e6
        elif "Round 2|RESULT:" in msg:
            dev_data["Round2"] = "DESYNCHRONIZED" if "DESYNCHRONIZED" in msg else "?"
            dev_data["Round2_ts"] = ts / 1e6
        elif "Round 3|RESULT:" in msg:
            dev_data["Round3"] = "RECOVERY SUCCESS" if "RECOVERY SUCCESSFUL" in msg else "RECOVERY FAILED"
            dev_data["Round3_ts"] = ts / 1e6
        elif "Round 4|RESULT:" in msg:
            dev_data["Round4"] = "SUCCESS" if "SUCCESS" in msg else "FAILED"
            dev_data["Round4_ts"] = ts / 1e6
        # PID tracking  
        elif "ENROLLMENT COMPLETE" in msg:
            pm = re.search(r"Initial PID=([0-9a-f]+)", msg)
            if pm:
                dev_data["PID_initial"] = pm.group(1)
        elif "SIMULATED DROP" in msg:
            pm = re.search(r"OLD PID=([0-9a-f]+)", msg)
            if pm:
                dev_data["PID_at_drop"] = pm.group(1)
        elif "Round 3|Auth OK" in msg:
            pm = re.search(r"New PID=([0-9a-f]+)", msg)
            if pm:
                dev_data["PID_after_recovery"] = pm.group(1)
    results.append(dev_data)

# AS-side recovery details
as_recovery = []
for ts, node, msg in events:
    if "DESYNC RECOVERY PATH" in msg:
        dm = re.search(r"device (\d+)", msg)
        if dm:
            as_recovery.append((ts / 1e6, int(dm.group(1))))

# Print summary
print("=" * 70)
print("DESYNC DEMONSTRATION RESULTS")
print("=" * 70)
print()

for r in results:
    did = r["Device"]
    print(f"Device {did}:")
    print(f"  Initial PID:        {r.get('PID_initial', '?')}")
    print(f"  Round 1 (Normal):   {r.get('Round1', '?'):20s} @ {r.get('Round1_ts', 0):.2f}s")
    print(f"  Round 2 (Drop):     {r.get('Round2', '?'):20s} @ {r.get('Round2_ts', 0):.2f}s")
    print(f"    PID at drop:      {r.get('PID_at_drop', '?')}")
    print(f"  Round 3 (Recovery): {r.get('Round3', '?'):20s} @ {r.get('Round3_ts', 0):.2f}s")
    print(f"    PID after recov:  {r.get('PID_after_recovery', '?')}")
    print(f"  Round 4 (Confirm):  {r.get('Round4', '?'):20s} @ {r.get('Round4_ts', 0):.2f}s")
    print()

print("-" * 70)
print("AS-Side Recovery Events (PID_old matched):")
for ts, did in as_recovery:
    print(f"  Device {did} recovered at {ts:.2f}s")

print()
print("-" * 70)
all_recovered = all(r.get("Round3") == "RECOVERY SUCCESS" for r in results)
all_confirmed = all(r.get("Round4") == "SUCCESS" for r in results)
print(f"Total devices:              {len(results)}")
print(f"All desync triggered:       {all(r.get('Round2') == 'DESYNCHRONIZED' for r in results)}")
print(f"All recovery successful:    {all_recovered}")
print(f"All post-recovery normal:   {all_confirmed}")
print(f"DUAL-STATE STORAGE WORKS:   {'YES' if all_recovered and all_confirmed else 'NO'}")
print("=" * 70)

# Write CSV
with open(CSV_FILE, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Device", "Round", "Result", "Time_s", "PID_Before", "PID_After"])
    for r in results:
        did = r["Device"]
        w.writerow([did, "1-Normal", r.get("Round1", ""), f"{r.get('Round1_ts', 0):.2f}", r.get("PID_initial", ""), ""])
        w.writerow([did, "2-Drop", r.get("Round2", ""), f"{r.get('Round2_ts', 0):.2f}", r.get("PID_at_drop", ""), ""])
        w.writerow([did, "3-Recovery", r.get("Round3", ""), f"{r.get('Round3_ts', 0):.2f}", r.get("PID_at_drop", ""), r.get("PID_after_recovery", "")])
        w.writerow([did, "4-Confirm", r.get("Round4", ""), f"{r.get('Round4_ts', 0):.2f}", "", ""])

print(f"\nResults saved to {CSV_FILE}")
