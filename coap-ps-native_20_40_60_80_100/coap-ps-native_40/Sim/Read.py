import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "2Server_5.txt")

START_NODE = 33
END_NODE = 40

# Totals
reg_cpu = reg_energy = 0.0
auth_cpu = auth_energy = 0.0
sess_cpu = sess_energy = 0.0
sesu_cpu = sesu_energy = 0.0   # ✅ FIX: initialized

# Regex patterns
reg_pattern = re.compile(
    r"ID:(\d+).*registration.*are\s+([\d.]+)\s+and\s+([\d.]+)",
    re.IGNORECASE
)

auth_pattern = re.compile(
    r"ID:(\d+).*authentication.*are\s+([\d.]+)\s+and\s+([\d.]+)",
    re.IGNORECASE
)

# More specific FIRST (to avoid overlap)
sesu_pattern = re.compile(
    r"ID:(\d+).*session\s*key\s*update.*are\s+([\d.]+)\s+and\s+([\d.]+)",
    re.IGNORECASE
)

sess_pattern = re.compile(
    r"ID:(\d+).*session\s*key\s*sharing.*are\s+([\d.]+)\s+and\s+([\d.]+)",
    re.IGNORECASE
)

with open(LOG_FILE, "r") as f:
    for line in f:

        # REGISTRATION
        match = reg_pattern.search(line)
        if match:
            node_id = int(match.group(1))
            if START_NODE <= node_id <= END_NODE:
                reg_cpu += float(match.group(2))
                reg_energy += float(match.group(3))

        # AUTHENTICATION
        match = auth_pattern.search(line)
        if match:
            node_id = int(match.group(1))
            if START_NODE <= node_id <= END_NODE:
                auth_cpu += float(match.group(2))
                auth_energy += float(match.group(3))

        # SESSION KEY UPDATE (checked BEFORE sharing)
        match = sesu_pattern.search(line)
        if match:
            node_id = int(match.group(1))
            if START_NODE <= node_id <= END_NODE:
                sesu_cpu += float(match.group(2))
                sesu_energy += float(match.group(3))

        # SESSION KEY SHARING
        match = sess_pattern.search(line)
        if match:
            node_id = int(match.group(1))
            if START_NODE <= node_id <= END_NODE:
                sess_cpu += float(match.group(2))
                sess_energy += float(match.group(3))

n=8
print("Nodes 81–100 Summary")
print("---------------------")

print("\n[Registration]")
print(f"CPU Time : {reg_cpu/n:.6f} sec")
print(f"Energy   : {reg_energy/n:.6f} J")

print("\n[Authentication]")
print(f"CPU Time : {auth_cpu/n:.6f} sec")
print(f"Energy   : {auth_energy/n:.6f} J")

print("\n[Session Key Sharing]")
print(f"CPU Time : {sess_cpu/n:.6f} sec")
print(f"Energy   : {sess_energy/n:.6f} J")

print("\n[Session Key Update]")
print(f"CPU Time : {sesu_cpu/n:.6f} sec")
print(f"Energy   : {sesu_energy/n:.6f} J")
