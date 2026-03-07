import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "9Server.txt")

START_NODE = 81
END_NODE = 100

total_cpu_time = 0.0
total_energy = 0.0

pattern = re.compile(
    r"ID:(\d+).*authentication\s+1.*are\s+([\d.]+)\s+and\s+([\d.]+)",
    re.IGNORECASE
)

with open(LOG_FILE, "r") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            node_id = int(match.group(1))
            if START_NODE <= node_id <= END_NODE:
                cpu_time = float(match.group(2))
                energy = float(match.group(3))

                total_cpu_time += cpu_time
                total_energy += energy

print("Authentication-1 (Nodes 81–100)")
print("--------------------------------")
print(f"Total CPU Time : {total_cpu_time:.6f} seconds")
print(f"Total Energy   : {total_energy:.6f} Joules")

